# LessonForge - Design Specifications

## Overview

LessonForge is an AI-powered lesson resource generator for Australian Mathematics educators, aligned to the ACARA v9 curriculum. It demonstrates a full-stack AI-first architecture with PostgreSQL reference data, Agno multi-step workflows, CAG/RAG patterns, SSE streaming, and database-driven prompt templates.

## Architecture

### System Diagram

```
┌─────────────────┐     ┌──────────────────────────────────────────┐
│                  │     │             Backend (FastAPI)             │
│    Frontend      │────>│  POST /api/generate (SSE)                │
│  (Nginx + HTML)  │<────│  GET  /api/debug/{id}                    │
│   Port 3000      │     │  GET  /api/reference/*                   │
│                  │     │                                          │
└─────────────────┘     │  ┌──────────────────────────────────┐    │
                        │  │    Agno Workflow (6 Steps)        │    │
                        │  │                                    │    │
                        │  │  1. InputAnalyzer (Agent/GPT-4o-m)│    │
                        │  │  2. CurriculumMatcher (CAG)       │    │
                        │  │  3. TeachingFocusRouter (Router)  │    │
                        │  │  4. PedagogyRetriever (RAG)       │    │
                        │  │  5. TemplateResolver (DB)         │    │
                        │  │  6. ResourceGenerator (Agent/4o)  │    │
                        │  └───────────────┬──────────────────┘    │
                        │                  │                        │
                        │  ┌───────────────┴──────────────────┐    │
                        │  │     PostgreSQL + pgvector          │    │
                        │  │  - 9 reference tables              │    │
                        │  │  - pedagogy_vectors (embeddings)   │    │
                        │  └──────────────────────────────────┘    │
                        │                          Port 8000        │
                        └──────────────────────────────────────────┘
```

### Tech Stack

| Component | Technology |
|-----------|-----------|
| Backend | FastAPI + Uvicorn |
| Workflow | Agno Workflows 2.0 (Steps, Router, Conditions) |
| LLM | OpenAI GPT-4o-mini (fast tasks) + GPT-4o (generation) |
| Database | PostgreSQL 16 + pgvector |
| ORM | SQLAlchemy 2.0 |
| Migrations | Alembic |
| Vector Store | Agno PgVector (manages its own table) |
| Embeddings | OpenAI text-embedding-3-small |
| Frontend | Vanilla HTML/CSS/JS + marked.js |
| Reverse Proxy | Nginx |
| Containerisation | Docker Compose |

## AI Patterns

### CAG (Context-Augmented Generation) - Step 2

All 240 ACARA v9 content descriptors are loaded into LLM context for semantic matching. This is preferable to RAG for this use case because:
- The dataset is finite and fits in context (~30k tokens)
- LLM can perform nuanced semantic matching (e.g., "fractions" matches "partition and combine collections using part-part-whole relationships")
- Returns confidence scores and reasoning for each match

### RAG (Retrieval-Augmented Generation) - Step 4

pgvector stores embeddings of:
- 1049 curriculum elaborations with metadata
- 5 pedagogy documents covering teaching approaches

Queries are constructed from matched descriptors + teaching focus + year level to retrieve the most relevant pedagogical context.

### Conditional Routing - Step 3

An Agno Router selects one of 5 teaching focus paths:
1. Explicit Instruction (I Do/We Do/You Do)
2. Deep Learning & Inquiry (thinking routines, open-ended)
3. Fluency & Practice (scaffolded repetition)
4. Assessment & Feedback (diagnostic, rubrics)
5. Planning (curriculum mapping, progression)

Each path adds focus-specific pedagogy notes. A secondary condition adds year-band-specific notes (early years / primary / secondary).

### Database-Driven Prompt Templates - Step 5

Prompt templates are stored in the `prompt_templates` table with:
- Resource type matching (NULL = any)
- Teaching focus matching (NULL = any)
- Year band matching (NULL = any)
- Priority scoring (higher wins)

Templates contain `{variable}` placeholders resolved from DB lookups at runtime.

## Database Schema

9 tables total:
- **year_levels** (11 rows) - Foundation to Year 10
- **strands** (6 rows) - Number, Algebra, Measurement, Space, Statistics, Probability
- **content_descriptors** (240 rows) - ACARA v9 content items
- **elaborations** (1049 rows) - Detailed elaborations per descriptor
- **achievement_standards** - Per year level expected outcomes
- **teaching_focuses** (5 rows) - The 5 teaching approach categories
- **resource_types** (17 rows) - Resource types across teaching focuses
- **prompt_templates** - DB-driven prompt templates with priority matching
- **generation_logs** - Audit trail with full step-by-step debug data

Plus **pedagogy_vectors** managed by Agno's PgVector class.

## Workflow Detail

### Step 1: InputAnalyzer
- **Type**: Agno Agent with GPT-4o-mini
- **Input**: Teacher's form data (topic, year level, strand, etc.)
- **Output**: Structured JSON with parsed topic, intent, keywords
- **Purpose**: Normalise free-text input for downstream steps

### Step 2: CurriculumMatcher (CAG)
- **Type**: Custom function step with Agno Agent
- **Input**: Parsed topic + all 240 content descriptors
- **Output**: Top 3-5 matching descriptors with confidence scores
- **CAG Pattern**: Full context loaded into LLM, not vector search

### Step 3: TeachingFocusRouter
- **Type**: Agno Router (selects 1 of 5 paths)
- **Input**: Teaching focus slug + year level
- **Output**: Routing decision with pedagogy notes
- **Conditions**: Year band differentiation (early/primary/secondary)

### Step 4: PedagogyRetriever (RAG)
- **Type**: Custom function step with PgVector search
- **Input**: Semantic query from matched descriptors + teaching focus
- **Output**: Top 5 relevant elaborations and pedagogy chunks
- **RAG Pattern**: Vector similarity search via Agno Knowledge

### Step 5: TemplateResolver
- **Type**: Custom function step with DB queries
- **Input**: Resource type, teaching focus, year band
- **Output**: Fully resolved prompt with all variables substituted
- **DB-Driven**: Template selected by priority matching

### Step 6: ResourceGenerator
- **Type**: Agno Agent with GPT-4o (streaming)
- **Input**: Fully resolved prompt from Step 5
- **Output**: Complete lesson resource in Markdown
- **Streaming**: Tokens streamed via SSE to frontend

## API Specification

### POST /api/generate
- **Content-Type**: multipart/form-data
- **Response**: text/event-stream (SSE)
- **Events**: generation_started, step_started, step_completed, cag_matches, routing_decision, rag_results, template_selected, content_chunk, generation_completed, error

### GET /api/debug/{generation_id}
- Returns complete generation log with all step data

### GET /api/reference/*
- /year-levels, /strands, /teaching-focuses, /resource-types
- Populate frontend dropdowns from database

## Data Sources

- **curriculum.json**: ACARA v9 Mathematics curriculum (240 content items, 1049 elaborations, 11 year levels, 6 strands)
- **message.txt**: 17 resource types across 5 teaching focuses with descriptions
- **pedagogy/*.md**: 5 pedagogy documents covering explicit instruction, inquiry, assessment, differentiation, and mathematical proficiencies
