import logging
from datetime import datetime
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

    await add_embeddings(
        session=session,
        node_label=config.REPO_LABEL,
        node_id=node_id,
        fields={"content": embedding_content},
    )
    return record["r"]

async def create_branch_node(session, node):
    """Create or merge a branch node and connect it to its parent repository."""
    repo_name = node["repository"]
    node_id = generate_stable_id(f"{node['name']}:{repo_name}")
    logger.info(f"Creating branch node: name={node['name']}...")

    try:
        # Create branch node
        query = f"""
            MERGE (b:{config.BRANCH_LABEL} {{ node_id: $node_id }})
            SET b.name = $name, 
                b.is_head = $is_head,
                b.is_default = $is_default,
                b.is_remote_tracking = $is_remote_tracking,
                b.upstream_name = $upstream_name,
                b.remote_name = $remote_name,
                b.latest_commit_id = $latest_commit_id,
                b.commit_count = $commit_count,
                b.repository = $repository,
                b.tree = $tree
            RETURN b
        """
        result = await session.run(
            query, 
            node_id=node_id,
            name=node["name"], 
            is_head=node["is_head"],
            is_default=node["is_default"],
            is_remote_tracking=node["is_remote_tracking"],
            upstream_name=node["upstream_name"],
            remote_name=node["remote_name"],
            latest_commit_id=node["latest_commit_id"],
            commit_count=node["commit_count"],
            repository=repo_name,
            tree = node["tree"]
        )
        record = await result.single()

        # Create relationship to repository
        await session.run(
            f"""
            MATCH (b:{config.BRANCH_LABEL} {{ node_id: $node_id }})
            MATCH (r:{config.REPO_LABEL} {{ name: $repository }})
            MERGE (r)-[:HAS_BRANCH]->(b)
            """,
            node_id=node_id,
            repository=repo_name
        )

        if node.get("file_diff"):
            from src.service.ingest.relationship import create_file_diff_relationships
            await create_file_diff_relationships(session, node, node["file_diff"])

        # Embedding
        content = f"""\
        Branch Name: {node['name']}
        Repository: {repo_name}
        Is Head: {node['is_head']}
        Is Default: {node['is_default']}
        Is Remote Tracking: {node['is_remote_tracking']}
        Upstream Name: {node['upstream_name']}
        Remote Name: {node['remote_name']}
        Latest Commit ID: {node['latest_commit_id']}
        Commit Count: {node['commit_count']}
        """
        await add_embeddings(
            session=session,
            node_label=config.BRANCH_LABEL,
            node_id=node_id,
            fields={"content": content}
        )

        logger.info(f"Branch node created and linked to repository: {record['b']}")
        return record["b"]

    except Exception as e:
        logger.error(f"Error creating branch node {node['name']}: {e}", exc_info=True)
        return None


async def create_commit_node(session, node):
    """
    Create or merge a commit node, and relate it to:
    - Branch (CONTAINS_COMMIT)
    - Files (MODIFIED_FILE)
    - Parent commits (PARENT)
    """
    commit_id = node["id"]
    repo_name = node["repository"]
    branch_name = node["branch"]

    logger.info(f"Creating commit node: {commit_id}...")

    try:
        # Create the commit node
        result = await session.run(
            f"""
            MERGE (c:{config.COMMIT_LABEL} {{ node_id: $node_id }})
            SET c.name = $name,
                c.message = $message,
                c.author = $author,
                c.email = $email,
                c.timestamp = $timestamp,
                c.repository = $repository,
                c.branch = $branch
            RETURN c
            """,
            node_id=commit_id,
            name= node["name"],
            message=node["message"],
            author=node["author"],
            email=node["email"],
            timestamp=node["timestamp"],
            repository=repo_name,
            branch=branch_name
        )
        record = await result.single()

        # Relate commit → branch
        await session.run(
            f"""
            MATCH (c:{config.COMMIT_LABEL} {{ node_id: $commit_id }})
            MATCH (b:{config.BRANCH_LABEL} {{ name: $branch_name, repository: $repository }})
            MERGE (b)-[:CONTAINS_COMMIT]->(c)
            """,
            commit_id=commit_id,
            branch_name=branch_name,
            repository=repo_name
        )

        # Relate commit → files
        for f in node.get("touched_files", []):
            print("#"*250)
            print(f)
            print("#"*250)
            await session.run(
                f"""
                MATCH (c:{config.COMMIT_LABEL} {{ node_id: $commit_id }})
                MATCH (f:{config.FILE_LABEL} {{ path: $file_path, repository: $repository }})
                MERGE (c)-[r:MODIFIED_FILE]->(f)
                SET r.diff = $diff
                """,
                commit_id=commit_id,
                file_path=f["file_path"],
                repository=repo_name,
                diff=f["diff"]
            )

        # Relate commit → parents
        for parent_id in node.get("parents", []):
            await session.run(
                f"""
                MATCH (c1:{config.COMMIT_LABEL} {{ node_id: $commit_id }})
                MATCH (c2:{config.COMMIT_LABEL} {{ node_id: $parent_id }})
                MERGE (c1)-[:PARENT]->(c2)
                """,
                commit_id=commit_id,
                parent_id=parent_id
            )

        # Embedding content
        content = f"""\
        Commit Message: {node['message']}
        Author: {node['author']} <{node['email']}>
        Branch: {branch_name}
        Timestamp: {datetime.utcfromtimestamp(node['timestamp']).isoformat()}
        """

        await add_embeddings(
            session=session,
            node_label=config.COMMIT_LABEL,
            node_id=commit_id,
            fields={"content": content}
        )

        logger.info(f"Commit node created and linked: {record['c']}")
        return record["c"]

    except Exception as e:
        logger.error(f"Error creating commit node {commit_id}: {e}", exc_info=True)
        return None
    
async def create_folder_node(session, node):
    """Create or merge a folder node and connect it to its parent node (repository or folder)."""
    node_id = generate_stable_id(f"{node["path"]}:{node["name"]}")
    logger.info(f"Creating folder node: name={node["name"]}, path={node["path"]}, parent_path={node["parent_path"]}, node_id={node_id}")    

    try:
        query = f"""
            MERGE (f:{config.FOLDER_LABEL} {{ node_id: $node_id }})
            SET f.name = $name, 
                f.path = $path , 
                f.parent_path = $parent_path, 
                f.tree = $tree,
                f.repository = $repository
            RETURN f
        """
        result = await session.run(
            query, 
            node_id=node_id,
            name=node["name"], 
            path=node["path"], 
            parent_path=node["parent_path"],
            tree=node["tree"],
            repository=node["repository"] 

        )
        record = await result.single()

        await add_embeddings(
            session=session,
            node_label=config.FOLDER_LABEL,
            node_id=node_id,
            fields={
                "name":node["name"],
                "content": node["tree"],
            }
        )
        logger.info(f"Folder node created or merged: {record['f']}")
        return record["f"]

    except Exception as e:
        logger.error(f"Error creating folder node {node["path"]}: {e}", exc_info=True)
        return None

async def create_file_node(session,node, file_content=None):
    """Create or merge a file node and connect it to its parent node (repository or folder)."""
    logger.info(f"Running query to create file node with name: {node["name"]}.")
    node_id = generate_stable_id(f"{node["path"]}:{node["name"]}")
    # Set file content only if provided
    file_content = file_content.strip() if file_content and file_content.strip() else "File is empty"

    query = (f"""
        MERGE (f:{config.FILE_LABEL} {{ node_id: $node_id }})
        SET f.name = $name,
            f.content = $file_content,
            f.parent_path = $parent_path,
            f.path = $path,
            f.extension = $extension,
            f.repository = $repository
        RETURN f
        """)
    result = await session.run(
        query, 
        node_id=node_id,
        name=node["name"], 
        path=node["path"],
        extension=node["extension"],
        repository=node["repository"], 
        parent_path=node["parent_path"], 
        file_content=file_content
    )
    record = await result.single()
    logger.info(f"File node created or merged: {record['f']}")
    await add_embeddings(
        session=session,
        node_label=config.FILE_LABEL,
        node_id=node_id,
        fields={
            "name":node["name"],
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