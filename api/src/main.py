from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import RedirectResponse
from contextlib import asynccontextmanager



app = FastAPI(
    debug=True,
    title="QA Agent API",
    description="API server providing various functionalities including user operations, file handling, and chat services.",
)



# Configure CORS middleware to allow requests from any origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods
    allow_headers=["*"],  # Allow all headers
)

# Redirect root path to API documentation
@app.get("/", include_in_schema=False)
def root_redirect():
    """
    Redirects the root URL to the API documentation.
    """
    return RedirectResponse(url="/docs/")

