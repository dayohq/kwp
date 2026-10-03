# 0005: Managed hosting and private attachments

Status: Proposed providers; accepted storage constraints

Recorded: 2 October 2026

Sources: [Product roadmap](../product-roadmap.md) and [Development roadmap](../development-roadmap.md), based on the supplied DOCX references. Status records the roadmap position, not implementation completion.

## Context

Deployment must support trustworthy financial data and backups; receipt uploads are optional P1 scope.

## Decision

Plan a static frontend, managed Django service using Gunicorn/WSGI, managed PostgreSQL, and private S3-compatible object storage when attachments are enabled. Provider selection and custom-domain timing remain open. Keep provider configuration in environment variables and use standard database/storage interfaces.

## Consequences and follow-up

Enable monitoring, a health endpoint and database backups; document and test a restore before release. Attachments support multiple files in the model, allow PDF/JPEG/PNG only, validate extension and actual type, randomize storage keys and require authorized time-limited access or streaming. Exact limits remain to be chosen; 5 MB per file is an example, not a finalized limit. Defer attachments/PDF if P0 is unstable at Day 47.
