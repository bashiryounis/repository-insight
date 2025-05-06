import os
import logging
import pygit2
import asyncio
import shutil
from fastapi import APIRouter, HTTPException, status, BackgroundTasks,WebSocket, WebSocketDisconnect
from typing import List
from src.core.config import config
from src.core.db import get_session
from src.utils.llamaindex_ingest import ingest_repo as llamaindex_ingest_repo
from src.utils.graph_utils import ingest_repo
from src.agent.insight.core import stream_agent_response_to_websocket


router = APIRouter()
logger = logging.getLogger(__name__)

def clone_repository_sync(repo_url: str, destination: str):
    return pygit2.clone_repository(repo_url, destination)

@router.get("/", response_model=List[str])
async def get_repos():
    """
    Endpoint to get all repositories in the Neo4j database.
    """
    cypher = """
    MATCH (r:Repository)
    RETURN r.name AS name
    ORDER BY name
    """
    try:
        async with get_session() as neo_session:
            result = await neo_session.run(cypher)
            repos = [record["name"] async for record in result]
        return repos
    except Exception as e:
        logger.error(f"Error fetching repositories: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch repositories from database.")

@router.post("/ingest", status_code=status.HTTP_201_CREATED)
async def clone_repo(repo_url: str, background_tasks: BackgroundTasks):
    """Clone a Git repository using pygit2 into a designated directory for repositories."""
    repo_name = os.path.basename(repo_url.rstrip('/')).replace('.git', '')
    destination = os.path.join(config.REPO_DIRS, repo_name)
    if os.path.exists(destination):
        shutil.rmtree(destination)
    os.makedirs(config.REPO_DIRS, exist_ok=True)
    
    try:
        cloned_repo = await asyncio.get_running_loop().run_in_executor(
            None, clone_repository_sync, repo_url, destination
        )
        logger.info(f"Repository cloned successfully to {destination}")
        background_tasks.add_task(ingest_repo, cloned_repo)   
        return {
            "message": "Repository cloned successfully.",
            "repository_path": destination,
        }
    except Exception as e:
        logger.error(f"Error cloning repository: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error cloning repository: {e}"
        )


@router.post("/ingest-llamaindex", status_code=status.HTTP_201_CREATED)
async def clone_repo(repo_url: str, background_tasks: BackgroundTasks):
    """Clone a Git repository using pygit2 into a designated directory for repositories."""
    repo_name = os.path.basename(repo_url.rstrip('/')).replace('.git', '')
    destination = os.path.join(config.REPO_DIRS, repo_name)
    if os.path.exists(destination):
        shutil.rmtree(destination)
    os.makedirs(config.REPO_DIRS, exist_ok=True)
    
    try:
        cloned_repo = await asyncio.get_running_loop().run_in_executor(
            None, clone_repository_sync, repo_url, destination
        )
        logger.info(f"Repository cloned successfully to {destination}")
        background_tasks.add_task(llamaindex_ingest_repo, cloned_repo)   
        return {
            "message": "Repository cloned successfully.",
            "repository_path": destination,
        }
    except Exception as e:
        logger.error(f"Error cloning repository: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error cloning repository: {e}"
        )
    
@router.websocket("/")
async def query_endpoint(websocket: WebSocket):
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