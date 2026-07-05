FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml .
RUN pip install uv && uv sync --no-dev

COPY agent/ ./agent/

# Cloud Run expects PORT env variable
ENV PORT=8090

# Starts the official ADK API server for the agent in this directory
CMD ["uv", "run", "adk", "api_server", "--host", "0.0.0.0", "--port", "8090", "./"]
