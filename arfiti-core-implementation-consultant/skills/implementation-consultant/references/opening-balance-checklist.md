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
- Cutoff on a fiscal year's last day with income or expense accounts still in the trial balance: first ask for a closed trial balance (balance-sheet accounts only, the year's result already in retained earnings). If the customer cannot provide one, propose dating the opening entry on the **last day of the old year** (`opening_date`), so those lines roll into the prior-year result, state that exact date, and get the customer's agreement before posting. This is the one exception to "balances as at D open on D+1" (Andrew, 24 Nov 2026, AR-1456). It is guidance for the assistant, not a rule the server enforces. (Dated the new year's first day, those lines would fall in the new year, whose income statement is then marked incomplete.) This needs `opening_balances` (or the CSV import): `opening_balances_with_subledger` takes no `opening_date` and refuses one, so with open items ask for the closed trial balance. The old year's last period must be open: a closed or locked period is refused before anything is written; it is reopened through the period operations, or the closed trial balance is used.

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
- **Connector sync** (automated for Path A)

## Account Mapping

For each line in the source document:
1. Match to an account in the imported CoA by account number or name
2. Determine if it's a debit or credit balance:
   - `account_type` asset: normally debit
   - `account_type` liability: normally credit
   - `account_type` equity: normally credit
   - `account_type` revenue, expense, cogs: NOT included in a balance-sheet opening balance
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
| Account Type | Range | Individual Records Needed |
|-------------|-------|--------------------------|
| Accounts Receivable | 1200-1299 | Open customer invoices |
| Accounts Payable | 2100-2199 | Open vendor bills |
| Fixed Assets | 1500-1599 (cost), 1600-1699 (depreciation) | Asset register entries |

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
| Large retained earnings difference | Prior year P&L not captured | Expected — retained earnings absorbs historical profits |
| Small rounding difference | Currency conversion or decimal rounding | Normal — balancing account handles this (typically < 1.00) |
| Negative bank balance | More outflows than inflows recorded | Check if opening balance is correct |
| Vendor/customer not found | Master data not imported | Import vendors/customers first, then retry |
