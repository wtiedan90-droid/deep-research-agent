FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONUTF8=1

WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY src/ ./src/
RUN python -m pip install --no-cache-dir . "langgraph-cli[inmem]==0.4.43"

COPY langgraph.json ./

EXPOSE 2024
CMD ["langgraph", "dev", "--host", "0.0.0.0", "--no-browser", "--no-reload"]
