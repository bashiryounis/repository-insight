import os
from src.core.config import config  
from src.utils.git_utils import traverse_tree_sync
from src.agent.base import run_code_analysis_agent , run_filter_agent
from src.agent.utils import get_project_tree_string , extract_file_content
import asyncio
from asyncio import Semaphore, Lock
import pygit2
import logging 
from llama_index.core import Document
from llama_index.core.schema import TextNode
from typing import Dict, Optional
from src.core.config import config
from src.utils.helper import (
    get_embedding, 
    generate_stable_id, 
    run_dependency_relationships_batch, 
    create_containment_relationships_cypher,
    run_dependency_relationships_batch,
    queue_dependency_relationships_safe
)

from src.core.index import get_index_for_label_field


logger=logging.getLogger(__name__)

# ------------------------------------------------------------
# Neo4j helper functions (using async session)
# ------------------------------------------------------------
def ingest_node(name: Optional[str], label: str, properties: dict, embed_fields: list[str] = None):
    """Ingest or enrich a single node in Neo4j with multiple embeddings."""
    logger.info(f"Ingesting node '{name}' with label '{label}' and properties: {properties}")
    if embed_fields is None:
        embed_fields = []

    path = os.path.normpath(properties.get("path", "")).lower() 
    identifier = f"{path}:{name}"
    node_id = generate_stable_id(identifier)

    for field in embed_fields:
        if field not in properties:
            continue

        text = properties[field]
        embedding = get_embedding(text)
        # Add embedding to metadata
        filtered_props = {k: v for k, v in properties.items() if k != field}
        metadata = {
            "id": node_id,
            "type": label,
            "path": path,
            **filtered_props,
        }

        if name:
            metadata["name"] = name

        node = TextNode(
            id_=node_id,
            text=text,
            metadata=metadata,
            embedding=embedding
        )
        vector_store = get_index_for_label_field(label=label, field=field)
        vector_store.add(nodes=[node])

        logger.info(f"{'Enriched' if not name else 'Ingested'} node '{metadata.get('name', '[unnamed]')}' ({label}) with field '{field}'.")

def ingest_repo_node(name, project_tree):
    ingest_node(
        name=name,
        label="Repository",
        properties={"content": project_tree},
        embed_fields=["content"]
    )

def ingest_folder_node(name, path, parent_path):   
    properties = {
        "path": path,
        "parent_path": parent_path,
        "content":f"This folder contains files for {name}.",
    }
    ingest_node(
        name=name,
        label="Folder",
        properties=properties,
        embed_fields=["content"]
    )

def ingest_file_node(name, path, parent_path, content, summary=None, description=None):
    if not content or not content.strip():
        content = f"# Empty file: {name}\n"
    properties = {
        "path": path,
        "parent_path": parent_path,
        "content": content,
    }
    if summary:
        properties["summary"] = summary
    if description:
        properties["description"] = description

    ingest_node(
        name=name,
        label="File",
        properties=properties,
        embed_fields=["content", "summary", "description"]
    )

def enrich_file_node(name:str, path: str, summary: str = None, description: str = None):
    """Enrich an existing File node with summary and/or description."""
    if not summary and not description:
        logger.warning(f"No enrichment fields provided for file '{path}'. Skipping.")
        return

    properties = {
        "path": path,
        "summary": summary,
        "description": description,
    }

    embed_fields = [field for field in ["summary", "description"] if properties.get(field)]

    ingest_node(
        name=name,
        label="File",
        properties=properties,
        embed_fields=embed_fields
    )

    logger.info(f"File '{path}' enriched with fields: {embed_fields}")


def ingest_script(name, description , code, file_path):
    properties = {
        "path": file_path,
        "description": description or "N/A",
        "code": code or "N/A",
    }
    ingest_node(
        name=name,
        label="Script",
        properties=properties,
        embed_fields=["description","code"]
    )

def ingest_class_method(name,label, description, docstring , content, file_path):
    properties = {
        "path": file_path,
        "description": description or "N/A",
        "code": content or "N/A",
        "docstring": docstring or "N/A",
    }

    ingest_node(
        name=name,
        label=label,
        properties=properties,
        embed_fields=["description","code","docstring"]
    )
    

def enrich_script_class_method(file_path,state):
    """Enrich the knowledge graph with class and method relationships."""
    try:
        # Extract class and method information from the state
        classes = state.get("classes", [])
        methods = state.get("methods", [])
        scripts = state.get("scripts", [])

        if not classes and not methods and not scripts:
            logger.info(f"No classes/methods/scripts found in {file_path}. Skipping enrichment.")
            return
        
        for class_info in classes:
            class_name = class_info.get("class_name")
            description = class_info.get("description")
            docstring = class_info.get("docstring")
            content = class_info.get("code")

            if class_name and description and content:
                ingest_class_method(
                    name=class_name,
                    label="Class",
                    description=description,
                    docstring=docstring,
                    content=content,
                    file_path=file_path
                )

        for method_info in methods:
            method_name = method_info.get("method_name")
            description = method_info.get("description")
            docstring = method_info.get("docstring")
            content = method_info.get("code")

            if method_name and description and content:
                ingest_class_method(
                    name=method_name,
                    label="Method",
                    description=description,
                    docstring=docstring,
                    content=content,
                    file_path=file_path
                )
        if scripts:
            logger.info("====="*10)
            logger.info(f"Enriching {len(scripts)} scripts in {file_path}...")
            logger.info(f"Scripts found: {scripts}")
            for script_info in scripts:
                script_name = script_info.get("script_name")
                description = script_info.get("description")
                code = script_info.get("code")

                if script_name and description and code:
                    ingest_script(
                        name=script_name,
                        description=description,
                        code=code,
                        file_path=file_path
                    )

    except Exception as e:
        logger.error(f"Error enriching class/method relationships: {e}")


async def enrich_kg(repo_name: str, file_name: str, file_path: str, state: dict, dep_queue: list, dep_lock: Lock):
    """Enrich the knowledge graph with analysis results + queue dependencies."""
    try:
        file_description = state.get("file_description")
        file_summary = state.get("code_summary", {}).get("summary", "N/A")
        need_analysis = state.get("code_summary", {}).get("need_analysis", False)

        if not state.get("code_analysis"):
            logger.warning(f"No code_analysis data found for {file_path}. Skipping enrichment.")
            return

        logger.info(f"Enriching file '{file_path}' with description and summary...")
        enrich_file_node(
            name=file_name,
            path=file_path,
            description=file_description,
            summary=file_summary
        )

        logger.info("Enriching script/class/method nodes...")
        if need_analysis:
            logger.info(f"File '{file_path}' requires further analysis. Enriching with class/method relationships...")
            enrich_script_class_method(
                file_path=file_path,
                state=state.get("code_analysis", {})
            )

            await queue_dependency_relationships_safe(
                state=state,
                repo_name=repo_name,
                dep_queue=dep_queue,
                lock=dep_lock
            )
            logger.info("Successfully enriched the knowledge graph.")
        else:
            logger.info("No further analysis needed. Only node property updated.")

    except Exception as e:
        logger.error(f"Error enriching knowledge graph: {e}")


async def ingest_repo(cloned_repo: pygit2.Repository):
    """Traverse repo and ingest code into Neo4j with embeddings + relationships."""
    dependency_queue = []
    dep_lock = Lock()
    file_semaphore = Semaphore(10)  # Limit concurrent file processing

    try:
        repo_path = cloned_repo.workdir
        repo_name = os.path.basename(repo_path.rstrip(os.sep))

        project_tree = get_project_tree_string(repo_path)
        ingest_repo_node(name=repo_name, project_tree=project_tree)

        logger.info(f"Project tree for '{repo_name}':\n{project_tree}")
        head_commit = cloned_repo[cloned_repo.head.target]
        nodes = await asyncio.to_thread(
            traverse_tree_sync, 
            cloned_repo, 
            head_commit.tree, 
            repo_path, 
            repo_path, 
            repo_name
        )

        logger.info(f"Retrieved {len(nodes)} nodes from repository '{repo_name}'.")
        filter_result = await run_filter_agent(project_tree)
        updated_filter_result = {
            f"{repo_name}/{key}": value for key, value in filter_result.items() if value is True
        }

        logger.info(f"Filtered useful files: {len(updated_filter_result)}")

        # --- Folder ingestion ---
        folder_tasks = [
            asyncio.to_thread(ingest_folder_node, node["name"], node["path"], node["parent_path"])
            for node in nodes if node["type"] == "folder"
        ]
        await asyncio.gather(*folder_tasks)


        # --- File ingestion ---
        async def process_file(node):
            async with file_semaphore:
                file_path = node["path"]
                full_path = os.path.join(config.REPO_DIRS, file_path)
                file_content = await extract_file_content(full_path)

                ingest_file_node(
                    name=node["name"],
                    path=file_path,
                    parent_path=node["parent_path"],
                    content=file_content
                )

                if updated_filter_result.get(file_path) and len(file_content.strip()) != 0:
                    logger.info(f"File {file_path} marked as useful. Running analysis...")
                    state = await run_code_analysis_agent(
                        file_path=full_path,
                        repo_base=os.path.join(config.REPO_DIRS, repo_name)
                    )

                    if not state or "code_summary" not in state or "code_analysis" not in state:
                        logger.warning(f"Skipping enrichment due to missing analysis for: {file_path}")
                        return

                    await enrich_kg(
                        repo_name=repo_name,
                        file_name=node["name"],
                        file_path=file_path,
                        state=state,
                        dep_queue=dependency_queue,  # Still shared
                        dep_lock=dep_lock
                    )


        file_tasks = [
            asyncio.create_task(process_file(node))
            for node in nodes if node["type"] == "file"
        ]
        await asyncio.gather(*file_tasks)

        # Final relationships
        await create_containment_relationships_cypher()
        await run_dependency_relationships_batch(dependency_queue)
        logger.info(f"Created {len(dependency_queue)} dependency relationships.")
        logger.info("Knowledge graph enrichment complete.")
        logger.info(f"Ingestion of repository '{repo_name}' complete.")

    except Exception as e:
        logger.error(f"Error ingesting repository: {e}")
