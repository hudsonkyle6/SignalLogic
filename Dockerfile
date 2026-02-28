# ── Build stage ──────────────────────────────────────────────────────────────
FROM python:3.11-slim AS build

WORKDIR /build
COPY pyproject.toml .
COPY src/ src/

# Install only the core runtime (no pandas/numpy unless you add [analytics])
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -e .


# ── Runtime image ─────────────────────────────────────────────────────────────
FROM python:3.11-slim

# Create a non-root user for the process
RUN useradd --system --no-create-home --shell /usr/sbin/nologin signallogic

WORKDIR /app
COPY --from=build /usr/local/lib/python3.11 /usr/local/lib/python3.11
COPY --from=build /usr/local/bin/signallogic-* /usr/local/bin/

# External data volume — never write into the image layer
ENV SIGNALLOGIC_DATA=/data
RUN mkdir -p /data /config && chown signallogic:signallogic /data /config

# Structured JSON logs in production; override to "text" for local dev
ENV LOG_FORMAT=json
ENV LOG_LEVEL=INFO

# Config file injected at runtime via volume mount
ENV SIGNALLOGIC_CONFIG=/config/deployment.yaml

VOLUME ["/data", "/config"]

USER signallogic

# Docker health check — exit 0 = warm, 1 = cold (degraded but alive), 2 = error
HEALTHCHECK --interval=60s --timeout=10s --start-period=120s --retries=3 \
    CMD signallogic-run --health

# Default command: run once.
# Override with "signallogic-meter" or "signallogic-run --loop 60" in compose.
CMD ["signallogic-run"]
