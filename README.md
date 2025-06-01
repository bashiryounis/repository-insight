# Repository Insight Service

A powerful service that transforms code repositories into intelligent knowledge graphs using Neo4j, enabling advanced analysis and deep codebase understanding through AI-powered insights.

##  Overview

Repository Insight Service automatically ingests Git repositories and creates comprehensive knowledge graphs that capture the structure, relationships, and semantics of your codebase. It leverages LLM-powered analysis and vector embeddings to enable intelligent querying and exploration of codebases at scale.

##  Key Features

###  Knowledge Graph Construction
- **Multi-node Architecture**: Creates structured nodes for files, folders, commits, branches, classes, methods, and scripts
- **Rich Relationships**: Establishes meaningful connections between code entities
- **Git Integration**: Full Git history analysis with commit tracking and branch relationships
- **Hierarchical Structure**: Maintains repository folder/file hierarchy

###  AI-Powered Analysis
- **LLM Enhancement**: Generates intelligent descriptions for code entities using Gemini
- **Vector Embeddings**: Enables semantic search and similarity matching
- **Multi-Agent System**: Specialized agents for discovery, research, and relationship analysis
- **Real-time Streaming**: WebSocket-based streaming responses for interactive analysis

### 🔍 Advanced Querying
- **Semantic Search**: Find code based on functionality rather than just keywords
- **Dependency Analysis**: Track relationships and dependencies between code components
- **Path Finding**: Discover connections between any two code entities
- **Context-Aware Insights**: Understand code structure and relationships at multiple levels

##  Architecture

### Knowledge Graph Schema

**Nodes:**
- **Repository**: Top-level container with metadata and project tree
- **Branch**: Git branches with commit tracking and file diffs
- **Commit**: Individual commits with touched files and relationships
- **Folder**: Directory structure with hierarchical organization  
- **File**: Source files with content and metadata
- **Class**: Code classes with descriptions and content
- **Method**: Functions/methods with detailed analysis
- **Script**: Standalone scripts and utilities

**Relationships:**
- `Repository` → `HAS_BRANCH` → `Branch`
- `Branch` → `CONTAINS_COMMIT` → `Commit`
- `Commit` → `MODIFIED_FILE` → `File`
- `Repository/Folder` → `CONTAINS` → `File/Folder`
- `File` → `DEPENDS_ON` → `File` (dependency relationships)

### Multi-Agent System

**PlannerAgent**: Central coordinator that orchestrates analysis workflows
- Routes queries to appropriate specialized agents
- Synthesizes results from multiple agents
- Provides comprehensive responses

**DiscoveryAgent**: Entity identification and extraction
- Locates specific code entities (files, classes, methods)
- Performs targeted graph searches
- Extracts relevant code snippets

**RelationResolverAgent**: Relationship and dependency analysis
- Maps dependencies between code entities
- Finds structural paths in the codebase
- Analyzes architectural relationships

**ResearcherAgent**: Semantic search and content analysis
- Performs vector similarity searches
- Finds semantically related code
- Provides context-aware recommendations

##  Getting Started

### Prerequisites
- Python 3.8+
- Neo4j database
- Docker , Docker compose 


### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/bashiryounis/repository-insight.git
   cd repository-insight 
   ```


2. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your Neo4j credentials and API keys
   ```

3. **Start the service**
   ```bash
   sudo make dev
   ```

4. **Frontend** 
  ```bash
  cd frontend
  pnpm dev 
  ```


##  API Usage

### Repository Ingestion

**Ingest a Git repository:**
```bash
POST /ingest
{
  "repo_url": "https://github.com/user/repository.git"
}
```

**List ingested repositories:**
```bash
GET /repos
```

### Intelligent Querying

**WebSocket connection for real-time analysis:**
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/insight');
ws.send(JSON.stringify({
  "query": "Find all authentication-related files in this repository"
}));
```

**Example queries:**
- "Show me all files that depend on the authentication module"
- "Find classes that handle database connections"
- "What are the main entry points of this application?"
- "Show me the relationship between user management and payment processing"

## 🛠️ Technical Stack

- **Backend**: FastAPI with async/await support
- **Database**: Neo4j graph database with vector indexes
- **AI/ML**: Google Gemini for LLM analysis, custom embeddings
- **Git Integration**: pygit2 for repository parsing
- **Agent Framework**: LlamaIndex workflow system
- **Communication**: WebSocket for real-time streaming

## 📁 Project Structure

```
src/
├── agent/                 # AI agents and workflows
│   ├── ingest/           # Code analysis agents
│   ├── insight/          # Query and insight agents
│   └── llm.py           # LLM configuration
├── core/                 # Core configuration and database
├── service/              # Business logic services
│   ├── ingest/          # Repository ingestion pipeline
│   └── websocket/       # Real-time communication
└── utils/               # Utility functions and helpers
```

##  Configuration

Key configuration options in `src/core/config.py`:

- **Neo4j Connection**: Database credentials and connection settings
- **LLM Settings**: API keys and model configurations  
- **Repository Storage**: Local storage paths for cloned repositories
- **Vector Indexes**: Embedding and search configurations

## 🎮 Use Cases

### Code Exploration
- **New Developer Onboarding**: Quickly understand large codebases
- **Architecture Analysis**: Discover system boundaries and dependencies
- **Code Navigation**: Find related functionality across the codebase

### Maintenance & Refactoring
- **Impact Analysis**: Understand the effect of changes before implementation
- **Dead Code Detection**: Identify unused or isolated components
- **Dependency Management**: Track and optimize inter-module dependencies

### Documentation & Knowledge Management
- **Automated Documentation**: Generate insights about code structure and purpose
- **Knowledge Preservation**: Capture institutional knowledge about the codebase
- **Code Quality Assessment**: Identify patterns and anti-patterns

