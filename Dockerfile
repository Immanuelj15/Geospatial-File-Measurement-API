# ==============================================================================
# Production Dockerfile for AEREO Geospatial File Measurement API
# Multi-stage/Slim image with GDAL/PROJ/GEOS support and non-root execution
# ==============================================================================

FROM python:3.11-slim

# Set environment variables for Python runtime performance and consistency
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PORT=8000 \
    HOST=0.0.0.0

# Install runtime system libraries for GDAL, GEOS, PROJ, PostgreSQL, and healthcheck curl
RUN apt-get update && apt-get install -y --no-install-recommends \
    gdal-bin \
    libgdal-dev \
    libgeos-dev \
    libproj-dev \
    libpq5 \
    curl \
    dos2unix \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application source code and migration scripts
COPY alembic.ini .
COPY alembic/ alembic/
COPY app/ app/
COPY docker-entrypoint.sh .

# Normalize line endings and set permissions on entrypoint script
RUN dos2unix docker-entrypoint.sh && \
    chmod +x docker-entrypoint.sh

# Create non-root user and initialize uploads directory with appropriate permissions
RUN useradd --create-home --shell /bin/bash --uid 10001 appuser && \
    mkdir -p /app/uploads && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose HTTP port
EXPOSE 8000

# Container healthcheck against FastAPI health endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Execute database migrations and start server
ENTRYPOINT ["/app/docker-entrypoint.sh"]
