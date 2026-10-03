# 0004: Authentication components and transport

Status: Proposed transport; accepted security constraints

Recorded: 2 October 2026

Sources: [Product roadmap](../product-roadmap.md) and [Development roadmap](../development-roadmap.md), based on the supplied DOCX references. Status records the roadmap position, not implementation completion.

## Context

Password and Google sign-in must work securely across the frontend/backend deployment topology.

## Decision

Use Django password handling and maintained Google OAuth components, preferably the django-allauth family. Prefer HttpOnly/Secure/SameSite cookie-based session or refresh handling. Final transport, cookie configuration and package selection remain pending the deployment topology. Do not use custom cryptography or long-lived bearer tokens in localStorage.

## Consequences and follow-up

Require verified email for password signup, standard password reset, rate limiting, owner-scoped authorization tests, HTTPS and restricted origins. Cookie-authenticated writes require CSRF protection. Record the final transport decision before auth integration is finalized; confirm allowed hosts, CORS/CSRF and OAuth callbacks against the deployed domains.
