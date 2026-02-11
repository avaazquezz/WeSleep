# Stage 1: Builder
FROM python:3.11-slim as builder

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
  curl \
  build-essential \
  && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install "poetry==1.7.1"

# Copy configuration files
COPY pyproject.toml README.md ./

# Export dependencies to requirements.txt
# This avoids venv copying issues by generating a standard pip requirements file
RUN poetry export -f requirements.txt --output requirements.txt --without-hashes

# Stage 2: Runner
FROM python:3.11-slim as runner

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
  curl \
  && rm -rf /var/lib/apt/lists/*

# Copy requirements from builder
COPY --from=builder /app/requirements.txt .

# Install dependencies globally in the container
# This ensures uvicorn is in /usr/local/bin/uvicorn, which is definitely in PATH
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Set environment variables
ENV PYTHONPATH="/app"
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Expose port
EXPOSE 8000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Run application directly
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
