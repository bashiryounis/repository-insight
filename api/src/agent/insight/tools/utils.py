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
        }
    return root

def format_nested_tree(tree: Dict[str, Any], prefix: str = "") -> str:
    """Convert nested tree to formatted text with brief descriptions."""
    lines = []
    entries = sorted((k, v) for k, v in tree.items() if k != "_meta")
    total_entries = len(entries)

    for idx, (name, subtree) in enumerate(entries):
        connector = "└── " if idx == total_entries - 1 else "├── "
        lines.append(f"{prefix}{connector}{name}")

        meta = subtree.get("_meta", {})
        description = meta.get("description")
        if description:
            brief_desc = (description[:250] + "…") if len(description) > 100 else description
            desc_prefix = "    " if idx == total_entries - 1 else "│   "
            lines.append(f"{prefix}{desc_prefix}📌 {brief_desc}")

        # Recursive call for nested children
        extension = "    " if idx == total_entries - 1 else "│   "
        subtree_str = format_nested_tree(subtree, prefix + extension)
        if subtree_str:
            lines.append(subtree_str)

    return "\n".join(lines)


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