from confy import read_environment_file, env
import os
from fabric.api import cd, run, local, get, settings
from fabric.contrib.files import exists, upload_template

read_environment_file()
DEPLOY_REPO_URL = env('DEPLOY_REPO_URL', '')
DEPLOY_TARGET = env('DEPLOY_TARGET', '')
DEPLOY_VENV_PATH = env('DEPLOY_VENV_PATH', '')
DEPLOY_VENV_NAME = env('DEPLOY_VENV_NAME', '')
DEPLOY_DEBUG = env('DEPLOY_DEBUG', '')
DEPLOY_PORT = env('DEPLOY_PORT', '')
DEPLOY_DATABASE_URL = env('DEPLOY_DATABASE_URL', '')
DEPLOY_SECRET_KEY = env('DEPLOY_SECRET_KEY', '')
DEPLOY_CSRF_COOKIE_SECURE = env('DEPLOY_CSRF_COOKIE_SECURE', '')
DEPLOY_SESSION_COOKIE_SECURE = env('DEPLOY_SESSION_COOKIE_SECURE', '')
DEPLOY_USER = env('DEPLOY_USER', '')
DEPLOY_DB_NAME = env('DEPLOY_DB_NAME', 'db')
DEPLOY_DB_USER = env('DEPLOY_DB_USER', 'dbuser')
DEPLOY_SUPERUSER_USERNAME = env('DEPLOY_SUPERUSER_USERNAME', 'superuser')
DEPLOY_SUPERUSER_EMAIL = env('DEPLOY_SUPERUSER_EMAIL', 'test@email.com')
DEPLOY_SUPERUSER_PASSWORD = env('DEPLOY_SUPERUSER_PASSWORD', 'pass')
DEPLOY_SUPERVISOR_NAME = env('DEPLOY_SUPERVISOR_NAME', 'sv')
DEPLOY_EMAIL_HOST = env('DEPLOY_EMAIL_HOST', 'email.host')
DEPLOY_EMAIL_PORT = env('DEPLOY_EMAIL_PORT', '25')
DEPLOY_SITE_URL = env('SITE_URL', 'url')
GEOSERVER_WMS_URL = env('GEOSERVER_WMS_URL', 'url')
GEOSERVER_WFS_URL = env('GEOSERVER_WFS_URL', 'url')


def _get_latest_source():
    """Creates target directory, either clones repo or pulls changes from master branch.
    """
    run('mkdir -p {}'.format(DEPLOY_TARGET))
    if exists(os.path.join(DEPLOY_TARGET, '.git')):
        run('cd {} && git pull'.format(DEPLOY_TARGET))
    else:
        run('git clone {} {}'.format(DEPLOY_REPO_URL, DEPLOY_TARGET))
        run('cd {} && git checkout master'.format(DEPLOY_TARGET))


def _create_dirs():
    """Ensure that required directories exist.
    """
    with cd(DEPLOY_TARGET):
        run('mkdir -p log && mkdir -p media')


def _update_venv(req='requirements.txt'):
    """Creates a virtualenv, installs requirements.
    """
    with cd(DEPLOY_VENV_PATH):
        if not exists('{}/bin/pip'.format(DEPLOY_VENV_NAME)):
            run('virtualenv {}'.format(DEPLOY_VENV_NAME))
        run('{}/bin/pip install -r {}'.format(DEPLOY_VENV_NAME, req))


def _setup_env():
    """Creates a .env file in the deployment directory.
    """
    with cd(DEPLOY_TARGET):
        context = {
            'DEPLOY_DEBUG': DEPLOY_DEBUG,
            'DEPLOY_PORT': DEPLOY_PORT,
            'DEPLOY_DATABASE_URL': DEPLOY_DATABASE_URL,
            'DEPLOY_SECRET_KEY': DEPLOY_SECRET_KEY,
            'DEPLOY_CSRF_COOKIE_SECURE': DEPLOY_CSRF_COOKIE_SECURE,
            'DEPLOY_SESSION_COOKIE_SECURE': DEPLOY_SESSION_COOKIE_SECURE,
            'DEPLOY_EMAIL_HOST': DEPLOY_EMAIL_HOST,
            'DEPLOY_EMAIL_PORT': DEPLOY_EMAIL_PORT,
            'DEPLOY_SITE_URL': DEPLOY_SITE_URL,
            'GEOSERVER_WMS_URL': GEOSERVER_WMS_URL,
            'GEOSERVER_WFS_URL': GEOSERVER_WFS_URL,
        }
        upload_template('prs2/templates/env.jinja', '.env', context, use_jinja=True, backup=False)


def _setup_supervisor_conf():
    """Creates a 'typical' supervisor conf in the deployment directory.
    """
    with cd(DEPLOY_TARGET):
        context = {
            'DEPLOY_SUPERVISOR_NAME': DEPLOY_SUPERVISOR_NAME,
            'DEPLOY_USER': DEPLOY_USER,
            'DEPLOY_TARGET': DEPLOY_TARGET,
            'DEPLOY_VENV_PATH': DEPLOY_VENV_PATH,
            'DEPLOY_VENV_NAME': DEPLOY_VENV_NAME,
        }
        upload_template(
            'prs2/templates/supervisor.jinja', '{}.conf'.format(DEPLOY_SUPERVISOR_NAME),
            context, use_jinja=True, backup=False)


def _chown():
    """Assumes that the DEPLOY_USER user exists on the target server.
    """
    run('chown -R {0}:{0} {1}'.format(DEPLOY_USER, DEPLOY_TARGET))


def _collectstatic():
    """Runs the Django collectstatic management command.
    """
    with cd(DEPLOY_TARGET):
        run_str = 'source {}/{}/bin/activate && python manage.py collectstatic --noinput'
        run(run_str.format(DEPLOY_VENV_PATH, DEPLOY_VENV_NAME), shell='/bin/bash')


def _create_db():
    """Creates a database on the deploy target. Assumes that PGHOST and PGUSER are set.
    """
    db = {
        'NAME': DEPLOY_DB_NAME,
        'USER': DEPLOY_DB_USER,
    }
    sql = '''CREATE DATABASE {NAME} OWNER {USER};
        \c {NAME}'''.format(**db)
    run('echo "{}" | psql -d postgres'.format(sql))


def _migrate():
    """Runs the Django migrate management command.
    """
    with cd(DEPLOY_TARGET):
        run_str = 'source {}/{}/bin/activate && python manage.py migrate'
        run(run_str.format(DEPLOY_VENV_PATH, DEPLOY_VENV_NAME), shell='/bin/bash')


def _create_superuser():
    script = """from django.contrib.auth.models import User;
User.objects.create_superuser('{}', '{}', '{}')""".format(DEPLOY_SUPERUSER_USERNAME, DEPLOY_SUPERUSER_EMAIL, DEPLOY_SUPERUSER_PASSWORD)
    with cd(DEPLOY_TARGET):
        run_str = 'source {}/{}/bin/activate && echo "{}" | python manage.py shell'
        run(run_str.format(DEPLOY_VENV_PATH, DEPLOY_VENV_NAME, script), shell='/bin/bash')


def deploy_env():
    """Normally used to deploy a new environment (idempotent).
    """
    _get_latest_source()
    _create_dirs()
    _update_venv()
    _setup_env()
    _chown()
    _setup_supervisor_conf()  # After the _chown step.
    _collectstatic()


def deploy_db():
    """Normally used to deploy a new database (idempotent).
    """
    _create_db()
    _migrate()
    _create_superuser()


def deploy_all():
    """Deploy to a new environment in one step. Non-destructive, but will
    raise lots of errors for an existing environment.
    """
    deploy_env()
    deploy_db()


def update_repo():
    """Update only: pulls repo changes, runs migrations, runs collectstatic.
    """
    _get_latest_source()
    _migrate()
    _collectstatic()


def export_legacy_json():
    """Dump, compress and download legacy PRS data to JSON fixtures for import to PRS2.
    """
    EXPORT_VENV_PATH = env('EXPORT_VENV_PATH', '')
    EXPORT_VENV_NAME = env('EXPORT_VENV_NAME', 'venv')
    EXPORT_TARGET = env('EXPORT_TARGET', '')

    models = [
        ('auth.Group', 'auth_group.json'),
        ('auth.User', 'auth_user.json'),
        ('taggit', 'taggit.json'),
        ('referral', 'referral.json'),
        ('reversion', 'reversion.json'),
    ]
    dump = 'python manage.py dumpdata --format=json --indent=4 --natural {} > {}'

    for model in models:
        cmd = dump.format(model[0], model[1])
        run_str = 'source {}/{}/bin/activate && cd {} && {}'
        run(run_str.format(EXPORT_VENV_PATH, EXPORT_VENV_NAME, EXPORT_TARGET, cmd), shell='/bin/bash')

    # Compress the JSON into a single file, then download it.
    with cd(EXPORT_TARGET):
        run('tar -cvzf data.tar.gz *.json')
        get('data.tar.gz', '.')

    # Decompress the archive locally.
    local('tar -xvf data.tar.gz')


def load_legacy_json():
    """Load legacy PRS data from JSON fixtures.
    """
    models = [
        # Order of loading is important.
        ('auth.Group', 'auth_group.json'),
        ('auth.User', 'auth_user.json'),
        ('taggit', 'taggit.json'),
        ('referral', 'referral.json'),
        ('reversion', 'reversion.json'),
    ]
    load = 'python manage.py loaddata --ignorenonexistent {}'

    for model in models:
        cmd = load.format(model[1])
        run_str = 'source {}/{}/bin/activate && cd {} && {}'
        run(run_str.format(DEPLOY_VENV_PATH, DEPLOY_VENV_NAME, DEPLOY_TARGET, cmd), shell='/bin/bash')


def test():
    """Locally runs unit tests for the referral application.
    """
    local('python manage.py test referral -v 2 -k', shell='/bin/bash')


def test_coverage():
    """Locally runs code coverage report for the referral application.
    """
    local('coverage run --source="." manage.py test referral -v 0 -k && coverage report -m', shell='/bin/bash')


def test_func():
    """Runs (Selenium) functional unit tests for the prs2 application.
    """
    cmds = """\
python manage.py test prs2.referral.test_functional.PrsSeleniumNormalUserTests.test_login -k
python manage.py test prs2.referral.test_functional.PrsSeleniumNormalUserTests.test_login -k
python manage.py test prs2.referral.test_functional.PrsSeleniumReadOnlyUserTests.test_login -k
    """.split("\n")
    with settings(warn_only=True):
        map(local, cmds)
