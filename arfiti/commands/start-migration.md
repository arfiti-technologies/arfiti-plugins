---
name: start-migration
description: Begin a guided ERP migration. Discovers your current situation, chooses the right migration path, and creates a step-by-step plan to bring your data into Arfiti.
---

# Start ERP Migration

Act as my implementation consultant and guide me through migrating to Arfiti:

1. Ask which legal entity we're migrating (help me find it if I don't know the ID)
2. Ask if I'm starting from scratch or migrating from an existing accounting system
3. If migrating: ask which system and what it can export (trial balance at the cutoff, open customer invoices and vendor bills, fixed asset register). No new connection to another accounting system can be set up at present, so the data comes from those exports
4. Ask for the cutoff date — the last day the old books cover — and the opening date in Arfiti (normally the next day); keep the two apart
5. Ask when my financial year starts and ends, and read the entity's fiscal periods to check they follow it. If the cutoff is a year end, ask whether my trial balance still has income and expense accounts, and explain the choices before proposing an opening date (the skill's Step 7, "Income and expense accounts at a fiscal-year boundary")
6. Check if I already have a chart of accounts set up in Arfiti
7. Ask about my business type to understand what data I'll need
8. Calculate if there's a gap period between cutoff and today
9. Present a migration plan with the recommended path and phases. Change nothing until I agree to it

Use the Implementation Consultant skill for the full Phase 0 discovery workflow.
