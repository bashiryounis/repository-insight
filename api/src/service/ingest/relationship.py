import os 
import logging 
from asyncio import Lock
from src.core.db import get_session
from src.core.config import config
from src.utils.helper import generate_stable_id


logger = logging.getLogger(__name__)

async def queue_dependency_relationships_safe(state: dict, repo_name: str, dep_queue: list, lock:Lock):
    deps = []
    for depend in state.get("dependency_analysis", []):
        if not depend.get("external"):
            source_path = os.path.join(repo_name, depend["source"])
            target_path = os.path.join(repo_name, depend["path"])
            description = depend.get("description", "")
            deps.append((source_path, target_path, description))

    async with lock:
        dep_queue.extend(deps)
        logger.info(f"Queued {len(deps)} dependency relationships for processing.")

async def create_containment_relationships_cypher():
    try:
        async with  get_session() as session:
            logger.info("Creating CONTAINS relationships in Neo4j...")

            # Connect Repository → Folder (for root-level folders)
            await session.run("""
                MATCH (repo:Repository), (folder:Folder)
                WHERE folder.parent_path = repo.name
                MERGE (repo)-[:CONTAINS]->(folder)
            """)
            # Connect Repository → File (for root-level folders)
            await session.run("""
                MATCH (repo:Repository), (file:File)
                WHERE file.parent_path = repo.name
                MERGE (repo)-[:CONTAINS]->(file)
            """)

            # Connect Folder → Folder (subfolders)
            await session.run("""
                MATCH (parent:Folder), (child:Folder)
                WHERE child.parent_path = parent.path
                MERGE (parent)-[:CONTAINS]->(child)
            """)

            # Connect Folder → File
            await session.run("""
                MATCH (folder:Folder), (file:File)
                WHERE file.parent_path = folder.path
                MERGE (folder)-[:CONTAINS]->(file)
            """)

            # Optionally: Connect File → Script/Class/Method nodes
            await session.run("""
                MATCH (file:File), (script:Script)
                WHERE script.file_path = file.path
                MERGE (file)-[:HAS_SCRIPT]->(script)
            """)

            await session.run("""
                MATCH (file:File), (cls:Class)
                WHERE cls.file_path = file.path
                MERGE (file)-[:Has_CLASS]->(cls)
            """)

            await session.run("""
                MATCH (file:File), (method:Method)
                WHERE method.file_path = file.path
                MERGE (file)-[:Has_METHOD]->(method)
            """)

            logger.info("All CONTAINS relationships created.")
    except Exception as e:
        logger.error(f"Error creating relationships via Cypher: {e}")


async def run_dependency_relationships_batch(dep_queue: list):
    """Run Cypher to create all queued RELATED_TO file relationships."""
    try:
        async with get_session() as session:
            for source, target, description in dep_queue:
                await session.run("""
                    MATCH (source:File {path: $source_path})
                    MATCH (target:File {path: $target_path})
                    MERGE (source)-[r:RELATED_TO]->(target)
                    SET r.description = $description
                """, {
                    "source_path": source,
                    "target_path": target,
                    "description": description,
                })

            logger.info(f"Created {len(dep_queue)} RELATED_TO relationships.")
    except Exception as e:
        logger.error(f"Error creating dependency relationships: {e}")


async def create_file_diff_relationships(session, branch_node, file_diff):
    """
    For a given branch, create ADDED_FILE, REMOVED_FILE, and MODIFIED_FILE relationships
    to the affected file nodes.
    """
    branch_id = generate_stable_id(f"{branch_node['name']}:{branch_node['repository']}")
    
    for path in file_diff.get("added", []):
        await session.run(
            f"""
            MATCH (b:{config.BRANCH_LABEL} {{ node_id: $branch_id }})
            MATCH (f:{config.FILE_LABEL} {{ path: $path }})
            MERGE (b)-[:ADDED_FILE]->(f)
            """,
            branch_id=branch_id,
            path=path
        )

    for path in file_diff.get("removed", []):
        await session.run(
            f"""
            MATCH (b:{config.BRANCH_LABEL} {{ node_id: $branch_id }})
            MATCH (f:{config.FILE_LABEL} {{ path: $path }})
            MERGE (b)-[:REMOVED_FILE]->(f)
            """,
            branch_id=branch_id,
            path=path
        )

    for item in file_diff.get("modified", []):
        await session.run(
            f"""
            MATCH (b:{config.BRANCH_LABEL} {{ node_id: $branch_id }})
            MATCH (f:{config.FILE_LABEL} {{ path: $path }})
            MERGE (b)-[r:MODIFIED_FILE]->(f)
            SET r.diff = $diff
            """,
            branch_id=branch_id,
            path=item["file_path"],
            diff=item["diff"]
        )
