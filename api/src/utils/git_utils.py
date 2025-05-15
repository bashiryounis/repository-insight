import os 
import pygit2
import asyncio

def traverse_tree_sync(repo, tree, parent_full_path, base_path, repo_name):
    """
    Synchronously traverse the pygit2 tree and return structured file/folder nodes.
    Paths and parent paths are normalized and namespaced with the repo name.
    """
    nodes = []
    for entry in tree:
        full_path = os.path.join(parent_full_path, entry.name)
        relative_path = os.path.relpath(full_path, base_path)
        path = os.path.normpath(os.path.join(repo_name, relative_path))

        relative_parent = os.path.relpath(parent_full_path, base_path)
        if relative_parent in (".", ""):
            parent_path = repo_name  # root folder connects to the repo
        else:
            parent_path = os.path.normpath(os.path.join(repo_name, relative_parent))

        if entry.filemode == pygit2.GIT_FILEMODE_TREE:
            # Folder
            nodes.append({
                "type": "folder",
                "name": entry.name,
                "path": path,
                "parent_path": parent_path,
            })
            subtree = repo[entry.id]
            nodes.extend(traverse_tree_sync(repo, subtree, full_path, base_path, repo_name))

        else:
            # File
            _, ext = os.path.splitext(entry.name)
            ext = ext.lstrip('.') if ext else entry.name

            nodes.append({
                "type": "file",
                "name": entry.name,
                "path": path,
                "extension": ext,
                "parent_path": parent_path,
            })
    return nodes

def traverse_tree(repo_path, base_path, repo_name):
    """Traverse the file system tree of the repo and return a structured tree of files and folders."""
    nodes = []
    
    # Walk the directory structure starting from the repo path
    for root, dirs, files in os.walk(repo_path):
        # Build relative paths based on the repo base path
        relative_path = os.path.relpath(root, base_path)
        relative_path_with_repo = os.path.join(repo_name, relative_path)  # Include repo name in path
        
        # Create a folder node for the directory
        nodes.append({
            "type": "folder",
            "name": os.path.basename(root),
            "path": relative_path_with_repo,
            "parent_path": os.path.dirname(relative_path_with_repo) if relative_path else None
        })
        
        # Create file nodes for each file in the directory
        for file in files:
            _, ext = os.path.splitext(file)  # Extract file extension
            ext = ext.lstrip('.')  # Remove leading dot

            nodes.append({
                "type": "file",
                "name": file,
                "path": os.path.join(relative_path_with_repo, file),
                "extension": ext,
                "parent_path": relative_path_with_repo
            })
    
    return nodes

async def get_repo_nodes(repo_path: str):
    """
    Given a repository path, traverse its directory structure,
    and return the collected node information asynchronously.
    """
    # Use asyncio to run the file tree traversal in a non-blocking way
    return await asyncio.to_thread(traverse_tree_sync, repo_path, repo_path, os.path.basename(repo_path))
