#!/bin/bash
exec uwsgi --ini uwsgi.ini --module prs2.wsgi
