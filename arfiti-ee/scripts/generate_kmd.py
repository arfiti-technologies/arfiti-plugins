"""
generate_kmd.py — Generate the Estonian VAT return (KMD) in the official KMD2 format.

Produces two artifacts for a single legal entity and period:

  1. KMD_YYYYMM_{REGCODE}.csv           — the KMD2 machine CSV (e-MTA's fixed-column
                                          upload format). **PRIMARY ARTIFACT.**
  2. vatDeclaration_YYYYMM_{REGCODE}.xml — the KMD2 XML: general part + main form
                                          (declarationBody) + KMD INF A/B annexes
                                          (salesAnnex / purchasesAnnex). Validated
                                          against the bundled vatdeclaration.xsd
                                          before it is written.

The KMD2 format is defined by e-MTA:
  Technical info : https://www.emta.ee/en/business-client/e-services-training-courses/how-use-e-services/technical-information-services
  XSD (07.2025+) : https://ncfailid.emta.ee/s/W5ncAiYRyye2of3/download/vatdeclaration.xsd
  Format desc.   : https://www.emta.ee/media/1096/download

Key facts (verified against the bundled XSD and e-MTA's own examples
`vatdeclaration_example6.csv` and the Hala `KMD_202606_14276473.csv`):

  * Root element `vatDeclaration`, NO XML namespace. The old
    `<KMD xmlns="http://emta.ee/schemas/vat">` output was fabricated and is gone.
  * General part order: taxPayerRegCode, submitterPersonCode (optional; required for
    the machine interface), year, month, declarationType (1=normal), version.
    `version` is period-dependent: KMD4 for 2024, KMD5 for 01.2025–06.2025,
    KMD6 from 07.2025 onward.
  * declarationBody holds taxable BASES by rate (transactions24 first, from 07.2025),
    plus zero-rated / EU / export bases, `inputVatTotal` (line 5, a VAT amount), the
    EU-acquisition / other-acquisition (reverse charge) bases, and adjustments. There
    are NO Line1_1 / Line4 / Line12 elements — e-MTA computes total VAT (line 4),
    VAT due (line 12) and overpaid (line 13) itself.
  * The machine CSV is a fixed-column, 31-field-per-row, semicolon-separated file with
    CRLF line endings, dot decimals and TRUE/FALSE flags. Row types: `header` (general
    part), the version row (declarationBody), `A` rows (salesAnnex saleLine), `B` rows
    (purchasesAnnex purchaseLine, dates as DD.MM.YYYY). It carries NO total-VAT or
    payable columns — do not emit them. This is NOT the English prose-header human
    export, which e-MTA rejects.

Reverse charge (corrected 2026-07-13 per EMTA's official completion guidance,
kaibedeklaratsiooni-taitmine): the KMD declares taxable transactions BY RATE
"sealhulgas kauba ühendusesisene soetamine … teenuste saamine (pöördmaksustamine)" —
reverse-charge / IC-acquisition bases belong INSIDE the rate lines (transactions24
for 24%), which is what drives e-MTA's line 4 (self-assessed output VAT), and the
deductible side goes into `inputVatTotal` (line 5). Lines 6 / 6.1 / 7 / 7.1 are
"informatiivsed lahtrid" (informative cells): fill them with the acquisition
breakout, but they do NOT drive the calculation — a base that appears only there
never enters the return's arithmetic. For a full-deduction taxpayer the RC output
(in line 4) and deduction (in line 5) cancel; a partial-deduction taxpayer puts
only the deductible portion in line 5 while line 4 still carries the full
self-assessed VAT. validate() rejects inputs whose positive acquisition parts
(line 6.1, line 6 - 6.1, line 7.1, line 7 - 7.1, each counted separately) exceed the rate-line bases (the acquisitions cannot then be inside the rate
lines). The rate lines are signed, so a month of credits only is a negative base,
not an error (AR-1473); with acquisitions and negative rate-line rows in one month
the input states those rows' sum (`rate_line_negative_bases`), the acquisitions are
compared with the positive part, and the stated figure is printed for the person.

NOTE: an earlier version of this script prescribed the opposite ("bases only on
6/7, never grossed") — for full-deduction taxpayers both conventions produce the
same line 12/13, which is why filings under the old rule were still accepted.

KMD INF annex (AR-1399, per EMTA "Instructions for filling in the appendix (form
KMD INF)", vorm_kmd_inf_2025_07_eng.pdf, and the EMTA page "Filing VAT returns and
reports"):

  * Partner threshold: the invoices' total WITHOUT VAT per transaction partner per
    taxation period is "at least 1,000 euros" (inclusive), counted separately for
    invoices issued (part A) and received (part B), and separately for ordinary
    invoices and for credit invoices. Only invoices containing supply at 24/13/9 %
    (in exceptional cases 22/20/5 %) count; an invoice with only 0 %, exempt or
    non-supply amounts does not. `select_inf_partners()` / `--select-inf` apply this.
  * Column 8 of part A (`invoiceSumForRate`) and column 7 of part B (`vatSum`) are
    "filled in by taxable persons using cash-accounting for value added tax". The
    input therefore states `cash_accounting` explicitly; validate() refuses either
    field unless it is true. Exception (part B col 7 text): a partial deduction under
    VAT Act § 32 / § 29(4) may present the amount; the line must then carry special
    code 11 in `comments` (code 11 is the instructions' own code for that partial
    deduction, so requiring it is our derivation, not a sentence in the source).
  * Column 2 is the partner's Estonian register code or personal ID code, never a
    VAT number: validate() refuses a reg-code value with a country prefix.
  * AR-1439 (EMTA KMD INF form and instructions 07.2025, Estonian text
    vorm_kmd_inf_2025_07.pdf; EMTA part A / part B examples 11.12.2025; EMTA page
    "Käibedeklaratsiooni lisa täitmine"): cross-border reverse-charge purchases are
    not reported; a negative part B deduction on an ordinary invoice goes to a person;
    a part A invoice with two or more rates incl. a negative rate group is declared
    with code 03; a part A § 41¹ line (code 02) with column 9 filled is warned about.
  * AR-1439 approved treatments (Andrew, 2026-11-24; "recommended" = EMTA's text is
    silent, see references/kmd-inf-annex.md): (1) a sales invoice's cancellation in a
    later period without a credit invoice is a minus row in the cancellation period
    when it refers to the original invoice and cancels the transaction (VAT Act § 29(7)
    on the period; a cancelled purchase invoice goes to a person); (2) a sales invoice
    issued and cancelled in the same period is left out with its
    cancellation when no turnover arose; (3) an invoice issued by mistake is corrected
    in its own period (§ 27(5)), so a cancellation whose reason is not recorded goes to
    a person; (4) § 41¹ invoices count toward the limit (unchanged); (5) a negative
    ordinary sales invoice is a minus row only when it refers to an original invoice;
    (6a) a single-rate sales invoice with lines of both signs is one row, no code;
    (6b) an ordinary part B invoice with lines of both signs is one row, net amounts. Every case
    whose deciding fact is absent goes to a person (`cancellation_review`,
    `sign_review`).

Usage:
    python3 generate_kmd.py --input /tmp/kmd_data_14276473.json --output /tmp/
    python3 generate_kmd.py --select-inf invoices.json --side A   # KMD INF partner selection

Input JSON format: see input_schema_kmd.json (real KMD2 element names).
"""

import argparse
import json
import re
import subprocess
import sys
import tempfile
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Bundled official schema, kept next to this script so validation works offline.
XSD_PATH = Path(__file__).resolve().parent / "vatdeclaration.xsd"

TOLERANCE = Decimal("0.02")

# declarationBody child elements in the exact order the XSD requires (and the exact
# order the machine CSV's 26 body columns use), omitting the obsolete selfSupply20 /
# selfSupply9. The two car-count fields are integers; everything else is a 2-decimal
# monetary value. This list is a strict subsequence of the XSD sequence, so emitting
# the present elements in this order is schema-valid.
BODY_ELEMENTS: List[str] = [
    "transactions24",                       # line 1   (24%, valid from 07.2025)
    "transactions22",                       # line 1²  (22%, from 07.2025; line 1 for 01.2024-06.2025)
    "transactions20",                       # line 1¹  (20%)
    "transactions9",                        # line 2   (9%)
    "transactions5",                        # line 2¹  (5%)
    "transactions13",                       # line 2²  (13%, valid from 01.2025)
    "transactionsZeroVat",                  # line 3   (0%)
    "euSupplyInclGoodsAndServicesZeroVat",  # line 3.1
    "euSupplyGoodsZeroVat",                 # line 3.1.1
    "exportZeroVat",                        # line 3.2
    "salePassengersWithReturnVat",          # line 3.2.1
    "inputVatTotal",                        # line 5   (total deductible input VAT)
    "importVat",                            # line 5.1 (import VAT paid in customs)
    "fixedAssetsVat",                       # line 5.2 (input VAT on fixed assets)
    "carsVat",                              # line 5.3 (input VAT on 100% cars)
    "numberOfCars",                         # line 5.3 (count, integer)
    "carsPartialVat",                       # line 5.4 (input VAT on partial cars)
    "numberOfCarsPartial",                  # line 5.4 (count, integer)
    "euAcquisitionsGoodsAndServicesTotal",  # line 6   (EU acquisitions + services)
    "euAcquisitionsGoods",                  # line 6.1
    "acquisitionOtherGoodsAndServicesTotal",# line 7   (non-EU services + reverse charge)
    "acquisitionImmovablesAndScrapMetalAndGold",  # line 7.1
    "supplyExemptFromTax",                  # line 8
    "supplySpecialArrangements",            # line 9
    "adjustmentsPlus",                      # line 10  (+ adjustment, non-negative)
    "adjustmentsMinus",                     # line 11  (- adjustment, non-negative)
]

# KMD INF partner threshold (EMTA KMD INF instructions 2025-07, "Accounting the limit
# per transaction partner"): total WITHOUT VAT per partner per period, "at least
# 1,000 euros" — inclusive, so exactly 1000.00 qualifies.
INF_THRESHOLD = Decimal("1000.00")

# A VAT number starts with a two-letter country prefix (EE123456789). KMD INF column 2
# takes the partner's register code or personal ID code assigned in Estonia, so a value
# shaped like a VAT number is refused rather than filed.
VAT_NUMBER_RE = re.compile(r"^[A-Za-z]{2}\s*[0-9A-Za-z]")

# Part B special code 11: partial deduction of input VAT (VAT Act § 32 or § 29(4)).
# The only case in which a non-cash-accounting taxpayer may fill column 7 (vatSum).
PARTIAL_DEDUCTION_SPECIAL_CODE = "11"

INTEGER_ELEMENTS = {"numberOfCars", "numberOfCarsPartial"}
ANNEX_AMOUNT_FIELDS = ("invoiceSum", "invoiceSumForRate", "sumForRateInPeriod",
                       "invoiceSumVat", "vatSum", "vatInPeriod")
NON_NEGATIVE_ELEMENTS = {"adjustmentsPlus", "adjustmentsMinus"}

# Every machine-CSV row is padded to this many semicolon-separated fields.
CSV_FIELDS = 31

# Standard VAT rates that feed the computed "total VAT" (line 4) shown in the console
# summary. The rate-line bases INCLUDE reverse-charge / IC acquisitions (see module
# docstring); lines 6 / 7 are informative breakouts and are intentionally not here.
LINE4_RATES: Dict[str, Decimal] = {
    "transactions24": Decimal("0.24"),
    "transactions22": Decimal("0.22"),
    "transactions20": Decimal("0.20"),
    "transactions9":  Decimal("0.09"),
    "transactions5":  Decimal("0.05"),
    "transactions13": Decimal("0.13"),
}

REVERSE_CHARGE_BASE_ELEMENTS = (
    "euAcquisitionsGoodsAndServicesTotal",
    "acquisitionOtherGoodsAndServicesTotal",
)


# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #
def dec(value) -> Decimal:
    """Coerce any input (None/str/number) to a Decimal, treating None/'' as 0."""
    if value is None or value == "":
        return Decimal("0")
    return Decimal(str(value))


def is_number(value) -> bool:
    """True for an int/float/Decimal or a numeric string ("1000.00"); False for bools,
    None, "" and text such as "1,000.00" that Decimal cannot parse."""
    if isinstance(value, bool) or value is None:
        return False
    try:
        parsed = Decimal(str(value))
        if not parsed.is_finite():
            return False
        parsed.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError, TypeError):
        return False
    return True


def is_integer(value) -> bool:
    """True for a whole number (int, or a numeric string / Decimal without a fraction)."""
    return is_number(value) and Decimal(str(value)) == Decimal(str(value)).to_integral_value()


def required_amount(record: dict, key: str, label: str) -> Decimal:
    """Read a required monetary field, refusing a missing, null or non-numeric value
    instead of treating it as 0.00 (a silent zero can drop a partner below the KMD INF
    limit and the annex from the filing)."""
    if key not in record:
        raise ValueError(f"{label}: {key} is required")
    if not is_number(record[key]):
        raise ValueError(f"{label}: {key} must be a number with a dot decimal, got {record[key]!r}")
    return q2(record[key])


def q2(value) -> Decimal:
    """Quantize to 2 decimals, half-up."""
    return dec(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def amount(value) -> str:
    """Monetary value: 2 decimals, dot separator (e.g. '910.00'). Used by CSV and XML."""
    return f"{q2(value):.2f}"


def esc(text) -> str:
    """Escape XML special characters."""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def xml_flag(value: bool) -> str:
    return "true" if value else "false"


def csv_flag(value: bool) -> str:
    return "TRUE" if value else "FALSE"


def csv_date(value) -> str:
    """Convert an ISO date (YYYY-MM-DD, as the XML uses) to the CSV's DD.MM.YYYY."""
    text = str(value or "").strip()
    if not text:
        return ""
    parts = text.split("-")
    if len(parts) == 3 and len(parts[0]) == 4:
        year, month, day = parts
        return f"{int(day):02d}.{int(month):02d}.{year}"
    return text  # already DD.MM.YYYY or unrecognised — pass through unchanged


def compute_version(year: int, month: int) -> str:
    """
    Return the mandatory KMD2 version string for the given period.

    Per the XSD: KMD4 for 01.2024–12.2024, KMD5 for 01.2025–06.2025,
    KMD6 from 07.2025 onward.
    """
    period = year * 100 + month
    if period >= 202507:
        return "KMD6"
    if period >= 202501:
        return "KMD5"
    if period >= 202401:
        return "KMD4"
    raise ValueError(
        f"Period {year}-{month:02d} predates the KMD2 format (valid from 01.2024)"
    )


def compute_totals(body: dict) -> Dict[str, Decimal]:
    """
    Compute line 4 (total VAT), line 12 (VAT due) and line 13 (overpaid) the way e-MTA
    does — for the console summary only. These are NOT emitted in the CSV or XML.

    line 4  = Σ(base × rate) over the six standard-rate lines, which include the
              reverse-charge / IC-acquisition bases (informative lines 6/7 are not
              added again).
    net     = line4 + adjustmentsPlus − inputVatTotal − adjustmentsMinus.
    line 12 = max(0, net)   (payable);  line 13 = max(0, −net)   (overpaid).
    """
    line4 = sum((q2(body.get(key, 0)) * rate for key, rate in LINE4_RATES.items()),
                Decimal("0")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    net = (
        line4
        + q2(body.get("adjustmentsPlus", 0))
        - q2(body.get("inputVatTotal", 0))
        - q2(body.get("adjustmentsMinus", 0))
    )
    return {
        "_line4": line4,
        "_line12": max(Decimal("0"), net),
        "_line13": max(Decimal("0"), -net),
    }


# --------------------------------------------------------------------------- #
# Validation (structural; the XSD is the authority for the XML)
# --------------------------------------------------------------------------- #
def validate(data: dict) -> List[str]:
    """Validate input data structurally. Returns a list of error strings."""
    errors: List[str] = []

    if not isinstance(data, dict):
        return ["the input must be a JSON object"]
    if not data.get("regcode"):
        errors.append("regcode is required")
    year, month = data.get("year"), data.get("month")
    if not is_integer(year):
        errors.append("year is required and must be a whole number")
    if not is_integer(month) or not (1 <= int(Decimal(str(month))) <= 12):
        errors.append("month is required and must be 1-12")
    elif is_integer(year) and (int(Decimal(str(year))) * 100 + int(Decimal(str(month)))) < 202401:
        errors.append(
            f"period {year}-{int(Decimal(str(month))):02d} predates the KMD2 format "
            "(valid from 01.2024)"
        )

    dtype = data.get("declaration_type", 1)
    if not is_integer(dtype) or int(Decimal(str(dtype))) not in (1, 2):
        errors.append("declaration_type must be 1 (normal) or 2 (bankruptcy)")

    for key in ("expected_vat_payable", "expected_vat_overpaid"):
        if data.get(key) is not None and not is_number(data[key]):
            errors.append(f"{key} must be a number with a dot decimal, got {data[key]!r}")

    body = data.get("declaration_body", {})
    if not isinstance(body, dict):
        errors.append("declaration_body must be an object")
        body = {}

    # No fabricated Line1_1/Line4/Line12 keys, and no removed importVatPayable field.
    stale = [k for k in body if k.lower().startswith("line") or k == "importVatPayable"]
    if stale:
        errors.append(
            "declaration_body uses removed keys "
            f"({', '.join(sorted(stale))}); use KMD2 element names "
            "(transactions24, inputVatTotal, …) — see input_schema_kmd.json"
        )

    unknown = [k for k in body if k not in BODY_ELEMENTS and not k.lower().startswith("line")
               and k != "importVatPayable"]
    if unknown:
        errors.append(
            f"declaration_body has unknown element(s): {', '.join(sorted(unknown))}"
        )

    # A present value must be numeric: an absent element means "line does not apply",
    # but text such as "1,000.00" must be refused, not crash or become 0. The count
    # fields must be whole numbers (they were truncated before).
    bad = [k for k, v in body.items() if v not in (None, "") and not is_number(v)]
    errors += [
        f"declaration_body.{k} must be a number with a dot decimal, got {body[k]!r}"
        for k in sorted(bad)
    ]
    fractional = [k for k in INTEGER_ELEMENTS
                  if k in body and k not in bad and body[k] not in (None, "")
                  and not is_integer(body[k])]
    errors += [f"declaration_body.{k} must be a whole number, got {body[k]!r}"
               for k in sorted(fractional)]
    if bad or fractional:
        # The checks below compare body values; with a value missing they would report
        # a structural problem the return may not have.
        errors += _validate_annex(data.get("sales_annex"), "sales_annex",
                                  "buyerRegCode", "buyerName", "invoiceSum", "taxRate")
        errors += _validate_annex(data.get("purchases_annex"), "purchases_annex",
                                  "sellerRegCode", "sellerName", "invoiceSumVat",
                                  "vatInPeriod")
        errors += _validate_cash_accounting_columns(data)
        return errors

    for key in NON_NEGATIVE_ELEMENTS:
        if key in body and dec(body[key]) < 0:
            errors.append(f"declaration_body.{key} must be >= 0")

    # Line 6.1 (goods) is part of line 6 (goods and services); the services part is
    # line 6 - 6.1. A positive 6.1 above line 6 is refused, as before AR-1473. A
    # negative 6.1 (an EU supplier's goods credit) is not compared: inside a credit line
    # 6 it is a smaller-or-equal credit, and beside an EU services purchase it can be
    # below line 6 legitimately (goods -500, services +400, line 6 -100). Netting of
    # goods against services cannot hide an acquisition missing from the rate lines,
    # because the rate-line check counts each positive part separately
    # (_positive_acquisitions). Whether a positive 6.1 above line 6 (goods bought, EU
    # services credited) is declared that way is not settled by the sources; it stays
    # refused for a person.
    goods = dec(body.get("euAcquisitionsGoods", 0))
    line_6 = dec(body.get("euAcquisitionsGoodsAndServicesTotal", 0))
    if goods > TOLERANCE and goods - line_6 > TOLERANCE:
        errors.append(
            "declaration_body.euAcquisitionsGoods (line 6.1) cannot exceed "
            "euAcquisitionsGoodsAndServicesTotal (line 6)"
        )

    errors += _validate_acquisitions_inside_rate_lines(data, body)

    errors += _validate_annex(data.get("sales_annex"), "sales_annex",
                              "buyerRegCode", "buyerName", "invoiceSum", "taxRate")
    errors += _validate_annex(data.get("purchases_annex"), "purchases_annex",
                              "sellerRegCode", "sellerName", "invoiceSumVat",
                              "vatInPeriod")
    errors += _validate_cash_accounting_columns(data)
    return errors


def _positive_acquisitions(body: dict) -> Decimal:
    """The acquisitions declared on lines 6 and 7, each part counted only when
    positive: line 6.1 (EU goods), the rest of line 6 (EU services, line 6 - 6.1),
    line 7.1 (immovables, scrap metal, gold: VAT Act § 41¹) and the rest of line 7
    (line 7 - 7.1). Netting would let a credit in one part (a non-EU supplier's credit,
    an EU services credit) hide acquisitions in another part that are missing from the
    rate lines."""
    zero = Decimal("0")
    total = zero
    for whole_key, part_key in (
            ("euAcquisitionsGoodsAndServicesTotal", "euAcquisitionsGoods"),
            ("acquisitionOtherGoodsAndServicesTotal",
             "acquisitionImmovablesAndScrapMetalAndGold")):
        whole, part = dec(body.get(whole_key, 0)), dec(body.get(part_key, 0))
        total += max(zero, part) + max(zero, whole - part)
    return total


def _stated_negative_bases(data: dict) -> Optional[Decimal]:
    """`rate_line_negative_bases` as a Decimal, None when absent; validated elsewhere."""
    value = data.get("rate_line_negative_bases")
    if value in (None, "") or not is_number(value):
        return None
    return dec(value)


def _validate_acquisitions_inside_rate_lines(data: dict, body: dict) -> List[str]:
    """
    Lines 6/7 are INFORMATIVE breakouts of acquisitions that must also sit inside the
    rate lines (line 1 etc.); that is what produces the self-assessed VAT in e-MTA's
    line 4 (module docstring). When the acquisitions declared on lines 6/7 exceed what
    the rate lines can hold, they cannot be inside them: structural error.

    The rate lines are signed: a credit invoice, a negative line or a cancellation
    reduces the base of the period it is declared in, and the bundled XSD types every
    rate line, line 5 and lines 6/7 as a signed MonetaryValue (only lines 10/11 are
    non-negative). So the comparison is made only where it can find an omission
    (AR-1473):

      * lines 6.1, 6 - 6.1, 7.1 and 7 - 7.1 are each counted only when positive. When
        none is, nothing is
        declared as acquired, so nothing can be missing from the rate lines: a month of
        credits only, or of credits exceeding sales, generates with negative rate lines.
      * a positive part is compared with the rate lines' positive part. The
        input may state `rate_line_negative_bases`: the sum of the negative
        `taxable_amount` rows of vat_report's `output_vat_details` that map to the six
        rate lines, split by acquisition part where one tax name covers several (self-
        assessed reverse charge is on that side already; rows of `input_vat_details`
        are never added). The positive part is the rate-line total
        less that amount. Without it the positive part is the signed total, the
        comparison made before AR-1473.

    The stated figure cannot be checked against the ledger here; it can only be
    bounded (zero or below, at least as negative as the rate lines). main() therefore
    prints it whenever it decided the comparison, for the person to tie to vat_report.
    """
    errors: List[str] = []
    acquisitions = _positive_acquisitions(body)
    rate_total = sum((dec(body.get(k, 0)) for k in LINE4_RATES), Decimal("0"))

    negative = data.get("rate_line_negative_bases")
    if negative in (None, ""):
        negative_bases = Decimal("0")
    elif not is_number(negative):
        return [f"rate_line_negative_bases must be a number with a dot decimal, "
                f"got {negative!r}"]
    else:
        negative_bases = dec(negative)
        if negative_bases > 0:
            errors.append(
                f"rate_line_negative_bases ({negative_bases:.2f}) must be zero or "
                "negative: it is the sum of the negative taxable_amount rows of "
                "vat_report's output_vat_details at the six rate lines, signed"
            )
            return errors
        if rate_total - negative_bases < -TOLERANCE:
            errors.append(
                f"the rate lines total {rate_total:.2f}, but rate_line_negative_bases "
                f"states only {negative_bases:.2f} of negative bases: the rate lines "
                "cannot be more negative than the negative bases inside them. Recheck "
                "both figures against vat_report"
            )
            return errors

    if acquisitions <= 0:
        return errors

    positive_part = rate_total - negative_bases
    if acquisitions - positive_part > TOLERANCE:
        if negative_bases < 0:
            held = (f"the positive part of the rate-line bases ({positive_part:.2f}: "
                    f"total {rate_total:.2f} less rate_line_negative_bases "
                    f"{negative_bases:.2f})")
        else:
            held = f"the rate-line bases ({rate_total:.2f})"
        errors.append(
            f"reverse-charge/IC-acquisition bases on informative lines 6/7 (positive "
            f"lines {acquisitions:.2f}) exceed {held}. Per EMTA guidance the "
            "acquisitions must be INCLUDED in the rate lines (e.g. transactions24); "
            "lines 6/7 are informative only and do not enter the calculation. If the "
            "ledger's acquisitions are missing from the rate lines, include them there "
            "and their deductible VAT in inputVatTotal (line 5). If the rate lines are "
            "lower because vat_report has negative rows at those rates this period "
            "(credit invoices, negative lines, cancellations), state their sum in "
            "rate_line_negative_bases and show those rows to the person. Never add an "
            "acquisition, or change a recorded amount, to pass this check."
        )
    return errors


def negative_bases_notes(data: dict) -> List[str]:
    """The note main() prints when `rate_line_negative_bases` decided the lines 6/7
    comparison: the figure cannot be verified by the script, so the person sees it."""
    body = data.get("declaration_body", {}) or {}
    negative_bases = _stated_negative_bases(data)
    acquisitions = _positive_acquisitions(body)
    if negative_bases is None or negative_bases >= 0 or acquisitions <= 0:
        return []
    rate_total = sum((q2(body.get(k, 0)) for k in LINE4_RATES), Decimal("0"))
    return [
        f"rate_line_negative_bases {q2(negative_bases):.2f} was used: the positive lines "
        f"6/7 ({q2(acquisitions):.2f}) were compared with the rate lines' positive part "
        f"{rate_total - q2(negative_bases):.2f} (total {rate_total:.2f} less the stated "
        "negative bases), not with the total. The script cannot verify that figure. "
        "Show it with the negative output_vat_details rows of vat_report it came from "
        "before filing."
    ]


def domestic_reverse_charge_warnings(data: dict) -> List[str]:
    """
    Warn about a part A line with special code 02 (VAT Act § 41¹ supply, the buyer
    accounts the VAT) that fills column 9 (sumForRateInPeriod). "The party transferring
    goods taxable under the special procedure provided for in § 41¹ ... shall not fill in
    column 9" (EMTA KMD INF instructions 2025-07, part A column 9; part A example: net
    1400, rate 24 %, column 9 empty, code 02 — the supply goes to KMD line 9). A warning,
    not a refusal: the instructions put general-procedure and § 41¹ supply at 24 % on the
    same row, so a row of an invoice carrying both may hold the general part in column 9.
    How such a row is filled is not settled by the sources; a person checks it.
    """
    warnings: List[str] = []
    for i, line in enumerate(_annex_lines(data.get("sales_annex"))):
        if DOMESTIC_REVERSE_CHARGE_SALES_CODE not in _special_codes(line.get("comments")):
            continue
        if _has_value(line.get("sumForRateInPeriod")):
            warnings.append(
                f"sales_annex.lines[{i}]: special code {DOMESTIC_REVERSE_CHARGE_SALES_CODE} "
                "(VAT Act § 41¹ supply) with sumForRateInPeriod (column 9) filled. A § 41¹ "
                "seller leaves column 9 empty (the supply goes to KMD line 9, "
                "supplySpecialArrangements). Column 9 may hold only general-procedure "
                "supply on the same invoice; a person confirms that before filing."
            )
    return warnings


def _has_value(value) -> bool:
    return value not in (None, "")


def _special_codes(comments) -> List[str]:
    """Split a KMD INF special-code cell ("11", "11,12", "11 12") into codes."""
    return [c for c in re.split(r"[\s,;]+", str(comments or "").strip()) if c]


def _annex_lines(annex) -> List[dict]:
    """The annex's line objects; malformed shapes are reported by _validate_annex."""
    if not isinstance(annex, dict) or not isinstance(annex.get("lines"), list):
        return []
    return [line if isinstance(line, dict) else {} for line in annex["lines"]]


def _validate_cash_accounting_columns(data: dict) -> List[str]:
    """
    Refuse the cash-accounting-only annex columns unless the input says the taxpayer
    uses cash accounting (EMTA KMD INF instructions 2025-07: part A column 8 and part B
    column 7 are "filled in by taxable persons using cash-accounting for value added
    tax"). `cash_accounting` must be stated as true; absent or false refuses them.
    Part B column 7 may also be filled for a partial deduction (special code 11).
    """
    errors: List[str] = []
    flag = data.get("cash_accounting")
    if flag is not None and not isinstance(flag, bool):
        return ["cash_accounting must be true or false"]
    on_cash = flag is True
    if on_cash:
        return errors
    state = "false" if flag is False else "not stated"
    for i, line in enumerate(_annex_lines(data.get("sales_annex"))):
        if _has_value(line.get("invoiceSumForRate")):
            errors.append(
                f"sales_annex.lines[{i}]: invoiceSumForRate (KMD INF A column 8) is filled "
                f"only by a cash-accounting taxpayer, but cash_accounting is {state}. "
                "Remove it, or set cash_accounting: true if the company uses cash accounting."
            )
    for i, line in enumerate(_annex_lines(data.get("purchases_annex"))):
        if not _has_value(line.get("vatSum")):
            continue
        if PARTIAL_DEDUCTION_SPECIAL_CODE in _special_codes(line.get("comments")):
            continue
        errors.append(
            f"purchases_annex.lines[{i}]: vatSum (KMD INF B column 7) is filled only by a "
            f"cash-accounting taxpayer, but cash_accounting is {state}. Remove it, set "
            "cash_accounting: true if the company uses cash accounting, or mark a partial "
            f"deduction with special code {PARTIAL_DEDUCTION_SPECIAL_CODE} in comments."
        )
    return errors


def _validate_annex(annex, name, id_field, name_field, *required_fields) -> List[str]:
    """Validate a sales/purchases annex block. Empty/None annex is valid (omitted)."""
    errors: List[str] = []
    if not annex:
        return errors
    if not isinstance(annex, dict):
        return [f"{name} must be an object"]
    lines = annex.get("lines", []) or []
    if not isinstance(lines, list):
        return [f"{name}.lines must be an array"]
    for i, line in enumerate(lines):
        prefix = f"{name}.lines[{i}]"
        if not isinstance(line, dict):
            errors.append(f"{prefix} must be an object")
            continue
        if not line.get(id_field) and not line.get(name_field):
            errors.append(f"{prefix}: at least one of {id_field} / {name_field} is required")
        if line.get(id_field) and VAT_NUMBER_RE.match(str(line[id_field]).strip()):
            errors.append(
                f"{prefix}: {id_field} '{line[id_field]}' looks like a VAT number. KMD INF "
                "column 2 is the register code or personal ID code assigned in Estonia; "
                "never derive it from a VAT number. Resolve the partner's register code "
                "or list the partner for review."
            )
        for field in required_fields:
            if line.get(field) in (None, ""):
                errors.append(f"{prefix}: {field} is required")
        for field in ANNEX_AMOUNT_FIELDS:
            if line.get(field) not in (None, "") and not is_number(line[field]):
                errors.append(
                    f"{prefix}: {field} must be a number with a dot decimal, got {line[field]!r}"
                )
    return errors


def reverse_charge_warnings(data: dict) -> List[str]:
    """
    Return warnings (not errors) about reverse-charge handling. Lines 6/7 are
    informative; the acquisition bases must ALSO be inside the rate lines (line 1)
    and the deductible side inside inputVatTotal (line 5) — see module docstring.
    """
    body = data.get("declaration_body", {}) or {}
    rc = q2(_positive_acquisitions(body))
    if rc <= 0:
        return []
    warnings = [
        f"Reverse-charge bases present (informative lines 6/7 total {rc:.2f}). "
        "Confirm the same bases are INCLUDED in the rate lines (e.g. transactions24) "
        "— that is what produces the self-assessed VAT in e-MTA's line 4 — and that "
        "the deductible side is included in inputVatTotal (line 5). For full "
        "deduction the two cancel; the refund/payable is unchanged."
    ]
    if not bool(data.get("input_vat_full_deduction", True)):
        warnings.append(
            "input_vat_full_deduction is false: include only the DEDUCTIBLE portion "
            "of the self-assessed VAT in inputVatTotal (line 5); line 4 still "
            "carries the full reverse-charge output, so the non-deductible part is "
            "payable. Review the split before filing."
        )
    return warnings


# --------------------------------------------------------------------------- #
# KMD INF partner selection (threshold)
# --------------------------------------------------------------------------- #
INF_EXCLUDED_PARTNER_KINDS = {"natural_person"}
# The KMD INF limit and annex amounts are in euros. The ledger keeps a foreign-currency
# document in its own currency; the invoice list must carry amounts converted to the
# entity's functional currency (EUR) and say so in `currency`.
INF_CURRENCY = "EUR"
# Document types per side. A credit memo's lines are stored positive and the canonical
# tax view negates them (migration 601: -abs(...) for AR/AP_CREDIT_MEMO); the selector
# applies the same rule, so a credit memo always counts toward the credit total.
INF_DOCUMENT_TYPES = {
    "A": {"AR_INVOICE": False, "AR_CREDIT_MEMO": True},
    "B": {"AP_INVOICE": False, "AP_CREDIT_MEMO": True},
}
# Gross tie: when an invoice carries the document's own total (`gross_amount`, the
# header amount: what the supplier is owed or the customer owes), its net plus the VAT
# on top must equal it. Reverse-charge VAT (`reverse_charge_vat_amount`) is self-
# assessed, not part of that total, so it is left out. A net that counted a generated
# control row (the "Accounts Payable" line, worth the whole document total) fails by
# the whole document total. The tolerance covers converting the four amounts (net,
# VAT, reverse-charge VAT, gross) to EUR separately, each rounded to cents.
# Signed, with a credit memo's net turned back to the document's sign (see
# gross_mismatch). A mismatch a person has reviewed and accepted
# (`gross_mismatch_reviewed`: the reason, e.g. a non-recoverable reverse-charge bill
# whose header amount includes the self-assessed VAT) is reported under
# `gross_reviewed` instead of refusing.
INF_GROSS_TOLERANCE = Decimal("0.02")
BOOLEAN_INVOICE_FLAGS = (
    "has_positive_rate_supply", "registry_code_verified", "non_resident",
    "travel_special_procedure_only", "professional_secrecy", "counted_in_earlier_period",
    "cross_border_reverse_charge", "import_reverse_charge",
)
# Part A special code 03 (KMD INF instructions 07.2025, part A column 10): the invoice
# contains supply at two or more rates "incl. negative supply" ("sealhulgas negatiivset
# käivet"). EMTA's part A examples (11.12.2025) show it: invoice 1500 = 24 % 2000 and
# 9 % −500, two rows, column 6 = 1500 on both, column 9 = 2000 and −500, code 03.
MIXED_RATE_SPECIAL_CODE = "03"
# Up to 4 lines are declared per invoice in part A (KMD INF instructions, part A).
MAX_PART_A_LINES_PER_INVOICE = 4
# Part A special code 02 (VAT Act § 41¹ supply, the buyer accounts the VAT). "The party
# transferring goods taxable under the special procedure provided for in § 41¹ ... shall
# not fill in column 9" (KMD INF instructions, part A column 9).
DOMESTIC_REVERSE_CHARGE_SALES_CODE = "02"
# The rates whose supply the annex covers (KMD INF instructions 07.2025: 24 %, 13 %,
# 9 %, in exceptional cases 22 %, 20 % and 5 %). A line_nets rate is canonicalised
# ("24.00" -> "24", see _line_rate) so one rate cannot be spelled two ways and pass as
# two rate groups. A 0 %, exempt or untaxed line has rate null; a zero rate is refused.
# A positive rate outside this set sends the invoice to a person (`rate_review`). A
# special-procedure line (§ 41/§ 42/§ 41¹) carries its rate and "special_procedure".
ANNEX_LINE_RATES = {"24": Decimal("0.24"), "22": Decimal("0.22"), "20": Decimal("0.20"),
                    "13": Decimal("0.13"), "9": Decimal("0.09"), "5": Decimal("0.05")}
# The line tie allows a cent per line for separate EUR roundings, up to this much.
LINE_NETS_MAX_TOLERANCE = Decimal("0.10")


def _line_nets(inv: dict, label: str) -> Optional[List[Tuple[Optional[str], Decimal, bool]]]:
    """The invoice's document-line nets as (rate, signed net, special procedure), or None.

    `line_nets` is a list of {"rate": <column-7 rate value, e.g. "24" or "9", for a line
    whose tax code is at 24/22/20/13/9/5 %; null for a 0 %, exempt or untaxed line>,
    "net_amount": <the line's net in EUR, in the document's own sign>}. A credit memo's
    lines are stored positive, so a credit memo line enters positive here and a negative
    one is a negative line on the credit memo. Optional "special_procedure": true marks a
    line under a special procedure (VAT Act § 41/§ 42 margin scheme, or § 41¹ domestic
    reverse charge), whose part A row carries code 01 or 02 as well.
    """
    raw = inv.get("line_nets")
    if raw is None:
        return None
    if not isinstance(raw, list) or not raw:
        raise ValueError(f"{label}: line_nets must be a non-empty array of "
                         "{rate, net_amount} objects")
    out: List[Tuple[Optional[str], Decimal, bool]] = []
    for i, line in enumerate(raw):
        if not isinstance(line, dict):
            raise ValueError(f"{label}: line_nets[{i}] must be an object")
        rate = _line_rate(line.get("rate"), f"{label}: line_nets[{i}].rate")
        value = required_amount(line, "net_amount", f"{label} line_nets[{i}]")
        special = line.get("special_procedure", False)
        if not isinstance(special, bool):
            raise ValueError(f"{label}: line_nets[{i}].special_procedure must be true or "
                             f"false, got {special!r}")
        out.append((rate, value, special))
    return out


def _line_rate(raw, where: str) -> Optional[str]:
    """A line_nets rate as a canonical number string, or None for a 0 %/exempt line.

    The ERP returns a tax code's `default_rate` as a decimal, so "24", "24.0", "24.00"
    and 24 are the same rate and all become "24". A zero rate ("0", "0.00") is refused:
    a 0 %, exempt or untaxed line is passed as null, so a zero-rated line cannot pass as
    a rate group. A positive rate outside the annex rates (e.g. an organisation's own
    21 %) is returned as is; the selector sends that invoice to a person
    (`rate_review`) instead of stopping the whole selection. Anything that is not a
    number is refused.
    """
    if raw is None:
        return None
    if isinstance(raw, bool) or not isinstance(raw, (str, int, float)):
        raise ValueError(f"{where} must be the tax code's rate as a number, or null for a "
                         f"0 %, exempt or untaxed line, got {raw!r}")
    try:
        value = Decimal(str(raw).strip())
    except InvalidOperation:
        raise ValueError(f"{where} must be the tax code's rate as a number, or null for a "
                         f"0 %, exempt or untaxed line, got {raw!r}") from None
    if not value.is_finite() or value < 0:
        raise ValueError(f"{where} must be a positive rate, or null, got {raw!r}")
    if value == 0:
        raise ValueError(f"{where} is a zero rate ({raw!r}): pass a 0 %, exempt or untaxed "
                         "line with rate null")
    if value == value.to_integral_value():
        return str(int(value))
    return format(value.normalize(), "f")


def line_nets_mismatch(lines: List[Tuple[Optional[str], Decimal, bool]], document_net: Decimal,
                       label: str) -> Optional[str]:
    """Describe line nets that do not add up to the invoice's net, or None.

    Each line converted to EUR and rounded separately may differ from the invoice's net
    by a cent per line, up to LINE_NETS_MAX_TOLERANCE.
    """
    total = sum((v for _r, v, _sp in lines), Decimal("0.00"))
    tolerance = max(INF_GROSS_TOLERANCE,
                    min(Decimal("0.01") * len(lines), LINE_NETS_MAX_TOLERANCE))
    if abs(total - document_net) <= tolerance:
        return None
    return (f"{label}: line_nets add up to {total:.2f}, the invoice's net is "
            f"{document_net:.2f}")


def mixed_rate_rows(lines: List[Tuple[Optional[str], Decimal, bool]],
                    vat: Optional[Decimal]) -> Tuple[Optional[List[dict]], Optional[str]]:
    """Part A rows for an ordinary sales invoice whose lines carry both signs.

    Lines of both signs at ONE rate (no 0 %/exempt part) are handed to single_rate_row
    (AR-1439 recommended treatment: one row, signed net, no code). Otherwise returns
    (rows, None) — one row per rate, signed net, document order — when the
    invoice is the case EMTA's instructions and examples settle: supply at two to four
    rates, a negative rate group among them, no negative 0 %/exempt/untaxed line, no
    rate whose lines carry both signs (on a multi-rate invoice that is not settled by
    the sources), every line under the general procedure (a § 41/§ 42/§ 41¹ line
    needs codes this tool does not assign, and a § 41¹ net stays out of column 9), and
    the invoice's VAT equal to Σ rate-group net × rate (so a line cannot carry another
    rate's label). Otherwise (None, the reason a person decides). Zero-net lines carry
    no sign and are left out. The caller checks the document type, that the invoice's
    net is above zero and (sign_inconsistency) that its VAT and total are not negative.
    """
    def person(why: str) -> Tuple[None, str]:
        return None, (f"invoice with negative lines: {why}; EMTA's instructions do not "
                      "settle how it is shown, a person decides")

    def check_data(why: str) -> Tuple[None, str]:
        return None, (f"invoice with negative lines: {why}; a person checks the invoice's "
                      "figures before it can be declared under code 03")

    groups: Dict[str, List[Decimal]] = {}
    untaxed_part = False
    for rate, value, special in lines:
        if special:
            return person("a line under a special procedure (§ 41/§ 42/§ 41¹)")
        if value == 0:
            continue
        if rate is None:
            if value < 0:
                return person("a negative 0 %/exempt/untaxed line")
            untaxed_part = True
            continue
        groups.setdefault(rate, []).append(value)
    if len(groups) == 1:
        return single_rate_row(groups, untaxed_part, vat, len(lines))
    for rate, values in groups.items():
        if any(v < 0 for v in values) and any(v > 0 for v in values):
            return person(f"lines of both signs at the single rate {rate} %")
    if not groups:   # defensive: a negative untaxed line has returned above
        return person("no line at an annex rate")
    if len(groups) > MAX_PART_A_LINES_PER_INVOICE:
        return person(f"supply at {len(groups)} rates, more than the "
                      f"{MAX_PART_A_LINES_PER_INVOICE} lines part A takes per invoice")
    totals = {rate: sum(values, Decimal("0.00")) for rate, values in groups.items()}
    if not any(t < 0 for t in totals.values()):   # defensive: unreachable from the checks above
        return person("no rate group is negative overall")
    if vat is None:
        return check_data("no vat_amount to check the rate labels against")
    expected = sum((t * ANNEX_LINE_RATES[r] for r, t in totals.items()), Decimal("0"))
    tolerance = max(INF_GROSS_TOLERANCE,
                    min(Decimal("0.01") * len(lines), LINE_NETS_MAX_TOLERANCE))
    if abs(expected - vat) > tolerance:
        return check_data(f"the rate groups give VAT {expected:.2f}, the invoice's VAT is "
                          f"{vat:.2f} (a rate label may be wrong)")
    return [{"tax_rate": r, "net_amount": f"{t:.2f}"} for r, t in totals.items()], None


def single_rate_row(groups: Dict[str, List[Decimal]], untaxed_part: bool,
                    vat: Optional[Decimal], line_count: int
                    ) -> Tuple[Optional[List[dict]], Optional[str]]:
    """One part A row for an ordinary sales invoice whose lines of both signs share one rate.

    AR-1439 recommended treatment (approved 2026-11-24; EMTA's text is silent): one row,
    the rate group's signed net total in column 9, no special code (code 03 needs two or
    more rates, or a 0 %/exempt part). Returns (rows, None), or (None, the reason a person
    decides) when the invoice also has a 0 %/exempt/untaxed part (whether code 03 then
    applies is the unsettled question recorded in references/kmd-inf-annex.md), or when
    the invoice's VAT is not the group's net × rate (a line may carry a wrong rate label).
    The caller has already refused negative 0 %/exempt lines and special-procedure lines.
    """
    (rate, values), = groups.items()
    if untaxed_part:
        return None, ("invoice with lines of both signs at one rate and a 0 %/exempt/"
                      "untaxed part: whether code 03 applies is not settled by EMTA's "
                      "text, a person decides")
    if vat is None:
        return None, ("invoice with lines of both signs at one rate: no vat_amount to "
                      "check the rate label against; a person checks the invoice's figures")
    total = sum(values, Decimal("0.00"))
    expected = total * ANNEX_LINE_RATES[rate]
    tolerance = max(INF_GROSS_TOLERANCE,
                    min(Decimal("0.01") * line_count, LINE_NETS_MAX_TOLERANCE))
    if abs(expected - vat) > tolerance:
        return None, (f"invoice with lines of both signs at the single rate {rate} %: the "
                      f"rate gives VAT {expected:.2f}, the invoice's VAT is {vat:.2f} (a rate "
                      "label may be wrong); a person checks the invoice's figures")
    return [{"tax_rate": rate, "net_amount": f"{total:.2f}"}], None


def gross_mismatch(inv: dict, net: Decimal, label: str, credit: bool) -> Optional[str]:
    """Describe an invoice whose net + VAT is not its gross total, or None.

    Only checked when the invoice carries `gross_amount`; `vat_amount` is then
    required (a missing VAT would read as 0 and blame the net). Signed, never as
    magnitudes: an invoice with a negative untaxed line can have a negative net and a
    positive total (net -50, VAT 120, total 70). `vat_amount`,
    `reverse_charge_vat_amount` and `gross_amount` are the document's own amounts as
    stored; `net_amount` carries the credit sign, so a credit memo's net (negative) is
    turned back to the document's sign before the sum.
    """
    if inv.get("gross_amount") in (None, ""):
        return None
    gross = required_amount(inv, "gross_amount", label)
    vat = required_amount(inv, "vat_amount", label)
    rc_vat = (required_amount(inv, "reverse_charge_vat_amount", label)
              if inv.get("reverse_charge_vat_amount") not in (None, "") else Decimal("0.00"))
    document_net = -net if credit else net
    expected = document_net + vat - rc_vat
    if abs(expected - gross) <= INF_GROSS_TOLERANCE:
        return None
    kind = "credit memo net (sign turned back)" if credit else "net"
    return (f"{label} (partner {inv.get('partner_key')!r}): {kind} {document_net:.2f} + VAT "
            f"{vat:.2f} - reverse-charge VAT {rc_vat:.2f} = {expected:.2f}, "
            f"document total {gross:.2f}")


def sign_inconsistency(inv: dict, net: Decimal, label: str, credit: bool) -> Optional[str]:
    """Describe an invoice whose amounts do not all carry one sign, or None.

    The annex presents an ordinary invoice with every amount positive, and a credit
    invoice with every amount negative: a credit memo (stored positive; `net_amount`
    with the credit sign) or an ordinary invoice whose net, VAT and total are all
    negative or zero (a reduction under VAT Act § 29¹). Anything else — an edited bill
    with a negative net and a positive total, a credit memo with a negative taxed line,
    a credit memo whose lines sum below zero — has no presentation in EMTA's
    instructions that this tool knows. It is neither declared nor counted toward the
    limit; it goes to `sign_review` with its figures for a person.
    """
    vat = (required_amount(inv, "vat_amount", label)
           if inv.get("vat_amount") not in (None, "") else Decimal("0.00"))
    gross = (required_amount(inv, "gross_amount", label)
             if inv.get("gross_amount") not in (None, "") else None)
    document_net = -net if credit else net
    amounts = [document_net, vat] + ([gross] if gross is not None else [])
    all_non_negative = all(a >= 0 for a in amounts)
    all_non_positive = all(a <= 0 for a in amounts)
    if all_non_negative or (all_non_positive and not credit):
        return None
    kind = "credit memo (stored amounts)" if credit else "invoice"
    figures = f"net {document_net:.2f}, VAT {vat:.2f}" + (
        f", total {gross:.2f}" if gross is not None else "")
    return (f"{kind} with amounts of mixed sign ({figures}): how the annex presents it "
            "is for a person to decide")


def negative_line_reason(credit: bool) -> str:
    """Why a sales invoice (part A) whose lines carry both signs goes to a person.

    Part B invoices with lines of both signs are declared as one row (AR-1439 rule 6b);
    an ordinary part A invoice with a positive net, or a negative net at a single rate
    with a reference to an original invoice, is decided by mixed_rate_rows.
    """
    if credit:
        return ("credit invoice with lines of both signs: EMTA's instructions give no "
                "presentation for it; a person decides")
    return ("invoice with lines of both signs and a total of zero or below (on more than "
            "one rate, or without a reference to an original invoice): EMTA's "
            "instructions do not settle how it is shown; a person decides")


# AR-1439 rules 1-3 (approved 2026-11-24). A cancellation entry is an invoice-list entry
# for a cancellation of an invoice WITHOUT a credit invoice (in the ledger: a reversal).
# It carries the cancelled invoice's partner, document type and figures as stored on that
# invoice (positive), its own number and date, `original_invoice_number` (the invoice the
# cancellation refers to, from a recorded link) and a `cancellation` object.
CANCELLATION_REASONS = ("transaction_cancelled", "issued_in_error")
# Only the cancellation of a sales invoice can be declared (part A minus row) or left out
# with its original; a purchase invoice's cancellation always goes to a person (part B
# takes a minus sign only on a received credit invoice or in the § 29¹(4) case).
DECLARABLE_CANCELLATION_TYPES = {"AR_INVOICE"}
CREDIT_MEMO_TYPES = {"AR_CREDIT_MEMO", "AP_CREDIT_MEMO"}
ISO_DATE_RE = re.compile(r"^(\d{4})-(\d{2})-\d{2}$")

# Rule 3 review text: which treatment applies in which situation.
MISTAKE_OR_CANCELLATION_TEXT = (
    "if the invoice was issued by mistake (no such transaction took place), the error is "
    "in the declaration of the period the invoice was declared in: correct that period "
    "(VAT Act § 27(5)) and resubmit its KMD INF with the line at zero amounts (KMD INF "
    "instructions, 'Correcting the KMD INF form'); nothing goes in this period. If the "
    "transaction itself was cancelled, it goes in the period of the cancellation (VAT Act "
    "§ 29(7)): a minus row here, like a credit invoice. A person says which and sets "
    "cancellation.reason ('issued_in_error' or 'transaction_cancelled')")


def _original_reference(inv: dict, label: str) -> str:
    """The original invoice number the document itself refers to, or ""."""
    raw = inv.get("original_invoice_number")
    if raw is None or raw == "":
        return ""
    if isinstance(raw, bool) or not isinstance(raw, (str, int)):
        raise ValueError(f"{label}: original_invoice_number must be the original invoice's "
                         f"number as text, got {raw!r}")
    return str(raw).strip()


def _cancellation(inv: dict, label: str) -> Optional[dict]:
    """The entry's `cancellation` object, validated, or None for an ordinary entry."""
    raw = inv.get("cancellation")
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ValueError(f"{label}: cancellation must be an object")
    reason = raw.get("reason")
    if reason is not None and reason not in CANCELLATION_REASONS:
        raise ValueError(f"{label}: cancellation.reason must be one of "
                         f"{', '.join(CANCELLATION_REASONS)} or null, got {reason!r}")
    turnover = raw.get("turnover_arose")
    if turnover is not None and not isinstance(turnover, bool):
        raise ValueError(f"{label}: cancellation.turnover_arose must be true, false or "
                         f"null, got {turnover!r}")
    original_date = raw.get("original_invoice_date")
    if original_date is not None and not isinstance(original_date, str):
        raise ValueError(f"{label}: cancellation.original_invoice_date must be a "
                         f"YYYY-MM-DD date, got {original_date!r}")
    return {"reason": reason, "turnover_arose": turnover,
            "original_invoice_date": original_date}


def _month(value) -> Optional[Tuple[int, int]]:
    match = ISO_DATE_RE.match(str(value or "").strip())
    return (int(match.group(1)), int(match.group(2))) if match else None


def _same_figures(a: dict, b: dict) -> bool:
    """True when two entries carry the same net, VAT and per-rate line nets (M6)."""
    def figures(inv: dict):
        label = f"invoice {inv.get('invoice_number')!r}"
        net = required_amount(inv, "net_amount", label)
        vat = (required_amount(inv, "vat_amount", label)
               if inv.get("vat_amount") not in (None, "") else None)
        gross = (required_amount(inv, "gross_amount", label)
                 if inv.get("gross_amount") not in (None, "") else None)
        lines = _line_nets(inv, label)
        per_rate = None
        if lines is not None:
            per_rate = {}
            for rate, value, _sp in lines:
                per_rate[rate] = per_rate.get(rate, Decimal("0.00")) + value
            per_rate = {r: v for r, v in per_rate.items() if v != 0}
        return net, vat, gross, per_rate
    return figures(a) == figures(b)


def cancellation_decisions(invoices: list) -> Dict[int, Tuple[str, str]]:
    """Decide every cancellation entry and the invoices it names (AR-1439 rules 1-3).

    Returns {index: ("declare" | "omit" | "review", reason)} for each cancellation entry
    and for each entry linked to one; entries not returned are ordinary invoices. A
    cancellation names the entry with the same partner_key whose invoice_number equals its
    `original_invoice_number`; any other document whose `original_invoice_number` is that
    same invoice (a credit memo, a reduction or replacement invoice) is linked too. Nothing is matched by amount or across partners.

    * Only the cancellation of a sales invoice (AR_INVOICE) can be declared or omitted.
      A cancelled purchase invoice (AP_INVOICE) always goes to a person: the buyer
      reflects it in the cancellation period (VAT Act § 29(7)), but part B takes a minus
      sign only on a received credit invoice or in the § 29¹(4) case. A cancelled credit
      memo also goes to a person.
    * Later period: "declare" (a minus row, counted as a credit; § 29(7) on the period,
      row form recommended) only with a reference, reason "transaction_cancelled", no
      other cancellation of the same invoice, no credit memo of that invoice in the list,
      and the invoice itself not in this period's list. Otherwise "review"; reason not
      recorded or "issued_in_error" (corrected in the original period, § 27(5)) included.
    * Same period (recommended): the cancellation and its one original are "omit" when
      turnover_arose is false and both carry the same figures; otherwise both "review".
    * Missing or contradictory dates, no reference: "review".

    A review spreads over everything linked by a reference (the invoice, its other
    cancellations, its credit memos, a cancellation of a cancellation), so an invoice is
    never declared or left out while a linked document waits for a person.
    """
    decisions: Dict[int, Tuple[str, str]] = {}
    links: Dict[int, set] = {}
    by_original: Dict[int, List[Tuple[int, dict]]] = {}
    # Every cancellation grouped by the invoice it names, before any is decided (M1):
    # two cancellations of one invoice go to a person together, whatever else they fail.
    groups: Dict[Tuple[str, str], List[int]] = {}
    for i, inv in enumerate(invoices):
        if isinstance(inv, dict) and inv.get("cancellation") is not None:
            ref = _original_reference(inv, f"invoice {inv.get('invoice_number')!r}")
            if ref:
                groups.setdefault((str(inv.get("partner_key") or "").strip(), ref),
                                  []).append(i)

    def link(a: int, b: int) -> None:
        links.setdefault(a, set()).add(b)
        links.setdefault(b, set()).add(a)

    def key_of(inv: dict) -> str:
        return str(inv.get("partner_key") or "").strip()

    def type_of(inv: dict) -> str:
        return str(inv.get("document_type") or "").strip().upper()

    for i, inv in enumerate(invoices):
        if not isinstance(inv, dict) or inv.get("cancellation") is None:
            continue
        label = f"invoice {inv.get('invoice_number')!r}"
        canc = _cancellation(inv, label)
        ref = _original_reference(inv, label)
        key = key_of(inv)
        doc_type = type_of(inv)
        named, memos = [], []
        if ref:
            for j, other in enumerate(invoices):
                if j == i or not isinstance(other, dict) or key_of(other) != key:
                    continue
                if str(other.get("invoice_number") or "").strip() == ref:
                    named.append(j)
                elif (other.get("cancellation") is None
                      and _original_reference(other, f"invoice {other.get('invoice_number')!r}")
                      == ref):
                    # Any other document that refers to the same invoice: a credit memo,
                    # a negative (reduction) invoice under rule 5, anything else.
                    memos.append(j)
        siblings = [j for j in groups.get((key, ref), []) if j != i] if ref else []
        for j in named + memos + siblings:
            link(i, j)
        cancelled_in = _month(inv.get("invoice_date"))
        issued_in = _month(canc["original_invoice_date"])
        if cancelled_in is None or issued_in is None:
            decisions[i] = ("review", "cancellation without invoice_date and "
                            "cancellation.original_invoice_date (YYYY-MM-DD): its period "
                            "cannot be placed; a person decides")
        elif issued_in > cancelled_in:
            decisions[i] = ("review", "cancellation dated before the invoice it cancels; "
                            "a person checks the dates")
        elif doc_type == "AP_INVOICE":
            decisions[i] = ("review", "cancellation of a purchase invoice without a credit "
                            "invoice: the buyer reflects it in the period of the cancellation "
                            "(VAT Act § 29(7)), but part B takes a minus sign only on a "
                            "received credit invoice or in the § 29¹(4) case; how it is "
                            "shown is for a person to decide")
        elif doc_type not in DECLARABLE_CANCELLATION_TYPES:
            decisions[i] = ("review", f"cancellation of a {doc_type}: only the cancellation "
                            "of a sales invoice is treated like a credit invoice; a person "
                            "decides")
        elif not ref:
            decisions[i] = ("review", "cancellation without a credit invoice that does not "
                            "refer to the original invoice (original_invoice_number): a "
                            "person decides")
        elif siblings:
            decisions[i] = ("review", f"invoice {ref!r} has {len(siblings) + 1} cancellations "
                            "in the period; a person decides")
        elif memos:
            decisions[i] = ("review", f"invoice {ref!r} is cancelled and another document in "
                            "the list (a credit memo, a reduction invoice or any other document) "
                            "also refers to it: the cancellation, the invoice and that document "
                            "are for a person to decide")
        elif issued_in < cancelled_in:
            if named:
                decisions[i] = ("review", f"cancellation says invoice {ref!r} is from an "
                                "earlier period, but it is in this period's list; a person "
                                "checks the dates")
            elif canc["reason"] == "issued_in_error":
                decisions[i] = ("review", f"invoice {ref!r} was issued by mistake: correct the "
                                "period it was declared in (VAT Act § 27(5)) and resubmit that "
                                "period's KMD INF with the line at zero amounts (KMD INF "
                                "instructions, 'Correcting the KMD INF form'); nothing is "
                                "declared for it in this period. A person makes the "
                                "correction")
            elif canc["reason"] is None:
                decisions[i] = ("review", f"invoice {ref!r} cancelled in a later period "
                                "without a credit invoice; whether it was issued by mistake "
                                "or the transaction was cancelled is not recorded: "
                                f"{MISTAKE_OR_CANCELLATION_TEXT}")
            else:
                decisions[i] = ("declare", "")
        else:
            originals = [j for j in named if invoices[j].get("cancellation") is None
                         and type_of(invoices[j]) == doc_type]
            if len(originals) != 1 or len(named) != 1:
                decisions[i] = ("review", f"invoice {ref!r} cancelled in the period it was "
                                "issued, but the list does not hold exactly one original "
                                f"for it (found {len(named)} entr{'y' if len(named) == 1 else 'ies'} "
                                "with that partner and number); a person decides")
            elif _month(invoices[originals[0]].get("invoice_date")) != issued_in:
                decisions[i] = ("review", "cancellation.original_invoice_date does not match "
                                f"the date of invoice {ref!r} in the list; a person checks "
                                "the dates")
            else:
                by_original.setdefault(originals[0], []).append((i, canc))

    for j, cancels in by_original.items():
        ref = str(invoices[j].get("invoice_number") or "").strip()
        if len(cancels) > 1:
            why = f"invoice {ref!r} has {len(cancels)} cancellations in the period; a person decides"
            for i, _canc in cancels:
                decisions[i] = ("review", why)
            decisions[j] = ("review", why)
            continue
        i, canc = cancels[0]
        if canc["turnover_arose"] is not False:
            known = ("turnover arose (goods or services supplied, or payment received)"
                     if canc["turnover_arose"] else
                     "it is not confirmed that nothing was supplied and no payment was ever "
                     "received")
            decisions[i] = decisions[j] = (
                "review", f"invoice {ref!r} issued and cancelled in the same period and "
                f"{known}: how it is shown is for a person to decide")
        elif not _same_figures(invoices[i], invoices[j]):
            decisions[i] = decisions[j] = (
                "review", f"invoice {ref!r} issued and cancelled in the same period, but the "
                "cancellation's figures (net, VAT, gross, per-rate lines) differ from the "
                "invoice's; "
                "a person checks them")
        else:
            why = (f"invoice {ref!r} issued and cancelled in the same period with no "
                   "turnover (confirmed: nothing supplied, no payment ever received): both "
                   "are left out (AR-1439 recommended treatment; EMTA's text is silent)")
            decisions[i] = decisions[j] = ("omit", why)

    # A review spreads over everything linked to it by a reference.
    pending = [i for i, (outcome, _why) in decisions.items() if outcome == "review"]
    while pending:
        source = pending.pop()
        for other in links.get(source, ()):
            if decisions.get(other, ("",))[0] != "review":
                number = invoices[source].get("invoice_number")
                decisions[other] = ("review", f"linked to {number!r}, which goes to a "
                                    f"person: {decisions[source][1]}")
                pending.append(other)
    return decisions


def select_inf_partners(invoices: List[dict], side: str) -> dict:
    """
    Decide which partners' invoices go into KMD INF part A (side "A", invoices issued)
    or part B (side "B", invoices received), from invoice-level input. Rules from
    EMTA's KMD INF instructions (vorm_kmd_inf_2025_07_eng.pdf), except the AR-1439
    bullet, which marks what is settled and what is a recommended treatment:

      * The limit is the invoices' total WITHOUT VAT per partner in the period and is
        met at "at least 1,000 euros" (>= INF_THRESHOLD).
      * Ordinary invoices and credit invoices are totalled separately; either total
        reaching the limit brings ALL that partner's invoices in, credit invoices
        included.
      * Only invoices containing supply taxable at 24/22/20/13/9/5 % count and are
        presented (`has_positive_rate_supply`); for such an invoice the whole total
        without VAT counts, 0 %/exempt parts included. Invoices issued solely under the
        travel-services special procedure (§ 40) and invoices subject to professional
        secrecy are not presented.
      * An invoice to a natural person (not self-employed) is not presented; nor is one
        with a non-resident that has no register code assigned in Estonia.
      * Part B: an invoice whose VAT is not deducted in field 5 this period is not
        presented (`vat_deducted_in_period` 0 or absent).
      * Part B covers invoices received from persons registered in Estonia as VAT
        payers (instructions, part B). Invoices for cross-border transactions that are
        reverse-charged in Estonia (intra-Community acquisitions, services from abroad)
        are not shown at all (EMTA page "Käibedeklaratsiooni lisa täitmine"):
        `cross_border_reverse_charge: true` excludes them by that rule, whatever the
        supplier's register code. Such an invoice that also carries VAT charged by the
        supplier goes to `reverse_charge_review`. Domestic reverse charge (VAT Act
        § 41¹) is not cross-border and is shown (part B code 12, part A code 02).
      * Part B takes a minus sign only on a credit invoice and on an invoice unpaid
        under VAT Act § 29¹(4) (instructions, part B). A negative
        `vat_deducted_in_period` or a negative total on an ordinary purchase invoice
        goes to `sign_review`
        (the § 29¹(4) case is identified by a person, not by this tool).
      * AR-1439 (approved 2026-11-24; "recommended" = EMTA's text is silent, agreed
        conservative treatment). Settled according to the 2026-11-24 research pass: a
        cancellation belongs to the period of the cancellation (§ 29(7)); an invoice
        issued by mistake is corrected in its own period (§ 27(5)). Recommended: the row
        forms below. cancellation_decisions decides every cancellation entry: only a
        sales invoice's cancellation in a later period, with a reference, reason
        "transaction_cancelled", no other cancellation and no other document referring to
        that invoice in the list, is declared (a part A minus row, counted as a credit); in the same
        period, the sales invoice and its cancellation are excluded when
        `cancellation.turnover_arose` is false and their figures match. Everything else
        goes to `cancellation_review` with every entry linked to it, a cancelled
        purchase invoice always. A negative ordinary sales invoice is declared as a minus
        row only when it carries `original_invoice_number`; otherwise `sign_review`. A
        part A ordinary invoice whose lines of both signs share one rate (no 0 %/exempt
        part, VAT = net × rate) is declared with one `rate_rows` entry and no special
        code; an ordinary part B invoice with lines of both signs is declared as one row
        with its net total and net deducted VAT (a negative one, and any part B credit
        memo with lines of both signs, go to `sign_review`).
      * Part A special code 03 covers an invoice with supply at two or more rates,
        "incl. negative supply" (instructions, part A column 10; EMTA part A example:
        1500 = 24 % 2000 and 9 % −500, two rows, column 6 = 1500 on both). Given
        `line_nets`, an ordinary invoice (side A) whose own net, VAT and total are
        positive and whose negative lines are whole rate groups is declared, counted at
        its net total, and returned with `rate_rows` and `special_codes: ["03"]` (only
        general-procedure lines: a line marked `special_procedure` keeps it with a
        person). Every other part A invoice whose lines carry both signs — a rate whose
        lines carry both signs on a multi-rate invoice, a negative 0 %/exempt line, a
        total of zero or below (unless single-rate with a reference, above), a credit
        memo — goes to `sign_review`, as does an ordinary purchase invoice with a
        negative total. These two checks run after the exclusions (an invoice
        that is not shown is not sent for review by them); the header sign check above
        still runs first.
      * An invoice counts into the limit only once, in the first period it must be
        presented. An invoice already presented in an earlier period whose supply (part A)
        or deduction (part B) also falls in this period must be presented again
        (`counted_in_earlier_period: true`): it stays out of the limit but is always
        presented, whatever this period's totals. The partner's other invoices join it
        only when this period's totals reach the limit.

    Each invoice dict: partner_key (required; the ERP customer / vendor id), document_type
    (required: AR_INVOICE / AR_CREDIT_MEMO on side A, AP_INVOICE / AP_CREDIT_MEMO on side
    B; a credit memo always counts as a credit and carries its net_amount with the
    credit sign, negative or zero),
    currency (required, must be "EUR": amounts converted to the functional currency),
    partner_name, registry_code,
    registry_code_verified (bool), non_resident (bool), partner_kind
    ("legal_person" default | "self_employed" | "authority" | "natural_person"),
    invoice_number, invoice_date, net_amount (REQUIRED, signed, WITHOUT VAT — credit
    invoices negative; a missing, null or non-numeric value is refused, never read as
    0), vat_amount, has_positive_rate_supply (bool, required),
    travel_special_procedure_only, professional_secrecy, counted_in_earlier_period,
    and for side B vat_deducted_in_period (REQUIRED on side B; 0 means not deducted)
    and cross_border_reverse_charge (bool, side B only; then vat_amount and
    reverse_charge_vat_amount are required) and import_reverse_charge (bool, side B only:
    a reverse-charge line on a code with tax_scope "import"; the invoice goes to
    `reverse_charge_review`, as does a cross-border bill with a special_procedure line).
    Optional original_invoice_number (text: the invoice the document itself refers to,
    from a link recorded on it, never matched by number or amount) and, on a cancellation
    entry only, cancellation = {reason: "transaction_cancelled" | "issued_in_error" | null
    (set by a person), original_invoice_date: "YYYY-MM-DD", turnover_arose: true | false
    | null}. line_nets (list of {rate, net_amount}, see
    _line_nets) must add up to the invoice's net (a credit memo's turned back to the
    document's sign) within a cent per line, or the whole selection is refused; invoices
    passed without it are listed under `lines_not_checked`, because negative lines cannot
    be seen without it.
    Optional gross_amount (the document total incl. VAT, i.e. the header amount) with
    reverse_charge_vat_amount (VAT self-assessed on reverse charge, not in that total):
    when gross_amount is given (vat_amount is then required), net_amount + vat_amount -
    reverse_charge_vat_amount must equal gross_amount within INF_GROSS_TOLERANCE, all
    signed: vat, reverse-charge VAT and gross as the document stores them, net with the
    credit sign (a credit memo's net is turned back before the sum), or the whole selection is refused with every invoice that
    differs (a doubled net is caught here) — unless the invoice carries
    gross_mismatch_reviewed (a person's reason), which lists it under `gross_reviewed`
    instead. Invoices without gross_amount are listed under `gross_not_checked`.

    For a non-resident, `registry_code_verified: true` with an empty registry_code means
    a person confirmed it has no register code assigned in Estonia (then not presented).
    Partner records that carry the same register code are combined into one partner (the
    limit is per transaction partner); `partner_keys` and `partner_names` list them. A
    partner is declared only when every one of its invoices carries the same verified
    code; otherwise it goes to `needs_registry_code` once it reaches the limit. Each
    returned invoice carries `signed_net_amount`, and `signed_vat_amount` /
    `signed_vat_deducted_in_period` when given (credit invoices negative), for the annex.
    A partner whose invoices carry conflicting register codes, or a code shaped like a
    VAT number, is also returned under `needs_registry_code` (see `conflicts`).
    A partner that qualifies but has no verified register code is returned under
    `needs_registry_code` for a person to resolve — never filled from a VAT number or
    another company's record. An invoice whose amounts do not all carry one sign (see
    sign_inconsistency) is neither declared nor counted toward the limit; it is returned
    under `sign_review` with its figures. Returns {"declare", "needs_registry_code",
    "below_threshold", "excluded", "sign_review", "reverse_charge_review",
    "rate_review", "cancellation_review", "gross_reviewed", "gross_not_checked", "lines_not_checked"}. A line
    rate is canonicalised ("24.00" -> "24"); an invoice with a positive line rate outside
    24/22/20/13/9/5 goes to `rate_review` for a person.
    """
    if side not in ("A", "B"):
        raise ValueError("side must be 'A' (invoices issued) or 'B' (invoices received)")

    if not isinstance(invoices, list):
        raise ValueError("the invoice list must be a JSON array of invoice objects")
    excluded: List[dict] = []
    included: List[tuple] = []
    gross_mismatches: List[str] = []
    gross_reviewed: List[dict] = []
    gross_not_checked: List[str] = []
    sign_review: List[dict] = []
    reverse_charge_review: List[dict] = []
    rate_review: List[dict] = []
    cancellation_review: List[dict] = []
    lines_not_checked: List[str] = []
    line_mismatches: List[str] = []
    if not all(isinstance(inv, dict) for inv in invoices):
        raise ValueError("each invoice must be a JSON object")
    decided = cancellation_decisions(invoices)
    for index, inv in enumerate(invoices):
        key = str(inv.get("partner_key") or "").strip()
        if not key:
            raise ValueError(f"invoice {inv.get('invoice_number')!r} has no partner_key")
        if not isinstance(inv.get("has_positive_rate_supply"), bool):
            raise ValueError(
                f"invoice {inv.get('invoice_number')!r}: has_positive_rate_supply is required "
                "and must be true or false (true when the invoice contains supply at "
                "24/22/20/13/9/5 %)"
            )
        for flag in BOOLEAN_INVOICE_FLAGS:
            if flag in inv and inv[flag] is not None and not isinstance(inv[flag], bool):
                raise ValueError(
                    f"invoice {inv.get('invoice_number')!r}: {flag} must be true or false, "
                    f"got {inv[flag]!r}"
                )
        label = f"invoice {inv.get('invoice_number')!r}"
        currency = str(inv.get("currency") or "").strip().upper()
        if currency != INF_CURRENCY:
            raise ValueError(
                f"{label}: currency must be {INF_CURRENCY!r} — convert the amounts to the "
                f"entity's functional currency first (got {inv.get('currency')!r})"
            )
        doc_type = str(inv.get("document_type") or "").strip().upper()
        if doc_type not in INF_DOCUMENT_TYPES[side]:
            raise ValueError(
                f"{label}: document_type must be one of "
                f"{', '.join(sorted(INF_DOCUMENT_TYPES[side]))} on side {side}, "
                f"got {inv.get('document_type')!r}"
            )
        net = required_amount(inv, "net_amount", label)
        mismatch = gross_mismatch(inv, net, label, INF_DOCUMENT_TYPES[side][doc_type])
        reviewed_value = inv.get("gross_mismatch_reviewed")
        if reviewed_value is not None and not isinstance(reviewed_value, str):
            raise ValueError(f"{label}: gross_mismatch_reviewed must be the person's reason "
                             f"as text, got {reviewed_value!r}")
        reviewed = (reviewed_value or "").strip()
        if inv.get("gross_amount") in (None, ""):
            gross_not_checked.append(str(inv.get("invoice_number") or f"partner {key}"))
        elif mismatch and reviewed:
            gross_reviewed.append({"partner_key": key, "invoice_number": inv.get("invoice_number"),
                                   "difference": mismatch, "reason": reviewed})
        elif mismatch:
            gross_mismatches.append(mismatch)
        credit_doc = INF_DOCUMENT_TYPES[side][doc_type]
        lines = _line_nets(inv, label)
        if lines is None:
            lines_not_checked.append(str(inv.get("invoice_number") or f"partner {key}"))
        cross_border = bool(inv.get("cross_border_reverse_charge"))
        import_rc = bool(inv.get("import_reverse_charge"))
        if (cross_border or import_rc) and side != "B":
            raise ValueError(f"{label}: cross_border_reverse_charge / import_reverse_charge "
                             "apply to invoices received (side B) only")
        vat_deducted = (required_amount(inv, "vat_deducted_in_period", label)
                        if side == "B" else None)
        reference = _original_reference(inv, label)
        cancellation = _cancellation(inv, label)

        # AR-1439 rules 1-3: cancellation entries and the invoices they name.
        cancel_why = None
        outcome, why = decided.get(index, ("", ""))
        if outcome == "omit":
            excluded.append({"partner_key": key, "invoice_number": inv.get("invoice_number"),
                             "reason": why})
            continue
        if outcome == "review":
            # Listed for a person even when the invoice would be excluded below (e.g. no
            # supply at an annex rate), so the person sees every cancellation.
            cancel_why = why
        if cancel_why:
            cancellation_review.append({
                "partner_key": key, "invoice_number": inv.get("invoice_number"),
                "document_type": doc_type, "original_invoice_number": reference or None,
                "original_invoice_date": (cancellation or {}).get("original_invoice_date"),
                "net_amount": inv.get("net_amount"), "vat_amount": inv.get("vat_amount"),
                "gross_amount": inv.get("gross_amount"), "reason": cancel_why})
            continue
        # Only a cancellation decided "declare" (rule 1) reaches here: `as_credit` below
        # makes it a minus row in this period, counted like a credit invoice.
        cancels = cancellation is not None

        # Who decides how the invoice is shown: the annex text, or a person.
        review = sign_inconsistency(inv, net, label, credit_doc)
        odd_rates = sorted({r for r, _v, _sp in (lines or [])
                            if r is not None and r not in ANNEX_LINE_RATES})
        if review is None and odd_rates:
            rate_review.append({
                "partner_key": key, "invoice_number": inv.get("invoice_number"),
                "document_type": doc_type, "rates": odd_rates,
                "reason": (f"line rate(s) {', '.join(odd_rates)} % are not among the rates "
                           f"the annex covers ({', '.join(ANNEX_LINE_RATES)} %): how this "
                           "invoice is classified is for a person to decide")})
            continue
        if review:
            sign_review.append({
                "partner_key": key, "invoice_number": inv.get("invoice_number"),
                "document_type": doc_type, "net_amount": inv.get("net_amount"),
                "vat_amount": inv.get("vat_amount"), "gross_amount": inv.get("gross_amount"),
                "vat_deducted_in_period": inv.get("vat_deducted_in_period"),
                "reason": review})
            continue
        # The line tie runs only for an invoice the header sign check lets through: one
        # already going to a person (e.g. a credit memo passed with a positive net) must
        # not stop the whole selection.
        if lines is not None:
            off = line_nets_mismatch(lines, -net if credit_doc else net, label)
            if off:
                line_mismatches.append(off)
        as_credit = credit_doc or cancels
        if as_credit:
            net = -abs(net) or Decimal("0.00")   # a zero net stays "0.00", never "-0.00"
        # Reviewed before the exclusions below: an import or mixed reverse-charge bill
        # that would also be excluded (e.g. VAT not deducted) still goes to a person.
        rc_review = None
        if import_rc:
            rc_review = ("reverse charge on a code with tax_scope 'import': the cross-border "
                         "rule (EMTA annex page) names intra-Community acquisitions and "
                         "services from abroad; whether this bill is shown is for a person "
                         "to decide")
        elif cross_border:
            vat = required_amount(inv, "vat_amount", label)
            rc_vat = required_amount(inv, "reverse_charge_vat_amount", label)
            if abs(vat - rc_vat) > INF_GROSS_TOLERANCE:
                rc_review = ("cross-border reverse charge on an invoice that also carries "
                             "VAT charged by the supplier: whether and how it is shown in "
                             "part B is for a person to decide")
            elif lines and any(special for _r, _v, special in lines):
                rc_review = ("cross-border reverse charge together with a special-procedure "
                             "(§ 41/§ 42/§ 41¹) line: § 41¹ is shown in part B, cross-border reverse "
                             "charge is not; how this bill is shown is for a person to decide")
        if rc_review:
            reverse_charge_review.append({
                "partner_key": key, "invoice_number": inv.get("invoice_number"),
                "vat_amount": inv.get("vat_amount"),
                "reverse_charge_vat_amount": inv.get("reverse_charge_vat_amount"),
                "reason": rc_review})
            continue
        reason = None
        reg_code = str(inv.get("registry_code") or "").strip()
        verified = bool(inv.get("registry_code_verified")) and bool(reg_code)
        if cross_border:
            reason = ("invoice for a cross-border transaction reverse-charged in Estonia "
                      "(intra-Community acquisition or service from abroad): not shown in "
                      "KMD INF")
        elif not inv["has_positive_rate_supply"]:
            reason = "no supply at 24/22/20/13/9/5 % on the invoice"
        elif inv.get("travel_special_procedure_only"):
            reason = "issued solely under the travel-services special procedure (VAT Act § 40)"
        elif inv.get("professional_secrecy"):
            reason = "subject to professional secrecy"
        elif (inv.get("partner_kind") or "legal_person") in INF_EXCLUDED_PARTNER_KINDS:
            reason = "partner is a natural person (not self-employed)"
        elif inv.get("non_resident") and not reg_code and inv.get("registry_code_verified"):
            reason = "non-resident without a register code assigned in Estonia"
        elif side == "B" and vat_deducted == 0:
            reason = "VAT not deducted in field 5 this period"
        if reason:
            excluded.append({"partner_key": key, "invoice_number": inv.get("invoice_number"),
                             "reason": reason})
            continue

        # Checked only for invoices that would be shown: lines of both signs, and a minus
        # sign on an ordinary purchase invoice.
        review = None
        rate_rows = None
        mixed_lines = bool(lines) and any(v < 0 for _r, v, _sp in lines) and any(
            v > 0 for _r, v, _sp in lines)
        if side == "B" and mixed_lines and credit_doc:
            # Rule 6b covers ordinary purchase invoices only. An ordinary part B invoice
            # with lines of both signs is one row with the net invoice total and the net
            # VAT deducted: nothing to decide here; a negative one is caught below.
            review = ("purchase credit invoice with lines of both signs: EMTA's instructions "
                      "give no presentation for it and the AR-1439 treatments do not cover "
                      "it; a person decides")
        if side == "A" and mixed_lines:
            if not as_credit and (net > 0 or (net < 0 and reference)):
                vat = (required_amount(inv, "vat_amount", label)
                       if inv.get("vat_amount") not in (None, "") else None)
                rate_rows, review = mixed_rate_rows(lines, vat)
                if rate_rows is not None and net < 0 and len(rate_rows) > 1:
                    rate_rows, review = None, negative_line_reason(False)
            else:
                review = negative_line_reason(as_credit)
        if review is None and side == "A" and not as_credit and net < 0 and not reference:
            # Rule 5 (recommended, from VAT Act § 37(4): a credit invoice amends an original
            # invoice and refers to it): a negative ordinary sales invoice is declared as a
            # minus row only when it refers to an original invoice.
            review = (f"ordinary sales invoice with a negative total (net {net:.2f}) that does "
                      "not refer to an original invoice (original_invoice_number): it is "
                      "declared as a minus row only when the document refers to the invoice "
                      "it amends; a person decides")
        if review is None and side == "B" and not as_credit and (vat_deducted < 0 or net < 0):
            review = (f"ordinary purchase invoice with a minus sign (net {net:.2f}, input VAT "
                      f"deducted {vat_deducted:.2f}): part B takes a minus sign only on a credit "
                      "invoice or on an invoice unpaid under VAT Act § 29¹(4) (bad debt, "
                      "original invoice number); which case this is, and how it is shown, is "
                      "for a person to decide")
        if review:
            sign_review.append({
                "partner_key": key, "invoice_number": inv.get("invoice_number"),
                "document_type": doc_type, "net_amount": inv.get("net_amount"),
                "vat_amount": inv.get("vat_amount"), "gross_amount": inv.get("gross_amount"),
                "vat_deducted_in_period": inv.get("vat_deducted_in_period"),
                "reason": review})
            continue

        # Returned with the invoice: the signed EUR net to put in the annex (credit
        # invoices are entered with a minus sign, KMD INF instructions parts A and B).
        # Only rows whose amounts carry one sign reach here (sign_inconsistency), so a
        # negative net means the whole invoice is negative: a credit.
        signed = dict(inv, signed_net_amount=f"{net:.2f}")
        if rate_rows is not None:
            # One part A row per rate, the invoice's net (column 6) repeated on each, the
            # rate's signed net for column 9. Two or more rates: special code 03. One rate
            # (lines of both signs, rule 6a): one row, no special code.
            signed["rate_rows"] = rate_rows
            signed["special_codes"] = [MIXED_RATE_SPECIAL_CODE] if len(rate_rows) > 1 else []
        is_credit = as_credit or net < 0
        for src, dst in (("vat_amount", "signed_vat_amount"),
                         ("vat_deducted_in_period", "signed_vat_deducted_in_period")):
            if src in inv and inv[src] not in (None, ""):
                value = required_amount(inv, src, label)
                signed[dst] = f"{((-abs(value) or Decimal('0.00')) if is_credit else value):.2f}"
        included.append((key, reg_code, verified, net, signed))

    if line_mismatches:
        raise ValueError(
            f"line_nets do not add up to the invoice's net on {len(line_mismatches)} "
            "invoice(s); fix the extraction before selecting:\n  "
            + "\n  ".join(line_mismatches)
        )
    if gross_mismatches:
        raise ValueError(
            "net plus VAT does not equal the document total on "
            f"{len(gross_mismatches)} invoice(s); fix the extraction before selecting "
            "(was a generated control line counted as a document line? A difference a "
            "person has reviewed is passed with gross_mismatch_reviewed):\n  "
            + "\n  ".join(gross_mismatches)
        )

    # The limit is per transaction partner, not per ERP record. Records are linked
    # through any register code they carry, verified or not (two cards for one company
    # with the same code are one partner); a code shaped like a VAT number links nothing.
    parent: Dict[str, str] = {}

    def find(node: str) -> str:
        parent.setdefault(node, node)
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    def union(a: str, b: str) -> None:
        parent[find(a)] = find(b)

    for key, reg_code, _verified, _net, _inv in included:
        find("key:" + key)
        if reg_code and not VAT_NUMBER_RE.match(reg_code):
            union("key:" + key, "code:" + reg_code)

    groups: Dict[str, dict] = {}
    for key, reg_code, verified, net, inv in included:
        g = groups.setdefault(find("key:" + key), {
            "partner_key": key, "partner_keys": [], "partner_names": [],
            "codes": set(), "all_verified": True, "conflicts": [],
            "invoice_total": Decimal("0.00"), "credit_total": Decimal("0.00"),
            "invoices": [],
        })
        if key not in g["partner_keys"]:
            g["partner_keys"].append(key)
        name = inv.get("partner_name")
        if name and name not in g["partner_names"]:
            g["partner_names"].append(name)
        if reg_code and VAT_NUMBER_RE.match(reg_code):
            g["conflicts"].append(
                f"invoice {inv.get('invoice_number')!r}: registry_code {reg_code!r} looks "
                "like a VAT number"
            )
            g["all_verified"] = False
        elif reg_code:
            g["codes"].add(reg_code)
        if not verified:
            g["all_verified"] = False
        if not inv.get("counted_in_earlier_period"):
            if net < 0:
                g["credit_total"] += -net
            else:
                g["invoice_total"] += net
        g["invoices"].append(inv)

    declare: List[dict] = []
    needs_code: List[dict] = []
    below: List[dict] = []
    for g in groups.values():
        codes = sorted(g.pop("codes"))
        all_verified = g.pop("all_verified")
        if len(codes) > 1:
            g["conflicts"].append(f"different register codes for one partner: {codes}")
        verified_code = codes[0] if (all_verified and len(codes) == 1) else None
        if len(g["partner_keys"]) > 1 and not verified_code:
            g["conflicts"].append(
                f"records {g['partner_keys']} share a register code that is not verified "
                "on every invoice; confirm they are one partner"
            )
        g["partner_name"] = g["partner_names"][0] if g["partner_names"] else None
        g["registry_code"] = verified_code
        g["registry_code_verified"] = verified_code is not None
        qualifies = g["invoice_total"] >= INF_THRESHOLD or g["credit_total"] >= INF_THRESHOLD
        carried = [i for i in g["invoices"] if i.get("counted_in_earlier_period")]
        row = dict(g, invoice_total=f"{g['invoice_total']:.2f}",
                   credit_total=f"{g['credit_total']:.2f}")
        if not qualifies and not carried:
            below.append(row)
            continue
        if not qualifies:
            # Only the invoices carried from an earlier period must be presented.
            others = [i for i in g["invoices"] if not i.get("counted_in_earlier_period")]
            if others:
                below.append(dict(row, invoices=others))
            row["invoices"] = carried
        if not row["registry_code_verified"] or row["conflicts"]:
            needs_code.append(row)
        else:
            declare.append(row)
    return {"declare": declare, "needs_registry_code": needs_code,
            "below_threshold": below, "excluded": excluded, "sign_review": sign_review,
            "reverse_charge_review": reverse_charge_review, "rate_review": rate_review,
            "cancellation_review": cancellation_review, "gross_reviewed": gross_reviewed, "gross_not_checked": gross_not_checked,
            "lines_not_checked": lines_not_checked}


# --------------------------------------------------------------------------- #
# XML generation
# --------------------------------------------------------------------------- #
def _body_xml(body: dict) -> List[str]:
    """Render the declarationBody child elements that carry a non-zero value."""
    out: List[str] = []
    for key in BODY_ELEMENTS:
        if key not in body or body[key] in (None, ""):
            continue
        if key in INTEGER_ELEMENTS:
            ival = int(dec(body[key]))
            if ival != 0:
                out.append(f"    <{key}>{ival}</{key}>")
        elif q2(body[key]) != 0:
            out.append(f"    <{key}>{amount(body[key])}</{key}>")
    return out


def _sales_annex_xml(annex: Optional[dict]) -> List[str]:
    """Render <salesAnnex> when partner lines exist, else nothing."""
    lines = (annex or {}).get("lines") or []
    if not lines:
        return []
    out = ["  <salesAnnex>"]
    for line in lines:
        out.append("    <saleLine>")
        if line.get("buyerRegCode"):
            out.append(f"      <buyerRegCode>{esc(line['buyerRegCode'])}</buyerRegCode>")
        if line.get("buyerName"):
            out.append(f"      <buyerName>{esc(line['buyerName'])}</buyerName>")
        if line.get("invoiceNumber"):
            out.append(f"      <invoiceNumber>{esc(line['invoiceNumber'])}</invoiceNumber>")
        if line.get("invoiceDate"):
            out.append(f"      <invoiceDate>{esc(line['invoiceDate'])}</invoiceDate>")
        out.append(f"      <invoiceSum>{amount(line.get('invoiceSum', 0))}</invoiceSum>")
        out.append(f"      <taxRate>{esc(line.get('taxRate', ''))}</taxRate>")
        if line.get("invoiceSumForRate") not in (None, ""):
            out.append(f"      <invoiceSumForRate>{amount(line['invoiceSumForRate'])}</invoiceSumForRate>")
        if line.get("sumForRateInPeriod") not in (None, ""):
            out.append(f"      <sumForRateInPeriod>{amount(line['sumForRateInPeriod'])}</sumForRateInPeriod>")
        if line.get("comments"):
            out.append(f"      <comments>{esc(line['comments'])}</comments>")
        out.append("    </saleLine>")
    out.append("  </salesAnnex>")
    return out


def _purchases_annex_xml(annex: Optional[dict]) -> List[str]:
    """Render <purchasesAnnex> when partner lines exist, else nothing."""
    lines = (annex or {}).get("lines") or []
    if not lines:
        return []
    out = ["  <purchasesAnnex>"]
    for line in lines:
        out.append("    <purchaseLine>")
        if line.get("sellerRegCode"):
            out.append(f"      <sellerRegCode>{esc(line['sellerRegCode'])}</sellerRegCode>")
        if line.get("sellerName"):
            out.append(f"      <sellerName>{esc(line['sellerName'])}</sellerName>")
        if line.get("invoiceNumber"):
            out.append(f"      <invoiceNumber>{esc(line['invoiceNumber'])}</invoiceNumber>")
        if line.get("invoiceDate"):
            out.append(f"      <invoiceDate>{esc(line['invoiceDate'])}</invoiceDate>")
        out.append(f"      <invoiceSumVat>{amount(line.get('invoiceSumVat', 0))}</invoiceSumVat>")
        if line.get("vatSum") not in (None, ""):
            out.append(f"      <vatSum>{amount(line['vatSum'])}</vatSum>")
        out.append(f"      <vatInPeriod>{amount(line.get('vatInPeriod', 0))}</vatInPeriod>")
        if line.get("comments"):
            out.append(f"      <comments>{esc(line['comments'])}</comments>")
        out.append("    </purchaseLine>")
    out.append("  </purchasesAnnex>")
    return out


def build_xml(data: dict) -> str:
    """Build the full vatDeclaration XML document as a string."""
    regcode = str(data["regcode"])
    year = int(dec(data["year"]))
    month = int(dec(data["month"]))
    dtype = int(dec(data.get("declaration_type", 1)))
    version = compute_version(year, month)
    body = data.get("declaration_body", {}) or {}
    sales = data.get("sales_annex")
    purchases = data.get("purchases_annex")
    has_sales = bool((sales or {}).get("lines"))
    has_purchases = bool((purchases or {}).get("lines"))

    out = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        "<vatDeclaration>",
        f"  <taxPayerRegCode>{esc(regcode)}</taxPayerRegCode>",
    ]
    if data.get("submitter_person_code"):
        out.append(
            f"  <submitterPersonCode>{esc(data['submitter_person_code'])}</submitterPersonCode>"
        )
    out += [
        f"  <year>{year}</year>",
        f"  <month>{month}</month>",
        f"  <declarationType>{dtype}</declarationType>",
        f"  <version>{version}</version>",
        "  <declarationBody>",
        f"    <noSales>{xml_flag(not has_sales)}</noSales>",
        f"    <noPurchases>{xml_flag(not has_purchases)}</noPurchases>",
        f"    <sumPerPartnerSales>{xml_flag((sales or {}).get('sum_per_partner', True) if has_sales else False)}</sumPerPartnerSales>",
        f"    <sumPerPartnerPurchases>{xml_flag((purchases or {}).get('sum_per_partner', True) if has_purchases else False)}</sumPerPartnerPurchases>",
    ]
    out += _body_xml(body)
    out.append("  </declarationBody>")
    out += _sales_annex_xml(sales)
    out += _purchases_annex_xml(purchases)
    out.append("</vatDeclaration>")
    return "\n".join(out) + "\n"


# --------------------------------------------------------------------------- #
# CSV generation (KMD2 machine format — the primary artifact)
# --------------------------------------------------------------------------- #
def _row(fields: List[str]) -> str:
    """Pad a field list to CSV_FIELDS and join with ';'."""
    padded = list(fields) + [""] * (CSV_FIELDS - len(fields))
    return ";".join(padded[:CSV_FIELDS])


def _csv_body_value(body: dict, key: str) -> str:
    """Render one declarationBody value for the CSV — blank when zero/absent."""
    if key not in body or body[key] in (None, ""):
        return ""
    if key in INTEGER_ELEMENTS:
        ival = int(dec(body[key]))
        return str(ival) if ival != 0 else ""
    value = q2(body[key])
    return amount(value) if value != 0 else ""


def build_csv(data: dict) -> str:
    """
    Build the KMD2 machine CSV: fixed 31-field rows, semicolon-separated, dot decimals,
    TRUE/FALSE flags, CRLF line endings, no BOM. Row types:
      header;{reg};{submitter};{year};{month};{declarationType}   — general part
      {version};{noSales};{noPurchases};{sumSales};{sumPurch};<26 body values>  — main form
      A;{buyerReg};{buyerName};{invNo};{invDate};{sum};{rate};{sumForRate};{sumInPeriod};{comments}
      B;{sellerReg};{sellerName};{invNo};{invDate};{sumVat};{vatSum};{vatInPeriod};{comments}
    """
    regcode = str(data["regcode"])
    year = int(dec(data["year"]))
    month = int(dec(data["month"]))
    dtype = int(dec(data.get("declaration_type", 1)))
    version = compute_version(year, month)
    submitter = str(data.get("submitter_person_code") or "")
    body = data.get("declaration_body", {}) or {}
    sales = data.get("sales_annex")
    purchases = data.get("purchases_annex")
    has_sales = bool((sales or {}).get("lines"))
    has_purchases = bool((purchases or {}).get("lines"))

    rows: List[str] = [
        _row(["header", regcode, submitter, str(year), str(month), str(dtype)]),
        _row(
            [
                version,
                csv_flag(not has_sales),
                csv_flag(not has_purchases),
                csv_flag((sales or {}).get("sum_per_partner", True) if has_sales else False),
                csv_flag((purchases or {}).get("sum_per_partner", True) if has_purchases else False),
            ]
            + [_csv_body_value(body, key) for key in BODY_ELEMENTS]
        ),
    ]

    for line in (sales or {}).get("lines") or []:
        rows.append(_row([
            "A",
            str(line.get("buyerRegCode", "") or ""),
            str(line.get("buyerName", "") or ""),
            str(line.get("invoiceNumber", "") or ""),
            csv_date(line.get("invoiceDate")),
            amount(line.get("invoiceSum", 0)),
            str(line.get("taxRate", "") or ""),
            amount(line["invoiceSumForRate"]) if line.get("invoiceSumForRate") not in (None, "") else "",
            amount(line["sumForRateInPeriod"]) if line.get("sumForRateInPeriod") not in (None, "") else "",
            str(line.get("comments", "") or ""),
        ]))

    for line in (purchases or {}).get("lines") or []:
        rows.append(_row([
            "B",
            str(line.get("sellerRegCode", "") or ""),
            str(line.get("sellerName", "") or ""),
            str(line.get("invoiceNumber", "") or ""),
            csv_date(line.get("invoiceDate")),
            amount(line.get("invoiceSumVat", 0)),
            amount(line["vatSum"]) if line.get("vatSum") not in (None, "") else "",
            amount(line.get("vatInPeriod", 0)),
            str(line.get("comments", "") or ""),
        ]))

    return "".join(row + "\r\n" for row in rows)


# --------------------------------------------------------------------------- #
# XSD validation
# --------------------------------------------------------------------------- #
def validate_xml_against_xsd(xml_text: str) -> Tuple[bool, str]:
    """
    Validate the XML against the bundled XSD using xmllint.

    Returns (ok, message). If xmllint is not installed, returns (True, warning) so the
    tool still runs in minimal environments. A genuine schema violation returns
    (False, errors).
    """
    if not XSD_PATH.exists():
        return False, f"bundled schema not found at {XSD_PATH}"
    with tempfile.NamedTemporaryFile(
        "w", suffix=".xml", encoding="utf-8", delete=False
    ) as tmp:
        tmp.write(xml_text)
        tmp_path = tmp.name
    try:
        proc = subprocess.run(
            ["xmllint", "--noout", "--schema", str(XSD_PATH), tmp_path],
            capture_output=True, text=True,
        )
    except FileNotFoundError:
        Path(tmp_path).unlink(missing_ok=True)
        return True, ("WARNING: xmllint not found — XSD validation skipped. "
                      "Install libxml2 (brew install libxml2) to validate output.")
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    if proc.returncode == 0:
        return True, "validates against vatdeclaration.xsd"
    return False, (proc.stderr or proc.stdout or "unknown xmllint error").strip()


# --------------------------------------------------------------------------- #
# Output-format self-check (validation gate — check 1, BLOCK)
# --------------------------------------------------------------------------- #
_NUMERIC_RE = re.compile(r"^$|^\d+$|^-?\d+\.\d{2}$")  # empty | integer | 2-decimal (dot)


def _numeric_ok(value: str) -> bool:
    """A CSV monetary/count field must be empty, an integer, or a 2-decimal dot value."""
    return bool(_NUMERIC_RE.match(value))


def self_check_csv(csv_text: str, version: str) -> List[str]:
    """
    Mechanically re-validate the generated CSV against e-MTA's fixed-column spec, so a
    malformed file never leaves the desk. Returns a list of BLOCK error strings.
    """
    errors: List[str] = []

    if not csv_text.endswith("\r\n"):
        errors.append("CSV must use CRLF line endings and end with CRLF")
    if "﻿" in csv_text:
        errors.append("CSV must not contain a BOM")

    rows = [r for r in csv_text.split("\r\n") if r != ""]
    if len(rows) < 2:
        errors.append("CSV must have at least the header and declarationBody rows")
        return errors

    for i, row in enumerate(rows, start=1):
        fields = row.split(";")
        if len(fields) != CSV_FIELDS:
            errors.append(
                f"CSV row {i} has {len(fields)} fields, expected {CSV_FIELDS} "
                "(an embedded ';' in a name/number corrupts the fixed-column layout)"
            )

    header = rows[0].split(";")
    if header[0] != "header":
        errors.append(f"CSV row 1 must start with 'header', got '{header[0]}'")

    body = rows[1].split(";")
    if body and body[0] != version:
        errors.append(f"CSV row 2 version is '{body[0]}', expected '{version}'")
    for idx in range(1, 5):  # noSales, noPurchases, sumPerPartnerSales, sumPerPartnerPurchases
        if len(body) > idx and body[idx] not in ("TRUE", "FALSE"):
            errors.append(f"CSV row 2 flag {idx} is '{body[idx]}', expected TRUE/FALSE")
    for idx in range(5, len(body)):  # the 26 declarationBody values
        if not _numeric_ok(body[idx]):
            errors.append(
                f"CSV row 2 body value {idx - 4} ('{body[idx]}') is not a dot-decimal "
                "amount (a comma decimal or a stray total-VAT column would land here)"
            )

    # Annex rows: check the monetary positions use dot decimals.
    monetary_positions = {"A": (5, 7, 8), "B": (5, 6, 7)}
    for i, row in enumerate(rows[2:], start=3):
        fields = row.split(";")
        kind = fields[0]
        if kind not in monetary_positions:
            errors.append(f"CSV row {i} has unknown row type '{kind}' (expected A or B)")
            continue
        for pos in monetary_positions[kind]:
            if pos < len(fields) and not _numeric_ok(fields[pos]):
                errors.append(f"CSV row {i} field {pos + 1} ('{fields[pos]}') is not a dot-decimal amount")

    return errors


def self_check_totals(data: dict) -> List[str]:
    """
    Recompute the derived figures and, when the caller supplies an expected value,
    assert the return agrees (check 1 + check 7). Returns BLOCK error strings.
    """
    errors: List[str] = []
    totals = compute_totals(data.get("declaration_body", {}) or {})

    if totals["_line12"] > 0 and totals["_line13"] > 0:
        errors.append(
            f"line 12 (payable {totals['_line12']:.2f}) and line 13 "
            f"(overpaid {totals['_line13']:.2f}) cannot both be non-zero"
        )

    expected_payable = data.get("expected_vat_payable")
    if expected_payable is not None and abs(q2(expected_payable) - totals["_line12"]) > TOLERANCE:
        errors.append(
            f"computed VAT payable (line 12) {totals['_line12']:.2f} does not match the "
            f"expected {q2(expected_payable):.2f} — recheck the bases / inputVatTotal"
        )
    expected_overpaid = data.get("expected_vat_overpaid")
    if expected_overpaid is not None and abs(q2(expected_overpaid) - totals["_line13"]) > TOLERANCE:
        errors.append(
            f"computed VAT overpaid (line 13) {totals['_line13']:.2f} does not match the "
            f"expected {q2(expected_overpaid):.2f} — recheck the bases / inputVatTotal"
        )
    return errors


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate the Estonian VAT return (KMD2 machine CSV + vatDeclaration XML)"
    )
    parser.add_argument("--input", help="Path to input JSON file")
    parser.add_argument("--output", default=".", help="Output directory (default: .)")
    parser.add_argument("--select-inf", metavar="INVOICES_JSON",
                        help="Select KMD INF partners from an invoice list (JSON array) "
                             "and print the selection; writes no files")
    parser.add_argument("--side", choices=("A", "B"),
                        help="With --select-inf: A = invoices issued, B = invoices received")
    args = parser.parse_args()

    if args.select_inf:
        if not args.side:
            parser.error("--select-inf needs --side A or --side B")
        if args.input:
            parser.error("--select-inf and --input are separate runs; pass one of them")
        try:
            with open(args.select_inf, encoding="utf-8") as fh:
                invoices = json.load(fh)
            selection = select_inf_partners(invoices, args.side)
        except (OSError, ValueError) as exc:  # json.JSONDecodeError is a ValueError
            print(f"INVALID INVOICE LIST: {exc}", file=sys.stderr)
            sys.exit(1)
        print(json.dumps(selection, indent=2, ensure_ascii=False, default=str))
        return
    if not args.input:
        parser.error("--input is required")

    try:
        with open(args.input, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as exc:  # json.JSONDecodeError is a ValueError
        print(f"INVALID INPUT FILE: {exc}", file=sys.stderr)
        sys.exit(1)

    errors = validate(data)
    if errors:
        print("VALIDATION ERRORS:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        sys.exit(1)

    regcode = str(data["regcode"])
    year = int(dec(data["year"]))
    month = int(dec(data["month"]))
    stem = f"{year}{month:02d}_{regcode}"

    # Build both artifacts, then run the output-format gate (check 1) BEFORE writing
    # anything. Any BLOCK error means no files are written — a malformed declaration
    # never reaches e-MTA.
    version = compute_version(year, month)
    xml_text = build_xml(data)
    csv_text = build_csv(data)

    xsd_ok, xsd_message = validate_xml_against_xsd(xml_text)
    block: List[str] = []
    if not xsd_ok:
        block.append(f"XML does not validate against vatdeclaration.xsd: {xsd_message}")
    block += self_check_csv(csv_text, version)
    block += self_check_totals(data)
    if block:
        print("OUTPUT-FORMAT GATE FAILED (BLOCK) — no files written:", file=sys.stderr)
        for err in block:
            print(f"  - {err}", file=sys.stderr)
        sys.exit(1)
    message = xsd_message

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / f"KMD_{stem}.csv"
    xml_path = output_dir / f"vatDeclaration_{stem}.xml"
    # CSV: bytes, no BOM, CRLF already embedded. XML: UTF-8.
    csv_path.write_bytes(csv_text.encode("utf-8"))
    xml_path.write_text(xml_text, encoding="utf-8")

    body = data.get("declaration_body", {}) or {}
    totals = compute_totals(body)
    print(f"Generated (PRIMARY):   {csv_path}")
    print(f"Generated (secondary): {xml_path}")
    print(f"Format gate: PASS ({message}; CSV 31-field rows, dot decimals, TRUE/FALSE, CRLF)")
    print(f"\nKMD {year}/{month:02d} — reg code {regcode} (version {version})")
    print(f"  Total VAT   (line 4):  EUR {totals['_line4']:.2f}  [computed by e-MTA]")
    print(f"  Input VAT   (line 5):  EUR {q2(body.get('inputVatTotal', 0)):.2f}")
    if totals["_line12"] > 0:
        print(f"  VAT PAYABLE (line 12): EUR {totals['_line12']:.2f}  [computed by e-MTA]")
    elif totals["_line13"] > 0:
        print(f"  VAT OVERPAID(line 13): EUR {totals['_line13']:.2f}  [computed by e-MTA]")
    else:
        print("  Net VAT: EUR 0.00")

    for warning in (reverse_charge_warnings(data) + domestic_reverse_charge_warnings(data)
                    + negative_bases_notes(data)):
        print(f"\nNOTE: {warning}")

    print("\nUpload the CSV at maasikas.emta.ee (or the XML). Deadline: 20th of next month.")


if __name__ == "__main__":
    main()
