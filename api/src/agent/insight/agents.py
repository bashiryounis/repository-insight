from llama_index.core.agent.workflow import FunctionAgent
from src.agent.llm import llm_gemini
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
   SYNTHESIS_PROMPT
)

discovery_agent = FunctionAgent(
   name="DiscoveryAgent",
   description="DiscoveryAgent is an autonomous retrieval agent that identifies, extracts, and searches exactly one code entity (File, Folder, Class, or Method) from a query using a graph database. It reports its findings in a specific format *only* to the PlannerAgent and then hands off execution for further synthesis and user response.",
   tools=[extract_node, search_graph],
   llm=llm_gemini,
   system_prompt=DISCOVERY_PROMPT, 
   can_handoff_to= ["PlannerAgent"]
)

relre_agent = FunctionAgent(
   name="RelationResolverAgent",
   description="Resolves dependencies, relationships, and structural paths between entities in the codebase graph, and hands the results back to the PlannerAgent for final response synthesis.",
   tools=[find_path_between_nodes_by_label, get_node_relationships_by_label, get_depend, get_full_path_to_node],
   llm=llm_gemini, 
   system_prompt=RELATION_PROMPT,
   can_handoff_to=["PlannerAgent"]
)

research_agent = FunctionAgent(
   name="ResearcherAgent",
   description="Researches the codebase using semantic search based on user queries. Analyzes queries to search relevant Files, Classes, or Methods. It reports its findings, including relevant descriptions and potentially code or content snippets, in a specific format *only* to the PlannerAgent and then hands off execution for further synthesis and user response.",
   tools=[similarity_search],
   llm=llm_gemini,
   system_prompt=RESEARCH_PROMPT,
   can_handoff_to= ["PlannerAgent"] 
)

synthesis_agent = FunctionAgent(
   name="SynthesisAgent",
   description="Narrates the reasoning process by converting each planning note (plan, observation, final) into user-friendly Markdown explanations. Acts as the system's voice — progressively summarizing the PlannerAgent's steps and findings for the user, and handing of control back to the PlannerAgent after each response.",
   tools=[],
   llm=llm_gemini,
   system_prompt=SYNTHESIS_PROMPT,
   can_handoff_to=["PlannerAgent"]
)


planner_agent = FunctionAgent(
    name="PlannerAgent",
    description="Central coordinator that reasons through codebase queries using other agents, and emits structured plaintext notes.",
    llm=llm_gemini,
    system_prompt=PLANNER_PROMPT,
    can_handoff_to=["DiscoveryAgent", "RelationResolverAgent", "ResearcherAgent"]
)
