import os
import asyncio
import logging
from pathlib import Path

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import RedirectResponse
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.sdk.resources import Resource, SERVICE_NAME
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.llamaindex import LlamaIndexInstrumentor
from src.core.logger_config import setup_logging
from src.core.index import setup_all_indexes
from src.core.config import config
from src.service.ingestion import router as ingestion_router
# from src.service.llama_ingestion import router as llama_router 
from src.service.insight_ws import router as websocket_router

setup_logging()
logger=logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # This runs before the app starts receiving requests
    if config.APP_ENV == "prod":
        if INDEX_FLAG_PATH.exists():
            logger.info("Index already exists. Skipping setup.")
            app.state.index_ready = True
        else:
            try:
                logger.info("Running vector index setup...")
                await setup_all_indexes()
                INDEX_FLAG_PATH.touch()
                app.state.index_ready = True
                logger.info("Vector index setup complete.")
            except Exception as e:
                logger.error(f"Error during index setup: {e}")
                app.state.index_ready = False
    else:
        app.state.index_ready = False  # for dev

    yield

    # This runs on shutdown
    logger.info("Application shutdown. Cleaning up if necessary.")

app = FastAPI(
    debug=True,
    title="Repo Insight API – Repository Intelligence Unleashed",
    description="""
    Repo Insight Agent automates repository analysis by cloning a target repo, 
    building a Neo4j graph of its code structure, and processing natural language 
    queries to deliver actionable insights.
    """,
    lifespan=lifespan
)

# Set the tracer provider
trace.set_tracer_provider(TracerProvider(resource=Resource.create({SERVICE_NAME:"Repository Insight"})))
tracer = trace.get_tracer(__name__)


# Configure the Jaeger exporter
jaeger_exporter = JaegerExporter(
    agent_host_name="jaeger",
    agent_port=6831,  # Jaeger agent port
)
jaeger_span_processor = BatchSpanProcessor(jaeger_exporter)
trace.get_tracer_provider().add_span_processor(jaeger_span_processor)

# Instrument the FastAPI app
FastAPIInstrumentor.instrument_app(app, tracer_provider=trace.get_tracer_provider())
LlamaIndexInstrumentor().instrument()

# Configure CORS middleware to allow requests from any origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods
    allow_headers=["*"],  # Allow all headers
)

INDEX_FLAG_PATH = Path(config.REPO_DIRS) / "index.ready"
app.state.index_ready = False

async def run_setup():
    if INDEX_FLAG_PATH.exists():
        logger.info("Index already exists. Skipping setup.")
        app.state.index_ready = True
        return

    try:
        logger.info("Running vector index setup...")
        await setup_all_indexes()
        INDEX_FLAG_PATH.touch()
        app.state.index_ready = True
        logger.info("Vector index setup complete.")
    except Exception as e:
        logger.error(f"Error during index setup: {e}")
        app.state.index_ready = False

# -- DEV MODE: Run setup via endpoint only --
if config.APP_ENV == "dev":
    @app.post("/index", tags=["Dev Tools"])
    async def trigger_index_build(secret: str = ""):
        if secret and secret != config.OPENAI_API_KEY:
            raise HTTPException(status_code=403, detail="Unauthorized")
        if app.state.index_ready:
            return {"status": "already built"}
        asyncio.create_task(run_setup())
        return {"status": "indexing started"}

    @app.get("/index/status", tags=["Dev Tools"])
    async def get_index_status():
        return {"ready": app.state.index_ready}
    

# Redirect root path to API documentation
@app.get("/", include_in_schema=False)
def root_redirect():
    """
    Redirects the root URL to the API documentation.
    """
    return RedirectResponse(url="/docs/")

app.include_router(ingestion_router, prefix="/api", tags=["Ingestion"])
# app.include_router(llama_router, prefix="/api", tags=["LlamaIndex Ingestion"])
app.include_router(websocket_router, tags=["WebSocket"])