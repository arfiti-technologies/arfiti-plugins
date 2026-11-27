# Arfiti Plugins

[![Arfiti MCP connector](https://glama.ai/mcp/connectors/io.github.arfiti-technologies/arfiti/badges/score.svg)](https://glama.ai/mcp/connectors/io.github.arfiti-technologies/arfiti)

AI-powered plugins that give finance and accounting teams superpowers inside Claude, Cursor, and other AI tools. Each plugin packages domain knowledge — reporting formats, tax rules, compliance workflows — so your AI assistant handles the details correctly.

## Available Plugins

### Core: `arfiti`

One plugin, [arfiti](./arfiti), for any chart of accounts and any country. It carries the Arfiti connector and every core skill, command and subagent; each skill is loaded only when the task matches. Commands are called `/arfiti:<command>`.

| Area | What it does | Commands or skills |
|--------|-------------|----------|
| Operating guide | How to use the connector: the `submit` write gateway and its approval lanes, the read tools, the `get_*` / `manage_*` tool pairs, and a domain guide for each area. Generated from the monorepo skill templates. | Skill `arfiti-erp` |
| Agent procedures | The procedures Arfiti's own agents follow (bills, bank and card statement lines, payment reconciliation, vendors and customers, configuration, expense claims and checks, period close, billing usage), so your own Claude or Cowork does the same work the same way. Generated from the agents' procedures. | Skills `arfiti-bill-processing`, `arfiti-bank-statement-lines`, `arfiti-reconciliation`, `arfiti-period-close`, `arfiti-expense-claim` and 8 more |
| Financial reports | Balance Sheet, P&L, Cash Flow, Trial Balance, AR and AP aging, P&L by dimension and a Financial Summary, presented from the server's report contract with deterministic formatters. | `/balance-sheet` `/profit-and-loss` `/cash-flow` `/trial-balance` `/aged-receivables` `/aged-payables` `/dimension-analysis` `/financial-summary` |
| Budget planning | Annual and quarterly budgets, forecasts from actuals, employee cost budgeting with burden rates, project budgeting and variance review. | `/create-budget` `/forecast-budget` `/preview-budget` `/review-variance` |
| Cost allocation | Allocation across departments, projects or dimensions, from GL balances or linked to a specific bill or invoice. | `/run-allocation` `/preview-allocation` |
| Implementation consultant | Migration from another system: chart of accounts, opening balances with open invoices, bills and fixed assets, master data import, gap period and go-live checks. Subagent `balance-sheet-analyzer`. | `/start-migration` `/migration-status` `/import-data` `/verify-migration` `/close-migration` |
| Country setup | Configures a live company for its country: tax codes, authorities, registrations, filing calendars, withholding, payroll taxes and expense rates, researched with sources, confirmed and read back. Subagents `tax-researcher` and `payroll-specialist`. | `/set-up-country` `/author-country-plugin` |

It replaces the seven `arfiti-core-*` plugins (AR-1467).

### Estonia (EE)

One plugin, [arfiti-ee](./arfiti-ee), with four skills. A country pack is one plugin per country, named `arfiti-<country code>`. It replaces `arfiti-ee-country-pack` (AR-1467).

| Area | What it does | Commands |
|--------|-------------|----------|
| Year-end bookkeeping | Builds a full year's accounting from scratch for Estonian companies (OÜ/AS). Guides through chart of accounts setup, opening balances, bank statement processing (month by month), source document posting, reconciliation, and period close — preparing the entity for annual report filing. | `/setup-entity` `/upload-opening-balance` `/process-bank-statements` `/fill-gaps` `/reconcile-and-close` `/check-progress` |
| Annual report | Prepares the full annual report (balance sheet, income statement, notes, management report) and generates XBRL for e-Business Register filing. Uses the et-gaap-2026 taxonomy. | `/prepare-annual-report` `/check-prerequisites` `/generate-xbrl-file` |
| Payroll and TSD | Calculates gross-to-net payroll with Estonian tax formulas (social tax, income tax, unemployment insurance, funded pension) and generates TSD declarations for EMTA. | `/calculate-payroll` `/generate-tsd` |
| VAT return | Prepares & validates VAT returns (KMD2 machine CSV + XML) and KMD INF annexes. Runs a pre-close validation gate, then generates. The EC Sales List (Form VD) is a separate filing. Dynamically discovers tax codes and maps to KMD lines. | `/prepare-vat-declaration` (add `validate` to run the gate only) `/prepare-ec-sales-list` |

More countries coming soon.

### Cursor

[cursor/arfiti](./cursor/arfiti) is the same core plugin packaged for Cursor: the Arfiti connector and the core skills (operating guide, agent procedures, financial reports, budget planning, cost allocation, migration and country setup), without the Claude-specific slash commands and subagents. A few pages still name other assistants where they describe Arfiti's own admin screens. Ask for the work in plain words and the matching skill is loaded.

- **Install:** from the Cursor Marketplace once it is listed, or copy `cursor/arfiti` to `~/.cursor/plugins/local/arfiti` and restart Cursor.
- **Sign in:** open Cursor's MCP settings and choose **Sign In** next to `arfiti`. A browser window opens at `id.arfiti.com`; sign in with your Arfiti account, or use the sign-up option there to create a company. The consent screen names Cursor and shows `www.cursor.com` as the place you return to.
- **What it can reach:** only the company and legal entities your account can access, with your role's permissions. Every write goes through your organisation's approval workflow. It moves no money: sending a payment batch to a bank is done from the Arfiti dashboard.
- **Configuration:** none. The plugin holds no keys or tokens.
- **Support:** [arfiti.com/contact/support](https://arfiti.com/contact/support) or support@arfiti.com.

This folder and `.cursor-plugin/marketplace.json` are generated from the core plugin; changes made to them here are overwritten.

## Getting Started

### Option 1: Clone the repository

```bash
git clone https://github.com/arfiti-technologies/arfiti-plugins.git
```

Add the plugin directory to your Claude Desktop project. For Cursor, use the `cursor/arfiti` folder (see Cursor above).

### Option 2: Download ZIP

[Download latest ZIP](https://github.com/arfiti-technologies/arfiti-plugins/archive/refs/heads/main.zip)

### Option 3: Via Arfiti admin dashboard

If you use [Arfiti](https://arfiti.com), plugins are available directly from the admin dashboard under **Administration > Plugins** with one-click download.

## How Plugins Work

Each plugin is a self-contained package that extends your AI assistant with domain-specific knowledge:

```
plugin-name/
  .claude-plugin/plugin.json    # Plugin manifest (name, version, description)
  .mcp.json                     # MCP server connection (links to Arfiti backend)
  commands/                     # Slash commands (e.g. /prepare-annual-report)
  agents/                       # Subagents (e.g. tax-researcher)
  skills/                       # Detailed workflow instructions + reference data
    skill-name/
      SKILL.md                  # Step-by-step workflow with checkpoints
      references/               # Tax tables, form structures, filing guides
  scripts/                      # Deterministic generators (XML, XBRL, etc.)
```

**Commands** are entry points — the user types `/prepare-vat-declaration` and the AI follows the workflow defined in the skill.

**Skills** contain the actual knowledge — multi-step workflows with mandatory checkpoints, validation rules, and reference data.

**References** are the source of truth — tax formulas, XBRL element mappings, regulatory form structures. The AI reads these instead of guessing.

**Scripts** generate deterministic output (XBRL, XML declarations) where AI generation would be unreliable. Claude builds compact JSON, the script produces valid XML with hardcoded namespaces and validated structure.

## Contributing a Country Plugin

We welcome contributions for new countries. A typical compliance plugin needs:

1. **Annual report** — Balance sheet and income statement formats, local GAAP taxonomy, filing portal instructions
2. **VAT/GST/Sales tax** — Return form structure, tax codes and rates, filing format
3. **Payroll** — Tax formulas (income tax, social contributions, pension), payslip format, declaration forms

See any existing country plugin for the structure. Open an issue or PR to get started.

## MCP transport config (checked in CI)

Each plugin's `.mcp.json` points at the Arfiti MCP server. The `type` field must
be a real transport — `http` (alias `streamable-http`), `sse`, `ws`, or `stdio`.
A remote endpoint uses `"type": "http"`:

```json
{ "mcpServers": { "arfiti": { "type": "http", "url": "https://mcp.arfiti.com/streamable/mcp" } } }
```

`"type": "url"` is **not** a transport. It shipped from April to 2026-08-19 and
cost five weeks of outage: Claude Code tolerated it, but Cowork's stricter sync
rejected the entire marketplace with a generic "Marketplace sync failed", so no
plugin was installable there. `claude plugin validate` does not read `.mcp.json`,
so nothing caught it. `plugins/scripts/check_mcp_configs.py` now runs in the
publish workflow and fails the build on an invalid transport.

The canonical production endpoint is `https://mcp.arfiti.com/streamable/mcp`.
After the October 2026 migration, update installed plugins to the new patch
versions; cached earlier releases still contain the old `/mcp` URL. Reconnect
the MCP connection if prompted. Updating source does not rewrite installed caches.

## Support

support@arfiti.com · Documentation: https://arfiti.com/docs

## Publishing to the Anthropic directory

This repository's contents are submitted to the Anthropic directory from `arfiti-technologies/arfiti-plugins`, which the publish workflow syncs and nobody edits by hand. Each plugin folder needs a README with a "What it runs and sends" section, a LICENSE and a `license` in `plugin.json`, all checked by `plugins/scripts/check_mcp_configs.py`. `arfiti` is partly generated: its `arfiti-erp` skill, manifest, `.mcp.json` and README come from `plugins/scripts/build_core_plugin.py` (edit `mcp-server/skill-templates/base`), its `arfiti-*` procedure skills from `managed-agents/scripts/build_skill_plugin.py --publish` (edit `managed-agents/skills`); its other skills, commands, agents and scripts are edited in place. Rerun `build_core_plugin.py` after adding a skill, command or agent so the README lists it, and commit both. The full process is in [GUIDE_PLUGINS.md](../docs/GUIDES/GUIDE_PLUGINS.md#anthropic-directory).

## Versioning (assigned when publishing)

Claude.ai caches installed plugins **by version** — shipping changed content under an
unchanged version means users keep the stale cached copy even after reinstalling.

A pull request that changes a plugin does **not** bump its version. When `main` is
published, `publish-plugins.yml` compares every plugin with the copy the public mirror
(`arfiti-technologies/arfiti-plugins`) already serves, ignoring the version field, and gives
each changed plugin the next patch above its published version
(`plugin_versions.py --assign`). The mirror therefore always serves a new version for
new content, and parallel pull requests no longer collide on one version number or on a
shared lock file (the former `versions.lock.json`, removed 2026-11-09).

The version in this repository is the **declared floor**. Raise it only for a deliberate
change, and publishing never goes below it:

```bash
python3 plugins/scripts/plugin_versions.py --bump <plugin-name> <major|minor>
```

- **major** — breaking: commands removed/renamed, output format changed
- **minor** — new commands or features
- **patch** — assigned by the publish; never needed by hand

`plugin_versions.py --check` (pull requests and the publish) fails when `plugin.json`
and the `marketplace.json` entry disagree or a plugin is missing from the marketplace.
The published patch can be a few numbers above the declared version: the app's plugin
registry and the landing catalog show the declared version. The onboarding plugin
download (`/api/plugins/download/{slug}`) serves the mirror's files, so its zip carries
the published version. It falls back to the repository copy, which has the declared
version, only when the mirror cannot be read or has not published the plugin yet; the
`X-Plugin-Source` response header says which (`mirror` or `repository`).

The publish compares with the mirror's current copy only. A plugin removed from the
mirror and added back later (or renamed) starts again from its declared version, so
declare one it never published (`--bump <plugin> minor`), or clients keep a cached copy
of that earlier version.

Why this exists (per the official plugin-marketplace docs): when `version` is set,
clients pin the cached plugin to that exact string — *"you must bump it every time you
want users to receive changes; pushing new commits alone is not enough."* The docs also
advise against setting `version` in both `plugin.json` and the marketplace entry
(the marketplace entry wins when set — see code.claude.com/docs/en/plugins, version
management); we deliberately keep both **because the CI check enforces they are
identical**, which removes the masking risk while every client surface sees the same
version. Do not remove one of them without updating the checker.

## License

[MIT](./LICENSE) - Arfiti Technologies OU
