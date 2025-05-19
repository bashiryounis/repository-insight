import os 
import logging 
from asyncio import Lock
from src.core.config import config
from src.core.db import get_session
from src.utils.helper import generate_stable_id
from src.service.ingest.node import create_class_node, create_method_node, create_script_node
from src.service.ingest.relationship import queue_dependency_relationships_safe 

logger = logging.getLogger(__name__)

async def enrich_file_node(session,path,name, state):
    """Update the description of a File node, and add their embeddings."""
    description = state.get("file_description", "")
    node_id = generate_stable_id(f"{path}:{name}")
    try:
        logger.info(f"Updating node properties for file: {path}, {name}")
        query = """
        MATCH (file:File {node_id: $node_id})
        SET file.description = $description
        RETURN file
        """
        result = await session.run(
            query, 
            node_id=node_id,
            description=description, 
        )

        # Return the updated node
        updated_node = await result.single()
        logger.info(f"Successfully updated node: {updated_node}")
        
        from src.service.ingest.embedding import add_embeddings
        add_embeddings(
            session=session,
            node_label=config.FILE_LABEL,
            node_id=node_id,
            fields={
                "description": description,
            }
        )
        logger.info(f"Added embeddings for node: {node_id}")
        return updated_node
    except Exception as e:
        logger.error(f"Error updating node properties: {e}")
        raise

async def enrich_script_class_method(session, file_path, state):
    try:
        classes = state.get("classes", [])
        methods = state.get("methods", [])
        scripts = state.get("scripts", [])

        if not classes and not methods and not scripts:
            logger.info(f"No classes/methods/scripts found in {file_path}. Skipping enrichment.")
            return
        
        for class_data in classes:
            class_node = await create_class_node(
                session, 
                class_data["class_name"], 
                class_data["description"], 
                class_data["code"], 
                file_path
            )
        for method_data in methods:
            logger.info(f"Creating method node for {method_data['method_name']}")
            # Create or update the method node
            method_node = await create_method_node(
                session, 
                method_data["method_name"], 
                method_data["description"], 
                method_data["code"], 
                file_path
            )
        
        for script_data in scripts:
            logger.info(f"Creating script node for {script_data['script_name']}")
            # Create or update the script node
            script_node = await create_script_node(
                session, 
                script_data["script_name"], 
                script_data["description"], 
                script_data["code"], 
                file_path
            )

        return 
    except Exception as e:
        logger.error(f"Error creating script/class/method relationships: {e}")
        raise

async def enrich_kg(
    repo_name: str, 
    file_name: str, 
    file_path: str, 
    state: dict, 
    dep_queue: list, 
    dep_lock: Lock
):
    """Enrich the Neo4j knowledge graph with data from a code analysis state."""
    try:
        async with get_session() as session:
            logging.info("Update Repositor property ....")
            await enrich_file_node(
                session=session,
                path=file_path,
                name=file_name,
                state=state
            )

            if state["analysis_skipped"]:
                logger.info(f"Analysis was skipped for {file_path}: {state.get('skip_reason')}")
                return
            
            if not state["skip_code_parser"]:
                await enrich_script_class_method(
                    session=session,
                    file_path=file_path,
                    state=state.get("code_analysis", {})
                )
                logger.info("Enriching knowledge graph with classes, methods, and scripts.")
            
            if not state["skip_dependency_parser"]:        
                await queue_dependency_relationships_safe(
                    state=state,
                    repo_name=repo_name,
                    dep_queue=dep_queue,
                    lock=dep_lock
                )
                logger.info("Successfully enriched the knowledge grap with relationship.")

            if state["skip_code_parser"] and state["skip_dependency_parser"]:
                logger.info("Only file node updated. No code or dependency enrichment was needed.")
        
    except Exception as e:
        logger.error(f"Error during enrichment process: {e}")
        raise

async def analyze_and_enrich(
    full_path: str,
    file_path: str,
    file_name: str,
    repo_name: str,
    repo_base: str,
    dependency_queue: list,
    dep_lock: Lock
):
    """Run code analysis and enrich the knowledge graph with the results."""
    from src.agent.ingest.base import run_code_analysis_agent

    state = await run_code_analysis_agent(file_path=full_path, repo_base=repo_base)
    await enrich_kg(
        repo_name=repo_name,
        file_name=file_name,
        file_path=file_path,
        state=state,
        dep_queue=dependency_queue,
        dep_lock=dep_lock
    )