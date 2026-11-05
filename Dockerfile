# The locked dependencies are shared with local/CI builds. No database or source
# archive lives in this image; visitors only read an external PostgreSQL service.
FROM node:22-bookworm-slim AS frontend
WORKDIR /build/web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

FROM python:3.13-slim-bookworm AS python-build
COPY --from=ghcr.io/astral-sh/uv:0.13.7 /uv /bin/uv
ENV UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never UV_COMPILE_BYTECODE=1
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --locked --no-dev --no-install-project
COPY src/ ./src/
RUN uv sync --locked --no-dev --no-editable

FROM python:3.13-slim-bookworm AS runtime
RUN groupadd --gid 10001 commute && useradd --uid 10001 --gid commute --no-create-home commute
WORKDIR /app
COPY --from=python-build /app/.venv /app/.venv
COPY --from=frontend /build/web/dist /app/web/dist
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 COMMUTE_WEB_DIR=/app/web/dist
USER 10001:10001
EXPOSE 8000
CMD ["python", "-m", "commute.server"]
