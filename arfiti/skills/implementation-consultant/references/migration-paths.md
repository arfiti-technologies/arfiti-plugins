# Migration Path Decision Tree

Use this to determine the right migration path during Phase 0 discovery.

## Decision Flow

```
Q: Is the user starting from scratch (no prior system)?
├── Yes → Path C (Greenfield)
└── No → Q: Which accounting system?
    ├── Any accounting system (Merit Aktiva, QuickBooks Online, SmartAccounts, Xero, SAP, custom, spreadsheets) → Path B (CSV/Manual)
    └── Several systems or sources → Path D (Hybrid: several exports)
```

## Path Comparison

| Aspect | Path B (CSV/Manual) | Path C (Greenfield) | Path D (Hybrid) |
|--------|--------------------|--------------------|----------------|
| **Automation** | Low — user prepares and uploads exports | Minimal — interactive creation | Mixed |
| **User effort** | Prepare exports, map fields, fix errors | Answer questions, create records | Several sources to reconcile |
| **Data quality** | Varies — depends on export quality | N/A | Varies |
| **Best for** | Any company moving from another system | New companies | Data spread over several systems |

## Path A — Connector Migration (not offered)

No new connection to another accounting system can be set up at present (an organisation that already has one keeps syncing it from the dashboard's connectors page), so every migration brings its data in from the old system's exports (Path B). Do not offer to set up a sync or a connector for a migration. Bank feeds are a separate, optional connector and are unaffected.

## Path B — CSV/Manual Migration

**Import sequence** (order matters — later imports reference earlier ones):
1. Accounts (chart of accounts)
2. Dimension types, then dimension values
3. Customers
4. Vendors
5. Items
6. Employees
7. Fixed assets
8. Opening balances (with or without subledger)
9. Transactions (gap period)

**For each import type, get format guidance:**
```
get_onboarding(action="get_support", support_type="import_<type>")
```

**Common source formats and how to handle:**
- **Excel/CSV from old system** → Map columns to Arfiti fields, import directly
- **PDF reports** → Extract data (Claude can read PDFs), structure into records
- **Pasted text/tables** → Parse and structure into records
- **Manual entry** → Use `submit()` for individual records or small batches

## Path C — Greenfield

**Minimal setup needed:**
1. Chart of accounts (use IFRS or US GAAP template)
2. Bank accounts
3. A few initial vendors/customers as needed
4. No opening balance (or just initial capital contribution)

**Recommended sequence:**
1. Set up CoA template
2. Create bank accounts
3. Start transacting — create vendors/customers as you go
4. Set up bank feeds for automatic reconciliation

## Path D — Hybrid

**When to use:**
- Some data in one system, other data in spreadsheets
- Migrating from multiple systems simultaneously

**Approach:**
1. Import each source's export in the Path B order
2. Agree with the person which source is authoritative where they overlap
3. One opening balance for the entity, reconciled to every source


### Bank/card purchase replay controls

Preserve provider event rows and their purchase membership. Replaying a charge and refund must not duplicate cash journals, create a second bill, or restart historical receipt reminders. Use the shared purchase identity decision; conflicting references, incomplete FX basis and disputed evidence require finance review. Keep original checking-account opening/closing balances and include explicitly routed card movements in balance and GL coverage checks before closing a period.

A bank/card reset is a separately authorized operation. Prepare scoped source IDs, transaction deletion dependencies, allocations and reclass/variance journals, retained bills/attachments, queued work and a tested restoration procedure before requesting authorization. Use `transaction.delete` with its dependents policy and internal force voucher when permitted; never improvise cascades. Re-link retained evidence through the supported purchase workflow. The August investigation is not general permission to delete another client's data.

Migration acceptance requires exact source coverage, one financial effect per booked movement, AP/subledger agreement, stable replay and one current documentation obligation per purchase. A balanced adjusting journal cannot explain missing provider movements. Keep purchase matching and reminder delivery disabled until the scoped validation and delivery cutoff are approved.
