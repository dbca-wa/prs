FROM python:3.6.6-slim-stretch
MAINTAINER asi@dbca.wa.gov.au

# Prepare the base environment.
RUN apt-get update -y \
  && apt-get install --no-install-recommends -y wget git libmagic-dev gcc binutils libproj-dev gdal-bin python3-dev \
  && rm -rf /var/lib/apt/lists/*

# Install the project.
WORKDIR /usr/src/app
COPY gunicorn.ini manage.py requirements.txt ./
COPY prs2 ./prs2
RUN pip install --no-cache-dir -r requirements.txt \
  && python manage.py collectstatic --noinput

HEALTHCHECK --interval=1m --timeout=5s --start-period=10s --retries=3 CMD ["wget", "-q", "-O", "-", "http://localhost:8080/healthcheck/"]
EXPOSE 8080
CMD ["gunicorn", "prs2.wsgi", "--config", "gunicorn.ini"]
