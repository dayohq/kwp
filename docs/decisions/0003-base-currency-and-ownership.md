# 0003: Single base currency and owner-scoped records

Status: Accepted planning baseline

Recorded: 2 October 2026

Sources: [Product roadmap](../product-roadmap.md) and [Development roadmap](../development-roadmap.md), based on the supplied DOCX references. Status records the roadmap position, not implementation completion.

## Context

Multi-currency and shared access would add accounting and authorization complexity beyond the MVP.

## Decision

Use one owner per profile and one base currency across all MVP accounts. Choose currency and local time zone during onboarding. Base currency requires explicit selection with no backend default; NGN may be recommended in a later UI but is never silently assigned. Users may change their base currency at any time, including after financial activity. Only the designation changes: no FX conversion occurs, and existing transaction amounts, journal amounts and account balances remain numerically unchanged. MVP does not provide multi-currency accounting. Scope all user-visible and ledger objects to the authenticated owner and reject cross-user references server-side.

## Consequences and follow-up

Use local time for user-facing dates and consistent backend timestamps. Permit back-dated records but no future/scheduled posting. Activate or rename starter account templates instead of creating all accounts automatically. Collect optional last four digits only. Archive accounts and categories with history; category identifiers remain stable across renames. Shared accounts and multi-currency accounting remain post-MVP.

## Custom User iteration — 2 October 2026

Store `base_currency` and `timezone` directly on `users.User`, as requested for this iteration, rather than creating the roadmap's separate profile model. Base currency has no default and is required by model validation, user creation and admin forms. `REQUIRED_FIELDS` includes `base_currency` so `createsuperuser` prompts for it. Time zone retains the `Africa/Lagos` default. Both preferences remain editable. Currency validation checks three uppercase letters only, not membership in a supported currency list. Time zones are validated using Python's IANA zone database. Email is the login identity, normalized to lowercase, with field uniqueness and a case-insensitive database uniqueness constraint.

The custom User iteration initially retained SQLite. Packet 4 now requires PostgreSQL for development (see ADR 0001), without changing these currency or ownership rules. Display preferences and onboarding state remain planned; they are not implemented here.

## Corrective iteration after Packet 2

The explicit selection and designation-only change rules above supersede the supplied DOCX currency policy. Removing the model default does not rewrite existing users’ stored currencies; selection provenance for existing records is unknown. No financial models or currency settings UI exist yet, so numeric preservation across financial activity must be verified when those features are implemented.

### Currency-change confirmation (later settings frontend)

Changing an existing currency must require explicit confirmation before the change is submitted or persisted. Cancel leaves the designation unchanged. Dynamically substitute the current and selected currency codes and their relevant symbols in this target copy:

> Change currency?
>
> Changing your currency from NGN to USD will not convert your existing balances
> or transactions.
>
> ₦250,000 will become $250,000, not its USD equivalent.
>
> [Cancel] [Change currency]

The amount is explanatory copy only; it is not an exchange-rate calculation. This confirmation is a requirement for the later currency settings frontend, not UI implemented in this corrective iteration.
