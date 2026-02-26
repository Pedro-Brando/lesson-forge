#!/usr/bin/env bash
set -e

echo "=== Running Alembic migrations ==="
cd /app
alembic upgrade head

echo "=== Seeding reference data ==="
python -c "from scripts.seed_data import main; main()"

echo "=== Seeding knowledge base ==="
# Knowledge seeding requires OPENAI_API_KEY for embeddings.
# If it fails (e.g. missing key), continue anyway so the server still starts.
python -c "from scripts.seed_knowledge import main; main()" || {
  echo "WARNING: Knowledge base seeding failed (OPENAI_API_KEY may be missing). RAG features will be unavailable."
}

echo "=== Starting server ==="
exec uvicorn backend.main:app --host 0.0.0.0 --port 8000
