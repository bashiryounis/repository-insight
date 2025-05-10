import logging 
import math 
import uuid
from src.utils.helper import get_embedding

logger=logging.getLogger(__name__)


async def add_embeddings(
    session,
    node_label: str,
    node_id: str,
    fields: dict,
):
    """Embeds the given content and stores it on the node with given node_id."""
    for field_name, content in fields.items():
        if not content:
            continue

        embedding = get_embedding(content)
        embed_prop = f"embedding_{field_name}"
        query = f"""
            MATCH (n:{node_label} {{node_id: $node_id}})
            SET n.{embed_prop} = $embedding
            RETURN n
        """
        await session.run(query, node_id=node_id, embedding=embedding)