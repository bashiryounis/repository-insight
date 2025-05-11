import logging
from src.utils.helper import generate_stable_id
from src.core.config import config
from src.service.ingest.embedding import add_embeddings

logger = logging.getLogger(__name__)

async def create_repository_node(session, node, username="admin"):
    """Create or merge a repository node in Neo4j."""
    node_id = generate_stable_id(f"{node["name"]}:{username}")
    query = (f"""
        MERGE (r:{config.REPO_LABEL} {{ node_id: $node_id }})
        SET r.name = $name,
            r.remote_url = $remote_url,
            r.default_branch = $default_branch,
            r.description = $description,
            r.tree = $tree
        RETURN r
    """)
    result = await session.run(
        query,
        node_id=node_id,
        name=node["name"],
        remote_url=node["remote_url"],
        default_branch=node["default_branch"],
        description=node["description"],
        tree=node["tree"],
    )
    record = await result.single()

    embedding_content = f"""
        Repository: {node['name']}
        Description: {node.get('description', 'No description')}
        Project Tree:
        {node['tree']}
        """

    # Add embedding for the project tree
    await add_embeddings(
        session=session,
        node_label=config.REPO_LABEL,
        node_id=node_id,
        fields={"content": embedding_content},
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
    file_content = file_content.strip() if file_content and file_content.strip() else "File is empty"

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

async def create_class_node(session, name, description, content, file_path):
    try:
        logger.info(f"Creating/Updating class node: {name}")
        node_id = generate_stable_id(f"{file_path}:{name}")
        query_class = f"""
        MERGE (class:{config.CLASS_LABEL} {{ node_id: $node_id }})
        SET class.name = $name,
            class.description = $description, 
            class.content = $content,
            class.file_path = $file_path
        RETURN class
       """
        result_class = await session.run(query_class,
                                         node_id=node_id,
                                         name=name,
                                         description=description,
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
                "content": content
            }
        )
        logger.info(f"Class node created or updated: {result['class']}")
        return result["class"]
    except Exception as e:
        logger.error(f"Error creating/updating class node: {e}")
        raise

# Function to create or merge the Method node and connect it to the Class or File node
async def create_method_node(session, name, description, content, file_path):
    try:
        logger.info(f"Creating/Updating method node: {name}")
        node_id = generate_stable_id(f"{file_path}:{name}")
        query_method = f"""
        MERGE (method:{config.METHOD_LABEL} {{ node_id: $node_id }})
        SET method.name = $name,
            method.description = $description,
            method.content = $content,
            method.file_path = $file_path
        RETURN method
       """
        result_method = await session.run(query_method,
                                          node_id=node_id,
                                          name=name,
                                          description=description,
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
                "content": content
            }
        )
        logger.info(f"Method node created or updated: {method_node['method']}")
        return method_node["method"]
    except Exception as e:
        logger.error(f"Error creating/updating method node: {e}")
        raise