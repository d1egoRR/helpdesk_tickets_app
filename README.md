# Helpdesk Tickets App

Helpdesk ticket management API built with Python, FastAPI, LangChain, and LangGraph following Hexagonal Architecture (Ports and Adapters).

## Tech Stack

- **Python**: 3.12+
- **API Framework**: FastAPI + Uvicorn
- **Configuration**: Pydantic Settings
- **AI Orchestration**: LangChain, LangChain Core, LangChain OpenAI, LangChain Chroma, LangGraph
- **Vector Store**: ChromaDB
- **Testing & Quality**: pytest, httpx, Ruff
- **Containerization**: Docker & Docker Compose (development setup)

## Project Structure

```text
.
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
├── requirements.txt
├── requirements-dev.txt
├── .env.example
├── src/
│   └── helpdesk/
│       ├── config.py
│       ├── main.py
│       └── adapters/
│           ├── inbound/
│           │   └── http/
│           │       └── health.py
│           └── outbound/
│               └── vectorstore/
│                   └── chroma_setup.py
└── tests/
    └── test_health.py
```

Additional architectural layers (`domain`, `application`) will be added incrementally as ticket, chat, and AI agent use cases are implemented.

## Configuration

Copy the environment template before running locally:

```bash
cp .env.example .env
```

Update `.env` with your local values (for example, `OPENAI_API_KEY` once LLM features are enabled). Never commit `.env` to version control.

## Running with Docker Compose

Build the development image:

```bash
docker compose build
```

Start the API with hot-reload on `http://localhost:8000`:

```bash
docker compose up
```

Interactive OpenAPI documentation is available at `http://localhost:8000/docs`, and the health endpoint is at `GET /health`.

## Vector Store Setup (ChromaDB)

Index the Markdown knowledge base in `docs/` into ChromaDB (one-time setup):

```bash
docker compose run --rm api python -m helpdesk.adapters.outbound.vectorstore.chroma_setup
```

Force rebuilding the persisted ChromaDB database from scratch:

```bash
docker compose run --rm api python -m helpdesk.adapters.outbound.vectorstore.chroma_setup --force
```

## Testing & Linting

Verify that core dependencies import properly:

```bash
docker compose run --rm api python -c "import fastapi, uvicorn, pydantic_settings, langchain, langchain_core, langchain_openai, langgraph, pytest; print('All packages imported successfully')"
```

Run the test suite:

```bash
docker compose run --rm api pytest -v
```

Run linting and formatting checks with Ruff:

```bash
docker compose run --rm api ruff check src tests
```
