# syntax=docker/dockerfile:1
FROM dhi.io/python:3.13-debian13-dev AS build-stage
LABEL org.opencontainers.image.authors=asi@dbca.wa.gov.au
LABEL org.opencontainers.image.source=https://github.com/dbca-wa/prs

# Install system packages required to run the project
RUN apt-get update -y \
  # Python package dependencies: fiona requires libgdal-dev and gcc, python-magic requires libmagic1t64
  && apt-get install -y --no-install-recommends libgdal-dev gcc g++ gdal-bin proj-bin libmagic1t64 \
  # Run shared library linker after installing packages
  && ldconfig \
  && rm -rf /var/lib/apt/lists/*

# Import uv to install dependencies
COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /bin/
WORKDIR /app
# Install project dependencies
COPY pyproject.toml uv.lock ./
RUN uv sync --no-group dev --link-mode=copy --compile-bytecode --no-python-downloads --frozen \
  # Remove uv and lockfile after use
  && rm -rf /bin/uv \
  && rm uv.lock

# Copy the remaining project files to finish building the project
COPY gunicorn.py manage.py pyproject.toml ./
COPY harvester ./harvester
COPY indexer ./indexer
COPY prs ./prs
COPY referral ./referral
COPY reports ./reports
ENV PYTHONUNBUFFERED=1
ENV PATH="/app/.venv/bin:$PATH"
# Compile scripts and collect static files
RUN python -m compileall -q prs harvester indexer referral reports \
  && python manage.py collectstatic --noinput

# Run the project as the nonroot user
USER nonroot
EXPOSE 8080
CMD ["gunicorn", "prs.wsgi", "--config", "gunicorn.py"]
