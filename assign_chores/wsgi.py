"""WSGI config for the assign_chores project."""

import os

from django.core.wsgi import get_wsgi_application


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "assign_chores.settings")

application = get_wsgi_application()