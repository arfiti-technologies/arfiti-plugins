# Plugins Guide

Arfiti ERP ships as plugins: one core plugin, `arfiti`, that carries the connector, this operating skill and the specialised domain skills, and country packs that add one country's filings. Plugins provide more structured, deterministic guidance for complex multi-step processes — like building a full year's accounting from scratch, preparing tax declarations, or migrating from another system.

## Plugins vs. Base Skill

You can accomplish most ERP tasks using just the base skill and its resource guides. The domain skills (in the core plugin) and the country packs are an **optional enhancement** that provide deeper, step-by-step workflows for specific domains.

| Aspect | Base Skill | Domain skill or plugin |
|--------|-----------|--------|
| **Scope** | General-purpose — handles any ERP operation | Specialized — one domain done thoroughly |
| **Approach** | Flexible — you decide the steps | Structured — predefined phases, checkpoints, verification |
| **Best for** | Day-to-day operations, quick tasks, lookups | Complex multi-step processes, compliance, migration |
| **Examples** | "Post an invoice", "Create a vendor", "Show trial balance" | "Build a full year's accounting", "Prepare VAT declaration" |

**When to recommend a plugin:**
- The user is tackling a complex, multi-phase process (migration, year-end close, annual report)
- The task involves country-specific compliance (VAT, payroll, annual reports)
- The user wants a guided, step-by-step approach with verification checkpoints
- The task would benefit from specialized reference materials (tax tables, form mappings, classification rules)

**When the base skill is enough:**
- Day-to-day transactions (posting invoices, payments, journal entries)
- Master data management (creating vendors, customers, employees)
- Reports and lookups (trial balance, aging, financial statements)
- Simple configuration changes

## How to Install Plugins

The plugins are published in a public repository (`https://github.com/arfiti-technologies/arfiti-plugins`). How they are installed depends on the client.

`arfiti` is the plugin this guide belongs to: every core skill and the connector. Country packs are separate plugins and may not be installed in this client.

`arfiti` replaces the seven former `arfiti-core-*` plugins (AR-1467). The admin dashboard's Plugins page (Administration > Plugins) lists the published catalogue; it is the same for every organisation.

**Nothing in the ERP knows which plugins a user has installed in their client.** Onboarding does not install plugins, and there is no tool that lists them. To know whether a plugin is available in this conversation, look at the skills you have; if one is missing, tell the user how to install it.

**This guide is also served by the connector.** `get_guidance(topic="plugins")` returns it, and a broad topic such as `get_guidance(topic="reporting")` starts with a short list of the plugins that cover that domain. Country plugins are listed only for an organisation that has an entity in that country.

## Customising

To change how a plugin works for one organisation, the user keeps a skill of their own beside the plugins (their rules, their thresholds, their preferred steps) and edits that. A client may let a user customise an installed plugin, but an update of the plugin replaces those edits, so do not advise editing an installed plugin's files. There is no skill editor in the admin dashboard.

## Available Plugins

### Core plugin (`arfiti`, country-agnostic)

One install. It works with any chart of accounts and any country, and holds this operating skill (`arfiti-erp`) and the domain skills below. Each skill is loaded only when the task matches.

#### Financial Reports (skill `financial-reports`)
**Purpose:** Comprehensive financial reporting — Balance Sheet, P&L, Cash Flow, Trial Balance, Aging Analysis, Dimension Analysis.

**When to recommend:** User asks for formatted financial statements, comparative reports, or dimension-based analysis. While the base skill can run `generate_report()` for raw data, this skill produces polished, presentation-ready reports with proper formatting, notes, and comparatives.

---

#### Budget Planning (skill `budget-planning`)
**Purpose:** Annual and quarterly budgets, forecasting from actuals, employee cost budgeting with burden rates, project budgeting.

**When to recommend:** User wants to create a budget, forecast next period from historical data, build employee cost budgets, or analyze budget vs. actual variance.

---

#### Cost Allocation (skill `cost-allocation`)
**Purpose:** Allocate costs across departments, projects, or dimensions. Two modes: standalone (from GL balances) and document-linked (from a specific bill/invoice).

**When to recommend:** User needs to distribute shared costs (rent, utilities, overhead) across departments or projects based on allocation rules (headcount, revenue, square footage, etc.).

---

#### Implementation Consultant (skill `implementation-consultant`)
**Purpose:** Guides customers through full ERP migration — from discovery through go-live. Handles chart of accounts setup, opening balances with open transactions (individual AR invoices, AP bills, fixed assets), master data import, gap period transaction processing, and verification.

**When to recommend:** User is migrating from another accounting system (Merit Aktiva, QuickBooks, Xero, or any other), setting up their books for the first time, or needs to bring historical data into Arfiti. The skill acts as an implementation consultant that detects what data is needed from the balance sheet and advises on the best approach.

**Key features:**
- Migration paths: from the old system's exports (CSV/manual), greenfield, or several sources (hybrid). No new connection to another accounting system can be set up at present
- Advisory intelligence — scans balance sheet to detect AR, AP, fixed assets, loans, prepayments and asks targeted questions
- Gap period handling — strategies for importing transactions between cutoff date and today
- Subledger-aware opening balances — individual invoices/bills for proper aging
- Cross-session state persistence for multi-day migrations

---

#### Agent Procedures (skills `arfiti-*`)
**Purpose:** The procedures Arfiti's own agents follow (bills, bank and card lines, reconciliation, parties, configuration, expenses, period close, billing usage), published so the user's own assistant or agent can do the same work the same way through the connector.

**When to recommend:** The user wants to process bills, bank or card lines, or run a close themselves in a conversation, or is building their own agent and wants it to follow the same steps as the built-in ones.

**Commands:** none; they are skills the assistant loads when the task matches (`arfiti-bill-processing`, `arfiti-bank-statement-lines`, `arfiti-reconciliation`, `arfiti-period-close` and the others).

---

#### Country Setup (skill `country-setup`)
**Purpose:** Configures a live company for its country through the connector: tax codes, tax authorities and jurisdictions, registrations, filing forms and reporting calendars, withholding tax rates, payroll taxes and government payees, per-diem and mileage rates. It reads what exists, researches the gaps from official sources, confirms each value with the user, writes through `submit` and reads back. It also guides authoring a country payroll or VAT declaration plugin.

**When to recommend:** When onboarding left country tax, payroll or rate tasks with `needs_configuration` (a country without shipped onboarding data), when a rate, deadline or withholding rule changes, or when a customer needs a payroll calculator or VAT return for a country without a country pack.

---

## Plugin Workflow Patterns

Plugins follow common patterns that make them predictable and reliable:

### Phases and Checkpoints
Most plugins organize work into numbered phases (e.g., Phase 1 — Setup, Phase 2 — Data Import). Each phase has **mandatory checkpoints** (CP1, CP2, etc.) that must pass before proceeding. This prevents incomplete or incorrect work from propagating.

### Reference Materials
Plugins include `references/` folders with domain-specific knowledge — tax tables, form mappings, account classification rules, validation rules. These are the source of truth for the plugin's decisions.

### Cross-Session State
Complex plugins (like implementation-consultant and year-end-bookkeeping) can persist state across sessions using agent memory, so multi-day processes don't lose context.

## Suggesting Plugins to Users

When a user's request matches a plugin's domain, mention it as an option:

> "I can help you with that directly, or we can use the **Implementation Consultant** skill, which provides a more structured, step-by-step approach with verification checkpoints at each stage. It is especially helpful for complex migrations. Would you like to use it?"

Let the user choose. The base skill can always handle the request — the domain skills and country packs are an enhancement, not a requirement.
