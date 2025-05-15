import os
import logging
import shutil
import pygit2
import asyncio
from asyncio import Semaphore, Lock
from src.core.db import get_session, close_driver
from src.core.config import config
from src.agent.ingest.tool import get_tree
from src.service.ingest.node import create_repository_node, create_folder_node, create_branch_node, create_commit_node
from src.service.ingest.relationship import (
    create_containment_relationships_cypher,
    run_dependency_relationships_batch,
)
from src.service.ingest.file_handler import process_file_node
from src.agent.ingest.base import run_filter_agent
from src.utils.git_utils import traverse_tree_sync
from src.service.ingest.git_repo_parser import GitRepoParser


logger = logging.getLogger(__name__)

async def ingest_repo(cloned_repo: pygit2.Repository):
    """Ingest a Git repository into Neo4j with nodes, embeddings, and relationships."""
    dependency_queue = []
    dep_lock = Lock()
    file_semaphore = Semaphore(10)  # Limit concurrency for file processing

    try:
        repo_path = cloned_repo.workdir

         # --- Parse repo structure using GitRepoParser ---
        parser = GitRepoParser(repo_path)
        nodes = parser.get_nodes()
        
        async with get_session() as session:
            await create_repository_node(
                session,
                node = nodes["metadata"],
                )
            logger.info(f"Repository node created: {nodes["metadata"]}")
        
        
        # --- Folder ingestion (parallel, safe) ---
        async def run_with_own_session_for_folder(node):
            async with get_session() as session:
                await create_folder_node(session, node)

        folder_tasks = [
            asyncio.create_task(run_with_own_session_for_folder(node))
            for node in parser.nodes["folders"]
        ]
        await asyncio.gather(*folder_tasks)
        logger.info(f"Created {len(folder_tasks)} folder nodes.")
        
        # # # --- Filter agent ---
        # filter_result = await run_filter_agent(parser.nodes.metadata["tree"])
        # updated_filter_result = {
        #     f"{parser.nodes.metadata["name"]}/{key}": val
        #     for key, val in filter_result.items()
        #     if val is True
        # }
        updated_filter_result = {}
        # # # --- File ingestion ---
        file_tasks = [
            asyncio.create_task(process_file_node(
                file_semaphore,
                node,
                updated_filter_result,
                dependency_queue,
                dep_lock
            ))
            for node in parser.nodes["files"]
        ]
        await asyncio.gather(*file_tasks)

        # # # --- Branch Ingestion ---
        async def run_with_own_session_for_branch(node):
            async with get_session() as session:
                await create_branch_node(session, node)

        branch_tasks = [
            asyncio.create_task(run_with_own_session_for_branch(node))
            for node in parser.nodes["branches"]
        ]
        await asyncio.gather(*branch_tasks)
        logger.info(f"Created {len(branch_tasks)} branches nodes.")

        # # # --- Commit Ingestion  
        async def run_with_own_session_for_commit(node):
            async with get_session() as session:
                await create_commit_node(session, node)

        commit_tasks = [
            asyncio.create_task(run_with_own_session_for_commit(node))
            for node in parser.nodes["commits"]
        ]
        await asyncio.gather(*commit_tasks)
        logger.info(f"Created {len(commit_tasks)} commits nodes.")

        # # # --- Final relationship setup ---
        await create_containment_relationships_cypher()
        await run_dependency_relationships_batch(dependency_queue)

        logger.info(f"Created {len(dependency_queue)} dependency relationships.")
        logger.info(f"Repository '{nodes["metadata"]}' ingestion complete.")

    except Exception as e:
        logger.error(f"Repository ingestion failed: {e}", exc_info=True)

    finally:
        await close_driver()