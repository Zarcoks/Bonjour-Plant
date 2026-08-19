# Stage 1: Builder
FROM python:3.13-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /app/wheels -r requirements.txt

# Stage 2: Runtime
FROM python:3.13-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy wheels and install
COPY --from=builder /app/wheels /wheels
RUN pip install --no-cache /wheels/* && rm -rf /wheels

# Create non-root user
RUN useradd -m -u 1000 appuser

WORKDIR /app

# Copy application
COPY --chown=appuser:appuser . .

# The uploads and the collected static files live in volumes: created here so
# that the volumes inherit the ownership of the user running the application.
RUN mkdir -p /app/media /app/staticfiles \
    && chown appuser:appuser /app/media /app/staticfiles \
    && chmod +x entrypoint.sh

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

CMD ["sh", "entrypoint.sh"]
