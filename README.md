# Planning Referral System

[![Build
Status](https://travis-ci.org/dbca-wa/prs.svg?branch=master)](https://travis-ci.org/dbca-wa/prs)

This project is the Department of Biodiversity, Conservation and Attractions
[Planning Referral System](https://prs.dbca.wa.gov.au/) corporate application.

# Installation

Create a new virtualenv and install required libraries using `pip`:

    pip install -r requirements.txt

# Environment variables

This project uses **django-confy** to set environment variables (in a `.env` file).
The following variables are required for the project to run:

    DATABASE_URL="postgis://USER:PASSWORD@HOST:5432/DATABASE_NAME"

Variables below may also need to be defined (context-dependent):

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
    GEOSERVER_WMS_URL="//kmi.dpaw.wa.gov.au/geoserver/gwc/service/wms"
    GEOSERVER_WFS_URL="//kmi.dpaw.wa.gov.au/geoserver/ows"
    PRS_USER_GROUP="PRS user"
    PRS_PWUSER_GROUP="PRS power user"
    BORGCOLLECTOR_API="https://borg.dpaw.wa.gov.au/api/"
    SLIP_USERNAME="slip_username"
    SLIP_PASSWORD="slip_password"
    SLIP_WFS_URL="https://wfs.slip.url.au/endpoint"
    SLIP_DATASET="slip:LGATE-001"

# Running

Use `runserver` to run a local copy of the application:

    python manage.py runserver 0.0.0.0:8080

Run console commands manually:

    python manage.py shell_plus

# Testing

Run unit tests for the **referral** app as follows:

    python manage.py test prs2.referral -k -v2

To run tests for e.g. models only:

    python manage.py test prs2.referral.test_models -k -v2

To obtain coverage reports:

    coverage run --source='.' manage.py test -k -v2
    coverage report -m

# Docker image

To build a new Docker image from the `Dockerfile`:

    docker image build -t dbcawa/prs .
