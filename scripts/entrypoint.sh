#!/bin/bash
set -e

echo "=== Running Alembic migrations ==="
alembic upgrade head

echo "=== Seeding reference data ==="
python -m scripts.seed_data

echo "=== Seeding knowledge base ==="
python -m scripts.seed_knowledge

echo "=== Starting server ==="
uvicorn backend.main:app --host 0.0.0.0 --port 8000
