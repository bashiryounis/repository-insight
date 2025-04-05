import os
from src.core.config import config  
from src.core.db import get_session, close_driver
from src.utils.git_utils import traverse_tree_sync
from src.agent.base import run_code_analysis_agent , run_filter_agent
from src.agent.utils import get_project_tree_string , extract_file_content
import asyncio
import pygit2
import logging 

logger=logging.getLogger(__name__)
# ------------------------------------------------------------
# Neo4j helper functions (using async session)
# ------------------------------------------------------------

async def create_repository_node(session, name, project_tree):
    """Create or merge a repository node in Neo4j."""
    query = (
        f"MERGE (r:{config.REPO_LABEL} {{ name: $name }}) "
        "SET r.project_tree = $project_tree "
        "RETURN r"
    )
    result = await session.run(query, name=name, project_tree = project_tree)
    record = await result.single()
    return record["r"]

async def create_folder_node(session, name, path, repo_name):
    """Create or merge a folder node and connect it to its parent node (repository or folder)."""
    parent_path = os.path.dirname(path)
    if parent_path == repo_name:
        parent_path = None  
    logger.info(f"Running query to create folder node with name: {name}, path: {path}, parent_path: {parent_path}, repo_name: {repo_name}")
    
    if parent_path:
        query = (
            f"MERGE (f:{config.FOLDER_LABEL} {{ path: $path }}) "
            "SET f.name = $name "
            "WITH f "
            f"MERGE (p:{config.FOLDER_LABEL} {{ path: $parent_path }}) "
            "MERGE (p)-[:CONTAINS]->(f) "
            "RETURN f"
        )
    else:
        # If it's the root folder, connect to the repository node
        query = (
            f"MERGE (f:{config.FOLDER_LABEL} {{ path: $path }}) "
            "SET f.name = $name "
            "WITH f "
            f"MERGE (p:{config.REPO_LABEL} {{ name: $repo_name }}) "
            "MERGE (p)-[:CONTAINS]->(f) "
            "RETURN f"
        )
    
    # Run the query
    result = await session.run(query, name=name, path=path, parent_path=parent_path, repo_name=repo_name)
    
    # Check the result
    record = await result.single()
    if record:
        logger.info(f"Folder node created or merged: {record['f']}")
        return record["f"]
    else:
        logger.error(f"Folder creation failed for path: {path}")
        raise ValueError(f"Folder creation failed for path: {path}")
    

async def create_file_node(session, name, path, extension, repo_name, file_content=None):
    """Create or merge a file node and connect it to its parent node (repository or folder)."""
    parent_path = os.path.dirname(path)
    if parent_path == repo_name:
        parent_path = None 

    logger.info(f"Running query to create file node with name: {name}, path: {path}, extension: {extension}, parent_path: {parent_path}, repo_name: {repo_name}")

    # Set file content only if provided
    set_file_content = ""
    if file_content:
        set_file_content = "SET f.content = $file_content "

    # Construct query based on whether it's in a folder or root directory
    if parent_path:
        query = (
            f"MERGE (f:{config.FILE_LABEL} {{ path: $path }}) "
            "SET f.name = $name, f.extension = $extension "
            + set_file_content +
            "WITH f "
            f"MERGE (p:{config.FOLDER_LABEL} {{ path: $parent_path }}) "  
            "MERGE (p)-[:CONTAINS]->(f) "
            "RETURN f"
        )
    else:
        query = (
            f"MERGE (f:{config.FILE_LABEL} {{ path: $path }}) "
            "SET f.name = $name, f.extension = $extension "
            + set_file_content +
            "WITH f "
            f"MERGE (p:{config.REPO_LABEL} {{ name: $repo_name }}) "  
            "MERGE (p)-[:CONTAINS]->(f) "
            "RETURN f"
        )

    try:
        await session.run(query, 
                         name=name, 
                         path=path, 
                         extension=extension, 
                         parent_path=parent_path, 
                         repo_name=repo_name, 
                         file_content=file_content)
        logger.info(f"File node created or merged for path: {path}")
        return True
    except Exception as e:
        logger.error(f"Error creating file node for path {path}: {str(e)}")
        return False

async def update_node_property(session, repo_name, file_path, state):
    description = state.get("file_description", "")
    summary = state.get("code_summary", {})
    file_content = state.get("file_content", "")
    try:
        logger.info(f"Updating node properties for file: {file_path}")
        query = """
        MATCH (file:File {path: $file_path})
        SET file.description = $description, 
            file.summary = $summary
        RETURN file
        """
        result = await session.run(query, 
                                   file_path= file_path, 
                                   description=description, 
                                   summary=summary.get("summary",""), 
                                )

        # Return the updated node
        updated_node = await result.single()
        logger.info(f"Successfully updated node: {updated_node}")
        return updated_node
    except Exception as e:
        logger.error(f"Error updating node properties: {e}")
        raise

async def create_dependency_relationships(session, state, repo_name):
    try:
        logger.info(f"Creating dependency relationships for repository: {repo_name}")
        for depend in state["dependency_analysis"]:
            if depend["external"] == False:  # Process only internal dependencies
                source = os.path.join(repo_name, depend["source"])
                target = depend["target"]
                path = os.path.join(repo_name, depend["path"])  # Full relative path for the target
                description = depend["description"]
                relationship_type = "RELATED_TO"
                print(path)

                # Create relationship in Neo4j
                query = f"""
                MATCH (source:File {{path: $source_path}})
                MATCH (target:File {{path: $target_path}})
                MERGE (source)-[r:{relationship_type}]->(target)
                SET r.description = $description
                RETURN source, target, r
                """
                await session.run(query, 
                                  source_path=source, 
                                  target_path=path, 
                                  description=description)

                logger.info(f"Created {relationship_type} relationship between {source} and {target}")
    except Exception as e:
        logger.error(f"Error creating dependency relationships: {e}")
        raise

async def create_script_node(session, script_name, description, code, file_path):
    try:
        logger.info(f"Creating/Updating script node: {script_name}")
        query_script = """
        MERGE (script:Script {name: $script_name, file_path: $file_path})
        ON CREATE SET script.description = $description, script.code = $code
        WITH script
        MATCH (file:File {path: $file_path})
        MERGE (file)-[:HAS]->(script)
        RETURN script
        """
        result_script = await session.run(query_script, 
                                          script_name=script_name, 
                                          description=description, 
                                          code=code,
                                          file_path=file_path)
        return await result_script.single()
    except Exception as e:
        logger.error(f"Error creating/updating script node: {e}")
        raise

async def create_class_node(session, class_name, description, docstring, code, file_path):
    try:
        logger.info(f"Creating/Updating class node: {class_name}")
        query_class = """
        MERGE (class:Class {name: $class_name, file_path: $file_path})
        ON CREATE SET class.description = $description, class.docstring = $docstring, class.code = $code
        WITH class
        MATCH (file:File {path: $file_path})
        MERGE (file)-[:HAS]->(class)
        RETURN class
       """
        result_class = await session.run(query_class,
                                         class_name=class_name,
                                         description=description,
                                         docstring=docstring,
                                         code=code,
                                         file_path=file_path)
        return await result_class.single()
    except Exception as e:
        logger.error(f"Error creating/updating class node: {e}")
        raise

# Function to create or merge the Method node and connect it to the Class or File node
async def create_method_node(session, method_name, description, docstring, code, file_path):
    try:
        logger.info(f"Creating/Updating method node: {method_name}")
        query_method = """
        MERGE (method:Method {name: $method_name, file_path: $file_path})
        ON CREATE SET method.description = $description, method.docstring = $docstring, method.code = $code
        WITH method
        MATCH (file:File {path: $file_path})
        MERGE (file)-[:HAS]->(method)
        RETURN method
       """
        result_method = await session.run(query_method,
                                          method_name=method_name,
                                          description=description,
                                          docstring=docstring,
                                          code=code,
                                          file_path=file_path)
        method_node = await result_method.single()
        return method_node
    except Exception as e:
        logger.error(f"Error creating/updating method node: {e}")
        raise

# Main function to process the entire script, class, and method nodes
async def create_script_class_method_relationships(session, repo_name, file_path, state):
    try:
        file_name = os.path.basename(file_path)

        for script in state.get("scripts", []):
            script_node = await create_script_node(session, 
                                                   script["script_name"], 
                                                   script["description"], 
                                                   script["code"], 
                                                   file_path)

        for class_data in state.get("classes", []):
            class_node = await create_class_node(session, 
                                            class_data["class_name"], 
                                            class_data["description"], 
                                            class_data["docstring"], 
                                            class_data["code"], 
                                            file_path)

        for method_data in state.get("methods", []):
            print(method_data)
            await create_method_node(session, 
                                    method_data["method_name"], 
                                    method_data["description"], 
                                    method_data["docstring"], 
                                    method_data["code"], 
                                    file_path)
        return 
    except Exception as e:
        logger.error(f"Error creating script/class/method relationships: {e}")
        raise

# Main function to enrich the Neo4j knowledge graph
async def enrich_kg(
    repo_name: str,
    file_path: str,
    state: dict
):
    """Enrich the Neo4j knowledge graph with data from a code analysis state."""
    try:
        code_summary = state.get("code_summary", {})
        need_analysis = code_summary.get("need_analysis", False)

        async with get_session() as session:
            logging.info("Update Repositor property ....")
            await update_node_property(
                session=session,
                repo_name=repo_name,
                file_path=file_path,
                state=state
            )

            if need_analysis:
                await create_dependency_relationships(
                    session=session,
                    repo_name=repo_name,
                    state=state
                )
                
                await create_script_class_method_relationships(
                    session=session,
                    repo_name=repo_name,
                    file_path=file_path,
                    state=state.get("code_analysis", {})
                )
                logger.info("Successfully enriched the knowledge graph.")
            else:
                logger.info("No further analysis needed. Only node property updated.")
        
    except Exception as e:
        logger.error(f"Error during enrichment process: {e}")
        raise

async def ingest_repo(cloned_repo: pygit2.Repository):
    """
    Given a cloned pygit2 Repository object, traverse its HEAD commit tree and ingest
    the resulting structure into Neo4j.
    """

    try:
        async with get_session() as session:
            repo_path = cloned_repo.workdir
            repo_name = os.path.basename(repo_path.rstrip(os.sep))
            project_tree = get_project_tree_string(repo_path)
            repo_node = await create_repository_node(session, repo_name,project_tree)
            logger.info(f"Created repository node for '{repo_name}'")
            head_commit = cloned_repo[cloned_repo.head.target]
            nodes = await asyncio.to_thread(traverse_tree_sync, cloned_repo, head_commit.tree, repo_path, repo_path, repo_name)
            logger.info(f"Retrieved {len(nodes)} nodes from repository '{repo_name}'.")
            filter_result = await run_filter_agent(project_tree)
            logger.info(f"Filter result: {filter_result}")
            updated_filter_result = {
                f"{repo_name}/{key}": value for key, value in filter_result.items() if value is True
            }
            logger.info(f"Updated filter result with repo name: {updated_filter_result}")


            for node in nodes:
                if node["type"] == "folder":
                    await create_folder_node(session, node["name"], node["path"], repo_name)
                elif node["type"] == "file":
                    file_content = await extract_file_content(os.path.join(config.REPO_DIRS,node["path"]))
                    await create_file_node(session, node["name"], node["path"], node["extension"],repo_name, file_content)
                    
                    if updated_filter_result.get(node["path"]):
                        logger.info(f"File {node['path']} is useful. Proceeding with code analysis.")

                        state = await run_code_analysis_agent(
                            file_path=os.path.join(config.REPO_DIRS, node["path"]),
                            repo_base=os.path.join(config.REPO_DIRS, repo_name)
                        )

                        # Enrich the knowledge graph with code analysis results
                        await enrich_kg(
                            repo_name=repo_name,
                            file_path=node["path"],
                            state=state
                        )
            logger.info(f"Ingestion of repository '{repo_name}' complete.")

    except Exception as e:
        logger.error(f"Error ingesting repository: {e}")
    finally:
        await close_driver()