FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:0.7 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_NO_DEV=1 PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Dependencies first (cached layer), then source.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-install-project
COPY . .
RUN uv sync --locked

RUN useradd --create-home app
USER app

EXPOSE 8000
# Migrations run on start; fine for a single instance. Use a release step if you ever scale out.
CMD ["sh", "-c", "alembic upgrade head && fastapi run --host 0.0.0.0 --port 8000"]
