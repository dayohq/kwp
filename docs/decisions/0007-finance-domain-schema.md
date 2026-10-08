# 0007: Finance domain and ledger schema

Status: Accepted for Packet 6; clarified by Packet 6B and ADR 0008

Recorded: 7 October 2026; clarified: 8 October 2026

## Context

[ADR 0002](0002-ledger-and-corrections.md) establishes the hidden double-entry ledger and future atomic posting service. [ADR 0003](0003-base-currency-and-ownership.md) requires one owner and one currency designation per user. Packet 6 supplies the schema and structural validation only. Posting, balancing, starter provisioning, finance APIs and frontend finance UI are not implemented.

## Model boundaries and relationships

Use one `finance` Django app. All six concrete models have stable BigAutoField identifiers and timezone-aware created_at/updated_at timestamps.

| Model | Meaning and important fields |
| --- | --- |
| FinancialAccount | User-visible place holding money. Required user/name/kind (bank, wallet, cash, other); optional institution_name/subtype/last_four; is_active, include_in_total and display_order. No full bank number, editable balance or opening-balance field. |
| Category | User-visible income/expense classification. Required user/name/kind; optional parent and is_active. Rename preserves identity. Hierarchy has roots and children only, with matching owner/type. |
| LedgerAccount | Internal accounting destination/source. Required user/name/kind (asset, income, expense, equity). Equity accounts can remain unlinked to user-visible objects. |
| Transaction | User-facing event (ordinary income/expense/transfer; special opening_balance/adjustment): user, kind, positive amount, occurred_at, optional note and idempotency_key, draft status. Optional account, destination_account and category links support incomplete drafts. account is primary for income/expense and source for transfers. |
| JournalEntry | Accounting representation: explicit user, optional unique transaction, accounting-effective entry_at, draft status. At most one journal per transaction; the explicit owner must match. Null transaction permits incomplete draft assembly only. Opening balances/adjustments require visible Transactions in the future posting workflow (ADR 0008). |
| JournalLine | One debit or credit against a LedgerAccount, attached to a JournalEntry. Ownership derives exclusively from the entry; no redundant line user field. Exactly one positive debit/credit, with the unused side NULL. |

FinancialAccount optionally links one-to-one to a same-user asset LedgerAccount. Category optionally links one-to-one to a same-user LedgerAccount of matching income/expense class. Linking is explicit; saving any object creates no companion ledger, journal or lines. Nullable companion links permit safe independent creation before future provisioning. Names are not unique: identity comes from primary keys, not labels.

entry_at is the accounting-effective timestamp, independent from creation time and the user's event timestamp. This supports explicit posting-date policy; it does not imply ledger-only opening/adjustment events. The future service must assign it deliberately; no timestamp synchronization/posting behavior is implemented now. All date values supplied through model validation must be aware, including parsed datetime strings. Storage follows Django USE_TZ/UTC; local display conversion is later work.

## Money representation

Transaction.amount and JournalLine.debit/credit are DecimalField(max_digits=24, decimal_places=6): 18 integral digits and six fractional digits, maximum 999999999999999999.999999. This covers 0/2/3 minor-unit currencies and additional supported precision up to six places with substantial per-row headroom. Aggregation uses Decimal/PostgreSQL numeric; do not cast sums back into a narrower field or introduce floats. Currency-specific allowed scales/rounding and amount limits belong to the posting boundary. There is no FX conversion or currency snapshot; values use the owner's selected designation per ADR 0003.

Ordinary model validation rejects float input, non-finite values and excessive precision rather than silently rounding them. Decimal values or exact decimal strings are accepted. PostgreSQL fixed-scale numeric can round over-precise raw SQL input, so bypassing validation is not a supported monetary input path.

## Database integrity

PostgreSQL enforces foreign keys, required owner references, non-null required columns, one-to-one ledger companions and transaction journals, and these constraints:

- Account, category, ledger and transaction kinds are limited to their declared choices.
- last_four is empty or exactly four ASCII digits (never a full bank number); field length is four.
- Categories cannot parent themselves.
- Transaction amount is positive and finite, below 10^18. The upper bound rejects numeric NaN, which PostgreSQL sorts above finite values.
- JournalLine has exactly one non-null, positive, finite debit/credit. Both populated, both NULL, zero and negative states are invalid. SQL predicates include explicit null tests to avoid CHECK's unknown/null loophole.
- Only income/expense can have a category: transfers, opening_balance and adjustment must have category NULL. Only transfers can have a destination, and source/destination differ when both exist.
- Optional transaction idempotency keys are unique per owner; NULL allows drafts without a request key. No key generation or replay service exists yet.
- Transactions and journals currently have only draft status. Rows cannot claim to be posted before a balancing service exists.

## Application integrity

Normal finance save()/objects.create() invoke full_clean(); clean() contains structural validation only. Django admin forms also validate. Cross-table ownership is not represented by unsupported SQL CHECKs.

Model validation checks the persisted related row, not stale Python FK caches. It rejects cross-user transaction accounts/categories, account/category ledger links, category parents, journal transactions and journal-line ledger links. Existing owners cannot be reassigned through validated writes; this prevents parent ownership edits invalidating related records. Parent/category/ledger class edits also check their reverse links, preventing ordinary edits from leaving mismatched children, transaction categories or companion classes.

Category trees are limited to two levels. Self-parenting, cycles, deeper descendants, mismatched types/owners, and reparenting a node with children are rejected. A populated transaction category must match its transaction kind.

These application checks are not database guarantees against raw SQL, QuerySet.update(), bulk_create()/bulk_update(), deliberate save overrides or concurrent class/hierarchy changes. Such bypasses are unsupported for finance writes without equivalent explicit validation. Future provisioning/posting services must validate and lock appropriate rows inside transactions, including concurrent changes. No database triggers or hidden multi-row lifecycle behavior are introduced in this packet.

## Archive, deletion and admin

is_active=False means archived for accounts/categories. Archived objects remain valid historical references; no history is deleted or relinked by archiving. Future posting decides whether new events may use archived objects.

All finance foreign keys use PROTECT. Deleting a user with finance objects, used accounts/categories, category parents, linked ledgers, transactions with journals, or journals with lines is blocked through normal Django deletion. Database foreign keys also preserve referential integrity. Unreferenced accounts/categories may be deleted. Direct draft line deletion remains possible in trusted code; this is not an immutable-history/audit implementation. A deliberate user deletion/privacy workflow and final posted-history edit/deletion policy are deferred.

All six models are registered for development inspection. Accounts, categories and ledgers have basic editable admin forms with immutable existing owner fields and model validation. Transactions, journals and lines are inspection-only in admin to avoid manual financial-history edits bypassing a future posting service. Full admin ownership filtering and posted-history protections must be reviewed before enabling non-superuser accounting administration.

## Deferred posting invariant

Every **posted** JournalEntry must eventually satisfy SUM(debits) == SUM(credits), with at least the required complete lines. Packet 6 deliberately allows incomplete/unbalanced drafts and does not check cross-row balance on JournalLine.save(). No posted state is exposed by this schema.

Packet 8's posting service must enforce balance, required companion/account/category links, valid leaf-category policy, amount/currency scale, nonfuture posting dates, archived-object eligibility, idempotent creation/replay, atomic transaction/journal/line creation or replacement, and audited edits/voids. Extending draft-only lifecycle constraints requires a forward migration alongside that service. ADR 0008 resolves visible opening/adjustment representation and equity counter-accounts. Their posting implementation, void/audit representation and reversal/replacement behavior remain future work under ADR 0002. No posting or balancing engine is implemented.

Packet 7 templates/provisioning and Packet 8 posting logic are not implemented. No starter or system ledger data migration is introduced.

## Packet 6B model and future UX clarification

FinancialAccount remains the user-visible money location; LedgerAccount remains the internal journal account. For example, the user sees GTBank Current, institution GTBank and last_four 1234; its eventual explicit backing is a same-user LedgerAccount named GTBank Current with kind=asset. These are distinct objects, not a collapsed account/category design.

Category.kind is the top-level income/expense classification, not a synthetic parent row named Income or Expense. Within income, root groups Employment/Professional can have children Salary/Bonus and Consulting/Freelance. Within expense, Feeding/Transportation can have Groceries/Eat Out and Fuel/Ride-hailing. Roots and children remain the existing two levels; no grouping rows or templates are seeded. Transfer is never a Category kind and never has a category. Transfers are excluded from ordinary income/expense totals.

The future ordinary Add Transaction UI must show only fields relevant to the selected kind:

| Ordinary kind | Relevant inputs | Excluded inputs |
| --- | --- | --- |
| Income | amount, account, category, note, date/time | destination account |
| Expense | amount, account, category, note, date/time | destination account |
| Transfer | amount, source account, destination account, note, date/time | category |

Nullable model links support different shapes and incomplete drafts; they do not justify exposing every field in every frontend form. Special opening_balance/adjustment kinds support dedicated accounting workflows and are not ordinary Add Transaction options. No finance UI or API is implemented.

[ADR 0008](0008-opening-balances-and-reconciliation.md) is the authoritative opening-balance/reconciliation decision. Balances remain ledger-derived. [The security backlog](../security-backlog.md) records optional future encrypted full identifiers, their scheme/country diversity and key-management requirements. last_four is unchanged; there is no plaintext full identifier or encryption implementation in the current schema.
