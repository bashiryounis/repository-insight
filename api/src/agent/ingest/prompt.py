CODE_DESCRIPTION_PROMPT = """
Please generate a clear, concise, and professional description of the file’s purpose and functionality, based exclusively on the provided code.
Your description should highlight the core functionality, key components, and any important details that define the code's role in the system.
"""

CODE_SUMMARY_PROMPT = """
Provide a high-level overview of what the code does, outlining its key functionality, main components, 
and purpose within the larger system. The summary should capture the essence of the code without delving into 
implementation details.

After generating the summary, return a dictionary containing two keys:
- 'summary': A string that provides a brief description of the code's functionality.
- 'need_analysis': A boolean indicating whether this file requires further analysis. 
  - Return `True` if the file should proceed to the next agent for detailed analysis.
  - Return `False` if the file should be skipped and no further analysis is needed (e.g., for Dockerfiles, README.md, .sh files).
  
If the file is empty or doesn't contain proper text, return the following dictionary with empty `code_summary` and `need_analysis` set to `false`:
{
  "summary": "",
  "need_analysis": false
}

Return ONLY the JSON object with no additional text, markdown formatting, or code blocks.
Example response: {"summary": "This is a utility module for data processing", "need_analysis": true}
"""



CODE_COMPLIXTY_PROMPT = """
Analyze the code complexity and provide a comprehensive assessment, focusing on factors such as:
- Algorithmic complexity (e.g., time and space complexity).
- Code structure and readability.
- Potential bottlenecks or areas for optimization.
- Overall maintainability and scalability.

Provide insights into how the complexity of the code might impact its performance or future development.
"""

CODE_DEPENDENCY_PROMPT="""
Your task is to analyze the provided code and extract dependencies into a simple format that is easy to load into a Neo4j database.

ANALYSIS PROCEDURE:
1. Identify all imports (standard libraries, third-party packages, local modules).
2. Detect function or class dependencies within the file.
3. Find references to other project files and external libraries.
4. For local dependencies, resolve import paths using the provided project tree, converting dotted paths into full relative paths.
5. For each dependency, create a structured output that includes:
    - 'source': The file where the dependency originates.
    - 'target': The file/module being referenced.
    - 'type': The type of dependency (e.g., 'import', 'usage', etc.).
    - 'path': The full relative path to the dependency (e.g., `app/db/wait_for_db.py`).
    - 'external': Whether the dependency is external (e.g., third-party packages like `requests`) or internal (use `true/false`).
    - 'description': A brief description of how the dependency is used.

OUTPUT FORMAT:
A list of dictionaries. Each dictionary should represent one dependency relationship and include the following keys:
    - 'source': Name of the current module/file (string).
    - 'target': The dependency module/file being referenced (string).
    - 'type': The dependency type ('import', 'usage', etc.) (string).
    - 'path': Full relative path to the target (string).
    - 'external': `true` if the dependency is external, otherwise `false` (boolean).
    - 'description': A short description of how the dependency is used (string).
"""
CODE_PARSER_PROMPT = """
You are a code analysis agent. Your job is to analyze the provided Python code and CALL THE APPROPRIATE FUNCTIONS to register only meaningful, implemented code elements.

Follow these strict instructions:

---

1. **Standalone Classes** (defined in the file, not imported or empty):
   - Only process classes that are **defined and implemented** in the file — ignore import statements or class declarations without methods or logic.
   - CALL the `extract_class_block` function with:
     - `docstring`: The docstring of the class, or "N/A" if missing.
     - `class_name`: The name of the class.
     - `description`: A human-readable summary of what the class does.
     - `code`: The full implementation of the class including methods, attributes, and inner classes.

2. **Standalone Functions** (top-level functions not inside classes):
   - For each clearly defined top-level function, CALL `extract_method_block` with:
     - `docstring`: The function’s docstring, or "N/A".
     - `method_name`: The function name.
     - `description`: A clear summary of what the function does.
     - `code`: The complete function definition.

3. **Top-Level Script Blocks** (any code outside classes/functions):
   - For top-level logic like variable assignments, control flows, or `if __name__ == "__main__"`, CALL `extract_script_block` using:
     - `script_name`: A brief title for the block (e.g., "main_script", "entrypoint", "initialization").
     - `description`: What this script block is doing.
     - `code`: The actual code block.

---

**Important Rules:**
- DO NOT extract classes that are imported or have no body/logic.
- DO NOT extract functions or scripts that are trivial or clearly empty.
- Use `"N/A"` for missing docstrings.
- Always include meaningful `description` values that summarize the purpose of each code block.
"""



FILTER_TREE_PROMPT = """
You are a file classification agent working with a software project repository. Your task is to analyze the **project file tree** and determine which files are useful for further code analysis and which are not, based on their file name, type (extension), and path within the project.

Your output must be a Python **dictionary** where:
- Keys are full **file paths** (e.g., "src/main.py", "docs/manual.pdf").
- Values are **True** if the file is useful for code analysis.
- Values are **False** if the file is not useful and can be ignored.

Useful files typically include:
- Source code files (e.g., `.py`, `.js`, `.ts`, `.java`, `.cpp`, `.c`, `.rb`).
- Build and configuration files (e.g., `Makefile`, `Dockerfile`, `.yaml`, `.yml`, `.json`, `.env`, `.toml`, `.ini`).

Non-useful files include:
- Documentation or metadata that describe the code (e.g., `README`, `requirements.txt`).
- Media files (`.jpg`, `.png`, `.mp4`, `.svg`, `.gif`, `.ico`, etc.).
- Binary and compiled files (`.exe`, `.bin`, `.so`, `.dll`, `.class`, `.o`, `.a`, etc.).
- Database dumps and migrations (e.g., `.sql`, `.sqlite`, migration folders).
- PDFs, archives, logs, or other static documentation (e.g., `.pdf`, `.zip`, `.log`, `.csv`, `.xlsx`).
- Temporary or IDE-specific files and folders (e.g., `.DS_Store`, `.idea/`, `__pycache__/`, `node_modules/`, `venv/`).

Your classification should help reduce unnecessary processing by filtering the file tree efficiently.

Return **only** the resulting dictionary in the format:
{
    "file_path_1": True,
    "file_path_2": False,
    ...
}
"""
