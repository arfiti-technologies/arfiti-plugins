# Arfiti

![Arfiti](assets/icon.png)

The Arfiti finance system inside Claude, in one plugin. It connects Claude to your Arfiti
organisation through the Arfiti MCP connector and teaches it how to use it: the `submit` write
gateway and its approval lanes; the `query`, `get_entity` and `generate_report` read tools;
and the paired `get_*` / `manage_*` tools for submissions, workflow configuration, agents,
connectors, imports, onboarding and organisation settings. It carries the procedures Arfiti's
own agents follow (bills, bank and card lines, reconciliation, parties, configuration,
expenses, period close, billing usage), the standard financial reports, budgets and forecasts,
cost allocation, migration from another system, and country setup.

Country-specific filings come in separate country packs (for Estonia,
`arfiti-ee`). Accounting policy that is yours (a different allocation or budgeting
method, a firm's own procedure) belongs in a plugin or skill of your own beside this one: an
update replaces edits made to an installed plugin.

## Requirements

- An Arfiti organisation and a user who can sign in to it.
- This plugin's `.mcp.json` connects the **Arfiti** connector (`https://mcp.arfiti.com/streamable/mcp`). If the
  connector is already added in your client, both point at the same server and show one set
  of tools.

## Install

In Claude Code:

```
/plugin install arfiti --marketplace arfiti-technologies/arfiti-plugins
```

or `/plugin marketplace add arfiti-technologies/arfiti-plugins`, then `/plugin install arfiti@arfiti-plugins`. In
Claude (web, Desktop, Cowork): Customize > Plugins > Add > Add marketplace, enter
`arfiti-technologies/arfiti-plugins`, then install **arfiti**. Commands are called with the plugin name,
for example `/arfiti:balance-sheet`.

It replaces the seven `arfiti-core-*` plugins (November 2026).

## Skills

| Skill | What it does |
| --- | --- |
| `arfiti-account-choice` | Choose the ledger account for one purchase in Arfiti - a card charge the bank agent posts or a line of a supplier bill - from the records, in a fixed order of authority (client rule, vendor default, vendor history, vendor notes, the chart of accounts), and say which evidence decided it. Use whenever a posting needs an expense, cost or asset account that the caller's skill does not already fix. |
| `arfiti-bank-statement-lines` | Settle one bank account's (or card programme's) unreconciled statement lines in Arfiti through the MCP tools - confirm a payment-batch line, post a bank entry or payment through submit anchored to the statement line and match it, or exclude a duplicate - in a fixed order of checks, never breaking a tie with a date or an amount, and reading the line back after every write. Use for every bank session. |
| `arfiti-bill-processing` | Process one incoming vendor bill in Arfiti end to end through the MCP tools only - read the document, find or delegate the vendor, choose accounts and tax codes from vendor defaults, history and the organisation's rules, check for a duplicate, validate, post through submit, attach the source document, and report. Use for every bill session. |
| `arfiti-billing-usage-answers` | Turn a person's answer to a "provide usage data" task into recorded contract usage and a billing run for exactly those contracts, through the Arfiti MCP tools - read the task and the answer, map each figure to a metered contract line, record it with submit(object_type="contract_usage", operation="record"), then submit(object_type="billing_run", operation="execute") for those contracts. Never invents a quantity. Use when a usage-data task has been answered. |
| `arfiti-configuration` | Resolve one accounting-configuration problem in Arfiti through the MCP tools - accounts, posting profiles, transaction-type posting links, fiscal periods, payment terms, tax codes, a confirmed entity time zone - by finding what exists, choosing the smallest change that only affects future postings, validating, submitting, and reading back. Refuses on its own to change anything that would reclassify or re-report posted history. Use for every configuration task, whether a session's own or a brief from another agent. |
| `arfiti-erp` | Operate the Arfiti ERP through its MCP connector — post transactions, manage customers, vendors, employees, banking, payroll, expenses, fixed assets, budgets, projects, tax and period close. Use for any Arfiti ERP question or operation. |
| `arfiti-expense-check` | Check a submitted expense claim in Arfiti against the company's own written rules - gather the evidence for every line (rate tables, meal deductions, the employee's other claims and per diems for the same days, card charges, duplicates, missing receipts, the employee's own history), weigh it against each rule the company wrote, and either report nothing or raise one plain-language task for the employee that names the line, the rule and what to do. Holds no company or country policy, no amounts and no thresholds of its own. Never approves, rejects, holds, modifies or pays a claim. |
| `arfiti-expense-claim` | Build an employee's expense claim in Arfiti through the MCP tools - sort each receipt (company card, supplier invoice, paid by the employee, not usable), add reimbursement, mileage and per-diem lines with amounts from the server's rate tables, check for duplicates and per-diem overlaps, write a draft report and read it back, and submit it only when the person it belongs to says so. Used by an employee's own Claude in Cowork and by the expense agent. Never approves, posts or pays. |
| `arfiti-expense-processing` | The expense agent's own procedure in Arfiti. Mode receipt - a receipt arrives with no claim around it (expenses or receipts mailbox, app upload) - file it on its company card charge, list a supplier invoice for the bill agent, or start a draft claim for the employee who paid and ask them by task to check and submit it. Mode check - check each submitted claim against the company's own written rules and raise one plain-language task for the employee when something is against them. Builds claims with arfiti-expense-claim and checks them with arfiti-expense-check. Never submits a claim for an employee unless a company rule says so; never approves, rejects, posts or pays. Use for every expense agent session. |
| `arfiti-master-data` | Find or create one vendor (or customer) in Arfiti through the MCP tools - multi-pass duplicate search, employee cross-check, registration and VAT number, a public-register lookup when the organisation's rules ask for it, tax code and terms from the organisation's own codes, bank details through the vendor workflow - and return a result block to the agent that asked. Use when briefed to resolve a party. |
| `arfiti-period-close` | Run the month-end close for one legal entity and fiscal period in Arfiti through the MCP tools only - collect the evidence for each standard check, report every finding with its evidence, decide which findings block from the client's own close rules (never from this skill), fix what ordinary operations or the helpers can fix, raise plain-language tasks for the rest, and close the period through submit(object_type="fiscal_period", operation="close") when asked and nothing the client calls blocking is open. Never forces, never reopens, never locks. |
| `arfiti-reconciliation` | Reconcile one legal entity's open payments (bank payments, card expenses, refunds) against its open bills and invoices in Arfiti through the MCP tools. Reads every document and its card purchase, uses history, dates, references and original-currency amounts as evidence, matches one-to-one, many-to-one and one-to-many, applies each match through submit with a row-level read-back, and turns every item it cannot settle into a person task. Use for every reconciliation session. |
| `arfiti-vendor-deduplication` | Sweep one organisation's vendors for duplicates through the Arfiti MCP tools, decide which pairs are certainly the same party from hard evidence (tax or registration number, bank account, history), and propose each merge through submit(object_type="vendor", operation="merge"), which the organisation's workflow holds for approval; never merge on a name alone. Use for a scheduled or requested duplicate sweep. |
| `arfiti-working-with-people` | How an Arfiti agent treats a person's answer to a task it raised, and how it keeps what the person told it - act on the answer, never ask the same thing again or look for a second opinion, and turn a standing instruction into a record update or a proposed rule so the same question is not asked next time. Use whenever a task you raised is answered, and before raising a task. |
| `budget-planning` | Builds budgets from scratch, copies forward with adjustments, forecasts from actuals, plans employee costs with burden rates, and creates project budgets. Reads GL data, employees, projects, and existing budgets to calculate amounts and submits via the ERP workflow system. |
| `cost-allocation` | Allocates costs across departments, projects, or dimensions. Supports two modes — standalone (from GL balances) and document-linked (from a specific transaction like an AP invoice). Reads data, calculates target splits using any method (fixed %, proportional, by headcount, custom formula), and submits allocation runs to the ERP with full validation. |
| `country-setup` | Configures a live Arfiti company for its country — tax codes, tax authorities and jurisdictions, registrations, filing forms and calendars, withholding rates, payroll taxes and expense rates — by reading what the company already has, researching the gaps from official sources, confirming each value with the customer, writing it through the Arfiti submit gateway and reading it back. Also guides the customer in authoring their own country plugins (payroll calculator, VAT declaration). Use for "set up Germany" (any country), "configure tax for my entity", "add withholding rates", "fix our filing calendar", "author a payroll plugin for Spain". |
| `financial-reports` | Present standard financial reports from Arfiti's server reports — Balance Sheet, Profit & Loss, Cash Flow Statement, Trial Balance, AR/AP Aging, P&L by dimension and a Financial Summary. The server classifies, totals and reconciles; this skill presents those results without rebuilding them. |
| `implementation-consultant` | Guides customers through full ERP migration — from discovery through go-live. Handles chart of accounts, opening balances with open transactions, master data, gap period transactions, and verification. Acts as a knowledgeable implementation partner that detects what data is needed and advises on the best migration strategy. |

## Commands

| Command | What it does |
| --- | --- |
| `/arfiti:aged-payables` | Present the server's AP aging with certification, overdue (1+ days) vendors, amounts coming due, credits and optional days payables outstanding over the real period. Uses format_aging.py. |
| `/arfiti:aged-receivables` | Present the server's AR aging with certification, overdue (1+ days) figures, credits, optional days sales outstanding over the real period, and labelled example follow-up. Uses format_aging.py. |
| `/arfiti:author-country-plugin` | Design your own country plugin — a payroll calculator or a VAT declaration — that works with your Arfiti company through the same connector |
| `/arfiti:balance-sheet` | Present the server's balance sheet with its reconciliation verdict, earnings bridge, optional comparison and labelled liquidity ratios. Uses format_balance_sheet.py. |
| `/arfiti:cash-flow` | Present the server's cash flow statement with its opening-to-closing cash bridge and reconciliation verdict. No formatter; the server's rows and totals are shown as returned. |
| `/arfiti:close-migration` | Finalize your ERP migration. Runs final verification, presents a migration summary, and advises on next steps for going live with Arfiti. |
| `/arfiti:create-budget` | Build a new budget from scratch, copy forward from prior year, or create from template. Supports monthly/quarterly/annual granularity. |
| `/arfiti:dimension-analysis` | Present a P&L by department, project or other dimension: one server income statement per dimension value, an untagged column and the entity total, without adding the columns up. Uses format_dimension_analysis.py. |
| `/arfiti:financial-summary` | Present a one-page summary from the server's income statement, balance sheet and cash flow for one period, with labelled ratios and period-length days outstanding. Uses format_financial_summary.py. |
| `/arfiti:forecast-budget` | Create a mid-year forecast by blending YTD actuals with projected amounts for remaining months. |
| `/arfiti:import-data` | Import a specific type of data into Arfiti. Provides format guidance and walks through the import process for vendors, customers, items, employees, transactions, or opening balances. |
| `/arfiti:migration-status` | Check the current progress of your ERP migration across all phases. Shows what's done, what's next, and any blockers. |
| `/arfiti:preview-allocation` | Calculate and preview an allocation without submitting it. Supports standalone and document-linked modes. |
| `/arfiti:preview-budget` | Calculate and preview budget amounts without submitting. Useful for what-if scenarios and planning discussions. |
| `/arfiti:profit-and-loss` | Present the server's income statement with its subtype sections, server totals, optional comparison and labelled margins. Uses format_income_statement.py. |
| `/arfiti:review-variance` | Analyze budget vs actual variances with drill-down, interpretation guidance, and corrective action recommendations. |
| `/arfiti:run-allocation` | Create and execute a cost allocation from start to finish. Supports standalone (from GL balances) and document-linked (from a specific bill/invoice). |
| `/arfiti:set-up-country` | Configure your live company for its country — tax codes, authorities, registrations, filing calendar, withholding, payroll taxes, expense rates — through the Arfiti connector, with sources, your confirmation and a read-back |
| `/arfiti:start-migration` | Begin a guided ERP migration. Discovers your current situation, chooses the right migration path, and creates a step-by-step plan to bring your data into Arfiti. |
| `/arfiti:trial-balance` | Present the server's trial balance with its full-selection totals and reconciliation verdict, and point out balances that are unusual for their account type. |
| `/arfiti:verify-migration` | Run the full verification suite to confirm your migration is correct. Checks trial balance, balance sheet, aging reports, bank balances, and fixed asset reconciliation. |

## Subagents

| Subagent | What it does |
| --- | --- |
| `arfiti:balance-sheet-analyzer` | Analyzes a balance sheet or trial balance document, extracts structured account lines, maps them to the entity's chart of accounts, and runs advisory intelligence to detect what additional data is needed for migration. |
| `arfiti:payroll-specialist` | Researches a country's payroll taxes and contributions, their brackets and ceilings, the authorities an employer pays, and statutory per-diem and mileage limits from official sources, and returns dated, sourced findings for the customer to confirm. Writes nothing. Use during country setup for a live Arfiti company. |
| `arfiti:tax-researcher` | Researches a country's indirect taxes (VAT/GST/sales tax), tax authorities and jurisdictions, filing forms and calendars, and withholding tax on payments from official sources, and returns dated, sourced findings for the customer to confirm. Writes nothing. Use during country setup for a live Arfiti company. |

## What it runs and sends

All data goes to the Arfiti MCP server over the authenticated connector. Your sign-in decides
the organisation and what you may do; every write goes through `submit`, under your
organisation's validation, workflows and approvals. Accounts, tax codes, parties, rules and
documents are read live through the connector; no organisation's data ships with the plugin.
Installing the plugin changes nothing in your organisation. There are no hooks and no local
servers.

- **Scripts.** The report commands run the Python 3 formatters in `scripts/` (standard
  library only). Each reads the JSON file you pass with `--input` (a `generate_report` result
  requested with `report_contract: 1`, saved unchanged), refuses anything else, and writes a
  Markdown report to the path you pass with `--output`. `report_v1.py` is a helper they import;
  it reads `ratio_policy.json`, which is example presentation policy (which subtypes count as
  current, cash, receivables, payables and inventory; example ratio bands and follow-up
  wording) for your firm to edit. `scripts/examples/` holds sample inputs that are never
  executed. No script opens a network connection or starts another process.
- **Local files.** The report commands save the `generate_report` result (your
  organisation's figures) as a JSON file and write the Markdown report to the paths the
  command names (under `/tmp` by default) on the machine Claude runs on. The migration
  commands and the `balance-sheet-analyzer` subagent read the balance sheet, trial balance or
  import files you give them (the subagents are declared with `Read`, `Glob` and `Grep`), and
  what you confirm is written to your Arfiti organisation through the connector.
- **Web access.** Country setup researches tax and payroll rules on the public web: the
  `tax-researcher` and `payroll-specialist` subagents (declared with `WebSearch` and
  `WebFetch`), or Claude itself with web search where subagents are not available. Those
  searches and page fetches carry the country, the facts about your entity you give for the
  research (for example whether it is VAT registered) and the search terms written; they go to
  search engines and public sites such as tax-authority and government pages. The
  `arfiti-master-data` skill may look a vendor or customer up in a public company register
  listed in its `REGISTERS.md`, sending that party's name or registration number from your
  records to that register's site, and to no other site. The `balance-sheet-analyzer`
  subagent (migration) is declared with `WebFetch` and fetches a public page only if you point
  it at one. Claude asks before web tools run unless you allowed them.

## Generated parts

`skills/arfiti-erp/` is generated from `mcp-server/skill-templates/base` in the Arfiti monorepo
by `plugins/scripts/build_core_plugin.py`; the `arfiti-*` procedure skills are generated from
the agents' own skills by `managed-agents/scripts/build_skill_plugin.py --publish`. This README
is generated too.

## Support

support@arfiti.com · Documentation: https://arfiti.com/plugins/arfiti ·
Privacy: https://arfiti.com/legal/privacy · Terms: https://arfiti.com/legal/terms
