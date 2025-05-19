import os 
from asyncio import Lock
import logging
from src.core.config import config
from src.core.db import get_session
from src.service.ingest.node import create_file_node
from src.agent.ingest.tool import extract_file_content


logger = logging.getLogger(__name__)

async def process_file_node(
    file_semaphore,
    node,
    updated_filter_result: dict,
    dependency_queue: list,
    dep_lock: Lock 
):
    async with get_session() as session:
        async with file_semaphore:
            file_path = node["path"]
            full_path = os.path.join(config.REPO_DIRS, file_path)

            try:
                file_content = await extract_file_content(full_path)

                await create_file_node(
                    session=session,
                    node=node,
                    file_content=file_content
                )
                # Run analysis only on useful files
                # if updated_filter_result.get(file_path) and file_content.strip():
                #     logger.info(f"Analyzing file: {file_path}")
                # from src.service.ingest.enrichment import analyze_and_enrich

                #     await analyze_and_enrich(
                #         full_path=full_path,
                #         file_path=file_path,
                #         file_name=node["name"],
                #         repo_name=repo_name,
                #         repo_base=repo_base,
                #         dependency_queue=dependency_queue,
                #         dep_lock=dep_lock
                #     )
            except Exception as e:
                logger.error(f"Error processing file {file_path}: {e}", exc_info=True)