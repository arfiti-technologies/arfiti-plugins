---
name: financial-reports
description: Present standard financial reports from Arfiti's server reports — Balance Sheet, Profit & Loss, Cash Flow Statement, Trial Balance, AR/AP Aging, P&L by dimension and a Financial Summary. The server classifies, totals and reconciles; this skill presents those results without rebuilding them.
---

## Trigger

Activate when the user mentions: balance sheet, profit and loss, P&L, income statement, cash flow, trial balance, financial statements, financial summary, aged receivables, aged payables, aging report, AR aging, AP aging, dimension analysis, department P&L, project profitability, or cost center analysis.

## Prerequisites

Determine:
1. **Legal entity ID**: the entity to report on. A report on an entity outside the user's access returns `code: REPORT_SCOPE_FORBIDDEN`; say they lack access to that entity instead of retrying.
2. **Date or period**: as-of date (balance sheet, trial balance, aging) or start and end date (P&L, cash flow).
3. **Comparison**: prior period or prior year, if wanted.

## Core principle: the server report is the source of truth

Always request the exact report contract by adding `"report_contract": 1` to every `generate_report` call, and present its figures as the server returned them. The server already returns:

- rows classified by account type and **account subtype** (never by account number);
- totals over the **full selection** (`coverage.totals_scope`), even when only one page of rows is delivered;
- the functional currency and its precision (`currency.code`, `currency.decimal_places`);
- a completeness status and every evidence gap, warnings included (`quality`);
- reconciliation verdicts (`details.reconciliation`), the balance sheet's earnings bridge and the cash flow bridge.

Never retype amounts into a hand-built JSON, re-classify accounts, sum displayed rows into totals, round to two decimals, or turn a `null` amount into zero. A `null` is **Unavailable**; say so and show the gap's message.

Show every evidence gap, including warnings on a complete report (for example a defaulted business timezone). When `coverage.has_more` is true, the rows are one page: the totals still cover everything, but row detail is not complete until the next page (`coverage.next_cursor`) is fetched.

## Reports

| Report | Server call (add `"report_contract": 1`) | Presentation |
|---|---|---|
| Balance sheet | `generate_report("balance_sheet", {legal_entity_id, as_of_date[, comparison_mode]})` | by hand, as under Output |
| Profit and loss | `generate_report("income_statement", {legal_entity_id, start_date, end_date[, comparison_mode]})` | by hand, as under Output |
| Cash flow | `generate_report("cash_flow_statement", {legal_entity_id, start_date, end_date[, method]})` | by hand: the server rows and bridge |
| Trial balance | `generate_report("trial_balance", {legal_entity_id, as_of_date})` | by hand: the server rows and totals |
| Aged receivables, aged payables | `generate_report("ar_aging" \| "ap_aging", {legal_entity_id, as_of_date})` | by hand, as under Output |
| Dimension analysis | one `income_statement` per dimension value with a `dimension_filter` | by hand, as under Output |
| Financial summary | `income_statement`, `balance_sheet` (as of the period end) and `cash_flow_statement` | by hand, as under Output |

`comparison_mode` is `"prior_period"` or `"prior_year"` for the income statement; for the balance sheet `"prior_year"`, or `"prior_period"` with `comparison_period_from`. The comparison arrives inside the same result (`details.comparison`) with its own quality; show it as a Prior column. Without a comparison there is no Prior column; never present a missing comparison as zeros.

## Ties between reports

- **Balance sheet**: use the server's reconciliation verdict. It is a pass only when the status is `tied` and quality is complete.
- **P&L and balance sheet**: the balance sheet's current-year result covers the **fiscal year to the as-of date** (`details.earnings_bridge`). Compare it with the P&L only when the P&L period is that same fiscal-year-to-date window; for any other period, don't assert a tie.
- **Cash flow**: present the server's opening cash + operating + investing + financing + FX effect + other balance adjustments = closing cash and its reconciliation verdict. Don't recompute cash flow from balance sheet differences.

## Plugin analysis and policy

Ratios, margins, days outstanding and follow-up suggestions are this plugin's analysis, not server facts, and the output labels them so. Which subtypes count as current items, cash, receivables, payables and inventory, which ratio bands apply and what follow-up wording to use are the firm's policy. This package ships no default for them: ask the user before calculating a ratio, and never present a band as universal ("healthy") or a follow-up step as an instruction. Days outstanding use the actual length of the income statement period, never a fixed 365.

Overdue means more than 0 days past due, as the server counts it (`totals.overdue`, every past-due bucket). Both agings report amounts owed: positive is owed by the customer (AR) or to the vendor (AP). A party with a negative total is a credit or unapplied amount, by its own sign, never by comparison with the overall total; it keeps its sign and stays visible.

Collection and payment suggestions are advice for the user to decide on. This plugin sends no reminders and schedules no payments.

## Discovery

- Accounts: `query("account", filters={"legal_entity_id": ID, "account_type": "asset", "account_subtype": "cash"})`. The filter fields are `account_type`, `account_subtype`, `is_active`, `is_header`, `allow_manual_entries`.
- Dimension types: `query("dimension_type")` gives the type names and IDs. Dimension values: `query("dimension_value", filters={"legal_entity_id": ID, "dimension_type_id": TYPE_ID})` returns a flat list. Each row carries `master_dimension_value_id`, `dimension_type_id`, `code`, `name` and `is_active`; inactive values remain valid for historical periods.
- Budgets: `variance_summary` needs `budget_version_id`; find the version first.

## Output

1. Present the report from the server result by hand. Start with a header that carries the entity, dates (requested and effective), currency, business date and timezone source; then quality, gaps and coverage; then the figures.
2. Commentary refers to the figures shown. Mention unavailable figures and gaps first.
3. For every report: server rows and totals, the currency's decimal places, every gap, the server's verdict.

## Errors

- `success: false` with a `code`: show the server's message (for example `REPORT_SCOPE_FORBIDDEN`, or `report_unavailable` with its reason).
- No rows: say so; check the period and entity. An empty complete report shows real zeros.
- A result requested without `report_contract: 1`, or results for one presentation that differ in entity, currency or period: fix the request (add `report_contract: 1`, use the same entity, currency and period) and run it again.
