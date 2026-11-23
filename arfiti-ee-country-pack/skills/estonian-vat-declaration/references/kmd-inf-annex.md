# KMD INF Annex (Transaction Partner Reporting)

The KMD INF is the annex to the KMD form that reports invoices issued (part A) and
received (part B) per transaction partner once the partner reaches the threshold.

**Sources** (read these before changing any rule here):
- EMTA, *Instructions for filling in the appendix (form KMD INF) to the value added tax
  return*, version 07.2025:
  <https://www.emta.ee/sites/default/files/documents/2025-07/vorm_kmd_inf_2025_07_eng.pdf>
  (cited below as "KMD INF instructions"). The Estonian original, *Vorm KMD INF* with
  its completion instructions (July 2025):
  <https://emta.ee/sites/default/files/documents/2025-07/vorm_kmd_inf_2025_07.pdf>.
- EMTA, *KMD INF A-osa täitmise näited* and *KMD INF B-osa näited* (worked examples,
  11.12.2025; cited as "part A examples" / "part B examples"):
  <https://ncfailid.emta.ee/s/7gqZDi4yW3FQGBe>, <https://ncfailid.emta.ee/s/9sykJcfi9xDzN7t>.
- EMTA, *Käibedeklaratsiooni lisa täitmine* (cited as "EMTA annex page"):
  <https://emta.ee/ariklient/maksud-ja-tasumine/kaibemaks/kaibedeklaratsiooni-ja-aruannete-esitamine/kaibedeklaratsiooni-lisa-taitmine>
- EMTA, *Filing VAT returns and reports*:
  <https://www.emta.ee/en/business-client/taxes-and-payment/value-added-tax/filing-vat-returns-and-reports>

A taxable person with limited liability files the KMD but not the annex (EMTA filing page).

## Threshold

**At least EUR 1,000.00 without VAT, per transaction partner, per taxation period
(calendar month).** Inclusive: exactly 1,000.00 qualifies, 999.99 does not. The amount is
the invoices' total **excluding VAT** — never the gross invoice amount.
(KMD INF instructions, introduction and "Accounting the limit per transaction partner";
EMTA filing page: "the total amount of sales or purchase invoices without VAT per
transaction partner is at least 1,000 euros".)

How the limit is counted (KMD INF instructions, "Accounting the limit per transaction partner"):

- Separately for invoices issued (part A) and invoices received (part B).
- Separately for ordinary invoices and for credit invoices. If either total reaches
  EUR 1,000 for a partner, **all** invoices with that partner in the period, credit
  invoices included, are declared.
- Only invoices containing supply taxable at 24 %, 13 %, 9 % (exceptionally 22 %, 20 %,
  5 %) count. For such an invoice the **whole** total without VAT counts, including
  0 %, exempt and non-supply amounts on the same invoice. An invoice with no supply at
  those rates does not count and is not declared.
- An invoice counts into the limit only once, in the first period it must be declared.
  An invoice declared earlier whose supply (part A) or deduction (part B) also falls in
  this period is declared again now, whatever this period's totals (pass it with
  `counted_in_earlier_period: true`).
- In a VAT group the limit is counted separately for each member.

Invoices that are **not** declared (KMD INF instructions, "Invoice data shall not be presented"):

1. Issued to a natural person (other than a self-employed person), or to a non-resident
   without a register code assigned in Estonia (register of taxable persons, Taxation Act § 17).
2. No supply at 24/22/20/13/9/5 % on the invoice (for example only exempt or 0 % supply).
3. Issued solely under the travel-services special procedure (VAT Act § 40).
4. Subject to professional secrecy (the recipient may still declare it).
5. Part B only: the VAT on the invoice is not deducted as input VAT.
6. Invoices for cross-border transactions that are reverse-charged in Estonia, for
   example an intra-Community acquisition of goods or a service bought from abroad
   (EMTA annex page: "Samuti ei kajastata vormil arveid piiriüleste tehingute kohta,
   mis kuuluvad Eestis pöördmaksustamisele"). Part B covers invoices received from
   persons registered in Estonia as VAT payers (KMD INF instructions, part B), so a
   non-resident registered in Estonia as a VAT payer is in part B for invoices it
   charges Estonian VAT on (our reading of that sentence), but a cross-border
   reverse-charge invoice is not shown whoever issued it. A reverse-charge code with
   `tax_scope: "import"` is not covered by this rule; such a bill
   (`import_reverse_charge`) goes to `reverse_charge_review`, as does a cross-border bill
   that also has a special-procedure line; these go there even when the bill would
   otherwise be excluded (for example VAT not deducted). Domestic
   reverse charge under VAT Act § 41¹ **is** shown (part A code 02, part B code 12).

A partner below the threshold may still be declared voluntarily (VAT Act § 27(1³)).

### Selecting partners (deterministic)

Build an invoice list from the period's ledger-effective invoices — every status that
carries the VAT, paid ones included (SKILL.md Step 2 fetches them with
`include_lines=true`). **Use only the lines whose `line_role` is `document`.** The
reads also return, for a native AP invoice or AP credit memo, the generated control
line (`line_role: "control"`, the whole document total, no tax code); counting it turns
a bill of net 1,000 into 2,240 and can push a partner over the limit. Per invoice, over
its `document` lines (SKILL.md Step 2, "Per-invoice figures"): the **net** total is the
sum of line net (`line_amount − tax_amount` when the line `is_tax_inclusive`, else
`line_amount`) — the rule the canonical tax view uses, so a tax-inclusive line never
pushes a partner over the limit on its gross amount — untaxed lines included; the VAT
is the sum of `tax_amount`; `reverse_charge_vat_amount` is the sum of `tax_amount` on
reverse-charge codes; `gross_amount` is the header `amount`; and
`has_positive_rate_supply` is true when any line carries a tax code at
24/22/20/13/9/5 %; `line_nets` lists each `document` line's net with its rate (below);
and, for part B, `cross_border_reverse_charge` is true when any `document` line carries
a tax code with `is_reverse_charge: true` and `tax_scope` `intra_union_goods`,
`intra_union_services` or `foreign_reverse_charge` (both fields come from
`query("tax_code")`; a reverse-charge code with no `tax_scope` is classified with the
person in SKILL.md Step 1, never guessed from the supplier's country). A § 41¹ code
(`is_reverse_charge: true`, `tax_scope: "domestic"`) is not cross-border. Amounts are in **EUR**: for a foreign-currency document multiply
the document amounts by the header's `exchange_rate` (document → functional rate) and
round to cents per invoice; the limit and the annex are in euros, and `vat_report` sums
the functional amounts (per line, so cents may differ). For a credit memo pass
`net_amount` = −(Σ line net), the document's stored (positive) sum negated, with VAT,
reverse-charge VAT and `gross_amount` as stored, and its `document_type`; the selector counts any credit
memo as a credit and returns `signed_net_amount` (negative) for the annex columns,
which take credit invoices with a minus sign. An ordinary invoice whose net, VAT and
total are all negative or zero (a reduction under VAT Act § 29¹) carries a negative
`net_amount` and also counts as a credit.

**Only an invoice whose amounts carry one sign is presented**, with one exception below.
An ordinary invoice with net, VAT and total all ≥ 0, an ordinary invoice with all ≤ 0
(the credit above), or a credit memo with a `net_amount` ≤ 0 (negative, or zero for a
VAT-only credit) and VAT and total ≥ 0 as stored. Anything else — an edited bill with
a negative net and a positive total, a credit memo whose lines sum below zero (or whose
`net_amount` was passed positive) — has no presentation in EMTA's instructions that this
skill knows. The selector neither declares it nor counts it toward the limit; it
returns it under `sign_review` with its figures, and a person decides.

**Lines of both signs (`line_nets`).** Each invoice carries `line_nets`: one
`{"rate": …, "net_amount": …}` per `document` line, `rate` being the column 7 value
("24", "13", "9", …) for a line whose tax code is at 24/22/20/13/9/5 % and `null` for a
0 %, exempt or untaxed line, `net_amount` the line net in EUR in the document's own sign
(a credit memo's lines as stored, positive). `rate` is the tax code's `default_rate`;
"24", "24.00" and 24 are read as the same rate. A zero rate is refused (a 0 %, exempt or
untaxed line is null), so a zero-rated line cannot pass as a rate group; a value that is
not a number is refused. A positive rate other than 24/22/20/13/9/5 (the rates whose
supply the annex covers) sends that one invoice to `rate_review` for a person. A § 41/§ 42/§ 41¹
line carries its numeric rate and `"special_procedure": true` (even at zero net it keeps
a mixed invoice with a person). Other zero-net lines are left out of the rate groups. They must add up to the invoice's net within a cent per line (at
most 0.10), or the selection is refused. Invoices passed without them are
listed under `lines_not_checked` and declared as one ordinary row: the selector cannot
tell whether such an invoice has more than one rate or a negative line, so the skill
passes `line_nets` for every invoice and the list must be empty before filing. Then:

- **Settled, declared:** an ordinary sales invoice (part A) whose net, VAT and total are
  positive, with supply at two or more rates where each negative amount is a whole rate
  group (no rate whose lines carry both signs, no negative 0 %/exempt line, at most 4
  rates), and the invoice's VAT equal to Σ rate-group net × rate within a cent per line
  (at least 0.02, at most 0.10; otherwise a line may carry another rate's label and it
  goes to a person, as does a candidate without `vat_amount`; an invoice with more than
  about 20 lines may exceed the cap on rounding alone and then also stops for a person). Code 03 covers an
  invoice "with supply at two or more rates, incl. negative supply" (KMD INF instructions, part A column 10: "sealhulgas negatiivset käivet"), and
  the part A examples show it: invoice 1500 = 24 % 2000 and 9 % −500 → two rows, column 6
  = 1500 on both, column 9 = 2000 and −500, code 03. The selector returns the invoice with
  `rate_rows` (one per rate, signed net) and `special_codes: ["03"]`. It counts toward the
  limit at its total without VAT (1500 in the example), as an ordinary invoice: the limit
  is "the total amount of invoices … without VAT" and this is not a credit invoice, so
  its negative rate group does not enter the credit total. EMTA gives no example at the
  limit; that reading follows the text.
- **Kept with a person (`sign_review`):** a negative line at a single rate (or a rate
  whose lines carry both signs), a negative 0 %/exempt/untaxed line, an invoice with
  lines of both signs whose total is zero or below, a credit memo with lines of both
  signs, a multi-rate invoice with a line under a special procedure (§ 41/§ 42/§ 41¹,
  marked `special_procedure`; its rows need codes 01/02 and a § 41¹ net stays out of
  column 9), and any part B invoice with lines of both signs. EMTA's sources have no
  example of these. The column definitions are totals (part A column 9 is the part of
  the invoice declared at the rate, part B columns 6 and 8 are invoice totals), so a
  discount line may well need no special treatment; the AR-1439 decision is that a
  person confirms it rather than the tool. In practice an invoice with a discount line
  stops for review, and so does an untaxed rounding line of −0.01: it is a real
  document line, and ignoring small negative lines could hide a real mixed-sign case.
  These line checks, and the part B minus-sign check below, skip
  invoices that would not be shown anyway (excluded above); an invoice whose own net,
  VAT and total disagree in sign still goes to `sign_review` first.

**Part B minus sign.** Part B shows a minus sign only on a credit invoice and on an
invoice partly or fully unpaid under VAT Act § 29¹(4) (KMD INF instructions, part B:
"Kreeditarve ja KMS § 29¹ lõikes 4 sätestatud juhul osaliselt või täielikult tasumata
arve arvulised andmed kajastatakse vormil miinusmärgiga"). An ordinary purchase invoice
with a minus sign — a negative `vat_deducted_in_period` or a negative total — therefore
goes to `sign_review`, even where the supplier's negative invoice is a credit in
substance (the selector cannot tell; a credit memo document type is declared as a
credit); the selector
does not recognise the § 29¹(4) case (bad debt, shown under the original invoice
number), a person does.

**Cross-border reverse charge.** An invoice with `cross_border_reverse_charge: true` is
excluded with its own reason, whatever the supplier's register code (rule 6 above). It
needs `vat_amount` and `reverse_charge_vat_amount`; when the invoice also carries VAT
charged by the supplier (VAT ≠ reverse-charge VAT) it goes to `reverse_charge_review`
for a person instead.

Before selecting, the checks in SKILL.md Step 2 must hold: per document, net + VAT −
reverse-charge VAT = the header total (signed; a credit memo's net turned back to the
document's sign); per direction, the documents' taxed nets = the
taxable bases in `vat_report` (over every `ap` / `ar`-category document inside the
VAT registration, not only invoices); and no AP invoice whose header carries `metadata.accrual_reversal` is used
without a person's decision. The selector enforces the first one for every invoice that
carries `gross_amount`, refusing the whole selection and listing each invoice that
differs; an invoice a person has reviewed carries their reason in
`gross_mismatch_reviewed` and is listed under `gross_reviewed`, and invoices passed
without `gross_amount` are listed under `gross_not_checked`. Invoices of mixed sign are
listed under `sign_review` (above).

**What `line_role` can and cannot see.** A role the writer recorded wins: the AP
invoice and credit memo writers record their payable row as `control` and the reversal
of an accrued expense as `generated`, on bills posted since that change (older rows are
not relabelled). Without a recorded role the read works it out: on an AP or AR invoice,
debit memo or credit memo, a line with no tax code posted to an account whose subtype is
the document's control subtype (`accounts_payable` / `accounts_receivable`) is
`control`, everything else `document`. Consequences:

- The reversal of an accrued expense for goods received earlier, which the AP invoice
  writer adds to a bill as a line ("Reverse … accrual (GRNI)", no tax code, so
  `vat_report` never sees it), is also added to the header total. On a newer bill it
  reads as `generated`: the net is the bill's own, and the gross tie shows a difference
  of the amount reversed. On an older bill it reads as `document`: the net is too high
  by that amount and the gross tie passes. Either way the header's
  `metadata.accrual_reversal` (returned by `get_entity`, not by the list query) shows
  it, and such an invoice goes to a person.
- An untaxed business line posted to the control account itself reads as `control`.
  It is then missing from the net, so the gross tie shows a difference of its amount.

Then run:

```
python3 scripts/generate_kmd.py --select-inf invoices_A.json --side A
python3 scripts/generate_kmd.py --select-inf invoices_B.json --side B
```

Each invoice object: `partner_key` (the ERP `customer_id` / `vendor_id`),
`document_type` (required: `AR_INVOICE` / `AR_CREDIT_MEMO` for part A, `AP_INVOICE` /
`AP_CREDIT_MEMO` for part B), `currency` (required, must be `"EUR"`), `partner_name`,
`registry_code`,
`registry_code_verified`, `non_resident`, `partner_kind`, `invoice_number`,
`invoice_date`, `net_amount` (required), `vat_amount`, `has_positive_rate_supply`
(required, true/false), `line_nets` (always pass it), `cross_border_reverse_charge`
(part B only), `gross_amount` (the header `amount`; always pass it; it makes
`vat_amount` required), `reverse_charge_vat_amount`, `gross_mismatch_reviewed` (only a
person sets it), optional
`travel_special_procedure_only`, `professional_secrecy`, `counted_in_earlier_period`,
and for part B `vat_deducted_in_period` (required: the input VAT this invoice puts into
KMD line 5 this period, `0` when none). Amounts are numbers with a dot decimal; a
missing, null or non-numeric amount is refused, never read as zero. The limit is per
transaction partner, not per ERP record: records that carry the same register code
(two customer cards for one company) are combined into one partner, listed in
`partner_keys` and `partner_names`. The group is declared only when every invoice in it
carries the same verified code; a group that reaches the limit with an unverified or
conflicting code goes to `needs_registry_code`. Records are never merged by name. The output lists `declare`, `needs_registry_code`, `below_threshold`,
`excluded` (with the reason), `sign_review` (mixed-sign invoices and negative part B
deductions, with their figures), `reverse_charge_review` (cross-border reverse charge
with supplier VAT on the same invoice), `rate_review` (a line rate outside the annex
rates), `gross_reviewed` (differences a person accepted,
with the reason), `gross_not_checked` (invoices passed without `gross_amount`) and
`lines_not_checked` (invoices passed without `line_nets`). Do **not** aggregate the header `amount` for the limit with
`query("transaction", group_by=..., aggregates={"amount": "sum"})`: that is the gross
amount, and it mixes in invoices the instructions exclude.

## Partner register code (column 2)

Column 2 is "the register code assigned to the transaction partner, including a
self-employed person, in Estonia"; for non-residents, the register code assigned in the
register of taxable persons (Taxation Act § 17); for notaries and bailiffs, their
personal ID code (KMD INF instructions, part A and part B, column 2). **A VAT number
is not a register code** (an Estonian VAT number `EE10…` is a different number from the
8-digit registry code), and `generate_kmd.py` refuses a reg-code value with a country
prefix.

Where ARTIFI stores it:

- **Customers**: `master_customers.tax_id` holds the registry / company code; the VAT
  number lives on the entity-level customer tax profile (`customer_tax_profiles.vat_number`).
  This is the convention the invoice PDF uses (`resolve_customer_tax_identifiers`:
  `tax_id` prints as "Reg.", `vat_number` as "VAT").
- **Vendors**: there is **no dedicated registry-code field**. `master_vendors.tax_id`
  accepts an EIN, an EU VAT number or a generic code, so it is often a VAT number.
- Either record may carry an organisation-defined custom field for the registry code
  (check `query("custom_field")` for one on customer / vendor).

Treat a value as the partner's register code only when **all** hold:

1. It comes from that partner's own record (`tax_id` for a customer, or a registry-code
   custom field) — never from another company with a similar name.
2. It has no country prefix and has the Estonian form (8-digit registry code, or an
   11-digit personal ID code for a notary / bailiff / self-employed person). A
   vendor's `tax_id` qualifies only if it is in this form; an `EE…` value is a VAT number.
3. It is confirmed by the partner's own document (the code printed on the invoice) or
   the e-Business Register (ariregister.rik.ee) — say which in the review list.

A partner that reaches the threshold without a verified register code goes on a **review
list for a person to resolve** (`needs_registry_code` in the selection output). Never
fill it from the VAT number, by stripping a prefix, or from another company's record. If
the person confirms the partner is a non-resident with no register code assigned in
Estonia, its invoices are not declared (instructions, column 2). Omitting a code is not a
failure to file if EMTA can identify the partner from the data given (KMD INF
instructions, introduction), but filing a wrong code is a wrong declaration.

## Structure

The form is filled **invoice by invoice** (KMD INF instructions, parts A and B).

### Part A — Invoices issued (`salesAnnex`)

| Col | KMD2 element | Content | Source |
|---|---|---|---|
| 2 | `buyerRegCode` | Register code / personal ID code (see above) | verified register code |
| 3 | `buyerName` | Partner name | `customer.customer_name` |
| 4 | `invoiceNumber` | Invoice number | `transaction_number` / invoice number on the document |
| 5 | `invoiceDate` | Invoice date | `transaction_date` |
| 6 | `invoiceSum` | Invoice total **without VAT**, incl. 0 %/exempt parts | Σ `document` line net |
| 7 | `taxRate` | Rate classifier (`24`, `13`, `9`, `5`, special-procedure variants) | tax code |
| 8 | `invoiceSumForRate` | Taxable value stated on the invoice — **cash-accounting taxpayers only** | only if `cash_accounting: true` |
| 9 | `sumForRateInPeriod` | Part declared in KMD lines 1, 1¹, 1², 2, 2¹, 2² this period; **empty for a § 41¹ seller** (code 02) | Σ `document` line net at that rate (signed; a code-03 invoice's `rate_rows`) |
| 10 | `comments` | Special code: 01 (§ 41/§ 42 special procedure), 02 (§ 41¹, buyer accounts the VAT), 03 (invoice also has 0 %/exempt/non-supply, or two or more rates incl. negative supply) | tax codes |

Part A is declared for the period in which the invoice's supply is incurred (VAT Act
§ 11); if supply on the same invoice is also incurred in a later period, the invoice is
declared again in that period. Selecting invoices by `transaction_date` assumes the
supply date and the invoice date fall in the same period; flag invoices where they do
not (gate check 3).

Up to 4 lines per invoice (one per rate group); every column is filled on each line, so
column 6 repeats the invoice total. Credit invoices, and an invoice reducing the taxable
value under VAT Act § 29¹, are entered with a minus sign (KMD INF instructions, part A).

**§ 41¹ seller (domestic reverse charge):** column 6 = the invoice total without VAT,
column 7 = the rate (24), column 9 empty, code 02; the supply is declared on KMD line 9
(`supplySpecialArrangements`), not lines 1–2² (KMD INF instructions, part A column 9;
part A example: metal scrap 1400, rate 24 %, column 9 empty, code 02). `generate_kmd.py`
warns about a code-02 line that fills column 9 rather than refusing it: the
instructions put general-procedure and § 41¹ supply at 24 % on the same row, and a
person confirms what column 9 holds for an invoice that carries both. Codes 01/02 and
03 can stand together on one row ("Kui ühel arvel on enam kui üks erisus, märgitakse
mitu erisuse koodi").

### Part B — Invoices received (`purchasesAnnex`)

| Col | KMD2 element | Content | Source |
|---|---|---|---|
| 2 | `sellerRegCode` | Register code / personal ID code (see above) | verified register code |
| 3 | `sellerName` | Partner name | `vendor.vendor_name` |
| 4 | `invoiceNumber` | Supplier's invoice number | `reference_number` |
| 5 | `invoiceDate` | Invoice date | invoice date on the bill |
| 6 | `invoiceSumVat` | Invoice total **with VAT** as shown on the invoice | Σ (`document` line net + `tax_amount`); for a § 41¹ purchase this includes the VAT the buyer accounts for, so it is **not** the header `amount` (what the supplier is owed) |
| 7 | `vatSum` | VAT stated on the invoice — **cash-accounting taxpayers only**; exceptionally the line-5 amount for a partial deduction (VAT Act § 32 / § 29(4)). The generator requires special code 11 on such a line: that is our derivation (code 11 is the instructions' code for exactly that deduction), not a sentence in the source | only if `cash_accounting: true` or code 11 |
| 8 | `vatInPeriod` | Input VAT declared in KMD line 5 this period | deductible `tax_amount` |
| 9 | `comments` | Special code: 11 (partial deduction, VAT Act § 32 / § 29(4)), 12 (§ 41¹ acquisition, buyer accounts the VAT) | tax codes |

**§ 41¹ buyer (domestic reverse charge):** column 6 = the invoice total with VAT as
shown on the invoice, column 8 = the VAT deducted, code 12 (KMD INF instructions, part B
columns 6 and 9; part B example: metal scrap 1550 incl. VAT 300 → column 6 1550, column 8
300, code 12). Not settled: column 6 when the seller's § 41¹ invoice shows no VAT amount;
list it for a person.

Part B is reported in the period the VAT is deducted in KMD line 5, not by invoice date
alone; a partly deductible or partly paid invoice appears again in later periods when
more is deducted.

### Cash accounting (kassapõhine)

Whether the company applies the special arrangements for cash accounting (VAT Act § 44)
is a fact about the entity that the preparer must establish, not assume — ask the user
or read it from the entity's recorded VAT setup. Record it as `cash_accounting` in the
generator input. For cash-accounting taxpayers, part A uses the period in which the
supply is generated under § 44(3)–(4), and part B lists invoices fully or partly paid in
the period. `generate_kmd.py` refuses `invoiceSumForRate` and `vatSum` unless
`cash_accounting` is `true` (part B special code 11 excepted).

## Reconciliation

- Part A column 9 per rate ≤ the KMD rate lines (1, 1¹, 1², 2, 2¹, 2²); the difference is
  partners below the threshold, natural persons and other excluded invoices.
- Part B column 8 ≤ KMD line 5 (`inputVatTotal`); the difference is the same population.
- List the difference by cause rather than calling it rounding.

## What the sources settle and what goes to a person

Settled (cited above): the limit and exclusions; credit invoices with a minus sign;
part A code 03 for a multi-rate invoice with a negative rate group; part B minus sign
only on a credit invoice or a § 29¹(4) unpaid invoice; cross-border reverse charge not
shown; domestic § 41¹ shown (A: code 02, column 9 empty; B: code 12, column 6 with VAT);
an invoice declared by mistake is re-entered with zero amounts.

Not settled by the official text found — **list for a person, do not add or remove
annex lines on your own**:

- a negative line at a single rate, an invoice with lines of both signs and a negative
  total, any part B invoice with lines of both signs, an ordinary purchase invoice with
  a negative total;
- code 03 on an invoice with two or more rates and no negative supply: the instructions
  give code 03, EMTA's first part A example (24 % 500 + 9 % 1000) shows none;
- a part A row that holds both general-procedure and § 41¹ supply at 24 %;
- a reverse-charge purchase code with `tax_scope: "import"`;
- a sales line on a § 41¹ code whose `default_rate` is 0 or empty (column 7 needs the
  rate, which the code does not give);
- open question, not decided here: an ordinary sales invoice whose amounts are all
  negative is declared as a credit (minus sign), on the reading that it reduces the
  taxable value (KMD INF instructions, part A: credit invoice and § 29¹ invoice); EMTA
  has no example of a negative ordinary invoice that is neither;
- the part B § 29¹(4) bad-debt case (the selector cannot tell it from an error);
- a cancellation in a later period **without a credit-invoice document** (VAT Act
  § 29(7) puts a cancellation in the period of the cancellation, like a credit invoice,
  but EMTA has no example of how a plain void appears in the annex);
- an invoice issued and voided in the same period before filing (leaving it out is an
  inference, not a sentence in the sources);
- an invoice voided by mistake: zeroed in the original period's form or reversed in
  the current period;
- part B column 6 when a § 41¹ invoice shows no VAT amount.

The annex lists invoices and credit invoices only; payments, set-offs and deposits are
never annex rows, so no minus sign comes from them. (The 23 Nov 2026 EMTA check on
AR-1439 records that set-offs and deposits may not be shown with a minus; that sentence
was not found again in the four sources above.)

## Corrections

Submitted electronically: complete or correct the data and submit the form again. A
line declared by mistake is deleted by resubmitting it with zero amounts (KMD INF
instructions, "Correcting the KMD INF form").

## Format (KMD2)

KMD INF A/B are the `salesAnnex` and `purchasesAnnex` parts of the **single**
`vatDeclaration` document (see `references/kmd-form-structure.md`). There is no
separate `<KMDINF>` file and no `http://emta.ee/schemas/vat` namespace. When no
partner reaches the threshold, set `noSales` / `noPurchases` to `true` in
`declarationBody` and omit the annex entirely.

Feed the generator via the `sales_annex` / `purchases_annex` blocks in the input JSON.
EMTA's instructions say the form is filled invoice by invoice, so prefer per-invoice
mode (`sum_per_partner: false`, below). The XSD also accepts a summed-per-partner mode
(`sum_per_partner: true`), where each line is one partner:

```json
"sales_annex": {
  "sum_per_partner": true,
  "lines": [
    {"buyerRegCode": "87654321", "buyerName": "Customer OÜ",
     "invoiceSum": 13000.00, "taxRate": "24", "sumForRateInPeriod": 13000.00}
  ]
},
"purchases_annex": {
  "sum_per_partner": true,
  "lines": [
    {"sellerRegCode": "11223344", "sellerName": "Vendor AS",
     "invoiceSumVat": 3660.00, "vatInPeriod": 660.00}
  ]
}
```

`generate_kmd.py` renders these into schema-valid `<salesAnnex>` / `<purchasesAnnex>`
elements:

```xml
<salesAnnex>
  <saleLine>
    <buyerRegCode>87654321</buyerRegCode>
    <buyerName>Customer OÜ</buyerName>
    <invoiceSum>13000.00</invoiceSum>
    <taxRate>24</taxRate>
    <sumForRateInPeriod>13000.00</sumForRateInPeriod>
  </saleLine>
</salesAnnex>
<purchasesAnnex>
  <purchaseLine>
    <sellerRegCode>11223344</sellerRegCode>
    <sellerName>Vendor AS</sellerName>
    <invoiceSumVat>3660.00</invoiceSumVat>
    <vatInPeriod>660.00</vatInPeriod>
  </purchaseLine>
</purchasesAnnex>
```

Per-invoice mode, the one EMTA's instructions describe: set `sum_per_partner: false`
and add `invoiceNumber` + `invoiceDate` to each line (up to 4 lines per invoice, one per
rate group). Mandatory fields
per the XSD: A → `invoiceSum`, `taxRate`; B → `invoiceSumVat`, `vatInPeriod`.
