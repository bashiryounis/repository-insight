import os  

EXT_TO_LANG = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".java": "java",
    ".cpp": "cpp",
    ".c": "c",
    ".h": "cpp",
    ".cs": "csharp"
}

def detect_language(file_path):
    _, ext = os.path.splitext(file_path)
    return EXT_TO_LANG.get(ext.lower())

def should_analyze(code: str = None, language:str = None) -> dict:
    if not language:
        return {"language": None, "parse_classes_methods": False, "parse_dependencies": False, "reason": "Unsupported extension"}
    lines = code.splitlines()
    if len(lines) < 3:
        return {"language": language, "parse_classes_methods": False, "parse_dependencies": False, "reason": "Too short"}

    # Language-specific heuristics
    if language == "python":
        has_class = "class " in code
        has_func = "def " in code
        has_import = "import " in code or "from " in code
    
    elif language in ["javascript", "typescript"]:
        has_class = "class " in code
        has_func = "function " in code or "=>" in code
        has_import = "import " in code or "require(" in code
    
    elif language == "java":
        has_class = "class " in code or "interface " in code
        has_func = "void " in code or "public " in code
        has_import = "import " in code

    elif language == "cpp":
        has_class = "class " in code or "struct " in code
        has_func = "(" in code and ")" in code and "{" in code
        has_import = "#include" in code

    elif language == "go":
        has_class = "type " in code and "struct" in code  # pseudo-class via struct
        has_func = "func " in code
        has_import = "import " in code
    

    else:
        # Placeholder for future languages
        return {"language": language, "parse_classes_methods": False, "parse_dependencies": False, "reason": "No parser defined yet"}

    return {
        "language": language,
        "parse_classes_methods": has_class or has_func,
        "parse_dependencies": has_import,
        "reason": "Heuristics matched"
    }
