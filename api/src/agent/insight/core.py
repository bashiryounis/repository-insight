import logging 
from llama_index.core.agent.workflow import AgentOutput, AgentStream
from llama_index.core.agent.workflow import AgentWorkflow
from collections import deque
from src.agent.insight.agents import (
    discovery_agent, planner_agent, relre_agent, research_agent, synthesis_agent
)

logger = logging.getLogger(__name__)

insight_agent=AgentWorkflow(
    agents=[planner_agent,discovery_agent, research_agent, relre_agent],
    root_agent=planner_agent.name,

)

async def stream_agent_response_to_websocket(websocket, user_query: str, target_agent: str = None):
    handler = insight_agent.run(user_msg=user_query)
    current_agent = None
    async for event in handler.stream_events():
        if (
            hasattr(event, "current_agent_name")
            and event.current_agent_name != current_agent
        ):
                current_agent = event.current_agent_name
                print(f"\n{'='*50}")
                print(f"🤖 Agent: {current_agent}")
                print(f"{'='*50}\n")

        if isinstance(event, AgentStream):
            if target_agent is None or current_agent == target_agent:
                await websocket.send_json({
                        "type": "stream",
                        "payload": event.delta
                    })
