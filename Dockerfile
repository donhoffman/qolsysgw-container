# syntax=docker/dockerfile:1

# =============================================================================
# Build stage: Install dependencies
# =============================================================================
FROM python:3.13-slim as builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy and install Python dependencies
COPY requirements.txt /tmp/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /tmp/requirements.txt

# =============================================================================
# Runtime stage: Create minimal runtime image
# =============================================================================
FROM python:3.13-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH"

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Install runtime dependencies (procps for health check)
RUN apt-get update && apt-get install -y --no-install-recommends \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 -s /bin/bash qolsysgw && \
    mkdir -p /app && \
    chown -R qolsysgw:qolsysgw /app

# Set working directory
WORKDIR /app

# Copy application code (preserve apps/ directory structure for absolute imports)
COPY --chown=qolsysgw:qolsysgw apps /app/apps

# Copy health check script
COPY --chown=qolsysgw:qolsysgw docker-healthcheck.sh /app/docker-healthcheck.sh
RUN chmod +x /app/docker-healthcheck.sh

# Switch to non-root user
USER qolsysgw

# Health check
# Checks every 30s, timeout 10s, start checking after 40s, fail after 3 retries
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD ["/app/docker-healthcheck.sh"]

# Expose no ports (MQTT client only, no inbound connections)

# Run the application
CMD ["python", "-m", "apps.qolsysgw"]