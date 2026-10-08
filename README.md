# KWP

Packets 3–6 provide environment configuration, PostgreSQL development storage, health connectivity, staged email/password sessions and the finance-domain schema. Finance posting, APIs and UI are not implemented. Email verification is deliberately deferred; this is not the final production signup flow.

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
| `DATABASE_URL` | Required PostgreSQL URL; use local credentials in ignored `backend/.env` only |

`django-environ` reads `backend/.env`; process environment values take precedence. Keep one settings file. PostgreSQL is the standard local database, with no SQLite fallback. Missing/invalid database configuration fails clearly. See the database setup below before starting Django. Packet 4 reused existing migrations without rewriting schema history; Packet 6 adds the initial finance schema migration.

### PostgreSQL development setup

Install and run PostgreSQL 17 (Django 5.2 supports PostgreSQL 14+). Use your existing installation, or on macOS use `brew install postgresql@17` and `brew services start postgresql@17`. Ensure its `bin` directory is on your PATH. The app does not depend on Homebrew. [Django compatibility reference](https://docs.djangoproject.com/en/5.2/ref/databases/#postgresql-notes).

Connect as your local PostgreSQL administrator, not the app role. Replace `postgres` below if your installation uses another administrator name:

```sh
psql -h 127.0.0.1 -U postgres -d postgres
```

In psql, create a non-superuser development role and database owned by it:

```sql
CREATE ROLE kwp_user LOGIN NOSUPERUSER NOCREATEROLE CREATEDB;
\password kwp_user
CREATE DATABASE kwp_db OWNER kwp_user;
```

`\password` prompts for a password without putting it in SQL history. Database ownership permits migrations to create/alter tables, including in the `public` schema on PostgreSQL 17; no extra blanket grants or superuser status are needed. Local `CREATEDB` permits Django to create and destroy its temporary `test_kwp_db` database. This development permission is not a production role design. [PostgreSQL ownership documentation](https://www.postgresql.org/docs/17/sql-createdatabase.html).

Add a `DATABASE_URL` entry to `backend/.env` using your database name, user, password, host and port. The placeholder-only format is in `backend/.env.example`. URL-encode special characters in the password; never paste the complete URL into logs, committed files or bug reports. Preserve your existing secret and other environment values.

Apply the existing schema and verify an actual connection from `backend/`:

```sh
source ../kwp_env/bin/activate
python manage.py migrate
python manage.py shell -c "from django.db import connection; connection.ensure_connection(); print(connection.vendor)"
```

Expected vendor: `postgresql`. If you need a development admin, run `python manage.py createsuperuser` and explicitly select base currency. There is no default admin account.

`backend/db.sqlite3` remains ignored and can stay on disk; it is no longer the active development database. Existing disposable SQLite users/admin data are not copied. Django's existing migration files are the canonical schema history. No migration deletion or custom data-transfer script is required.

Create `frontend/.env` from `frontend/.env.example` if it does not exist. It sets `VITE_API_BASE_URL=http://localhost:8000/api`. The base URL includes `/api` but not `/health/`; a trailing slash is accepted. Vite embeds `VITE_*` values in browser code: never put secrets there. Restart Vite after environment changes.

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

Open `http://localhost:5173`. Expect `API status: Checking...` followed by `API status: Connected`. Stop Django and reload the page to verify `API status: Unavailable` without a crash. There is no automatic retry; reload after restarting Django.

Direct backend check:

```sh
curl http://localhost:8000/api/health/
```

Expected HTTP 200 body: `{"status":"ok"}`. This public endpoint checks liveness/connectivity only; it performs no database access, exposes no configuration and does not establish database readiness.

When `DJANGO_DEBUG=True`, both frontend loopback origins on port 5173 are explicitly permitted alongside `FRONTEND_URL`. Other ports/origins are rejected unless explicitly configured. With debug off, only the configured `FRONTEND_URL` is permitted; there are no automatic development origins. CORS applies to `/api/` only and is not globally open. Packet 5 permits credentialed CORS only for these explicit origins and trusts the same origins for CSRF. CSRF remains enforced separately.

## Validation

From `backend/` with PostgreSQL running and local environment configuration (tests use PostgreSQL, create `test_kwp_db`, then destroy it):

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

With the localhost Django and Vite servers running, `npm run test:e2e` runs the real auth UI in isolated headless Chrome. Set `CHROME_BIN` if Chrome is not at its standard macOS path or `google-chrome` on Linux. It verifies registration, login, reload, safe profiles, HttpOnly sessions, empty browser storage, logout, generic failures, duplicate email, CSRF rejection, unavailable-backend UI and recovery. It creates one disposable test account and reports its email so it can be removed using Django admin; no auth secrets are reported.

See [ADR 0006](docs/decisions/0006-environment-and-connectivity.md) for the configuration boundary. Production domains and HTTPS/cookie hardening remain later work; ADR 0004 selects Django sessions. The old source-embedded development key is removed; it must not be reused, and any deployment that used it needs rotation before release. Git history is not rewritten by this packet.

## Packet 5 authentication

[Django server-side session architecture](docs/decisions/0004-authentication-transport.md) is selected. No JWT or DRF tokens are used. The browser manages the HttpOnly, host-only, SameSite=Lax session cookie. No session identifiers, auth tokens or passwords are persisted in localStorage/sessionStorage. Cookies use Secure when DEBUG=False; local DEBUG=True permits HTTP. A production same-site HTTPS topology and security review remain required.

Use **localhost for both services**: frontend http://localhost:5173, backend http://localhost:8000, VITE_API_BASE_URL=http://localhost:8000/api. Existing frontend/.env files using 127.0.0.1 must update their public API URL and restart Vite. Do not mix these hostnames for auth. The PostgreSQL host in DATABASE_URL is independent and does not need changing.

| Method/path | Input / response |
| --- | --- |
| GET /api/auth/csrf/ | Returns a masked csrfToken and sets an HttpOnly CSRF cookie; no session identifier is returned |
| POST /api/auth/register/ | email, password, password_confirmation, explicit base_currency; optional timezone. HTTP 201 safe profile; does not sign in |
| POST /api/auth/login/ | email and password. HTTP 200 safe profile and Django session cookie |
| GET /api/auth/me/ | HTTP 200 current user's id, email, base_currency, timezone; anonymous requests get HTTP 403 |
| POST /api/auth/logout/ | Empty JSON object. HTTP 200 detail; deletes the server session and expires the browser session cookie; requires authentication |

All frontend auth fetches use credentials: 'include'. Before each POST, fetch /api/auth/csrf/ and send its csrfToken as X-CSRFToken with JSON Content-Type. This includes anonymous registration/login. Bootstrap again after login because Django rotates CSRF state. The helper keeps each token only in request memory. Bad/missing CSRF or untrusted origins return HTTP 403, possibly Django's HTML CSRF error page. API validation returns HTTP 400 JSON field errors. Incorrect passwords, nonexistent accounts and inactive users get the same invalid-credentials message. Session-protected anonymous HTTP 403 is distinct from network failure/HTTP 5xx in the frontend. Auth responses are marked no-store.

Registration normalizes email using the existing User manager and enforces case-insensitive uniqueness, including competing registrations. It runs Django's configured password validators and hashes through create_user. Currency requires three uppercase letters with no default (this model checks format, not ISO membership); timezone defaults to Africa/Lagos. No schema changes, finance setup or full onboarding are introduced. Registration requires password confirmation. The UI clears submitted passwords after every outcome.

### Manual end-to-end verification

1. Start PostgreSQL. From backend/, run ../kwp_env/bin/python manage.py migrate then ../kwp_env/bin/python manage.py runserver localhost:8000.
2. From frontend/, confirm the public localhost API URL in the ignored .env and run npm run dev -- --host localhost --port 5173 --strictPort. Open http://localhost:5173.
3. Confirm API status: Connected and Signed out. Choose Create an account. Register a unique test-only email, an explicit currency such as USD, and a strong test-only password/confirmation. Expect Registration successful and the login form.
4. Confirm storage without printing a password/hash: from backend/, run ../kwp_env/bin/python manage.py shell, then enter:

   ```python
   from django.contrib.auth import get_user_model
   from django.contrib.auth.hashers import identify_hasher
   user = get_user_model().objects.get(email="your-test-email@example.com")
   print(user.email, user.base_currency, user.timezone)
   print(identify_hasher(user.password).algorithm)
   ```

   A recognized Django hashing algorithm proves the stored value is encoded. Existing admin users can also inspect the user at http://localhost:8000/admin/; create a local admin with manage.py createsuperuser and explicitly choose base currency if needed.
5. Login with the registered email/password. Expect Signed in as the normalized email. Reload: the authenticated session remains. Browser DevTools Network should show GET /api/auth/me/ returning HTTP 200 and only id/email/base_currency/timezone. Do not copy cookies or tokens into reports.
6. Click Logout. Expect Signed out. Reload: /me/ returns HTTP 403. The previous server session is invalidated.
7. Try an incorrect password and then an unknown email: both give Invalid email or password. Try registration with the registered email in different casing: controlled duplicate-email validation.
8. Omit base currency or use a weak password: registration fails. POST login/logout without a valid CSRF token is rejected. Auth POSTs never use GET.
9. Confirm http://localhost:8000/api/health/ still returns {"status":"ok"}. Stop Django and reload the frontend: API unavailable is shown rather than Signed out. Restart Django and reload to recover.

### Deferred authentication work

Verified email remains a final signup requirement, but this development-stage packet permits unverified password users to authenticate. A dedicated later auth packet must implement verification emails/tokens, resend, enforcement, password reset and production email configuration. Google OAuth, rate limiting/abuse prevention and final production security/deployment hardening remain deferred. No production-readiness or brute-force protection is claimed; no Redis or misleading in-memory throttle is introduced. Packet 6 is not part of this change.

## Packet 6 finance schema

The finance app contains FinancialAccount, Category, LedgerAccount, Transaction, JournalEntry and JournalLine. See [ADR 0007](docs/decisions/0007-finance-domain-schema.md) for fields, links, Decimal precision, ownership enforcement, deletion/archiving and draft-only lifecycle decisions.

After pulling this schema change, apply the new migration from backend/:

```sh
../kwp_env/bin/python manage.py migrate
../kwp_env/bin/python manage.py test
../kwp_env/bin/python manage.py check
../kwp_env/bin/python manage.py makemigrations --check --dry-run
```

Django admin can inspect all six models; transactions, journals and lines are read-only there. Accounts/categories may be archived with is_active=False while retaining their historical references. All finance foreign keys protect referenced records from casual deletion. Normal model saves validate cross-user links; raw SQL and bulk/queryset writes bypass application rules and are not supported creation/update paths without equivalent validation.

Money uses Decimal(24,6); no balances or bank numbers are stored. Journal lines have one positive debit or credit, with the other side NULL. PostgreSQL enforces local money/shape constraints, while ownership/type/hierarchy checks across rows are application validated. Every eventual posted journal must balance total debits == total credits. Packet 6 has only drafts and does not implement the posting or balancing engine. Packet 7 starter templates and Packet 8 posting services remain unimplemented. Authentication and the frontend are unchanged.

## Packet 6B design clarifications

[ADR 0007](docs/decisions/0007-finance-domain-schema.md) clarifies account/ledger separation, two-level category grouping and future conditional transaction fields. [ADR 0008](docs/decisions/0008-opening-balances-and-reconciliation.md) defines visible opening-balance and balance-adjustment Transactions linked to journals, with equity counter-accounts and separate reporting treatment. Their special model kinds are draft-only and are not ordinary Add Transaction choices. Apply the forward Packet 6B migration with the existing migrate command; no data is seeded.

Balances remain ledger-derived. Posting, balancing, reconciliation, reports, finance APIs/UI and starter templates are still unimplemented. The [identifier security backlog](docs/security-backlog.md) records optional future encrypted account identifiers; last_four is unchanged and no full identifier is stored.
