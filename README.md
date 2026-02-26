# LessonForge

AI-powered lesson resource generator for Australian Mathematics, aligned to the ACARA v9 curriculum.

## Quick Start

```bash
# 1. Clone and configure
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY

# 2. Start everything
docker compose up --build

# 3. Open
# Frontend:  http://localhost:3000
# Backend:   http://localhost:8000
# API docs:  http://localhost:8000/docs
```

## What It Does

An educator describes what they want to teach, selects a resource type (e.g. Worked Example Study, Exit Ticket, Task Set), and the system generates a tailored, curriculum-aligned educational resource through a 6-step AI workflow:

1. **Input Analysis** -- parses the teacher's free-text request
2. **Curriculum Match (CAG)** -- semantically matches against all 240 ACARA v9 content descriptors
3. **Teaching Focus Router** -- routes through one of 5 teaching approaches with year-band conditioning
4. **Pedagogy Retrieval (RAG)** -- retrieves relevant elaborations and pedagogy from pgvector
5. **Template Resolution** -- selects and resolves a database-driven prompt template
6. **Resource Generation** -- streams the final resource via SSE

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI, Uvicorn, SQLAlchemy 2.0, Alembic |
| AI Workflow | Agno Workflows 2.0 (Steps, Router) |
| LLM | OpenAI GPT-4o-mini (parsing) + GPT-4o (generation) |
| Database | PostgreSQL 16 + pgvector |
| Vector Store | Agno PgVector + text-embedding-3-small |
| Frontend | Vanilla HTML/CSS/JS, marked.js |
| Infrastructure | Docker Compose, Nginx reverse proxy |

## Architecture

```
Teacher Input
    |
    v
[InputAnalyzer]  --> Agent: parse free-text
[CurriculumMatcher] --> CAG: all 240 descriptors in context
[TeachingFocusRouter] --> Router: 5 paths x 3 year bands
[PedagogyRetriever] --> RAG: pgvector similarity search
[TemplateResolver] --> DB: priority-based template selection
[ResourceGenerator] --> Agent: GPT-4o streaming output
    |
    v
SSE Stream --> Frontend (markdown rendering + execution trace)
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/generate` | Generate resource (SSE streaming) |
| GET | `/api/generations` | List recent generations (history) |
| GET | `/api/debug/{id}` | Full generation log with step data |
| GET | `/api/reference/year-levels` | 11 year levels (Foundation-Y10) |
| GET | `/api/reference/strands` | 6 maths strands |
| GET | `/api/reference/teaching-focuses` | 5 teaching focuses |
| GET | `/api/reference/resource-types` | 17 resource types (filterable) |

## Database

9 tables seeded from ACARA v9 curriculum data:

- **year_levels** (11) -- Foundation to Year 10
- **strands** (6) -- Number, Algebra, Measurement, Space, Statistics, Probability
- **content_descriptors** (240) -- curriculum content items
- **elaborations** (1049) -- detailed elaborations per descriptor
- **achievement_standards** -- per year level outcomes
- **teaching_focuses** (5) -- teaching approach categories
- **resource_types** (17) -- resource types across focuses
- **prompt_templates** -- DB-driven prompt templates with priority matching
- **generation_logs** -- audit trail with debug data

Plus **pedagogy_vectors** (pgvector, Agno-managed) for RAG embeddings.

## Running Tests

```bash
# Unit tests (no Docker required)
pip install -e ".[dev]"
pytest tests/unit/ -v

# Full test suite (requires running database)
pytest -v
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | Yes | OpenAI API key for LLM and embeddings |
| `DATABASE_URL` | No | PostgreSQL connection string (set automatically in Docker) |
| `OPENAI_MODEL_SMALL` | No | Model for parsing tasks (default: `gpt-4o-mini`) |
| `OPENAI_MODEL_LARGE` | No | Model for generation (default: `gpt-4o`) |

## Project Structure

```
lesson-forge/
├── backend/
│   ├── api/           # FastAPI routes + schemas
│   ├── db/            # SQLAlchemy models + session
│   ├── workflow/      # Agno workflow + 6 step executors
│   ├── knowledge/     # PgVector knowledge base setup
│   └── services/      # CAG matching + template resolution
├── frontend/          # HTML/CSS/JS SPA
├── data/              # Curriculum JSON + pedagogy docs
├── scripts/           # Seed scripts + entrypoint
├── alembic/           # Database migrations
├── tests/             # Unit + integration tests
├── docker-compose.yml
└── DESIGN.md          # Detailed design specifications
```
