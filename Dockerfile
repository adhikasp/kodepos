FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY . .

RUN apt-get update && \
    apt-get install -y curl && \
    python -m venv .venv && \
    curl -LsSf https://astral.sh/uv/install.sh | sh && \
    .venv/bin/pip install uv && \
    .venv/bin/uv pip compile pyproject.toml -o requirements.lock && \
    .venv/bin/uv pip sync requirements.lock && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

CMD [".venv/bin/uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
