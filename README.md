# Planning Referral System

This project is the Department of Biodiversity, Conservation and Attractions
[Planning Referral System](https://prs.dbca.wa.gov.au/) corporate application.

# Installation

The recommended way to set up this project for development is using
[Poetry](https://python-poetry.org/docs/) to install and manage a virtual Python
environment. With Poetry installed, change into the project directory and run:

    poetry install

Activate the virtualenv like so:

    poetry shell

To run Python commands in the activated virtualenv, thereafter run them like so:

    python manage.py

Manage new or updating project dependencies with Poetry also, like so:

    poetry add newpackage==1.0

# Environment variables

This project uses **django-confy** to set environment variables (in a `.env` file).
The following variables are required for the project to run:

    DATABASE_URL="postgis://USER:PASSWORD@HOST:5432/DATABASE_NAME"

Variables below may also need to be defined in production (context-dependent):

    SECRET_KEY="ThisIsASecretKey"
    DEBUG=True
    ALLOWED_DOMAINS=".dbca.wa.gov.au,localhost"
    CSRF_COOKIE_SECURE=False
    SESSION_COOKIE_SECURE=False
    EMAIL_HOST="email.host"
    EMAIL_PORT=25
    REFERRAL_EMAIL_HOST="outlook.office365.com"
    REFERRAL_EMAIL_USER="referrals@email.address"
    REFERRAL_EMAIL_PASSWORD="password"
    REFERRAL_ASSIGNEE_FALLBACK="admin"
    PLANNING_EMAILS="referrals@planning.wa.gov.au,referrals@dplh.wa.gov.au"
    ASSESSOR_EMAILS="assessor1@dbca.wa.gov.au,assessor2@dbca.wa.gov.au"
    SITE_URL="prs.dbca.wa.gov.au"
    GEOSERVER_URL="https://geoserver.url/service"
    PRS_USER_GROUP="PRS user"
    PRS_PWUSER_GROUP="PRS power user"
    SLIP_USERNAME="slip_username"
    SLIP_PASSWORD="slip_password"
    SLIP_ESRI_FS_URL="https://wfs.slip.url.au/endpoint"

# Media uploads

By default, PRS assumes that user-uploaded media will be saved to Azure blob
storage. To use local storage, set the environment variable `LOCAL_MEDIA_STORAGE=True`
and ensure that a writeable `media` directory exists in the project directory.

Credentials for Azure should be defined in the following environment variables:

    AZURE_ACCOUNT_NAME=name
    AZURE_ACCOUNT_KEY=key
    AZURE_CONTAINER=container_name

# Running

Use `runserver` to run a local copy of the application:

    python manage.py runserver 0:8080

Run console commands manually:

    python manage.py shell_plus

Run a single Celery worker alongside the local webserver to test indexing:

    celery --app prs2 worker --loglevel INFO --events --without-heartbeat --without-gossip --without-mingle

Note: a message broker service is required for Celery tasks to run; Redis
is typically used for this purpose. The `CELERY_BROKER_URL` env variable
should contain the broker URL value. Reference:

<https://docs.celeryq.dev/en/stable/getting-started/backends-and-brokers/redis.html#broker-redis>

# Testing

Run unit tests as follows:

    python manage.py test --keepdb -v2 --settings prs2.test-settings

To run tests for e.g. models only:

    python manage.py test prs2.referral.test_models --keepdb -v2 --settings prs2.test-settings

To obtain coverage reports:

    coverage run --source='.' manage.py test --keepdb -v2 --settings prs2.test-settings
    coverage report -m

# Docker image

To build a new Docker image from the `Dockerfile`:

    docker image build -t ghcr.io/dbca-wa/prs .

# Pre-commit hooks

This project includes the following pre-commit hooks:

- TruffleHog: <https://docs.trufflesecurity.com/docs/scanning-git/precommit-hooks/>

Pre-commit hooks may have additional system dependencies to run. Optionally
install pre-commit hooks locally like so:

    pre-commit install

Reference: <https://pre-commit.com/>
