import asyncio
import json_repair
import logging
from llama_index.core.agent.workflow import AgentWorkflow
from src.agent.ingest.agents import (
    dependency_agent,
    description_agent,
    parser_code_agent,
    filter_agent
)
from src.agent.ingest.tool import extract_file_content, get_project_tree_string, extract_tool_output_structures
from src.agent.ingest.utils import should_analyze, detect_language


# Initialize the workflow with an initial state.
logger=logging.getLogger(__name__)

async def run_filter_agent(repo_content:str): 
    """Runs the filter agent to classify files in the repository based on the provided content."""
    results  = await filter_agent.run(repo_content)
    filter_result =  json_repair.loads(results.response.content)
    return filter_result


async def run_code_analysis_agent(file_path: str, repo_base: str):
    """Run description and optionally dependency + parser agents based on analysis need."""
    try:
        file_content = await extract_file_content(file_path)
        language = detect_language(file_path)

        # Initialize state early
        state = {
            "file_content": file_content,
            "file_description": "",
            "skip_code_parser": False,
            "skip_dependency_parser": False,
            "analysis_skipped": False,
        }

        if not file_content or file_content.strip() == "":
            logger.info(f"File {file_path} is empty. Skipping all analysis.")
            state.update({
                "analysis_skipped": True,
                "skip_code_parser": True,
                "skip_dependency_parser": True,
                "skip_reason": "File is empty"
            })
            return state

        logger.info(f"File {file_path} is not empty. Proceeding with analysis.")

        description_result = await description_agent.run(file_content)
        state["file_description"] = description_result.response.content

        should_analyze_result = should_analyze(file_content, language)
        skip_code = not should_analyze_result["parse_classes_methods"]
        skip_deps = not should_analyze_result["parse_dependencies"]

        # If both are skipped
        if skip_code and skip_deps:
            logger.info(f"File {file_path} has no relevant structure.")
            state.update({
                "analysis_skipped": True,
                "skip_code_parser": True,
                "skip_dependency_parser": True,
                "skip_reason": "No relevant structure"
            })
            return state

        # Save individual skip flags
        state["skip_code_parser"] = skip_code
        state["skip_dependency_parser"] = skip_deps

        # Run only what’s needed
        project_tree = get_project_tree_string(repo_base)
        combined_content = (
            "Project Tree:\n"
            "-------------\n"
            f"{project_tree}\n\n"
            "File Content:\n"
            "-------------\n"
            f"{file_content}"
        )

        if not skip_deps:
            logger.info(f"Running dependency analysis for {file_path}...")
            dependency_result = await dependency_agent.run(combined_content)
            state["dependency_analysis"] = json_repair.loads(dependency_result.response.content)

        if not skip_code:
            logger.info(f"Running class/method parser for {file_path}...")
            parser_code_result = await parser_code_agent.run(file_content)
            state["code_analysis"] = extract_tool_output_structures(parser_code_result)

        return state

    except Exception as e:
        logger.error(f"Error during code analysis: {e}")
        return {
            "error": str(e),
            "file_path": file_path,
            "analysis_skipped": True,
            "skip_reason": "Error occurred"
        }
