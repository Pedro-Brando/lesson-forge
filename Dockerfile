FROM python:3.12-slim

WORKDIR /app

ENV PYTHONPATH=/app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev dos2unix && \
    rm -rf /var/lib/apt/lists/*

# Copy all project files
COPY pyproject.toml .
COPY alembic.ini .
COPY alembic/ alembic/
COPY scripts/ scripts/
COPY backend/ backend/
COPY data/ data/

# Fix Windows line endings in shell scripts
RUN find /app/scripts -name '*.sh' -exec dos2unix {} +

# Install dependencies
RUN pip install --no-cache-dir .

EXPOSE 8000
