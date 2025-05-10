import logging
from src.core.db import get_session 
from src.service.ingest.node import create_folder_node 

logger = logging.getLogger(__name__)

# --- Folder ingestion ---
async def process_folder_node(node):
    async with get_session() as session:
        try:
            await create_folder_node(
                session,
                name=node["name"],
                path=node["path"],
                parent_path=node["parent_path"]
            )
        except Exception as e:
            logger.error(f"Error processing folder {node['path']}: {e}", exc_info=True)

