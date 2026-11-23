# Organization Onboarding Procedure

Step-by-step procedure for setting up a new organization in Arfiti. Follow this exactly.

---

## When This Applies

Use this procedure when ANY of these are true:
- User says "set up my organization", "onboard my company", "initialize", etc.
- `get_onboarding(action="check_status")` returns `needs_onboarding: true`
- Organization has no legal entities yet
- Onboarding checklist shows incomplete tasks

---


### Authority for organization setup

Organization-wide setup requires **current owner or admin membership** in the
connected organization and **access to all entities**. The backend reads live
membership; a Controller, Viewer, role named Admin, stale owner token, or
`admin:write`/`config:write` grant alone does not qualify. Agent credentials cannot
perform these user administration operations.

This applies to `manage_onboarding` actions `start`, `run_wave`, `update_task`,
`reset`, `add_entity`, `initialize_entity`, and `load_demo_data`, plus template
repair and `legal_entity.create` / `legal_entity.rerun_onboarding_task` workflows.
They can seed shared accounting configuration, workflow/agent definitions and
credentials, so entity-limited administrators must ask an unrestricted owner or
admin to perform them. Ordinary entity-scoped accounting workflows are unchanged.

Onboarding status/checklist/summary and support actions retain
their existing access rules. New organization owners can still run first-time
onboarding before the organization has any entities. Explicit organization IDs
must match the connected organization; initialization/copy targets must belong
to it. Omitting `organization_id` in the MCP initialization/demo gateway uses
the connected organization. Switching the Admin browser login does not change
the identity of an existing MCP connection.

A permission refusal must be resolved with the correct owner/admin connection,
not by retrying through another setup tool or resetting the checklist. After a
legitimate setup failure, inspect the checklist and retry only the failed task.

## CRITICAL RULES

1. **ALWAYS use `manage_onboarding(action="start")` then `manage_onboarding(action="run_wave")`** for first-time setup
2. **Do not create the first entity manually.** The legal entity is created automatically by the first onboarding wave (`create_organization` task).
3. **NEVER call `manage_onboarding(action="initialize_entity")` before `start`** — `initialize_entity` requires an existing `legal_entity_id` and will fail with a fiscal_periods FK error if the entity doesn't exist yet.
4. **NEVER use `manage_onboarding(action="add_entity")`** for the first entity — that action is ONLY for adding a 2nd+ entity to an already-onboarded organization
5. **Run waves while runnable tasks remain.** Completion requires every task to be completed or explicitly skipped. Failed tasks remain open: inspect the error, resolve it, use `update_task` to reset that task to `pending`, then retry; never reset populated company data to recover a failed task.
6. The wave runner creates the legal entity, the chart of accounts and posting profiles (from a template chart only), tax codes, number series, agents, payroll and dimension setup. It installs no plugins and cannot see which ones a client has: the person installs them (Step 6).
7. **Never assume a material choice from silence.** `start` lists every one it was not given in `material_choices_not_provided`; ask those before the first wave.

---

## Step-by-Step

### Step 1: Check Current Status

```
get_onboarding(action="check_status")
```

- If `needs_onboarding` is `false` → org is already set up. Ask what the user needs help with.
- If `needs_onboarding` is `true` → continue to Step 2.

### Step 2: Collect Company Details

Ask the user every row; each one changes accounting outcomes:

| Field | Ask | Example | Used by `start` |
|-------|-----|---------|-----------------|
| Country | Yes | EE, US, GB, DE (2-letter ISO) | `country_code` |
| Chart of accounts | Yes | IFRS template, US GAAP template, or their own chart | `accounting_standard` |
| Tax jurisdiction | Yes | EU, US, UK | `tax_jurisdiction` |
| Fiscal year start month | Yes | 1 = January, 4 = April | `fiscal_year_start_month` |
| Registered for VAT? | Yes (same as `add_entity`) | true/false, and the number | `is_vat_registered` (VAT only; a US sales-tax registration is recorded separately, see below) |
| Reporting timezone | Yes | America/New_York | not a `start` parameter: set once the entity exists |
| New business, or moving from another system? | Yes | "moving from QuickBooks" | not a `start` parameter: decides the migration offer in Step 6 (do not ask it again there) |

**Moving from another system, or keeping a chart they already have?** Offer `accounting_standard="custom"` before calling `start`, and say why: a template chart, once created, is shared master data that an import adds to but does not replace, so their own chart could not take its place later. See [Custom chart of accounts](#custom-chart-of-accounts).

`start` applies a default for anything omitted so the checklist can be saved, and lists it in `material_choices_not_provided` (omitted is "not provided"; `is_vat_registered=false` is an answer). Ask each listed choice, then, before running any wave, call `start` again with the same arguments plus the answers: that replaces the saved choices. Once the waves have created the entity, `start` without `legal_entity_id` is refused (`onboarding_already_started`): continue with `run_wave`, and change a choice through the operations (for example `tax_registration`, `legal_entity.update`). A VAT answer of yes creates a `vat` registration row with number `PENDING` when the waves create the legal entity (not for an existing `legal_entity_id`); with no answer none is created. Record the real number with `submit(object_type="tax_registration", operation="update", ...)`; the type cannot be changed, so a wrong one is deleted (`tax_registration.delete`) and created again. For an existing entity, or a US sales-tax registration (answer `is_vat_registered=false`), create it: `submit(object_type="tax_registration", operation="create", ...)` with `registration_type` `sales_tax` (fields: `get_submissions(action="schema", object_type="tax_registration", operation="create")`). The `create_legal_entity` result shows `is_vat_registered: null` with `vat_registration: not provided…` when nobody answered, and `false` only for an answer of no.

**Reporting timezone.** When the waves create the legal entity (`create_legal_entity` completed), it gets a default zone marked for review: the organisation's zone if set, else a listed country's zone, else `UTC` (any country not listed, the US included, gets `UTC`). Ask the person which zone their books use; do not just confirm the default. Then set it:
`submit(object_type="legal_entity", operation="update", data='{"legal_entity_id": 12, "reporting_timezone": "America/New_York"}')`. Until then reports carry `REPORTING_TIMEZONE_DEFAULTED`.

**Note on entity name/code/currency:** Wave 1 auto-derives these from the organization record and country_code. Entity name = org name, entity_code = country_code, currency = country-derived (EE→EUR, US→USD, GB→GBP). Collect these from the user only for confirmation/context — they are NOT passed to `start`.

### Step 3: Initialize Onboarding Checklist (creates the legal entity)

Do NOT create the legal entity first. The `start` action initializes the checklist; the first wave's `create_legal_entity` task auto-creates the legal entity from the organization record.

```
manage_onboarding(action="start",
    country_code="EE",
    accounting_standard="ifrs_standard",
    tax_jurisdiction="eu_vat",
    fiscal_year_start_month=1,
    is_vat_registered=true
)
```

**Parameters `start` actually accepts:** `country_code`, `accounting_standard`, `tax_jurisdiction`, `onboarding_path`, `fiscal_year_start_month`, `is_vat_registered`, `legal_entity_id` (optional — omit for first-time setup).

**Tax jurisdiction values:**
- Estonia/EU → `eu_vat`
- United States → `us_sales_tax`
- United Kingdom → `uk_vat`

**Accounting standard values** (any other value is refused and nothing is saved):
- `us_gaap_standard` (also `GAAP`): loads the US GAAP chart and its posting profiles.
- `ifrs_standard` (also `IFRS`, `LOCAL`): loads the IFRS chart and its posting profiles.
- `custom` (also `CUSTOM`): the person's own chart. No chart and no posting profiles are created; follow [Custom chart of accounts](#custom-chart-of-accounts). Offer it whenever the person already has a chart they want to keep.

**What Wave 1 uses for the legal entity (no way to override today):**
- `entity_name` ← `organizations.name` (the name collected during org signup)
- `entity_code` ← `country_code` (e.g., `EE`)
- `functional_currency` ← derived from country (EE → EUR, US → USD, GB → GBP, etc.)

If the user wants a different entity_name or entity_code (e.g., "AHG-EE" instead of "EE"), they must update the org name first or edit the entity after onboarding completes — do NOT pass `entity_name`/`entity_code`/`base_currency` to `start`; those parameters are ignored.

This creates ~34 onboarding tasks organized in dependency waves.

### Step 4: Run ALL Waves Until Complete

```
manage_onboarding(action="run_wave")
```

After each wave, check progress:

```
manage_onboarding(action="get_summary")
```

**Keep calling `run_wave` until `progress_pct` = 100.** Typical setup needs 3-5 waves.

A wave advances one legal entity's checklist. When more than one entity has open onboarding tasks, `run_wave` needs the entity, `manage_onboarding(action="run_wave", legal_entity_id=12)`; without it the call runs nothing and lists each entity with its open task count. Follow the call each answer's message names: when this entity has nothing runnable left, it names the other entity's call.

If a task fails, inspect and resolve its error, reset only that task to `pending` with `update_task`, then run another wave. Do not assume the failure is transient or repeatedly run a blocked wave.

### Step 5: Verify Setup

```
get_onboarding(action="check_status")
```

Should return `needs_onboarding: false` with complete `setup_info` including:
- Legal entity details
- Agent email addresses
- Enabled agents

### Step 6: Inform User About Next Steps

Tell the user:
1. What was set up and what was not, from the completion response's `setup_counts` and `not_set_up`. When `ready_to_post` is false (always for a custom chart until it is imported), say the books cannot post yet and why. Never list something with zero records as set up.
2. **Agent email addresses** — list ONLY the emails with autonomous agent processing:
   - `bills.{entity}.{org-slug}@mail.arfiti.com` → bill_processor (forward vendor bills here)
   - `receipts.{entity}.{org-slug}@mail.arfiti.com` → expense_processor (forward expense receipts here)

   Do NOT list `invoices.*` or `payments.*` in the wrap-up. They exist in the DB but are manual/outbound utility addresses (invoices.* is for sending customer invoices; payments.* is a manual inbox for remittance advices). Listing them as "agent emails" confuses users because there is no agent behind them.
3. **Offer, in this order, all optional** (none is needed to use the books):
   1. **Plugins.** Name the ones that fit (`arfiti-core-erp` first; the country pack, or `arfiti-core-country-setup` where none exists; domain plugins the person asked about) and give the install steps from `setup_info.plugins`. The person installs them; ask them to confirm. You cannot see what their client has installed, so never say a plugin is installed.
   2. **A project for this company**, where the client has projects, with `setup_info.claude_project_description` as its instructions. The project keeps the instructions and conversation files in the client; the books, documents and settings stay in Arfiti.
   3. **New business or moving from another system?** (Asked in Step 2; ask now only if it was not answered.) For a migration, offer the `arfiti-core-implementation-consultant` plugin (`/start-migration`). It needs the old system's name, the cutoff date, a trial balance at the cutoff, open customer and vendor invoices, and the fixed asset register if there is one.
4. **Other next steps** — choose from:
   - Import vendors, customers, and employees (via CSV or manual entry)
   - If migrating from a prior accounting system: import opening balances — see [Bulk Import: Opening Balance](../resources/bulk-import.md#opening-balance-import)
   - Set up payroll employees and compensation
   - Configure projects, dimensions, or budgets

   Do NOT suggest:
   - ❌ "Download the skill from the admin dashboard" — there is no skill package to download. The guide to the tools is the `arfiti-core-erp` plugin, and the completion response's `setup_info.plugins` names the marketplace (`arfiti-technologies/arfiti-plugins`) to install it and the country plugins from. Say that once, from the completion response; do not invent a download link.
   - ❌ "Add bank accounts (bank connectors available)" — don't push connectors unprompted during onboarding. Revolut Business is the bank connectivity, and it is set up from the admin dashboard's connector wizard (certificate + consent), not from chat. Only mention it if the user explicitly asks about bank integrations.

---

## Custom chart of accounts

For a company that keeps its own chart. Choose it **before** the waves: a template chart, once created, is shared master data that an import adds to but does not replace.

1. **Get the chart from the person** (an export from their old system, a file, or a list). Never invent account numbers or names.
2. **Start with `accounting_standard="custom"`** and run the waves. `create_coa` and `create_posting_profiles` end `skipped` with `needs_configuration: true`; nothing was created for them.
3. **Compare with what exists.** Other onboarding tasks seed a few accounts of their own (a US company gets payroll liability and expense accounts with template numbers). List them, `query("account", filters={"legal_entity_id": 12})`, and agree with the person how each one maps to their chart: an import skips an account number that already exists anywhere in the organisation (`on_duplicate="skip"`). Keep the seeded account under its number and use it in place of the person's equivalent, or rename it with `submit(object_type="account", operation="update", data=...)`; a per-entity number override does not free the number for the import.
4. **Import the chart.** Fields: `get_onboarding(action="get_support", support_type="import_accounts")`. Required per account: `account_number`, `account_name`, `account_type` (`asset`, `liability`, `equity`, `revenue`, `cogs`, `expense`), `normal_balance` (`debit`/`credit`). Set `account_subtype` on every account: reports, cash flow and the control-account checks read it. Dry run first, then import:
   `manage_imports(action="accounts", legal_entity_id=12, records=[...], validate_only=true)`, then the same call without `validate_only`. More than 50 records are processed asynchronously; follow the import with `get_imports(action="status", import_id=...)`.
5. **Control accounts.** The receivables and payables accounts carry `account_subtype` `accounts_receivable` / `accounts_payable` and `allow_manual_entries=false`; bank accounts carry `bank`; VAT accounts `vat_payable` / `vat_recoverable` (US sales tax: `sales_tax_payable`). Set these in the import records, or fix one with `submit(object_type="account", operation="update", data=...)`.
6. **Posting profiles.** Create one per transaction type the company uses, with the person's account numbers: `submit(object_type="posting_profile", operation="create", data='{"legal_entity_id": 12, "profile_name": "Customer receivables", "profile_type": "customer", "debit_account_number": "...", "credit_account_number": "...", "is_default": true, "transaction_type_code": "AR_INVOICE"}')`. Check fields with `get_submissions(action="schema", object_type="posting_profile", operation="create")`. The profile types and transaction types are in [Posting Profiles](../resources/posting-profiles-management.md).
7. **Tax accounts.** For each tax code: `submit(object_type="tax_code", operation="update", data='{"tax_code_id": ..., "sales_account_number": "...", "purchase_account_number": "..."}')`.
8. **Defaults that point at accounts.** Check fixed asset categories and expense items' default expense accounts against the imported chart (`query("item", ...)`); onboarding seeded them for a template chart.
9. **Verify.** Dry run a real first document the person has, `submit(object_type="transaction", operation="post", data=..., validate_only=true)`, then post it and read it back (`get_entity`). Then `generate_report(report_type="trial_balance", ...)`.

**When something is missing**, the posting refuses with the account or profile it could not resolve; there is no fallback account. Create the missing account, profile or tax account through the operations above and retry. Do not skip or re-run onboarding tasks to get past it; `update_task` is for retrying a failed task, not for bypassing this procedure.

---

## Adding a Second Entity (DIFFERENT Procedure)

**Only after the org is fully onboarded** (`check_status` returns `needs_onboarding: false`).

### Step A: Collect ALL entity details BEFORE calling add_entity

`add_entity` does NOT have a post-hoc update path for VAT/tax_id — those fields are only set correctly when passed at creation time. Do not call `add_entity` until you have every answer below.

Ask the user for:

| Field | Required | Example |
|-------|----------|---------|
| Entity legal name | Yes | "Hala Digital OÜ" |
| Entity code (short, unique in org) | Yes | "HALA-EE" |
| Country | Yes | EE, US, GB (2-letter ISO) |
| Currency | Yes | EUR, USD, GBP (3-letter ISO) |
| VAT-registered? | Yes | true / false |
| Tax ID / VAT number | Conditional (required if VAT-registered) | "EE101980223" |

If the user doesn't know the VAT number yet but will be registered, pass `is_vat_registered=true` with `tax_id="PENDING"` — the record can be updated later via `submit(object_type="tax_registration", operation="update", data=JSON_STRING)` or the admin dashboard.

### Step B: Call add_entity

```
manage_onboarding(action="add_entity",
    entity_name="Hala Digital OÜ",
    entity_code="HALA-EE",
    country_code="EE",
    base_currency="EUR",
    is_vat_registered=true,
    tax_id="EE101980223"
)
```

This reuses the org's chart of accounts, tax codes and agents via MSEO and creates entity-specific items (fiscal periods, number series, emails, exchange rates, and an `entity_tax_registrations` row if `is_vat_registered=true`). It creates **no posting profiles**: they are kept per entity, so the new entity cannot post until they are created with `submit(object_type="posting_profile", operation="create", ...)` for its `legal_entity_id` (the answer's `not_set_up` says so).

### Step C: Updating a legal entity after creation

Safe fields updatable via `submit(object_type="legal_entity", operation="update", data=JSON_STRING)`: `entity_name`, `tax_id`, `country_code`, `address`, `is_active`, `metadata`.

```
submit(object_type="legal_entity", operation="update",
    data='{"entity_id":37,"entity_name":"Hala Digital OÜ (renamed)","tax_id":"EE101980223"}')
```

**NOT updatable via this executor** (intentionally blocked — would invalidate existing data):
- `entity_code` — referenced by agent emails, number series, reports. If the code is truly wrong, deactivate and create a replacement entity.
- `functional_currency` / `reporting_currency` — transaction amounts are already stored in this currency.
- `entity_type` / `accounting_standard` — structural; affects consolidation and COA.

**VAT registration** goes through `submit(object_type="tax_registration", operation="create", data=JSON_STRING)` / `tax_registration.update`, NOT `legal_entity.update`. The `legal_entities` table has no `is_vat_registered` column — VAT status lives in `entity_tax_registrations`.

---

## Troubleshooting

### "Organization has not completed initial onboarding"

If you get this error from `add_entity`, it means the org hasn't been set up yet. Use this procedure (Steps 1-5) instead.

### Waves stuck at less than 100%

Check which tasks are blocked:
```
get_onboarding(action="get_checklist", status="failed")
get_onboarding(action="get_checklist", status="pending")
```

Resolve the failed task’s cause, then use manage_onboarding(action="update_task", task_key=THE_FAILED_KEY, new_status="pending") before running another wave. Pending tasks may have unmet dependencies; inspect get_summary instead of repeatedly running a blocked wave. Do not reset populated company data.

### Country tasks left for configuration

A country without shipped onboarding data leaves its tax, payroll and expense-rate tasks skipped, not failed, so onboarding can complete. `get_onboarding(action="get_checklist", status="skipped")` shows what each task's last onboarding-wave run reported in `result`: `needs_configuration: true` with the `section` and `reason` is a gap to configure through the governed operations (the `arfiti-core-country-setup` plugin does this with the user); `needs_configuration: false` means the section does not apply. Nothing was generated for these tasks — never fill them with assumed rates.

### User already created entity via admin dashboard

If a legal entity exists but the checklist was never initialized, call `start` with `legal_entity_id=<existing_id>` and the wave runner will detect existing data and skip tasks that are already done.

### "No executor registered for 'legal_entity.create'"

The current code registers a legal_entity.create executor. This error can indicate an older deployment or a missing workflow/executor configuration; inspect the deployed schema and setup status before retrying. For first-time assistant-led setup, use start and run_wave as described above. The Admin wizard has its own entity-create/setup flow. Do not create a duplicate entity or bypass authority to recover this error.

### "fiscal_periods_legal_entity_id_fkey" FK error from initialize_entity

You called `initialize_entity` before the legal entity was created. Do NOT call `initialize_entity` before `start`. Use `start` to initialize the checklist, then `run_wave` to execute runnable tasks. Inspect the existing entity and task state before retrying.

---

**Version**: 1.4
**Last Updated**: 2026-11-23

### Recovery and verification

Admin signup and MCP provisioning use shared database initialization for workflow definitions and subledger history. After deploying migration 623, an owner/admin can call `manage_organization(action="repair_template_data")` in their current company to repair missing initialization. Switch company first for a client company; cross-company repair arguments are refused. Existing/customized or inactive workflows are preserved, so intentionally inactive definitions need explicit review.

Check both `completed` and `skipped` counts. An empty migration task is skipped, not imported. An explicit null VAT configuration in the US template is not applicable and does not call an AI generator. A software failure must remain failed. Reports for periods before a repaired company's historical evidence boundary may remain unavailable; repair does not fabricate application history.

### After the final wave

Make the three offers in Step 6 (plugins, project, migration question). Each plugin is installed separately; adding the marketplace installs none. An organisation that wants its own rules keeps a skill of its own beside the plugins: an update replaces edits made inside an installed plugin. Verify the chosen client connects to the intended organization; completed company setup does not certify that connection. Review any `needs_attention` items before relying on them.

The Admin finish summary uses the label Assistant. Its external Claude link appears only when the recorded path is Claude; IDE or unknown paths finish at the dashboard. Do not treat the finish-screen link or label as proof of a working connection.

Connection-step copy/download indicators describe local browser actions only. Changed instructions, organization URLs or replaced keys/configurations need copying again. A failure clears the corresponding success indicator; it does not revoke or create a key, verify installation, or change onboarding status.

Overlapping copy requests show feedback for the latest attempt. A login/error page returned by a plugin download is rejected rather than reported as a downloaded archive; restore the browser session if needed and retry.


If Admin reports **Entities not loaded**, ask the user to retry the list read; do not infer that the organization has no entities or start duplicate setup from that message. The form disables currency selection when its catalog is unavailable: use Retry currencies after a read failure, or ask an administrator to investigate an empty catalog. Existing draft values are preserved; these browser states do not change MCP onboarding contracts.


Onboarding's **Entity refresh failed** means the displayed entity state came from the last successful read. Use **Reload** to refresh it without rerunning ledger tasks. **Retry currencies** reloads only currency choices and preserves draft edits; a full browser reload is unnecessary for that read failure. Neither action certifies setup completion or changes MCP contracts.

Admin configuration and record-page help offers ChatGPT, Claude, and a copyable
question for another assistant. The client choice does not install a connector or
change the MCP organization. Ask the user to paste the question into their
connected client and verify the current organization before record operations.
Clipboard refusal has a manual-copy fallback; it does not mean company setup failed.

Configuration company references such as ORG-0000002 are display labels, not API IDs; the underlying organization_id remains 2. The Admin connection wizard exposes ChatGPT, Claude and IDE setup paths. ChatGPT instructions use the company-pinned connector URL and OAuth; the selected path persists across reloads. Ask the user to select the installed Arfiti plugin in ChatGPT and request Check onboarding status, then confirm the returned company. The company connection timestamp may come from another client or user and does not verify this ChatGPT session. Workspace availability and live OAuth must be verified separately. The ChatGPT path offers neither IDE keys nor Claude skill/plugin downloads. The separate page-help link only opens the assistant destination.

On every path (Claude, ChatGPT, IDE) the Admin badge reads **First company connection** with a time, or **No company connection recorded**. It is organization history, not a live connection for the selected client; ask the user to confirm the company from that client's own tool response. Step 3's soft gate uses the same signal, and the step 3 and finish summaries show it beside the saved client choice. If the entity card reports failed onboarding tasks, check the checklist (`get_summary`), resolve each cause, then return only the affected task to `pending` with `update_task` and run another wave; nothing reruns automatically.


The final wizard screen is **Review your setup**, labeled **SETUP REVIEW**.
Reaching it records navigation progress; it does not certify ledger completion
or the current assistant connection. Read the loaded entity/ledger/connection
facts and any failure or retry messages. A missing entity, running/failed ledger,
or failed finish save must be resolved through its existing setup/retry action.
The review heading stays neutral even when setup has completed.


The onboarding shell now uses the same company display reference as configuration:
ORG-0000002 for internal ID 2, followed by the organization slug. References are
padded to at least seven digits and never truncated. This is display formatting,
not a new random identifier or a change to tenant IDs, schemas, API arguments,
connector URLs, or organization selection. The shell still hides the company
line on the initial organization step.


### Claude plugin setup

In Claude, open Customize → Plugins → Add → Add marketplace and enter
`arfiti-technologies/arfiti-plugins`, or upload a downloaded plugin ZIP in the Plugins tab.
Plugins are available on Claude web and Desktop with a paid plan, subject to
workspace policy. Hooks, sub-agents and local MCP servers require Cowork or
Claude Code. Downloading a ZIP does not install or verify the plugin. The ZIP holds
the plugin as the marketplace publishes it, with the same version; when the
marketplace cannot be reached it holds the copy deployed with the dashboard, whose
version can be lower.

Provider instructions checked on 2026-10-16 against
[Anthropic’s plugin guide](https://support.claude.com/en/articles/13837440-use-plugins-in-claude).
Actual Arfiti marketplace access, installation and execution still require
verification in the intended client and workspace.


### Onboarding rename HTTP failures

The onboarding rename endpoint requires a JSON object with a string name; invalid
JSON or a missing/non-string name returns 400 before organization lookup or
workflow submission. Valid names are trimmed and checked against the existing
2–255 character rule. Unexpected failures return a generic 500 response without
exception details; the handler logs a static failure marker. Owner/admin and
unfinished-onboarding checks, workflow approval, and idempotency remain unchanged.
