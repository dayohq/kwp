# 0002: Ledger source of truth and transaction corrections

Status: Accepted planning baseline

Recorded: 2 October 2026

Sources: [Product roadmap](../product-roadmap.md) and [Development roadmap](../development-roadmap.md), based on the supplied DOCX references. Status records the roadmap position, not implementation completion.

## Context

Balances and reports must reconcile after creation, editing and removal, while users interact with income, expense and transfer concepts.

## Decision

Use a hidden double-entry ledger and Decimal money fields. Income debits assets and credits income; expense debits expense and credits assets; transfers debit destination assets and credit source assets. Positive opening balances debit assets and credit Opening Balance Equity. A posting service creates or updates the transaction, journal entry and lines atomically. Edits re-post affected lines atomically and record audit events. Delete/void excludes the posting from active balances and reporting in a controlled, audited manner.

## Consequences and follow-up

Every posted entry must balance exactly. Derive MVP balances and reports from journal lines; defer caching until profiling justifies it. Require positive input amounts, same-user ownership, distinct transfer accounts, and creation idempotency unique per user. Transfers and opening balances do not create income/expense. Immutable reversal plus replacement is a later option; the precise delete/void representation remains to be defined.
