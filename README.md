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

## Weekly scheduling policy

The application uses the timezone configured by `TIME_ZONE` in
`assign_chores/settings.py` (`America/Chicago` by default). A household week
runs Sunday through Saturday. Weekly instances are generated idempotently when
an approved member opens the household board, only for the current week. The
selected weekday is due at the end of that local day; past and future weeks are
not generated automatically.

