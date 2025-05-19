import logging
from typing import Optional

logger = logging.getLogger(__name__)


def build_insight_agent():
    from llama_index.core.agent.workflow import AgentWorkflow
    from src.agent.insight.agents import (
        build_planner_agent,
        build_discovery_agent,
        build_research_agent,
        build_relre_agent,
    )

    planner = build_planner_agent()  # Cache once to avoid repeated construction

    return AgentWorkflow(
        agents=[
            planner,
            build_discovery_agent(),
            build_research_agent(),
            build_relre_agent(),
        ],
        root_agent=planner.name,
    )


async def stream_agent_response_to_websocket(websocket, user_query: str, target_agent: Optional[str] = None):
    """Streams LLM agent responses to a WebSocket, optionally filtering by agent name."""
    from llama_index.core.agent.workflow import AgentStream
    handler = build_insight_agent().run(user_msg=user_query)
    current_agent = None

    async for event in handler.stream_events():
        if hasattr(event, "current_agent_name") and event.current_agent_name != current_agent:
            current_agent = event.current_agent_name
            logger.info(f"\n{'='*50}")
            logger.info(f"🤖 Agent: {current_agent}")
            logger.info(f"{'='*50}\n")

        if isinstance(event, AgentStream):
            if target_agent is None or current_agent == target_agent:
                await websocket.send_json({
                    "type": "stream",
                    "payload": event.delta
                })
