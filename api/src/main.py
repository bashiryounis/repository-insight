import logging
from fastapi import FastAPI
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
from src.service.api import router as repo_router
from src.core.index import setup_all_indexes

setup_logging()
logger=logging.getLogger(__name__)

app = FastAPI(
    debug=True,
    title="Repo Insight API – Repository Intelligence Unleashed",
    description="""
    Repo Insight Agent automates repository analysis by cloning a target repo, building a Neo4j graph of its code structure, and processing natural language queries to deliver actionable insights.   
    """
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

@app.on_event("startup")
async def initialize_indexes():
    try:
        logger.info("Running vector index setup on startup...")
        await setup_all_indexes()
        logger.info("Vector index setup complete.")
    except Exception as e:
        logger.error(f"Error during index setup: {e}")


# Redirect root path to API documentation
@app.get("/", include_in_schema=False)
def root_redirect():
    """
    Redirects the root URL to the API documentation.
    """
    return RedirectResponse(url="/docs/")

app.include_router(repo_router, prefix="/api", tags=["Repository Opreation"])