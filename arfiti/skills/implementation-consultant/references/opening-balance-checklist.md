# Opening Balance Preparation Checklist

Step-by-step guide to preparing and uploading opening balances.

## What Are Opening Balances?

Opening balances represent the financial position of the company at the cutoff date — the moment the old system stops and Arfiti takes over. Every balance sheet account (assets, liabilities, equity) gets an opening entry. Income statement accounts (revenue, expense) are NOT included — they start at zero in Arfiti.

## The Opening Date

Keep two dates apart: the **as-of date** of the source balances (the cutoff, e.g. 31 October 2026) and the **opening date** the entry is dated in Arfiti (the cutover, normally the next day: 1 November 2026).

- The opening entry is dated the first day of the fiscal period in `fiscal_period_name`, unless `opening_date` names another day inside it (`opening_balances` only).
- Balances as at D with cutover D+1: name the period containing D+1 (31 October balances, 1 November cutover: `"2026-11"`, dated 1 November).
- An entry dated the as-of date itself (31 October) only if the user explicitly agrees: `fiscal_period_name="2026-10", opening_date="2026-10-31"`. A mid-period cutover: `opening_date` on that day.
- The preview (`validate_only=true`) and the result state `posting_date`. Tell the user that date and get agreement before posting; read it back afterwards.
- Look for opening entries already posted in **any** period (`query("transaction", filters={"legal_entity_id": ID, "transaction_type": "OPENING_ENTRY"})`): the one-per-period guard does not see another period. Reverse a wrong one first.
- Cutoff on a fiscal year's last day with income or expense accounts still in the trial balance: see **At a fiscal-year boundary** below before proposing a date.

## At a fiscal-year boundary

The tool posts the date it is given; it does not refuse an unclosed trial balance, and the amounts are posted as given. What changes is how the reports treat the income and expense lines:

| Choice | What the reports do |
|---|---|
| Closed trial balance (balance-sheet accounts only, the year's result closed to equity) | Nothing special; the normal D+1 date. Recommend this first. |
| Unclosed, dated the new year's first day | An income statement whose dates include that day is returned `quality: "incomplete"` without totals (gap `AMBIGUOUS_PERFORMANCE_JOURNAL`); the new year's balance sheet leaves the equity total open. No tool marks the entry's year as confirmed, so this stays unless the entry is reversed and posted again on another date. |
| Unclosed, dated the old year's last day (`opening_date`) | The new year's balance sheet balances, with the amount under "Prior years result (not closed)"; the new year's income statement is complete. Income statements covering the old year's last day are withheld the same way, and the balance sheet as at that day has no equity total: check the import against the source with the trial balance report. |

1. Ask for the closed trial balance first. Explain it in those terms (which reports are withheld, from when), not as "every figure will be wrong".
2. If they cannot provide one, propose the old year's last day, name the exact date and period, and wait for agreement. This is the one exception to "balances as at D open on D+1" the assistant proposes on its own (Andrew, 24 Nov 2026, AR-1456); guidance, not a rule the server enforces.
3. Check it is possible first: the old year's last monthly period must exist and be open (reopening a closed one is the accountant's decision; creating a lone month in a year the books never ran in is the person's or accountant's decision, and its report behaviour is untested), and the import must be `opening_balances` or the CSV import. `opening_balances_with_subledger` refuses `opening_date`, so with open items or assets the closed trial balance is the way; chosen anyway, receivables and payables post without the invoices and bills behind them and the assets are not in the register.
4. The person or their accountant chooses. Never decide how the old year's result is closed, never post a closing entry to "fix" it, and never present one country's year-end rule as general (the country pack covers its own).

## Prerequisites

Before uploading opening balances, ensure:
- [ ] Chart of accounts is imported (Phase 1 complete)
- [ ] Bank accounts are created
- [ ] Vendors and customers are imported (needed for subledger records)
- [ ] Fixed asset categories exist (if importing assets)

## Source Document

The user needs one of these:
- **Trial balance** as of cutoff date (preferred — has all accounts with balances)
- **Balance sheet** as of cutoff date (only balance sheet accounts — no P&L)
- **Closing balance report** from old system

## Account Mapping

For each line in the source document:
1. Match to an account in the imported CoA by account number or name
2. Determine if it's a debit or credit balance:
   - `account_type` asset: normally debit
   - `account_type` liability: normally credit
   - `account_type` equity: normally credit
   - `account_type` revenue, expense, cogs: not part of a balance-sheet opening balance. A trial balance that still holds them is either the year-end case ("At a fiscal-year boundary" above) or a mid-year cutoff, which no agreed treatment covers: ask the person or their accountant and state what each choice does (left out, the year-to-date result falls into the balancing account; included, income statements covering the opening date are withheld and the balance sheet's equity stays open for the rest of that year)
   (use the mapped account's type, never its number range)
3. Flag any unmatched lines for user clarification

## The Clearing Account Pattern

Opening balances use a balancing equity account the client chooses (often retained earnings; ask, never assume a number) to ensure the entry balances:

```
Debit:  1000 Cash           10,000
Debit:  1200 Receivables    25,000
Credit: 2100 Payables              15,000
Credit: 2500 Loans                  8,000
Credit: <equity>  Ret. Earnings   12,000  ← balancing entry (client's chosen account)
```

**Why clearing account matters for subledger:**
When AR and AP have individual open items (invoices/bills), the opening balance entry uses clearing account 0000 for the control accounts (1200, 2100). The individual AR_INVOICE and AP_INVOICE transactions post to the actual control accounts. This way:
- The GL control account total is correct (sum of individual items = clearing offset)
- Each individual invoice/bill appears in aging reports
- The clearing account (0000) nets to zero

## Subledger Detection

Scan the balance sheet for accounts that need individual records. See **advisory-intelligence.md** for the full detection rules.

**Critical subledger accounts:**
| Account | `account_subtype` | Individual Records Needed |
|-------------|-------|--------------------------|
| Accounts Receivable | `accounts_receivable` | Open customer invoices |
| Accounts Payable | `accounts_payable` | Open vendor bills |
| Fixed Assets | `fixed_asset_cost`, `accumulated_depreciation` | Asset register entries |

Classify by the mapped account's subtype, never by number range: ranges differ between charts and countries.

## Upload Methods

### Basic Opening Balance (no subledger detail)
```
manage_imports(
    action="opening_balances",
    legal_entity_id=ENTITY_ID,
    balances=[
        {"account_number": "1000", "debit": "10000.00", "credit": "0"},
        {"account_number": "1200", "debit": "25000.00", "credit": "0"},
        {"account_number": "2100", "debit": "0", "credit": "15000.00"},
        ...
    ],
    fiscal_period_name="2026-01",
    balancing_account_number="<equity account the client chose>"
)
```

### With Subledger Details (recommended)
```
manage_imports(
    action="opening_balances_with_subledger",
    legal_entity_id=ENTITY_ID,
    balances=[...],
    fiscal_period_name="2026-01",
    balancing_account_number="<equity account the client chose>",
    open_ar_items=[
        {
            "customer_name": "Acme Corp",
            "reference_number": "INV-2025-089",
            "amount": 5000.00,
            "invoice_date": "2025-10-15",
            "due_date": "2025-11-15"
        }
    ],
    open_ap_items=[
        {
            "vendor_name": "Office Supply Co",
            "reference_number": "BILL-4521",
            "amount": 2500.00,
            "invoice_date": "2025-11-01",
            "due_date": "2025-12-01"
        }
    ],
    fixed_assets_detail=[
        {
            "name": "Dell Server R750",
            "acquisition_date": "2023-06-15",
            "original_cost": 15000.00,
            "accumulated_depreciation": 5000.00,
            "useful_life_months": 60
        }
    ]
)
```

## Verification

After uploading, run these checks:

1. **Stored date**: the result's `posting_date` (or `get_imports(action="get_opening_balances", ...)`) is the agreed opening date
2. **Trial balance**: `generate_report("trial_balance", {"legal_entity_id": ID, "as_of_date": "OPENING_DATE"})`
   - Total debits MUST equal total credits
   - Each account balance should match the source document
   - The day before OPENING_DATE shows none of the opening amounts

3. **If subledger items provided** (open items are dated the opening date too):
   - AR aging: `generate_report("ar_aging", {"legal_entity_id": ID, "as_of_date": "OPENING_DATE"})` — each invoice visible
   - AP aging: `generate_report("ap_aging", {"legal_entity_id": ID, "as_of_date": "OPENING_DATE"})` — each bill visible
   - Fixed assets: `query("fixed_asset", filters={"legal_entity_id": ID})` — each asset visible

4. **Bank balances**: Compare system bank account balance on the opening date vs actual bank balance at cutoff

## Common Issues

| Issue | Cause | Fix |
|-------|-------|-----|
| Debits ≠ credits | Missing accounts or wrong amounts | Review mapping, add missing lines |
| Account not found | Account number doesn't exist in CoA | Create the account or fix the number |
| Balancing amount larger than rounding | Lines missing or mis-mapped, or a year's result not captured | Explain it before posting: find the missing or mis-mapped lines, and if a year's result is the cause, go to "At a fiscal-year boundary" (or ask, for a mid-year cutoff). Never let the balancing account absorb it silently |
| Small rounding difference | Currency conversion or decimal rounding | Normal — balancing account handles this (typically < 1.00) |
| Negative bank balance | More outflows than inflows recorded | Check if opening balance is correct |
| Vendor/customer not found | Master data not imported | Import vendors/customers first, then retry |
