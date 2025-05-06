import re
from typing import Dict, Literal, List, Optional, Any
from collections import defaultdict


async def extract_node(node_name: str, node_label: Literal["File", "Folder", "Class", "Method"]) -> Dict[str, str]:
    """Useful to extract exactly one repository entity from the user query."""
    return {"node_label": node_label, "node_name": node_name}

def build_nested_tree(records: List[dict]) -> dict:
    """Build nested dict from path lists."""
    tree = lambda: defaultdict(tree)
    root = tree()
    for record in records:
        current = root
        for part in record["path_names"]:
            current = current[part]
        current["_meta"] = {
            "label": record["label"],
            "description": record.get("description"),
            "content": record.get("content")
        }
    return root

def format_nested_tree(tree: Dict[str, Any], prefix: str = "") -> str:
    """Convert nested tree to formatted text."""
    lines = []
    entries = sorted(tree.items())
    entries_meta = [(k, v) for k, v in entries if k != "_meta"]
    total_entries = len(entries_meta)

    for idx, (name, subtree) in enumerate(entries_meta):
        connector = "└── " if idx == total_entries - 1 else "├── "
        lines.append(f"{prefix}{connector}{name}")

        # Add description and code if present
        meta = subtree.get("_meta")
        if meta:
            desc = meta.get("description")
            content = meta.get("content")
            if desc:
                lines.append(f"{prefix}{'    ' if idx == total_entries -1 else '│   '}📌 {desc}")
            if content:
                content_lines = content.strip().split("\n")
                formatted_content = "\n".join(f"{prefix}{'    ' if idx == total_entries -1 else '│   '}    {line}" for line in content_lines)
                lines.append(f"{prefix}{'    ' if idx == total_entries -1 else '│   '}💻 Code:\n{prefix}{'    ' if idx == total_entries -1 else '│   '}    ```\n{formatted_content}\n{prefix}{'    ' if idx == total_entries -1 else '│   '}    ```")

        # Recursive call for children
        extension = "    " if idx == total_entries - 1 else "│   "
        lines.append(format_nested_tree(subtree, prefix + extension))

    return "\n".join(filter(None, lines))

def format_search_results(records: List) -> str:
    """Formats list of nodes for LLM input."""
    parts: List[str] = []
    for r in records:
        name = r["name"]
        desc = f": {r['description']}" if r.get("description") else ""
        content = r.get("content", "").rstrip()
        parts.append(
            f"\n\n**Name:** {name}\n"
            f"**Description**{desc}\n\n"
            f"**Code:**\n```\n{content}\n```\n"
        )
    return "\n".join(parts)