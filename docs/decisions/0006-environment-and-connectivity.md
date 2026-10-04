# 0006: Environment configuration and API connectivity

Status: Accepted for Packet 3

Recorded: 3 October 2026

## Context

Local Vite and Django run on different origins. Configuration must support this development setup while keeping secrets out of source and leaving authentication transport and production providers unresolved.

## Decision

Use `django-environ` in the existing settings file. Read the ignored `backend/.env` without overriding process environment. Require `DJANGO_SECRET_KEY`, reject empty/example secrets, default debug off and allowed hosts to an empty list. Use `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS` and `FRONTEND_URL` for environment-specific configuration.

Install/configure DRF and django-cors-headers. Place CorsMiddleware before response-producing middleware, following [package guidance](https://github.com/adamchainz/django-cors-headers#setup). Restrict CORS to `/api/`, allow the configured frontend origin, and add only `http://localhost:5173` and `http://127.0.0.1:5173` when debug is enabled. No wildcard/global CORS or production domains are introduced.

Local frontend URL is `http://localhost:5173`; backend URL is `http://127.0.0.1:8000`. The public Vite variable `VITE_API_BASE_URL` includes `/api`, conventionally `http://127.0.0.1:8000/api`. Native fetch calls its `/health/` path. The temporary UI displays Checking, Connected or Unavailable and aborts its request on unmount.

`GET /api/health/` returns HTTP 200 and `{"status":"ok"}` without authentication or database access. It is a liveness/connectivity check, not a database readiness check. Authentication is disabled only for this public endpoint; no global DRF auth policy is chosen.

## Consequences and follow-up

Local env files remain ignored; example files contain placeholders only. Runtime dependencies are pinned in `backend/requirements.txt`; no transitive freeze or frontend dependency is added. Production must supply its own secret, origins/hosts and security settings. ADR 0004 still governs the pending auth transport decision; no credentialed cross-origin requests or CSRF origin policy are implemented here. SQLite remains unchanged.

See [local setup and validation](../../README.md) for exact commands and environment-file preparation. The endpoint and minimal UI can evolve later without adding business features to this packet.
