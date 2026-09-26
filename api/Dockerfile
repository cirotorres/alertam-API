# syntax=docker/dockerfile:1.7

FROM python:3.12-slim-trixie AS base

COPY --from=ghcr.io/astral-sh/uv:0.12.19 /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

COPY pyproject.toml uv.lock ./

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=2)" || exit 1


FROM base AS dev

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --extra dev --no-install-project

COPY . /app

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]


FROM base AS prod

ENV UV_COMPILE_BYTECODE=1 \
    UV_NO_DEV=1

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-install-project

COPY app /app/app
COPY main.py /app/main.py

RUN useradd --create-home --uid 10001 alertam \
    && chown -R alertam:alertam /app

USER alertam

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
