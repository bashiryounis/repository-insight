from typing import Dict, Literal, List, Any
from src.core.db import get_session
from src.agent.insight.tools.utils import (
    build_nested_tree,
    format_nested_tree,
)

async def traverse_node(folder_name: str) -> str:
    """Recursively gather all contents under a folder."""
    cypher = """
    MATCH path = (f:Folder {name: $folder_name})-[:CONTAINS|HAS*]->(node)
    WHERE NOT node:Folder
    RETURN [n IN nodes(path) | n.name] AS path_names,
        labels(node)[0] AS label,
        node.description AS description,
        node.content AS content
    ORDER BY path_names

    """

    async with get_session() as session:
        result = await session.run(cypher, {"folder_name": folder_name})
        records = [r async for r in result]

    if not records:
        return "No matching node found."

    nested_tree = build_nested_tree(records)
    formatted_tree = f"{folder_name}\n" + format_nested_tree(nested_tree)
    return formatted_tree



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