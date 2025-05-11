import os
import uuid 
from llama_index.core.settings import Settings
import logging  
import math
import fnmatch

logger=logging.getLogger(__name__)

def generate_stable_id(identifier: str) -> str:
    """Generate a UUID5 based on a file path (stable across runs)."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, identifier))

def get_embedding(text: str) -> list[float]:
    if not text or not text.strip():
        return []

    embedding = Settings.embed_model.get_text_embedding(text)
    if not isinstance(embedding, list):
        embedding = embedding.tolist()

    if not all(isinstance(x, (float, int)) and math.isfinite(x) for x in embedding):
        logger.warning("Embedding contains non-finite values. Skipping embedding.")
        return []

    return embedding

def get_tree(root_path: str, prefix: str = "", ignore: list = None) -> str:
    """
    Recursively generates a tree-like string for the given directory,
    skipping files/folders matching any pattern in `ignore`.

    Args:
        root_path (str): The root directory to walk.
        prefix (str): Used for indentation (internal use).
        ignore (list): List of directory or filename patterns to skip.

    Example output:
        ├── folder1
        │   ├── file1.py
        │   └── file2.py
        └── folder2
            └── file3.py
    """
    if ignore is None:
        ignore = [".git", "__pycache__", "*.pyc", "*.pyo", ".DS_Store"]

    lines = []
    try:
        entries = os.listdir(root_path)
    except Exception as e:
        return f"Error reading directory {root_path}: {e}"

    # Filter out ignored entries
    entries = [
        entry for entry in entries
        if not any(fnmatch.fnmatch(entry, pattern) for pattern in ignore)
    ]

    entries.sort()
    entries_count = len(entries)
    for index, entry in enumerate(entries):
        full_path = os.path.join(root_path, entry)
        is_last = (index == entries_count - 1)
        connector = "└── " if is_last else "├── "
        lines.append(prefix + connector + entry)
        if os.path.isdir(full_path):
            extension_prefix = prefix + ("    " if is_last else "│   ")
            subtree = get_tree(full_path, extension_prefix, ignore)
            if subtree:
                lines.append(subtree)
    return "\n".join(lines)
