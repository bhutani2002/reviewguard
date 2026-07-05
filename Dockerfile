FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml .
RUN pip install uv && uv sync --no-dev

COPY agent/ ./agent/

# Cloud Run expects PORT env variable
ENV PORT=8080

# Simple HTTP wrapper around the agent for webhook mode
CMD ["uv", "run", "python", "-m", "agent.webhook_server"]
