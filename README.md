# KWP

Packet 3 provides local environment configuration and a development connectivity check. Authentication and financial features are not implemented here.

## Local setup

From the repository root, install the recorded backend dependencies:

```sh
kwp_env/bin/python -m pip install -r backend/requirements.txt
```

Create `backend/.env` from `backend/.env.example` if it does not exist. Generate a local secret and put its value in `DJANGO_SECRET_KEY` in that ignored file:

```sh
kwp_env/bin/python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

The example secret is a placeholder and is intentionally rejected. Do not commit generated secrets. This packet creates an ignored local `.env` for developer convenience if none exists. For a fresh checkout, create it yourself with the steps above.

Backend variables:

| Variable | Local value / behavior |
| --- | --- |
| `DJANGO_SECRET_KEY` | Required generated secret; no runtime fallback |
| `DJANGO_DEBUG` | `True` locally; defaults to `False` when absent |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1`; defaults to an empty list |
| `FRONTEND_URL` | `http://localhost:5173`; origin only, no path |

`django-environ` reads `backend/.env`; process environment values take precedence. Keep one settings file. SQLite remains the local database. Existing migrations can be applied with `python manage.py migrate` after activation; this packet adds no migrations.

Create `frontend/.env` from `frontend/.env.example` if it does not exist. It sets `VITE_API_BASE_URL=http://127.0.0.1:8000/api`. The base URL includes `/api` but not `/health/`; a trailing slash is accepted. Vite embeds `VITE_*` values in browser code: never put secrets there. Restart Vite after environment changes.

Terminal 1, from the repository root:

```sh
cd backend
source ../kwp_env/bin/activate
python manage.py runserver
```

Terminal 2, from the repository root:

```sh
cd frontend
npm ci
npm run dev -- --port 5173 --strictPort
```

Open `http://localhost:5173` (or `http://127.0.0.1:5173`). Expect `API status: Checking...` followed by `API status: Connected`. Stop Django and reload the page to verify `API status: Unavailable` without a crash. There is no automatic retry; reload after restarting Django.

Direct backend check:

```sh
curl http://127.0.0.1:8000/api/health/
```

Expected HTTP 200 body: `{"status":"ok"}`. This public endpoint checks liveness/connectivity only; it performs no database access, exposes no configuration and does not establish database readiness.

When `DJANGO_DEBUG=True`, both frontend loopback origins on port 5173 are explicitly permitted alongside `FRONTEND_URL`. Other ports/origins are rejected unless explicitly configured. With debug off, only the configured `FRONTEND_URL` is permitted; there are no automatic development origins. CORS applies to `/api/` only and is not globally open. CORS is not authentication or CSRF protection; the future authentication packet must establish those separately.

## Validation

From `backend/` with local environment configuration:

```sh
../kwp_env/bin/python manage.py test
../kwp_env/bin/python manage.py check
../kwp_env/bin/python manage.py makemigrations --check --dry-run
```

From `frontend/`:

```sh
npm test
npm run lint
npm run build
```

See [ADR 0006](docs/decisions/0006-environment-and-connectivity.md) for the configuration boundary. Production domains, HTTPS/cookie hardening and final auth transport remain later work. The old source-embedded development key is removed; it must not be reused, and any deployment that used it needs rotation before release. Git history is not rewritten by this packet.
