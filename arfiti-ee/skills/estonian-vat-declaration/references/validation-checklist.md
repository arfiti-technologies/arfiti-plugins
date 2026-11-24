# KMD Pre-Close Validation Gate

The single gate that runs **before** the KMD is generated or uploaded. Every check has
a severity:

- **BLOCK** — do not generate the return until fixed.
- **WARN** — generate, but surface for the reviewer to confirm.

Run all seven, then emit one pass/fail report (see "Output" below). If any BLOCK is
open, **refuse to generate** and print the list. The `/prepare-vat-declaration` command
runs this gate automatically before the generate step; `/prepare-vat-declaration
validate` runs it standalone and stops.

Each check caused real rework in a prior period; the *Caught* note says what it would
have prevented.

---

## 1. Output-format validation — BLOCK

Enforced mechanically by `scripts/generate_kmd.py` after it builds the files and
**before** it writes them (the script refuses to write on any failure):

- XML validates against the bundled official `vatdeclaration.xsd` (`xmllint --noout --schema`).
- CSV is mechanically well-formed: exactly **31 fields** per row, period-correct
  **version** (KMD6 from 07.2025), **dot** decimals, `TRUE`/`FALSE` flags, **CRLF**
  endings, no BOM, and no total-VAT/payable columns.
- Derived figures recomputed and asserted: `line4 = 24%·line1 + 9%·line2 + …`;
  `line12 = line4 − inputVatTotal + adjustmentsPlus − adjustmentsMinus`; and, when the
  caller passes `expected_vat_payable` / `expected_vat_overpaid`, the computed value
  must match.

*Caught:* all three e-MTA rejections (the fabricated `<KMD>` schema and the
prose-header CSV) and the €20.79 line-5 gross-up error.

## 2. Completeness — payments without a document — BLOCK

Find cash movements in the period with no matching invoice/bill:

```
query("transaction", filters={"legal_entity_id": ID, "transaction_type": "AR_PAYMENT"},
    date_filters={"transaction_date": {"from": "YYYY-MM-01", "to": "YYYY-MM-DD"}})
query("transaction", filters={"legal_entity_id": ID, "transaction_type": "AP_PAYMENT"}, ...)
# plus unmatched bank statement lines for the period
```

Any AR_PAYMENT / AP_PAYMENT with `recon_status` null/unmatched, or any unmatched
`bank_statement_line`, is a **missing invoice/bill** (or a payment that should not be
there). List them and BLOCK until each is resolved.

*Caught:* the €572.88 Telia receipt whose invoice 2077 was never posted; the orphaned
EMTA tax payments.

## 3. Period basis / cut-off — WARN

Build the return strictly from documents **by invoice/document date**, never by payment
date. Flag any document whose invoice date and settlement date fall in different
periods so the reviewer checks the other period.

*Caught:* Nexia (invoice April, paid June) and the DigitalOcean / Supabase / Google May
invoices paid in June — the payment-vs-invoice-date confusion.

## 4. Tax-code coverage & jurisdiction sanity — BLOCK on missing, WARN on mismatch

- **BLOCK**: every taxable transaction line has a tax code (existing CP2), and each code
  resolves to a KMD line (see `references/tax-codes-ee.md`). Check only lines whose
  `line_role` is `document`: the generated `control` row of an AP invoice never carries
  a tax code and is not a gap.
- **WARN**: supplier jurisdiction agrees with the code — an Estonian (EE) vendor must
  **not** carry an intra-EU-acquisition code (line 6); a non-EU supplier must map to
  line 7, not line 6. Compare `vendor.country_code` against the code's `tax_scope`.

*Caught:* Nexia / Wise Guys / AWS coded 845 (intra-EU) though domestic; the EU/non-EU
reverse-charge merge. (See `BILL_AGENT_FIX_for_ClaudeCode.md` — this check is the safety
net for that agent bug.)

## 5. GL tie-out — BLOCK on material difference

Reconcile the declaration against BOTH the canonical tax computation and the GL:

1. **Canonical computation** — run `generate_report("vat_report", {"legal_entity_id":
   ID, "start_date": "YYYY-MM-01", "end_date": "YYYY-MM-DD"})`. It aggregates from the
   `v_tax_lines` view (migrations 465, 601) — the same source as the dashboard Sales-tax
   report — so output VAT, input VAT and net must match your computed
   `declaration_body` figures. This is the authoritative figure: the view counts every
   ledger-effective document (`posted`, `partial`, `paid`, `partially_paid`,
   `completed`, `approved`, `reversed` with `posted_at` set, each reversal signed in its
   own period, amounts in the functional currency), so a
   difference usually means a document list filtered on `status: "posted"` alone and
   dropped the paid documents.
2. **GL tie-out** — via
   `generate_report("trial_balance", {"legal_entity_id": ID, "as_of_date": "YYYY-MM-DD"})`:
   - output VAT (`24%·line1 + reduced rates`) ↔ output-VAT account movement (2300 / 2310);
   - input VAT (`inputVatTotal`, line 5) ↔ input-VAT account movement (2300 debit side / 2311);
   - net ↔ line 12.

Report any difference above a rounding tolerance (≈ EUR 1) together with the driving
account or tax code.

## 6. INF threshold / annex consistency — BLOCK

Run the partner selection on the period's invoice lists (both sides **without VAT**,
per EMTA's KMD INF instructions 07.2025 — see `kmd-inf-annex.md`):

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/generate_kmd.py" --select-inf invoices_A.json --side A
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/generate_kmd.py" --select-inf invoices_B.json --side B
```
If `${CLAUDE_PLUGIN_ROOT}` is not set in your shell, use the folder this plugin is installed in (ask the user for it); never search their home folder.

Do not aggregate the transaction header `amount` for the limit: it is gross, and it
includes invoices the instructions exclude (no supply at a positive rate, natural
persons, part B invoices without deducted VAT). Pass it per invoice as `gross_amount`
only, for the check below.

Each invoice's figures come from its `line_role: "document"` lines only (SKILL Step 2,
"Per-invoice figures"); the `control` row a native AP invoice returns among its lines
is worth the whole document total and must never be added.

- **Gross tie** — every invoice in both lists carries `gross_amount` (the header
  `amount`, in EUR) and, where it has reverse-charge lines, `reverse_charge_vat_amount`.
  The selector refuses the selection when net + VAT − reverse-charge VAT (signed; a
  credit memo's net turned back to the document's sign) differs from `gross_amount` by
  more than 0.02 on any invoice, and lists each one — **BLOCK** until
  a person has dealt with every listed invoice (an invoice the person accepts carries
  their reason in `gross_mismatch_reviewed` and is reported under `gross_reviewed`). A
  non-empty `gross_not_checked` is itself a **BLOCK**: the check did not run on those
  invoices.
- **Line tie** — every invoice carries `line_nets` (each `document` line's net and
  rate, SKILL Step 2). The selector refuses the selection when they do not add up to
  the invoice's net (a cent per line allowed). A non-empty `lines_not_checked` is a
  **BLOCK**: the selector declared those invoices as one ordinary row without seeing a
  second rate or a negative line.
- **Canonical tie** — over every document of an `ap`-category type (input) and
  `ar`-category type (output) inside the VAT registration (`registration_type` `vat`;
  `effective_to` from `get_entity("tax_registration", id=…)`; by the document's date, a
  credit memo by the date of the invoice it credits), not only invoices and credit
  memos: input Σ `taxed_net` = Σ `taxable_amount` of
  `vat_report.input_vat_details`; output Σ `taxed_net` = Σ `taxable_amount` of
  `output_vat_details` − Σ line net of the `ap` documents' reverse-charge lines;
  reversals dated in the period subtract the reversed document's `taxed_net`. Exact
  for EUR documents, 0.01 per line for foreign-currency ones. Any other difference —
  **BLOCK**, with the documents that explain it (SKILL Step 2).
- **Accrual reversals** — any AP invoice whose header (`get_entity("transaction",
  ids=[…])`) carries `metadata.accrual_reversal` — **BLOCK** for that invoice until a
  person decides its net: the header total includes the accrual reversal; on a bill
  posted before AR-1438 its line reads as `document` and neither tie catches it, on a
  later one it reads as `generated` and the gross tie differs by the amount reversed.
  Bills posted since AR-1444 (November 2026) never carry the mark or the line (the AP
  invoice no longer reverses accruals), so only older bills reach this check.

- Every partner in `declare` (invoices without VAT at least EUR 1,000.00, inclusive)
  must have its invoices in the annex, and the annex must hold no other partner unless
  declared voluntarily. If the annex is empty, `noSales` / `noPurchases` must be TRUE.
  A partner below the limit that has an invoice carried from an earlier period
  (`counted_in_earlier_period`) appears twice: the carried invoice under `declare` (it
  must be presented) and its other invoices under `below_threshold` (they are not).
  (`generate_kmd.py` derives the flags from the annex lines, so the gate's job is to
  confirm the annex lines match the selection.)
- Any invoice in `sign_review` — **BLOCK** until a person decides how it is presented;
  it was neither declared nor counted toward the limit. It holds: amounts of mixed sign
  (an edited bill with a negative net and a positive total, a credit memo whose lines
  sum below zero); an ordinary sales invoice with a negative total that does not refer
  to an original invoice (AR-1439 rule 5); lines of both signs that neither EMTA's text
  nor the AR-1439 treatments settle (on a multi-rate sales invoice a rate with both
  signs, a negative 0 %/exempt line, a single-rate invoice with a 0 %/exempt part or
  VAT not equal to net × rate, a negative multi-rate total, a sales credit memo); and
  an ordinary purchase invoice with a minus sign (negative
  `vat_deducted_in_period` or negative total) (part B takes a minus sign only on a credit invoice or an invoice unpaid under VAT Act
  § 29¹(4); a person decides which, the tool cannot). A multi-rate sales invoice whose
  negative amounts are whole rate groups is **not** here: EMTA settles it (code 03, one
  row per rate, signed column 9, column 6 repeated; part A example 1500 = 24 % 2000 and
  9 % −500) and the selector declares it with `rate_rows`. Nor are a single-rate sales
  invoice with lines of both signs (one row, no code) or an ordinary part B invoice
  with lines of both signs (one row, net amounts): AR-1439 recommended treatments,
  declared. A purchase credit memo with lines of both signs **is** here.
- Any entry in `cancellation_review` — **BLOCK** until a person decides: a cancellation
  without a reference to the original invoice, one whose reason (cancelled transaction
  or invoice issued by mistake) is not recorded, an invoice issued by mistake (correct
  the original period, VAT Act § 27(5), nothing in this period), a sales invoice issued
  and cancelled in this period where turnover arose or is not confirmed absent, or
  whose cancellation's figures differ, two cancellations of one invoice, an invoice
  that any other document (credit memo, reduction or replacement invoice) also refers to, a
  cancellation of a credit memo, and **every cancelled purchase invoice**. The invoice
  a reviewed cancellation names, and every other document in the list that refers to
  that invoice, are listed there too (neither declared nor left out until
  the person decides). Not declared, not counted
  toward the limit. A cancellation without a reference names no invoice: check whether
  the invoice it cancels was declared, and show both to the person.
- Any invoice in `reverse_charge_review` (cross-border reverse charge on a bill that
  also carries supplier VAT) — **BLOCK** until a person decides. Plain cross-border
  reverse-charge bills (intra-Community acquisitions, services from abroad) are
  `excluded`: KMD INF does not show them (EMTA annex page, see `kmd-inf-annex.md`).
- Any invoice in `rate_review` (a line rate outside 24/22/20/13/9/5, e.g. an
  organisation's own code) — **BLOCK** until a person decides how it is classified; it
  was neither declared nor counted toward the limit.
- Any sales invoice with a line on a § 41¹ code whose `default_rate` is 0 or empty
  (SKILL Step 2) — **BLOCK**. It is kept out of the selector, so the partner totals
  exclude it and it can neither bring the partner over EUR 1,000 nor be declared. A
  person decides the rate for column 7 and whether it counts toward the limit before
  filing.
- Any part B bill with a reverse-charge code whose `tax_scope` is `import` — **BLOCK**
  until a person decides: the cross-border rule above does not cover it. Passed with
  `import_reverse_charge: true`, the selector lists it under `reverse_charge_review`.
- A part A line with special code 02 (§ 41¹ seller) and column 9 filled — **WARN**
  (`generate_kmd.py` prints a note): a pure § 41¹ row leaves column 9 empty and the
  supply goes to KMD line 9; only general-procedure supply on the same invoice may sit
  there, and a person confirms it. A part B § 41¹ line
  carries code 12 and column 6 = the invoice total with VAT as shown on the invoice.
- Any partner in `needs_registry_code` — **BLOCK** until a person supplies a verified
  register code or confirms the partner is a non-resident without one. Never fill it
  from a VAT number.
- Every reversal of an AR/AP invoice dated in the period is passed to the selector as a
  cancellation entry (SKILL Step 2, item 3) — **BLOCK** if one is missing: its minus row
  (later period) or the omission of the pair (same period) depends on it. A
  `turnover_arose: false` that rests on `amount_paid` alone — **BLOCK**: a reversed
  invoice always reads 0 there (payments are unmatched before a reversal); it needs the
  payment history and the person's word that nothing was supplied. A reversal of an
  invoice that also has a credit memo in another period — **BLOCK**: listed for the
  person, not passed to the selector. Voided
  documents (never posted, no turnover declared) — **WARN**: listed for the person only.
- Any `include_lines` response with the "Line items truncated" warning — **BLOCK** until
  the lines are re-read; a truncated invoice has a net that is too low.
- `vatSum` / `invoiceSumForRate` present while the entity is not on cash accounting —
  **BLOCK** (the generator also refuses it).

*Caught:* confirms Hala's `noSales` / `noPurchases` = TRUE were correct (Telia €910 <
€1,000), and would flag the opposite mistake.

## 7. Arithmetic / form rules — BLOCK

- line 12 and line 13 are mutually exclusive (enforced by the script).
- If an EC Sales List (Form VD) exists: goods total (col 3) = `euSupplyGoodsZeroVat`
  (line 3.1.1); services total (col 5) = `euSupplyInclGoodsAndServicesZeroVat` −
  `euSupplyGoodsZeroVat` (line 3.1 − 3.1.1). Triangular resale (col 4) is NOT in the
  KMD. (Not "3.1 / 3.2" — 3.2 is export, never on the VD.)
- All monetary values have 2 decimals and are non-negative where the XSD requires
  (`adjustmentsPlus` / `adjustmentsMinus`).

---

## Output

Emit a single report — one row per check with **PASS / WARN / BLOCK**, the offending
records, and the fix:

```
KMD Pre-Close Gate — Entity 41, 2026-06
  1. Output format ............ PASS
  2. Payments w/o document .... BLOCK  AP_PAYMENT #518 (€572.88 Telia) unmatched → post invoice 2077
  3. Period cut-off ........... WARN   Nexia inv 2026-04-…, settled 2026-06 → confirm April period
  4. Tax-code jurisdiction .... WARN   Vendor "AWS" (US) coded 845 (intra-EU) → should be line 7
  5. GL tie-out ............... PASS
  6. INF threshold ............ PASS   no partner ≥ €1,000 without VAT → noSales/noPurchases=TRUE
  7. Arithmetic / form rules .. PASS

RESULT: 1 BLOCK, 2 WARN → generation refused. Fix BLOCK items and re-run.
```

- **If any BLOCK is open**, refuse to generate the KMD and print the list.
- **WARN items** are listed but do not stop generation — the reviewer confirms them.

## Common issues and resolutions

| Issue | Resolution |
|---|---|
| Payment with no matching document | Post the missing invoice/bill, or reverse the stray payment |
| EE vendor carrying an intra-EU code | Recode to a domestic code; if reverse charge, use line 7 not line 6 |
| Missing tax code on invoice | Assign the correct code (property-based, see tax-codes-ee.md) |
| GL balance ≠ KMD | Unposted entries, manual journals, or a cut-off timing difference |
| KMD INF total ≠ KMD | Partners below threshold, credit notes, exempt transactions |
| EC Sales List ≠ lines 3.1.1 / (3.1−3.1.1) | Verify IC goods-vs-services classification and customer EU VAT IDs |
