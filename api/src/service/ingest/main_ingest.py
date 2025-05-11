import os
import logging
import shutil
import pygit2
import asyncio
from asyncio import Semaphore, Lock
from src.core.db import get_session, close_driver
from src.core.config import config
from src.agent.ingest.tool import get_tree
from src.service.ingest.node import create_repository_node
from src.service.ingest.relationship import (
    create_containment_relationships_cypher,
    run_dependency_relationships_batch,
)
from src.service.ingest.folder_handler import process_folder_node
from src.service.ingest.file_handler import process_file_node
from src.agent.ingest.base import run_filter_agent
from src.utils.git_utils import traverse_tree_sync


logger = logging.getLogger(__name__)

async def ingest_repo(cloned_repo: pygit2.Repository):
    """Ingest a Git repository into Neo4j with nodes, embeddings, and relationships."""
    dependency_queue = []
    dep_lock = Lock()
    file_semaphore = Semaphore(10)  # Limit concurrency for file processing

    try:
        repo_path = cloned_repo.workdir
        repo_name = os.path.basename(repo_path.rstrip(os.sep))
        repo_base = os.path.join(config.REPO_DIRS, repo_name)
        async with get_session() as session:
            # --- Repository node ---
            project_tree = get_tree(repo_path)
            await create_repository_node(session, repo_name, project_tree)
            logger.info(f"Repository node created: {repo_name}")

        # --- Git tree traversal ---
        head_commit = cloned_repo[cloned_repo.head.target]
        nodes = await asyncio.to_thread(
            traverse_tree_sync,
            cloned_repo, head_commit.tree, repo_path, repo_path, repo_name
        )
        logger.info(f"Discovered {len(nodes)} nodes in repository.")

        # --- Folder ingestion ---
        folder_tasks = [
            asyncio.create_task(process_folder_node(node=node))
            for node in nodes if node["type"] == "folder"
        ]
        await asyncio.gather(*folder_tasks)
        logger.info(f"Created {len(folder_tasks)} folder nodes.")

        # # --- Filter agent ---
        filter_result = await run_filter_agent(project_tree)
        updated_filter_result = {
            f"{repo_name}/{key}": val
            for key, val in filter_result.items()
            if val is True
        }
        # # --- File ingestion ---
        file_tasks = [
            asyncio.create_task(process_file_node(
                file_semaphore,
                node,
                repo_name,
                repo_base,
                updated_filter_result,
                dependency_queue,
                dep_lock
            ))
            for node in nodes if node["type"] == "file"
        ]
        await asyncio.gather(*file_tasks)

        # # --- Final relationship setup ---
        await create_containment_relationships_cypher()
        await run_dependency_relationships_batch(dependency_queue)

        logger.info(f"Created {len(dependency_queue)} dependency relationships.")
        logger.info(f"Repository '{repo_name}' ingestion complete.")

    except Exception as e:
        logger.error(f"Repository ingestion failed: {e}", exc_info=True)

    finally:
        await close_driver()