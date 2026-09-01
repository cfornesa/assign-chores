# assign-chores

This repository now contains a basic Django project and `chores` app.

## Run locally

```bash
python manage.py migrate
python manage.py runserver 0.0.0.0:5000
```

The Django configuration is in `assign_chores/settings.py`.

## Authentication

The app uses Django's built-in authentication views. Sign in at
`/accounts/login/`; the existing home/board route requires authentication, and
signed-in users can sign out from the home page.

To create a local user for development, run:

```bash
python manage.py createsuperuser
```

