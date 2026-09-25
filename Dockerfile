# Build Stage
FROM python:3.11-slim AS builder

WORKDIR /app
COPY requirements.txt .
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /app/wheels -r requirements.txt

# Production Stage
FROM python:3.11-slim

# Create a non-root user for security
RUN groupadd -r scrapergroup && useradd -r -g scrapergroup scraperuser

WORKDIR /app

# Install system dependencies required for psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy built wheels and install
COPY --from=builder /app/wheels /wheels
COPY --from=builder /app/requirements.txt .
RUN pip install --no-cache /wheels/*

# Copy application code
COPY src/ ./src/

# Ensure proper permissions
RUN chown -R scraperuser:scrapergroup /app

USER scraperuser

# Run the scheduler
CMD ["python", "-m", "src.main"]
