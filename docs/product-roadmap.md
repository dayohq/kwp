# KWP Product Roadmap

Source: `KWP_Product_Roadmap.docx` (supplied reference). This document records the planning baseline; it does not assert that implementation or release gates are complete.

A mobile-first personal finance product focused on fast capture, trustworthy accounting and useful daily visibility

MVP planning baseline • 60-day build window: 1 October–29 November 2026

Product promise: record money movement in seconds, while KWP quietly maintains accounting integrity underneath. The user should not need to think in debits and credits to get reliable balances and reports.

## 1. Product direction

### Vision

KWP should make personal finance tracking feel lighter than a spreadsheet and more trustworthy than a simple expense log. Its first job is to help an individual record money movement quickly on a phone, then turn those records into accurate daily flow, account balances and simple financial reports.

### Primary MVP user

An individual who actively uses multiple bank, fintech and cash accounts and wants one reliable place to record personal money movement.

The user is comfortable with financial concepts but should not be required to perform accounting entries manually.

The MVP assumes one owner per KWP profile. Shared household accounts, teams and delegated access are later features.

### Core product principles

| Principle | What it means in KWP |
| --- | --- |
| Mobile first | The transaction flow is designed for a phone first; desktop preserves the same sequential experience rather than turning it into a long form. |
| Amount first | New transaction capture begins with one dominant amount input. Other decisions appear one step at a time. |
| Accounting hidden, correctness visible | KWP posts balanced journal lines in the backend but presents user-friendly transaction language. |
| Fast defaults, easy correction | Date/time, starter accounts and categories default intelligently; base currency requires explicit selection during onboarding and has no backend default. Every choice remains editable. |
| No false financial meaning | Transfers are not income or expenses. Reports must avoid double-counting internal money movement. |
| User owns the data | Users can view, filter and export their records. Sensitive information is collected only when needed. |
| MVP discipline | The app solves capture + visibility well before budgets, bank sync, OCR, investments or advanced AI. |

## 2. MVP outcome and scope

The 60-day target is a usable MVP that can be trusted with real personal transactions. The release should be small enough to finish, but architected so future finance features do not require replacing the core ledger.

| Tier | Included |
| --- | --- |
| P0 — Release-critical | Secure signup/login; Google sign-in; base currency/profile; account and category setup; opening balances; income/expense/transfer recording; balanced ledger; mobile-first transaction wizard; daily flow dashboard; account balances; transaction register; filters; edit/delete/void behavior; income/expense report; CSV export; production database; automated tests; secure deployment; backups and basic monitoring. |
| P1 — Scheduled but cuttable | PDF report/export; receipt/document attachments; richer note suggestions; extra dashboard widgets; polished report layouts. These should not delay release if P0 is unstable. |
| P2 — Post-MVP | Budgets; recurring transactions; notifications; bank integrations; OCR/receipt extraction; AI/ML categorisation; multi-currency accounting; credit cards/loans; investments; net-worth reporting; shared accounts; offline/PWA; advanced tax and financial analytics. |

## 3. Transaction capture experience

The capture experience is a guided sequence, not a web form. Only the current decision is visually dominant. Progress dots/back navigation may be shown, but future fields should not crowd the screen.

### Income / expense flow

Amount — large numeric input with the user’s base-currency symbol. Amount must be positive; transaction type determines accounting direction.

Type — Income, Expense or Transfer.

Account — select the bank/wallet/cash account affected.

Category — shown for Income or Expense. Category is not required for Transfer.

Note — optional. Show relevant templates/recent phrases based on category and month, without requiring machine learning in the MVP.

Record — the last screen/button shows a compact summary and records the transaction. Date/time defaults to now but is editable without creating another mandatory step.

### Transfer flow

Amount

Type = Transfer

From account

To account

Optional note

Record transfer

Interaction rule: disable the Record action while a request is being submitted and use an idempotency key server-side so double-taps cannot create duplicate money entries.

Correction rule: users can go back to earlier steps before posting. After posting, edits must update the transaction and its ledger atomically and create an audit event.

Date rule: default to the user’s local date/time; allow back-dated records; do not allow scheduled/future posting in MVP.

Desktop rule: use a centered step panel or modal-like flow rather than exposing the entire transaction form at once.

Accessibility rule: touch targets, labels, keyboard navigation, focus states and readable contrast are release requirements, not polish.

## 4. Accounts and opening balances

Starter accounts should be templates that users activate or rename, not 15 accounts automatically added to every dashboard. All MVP accounts use the user’s single base currency.

| Starter template | Default kind | Purpose |
| --- | --- | --- |
| Main Current Account | Bank | Primary transactional bank account |
| Main Savings Account | Bank | Primary savings bank account |
| Salary Account | Bank | Dedicated salary account |
| Secondary Current Account | Bank | Secondary transactional account |
| Secondary Savings Account | Bank | Secondary savings account |
| Digital Bank / Fintech Wallet | Wallet | Fintech balance such as a digital bank/wallet |
| Mobile Money Wallet | Wallet | Mobile money balance |
| Side Gig / Business Account | Bank | Personal side-business cash account |
| Joint / Household Account | Bank | Tracked jointly-used account; still owned by the KWP user in MVP |
| Other Bank Account | Bank | Generic bank account slot |
| Wallet Cash | Cash | Cash carried personally |
| Home Cash | Cash | Cash held at home |
| Office Cash | Cash | Cash kept at work |
| Travel Cash | Cash | Cash separated for travel |
| Emergency Cash | Cash | Physical emergency reserve |

### Account fields

Display name; kind (Bank, Wallet, Cash, Other); optional institution name; optional subtype; optional last four digits only; opening balance; active/archived state; include-in-total flag; display order.

Do not collect full bank account numbers in the MVP because there is no bank integration that requires them.

Accounts with transaction history are archived rather than hard-deleted.

Opening balance is not income. It is posted against an internal Opening Balance Equity account so reports are not distorted.

## 5. Categories and note suggestions

Default categories are copied into each user’s profile so the user can rename, archive or add categories without changing system-wide templates. Category IDs remain stable even when labels change so historical reports stay consistent.

| Type | Parent | Examples |
| --- | --- | --- |
| Income | Employment | Salary, Bonus, Allowance |
| Income | Professional | Professional Income, Consulting, Freelance / Side Gig |
| Income | Business | Business Income, Commission |
| Income | Investments / Other | Interest, Investment Income, Gifts, Reimbursements, Other Income |
| Expense | Feeding | Groceries, Eat Out, Snacks & Drinks |
| Expense | Transportation | Fuel, Public Transport, Ride-hailing, Vehicle Maintenance, Parking & Tolls |
| Expense | Housing | Rent, Home Maintenance, Furnishing |
| Expense | Utilities & Bills | Electricity, Internet, Airtime, Subscriptions |
| Expense | Personal | Clothing, Grooming, Health, Fitness |
| Expense | Growth & Leisure | Education, Books, Entertainment, Travel |
| Expense | Family & Giving | Family/Dependants, Gifts, Donations & Giving |
| Expense | Financial / Statutory | Bank Charges, Taxes, Fees |
| Expense | Other | Miscellaneous |

Categories can have parent/child relationships but the transaction should normally post to a leaf category.

Used categories are archived rather than deleted. Unused user-created categories may be deleted.

MVP note suggestions use deterministic templates and recent history — e.g., Salary → “September salary” — rather than claiming to learn with AI.

A later version can rank suggestions from transaction history, merchants, location or recurring patterns.

## 6. Accounting and transaction logic

KWP should expose three user transaction types while maintaining a hidden double-entry ledger. Journal entries are the accounting source of truth; dashboard and report logic must respect the posting rules below.

| User action | Debit | Credit | Reporting effect |
| --- | --- | --- | --- |
| Income into an account | Selected asset account | Income category ledger account | Increases selected account balance and period income. |
| Expense from an account | Expense category ledger account | Selected asset account | Decreases selected account balance and increases period expense. |
| Transfer between owned accounts | Destination asset account | Source asset account | Changes individual balances; no income/expense and no change to aggregate tracked assets. |
| Positive opening balance | Selected asset account | Opening Balance Equity | Sets starting tracked balance without creating income. |

Ledger invariant: every posted journal entry must balance exactly: total debit = total credit.

Money precision: use decimal money fields, never binary floating-point values.

Ownership: every user-visible and ledger object is scoped to the authenticated user; cross-user access is rejected server-side.

Atomicity: transaction record, journal entry and journal lines are created/updated within one database transaction; partial postings are not permitted.

Transfers: source and destination must be different and must both belong to the same authenticated user in the MVP.

Base currency: one base currency per user, explicitly selected during onboarding without a backend default. NGN may later be recommended in the UI but must not be silently assigned. Users may change base currency at any time, including after financial activity. MVP changes only the currency designation: no FX conversion occurs, and existing transaction amounts, journal amounts and account balances remain numerically unchanged. KWP does not provide multi-currency accounting in MVP.

Reversals/audit: for MVP, edits can re-post ledger lines atomically while recording an audit event. A stricter immutable reversal model can be introduced later.

## 7. Dashboard and reporting

The home screen is a responsive collection of summary cards/widgets. It should prioritise the user’s current money position and today’s movement, not show a long transaction ledger by default.

| Widget/report | MVP behaviour |
| --- | --- |
| Daily Flow | Today by default: income, expense and net flow. Transfers are excluded from income/expense totals and may be shown separately. |
| Account Balances | Active accounts with individual balances plus total tracked balance. |
| Month-to-Date | Income, expense and net for the current month. |
| Spending by Category | Top expense categories for selected period. |
| Income by Category | Income composition for selected period. |
| 7/30-day Trend | Simple income/expense/net trend. |
| Income & Expense Statement | Date-range report generated from income and expense ledger accounts. |
| Transaction Register | Separate screen: searchable/filterable/editable list, not the main dashboard. |
| Exports | CSV is P0; clean PDF report/register export is P1. |

Filters: date range, transaction type, account, category, and note search.

Report labels should use understandable personal-finance wording even when derived from formal ledger accounts.

Do not call total asset-account balance “net worth” until liabilities and investments are properly modelled.

Empty-state dashboards should teach the next useful action instead of displaying zero-heavy cards.

## 8. Attachments / receipts

Attachments are a P1 feature scheduled within the 60-day plan but are cuttable if the core ledger is not stable. The data model should support multiple attachments even if the first UI exposes a small limit.

Allowed MVP types: PDF, JPEG and PNG only.

Set a small per-file limit (for example 5 MB) and a small per-transaction limit.

Validate extension and actual file type; generate storage filenames; never execute uploaded files.

Store privately in object storage and serve through authorized, time-limited access rather than public URLs.

Receipt OCR and automatic categorisation are post-MVP.

## 9. Signup, onboarding and user settings

Create account with email/password or Google.

Verify email when using password signup.

Explicitly select base currency (no automatic NGN assignment) and confirm local time zone.

Select/rename starter accounts and enter opening balances.

Accept preset categories; optionally rename or add a few.

Land on the dashboard with a prominent “Add transaction” action.

Settings: profile, currency (changeable at any time with explicit confirmation), time zone, account management, category management, export data, change password, logout and delete KWP account.

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

Password reset and Google account recovery should rely on standard proven flows rather than custom security questions.

## 10. Security, privacy and data resilience

| Area | MVP requirement |
| --- | --- |
| Authentication | Use Django’s proven password handling; Google OAuth through a maintained package/provider flow; verified email; password reset; secure session/token handling. |
| Authorization | All account, category, transaction, attachment and report queries are user-scoped and tested for cross-user access failures. |
| Secrets | No secrets in Git. Separate local/staging/production environment variables. Rotate any exposed credentials. |
| Transport | HTTPS-only in production; secure cookie settings and CSRF/CORS rules matched to deployed origins. |
| Uploads | Allowlist file types; validate size/type; randomise storage name; private object storage; authorized access. |
| Database | Managed PostgreSQL in production; backups enabled; one restore test before launch. |
| Logging | Log errors and security events, but avoid passwords, auth tokens, full financial notes or attachment contents. |
| Abuse controls | Rate-limit login/password-reset and other sensitive endpoints; generic auth errors where appropriate. |
| Lifecycle | Users can export their records and request deletion. Accounts/categories with history archive rather than silently breaking reports. |

## 11. Non-functional requirements

Responsive from ~320px phone width through desktop; no horizontal scrolling in core flows.

Core transaction creation should feel immediate; show explicit loading and failure states and never create a silent duplicate.

Keyboard and screen-reader basics: semantic controls, labels, visible focus, logical tab order and sufficient contrast.

Graceful network errors with retry; no false “success” message until the API confirms a post.

Database migrations version-controlled; production migrations reversible or backed up when data-destructive.

Monitoring for server errors and uptime; structured application logs; health endpoint.

Separate local, staging/preview and production configuration where practical.

User-facing dates use local time zone; backend timestamps stored consistently.

## 12. MVP success criteria

| Gate | Acceptance target |
| --- | --- |
| Capture | A user can record income, expense and transfer successfully on mobile without seeing a long form. |
| Accounting | Test suite proves every posting balances and transfer is excluded from income/expense. |
| Balances | Account balances match ledger postings after create, edit and delete/void operations. |
| Reporting | Daily flow, month-to-date and income/expense statement reconcile to the same underlying transactions. |
| Security | Cross-user API access tests fail as expected; deployment checklist passes; secrets are not committed. |
| Resilience | Production database backup is enabled and a restore procedure is documented/tested once. |
| Usability | Core flows work on at least one small phone viewport, one larger phone/tablet viewport and desktop. |
| Release | No open blocker/critical defect; P1 features may be deferred without delaying release. |

## 13. Risks and trade-offs

| Risk | Decision / mitigation |
| --- | --- |
| Scope grows beyond 60 days | Maintain P0/P1/P2 boundaries. Cut P1 before compressing testing or ledger work. |
| Double-entry logic becomes UI complexity | Keep ledger internal; expose only Amount / Type / Account / Category / Note. |
| Too many starter accounts/categories | Use templates and activation rather than auto-creating everything. |
| Auth consumes build time | Use maintained Django/OAuth components; do not build a custom auth protocol. |
| Receipt uploads create security/storage burden | Make P1 and private; strict type/size rules; no OCR yet. |
| Reports disagree | All report queries derive from one posting model and have reconciliation tests. |
| Busy schedule causes slippage | Plan by outcome windows, include buffer and protect final 9 days for testing/deployment/UAT. |

## 14. Post-MVP roadmap

| Horizon | Likely themes |
| --- | --- |
| v0.2 — Automation | Recurring transactions, reminders, richer note/category suggestions, saved report filters. |
| v0.3 — Planning | Budgets, goals/sinking funds, planned vs actual, cash-flow forecasting. |
| v0.4 — Broader balance sheet | Credit cards, loans, liabilities, investments, net-worth reporting. |
| v0.5 — Data capture | Bank feeds/integrations, receipt OCR, import from CSV/bank statements. |
| Later | Multi-currency accounting, household/shared access, PWA/offline capture, advanced analytics/AI insights. |

## 15. Open design discussions to resolve during the build

Final report visual format and terminology after the ledger is working with real sample data.

Whether a transaction edit should update the original journal or automatically create reversal + replacement entries in a later accounting-hardening version.

Whether PDF export and attachments remain inside MVP after Day 47 core review.

Exact starter category depth: enough to be useful without creating selection fatigue.

How much of the transaction date/time control should be visible before the final step.

Hosting provider selection and custom-domain timing once staging is working.

### Technical reference notes

The product requirements above are implementation-agnostic, but the security and deployment expectations align with current Django and OWASP guidance. Useful references:

https://vite.dev/guide/

https://www.djangoproject.com/download/

https://docs.djangoproject.com/en/6.0/howto/deployment/

https://docs.djangoproject.com/en/6.1/topics/security/

https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html

https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html

## Architecture decisions

See [the decision index](decisions/README.md) for recorded decisions and unresolved architecture choices.
