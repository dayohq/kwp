# KWP Development Roadmap

Source: `KWP_Development_Roadmap.docx` (supplied reference). This document records the planning baseline; it does not assert that implementation or release gates are complete.

Technical architecture and execution plan for a 60-day React + Vite / Django MVP

MVP planning baseline • 60-day build window: 1 October–29 November 2026

Build principle: keep the frontend simple, put financial correctness in a tested Django service layer, and protect the last part of the schedule for deployment, security and reconciliation rather than adding features.

## 1. Technical target

KWP will be rebuilt as a clean project rather than migrating the old Create React App codebase. The previous Minas code remains a reference for ideas and working experiments; KWP starts with a deliberate product/data model and a new repository.

| Layer | Recommended MVP choice | Rationale |
| --- | --- | --- |
| Frontend | React 19 + Vite (JavaScript) | Modern React tooling, fast dev server/build, avoids Create React App legacy. |
| Backend | Django 5.2 LTS (latest patch) + Django REST Framework | Stable supported backend with mature auth, ORM, permissions and transaction handling. |
| Database | PostgreSQL | Reliable constraints/transactions and production-ready relational model for ledger data. |
| Authentication | Django auth + maintained Google OAuth package (preferred: django-allauth family) | Do not custom-build password/OAuth security flows. |
| Charts | Recharts | Simple React charting for dashboard trends/category breakdowns. |
| Frontend tests | Vitest + React Testing Library; Playwright for golden-path E2E | Fits Vite and gives component + end-to-end confidence. |
| Backend tests | Django/DRF test framework | Focus on posting invariants, permissions, filters and report reconciliation. |
| Hosting | Static frontend + managed Django service + managed PostgreSQL + private S3-compatible object storage | Separate concerns while keeping deployment understandable. |
| Source control | GitHub, main branch protected by tests once CI is active | Repeatable deployment and reviewable changes. |

Recommended conservative backend baseline as of 30 September 2026: Django 5.2 LTS on the latest security patch rather than chasing the newest feature release. Upgrade later when the dependency stack is proven.

## 2. Repository and project structure

```text
kwp/
  frontend/        React + Vite
  backend/         Django + DRF
    config/        settings / urls / environment config
    users/         custom user, profile, auth integration
    finance/       accounts, categories, transactions, ledger, reports
    mediafiles/    local-only development media (not production)
  docs/            ADRs, API notes, release checklist
  .github/         CI workflow
  .gitignore
  README.md
```

Start with a custom Django User model before the first production migration so email identity/profile changes do not require a painful mid-project swap.

Use environment variables for secrets and environment-specific URLs; commit an .env.example with placeholders only.

Pin backend and frontend dependencies with lock files; upgrade intentionally rather than automatically during the 60-day build.

## 3. Backend domain model

| Model | Responsibility / key fields |
| --- | --- |
| User | Implemented as `users.User`: unique case-insensitive email identity, auth flags, inherited `date_joined`, base currency and time zone. Base currency is explicitly required with no default and is changeable at any time. Additional timestamps remain future work. |
| UserProfile / Preferences | Display preferences and onboarding state remain planned. Base currency and time zone are stored directly on `users.User` for this iteration; see ADR 0003. |
| FinancialAccount | User, name, kind, institution, subtype, last4, opening balance/posting link, active flag, include-in-total, display order. |
| Category | User, type (income/expense), parent, name, system-template origin, active flag. |
| Transaction | User-facing record: type, amount, date/time, source/primary account, destination account for transfers, category, note, status, idempotency key. |
| LedgerAccount | Hidden chart-of-accounts record: asset, income, expense, equity; links user-facing accounts/categories to accounting ledgers. |
| JournalEntry | Posting envelope tied to a Transaction; status; posting timestamp. |
| JournalLine | JournalEntry, ledger account, debit, credit. The sum of debits must equal sum of credits. |
| Attachment | Transaction, private storage key, original display name, size, MIME, created time. |
| AuditEvent | Who/what/when for create, edit, archive/delete, login-sensitive events; avoid secrets and unnecessary sensitive text. |

Currency rule: changing base currency updates only the user’s designation, without FX conversion or numeric changes to transactions, journals or balances, regardless of financial activity. MVP is single-currency accounting. The later settings frontend must obtain explicit confirmation before persisting a change, dynamically showing currency codes and symbols with the warning in [ADR 0003](decisions/0003-base-currency-and-ownership.md#currency-change-confirmation-later-settings-frontend). Tests for unchanged financial amounts must accompany the future finance/settings implementation.

Balance rule: the ledger is the source of truth. FinancialAccount.current_balance may be cached later for performance, but the MVP can derive balances from journal lines until profiling proves a need for caching.

### Packet 6 structural implementation

The six core finance models are now implemented in the finance app. [ADR 0007](decisions/0007-finance-domain-schema.md) records the exact schema and enforcement boundaries. Optional companion/account/category links support independent draft creation, all monetary fields use Decimal(24,6), journals are one-to-one with ordinary transactions, and all finance references use PROTECT. Draft-only states prevent records from claiming a validated posting. Cross-table ownership/hierarchy/type rules are validated on normal saves; local scalar/shape rules have PostgreSQL constraints. No templates, posting/balancing engine, finance API, balances or frontend finance UI is implemented in this packet. The broader model table above remains the eventual target; opening-balance posting links, seed provenance and posted/audit lifecycle behavior are later work.

### Packet 6B clarification

Transaction.Kind also includes the special opening_balance and adjustment kinds for dedicated future workflows. Ordinary Add Transaction choices remain income/expense/transfer. Categories remain income/expense; special events and transfers have no category. [ADR 0008](decisions/0008-opening-balances-and-reconciliation.md) resolves opening/adjustment representation as visible Transactions linked to journals, using distinct equity counter-accounts and separate reporting treatment. No posting, reconciliation, reporting, frontend or provisioning implementation is introduced. Full identifiers remain future encrypted-storage design work in [the security backlog](security-backlog.md).

## 4. Posting service design

Do not scatter debit/credit logic across serializers and React components. Create a backend finance service that receives validated user intent and posts the corresponding ledger entry inside a database transaction.

| Operation | Posting service |
| --- | --- |
| Income | Debit selected asset ledger; credit selected income-category ledger. |
| Expense | Debit selected expense-category ledger; credit selected asset ledger. |
| Transfer | Debit destination asset ledger; credit source asset ledger. |
| Opening balance | Debit asset ledger; credit Opening Balance Equity. |
| Edit | Validate ownership; update user-facing record and re-post affected lines atomically; write audit event. |
| Delete / void | Remove from active reporting in a controlled way and keep an audit event; implementation may soft-delete/void rather than destructive hard delete. |

Reject zero/negative amount input at the API boundary; transaction type determines direction.

Use Decimal fields and explicit currency precision. Do not use float for money.

Enforce same-user ownership for accounts/categories/destination accounts in service and queryset permission layers.

Use transaction.atomic() for posting and edits; an exception rolls back every leg.

Generate or accept a client idempotency key for transaction creation and make it unique per user.

Create explicit tests for the accounting equation after every transaction scenario.

## 5. API surface

| Area | Indicative endpoints / behaviour |
| --- | --- |
| Auth | signup, login, logout, email verification, password reset, Google sign-in/callback/session. |
| Profile | GET/PATCH profile/preferences; base currency; time zone; onboarding state. |
| Accounts | list/create/update/archive; starter templates; opening balance creation. |
| Categories | list/create/update/archive; default seed; parent/child. |
| Transactions | create/list/detail/update/void; filters for dates/type/account/category/search. |
| Dashboard | daily flow; account balances; month-to-date; trends/category summaries. |
| Reports | income-expense statement; date-range summaries; CSV/PDF export. |
| Attachments | authorized upload/list/delete; private download URL or streamed response. |
| Health | simple health/readiness endpoint for deployment monitoring. |

## 6. Frontend architecture and UX

React Router for authenticated/public routes; a small API client wrapper around fetch; no Redux for MVP unless complexity proves it necessary.

Use feature folders: auth, dashboard, transactions, accounts, categories, reports, settings, shared UI.

Transaction wizard keeps draft state in memory; no sensitive persistent draft in localStorage by default.

Wizard steps: Amount → Type → Account(s) → Category (income/expense only) → Note → Record.

Date/time defaults now and is editable from a small control without becoming a mandatory step.

Desktop reuses the step experience in a constrained panel; mobile is the design baseline.

Dashboard uses responsive cards/grid; transaction register is a separate route.

Build explicit Loading / Empty / Error / Success states for every data view.

## 7. Authentication and security architecture

| Control | Implementation requirement |
| --- | --- |
| Password/OAuth | Use maintained Django authentication components and Google OAuth; never store raw passwords or implement custom crypto. |
| Session storage | Django server-side sessions with HttpOnly/SameSite cookies; Secure over production HTTPS. No JWT/DRF tokens or auth state in localStorage/sessionStorage; see ADR 0004. |
| CSRF / CORS | Explicit allowed frontend origins; CSRF protection for cookie-authenticated writes; no wildcard production origins. |
| Authorization | Every queryset/API object is filtered by request.user; tests attempt cross-user object IDs. |
| Secrets | SECRET_KEY, OAuth secrets, DB credentials and storage credentials live in environment/secret manager only. |
| Production settings | DEBUG=False, strict ALLOWED_HOSTS, HTTPS redirect where appropriate, secure cookies, security headers, run manage.py check --deploy. |
| Rate limiting | Protect login, password reset and sensitive endpoints against automated abuse. |
| Uploads | Allowlist PDF/JPEG/PNG; verify size/type; randomized storage key; private bucket; no executable serving. |
| Logging | No passwords/tokens; limit note/financial content in logs; record auth failures and application errors safely. |
| Dependencies | Pin versions, run vulnerability checks periodically, apply supported security patches. |

## 8. Environments, cloud and operations

### Environment model

| Environment | Purpose |
| --- | --- |
| Local | Development and tests use PostgreSQL, configured through required `DATABASE_URL`; no SQLite fallback. See ADR 0001 and README setup instructions. |
| Preview / Staging | Deploy before production when feasible; separate database and OAuth URLs; used for smoke/E2E testing. |
| Production | Managed PostgreSQL, HTTPS, private media storage, monitoring and backup enabled. |

### Recommended simple hosting topology

Frontend: Vite static build on Vercel, Render Static Site or comparable provider.

Backend: Django web service on Render or comparable managed service using Gunicorn/WSGI for MVP.

Database: managed PostgreSQL; automated backups enabled.

Attachments: private S3-compatible bucket, accessed only after KWP authorization checks.

Monitoring: provider logs + an error tracker such as Sentry; uptime/health check.

Do not bind the roadmap to one vendor: environment variables and standard PostgreSQL/object-storage interfaces keep migration possible.

## 9. Testing strategy

| Layer | Tests that matter |
| --- | --- |
| Ledger unit tests | Income, expense, transfer, opening balance, edit, void; every journal balances; account/report totals correct. |
| Model/validation | Ownership, amount precision, required fields by type, category type consistency, transfer source ≠ destination. |
| API permissions | Unauthenticated denied; User A cannot read/write User B accounts, categories, transactions or attachments. |
| API behaviour | Filters, pagination, search, idempotency, error messages, exports. |
| Frontend components | Wizard progression/branching; validation; back navigation; loading/error states; dashboard cards. |
| E2E golden paths | Signup/login → onboarding → income → expense → transfer → dashboard → edit → export. |
| Responsive/manual | Small phone, large phone/tablet, desktop; keyboard navigation; browser smoke tests. |
| Deployment smoke | Production settings, HTTPS, migrations, static assets, auth callback, media access, backup/restore procedure. |

## 10. 60-day execution plan

The source roadmap refers to an Excel task tracker, which was not supplied with these documents. This document keeps the phase outcomes and exit gates. The window starts 1 October 2026 and ends 29 November 2026.

| Days | Dates | Phase | Outcome / exit gate |
| --- | --- | --- | --- |
| 1–5 | Oct 1–5 | Product freeze & architecture | MVP scope, transaction flow, posting rules, data model and security baseline are written and accepted. |
| 6–11 | Oct 6–11 | Foundation | New KWP repo runs React/Vite + Django/DRF + PostgreSQL locally; custom User exists; CI/lint basics working. |
| 12–18 | Oct 12–18 | Auth & onboarding | Email/password + Google sign-in, profile/base currency/time zone, account/category starter setup and ownership tests. |
| 19–28 | Oct 19–28 | Ledger & finance API | Accounts/categories/transactions/ledger models and posting service work; accounting tests pass. |
| 29–38 | Oct 29–Nov 7 | Transaction UX | Mobile-first wizard supports income/expense/transfer and edit/void paths against real API. |
| 39–47 | Nov 8–16 | Dashboard, reports & register | Daily flow, balances, month summary, register/filters and core report/CSV reconcile to ledger. |
| 48–51 | Nov 17–20 | P1 + settings | Attachments and/or PDF export added only if core stable; settings/archive/export-data paths polished. |
| 52–57 | Nov 21–26 | Hardening & deployment | Production/staging deployed, security checklist, monitoring, backups, E2E and reconciliation completed. |
| 58–60 | Nov 27–29 | UAT & release | Realistic test run, defects triaged/fixed, release checklist complete, v0.1 tagged. |

Scope checkpoint at Day 47: if any P0 accounting, auth or report reconciliation issue remains, immediately defer PDF/attachments/polish and protect Days 48–60 for stability.

## 11. Definition of Done by feature

| Feature | Done means |
| --- | --- |
| Account | Can create/rename/archive; opening balance posts correctly; balance reconciles; only owner can access. |
| Category | Defaults seeded; custom category can be created/renamed/archived; history remains valid. |
| Income | Wizard posts transaction; selected account increases; category income increases; journal balances; dashboard/report updates. |
| Expense | Selected account decreases; expense category increases; journal balances; dashboard/report updates. |
| Transfer | Source decreases, destination increases; total tracked assets unchanged; no income/expense impact. |
| Edit / void | Ledger and reports remain consistent and audit event exists. |
| Dashboard | Cards reconcile to report/register for same period and behave on mobile/desktop. |
| Export | Exported rows/totals match filters and server-side source data. |
| Deployment | HTTPS, production secrets, DB migrations, backups, monitoring and deployment checks verified. |

## 12. Release checklist

All P0 tasks marked Done; no blocker/critical defect open.

Backend automated tests green; frontend tests green; golden-path E2E green.

Manual reconciliation sample proves dashboard/report/account balances match source transactions.

Production uses supported patched dependencies; DEBUG is off; manage.py check --deploy reviewed.

CORS/CSRF/host/OAuth origins restricted to intended domains.

Database backup enabled and restore steps tested/documented once.

Attachment storage (if enabled) is private and authorization-tested.

No secrets or real credentials are committed to Git history.

Privacy/data export/delete-account path documented.

README includes local setup, environment variables, tests, migrations and deployment notes.

Tag release v0.1.0 and record deferred P1/P2 backlog.

## 13. Working rules for the 60 days

Build vertical slices: backend rule + API + UI + test before moving too far ahead.

Do not design reports from fake totals; derive them from the same ledger postings the transaction API creates.

Prefer small commits that leave the app runnable; never combine security/deployment work into one final-night push.

Use one lightweight Architecture Decision Record (ADR) whenever a decision would be expensive to reverse: auth transport, edit/reversal model, storage provider, base-currency rule.

Keep a “Later” list visible. New ideas go there unless they unblock P0.

Every week ends with a working demo and a 10-minute reconciliation check, not just code volume.

If behind schedule, cut P1 first, then dashboard polish. Never cut ledger tests, authorization tests, backups or deployment hardening.

## 14. Current technical references

Vite Getting Started: https://vite.dev/guide/

Django supported versions: https://www.djangoproject.com/download/

Django deployment guidance: https://docs.djangoproject.com/en/6.0/howto/deployment/

Django security guidance: https://docs.djangoproject.com/en/6.1/topics/security/

OWASP Authentication Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html

OWASP Authorization Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html

OWASP File Upload Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html

## Architecture decisions

See [the decision index](decisions/README.md) for recorded decisions and unresolved architecture choices.
