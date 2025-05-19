from typing import Literal 
from src.core.db import get_session
from src.agent.insight.tools.utils import format_search_results
from src.agent.insight.tools.neo4j_utils import traverse_node

async def search_graph(node_label: Literal["File", "Folder", "Class", "Method"], node_name: str ) -> str :
    """Usefull to search for spacific node in Graph databse"""
    top_k: int = 5
    from src.utils.helper import get_embedding
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

    if node_label == "Folder" and records:
            matched_folder_name = records[0]["name"]
            return await traverse_node(matched_folder_name)
    elif records:
        return format_search_results(records)
    else:
        return "No matching node found."

async def similarity_search( node_label: Literal["File", "Class", "Method"], query: str):
    """
    Searches the code graph for nodes (Files, Classes, or Methods)
    semantically similar to the query using vector embeddings.
    Searches within both description and content fields.
    Returns the top_k most relevant nodes and their scores.
    """
    top_k=5 
    from src.utils.helper import get_embedding
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
