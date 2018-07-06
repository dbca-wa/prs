FROM python:3.6.6-slim-stretch
MAINTAINER asi@dbca.wa.gov.au

WORKDIR /usr/src/app
COPY gunicorn.ini manage.py requirements.txt ./
COPY prs2 ./prs2
RUN apt-get update -y \
  && apt-get install -y wget git libmagic-dev gcc binutils libproj-dev gdal-bin \
  && pip install --no-cache-dir -r requirements.txt \
  && python manage.py collectstatic --noinput

EXPOSE 8080
CMD ["gunicorn", "prs2.wsgi", "--config", "gunicorn.ini"]
