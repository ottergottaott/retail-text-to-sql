FROM python:3.12.9-slim-bookworm
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_CACHE_DIR=/tmp/uv-cache
RUN pip install --no-cache-dir uv==0.9.11
COPY pyproject.toml uv.lock ./
COPY retail ./retail
COPY evaluation ./evaluation
COPY scripts ./scripts
COPY integrations ./integrations
RUN uv sync --frozen --no-dev --no-cache \
    && useradd --uid 10001 --create-home retail \
    && mkdir /data && chown retail:retail /data
ENV PATH="/app/.venv/bin:$PATH" LOG_PATH=/data/events.jsonl
USER retail
EXPOSE 8000
CMD ["uvicorn", "retail.api:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
