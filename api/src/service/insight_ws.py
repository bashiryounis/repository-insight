import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect


router = APIRouter()
logger = logging.getLogger(__name__)

@router.websocket("/")
async def query_endpoint(websocket: WebSocket):
    from src.agent.insight.core import stream_agent_response_to_websocket
    await websocket.accept()
    try:
        while True:
            # 1) Receive and validate the raw JSON
            data = await websocket.receive_json()
            query = data.get("query")
            if not isinstance(query, str) or not query.strip():
                await websocket.send_json({
                    "type": "error",
                    "payload": "Invalid payload – expected { \"query\": \"...\" }."
                })
                continue

            await stream_agent_response_to_websocket(websocket, user_query=query, target_agent="PlannerAgent")

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected by client")
    except Exception as exc:
        logger.exception("Unexpected error in WebSocket handler", exc_info=exc)
        try:
            await websocket.send_json({
                "type": "error",
                "payload": f"Server error: {exc}"
            })
        except:
            pass
    finally:
        await websocket.close()