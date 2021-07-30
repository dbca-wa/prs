# Prepare the base environment.
FROM python:3.9.6-slim-buster as builder_base_prs
MAINTAINER asi@dbca.wa.gov.au
RUN apt-get update -y \
  && apt-get upgrade -y \
  && apt-get install --no-install-recommends -y wget git libmagic-dev gcc binutils libproj-dev gdal-bin python3-dev proj-bin \
  && rm -rf /var/lib/apt/lists/* \
  && pip install --upgrade pip

# Install Python libs using poetry.
FROM builder_base_prs as python_libs_prs
WORKDIR /app
ENV POETRY_VERSION=1.1.6
RUN pip install "poetry==$POETRY_VERSION"
RUN python -m venv /venv
COPY poetry.lock pyproject.toml /app/
RUN poetry config virtualenvs.create false \
  && poetry install --no-dev --no-interaction --no-ansi

# Install the project.
FROM python_libs_prs
COPY gunicorn.py manage.py ./
COPY prs2 ./prs2
COPY pygeopkg ./pygeopkg
RUN python manage.py collectstatic --noinput
# Run the application as the www-data user.
USER www-data
EXPOSE 8080
HEALTHCHECK --interval=1m --timeout=5s --start-period=10s --retries=3 CMD ["wget", "-q", "-O", "-", "http://localhost:8080/healthcheck/"]
CMD ["gunicorn", "prs2.wsgi", "--config", "gunicorn.py"]

LABEL org.opencontainers.image.source https://github.com/dbca-wa/prs
