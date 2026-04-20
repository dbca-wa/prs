# Copilot Instructions for PRS

This is a Django 5.2 web application for the [Planning Referral System (PRS)](https://prs.dbca.wa.gov.au/), a corporate referral management system for the WA Department of Biodiversity, Conservation and Attractions (DBCA).

## Quick Start

### Setup

- Use `uv` (Python package manager) for dependency management, not pip
- Install dependencies: `uv sync`
- Activate virtualenv: `source .venv/bin/activate`
- Set up environment variables in `.env` file (see README.md for required variables)

### Running the Application

- Local webserver: `python manage.py runserver 0:8080`
- Interactive shell: `python manage.py shell_plus`
- Background Celery worker: `celery --app prs worker --loglevel INFO --events --without-heartbeat --without-gossip --without-mingle`

### Testing

- Full test suite: `python manage.py test --keepdb -v2 --settings prs.test-settings --failfast`
- Single app tests: `python manage.py test prs.referral.test_models --keepdb -v2 --settings prs.test-settings`
- Coverage report: `coverage run --source='.' manage.py test --keepdb -v2 --settings prs.test-settings && coverage report -m`
- Note: Tests cannot run in parallel due to DB constraint setup

### Code Quality

- Ruff is configured with a 140-character line length (see pyproject.toml)
- Ruff ignores: E265 (block comment format), E501 (line length in some contexts), E722 (bare except)
- Django HTML templates use djlint profile
- Pre-commit hooks include TruffleHog for secret detection

## Architecture

### Project Structure

**Main Django app (`prs/`):**

- `settings.py` - Project configuration (includes media storage, GeoServer, email config)
- `test-settings.py` - Test-specific settings (uses MD5 hashing, disables logging, etc.)
- `celery.py` - Celery beat task scheduling
- `middleware.py` - Custom middleware
- `context_processors.py` - Template context injection
- `urls.py`, `wsgi.py`, `api.py` - Core routing and WSGI

**Referral app (`referral/`):**

- Core business logic for planning referrals
- `models.py` - Main domain models (referrals, assessments, locations, etc.)
- `base.py` - Abstract base classes: `ActiveModel` (soft delete), `Audit` (created_by/modified_by tracking)
- `views.py` / `views_base.py` - Request handlers
- `api_v3.py` - REST API endpoints (version 3)
- `forms.py` - Django forms
- `tasks.py` - Celery background tasks (indexing, email notifications)
- `utils.py` - Helper functions (text processing, geometry, document parsing)
- `admin.py` - Django admin interface

**Harvester app (`harvester/`):**

- Automated data ingestion system for populating referral data

**Indexer app (`indexer/`):**

- Search indexing integration with Typesense for fast full-text search

**Reports app (`reports/`):**

- Report generation and export functionality

### Key Technologies

- **Database**: PostgreSQL with PostGIS (geographic data support)
- **Task Queue**: Celery with Redis broker
- **Search**: Typesense for full-text search and indexing
- **Geospatial**: Shapely, Fiona, pyproj, GeoDjango (django.contrib.gis)
- **Document Processing**: extract-msg (MSG files), pdfminer-six, docx2txt
- **Forms**: Django Crispy Forms with Bootstrap 5
- **API**: Django REST Framework (v3)
- **Media Storage**: Azure blob storage (configurable for local file storage)
- **SSO/Authentication**: Uses DBCA's SSO system for production

## Code Conventions

### Models

- Use `ReferralLookup` abstract base class for lookup tables (auto-slugs, audit fields)
- Use `ActiveModel` and `Audit` mixins for soft deletes and change tracking
- Geospatial fields use `models.PolygonField` (from django.contrib.gis.db.models)
- Text normalization with `unidecode()` on save to handle international characters
- Models may override `as_row()` for custom table rendering

### Database & Migrations

- PostGIS is required (both GeoDjango and full PostGIS extension)
- Migrations are auto-generated but review spatial field changes
- Full-text search uses PostgreSQL SearchVectorField (not manually updated—use signals or tasks)

### Testing

- Test files named `test_*.py` (e.g., `test_models.py`, `test_views.py`)
- Test classes inherit from `TestCase`
- Use `mixer` library for model fixtures in development
- Test database uses temporary storage (tmpfs in CI)
- Always use `--settings prs.test-settings` when running tests
- Do NOT run tests in parallel

### Celery Tasks

- Tasks defined in `referral/tasks.py`
- Decorators: `@shared_task` for async functions
- Common tasks: `index_object`, `index_record` (for Typesense), email notifications
- Worker typically runs with `--loglevel INFO` and `--without-gossip --without-mingle` flags (see README)

### File Uploads & Media Storage

- Default: Azure blob storage (see AZURE\_\* environment variables)
- Override with `LOCAL_MEDIA_STORAGE=True` for local testing
- Uploaded files validated using python-magic

### Environment Variables

- Use `dbca_utils.utils.env()` for reading env vars (wraps python-dotenv)
- Example: `env("DEBUG", False)` returns False by default if DEBUG is not set
- Check README.md for complete list of required/optional environment variables

## Development Notes

### Static Files & Templates

- Static files: `prs/static/`
- Base template: `prs/templates/base_prs.html`
- WhiteNoise handles static file compression and caching
- collectstatic required before deployment

### Geospatial Data

- Uses fudgeo for GeoPackage export (supports shapefile export too)
- SRS defaults to WGS84 (EPSG:4326)
- GeoServer integration for map services (configuration via env vars)

### Email

- REFERRAL_EMAIL_HOST for outgoing referral notifications (separate from default EMAIL_HOST)
- Email templates use template rendering
- Supports HTML and text alternatives

### API

- REST API v3 in `api_v3.py`

### Pre-commit Hooks

- TruffleHog secret scanning enabled
- Install with `pre-commit install`
- TruffleHog can run in Docker if native binary unavailable

### Deployment

- Docker support: `docker image build -t ghcr.io/dbca-wa/prs .`
- Gunicorn WSGI server (production)
- Static file compression via WhiteNoise
- Kustomize configs in `kustomize/` directory

## Security

- See SECURITY.md for vulnerability reporting procedures
- Project follows WA Government Cyber Security Policy
- Pre-commit hooks prevent accidental secret commits
- All code/credentials should be managed through GitHub Secrets in CI/CD
