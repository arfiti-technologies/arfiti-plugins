

## Card purchase policy

Use the backend purchase workspace and shared matching decision; do not implement a competing card matcher in conversation. Preserve provider rows and show net purchase spend. Reference conflicts and competing candidates require review. A paid/settled item can still lack documentation; attach missing source evidence to the existing bill. Evidence review, waiver and grouping use `card_purchase.manage` with current version, evidence fingerprint and reason. Never infer write-off authority from matching tolerance.

Receipt follow-up belongs to the purchase obligation, with one owner and deduplicated reminder stages. Automation and delivery are report-only until the entity rollout settings are explicitly enabled. Statement coverage and opening/movement/closing balance controls must pass independently of agent match counts. August deletion/replay requires its own reviewed manifest and explicit authorization through transaction.delete; implementation permission does not authorize it.

Legacy payment-pass descriptions below apply to non-card AP/AR behavior. Card rows use the shared purchase policy and cannot use nearest-date refund pairing, fuzzy amount identity or adjusting-journal workarounds.

# Bulk Import (Master Data & Admin Panel)

This resource covers the universal bulk import system for **master data** (customers, vendors, employees, accounts, items, dimensions, fixed assets) via Claude chat or the admin panel CSV wizard.

> **For bulk transaction import** (AP invoices, AR invoices, journal entries, payments), see [Bulk Transaction Processing](bulk-transaction-processing.md).

---

## Overview

The import system provides a single entry point for all object types:

```
submit(object_type="<type>", operation="import", data=JSON.stringify({
    legal_entity_id: <id>,
    records: [...],
    options: { on_duplicate: "skip", batch_size: 50 }
}))
```

**Key features:**
- Single API for all object types
- Automatic sync (≤50 records) / async (>50 records) routing
- Pre-cached reference data for O(1) lookups
- Flexible entity resolution (by name, ID, tax_id, global_id, or external_id)
- Duplicate detection per object type
- Per-record error isolation (one failure doesn't block others)
- External ID support for data migration from QuickBooks, Xero, etc.
- Validate-only mode (dry run)
- Real-time progress tracking via `get_imports(action="status", import_id=...)`
- Entity scope enforced before the import runs — a caller cannot import into a `legal_entity_id` outside their scope

> **Two equivalent entry points:** `submit(object_type, "import", ...)` and `manage_imports(action, ...)` (see [manage_imports() in Tools Reference](tools-reference.md)) both route through the same import executor. Whichever you use, the same rules apply: any org-configured `import_batch.review` approval workflow can put a batch into `pending_approval` before it runs, and a zero-error run — including an idempotent re-run where every record is a duplicate skip — always reports `success: true`. `manage_imports` submits its record actions as `submit(<type>, "import", ...)`, so the gateway's checks apply to both. A record import is a submission (AR-1553): a read-only caller is refused with `permission_denied` (a preview too), customers, vendors and employees also need `master_data:write`, and an identical repeat (same records and options, no `idempotency_key`) returns the first answer with `idempotent_replay: true` and imports nothing; pass a new `idempotency_key` to run the same records again on purpose. A refusal before anything was written (an agent without the import grant, a record for another entity) answers `refused: true`, `effect_outcome: "no_effect"` with the reason in `message`; after fixing the cause send the same request again, it is checked again. A failure after the import took a connection (for example, another import is running) answers `status: "posting_unknown"` with `failure_reason` and a `next_step`: check the first and last records (imports commit in batches), fix the cause, and send them again with a new `idempotency_key` and `on_duplicate: "skip"` so existing records are skipped. When every row fails the answer is `status: "posting_unknown"` with the `import_id`: read `get_imports(action="status", import_id)` for the row errors; when it shows nothing imported or updated, fix the cause and resend with a new `idempotency_key`. The saved answer does not expire, so an unchanged monthly sheet re-sent without a key does nothing and reports the first run's counts: pass a new `idempotency_key` for each run. A `manage_imports` preview (`validate_only=true`) without a key runs afresh each time; with a key it follows the key. A direct `submit(<type>, "import", {..., options: {validate_only: true}})` without a key keeps the gateway's rule: a preview with every row valid replays for the same payload, one with invalid rows is checked again. Refused before anything runs (previews included): more than 10,000 records, an `on_duplicate` other than `skip`, `update` or `error`, and an organisation at its storage allowance.

---

## Supported Object Types

| Object Type | Required Fields | Duplicate Key | Notes |
|-------------|----------------|---------------|-------|
| `customer` | customer_name, email | tax_id, then customer_name | Supports billing/shipping addresses |
| `vendor` | vendor_name, email, payment_terms_code | tax_id, then vendor_name | Supports billing/remit-to addresses |
| `employee` | first_name, last_name, work_email, hire_date | work_email | Auto-generates global_employee_id |
| `account` | account_number, account_name, account_type, normal_balance | account_number | Supports parent_account_number hierarchy |
| `item` | item_number, item_name | item_number | Revenue/expense/asset/COGS account linking |
| `dimension_type` | name, display_name, applies_to | name | Hierarchy support |
| `dimension_value` | dimension_type_name, code, name | dimension_type_id + code | Parent code for hierarchies |
| `fixed_asset` | asset_number, name, legal_entity_id, original_cost, useful_life_months, in_service_date | asset_number + legal_entity_id | Category code resolution, depreciation config |

### Banking Data Importers

| Object Type | Required Fields | Duplicate Key | Notes |
|-------------|----------------|---------------|-------|
| `card_transaction` | external_transaction_id, card_id, amount, transaction_date | external_transaction_id + card_id + transaction_type | From connector or CSV. Writes to `bank_card_transactions`. **Also set `metadata.provider_purchase_id`** — the provider's id for the *purchase*, shared by every leg (charge, refund, fee) — or each leg becomes its own singleton and refunds land in review with no netting. See bank-statements-management.md, "Two ids per card row". |
| `opening_balance` | legal_entity_id, as_of_date, lines[] | — | Posts opening balance journal entry |
| `opening_balances_with_subledger` | legal_entity_id, balances[], fiscal_period_name | — | Opening balances with individual AR/AP items and fixed assets (uses clearing account 0000). Fixed assets are created with or without open items |

### Transaction Importer (Generic)

| Object Type | Required Fields | Duplicate Key | Notes |
|-------------|----------------|---------------|-------|
| `transaction` | transaction_type_code, legal_entity_id, lines[] | type + reference_number + party | Handles all 30+ transaction types via executor registry |

> **IMPORTANT — Schema Discovery Required**: Before calling `submit()` for any workflow below, you MUST first call `get_submissions(action='schema', object_type, operation)` to discover the exact required and optional fields. Each organization configures different field requirements. Never assume the fields listed below are complete — always check the schema first.

---

## Preflight Check (Discover Required Fields)

Before importing transactions, run a preflight check to discover the required fields for a specific transaction type. Required fields are configured per company in the workflow definition, so they vary between organizations.

```javascript
submit(object_type="transaction", operation="import", data=JSON.stringify({
    "_operation": "preflight",
    "transaction_type_code": "AP_INVOICE",
    "legal_entity_id": 12
}))
// Returns:
// {
//   "preflight": true,
//   "transaction_type_code": "AP_INVOICE",
//   "required_header_fields": [
//     {"field": "transaction_type_code", "type": "string"},
//     {"field": "legal_entity_id", "type": "number"},
//     {"field": "vendor_id", "type": "number"},
//     {"field": "payment_method", "type": "string"}
//   ],
//   "required_line_fields": [...],
//   "optional_header_fields": [...],
//   "optional_line_fields": [...]
// }
```

Optionally include a sample record in `records` to validate it against the full pipeline before submitting the batch.

---

## Performance Expectations

| Volume | Mode | Expected Time | Notes |
|--------|------|---------------|-------|
| 10 records | Sync | ~5 seconds | |
| 50 records | Sync | ~25 seconds | Dimension caching active |
| 200 records | Async | ~90 seconds | Dimension caching reduces ~30% of queries |
| 500 records | Async | ~4 minutes | |
| 5,000 records | Async | ~50 minutes | Multiple batches |
| 20,000 records | Async | ~2 hours | With dimension caching |

---

## Import via Claude Chat

### Step 1: User Provides Data

User may provide data as:
- CSV file upload
- Pasted table or list
- Verbal description ("Add these 5 vendors...")

### Step 2: Build Records Array

Map the data to the import format:

```javascript
// Step 1: Discover required fields for import
schema = get_submissions(action='schema', object_type="vendor", operation="import")

// Step 2: Submit with discovered fields
submit(object_type="vendor", operation="import", data=JSON.stringify({
    legal_entity_id: 12,
    records: [
      {
        vendor_name: "Acme Corp",
        email: "ap@acme.com",
        payment_terms_code: "NET_30",
        tax_id: "12-3456789"
      },
      {
        vendor_name: "Office Plus",
        email: "billing@officeplus.com",
        payment_terms_code: "NET_45"
      }
    ],
    options: {
      on_duplicate: "skip"
    }
}))
// Tip: Use options: { validate_only: true } to validate an import without persisting it.
```

### Step 3: Preview Before Submitting

**Always show a summary before importing:**

```
I've prepared 15 vendor records for import:
- Entity: Arfiti Technologies OÜ (ID: 12)
- Payment terms: NET_30 (10), NET_45 (3), DUE_ON_RECEIPT (2)
- Duplicate handling: skip existing

Shall I proceed?
```

### Step 4: Report Results

```
Import complete:
- 13 of 15 vendors created
- 2 skipped (duplicates: Acme Corp, Tech Solutions — already exist)
- 0 errors
```

---

## Sync vs Async Routing

| Records | Mode | Behavior |
|---------|------|----------|
| 1-50 | **Synchronous** | Full result returned immediately |
| 51+ | **Asynchronous** | Returns `import_id`, processes in background |

### Async Flow

```javascript
// Step 1: Submit large import
const result = submit(object_type="customer", operation="import", data=JSON.stringify({
    legal_entity_id: 12,
    records: largeArray,  // 200+ records
    options: { on_duplicate: "skip" }
}))
// Returns: { import_id: "uuid", async: true, status: "importing" }

// Step 2: Poll for progress
get_imports(action="status", import_id="uuid")
// Returns: { status: "importing", progress_pct: 60, processed_records: 120, ... }

// Step 3: Final result
get_imports(action="status", import_id="uuid")
// Returns: { status: "completed", imported_count: 190, skipped_count: 5, error_count: 5, ... }
```

**Concurrent limit:** Only one background import per organization at a time, including CSV and approved background imports, across server processes. Small record-array imports (≤50 rows) are unaffected. If refused, check import history and retry when the running import finishes; the refusal may include its import ID when that job is on the same server process. Without an import review, a refused new submission creates no import record. With an active `import_batch.review` (the default since migration 942) the import record is created before its review starts; when the start is refused (for example a green batch that runs at once while another import is running) that record is marked `failed` with the reason and its stored batch cleared, and nothing is imported. An approved batch keeps its existing record.

**Approval gate:** If the org has an `import_batch.review` workflow configured, the import (sync or async) can land in `pending_approval` instead of running immediately — check `status` in the response rather than assuming it always executes right away. By default (migration 942) every organisation has one that holds an import carrying payee bank details (vendor or employee `bank_*` fields, including a bank account added to an existing payee) for an owner or admin; imports without bank details run at once. Tell the user the import is waiting and who decides it; do not resend it, and do not strip the bank columns to get past the review unless the user asks for that. The approver sees each bank row masked (the IBAN's country and check digits, or only the country on a short national IBAN, and its last four characters; the account number's last four; the account holder, bank and SWIFT/BIC), whether the payee is new or existing, and whether the account becomes the default; a CSV file is pinned by its SHA-256 at submission, so re-uploading a different file under the same import does nothing but fail the approved run. A reviewer rejection or request for changes marks that import `rejected`; no business rows are imported. Use `get_imports(action="status", import_id=...)` to read its final status.

### What each row reports, and where to read it

Every row of a CSV file, or record of a submitted array, ends in one outcome:

| Outcome | Meaning | Where it shows |
|---------|---------|----------------|
| imported / updated | written; `updated` only with `on_duplicate="update"` | `imported` / `updated` in a synchronous answer, `imported_count` / `updated_count` in the status read |
| skipped | already there under the duplicate rule (`on_duplicate="skip"`) | `skipped` / `skipped_count`. Re-running a file that is already in reports every row skipped and `imported: 0` with no error: that is the expected result |
| error | refused, with a reason; nothing of that row is written | `errors` / `error_count`, and an entry in `errors_detail` with `row`, `field`, `error` and `record_identifier` |
| validated | a check (`validate_only`) passed it; nothing written | the check's counts |

Some outcomes belong to the whole import, not to a row:

- **Waiting for approval.** When the organisation's `import_batch.review` workflow puts the import on a reviewed lane (by default: it carries payee bank details) the answer says `pending_approval` and no row is written until a reviewer approves. A rejection ends it `rejected`: nothing imported.
- **Refused before the first row.** Another background import is running (no import record is created, or, with an import review, one marked `failed`), or a transaction file was already imported into the same entity and some of its rows carry no reference number (a deliberate re-import after reversing the first passes `options.allow_reimport: true`).

**A synchronous answer** (50 records or fewer) is final: `status` is `completed` (no errors), `partial` (some written, some refused) or `failed` (nothing written), with the counts and `errors_detail` (up to 100 entries). `success: true` can still mean a partial import; read `errors`.

**An asynchronous import** (more than 50 records, or a CSV file) answers with `import_id`. Read it with `get_imports(action="status", import_id=...)`: `status`, `total_records`, `processed_records`, the four counts, `progress_pct` and `message`. How current the counts are depends on the source:

- **CSV file job:** each row commits together with its outcome and the run's counts, so the counts always match the rows written, even after a worker stops.
- **Submitted records array:** the counts and row outcomes are written after each batch of records has committed (`batch_size`, default 100). A worker that stops mid-batch can leave the counts behind the rows already written; check the records before resubmitting.

Once the run is `completed` or `failed` the read adds `errors_detail` (the first 20 of up to 100 stored errors), `warnings` (first 20), `started_at` and `completed_at`; a `rejected` import has none of these. Any run that has stopped and records its rows adds `row_counts`: how many rows ended `imported`, `updated`, `skipped`, `error` or `validated`. `row_counts` is not given while the run is going, nor for an import from before row records existed.

**What is not reported through the tools:**

- The rows themselves (each row's values, outcome, errors and the record it wrote). The dashboard's import run page lists them; through the tools there are only the counts, `row_counts` and the first 20 errors. With more errors than that, send the person to the run page, or fix the file and run it again with `on_duplicate="skip"`.
- An opening-balance CSV keeps no row records: it posts one journal. Read it with `get_imports(action="get_opening_balances", ...)`.
- `completed` means the worker finished, not that every row went in: read `error_count`. `total_records - processed_records` is the rows not reached when a job stopped, not an error count.

---

## Import Options

| Option | Default | Description |
|--------|---------|-------------|
| `on_duplicate` | `"skip"` | `"skip"` = ignore, `"update"` = overwrite, `"error"` = fail |
| `batch_size` | `100` | Records per processing batch; independent records commit separately and grouped imports retain their group transaction |
| `stop_on_error` | `false` | Stop entire import on first error |
| `validate_only` | `false` | Dry run — no business writes. Record-array previews persist no import tracking; CSV checks retain a check record, file hash and row results |
| `defaults` | `{}` | Default values merged into every record |
| `advisory_thresholds` | none | `fixed_asset` only: warning thresholds for this import — `original_cost_above`, `useful_life_months_above`, `salvage_ratio_above` (fraction, `0.5` = 50%). None set means no threshold warnings. Take the numbers from the firm's instructions; there are no built-in ones. A threshold warns, never refuses |

With `stop_on_error: true`, a CSV worker starts no further batch after an error.
A CSV check (`validate_only`) still reads every row.
Earlier committed rows remain written. Inspect row results and counts even when
the CSV job says `completed`; `total_records - processed_records` counts rows
not attempted. Correct failed rows and use duplicate handling for any retry.

---

## Validate-Only Mode (Dry Run)

Run validation without persisting any records:

```javascript
submit(object_type="vendor", operation="import", data=JSON.stringify({
    legal_entity_id: 12,
    records: [...],
    options: { validate_only: true }
}))
```

Returns validation results: which records would succeed, which would fail, and why.

---

## External ID Support (Data Migration)

For migrating from external systems (QuickBooks, Xero, etc.):

### Step 1: Import Master Data with External IDs

```javascript
submit(object_type="vendor", operation="import", data=JSON.stringify({
    records: [{
      vendor_name: "Acme Corp",
      email: "ap@acme.com",
      payment_terms_code: "NET_30",
      metadata: { external_id: "QB-VEND-1234" }
    }]
}))
```

The `external_id` is stored in the `metadata` JSONB column. Later, transaction imports can reference entities by their external IDs (`external_vendor_id: "QB-VEND-1234"`).

### Supported External ID Fields

| Entity | Store As | Reference As (in transactions) |
|--------|----------|-------------------------------|
| Vendors | `metadata.external_id` | `external_vendor_id` |
| Customers | `metadata.external_id` | `external_customer_id` |
| Employees | `metadata.external_id` | `external_employee_id` |
| Accounts | `metadata.external_id` | `external_account_id` (line-level) |
| Items | `metadata.external_id` | `external_item_id` (line-level) |
| Tax Codes | `metadata.external_id` | `external_tax_code_id` (line-level) |

### Migration Order

1. Import accounts (chart of accounts)
2. Import vendors, customers, employees — all with `metadata.external_id`
3. Import items
4. **Import opening balances** (see below)
5. Import transactions referencing entities by external IDs
6. Import fixed assets

---

## Opening Balance Import

**CRITICAL:** Always use `manage_imports("opening_balances", ...)` for opening balances. **Never** use `submit(object_type="transaction", operation="post")` — it will fail with validation errors and miss auto-balancing, fiscal period checks, and subledger support.

### When to Use

- Migrating from a prior accounting system (Merit, QuickBooks, Xero, etc.)
- Setting up opening balances for a new entity starting on Arfiti
- User provides a balance sheet from the prior year

### Before you import: what to ask and check

Ask these before any write, in this order, and answer the person's question first if they asked one ("can I put it all in on 1 April?" is a question, not an instruction to post). When they say not to change anything, read and explain only.

1. **Which entity, and which old system.** Ask what the old system can export: a trial balance at the cutoff, the open customer invoices and vendor bills behind the receivable and payable balances, and the fixed asset register. Data comes in from those exports through the imports below.
2. **The fiscal year.** Ask when the company's financial year starts and ends, then read the entity's periods: `query("fiscal_period", filters={"legal_entity_id": ID}, limit=50)`. If the periods in Arfiti do not follow the year the person gives, stop and say so; do not post until it is resolved.
3. **The cutoff and the opening date.** The last day the old books cover (the trial balance's as-of date) and the first day the books run here. See Step 1.
4. **Does the trial balance still hold income and expense accounts?** At the last day of a financial year, read [At a fiscal-year boundary](#at-a-fiscal-year-boundary) before proposing a date. In the middle of a year, see the note under Step 2.
5. **Open items and assets.** Whether they can give the open invoices, bills and asset register (Step 3); they decide which import runs.
6. **The balancing account.** A trial balance that balances needs none. Any difference beyond rounding is explained before posting, not absorbed. For what remains, the person names the equity account (`balancing_account_number` has no default; you may list the entity's equity accounts to choose from) and you record their choice.
7. **What already exists.** Opening entries in any period (Step 1; `get_onboarding(action="check_status")` gives the number of posted opening entries and their first and last dates), a chart and posting profiles (`ready_to_post` covers only the chart and one active profile), and an open monthly period containing the opening date: `check_status` reports only the period containing today, so read the opening date's period with `query("fiscal_period", ...)`.

Do not guess any of these. In particular never assume the fiscal year, the cutoff date, the balancing account, how the old year's result was or should be closed, or a tax treatment of the prior year. Where the answer depends on a country's rules (for example how a year-end result is closed or filed), say so and point to that country's pack (`plugins-guide.md`) or the person's accountant; this guide states no country's rule.

### Step 1: Agree the Opening Date, then Ensure Its Fiscal Period Exists

Two dates are involved; keep them apart:

- **As-of date** — the date of the source trial balance or balance sheet ("balances as at 31 October 2026").
- **Opening date** — the day the opening entry is dated in Arfiti: the cutover, the first day the books run here.

The opening entry is dated the **first day of the fiscal period** you name in `fiscal_period_name`, unless `opening_date` names another day inside that period. Balances as at D with a cutover on D+1 open on **D+1**: name the period that contains D+1. A trial balance as at 31 October 2026 with a 1 November cutover goes to `fiscal_period_name="2026-11"` and is dated 1 November 2026. Never pick the as-of date's month just because the source is dated month-end: `"2026-10"` would date it 1 October and show the balances for the whole of October.

- If the user wants the entry dated the as-of date itself (31 October), that is a different, explicit choice: pass `fiscal_period_name="2026-10", opening_date="2026-10-31"` only after they agree to it.
- A mid-period cutover (balances as at 14 November, cutover 15 November): `fiscal_period_name="2026-11", opening_date="2026-11-15"`.
- `opening_date` outside the named period, a quarter or year period, or a closed or locked period is refused before anything is written. `opening_balances_with_subledger` takes no `opening_date`; it always posts on the period's first day.
- **One opening entry per entity and period.** A second upload for a period that already has a posted opening entry, or one still waiting for approval, is refused; the answer's `existing_opening_entry` names it and its own date (`existing_posting_date`). To change the date of a waiting one, have it rejected first; of a posted one, reverse it first.
- **Check every period first.** The guard is per period: an opening entry already posted in another period of the entity (for example one dated 1 October when the agreed date is 1 November) is not refused. Before importing, look for existing opening entries in all periods (`query("transaction", filters={"legal_entity_id": ID, "transaction_type": "OPENING_ENTRY"})`) and, if one is wrong, reverse it before posting the new one.
- **At a fiscal-year boundary with a trial balance that still holds income and expense accounts**, the date is chosen differently: see [At a fiscal-year boundary](#at-a-fiscal-year-boundary) below.

Every preview (`validate_only=true`) and every result states `posting_date`, `posting_period` and `posting_date_note`. **Before posting, tell the user the exact date** ("the opening entry will be dated 1 November 2026, period 2026-11") and get their agreement. After posting, read the stored date back (`get_imports(action="get_opening_balances", ...)` returns `posting_date`), not only the totals.

Opening balances from a 31.12.2024 balance sheet with a 1 January cutover go to fiscal period **2025-01** (January of the new fiscal year). Check if the period exists:

```javascript
query("fiscal_period", filters={"legal_entity_id": 12}, limit=50)
```

If periods for the target year don't exist, **create them first**:

```javascript
// Create the needed fiscal period
submit(object_type="fiscal_period", operation="create", data=JSON.stringify({
    "legal_entity_id": 12,
    "period_name": "2025-01",
    "period_type": "month",
    "start_date": "2025-01-01",
    "end_date": "2025-01-31",
    "fiscal_year": 2025
}))
```

**Do NOT just post to the earliest existing period** — opening balances MUST be in the correct fiscal year.

### At a fiscal-year boundary

When the cutoff is the last day of a financial year and the trial balance still holds income and expense accounts (the year's result is not yet closed to equity, for example to retained earnings), say what each choice does before proposing one. The tool posts whatever date it is given; it does not refuse an unclosed trial balance, and nothing is wrong in the posted amounts. The difference is in how the reports treat the income and expense lines:

| Choice | What the reports do |
|---|---|
| **A closed trial balance** (balance-sheet accounts only, the year's result already closed to equity) | Nothing special: the normal rule applies (balances as at D open on D+1). Recommend this first. |
| **Unclosed, dated the new year's first day** | The opening entry carries income and expense lines into the new year. An income statement whose dates include that day comes back `quality: "incomplete"`, without totals, with the evidence gap `AMBIGUOUS_PERFORMANCE_JOURNAL` ("Opening balances or transfers to retained earnings may contain earlier profit"); the new year's balance sheet leaves the equity total open. No tool marks the entry's year as confirmed, so this stays for every income statement covering that day unless the entry is reversed and posted again on another date. |
| **Unclosed, dated the old year's last day** (`opening_date`) | The lines belong to the old year. The new year's balance sheet balances and shows them as "Prior years result (not closed)"; the new year's income statement is complete. Income statements whose dates include the old year's last day are withheld the same way, and the balance sheet as at that day (the cutoff itself) has no equity total, so compare the import with the source trial balance through the trial balance report, not the balance sheet. |

How to handle it:

1. Ask for a closed trial balance first, and say why in these terms (which reports are withheld, and from when), not as "the figures will be wrong".
2. If they cannot provide one, propose the old year's last day: name the exact date and period ("the opening entry will be dated 31 December 2025, period 2025-12") and wait for their agreement. This is the one exception to "balances as at D open on D+1" the assistant proposes on its own (Andrew, 24 Nov 2026, AR-1456); it is guidance, not a rule the server enforces. Example: `fiscal_period_name="2025-12", opening_date="2025-12-31"`.
3. Check it is possible before proposing it: the old year's last monthly period must exist in Arfiti and be open (a closed or locked period is refused before anything is written; reopening one is the accountant's decision). If it does not exist because the books never ran here in that year, creating a lone month there is the person's or accountant's decision, and how the reports treat such a partial year has not been tested; the closed trial balance avoids the question. The import must be `opening_balances` or the CSV import (there `opening_date` is a default value for the whole file, never a mapped column): `opening_balances_with_subledger` takes no `opening_date` and refuses one, so with open invoices, bills or assets to load, the closed trial balance is the way. If the person still chooses the old-year date, the receivable and payable balances post as amounts with no invoices or bills behind them and the assets are not in the register; say so.
4. The choice is the person's (or their accountant's). Do not decide for them how the old year's result should be closed, do not post a closing entry to "fix" it on your own, and do not describe a country's year-end rule as general.

### Step 2: Map the Balance Sheet

Read the user's balance sheet and map each line to a chart of accounts entry. For a closed trial balance, only include **balance sheet accounts** (assets, liabilities, equity) — NOT revenue or expense accounts (those reset to zero each year). A trial balance at a year end that still holds income and expense accounts is the case in [At a fiscal-year boundary](#at-a-fiscal-year-boundary).

**A cutoff in the middle of a financial year, with year-to-date income and expense in the trial balance, is not covered by this guide**: no treatment has been agreed. Do not drop those lines and do not pick a date on your own. Say the case is open, ask the person or their accountant how they want it handled, and tell them what the tools do with each choice: left out, the year-to-date result falls into the balancing equity account and this year's income statement covers only the period after the cutover; included in the opening entry, every income statement whose dates include the opening date is withheld (`AMBIGUOUS_PERFORMANCE_JOURNAL`) and the balance sheet's equity total stays open for the rest of that year.

**Debit/credit rules:**
- Assets with positive balances → **debit**
- Liabilities with positive balances → **credit**
- Equity with positive balances → **credit**
- Accumulated depreciation (contra-asset) → **credit**

### Step 3: Detect Subledger Accounts (ALWAYS DO THIS)

Before uploading, check if the balance sheet includes these accounts:

| Account Type | Detection | Ask For |
|---|---|---|
| **Accounts Receivable** | `account_subtype: accounts_receivable`; names with "receivable", "trade debtor" | List of unpaid customer invoices (customer, invoice #, amount, date, due date) |
| **Accounts Payable** | `account_subtype: accounts_payable`; names with "payable", "trade creditor" | List of unpaid vendor bills (vendor, bill #, amount, date, due date) |
| **Fixed Assets** | `account_subtype: fixed_asset_cost` (cost) + `accumulated_depreciation` | List of assets (name, acquisition date, cost, accum depreciation, useful life) |

**ALWAYS ask the user for these details.** Explain the tradeoff:
- **With details**: aging reports work, depreciation runs automatically, payment scheduling has individual items
- **Without details**: GL balance is correct but subledger features don't work (one lump sum in aging)

### Step 4: Upload

**Basic (no subledger details):**

```javascript
manage_imports("opening_balances", {
    legal_entity_id: 12,
    balances: [
        {"account_number": "1000", "debit": 50000, "credit": 0},
        {"account_number": "1200", "debit": 25000, "credit": 0},
        {"account_number": "2000", "debit": 0, "credit": 30000},
        {"account_number": "3000", "debit": 0, "credit": 45000}
    ],
    fiscal_period_name: "2025-01",
    balancing_account_number: "3300"
})
```

**With subledger details (preferred):**

```javascript
manage_imports("opening_balances_with_subledger", {
    legal_entity_id: 12,
    balances: [
        {"account_number": "1000", "debit": 50000, "credit": 0},
        {"account_number": "1200", "debit": 25000, "credit": 0},
        {"account_number": "2000", "debit": 0, "credit": 30000},
        {"account_number": "1500", "debit": 40000, "credit": 0},
        {"account_number": "1600", "debit": 0, "credit": 15000},
        {"account_number": "3000", "debit": 0, "credit": 70000}
    ],
    fiscal_period_name: "2025-01",
    balancing_account_number: "3300",
    open_ar_items: [
        {"customer_name": "Acme Corp", "reference_number": "INV-001", "amount": 15000,
         "invoice_date": "2024-10-15", "due_date": "2024-11-15"},
        {"customer_name": "Widget Inc", "reference_number": "INV-002", "amount": 10000,
         "invoice_date": "2024-11-20", "due_date": "2024-12-20"}
    ],
    open_ap_items: [
        {"vendor_name": "Supplier Co", "reference_number": "BILL-042", "amount": 20000,
         "invoice_date": "2024-12-01", "due_date": "2025-01-15"},
        {"vendor_name": "Office Depot", "reference_number": "BILL-043", "amount": 10000,
         "invoice_date": "2024-12-10", "due_date": "2025-01-10"}
    ],
    fixed_assets_detail: [
        {"name": "Server Equipment", "category": "COMPUTER", "acquisition_date": "2023-06-15",
         "in_service_date": "2023-06-15", "original_cost": 25000,
         "accumulated_depreciation": 10000, "useful_life_months": 60},
        {"name": "Office Furniture", "category": "FURNITURE", "acquisition_date": "2022-01-01",
         "in_service_date": "2022-01-01", "original_cost": 15000,
         "accumulated_depreciation": 5000, "useful_life_months": 84}
    ]
})
```

**Fixed assets (AR-1409).** Each record needs `name`, `category` (an existing category code of
the entity), `acquisition_date`, `in_service_date` (never defaulted) and `original_cost`;
`useful_life_months`, `depreciation_method` and `salvage_value` fall back to the category when
omitted. Assets are created whether or not there are open AR/AP items. Every record is checked
before anything posts: one unusable record (or an entity without a `fixed_asset` number series)
refuses the whole migration, naming each asset and why, and nothing is written; the dry run
reports the same. `accumulated_depreciation` is recorded on each asset as taken through the day
before the migration period, posting no GL (the opening entry carries it), and the schedule
covers only what remains. The answer's `fixed_assets` block lists the assets created and any
difference between the asset register and the GL accounts (`gl_variances`, also named in
`warnings`): compare the assets' cost and accumulated depreciation with the trial balance lines
of their category accounts.

**How the subledger version works:** The system uses a clearing account (0000) to keep the GL balanced. Each open AR/AP item becomes its own posted transaction. The OPENING_ENTRY posts the clearing account instead of the AR/AP control accounts. The clearing account nets to zero. Result: same GL balances, but individual items in aging reports.

**Both versions go through the organization's workflow.** `opening_balances` submits its OPENING_ENTRY as `transaction.post`; `opening_balances_with_subledger` runs as the operation `opening_balance.migrate`. The answer carries a `workflow_id`. If the organization's workflow holds it for approval, the answer is `status: "pending"` and nothing is posted until a person approves — tell the user, and do not resubmit. A refusal (`workflow_definition_missing`, `permission_denied`) means nothing was written. `validate_only=true` previews and needs no approval.

### Step 5: Verify

Check the stored date first, then the amounts, on the opening date and the day before:

```javascript
get_imports(action="get_opening_balances", legal_entity_id=12, fiscal_period_name="2025-01")  // posting_date
generate_report("trial_balance", {"legal_entity_id": 12, "as_of_date": "2025-01-01"})  // the opening date
generate_report("trial_balance", {"legal_entity_id": 12, "as_of_date": "2024-12-31"})  // the day before: no opening amounts
```

Check: `posting_date` is the agreed date, total debits = total credits, each line matches the user's balance sheet on the opening date, and none of it shows the day before.

### The Balancing Account

The `balancing_account_number` (an equity account of the entity, e.g. its `retained_earnings` account; ask the user which one) absorbs any small rounding difference. If the balancing amount is more than rounding, something is wrong — review the data.

### Common Pitfalls

1. **Forgetting accumulated depreciation**: Fixed assets at cost (a debit to the `fixed_asset_cost` account, e.g. 1500), accumulated depreciation as a separate credit (the `accumulated_depreciation` account, e.g. 1600)
2. **Double-counting net income**: If the balance sheet already includes net income in retained earnings, don't add it again
3. **Missing fiscal periods**: Always create periods before posting — don't post to wrong year
4. **Dating the entry on the as-of month**: balances as at 31 October with a 1 November cutover belong in period 2026-11 (dated 1 November), not 2026-10 (dated 1 October)
5. **Using submit() instead of manage_imports()**: submit() doesn't handle auto-balancing or subledger detection

---

## Address Support

Three importers support address fields via flat CSV columns:

**Customer:** `billing_*` and `shipping_*` prefixes
```
billing_address_line_1, billing_city, billing_state, billing_postal_code, billing_country
shipping_address_line_1, shipping_city, shipping_state, shipping_postal_code, shipping_country
```

**Vendor:** `billing_*` (primary) and `shipping_*` (remit-to) prefixes

**Employee:** `home_*` and `mailing_*` prefixes

Addresses require `legal_entity_id` to be set.

---

## Admin Panel: CSV Import Wizard

The admin dashboard provides a 5-step wizard for CSV file imports at **Administration > Bulk Import**.

### Step 1: Select Type
- Choose object type (customer, vendor, employee, account, item, etc.)
- Select target legal entity

### Step 2: Upload CSV
- Drag-and-drop or browse file upload
- Instant preview of first 50 rows
- Shows total row count and column headers

### Step 3: Field Mapping
- **Auto-mapping**: CSV headers automatically matched to target fields (lowercased, normalized)
- **Required fields** highlighted — must be mapped or given a default value
- **Default values**: Set fallback values for unmapped required fields
- **Metadata catch-all**: Toggle to store all unmapped CSV columns as JSONB metadata (preserves legacy data)
- **Mapping templates**: Save/load reusable mapping configurations per object type

### Step 4: Review
- Summary of settings, field mapping, and options
- Duplicate handling mode selection

### Step 5: Progress
- Real-time progress bar with percentage
- Live counters: imported, updated, skipped, errors
- Error list with row numbers and record identifiers
- Duration on completion

### Import History

View past imports at **Administration > Bulk Import > History**:
- Status, counts, and duration for each import
- Filter by object type
- Color-coded status badges

---

## Common Errors

| Error | Cause | Fix |
|-------|-------|-----|
| `Required field missing: email` | CSV row missing required field | Map the column or set a default value |
| `Duplicate: Acme Corp` | Record already exists | Use `on_duplicate: "update"` or `"skip"` |
| `Payment term NET99 not found` | Invalid foreign key reference | Check available payment terms. Use underscore format: `NET_30`, `NET_60`, `DUE_ON_RECEIPT` |
| `Account 9999 not found` | Invalid account number | Verify account exists for this entity |

### Recovery from Partial Failures

1. Check `errors_detail` in the response
2. Fix problematic records in CSV
3. Re-submit with `on_duplicate: "skip"` to skip already-imported records
4. Successfully imported records are NOT rolled back

> A clean re-run of a batch that's already fully imported reports `success: true` with `imported: 0` and every record counted as a duplicate skip — that's the expected idempotent result, not a failure. Look at `error_count`, not `imported_count`, to tell whether the re-run actually found new problems.

---

**Version**: 1.0
**Last Updated**: February 2026
**Related Resources**:
- [Bulk Transaction Processing](bulk-transaction-processing.md) - Transaction-specific bulk import
- [Vendor Management](vendor-management.md) - Vendor master data
- [Customer Management](customer-management.md) - Customer master data
- [Employee Management](employee-management.md) - Employee records
- The `implementation-consultant` skill in the `arfiti` plugin (`/start-migration`) - Full system migration workflow

### Import scope and dry runs

For a records-array `import.execute`, place `validate_only` inside `options`; a top-level flag is rejected. A stored-CSV request instead supplies a company-scoped `r2_storage_key` and non-empty `field_mapping` without `records`; its legacy top-level check flag remains accepted. `get_submissions(action="schema", object_type="customer", operation="import")` describes both alternatives. Public `submit(..., validate_only=True)` checks the envelope but does not read the file or validate its rows; `options.validate_only` starts an actual CSV row check. The outer `submit` object type supplies the payload type when omitted. Supported built-in import types are `account`, `card_transaction`, `customer`, `dimension_type`, `dimension_value`, `employee`, `fixed_asset`, `item`, `opening_balance`, `transaction`, and `vendor`. A top-level `legal_entity_id` is copied into each record for synchronous, asynchronous and approval paths. A conflicting record entity is rejected. Use separate imports for different entities. Dimension codes identify classification; they never compute or allocate monetary amounts.

## Validation, partial results and transaction boundaries

For a submitted **records array**, `options.validate_only` (or `manage_imports(action=<import type>, validate_only=true)`) validates without import tracking, approval requests or business writes. The response sets `validation_only=true`; `validated_records` counts valid records and `imported` is zero. When any row is invalid it also sets `success=false` and lists the rows in `errors_detail`. Through `submit()` the dry run runs inside a database transaction that is always rolled back, so the answer carries `effect_outcome: no_effect` and the same request identity replays it; before AR-1346 a dry run with an invalid row was answered `posting_unknown`.

Each independent imported record commits with its GL, workflow audit and external-link rows on one connection. A failed record rolls back its counts and IDs, and processing continues unless `stop_on_error=true`. Existing grouped imports retain group transactions. The synchronous record-array response reports `status="partial"` if some records succeeded, otherwise `status="failed"`; compatibility `success=true` may still represent partial success. A CSV job can report `completed` with rejected rows; inspect its `error_count` and row records. Inspect errors before retrying and use duplicate handling to avoid replaying committed records.

For a rejected Merit group, every rolled-back row counts as processed and as an error. The group has one summary cause and one error row outcome per record; `total_records - processed_records` still means rows not attempted.

Transaction imports refuse missing/inactive tenant `transaction.post` definitions when the template defines that operation, including validation and connector imports. This check supplements the existing `import_batch.review` approval path; it does not remove it. `get_submissions(action="schema", object_type="customer", operation="import")` and other supported import aliases expose the shared two-form import envelope; public preview success is not proof of row or file validity.


### Employee numbering across imports and creation (E2E-041)

Employee creation and imports without a supplied `global_employee_id` use the
same tenant `master_employee_seq` through the shared employee allocator. IDs
are organization-wide, formatted `EMP-` plus at least six digits; separate legal
entities do not restart this master ID sequence. Allocation skips IDs already
occupied by earlier or explicit imports, without resetting the counter or
renumbering existing records. Concurrent generated allocations use PostgreSQL
`nextval`; rolled-back or failed operations may leave normal gaps.

Explicit IDs in imports are preserved and still subject to duplicate detection
and database uniqueness checks. They do not change the configured sequence.
Do not manually reset the counter to recover a collision; retry the failed
creation after deploying the shared allocator. Custom source IDs need not have
a numeric EMP suffix. Numbers beyond six digits are preserved, not truncated.


For an R2 CSV payload (`r2_storage_key`), `options.validate_only` is the
implemented **Check rows first** path. It streams the file and persists an
import check record, `check_sha256` and per-row validation/error results; it
does not write business records or consume the approval or re-import gates.
On that check record, `imported_count` counts rows that passed validation,
not newly imported business records. Inspect `options.validate_only` and the
later Execute run separately.
A later Execute uses only the rows that passed that completed check, after
verifying the file bytes and the checked target/mapping still match.

### Interrupted import recovery

The server probes import lifetime session locks at startup and every five minutes
until shutdown. The interval schedules probes; it is not an import-age threshold.
New jobs claim
that lock before publishing `importing`, including preprocessing and nontransaction
imports, and release it after processing/finalization. Another worker's held lock
prevents recovery. An unlocked marked record becomes `failed`, retaining its
counts and existing errors and appending a restart explanation. No age threshold
is used. The message says rows **recorded** as written. CSV jobs with row
records (every importer except opening balances) commit each row or Merit
group with its row outcome and the run's counts in the same transaction. A failed outcome write
rolls back that business row, which is then recorded as an error ("CSV row
outcomes could not be persisted"); a row the ledger refuses at COMMIT is
recorded the same way. A worker loss after commit preserves its outcome. A rolled-back row's error outcome is written right after
the rollback; if that write fails, the run stops and its row records are marked
`partial`. The difference between total and processed rows is not an error
count: it is the rows not reached when the job stopped. Large record-array
imports and CSV jobs from before November 2026 can still have lagging progress,
so inspect the ledger before resubmitting a partial or historical file.

For a failed run with known or uncertain written rows, the public import-status
message and Dashboard run detail repeat that review-before-retry instruction.
They do not describe a no-write refusal as having written rows.

A CSV opening-balance import binds its posted
`OPENING_ENTRY` to the import ID and stores its processed/imported counts in the
journal metadata. If the worker stops just after posting, recovery restores
counts only from that exact journal; an unbound same-period entry is never
credited to the import. When binding cannot be verified, review the period
before retrying. A second opening entry for the same entity and period is
refused. Opening-balance CSV does not use generic per-row receipts. The CSV job reads
an opening-balance file as one batch, whatever its size, so a trial balance of more
than 100 accounts posts as one journal.
Its imported count excludes a generated balancing-account line.

Rolling-upgrade limitation: unmarked legacy `importing` records are counted in
startup logs as `legacy_needing_review` and left unchanged. Their liveness cannot
be proved with the transaction-only file lock, especially during preprocessing.
Review them after all old workers stop; do not infer failure from age or reset
counts. Pending jobs that died before starting are also outside this sweep.
The file fingerprint lock prevents a simultaneous duplicate transaction-file import. For new imports, a marker committed with the first written row also prevents a same-file retry if the worker dies before its progress count is saved. Recovery reports only durably stored outcomes; it does not guess what an in-flight row would have done. Older fingerprinted imports made before this marker or the row-outcome change require manual review when their counts may have lagged.

### Mandatory account subtype

Supply a canonical `account_subtype` for every account creation/full import, including
headers, inactive accounts and duplicate updates. Use the stored account type on updates.
Missing, null and blank subtype are errors. A partial `account.update` may omit subtype
only to retain an existing classification; explicit clearing is refused. A legacy account
with no subtype needs reviewed classification before update. Unmapped connector accounts
cannot be promoted; do not guess from names or default them to an arbitrary subtype.
Migration 664 installs the database presence constraint; legacy gaps are preserved and
require operator review/validation. This does not activate the new AP/AR membership policy.

Account updates after migrations 665–668 must preserve protected settings once the account
has a GL/document-line/profile reference. Duplicate imports with changed classification or
policy flags fail that row; unchanged settings and presentation edits remain permitted.
Zero balance is not permission to reclassify. Refer the change for a reviewed transition;
do not clear usage state or delete references. Historical transition apply remains unavailable. The migration-669 operator correction
procedure is separate, requires no retained financial evidence and cannot be invoked merely
because an import was approved.


### Transaction import event references — historical policy, superseded by PR403

Generic MCP reads of retained `import.completed.transaction` and
`import.completed.opening_balance` events from `import_executor` validate every
ID in `created_ids` and `updated_ids` against stored transaction type and the
event entity. Opening-balance import IDs refer to `OPENING_ENTRY` transactions.
The event type must agree with its payload object type; both arrays must be
present and contain positive integer IDs. Malformed, missing, foreign-entity or
unauthorized references hide the event on all generic read surfaces.

This changes event reads only. Transaction update-on-duplicate remains unsupported
and skipped by the importer; validating hostile updated arrays does not add update
support. Binding the event to its retained import record remains open coverage. Import execution and recovery permissions are unchanged.


### Master-data and card import event references — historical policy, superseded by PR403

Import completion events for customers, vendors, employees, accounts, items,
dimension types/values, fixed assets and card transactions validate both ID
arrays using the installed registry's read permissions and record keys. Effective
views use master IDs, not entity-assignment IDs. Entity records must match the
event entity; dimension types belong to the caller's organization. Every supplied
ID must resolve, even for wildcard callers.

Card IDs additionally use stored employee ownership: ordinary members can read
their own employee's records, while the existing broad membership roles retain
their wider access. Caller-supplied role labels do not grant that access. The
existing event payload domain, organization, entity, task and mailbox checks also
apply. Unknown importer types, mismatched event types and malformed arrays fail
closed. This checks referenced record access; it does not yet prove the event's
binding to a retained import run or certify arbitrary copied narrative.


### PR396 disposition — superseded by PR403 (2026-10-20)

PR396 was closed unmerged after comparing its head
`5a032a152181097285889c823e594d28df3ba475` with main
`0fe26ae70eb6c5030483d07d0ec2c1f8eb6088b0`. Its only production-code
change added retained-import envelope checks to `import_event_read_sql`. That
helper has no production callers after PR403; its remaining caller is the
explicitly historical `tests/legacy_event_read_fixtures.py`.

Current Dashboard and MCP agent-event reads use the shared agent-artifact grant
and certified entity-scope policy. Import source/payload traversal is not part of
that read decision. PR396 did not change import producers or execution validation,
so it would not fix current production behavior. The old tests and benchmarks
remain historical evidence, not acceptance requirements for the replacement
policy. Import execution/recovery and underlying business-record permissions remain
unchanged. PR396 was never merged or deployed; no replacement CI run is needed
for this documentation-only disposition.
