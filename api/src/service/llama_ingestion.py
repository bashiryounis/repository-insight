import logging 
import os
import shutil 
from src.core.config import config 
from fastapi import APIRouter, HTTPException, status, BackgroundTasks

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/ingest-llamaindex", status_code=status.HTTP_201_CREATED)
async def clone_repo_llama(repo_url: str, background_tasks: BackgroundTasks):
    """Clone a Git repository using pygit2 into a designated directory for repositories."""
    from src.utils.llamaindex_ingest import ingest_repo as llamaindex_ingest_repo

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
    