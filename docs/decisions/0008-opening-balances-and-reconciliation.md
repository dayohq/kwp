# 0008: Visible opening balances and reconciliation adjustments

Status: Accepted design for Packet 6B; posting and reporting not implemented

Recorded: 8 October 2026

## Context

[ADR 0002](0002-ledger-and-corrections.md) makes the ledger the balance source of truth. Packet 6 left opening-balance representation open and allowed nullable journal/transaction links. This approved correction supersedes ADR 0007's suggestion of invisible ledger-only opening balances. Both initialization and subsequent reconciliation must be visible, auditable financial events.

## Decision

Opening balance and balance adjustment each use a visible Transaction, its same-owner one-to-one JournalEntry, and JournalLines. They ultimately appear in the user's transaction register, clearly distinguished from ordinary activity. They never directly edit FinancialAccount balances, create ordinary income/expense categories, or change the asset/income/expense/equity ledger classes.

Ordinary Add Transaction choices remain Income, Expense and Transfer. The model also supports the special/internal kinds opening_balance and adjustment. Adding these now is a small structural extension: widen Transaction.kind to 15 characters and update its kind/category constraints. No new direction, balance, target-balance or lifecycle fields are introduced. These rows remain drafts; no posting, provisioning, reporting or automatic journal creation is added.

amount remains a positive Decimal magnitude for every kind. The posted journal will establish whether an adjustment increases or decreases the asset (asset debit versus asset credit). A negative movement is not a negative stored Transaction.amount. The future reconciliation command will receive the actual balance and derive direction/magnitude inside the posting service; incomplete drafts are not yet executable reconciliation instructions. Packet 8 must specify and validate that command contract and audit metadata before posting is enabled.

## Opening balance versus adjustment

| Event | Purpose | Visible representation | Counter-account |
| --- | --- | --- | --- |
| Opening balance | Initialize an account when starting KWP: “I already had 200,000 in GTBank.” | Transaction(kind=opening_balance) + JournalEntry + JournalLines | Opening Balance Equity |
| Balance adjustment | Reconcile an already-used account: “KWP says 185,000; my bank says 200,000.” | Transaction(kind=adjustment) + JournalEntry + JournalLines | Unclassified Balance Adjustment / Reconciliation Equity |

Both counter-accounts use the existing equity ledger class and belong to the same user. Their distinct purposes must remain explicit even if display names are refined. Do not reuse opening-balance semantics for routine reconciliation. No equity accounts are seeded or provisioned by Packet 6B.

## Intended Packet 8 accounting

The following rules are approved design, not implemented posting logic:

| Event | Debit | Credit |
| --- | --- | --- |
| Positive asset opening balance (200,000) | FinancialAccount's asset ledger, 200,000 | Opening Balance Equity, 200,000 |
| Positive asset adjustment (+15,000) | FinancialAccount's asset ledger, 15,000 | Reconciliation Equity, 15,000 |
| Negative asset adjustment (-15,000) | Reconciliation Equity, 15,000 | FinancialAccount's asset ledger, 15,000 |

The future workflow calculates the ledger balance, accepts the actual balance, detects a difference, and obtains user confirmation before recording a visible adjustment. It does not rewrite the calculated balance or reconstruct fabricated missing activity. The difference may come from a missing transfer, omitted income/expense, refund, fee, deposit or recording error; the default must not assert an unknown economic cause as classified income or expense. A zero difference creates no monetary event under the positive-amount invariant.

The posting service must create Transaction + JournalEntry + JournalLines atomically, with same-user ownership and balanced total debits/credits. It must require a visible transaction for opening/adjustment postings. JournalEntry.transaction stays nullable solely for incomplete draft assembly; this does not authorize future invisible opening/adjustment postings. Posted-link completeness belongs to Packet 8's lifecycle enforcement.

## Register and reporting direction

Example future register (illustrative design, not data inserted by this packet):

| Date | Event | Account effect |
| --- | --- | --- |
| 1 Oct | Opening balance — GTBank | +200,000 |
| 7 Oct | Salary | +500,000 |
| 7 Oct | Eat Out | -8,500 |
| 8 Oct | Transfer GTBank to OPay | 50,000 transfer |
| 10 Oct | Balance adjustment — GTBank | +15,000 |

Opening balances establish the starting position and are excluded from ordinary income/expense totals. Transfers are movements between owned accounts, excluded from ordinary income/expense totals. Adjustments affect balances and remain visible separately as unclassified reconciliation movement; they do not masquerade as classified income/expense.

One possible future report separates income 500,000 and expenses 260,000 into net classified flow 240,000, then separately shows unclassified adjustments +15,000 and net movement 255,000. Exact report names/layout, period treatment of initialization and inclusion rules remain future reporting design. This example does not imply an implemented report calculation.

Repeated or material adjustments may indicate incomplete records. Future analytics may show adjustment magnitude/frequency, the proportion of movement that is classified and reconciliation/data-quality indicators. No metric, report, register, API or frontend finance form is implemented now.

## Consequences and remaining decisions

Retain Decimal(24,6), positive magnitude, draft-only states, ownership validation, PROTECT, idempotency uniqueness and journal admin read-only protections. Categories are permitted only on income/expense; destination_account is permitted only on transfers. Special kinds are schema vocabulary for dedicated future workflows, not additional ordinary entry choices.

The representation, equity classification, report separation and both adjustment directions are decided. Command/audit metadata, posting-date policy, posted lifecycle enforcement and edit/void implementation remain Packet 8 work under ADR 0002. Exact reporting presentation and future encrypted account-identifier security are separate later work. This correction does not implement Packet 7 or Packet 8.
