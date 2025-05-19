from llama_index.core.agent.workflow import FunctionAgent
from src.agent.llm import get_llm_gemini
from src.agent.insight.tools.utils import extract_node 
from src.agent.insight.tools.neo4j_utils import (
   get_node_relationships_by_label,
   get_depend,
   find_path_between_nodes_by_label,
   get_full_path_to_node,
)
from src.agent.insight.tools.search import (
   search_graph,
   similarity_search
)

from src.agent.insight.prompt import (
   DISCOVERY_PROMPT, RELATION_PROMPT, RESEARCH_PROMPT, PLANNER_PROMPT,
)



def build_discovery_agent() -> FunctionAgent:
    return FunctionAgent(
        name="DiscoveryAgent",
        description="DiscoveryAgent is an autonomous retrieval agent that identifies, extracts, and searches exactly one code entity (File, Folder, Class, or Method) from a query using a graph database. It reports its findings in a specific format *only* to the PlannerAgent.",
        tools=[extract_node, search_graph],
        llm=get_llm_gemini(),
        system_prompt=DISCOVERY_PROMPT,
        can_handoff_to=["PlannerAgent"]
    )

def build_relre_agent() -> FunctionAgent:
    return FunctionAgent(
        name="RelationResolverAgent",
        description="Resolves dependencies, relationships, and structural paths between entities in the codebase graph, and hands the results back to the PlannerAgent.",
        tools=[find_path_between_nodes_by_label, get_node_relationships_by_label, get_depend, get_full_path_to_node],
        llm=get_llm_gemini(),
        system_prompt=RELATION_PROMPT,
        can_handoff_to=["PlannerAgent"]
    )


def build_research_agent() -> FunctionAgent:
    return FunctionAgent(
        name="ResearcherAgent",
        description="Performs semantic search based on user queries. Returns relevant files, descriptions, and snippets back to the PlannerAgent.",
        tools=[similarity_search],
        llm=get_llm_gemini(),
        system_prompt=RESEARCH_PROMPT,
        can_handoff_to=["PlannerAgent"]
      )

def build_planner_agent() -> FunctionAgent:
    return FunctionAgent(
        name="PlannerAgent",
        description="Central coordinator that reasons through codebase queries using other agents.",
        llm=get_llm_gemini(pro=True),
        system_prompt=PLANNER_PROMPT,
        can_handoff_to=["DiscoveryAgent", "RelationResolverAgent", "ResearcherAgent"]
    )