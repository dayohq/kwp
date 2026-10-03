# 0001: MVP stack and project boundary

Status: Accepted planning baseline

Recorded: 2 October 2026

Sources: [Product roadmap](../product-roadmap.md) and [Development roadmap](../development-roadmap.md), based on the supplied DOCX references. Status records the roadmap position, not implementation completion.

## Context

The 60-day build needs mature tools and a reliable relational database without carrying forward the old Create React App implementation.

## Decision

Use a clean React 19 + Vite JavaScript frontend, Django 5.2 LTS on a supported security patch with Django REST Framework, and PostgreSQL. Start with a custom email-identity User model. Use Recharts, Vitest/React Testing Library, Playwright, and Django/DRF tests. Pin dependencies and retain lock files. Minas remains a reference rather than a migration source.

## Consequences and follow-up

Keep financial rules in Django and use frontend feature folders with a small fetch wrapper and React Router. Avoid Redux unless complexity warrants it. The baseline is from the supplied roadmap, not a statement that versions or implementation have been verified.
