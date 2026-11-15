# syntax=docker/dockerfile:1
# Args to centralise versions.
# PYTHON_VERSION is the DHI builder and runtime stage tag.
ARG PYTHON_VERSION=3.13-debian13-dev
ARG UV_VERSION=0.13

# ---- Stages ----
FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv
FROM dhi.io/python:${PYTHON_VERSION} AS builder

# ---- Builder stage ----
COPY --link --from=uv /uv /usr/local/bin/uv

WORKDIR /app

# Compilers and GDAL headers are needed only to build two dependencies from
# source. Neither is copied into the runtime image, which keeps only the
# runtime libs (see the runtime stage).
#   * gunicorn-h1c (gunicorn[fast]) publishes no cp313 wheel on any platform, so
#     its C extension is always compiled from the sdist -> gcc.
#   * fiona 1.10.1 publishes no linux/aarch64 cp313 wheel (amd64 uses the
#     manylinux wheel), so the linux/arm64 tier builds it from the sdist. That
#     build needs gdal-config from libgdal-dev and a C++ compiler for its
#     fiona._transform extension -> g++.
# A source-built fiona links the system libgdal.so.36 rather than a bundled
# copy, which the runtime stage already provides.
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
  --mount=type=cache,target=/var/lib/apt/lists,sharing=locked \
  apt-get update && apt-get install -y --no-install-recommends \
  gcc \
  g++ \
  libgdal-dev

# Install only runtime dependencies into /app/.venv. The venv path must match
# the runtime stage: uv writes absolute shebangs into console scripts such as
# gunicorn.
RUN --mount=type=cache,target=/root/.cache/uv \
  --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
  --mount=type=bind,source=uv.lock,target=uv.lock \
  uv sync --locked --no-group dev --link-mode=copy --compile-bytecode --no-python-downloads --no-install-project

# ---- runtime stage: minimal packages needed to run the application ----
# NOTE: the runtime stage requires the -dev base in order to provide a shell for the application
# to run Django management commands.
FROM dhi.io/python:${PYTHON_VERSION} AS runtime
LABEL org.opencontainers.image.description="DBCA Planning Referral System" \
  org.opencontainers.image.source="https://github.com/dbca-wa/prs" \
  org.opencontainers.image.vendor="DBCA" \
  org.opencontainers.image.authors="asi@dbca.wa.gov.au"

# Environment variables
ENV PYTHONUNBUFFERED=1 \
  PYTHONDONTWRITEBYTECODE=1 \
  PATH="/app/.venv/bin:$PATH"

# GDAL/GEOS/PROJ runtime libraries for django.contrib.gis. The DHI base has no
# /etc/ld.so.cache, so ldconfig is required for Django's ctypes-based lookup.
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
  --mount=type=cache,target=/var/lib/apt/lists,sharing=locked \
  apt-get update && apt-get install -y --no-install-recommends \
  libgdal36 \
  libgeos-c1t64 \
  libproj25 \
  proj-data \
  libmagic1t64 \
  && ldconfig

WORKDIR /app

# Copy installed virtualenv from builder (same path, so console-script shebangs stay valid).
# --chown must be numeric here: a link layer can't resolve usernames from the
# base image's /etc/passwd.
COPY --link --chown=65532:65532 --from=builder /app/.venv /app/.venv
COPY --link --chown=65532:65532 gunicorn.py manage.py pyproject.toml uv.lock ./
COPY --link --chown=65532:65532 harvester ./harvester
COPY --link --chown=65532:65532 indexer ./indexer
COPY --link --chown=65532:65532 prs ./prs
COPY --link --chown=65532:65532 referral ./referral
COPY --link --chown=65532:65532 reports ./reports

# Compile scripts and collect static files
RUN <<EOF
set -eux
python -m compileall -q prs harvester indexer referral reports manage.py
DEBUG=True python manage.py collectstatic --noinput
EOF

# Image runs as the nonroot user
USER nonroot
EXPOSE 8080
CMD ["gunicorn", "prs.wsgi", "--config", "gunicorn.py"]
