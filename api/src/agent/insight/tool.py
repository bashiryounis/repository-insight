from src.utils.helper import get_embedding
from typing import Literal, Dict, List, Any
from src.core.db import get_session
import re



async def extract_node(node_name: str, node_label: Literal["File", "Folder", "Class", "Method"]) -> Dict[str, str]:
    """Useful to extract exactly one repository entity from the user query."""
    return {"node_label": node_label, "node_name": node_name}


async def search_graph(node_label: Literal["File", "Folder", "Class", "Method"], node_name: str ) -> str :
    """Usefull to search for spacific node in Graph databse"""
    top_k: int = 5
    name_embedding = get_embedding(node_name)  

    cypher = f"""
    CALL db.index.vector.queryNodes('{node_label.lower()}_embedding_name_index', $top_k, $embedding)
    YIELD node, score
    {f"WHERE '{node_label}' IN labels(node)" if node_label else ""}
    RETURN node.name AS name,node.description AS description,node.content AS content, score
    ORDER BY score DESC
    """

    async with get_session() as session:  # Assumes get_session can be used as context manager
        result = await session.run(cypher, {
            "embedding": name_embedding,
            "top_k": top_k
        })
        records = [r async for r in result]

    parts: List[str] = []
    for r in records:
        name = r["name"]
        desc = f": {r['description']}" if r.get("description") else ""
        content = r["content"].rstrip()      # trim any trailing whitespace
        parts.append(
            f"- **{name}**\n"
            f"**Description:** {desc}\n\n"
            f"**Code:**\n```\n{content}\n```\n"
        )

    return "\n".join(parts)


async def get_depend(filename: str, direction: Literal["out", "in"]) -> List[Dict[str, Any]]:
    """Get full node objects of dependencies related to a given file."""
    if direction == "out":
        cypher = """
        MATCH (f:File {name: $filename})-[:RELATED_TO]->(dep:File)
        RETURN dep AS node
        """
    else:
        cypher = """
        MATCH (f:File {name: $filename})<-[:RELATED_TO]-(dep:File)
        RETURN dep AS node
        """

    async with get_session() as session:
        result = await session.run(cypher, {"filename": filename.strip()})
        records = [r async for r in result]

    cleaned_nodes = []
    for record in records:
        node = record.values()[0]
        if hasattr(node, "items"):
            cleaned = {k: v for k, v in dict(node).items() if not k.startswith("embedding")}
            cleaned_nodes.append(cleaned)

    return cleaned_nodes

async def get_node_relationships_by_label(
    label: Literal["File", "Folder", "Class", "Method"],
    name: str,
    direction: Literal["out", "in", "both"],  
    relationship_type: Literal["CONTAINS", "RELATED_TO"],           
):
    """Fetch relationships of a node with the given label and name.
    Excludes any node properties that start with 'embedding'.
    """
    limit = 25
    rel_filter = f":{relationship_type}" if relationship_type else ""

    if direction == "out":
        cypher = f"""
        MATCH (n:{label} {{name: $name}})-[r{rel_filter}]->(m)
        RETURN type(r) AS rel_type, labels(m) AS target_labels, m AS target_node
        LIMIT $limit
        """
    elif direction == "in":
        cypher = f"""
        MATCH (m)-[r{rel_filter}]->(n:{label} {{name: $name}})
        RETURN type(r) AS rel_type, labels(m) AS target_labels, m AS target_node
        LIMIT $limit
        """
    else:  # both
        cypher = f"""
        MATCH (n:{label} {{name: $name}})
        OPTIONAL MATCH (n)-[r1{rel_filter}]->(m1)
        OPTIONAL MATCH (m2)-[r2{rel_filter}]->(n)
        RETURN 
            type(r1) AS out_rel, labels(m1) AS out_labels, m1 AS out_node,
            type(r2) AS in_rel, labels(m2) AS in_labels, m2 AS in_node
        LIMIT $limit
        """

    async with get_session() as session:
        result = await session.run(cypher, {"name": name, "limit": limit})
        records = [record async for record in result] 

    relationships = []

    for record in records:
        if direction in ("out", "both") and record.get("out_rel") and record.get("out_node"):
            node = {k: v for k, v in dict(record["out_node"]).items() if not k.startswith("embedding")}
            relationships.append({
                "direction": "out",
                "relationship_type": record["out_rel"],
                "target_labels": record["out_labels"],
                "target_node": node,
            })
        if direction in ("in", "both") and record.get("in_rel") and record.get("in_node"):
            node = {k: v for k, v in dict(record["in_node"]).items() if not k.startswith("embedding")}
            relationships.append({
                "direction": "in",
                "relationship_type": record["in_rel"],
                "target_labels": record["in_labels"],
                "target_node": node,
            })
        if direction in ("out", "in") and record.get("rel_type") and record.get("target_node"):
            node = {k: v for k, v in dict(record["target_node"]).items() if not k.startswith("embedding")}
            relationships.append({
                "direction": direction,
                "relationship_type": record["rel_type"],
                "target_labels": record["target_labels"],
                "target_node": node,
            })

    return relationships

async def find_path_between_nodes_by_label(
    start_label: Literal["File", "Folder", "Class", "Method"],
    start_name: str,
    end_label: Literal["File", "Folder", "Class", "Method"],
    end_name: str,
    relationship_filter: Literal["CONTAINS", "RELATED_TO"],
):
    """Finds the shortest path between two nodes via a specific relationship type and label."""
    max_depth = 5

    # Relationship filter must be injected directly into the Cypher query
    cypher = f"""
    MATCH path = shortestPath(
        (start:{start_label} {{name: $start_name}})-[:{relationship_filter}*..{max_depth}]-(end:{end_label} {{name: $end_name}})
    )
    RETURN nodes(path) AS nodes, relationships(path) AS relationships
    """

    async with get_session() as session:
        result = await session.run(cypher, {
            "start_name": start_name,
            "end_name": end_name
        })
        records = [record async for record in result]

    paths = []
    for record in records:
        node_path = [
            {k: v for k, v in dict(n).items() if not k.startswith("embedding")}
            for n in record["nodes"]
        ]
        rel_path = [r.type for r in record["relationships"]]
        paths.append({
            "nodes": node_path,
            "relationships": rel_path
        })

    return paths

async def get_full_path_to_node(
    target_label: Literal["File", "Folder", "Class", "Method"],
    target_name: str
):
    """
    Finds the full hierarchical path (using :CONTAINS relationships)
    from the root node labeled 'Repository' down to the specified target node.
    """
    cypher = f"""
    MATCH (root:Repository)
    MATCH path = (root)-[:CONTAINS*]->(target:{target_label} {{name: $target_name}})
    RETURN [n in nodes(path) | n.name] AS path_names // Return the list of node names in order
    """

    async with get_session() as session:
        result = await session.run(cypher, {"target_name": target_name})
        records = await result.data()

    paths_as_strings = []
    for record in records:
        path_names = record.get("path_names")
        if path_names:
            paths_as_strings.append("/".join(path_names))

    return paths_as_strings

async def similarity_search( node_label: Literal["File", "Class", "Method"], query: str):
    """
    Searches the code graph for nodes (Files, Classes, or Methods)
    semantically similar to the query using vector embeddings.
    Searches within both description and content fields.
    Returns the top_k most relevant nodes and their scores.
    """
    top_k=5 
    embedding = get_embedding(query) # If get_embedding is sync and blocking, this is a problem


    indexes = [
        f"{node_label.lower()}_embedding_description_index",
        f"{node_label.lower()}_embedding_content_index"
    ]

    combined_results = []

    async with get_session() as session:
        for index in indexes:
            cypher = """
            CALL db.index.vector.queryNodes($index_name, $top_k, $embedding)
            YIELD node, score
            RETURN node.name AS name,
                   node.description AS description,
                   node.content AS content,
                   labels(node) AS labels,
                   score
            ORDER BY score DESC
            """
            # Use the 'session' obtained from the 'async with' block
            result = await session.run(cypher, {
                "index_name": index,
                "embedding": embedding,
                "top_k": top_k # Use the local top_k variable
            })

            # Correctly iterate over the async result cursor
            combined_results.extend([record async for record in result])

    seen = set()
    deduped = []
    for record in sorted(combined_results, key=lambda r: r["score"], reverse=True):
        key = record.get("name") # Use get("name") as it's explicitly returned
        if key and key not in seen:
            seen.add(key)
            deduped.append(record)
        elif not key:
             deduped.append(record) 

    return deduped[:top_k]

def strip_markdown_fences(text: str) -> str:
    # Removes all Markdown code block fences like ``` or ```markdown
    return re.sub(r"```(?:markdown)?\n?|```", "", text)