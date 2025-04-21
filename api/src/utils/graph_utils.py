import os
import asyncio
import pygit2
import logging 
from src.core.config import config  
from asyncio import Semaphore, Lock
from src.core.db import get_session, close_driver
from src.utils.git_utils import traverse_tree_sync
from src.agent.base import run_code_analysis_agent , run_filter_agent
from src.agent.utils import get_project_tree_string , extract_file_content
from src.utils.helper import (
    get_embedding, 
    generate_stable_id, 
    queue_dependency_relationships_safe,
    run_dependency_relationships_batch,
    create_containment_relationships_cypher
)

logger=logging.getLogger(__name__)
# ------------------------------------------------------------
# Neo4j helper functions (using async session)
# ------------------------------------------------------------
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

async def create_repository_node(session, name, project_tree):
    """Create or merge a repository node in Neo4j."""
    node_id = generate_stable_id(name)
    query = (f"""
        MERGE (r:{config.REPO_LABEL} {{ node_id: $node_id }})
        SET r.name = $name,
            r.project_tree = $project_tree 
        RETURN r
    """)
    result = await session.run(
        query,
        node_id=node_id,
        name=name,
        project_tree=project_tree
    )
    record = await result.single()

    # Add embedding for the project tree
    await add_embeddings(
        session=session,
        node_label=config.REPO_LABEL,
        node_id=node_id,
        fields={"content": project_tree}
    )
    return record["r"]

async def create_folder_node(session, name, path, parent_path):
    """Create or merge a folder node and connect it to its parent node (repository or folder)."""
    node_id = generate_stable_id(f"{path}:{name}")
    logger.info(f"Creating folder node: name={name}, path={path}, parent_path={parent_path}, node_id={node_id}")    

    try:
        query = f"""
            MERGE (f:{config.FOLDER_LABEL} {{ node_id: $node_id }})
            SET f.name = $name, 
                f.path = $path , 
                f.parent_path = $parent_path 
            RETURN f
        """
        result = await session.run(query, name=name, path=path, parent_path=parent_path, node_id=node_id)
        record = await result.single()

        await add_embeddings(
            session=session,
            node_label=config.FOLDER_LABEL,
            node_id=node_id,
            fields={
                "name":name,
                "content": "N/A"
            }
        )

        logger.info(f"Folder node created or merged: {record['f']}")
        return record["f"]

    except Exception as e:
        logger.error(f"Error creating folder node {path}: {e}", exc_info=True)
        return None


async def create_file_node(session, name, path, parent_path, file_content=None):
    """Create or merge a file node and connect it to its parent node (repository or folder)."""
    logger.info(f"Running query to create file node with name: {name}, path: {path}, parent_path: {parent_path}")
    node_id = generate_stable_id(f"{path}:{name}")
    # Set file content only if provided
    file_content = file_content if file_content else "File is empty"

    query = (f"""
        MERGE (f:{config.FILE_LABEL} {{ node_id: $node_id }})
        SET f.name = $name,
            f.parent_path = $parent_path,
            f.content = $file_content,
            f.path = $path
        RETURN f
        """)
    result = await session.run(
        query, 
        node_id=node_id,
        name=name, 
        path=path, 
        parent_path=parent_path, 
        file_content=file_content
    )
    record = await result.single()
    logger.info(f"File node created or merged: {record['f']}")
    await add_embeddings(
        session=session,
        node_label=config.FILE_LABEL,
        node_id=node_id,
        fields={
            "name":name,
            "content": file_content
        }
    )
    return record["f"]

async def enrich_file_node(session,path,name, state):
    """Update the description and summary of a File node, and add their embeddings."""
    description = state.get("file_description", "")
    summary = state.get("code_summary", {})
    node_id = generate_stable_id(f"{path}:{name}")
    try:
        logger.info(f"Updating node properties for file: {path}, {name}")
        query = """
        MATCH (file:File {node_id: $node_id})
        SET file.description = $description, 
            file.summary = $summary
        RETURN file
        """
        result = await session.run(
            query, 
            node_id=node_id,
            description=description, 
            summary=summary.get("summary","N/A")
        )

        # Return the updated node
        updated_node = await result.single()
        logger.info(f"Successfully updated node: {updated_node}")

        add_embeddings(
            session=session,
            node_label=config.FILE_LABEL,
            node_id=node_id,
            fields={
                "description": description,
                "summary": summary.get("summary", "N/A"),
            }
        )
        logger.info(f"Added embeddings for node: {node_id}")
        return updated_node
    except Exception as e:
        logger.error(f"Error updating node properties: {e}")
        raise

async def create_script_node(session, name, description, content, file_path):
    try:
        node_id = generate_stable_id(f"{file_path}:{name}")
        logger.info(f"Creating/Updating script node: {name}")
        query_script = f"""
        MERGE (script:{config.SCRIPT_LABEL} {{ node_id: $node_id }})
        SET script.name= $name, 
            script.description = $description, 
            script.content = $content, 
            script.file_path = $file_path
        RETURN script
        """
        result_script = await session.run(query_script, 
                                          node_id=node_id,
                                          name=name, 
                                          description=description, 
                                          content=content,
                                          file_path=file_path)
        result = await result_script.single()
        await add_embeddings(
            session=session, 
            node_label=config.SCRIPT_LABEL,
            node_id=node_id,
            fields={
                "name": name,
                "description": description,
                "content": content
            }
        )    
        logger.info(f"Script node created or updated: {result['script']}")
        return result["script"]
    except Exception as e:
        logger.error(f"Error creating/updating script node: {e}")
        raise

async def create_class_node(session, name, description, docstring, content, file_path):
    try:
        logger.info(f"Creating/Updating class node: {name}")
        node_id = generate_stable_id(f"{file_path}:{name}")
        query_class = f"""
        MERGE (class:{config.CLASS_LABEL} {{ node_id: $node_id }})
        SET class.name = $name,
            class.description = $description, 
            class.docstring = $docstring, 
            class.content = $content,
            class.file_path = $file_path
        RETURN class
       """
        result_class = await session.run(query_class,
                                         node_id=node_id,
                                         name=name,
                                         description=description,
                                         docstring=docstring,
                                         content=content,
                                         file_path=file_path)
        result = await result_class.single()
        await add_embeddings(
            session=session,
            node_label=config.CLASS_LABEL,
            node_id=node_id,
            fields={
                "name":name,
                "description": description,
                "docstring": docstring,
                "content": content
            }
        )
        logger.info(f"Class node created or updated: {result['class']}")
        return result["class"]
    except Exception as e:
        logger.error(f"Error creating/updating class node: {e}")
        raise

# Function to create or merge the Method node and connect it to the Class or File node
async def create_method_node(session, name, description, docstring, content, file_path):
    try:
        logger.info(f"Creating/Updating method node: {name}")
        node_id = generate_stable_id(f"{file_path}:{name}")
        query_method = f"""
        MERGE (method:{config.METHOD_LABEL} {{ node_id: $node_id }})
        SET method.name = $name,
            method.description = $description,
            method.docstring = $docstring,
            method.content = $content,
            method.file_path = $file_path
        RETURN method
       """
        result_method = await session.run(query_method,
                                          node_id=node_id,
                                          name=name,
                                          description=description,
                                          docstring=docstring,
                                          content=content,
                                          file_path=file_path)
        method_node = await result_method.single()
        await add_embeddings(
            session=session,
            node_label=config.METHOD_LABEL,
            node_id=node_id,
            fields={
                "name":name,
                "description": description,
                "docstring": docstring,
                "content": content
            }
        )
        logger.info(f"Method node created or updated: {method_node['method']}")
        return method_node["method"]
    except Exception as e:
        logger.error(f"Error creating/updating method node: {e}")
        raise

# Main function to process the entire script, class, and method nodes
async def enrich_script_class_method(session, file_path, state):
    try:
        # Extract class and method information from the state
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
                class_data["docstring"], 
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
                method_data["docstring"], 
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
        code_summary = state.get("code_summary", {})
        need_analysis = code_summary.get("need_analysis", False)

        async with get_session() as session:
            logging.info("Update Repositor property ....")
            await enrich_file_node(
                session=session,
                path=file_path,
                name=file_name,
                state=state
            )

            if need_analysis:
                
                await enrich_script_class_method(
                    session=session,
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
        logger.error(f"Error during enrichment process: {e}")
        raise


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



# --- File ingestion ---
async def analyze_and_enrich(
    full_path: str,
    file_path: str,
    file_name: str,
    repo_name: str,
    repo_base: str,
    dependency_queue: list,
    dep_lock: Lock
):
    state = await run_code_analysis_agent(file_path=full_path, repo_base=repo_base)

    if not state or "code_summary" not in state or "code_analysis" not in state:
        logger.warning(f"Analysis skipped for {file_path} due to missing data.")
        return

    await enrich_kg(
        repo_name=repo_name,
        file_name=file_name,
        file_path=file_path,
        state=state,
        dep_queue=dependency_queue,
        dep_lock=dep_lock
    )

async def process_file_node(
    file_semaphore,
    node,
    repo_name: str,
    repo_base: str,
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
                    name=node["name"],
                    path=file_path,
                    parent_path=node["parent_path"],
                    file_content=file_content
                )
                # Run analysis only on useful files
                if updated_filter_result.get(file_path) and file_content.strip():
                    logger.info(f"Analyzing file: {file_path}")
                    await analyze_and_enrich(
                        full_path=full_path,
                        file_path=file_path,
                        file_name=node["name"],
                        repo_name=repo_name,
                        repo_base=repo_base,
                        dependency_queue=dependency_queue,
                        dep_lock=dep_lock
                    )
            except Exception as e:
                logger.error(f"Error processing file {file_path}: {e}", exc_info=True)


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
            project_tree = get_project_tree_string(repo_path)
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