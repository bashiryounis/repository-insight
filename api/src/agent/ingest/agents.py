from llama_index.core.agent.workflow import FunctionAgent, AgentWorkflow
from src.agent.ingest.tool import (
    generate_file_description,
    generate_code_summary,
    analyze_complexity,
    analyze_dependency, 
    extract_class_block,
    extract_method_block, 
    extract_script_block,
    filter_tree_repository
    )
from src.agent.ingest.prompt import (
    CODE_DESCRIPTION_PROMPT,
    CODE_SUMMARY_PROMPT,
    CODE_COMPLIXTY_PROMPT,
    CODE_DEPENDENCY_PROMPT,
    CODE_PARSER_PROMPT,
    FILTER_TREE_PROMPT

)
from src.agent.llm import get_llm_gemini

def build_description_agent():
    return FunctionAgent(
            name="DescriptionAgent",
            description="Generates a detailed description of a file based on its code.",
            system_prompt=CODE_DESCRIPTION_PROMPT,
            llm=get_llm_gemini(),  # Replace with your LLM instance as needed.
            tools=[generate_file_description]
        )
def build_summary_agent():
    return FunctionAgent(
        name="SummaryAgent",
        description="Generates a summary of the code including its functionality.",
        system_prompt=CODE_SUMMARY_PROMPT,
        llm=get_llm_gemini(),
        tools=[generate_code_summary]
    )

def build_complexity_agent():
    return FunctionAgent(
        name="ComplexityAgent",
        description="Analyzes the complexity of the code.",
        system_prompt=CODE_COMPLIXTY_PROMPT,
        llm=get_llm_gemini(),
        tools=[analyze_complexity],
    )

def build_dependency_agent():
    return  FunctionAgent(
        name="DependencyAgent",
        description="Analyzes code dependencies and extracts internal dependency as a comprehensive structured list.",
        system_prompt=CODE_DEPENDENCY_PROMPT,
        llm=get_llm_gemini(),
        tools=[analyze_dependency]
    )

def build_parser_code_agent():
    return AgentWorkflow.from_tools_or_functions(
        system_prompt = CODE_PARSER_PROMPT,
        llm=get_llm_gemini(),
        tools_or_functions=[extract_class_block, extract_method_block, extract_script_block],
        initial_state={
                "scripts": [],
                "classes": [],
                "methods": []
        }
    )

def build_filter_agent():
    return FunctionAgent(
        name="FileClassificationAgent",
        description="This agent classifies files in a repository based on their name, type, and location within the project structure. The agent filters out files that are not useful for further analysis (e.g., Dockerfiles, README files, binary files, configuration files) and returns a classification of 'useful' and 'not useful' files. This helps reduce processing overhead during subsequent stages of the pipeline, such as parsing, dependency resolution, and code splitting.",
        system_prompt=FILTER_TREE_PROMPT,
        llm=get_llm_gemini(),
        tools=[filter_tree_repository]
    )
