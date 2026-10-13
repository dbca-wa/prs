# syntax=docker/dockerfile:1
# Args to centralise versions.
ARG PYTHON_VERSION=3.13-debian13-dev

# ---- Builder stage ----
FROM dhi.io/python:${PYTHON_VERSION} AS builder

RUN <<EOF
set -euxo pipefail
apt-get update
apt-get install -y --no-install-recommends \
  gdal-bin \
  proj-bin \
  libgdal-dev \
  libmagic1t64 \
  gcc \
  g++
EOF

WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:0.12 /uv /bin/
COPY pyproject.toml uv.lock ./
RUN uv sync --no-group dev --link-mode=copy --compile-bytecode --no-python-downloads --frozen

# ---- runtime stage: minimal packages needed to run the application ----
FROM dhi.io/python:${PYTHON_VERSION} AS runtime
LABEL org.opencontainers.image.authors=asi@dbca.wa.gov.au \
  org.opencontainers.image.source=https://github.com/dbca-wa/prs \
  org.opencontainers.image.description="DBCA Planning Referral System" \
  org.opencontainers.image.source="https://github.com/dbca-wa/prs" \
  org.opencontainers.image.vendor="DBCA" \
  org.opencontainers.image.authors="asi@dbca.wa.gov.au"

RUN <<EOF
set -euxo pipefail
apt-get update
apt-get install -y --no-install-recommends \
  gdal-bin \
  proj-bin \
  libgdal36 \
  libmagic1t64
ldconfig
rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*
EOF

# Environment variables
ENV PYTHONUNBUFFERED=1 \
  PYTHONDONTWRITEBYTECODE=1 \
  PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Copy installed virtualenv from builder
COPY --from=builder /app /app

# Copy the remaining project files to finish building the project
COPY --chown=nonroot:nonroot gunicorn.py manage.py pyproject.toml uv.lock ./
COPY --chown=nonroot:nonroot harvester ./harvester
COPY --chown=nonroot:nonroot indexer ./indexer
COPY --chown=nonroot:nonroot prs ./prs
COPY --chown=nonroot:nonroot referral ./referral
COPY --chown=nonroot:nonroot reports ./reports

# Compile scripts and collect static files
RUN <<EOF
python -m compileall -q prs harvester indexer referral reports
python manage.py collectstatic --noinput
EOF

# Run the project as the nonroot user
USER nonroot
EXPOSE 8080
CMD ["gunicorn", "prs.wsgi", "--config", "gunicorn.py"]
