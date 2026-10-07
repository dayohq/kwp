# 0004: Authentication components and transport

Status: Accepted session transport; staged authentication implementation

Recorded: 2 October 2026; approved correction: 7 October 2026

## Context

KWP's first-party React frontend and Django API need email/password authentication across explicitly configured origins.

## Decision

Use Django server-side sessions for first-party browser authentication, with DRF SessionAuthentication. Django manages the HttpOnly session cookie. Do not use JWT, DRF TokenAuthentication, or browser storage of authentication tokens/session identifiers in localStorage or sessionStorage. Use Django authentication, password hashing and configured password validators.

CSRF protection remains enabled, including anonymous registration and login and authenticated logout. The frontend obtains a masked CSRF token from GET /api/auth/csrf/ and submits it as X-CSRFToken on state-changing requests with credentials included. The token stays only in request memory; Django rotates CSRF state on login and session identifiers when establishing authentication.

Credentialed CORS and CSRF trusted origins are restricted to explicitly configured frontend origins; no wildcard origins. Local development uses http://localhost:5173 and http://localhost:8000 with API base http://localhost:8000/api. Both services must use the same hostname; do not mix localhost and 127.0.0.1 for auth. Loopback aliases may remain supported independently.

Sessions and CSRF cookies are host-only with SameSite=Lax. Session cookies are HttpOnly; the bootstrap token avoids needing JavaScript cookie access. HTTPS with Secure cookies is the intended production posture. Deployment hardening may tighten cookie/domain, HTTPS, host/origin and proxy settings without changing the session architecture. A production topology must support these same-site cookies; cross-site deployments require a reviewed cookie/CSRF configuration.

## Staged signup policy

Verified email is required for the finished password-signup experience. Packet 5 deliberately implements only registration, login, session/profile, logout, password validation, CSRF and minimal frontend proof. During this incomplete development stage, password users may authenticate without email verification. This is not the final production signup policy.

A later dedicated authentication packet will implement and enforce verification emails/tokens, resend behavior, verified-email enforcement, password reset and production email configuration. Google OAuth remains later work using maintained components, preferably the django-allauth family. None of these features is implemented in Packet 5.

## Consequences and follow-up

Registration requires explicit base_currency because the current User model has no default; timezone retains Africa/Lagos. Registration creates the user without signing them in; login establishes the session. API profiles contain only id, email, base_currency and timezone. Session-protected anonymous requests return DRF's HTTP 403; invalid credentials return the same HTTP 400 message for wrong passwords, unknown emails and inactive users.

Production rate limiting/abuse controls, HTTPS/security review and email verification enforcement remain required before release. Packet 5 adds no Redis or throttling that could imply production protection. Owner isolation and transport regression tests are required. See the README for API and local verification steps.
