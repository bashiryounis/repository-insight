import aiofiles 
import os
from llama_index.core.workflow import Context
from llama_index.core.agent.workflow import AgentInput, AgentOutput, ToolCall, ToolCallResult, AgentStream
# from src.agent.base import code_analysis_agent
# ----- TOOL FUNCTIONS -----

async def extract_file_content(file_path: str) -> str:
    """Extracts and returns the content of a file given its relative path from the repository base asynchronously."""
    try:
        async with aiofiles.open(file_path, mode='r', encoding='utf-8') as f:
            content = await f.read()
        return content
    except UnicodeDecodeError:
        try:
            async with aiofiles.open(file_path, mode='r', encoding='latin-1') as f:
                content = await f.read()
            return content
        except Exception as e:
            return f"Error reading file (tried multiple encodings): {str(e)}"
    except FileNotFoundError:
        return f"File not found: {file_path}"
    except Exception as e:
        return f"Error reading file: {str(e)}"

def get_project_tree_string(root_path: str, prefix: str = "") -> str:
    """
    Recursively generates a tree-like string for the given directory.
    Example output:
        ├── folder1
        │   ├── file1.py
        │   └── file2.py
        └── folder2
            └── file3.py
    """
    lines = []
    try:
        entries = os.listdir(root_path)
    except Exception as e:
        return f"Error reading directory {root_path}: {e}"
    
    entries.sort()
    entries_count = len(entries)
    for index, entry in enumerate(entries):
        full_path = os.path.join(root_path, entry)
        is_last = (index == entries_count - 1)
        connector = "└── " if is_last else "├── "
        lines.append(prefix + connector + entry)
        if os.path.isdir(full_path):
            extension_prefix = prefix + ("    " if is_last else "│   ")
            subtree = get_project_tree_string(full_path, extension_prefix)
            if subtree:
                lines.append(subtree)
    return "\n".join(lines)

async def get_combined_file_content_with_tree(file_path: str, repo_base_path: str) -> str:
    """Combines the project tree (as textual context) with the content of a file."""
    file_content = await extract_file_content(file_path)    
    project_tree = get_project_tree_string(repo_base_path)
    combined_content = (
        "Project Tree:\n"
        "-------------\n"
        f"{project_tree}\n\n"
        "File Content:\n"
        "-------------\n"
        f"{file_content}"
    )
    return combined_content

async def generate_file_description(ctx: Context, description:str) ->str :
    """Usefull to generate detailed description of a file based on its code"""
    current_state = await ctx.get("state")
    current_state["file_description"] = description
    await ctx.set("state", current_state)
    return "Description recorded."

async def generate_code_summary(ctx: Context, summary: str, need_analysis: bool) -> str:
    """Generates a detailed summary of a file's code and determines if further analysis is necessary based on the file's content."""
    current_state = await ctx.get("state")
    if "summary" not in current_state:
        current_state["summary"] = {}
    current_state["summary"]["summary"] = summary
    current_state["summary"]["need_analysis"] =  need_analysis
    await ctx.set("state", current_state)    
    return "Summary recorded."

async def analyze_complexity(ctx: Context, complexity_analysis: str) -> str:
    """Usefull to generate detailed analyze complexity of a file based on its code"""
    current_state = await ctx.get("state")
    current_state["complexity_analysis"] = complexity_analysis
    await ctx.set("state", current_state)
    return "complexity analysis detailed."

async def analyze_dependency(
    ctx: Context,
    source: str,
    target: str,
    type: str,
    relationship: str,
    is_external: bool,
    is_standard_lib: bool
) -> str:
    """Analyzes code dependencies and records detailed dependency information as a structured list"""
    current_state = await ctx.get("state")
    if "dependency_analysis" not in current_state:
        current_state["dependency_analysis"] = []
    
    dependency_item = {
        "source": source,
        "target": target,
        "type": type,
        "relationship": relationship,
        "is_external": is_external,
        "is_standard_lib": is_standard_lib
    }
    
    current_state["dependency_analysis"].append(dependency_item)
    await ctx.set("state", current_state)
    return "Dependency analysis completed with structured data."

async def extract_class_block(
        ctx: Context,
        docstring: str,
        class_name:str,
        description: str,
        code: str
    ):
    """Usefull to Extracts and registers a class block from the provided code."""
    current_state = await ctx.get("state")
    if "classes" not in current_state:
        current_state["classes"] = []
    class_block = {
        "description": description,
        "docstring": docstring,
        "class_name":class_name,
        "code": code
    }
    current_state["classes"].append(class_block)
    await ctx.set("state", current_state)
    return "Class block extraction completed"

async def extract_method_block(
    ctx: Context,
    docstring: str,
    method_name: str,
    code: str,
    description: str
):
    """Usefull to Extracts and registers a method block from the provided code."""
    current_state = await ctx.get("state")
    if "methods" not in current_state:
        current_state["methods"] = []
    method_block = {
        "description": description,
        "docstring": docstring,
        "method_name": method_name,
        "code": code
    }
    current_state["methods"].append(method_block)
    await ctx.set("state", current_state)
    return "Method block extraction completed"

async def extract_script_block(
    ctx: Context,
    code: str,
    description: str,
    script_name:str
):
    """Usefull to Extracts and registers a script block from the provided code."""
    current_state = await ctx.get("state")
    if "scripts" not in current_state:
        current_state["scripts"] =  []
    script_block = {
        "script_name": script_name,
        "description": description,
        "code": code,
    }
    
    current_state["scripts"].append(script_block)
    await ctx.set("state", current_state)
    return "Script block extraction completed"


async def filter_tree_repository(
        ctx: Context,
        file_path: str,  
        is_useful: bool,  
    ):
    """Classify files as useful or not useful based on their name and location within the repository."""
    current_state = await ctx.get("state")    
    if "file_filter" not in current_state:
        current_state["file_filter"] = {}
    current_state["file_filter"][file_path] = is_useful

    await ctx.set("state", current_state)    
    return f"File '{file_path}' classified as {'useful' if is_useful else 'not useful'}"

def extract_tool_output_structures(agent_output):
    state = {
        "classes": [],
        "methods": [],
        "scripts": []
    }

    for tool_call in agent_output.tool_calls:
        tool_name = tool_call.tool_name
        kwargs = tool_call.tool_kwargs

        if tool_name == "extract_class_block":
            state["classes"].append({
                "class_name": kwargs.get("class_name"),
                "description": kwargs.get("description"),
                "docstring": kwargs.get("docstring"),
                "code": kwargs.get("code")
            })

        elif tool_name == "extract_method_block":
            state["methods"].append({
                "method_name": kwargs.get("method_name"),
                "description": kwargs.get("description"),
                "docstring": kwargs.get("docstring", "N/A"),
                "code": kwargs.get("code")
            })

        elif tool_name == "extract_script_block":
            state["scripts"].append({
                "script_name": kwargs.get("script_name"),
                "description": kwargs.get("description"),
                "code": kwargs.get("code")
            })

    return state
