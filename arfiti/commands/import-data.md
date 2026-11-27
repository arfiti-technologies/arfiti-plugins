---
name: import-data
description: Import a specific type of data into Arfiti. Provides format guidance and walks through the import process for vendors, customers, items, employees, transactions, or opening balances.
---

# Import Data

Help me import data into Arfiti:

1. Ask which legal entity we're importing into
2. Ask what type of data to import (vendors, customers, items, employees, transactions, opening balances, fixed assets, dimensions, or accounts)
3. Show the required and optional fields for that import type using `get_onboarding(action="get_support", support_type="import_<type>")`
   - **Opening balances:** before asking for data, follow the Implementation Consultant skill's Phase 0 questions and Step 7 checks: my financial year (read the entity's fiscal periods), the cutoff (as-of) date and the opening date kept apart, existing opening entries in any period, and which equity account absorbs the difference. If the cutoff is a year end and my trial balance still has income and expense accounts, explain the choices (a closed trial balance first; otherwise the old year's last day, with its limits) and what each does to the reports, then let me choose. Never post an opening entry before I agree to its exact date
4. Ask me to paste or upload the data
5. Validate with a dry run first: `manage_imports(action="<type>", records=[...], validate_only=true)` (opening balances take `balances=[...]` and `fiscal_period_name`, not `records`; the preview states `posting_date`)
6. Show validation results — fix any errors
7. Run the actual import
8. If async (more than 50 records, or a CSV file), monitor progress with `get_imports(action="status", import_id=...)`
   If the answer is `pending_approval`, nothing is imported yet: the organisation's import review holds it (by default, an import carrying vendor or employee bank details waits for an owner or admin). Say who decides it and where (their tasks in the dashboard); do not resend it or drop the bank columns to get past the review unless the user asks for that
9. Show final results: imported, updated, skipped, errors. A `completed` import can still have refused rows: show `error_count` and the errors, and say that the full row list is on the import's page in the dashboard. When every row failed, the answer says `posting_unknown` and gives an `import_id`: read `get_imports(action="status", import_id=...)` for the row errors; when it shows nothing imported or updated, fix the cause and run the import again with a new `idempotency_key`

Use the Implementation Consultant skill for data quality rules and validation guidance.
