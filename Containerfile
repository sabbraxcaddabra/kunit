# syntax=docker/dockerfile:1

FROM node:22-slim AS web-assets

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY kunit/web/templates ./kunit/web/templates
COPY kunit/web/assets ./kunit/web/assets
RUN npm run build:css

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LC_ALL=C.UTF-8 \
    LANG=C.UTF-8 \
    PATH="/root/.local/bin:/app/.venv/bin:${PATH}"

WORKDIR /app

# System deps for installing uv
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install uv (Astral) — single static binary to ~/.local/bin/uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

# Copy project metadata first to leverage layer caching
COPY pyproject.toml ./
COPY uv.lock ./

# Create venv and install locked runtime dependencies (no dev, no project yet)
RUN uv sync --no-dev --frozen --no-install-project

# Copy application source and config
COPY kunit ./kunit
COPY --from=web-assets /app/kunit/web/static/css/app.css ./kunit/web/static/css/app.css
COPY gunicorn.conf.py ./gunicorn.conf.py
COPY AGENTS.md ./AGENTS.md

# Install the project itself into the existing venv (uses lock file)
RUN uv sync --no-dev --frozen

# Expose web port
EXPOSE 8000

# Run the Flask app via Gunicorn (WSGI) inside the uv-managed venv
CMD ["gunicorn", "-c", "gunicorn.conf.py", "kunit.web.app:app"]
