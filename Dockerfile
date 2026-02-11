# Stage 1: Builder
FROM python:3.11-slim as builder

WORKDIR /app

# Install system dependencies including curl for poetry
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install poetry

# Copy configuration files
COPY pyproject.toml ./

# Configure poetry to create venv in project implementation
RUN poetry config virtualenvs.in-project true

# Install dependencies
# Note: We copy the rest of the code later to use docker cache efficiently
# If you have a lock file, copy it here too: COPY pyproject.toml poetry.lock ./
# For this initial setup, we run install which resolves dependencies
RUN poetry install --without dev --no-root --no-interaction --no-ansi

# Stage 2: Runner
FROM python:3.11-slim as runner

WORKDIR /app

# Install runtime dependencies for potential healthchecks or optimization
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application code
COPY . .

# Set environment variables
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app"
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Expose port
EXPOSE 8000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Run application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
