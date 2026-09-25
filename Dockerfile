# ── сборка ────────────────────────────────────────────────────────────
FROM python:3.13-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.12.6 /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# отдельным слоем: пока манифесты не менялись, зависимости берутся из кэша
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-install-project --no-dev

COPY README.md ./
COPY src ./src
RUN uv sync --locked --no-dev

# ── итоговый образ ────────────────────────────────────────────────────
FROM python:3.13-slim

RUN useradd --create-home --uid 1000 app
USER app

WORKDIR /app
COPY --from=builder /app /app

ENV PATH="/app/.venv/bin:$PATH"

CMD ["punctual"]
