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
You are a code analysis agent. Your task is to analyze the provided code and EXECUTE THE APPROPRIATE FUNCTIONS to register each code element you find:

1. **Standalone Classes:** For EVERY standalone class you find (i.e., a class that is not nested inside another class or function):
   - You MUST CALL the `extract_class_block` function with the class's docstring, description, name, and the class's complete code, including any methods and attributes defined within the class.
   - This includes **all code related to the class**, such as methods, attributes, and any inner classes, if applicable.

2. **Methods Inside Classes:** For EVERY method **inside a class**:
   - You MUST CALL the `extract_method_block` function with the method's docstring, name, and code.
   - Methods are always extracted within their corresponding class.

3. **Standalone Functions:** For EVERY standalone function (i.e., functions that are not part of any class):
   - You MUST CALL the `extract_method_block` function with the function's code, description, and the function name.
   - This applies to functions that are **not inside any class** (top-level functions, not methods).

4. **Standalone Scripts:** For EVERY script block that is **not part of a function or class** (global-level code, initialization code, script sections):
   - You MUST CALL the `extract_script_block` function with the script's code and a description.
   - This applies to **any code that exists outside of a function or class**.

For each extracted element (class, function, or script), generate clear and concise description , ensuring that methods are nested within their corresponding classes, and script blocks are properly handled.

Make sure to EXECUTE the appropriate function for each element:
- `extract_class_block` for **standalone classes**, including all related code (methods, attributes, etc.).
- `extract_method_block` for **methods** inside classes and **standalone functions**.
- `extract_script_block` for **standalone script blocks** and **global code**.
"""

FILTER_TREE_PROMPT = """
You are a file classification agent. Your task is to classify files in a project repository based on their name, type, and location within the project structure. The goal is to help reduce the processing workload by identifying files that are useful for further analysis (e.g., code files) and those that are not useful (e.g., configuration files, documentation files, non-code files).

Please return a dictionary where:
- The keys are the **file paths**.
- The values are **True** for useful files and **False** for non-useful files.

Useful files are those that are relevant for further processing and analysis, such as:
- Code files (e.g., Python, JavaScript, TypeScript, etc.).
- Configuration files that are required for processing the code (e.g., `.json`, `.yml`, `.env` if they are required).

Non-useful files are those that are not required for further analysis, such as:
- Documentation files (e.g., README.md).
- Configuration files like Dockerfiles, YAML files used for deployment, or files that contain non-relevant data (e.g., `.pdf`, `.sh`, `.svg`).
- Binary files or files that would introduce errors or are not part of the core logic of the project.

Return ONLY the dictionary with the following format:
{
    "file_path_1": True,
    "file_path_2": False,
    ...
}
"""
