import asyncio
import json_repair
import logging
from llama_index.core.agent.workflow import AgentWorkflow
from src.agent.agents import (
    dependency_agent,
    summary_agent,
    description_agent,
    complexity_agent,
    parser_code_agent,
    filter_agent
)
from src.agent.utils import extract_file_content, get_project_tree_string, extract_tool_output_structures


# Initialize the workflow with an initial state.
logger=logging.getLogger(__name__)

async def run_filter_agent(repo_content:str): 
    """Runs the filter agent to classify files in the repository based on the provided content."""
    results  = await filter_agent.run(repo_content)
    filter_result =  json_repair.loads(results.response.content)
    return filter_result


async def run_code_analysis_agent(file_path: str, repo_base:str):
    """Run description and summary in parallel, then conditionally run further analysis agents based on the summary result."""
    try:
        file_content = await  extract_file_content(file_path)
        project_tree =  get_project_tree_string(repo_base)
        description_result, summary_result = await asyncio.gather(
            description_agent.run(file_content),
            summary_agent.run(file_content)
        )
        summary_result =  json_repair.loads(summary_result.response.content)

        # Check the summary result
        if not summary_result.get("need_analysis", False):
            return {
                "file_description": description_result.response.content,
                "code_summary": summary_result,
                "file_content":file_content,
                "message": "No further analysis required (summary returned False)."
            }
        combined_content = (
            "Project Tree:\n"
            "-------------\n"
            f"{project_tree}\n\n"
            "File Content:\n"
            "-------------\n"
            f"{file_content}"
        )
        # If summary is True, continue with the other agents (complexity, dependency, parser)
        complexity_result, dependency_result ,parser_code_result = await asyncio.gather(
            complexity_agent.run(file_content),
            dependency_agent.run(combined_content),
            parser_code_agent.run(file_content)
        )

        # Aggregate the results into the state dictionary
        state = {
            "file_description": description_result.response.content,
            "code_summary":summary_result,
            "complexity_analysis": complexity_result.response.content,
            "dependency_analysis":json_repair.loads(dependency_result.response.content),
            "code_analysis": extract_tool_output_structures(parser_code_result),
            "file_content":file_content,
        }

        return state

    except Exception as e:
        logger.error(f"Error during code analysis: {e}")
        return {"error": str(e)}
