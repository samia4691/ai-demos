"""
doc_extraction.py  —  unstructured documents to trustworthy structured JSON.

The pattern behind most "turn our messy files into data" jobs. What makes it trustworthy
is not the LLM call, it is everything around it:

  ingest -> OCR (with per-field confidence) -> schema-enforced extraction ->
  validation -> deterministic business rules -> confidence gate (auto vs human review) -> output

Low-confidence or rule-failing docs are routed to a human instead of being silently wrong.
Runs offline: OCR and the LLM extractor are stubs. Swap them for Textract/Tesseract and a
provider call; the validation, rules, and gating stay exactly the same.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable
import re


@dataclass
class Field:
    type: type
    required: bool = True
    validate: Callable[[object], bool] | None = None


# Target schema for an invoice
INVOICE_SCHEMA = {
    "invoice_no": Field(str, validate=lambda v: bool(re.fullmatch(r"INV-\d{4,}", v))),
    "vendor":     Field(str),
    "amount":     Field(float, validate=lambda v: v > 0),
    "currency":   Field(str, validate=lambda v: v in {"USD", "EUR", "GBP"}),
    "net_days":   Field(int, required=False, validate=lambda v: 0 <= v <= 180),
}


@dataclass
class ExtractResult:
    data: dict
    confidence: dict            # field -> 0..1
    status: str = "pending"     # auto_approved | needs_review | rejected
    issues: list[str] = field(default_factory=list)


def validate_against_schema(data: dict, schema: dict) -> list[str]:
    issues = []
    for name, spec in schema.items():
        if name not in data or data[name] is None:
            if spec.required:
                issues.append(f"missing required field '{name}'")
            continue
        val = data[name]
        if not isinstance(val, spec.type):
            issues.append(f"'{name}' should be {spec.type.__name__}, got {type(val).__name__}")
            continue
        if spec.validate and not spec.validate(val):
            issues.append(f"'{name}' failed validation (value={val!r})")
    return issues


def business_rules(data: dict) -> list[str]:
    """Deterministic checks that must never be left to the model."""
    issues = []
    if data.get("amount", 0) > 10000 and data.get("net_days", 0) < 15:
        issues.append("high-value invoice with unusually short payment terms — flag for approval")
    if data.get("currency") == "USD" and data.get("vendor", "").endswith("GmbH"):
        issues.append("German vendor billing in USD — verify currency")
    return issues


def process(doc_id: str, ocr: Callable[[str], tuple[str, dict]],
            extract: Callable[[str], tuple[dict, dict]],
            auto_threshold: float = 0.85) -> ExtractResult:
    text, ocr_conf = ocr(doc_id)
    data, field_conf = extract(text)

    issues = validate_against_schema(data, INVOICE_SCHEMA)
    issues += business_rules(data)

    min_conf = min(field_conf.values()) if field_conf else 0.0
    if issues and any("missing" in i or "should be" in i or "failed validation" in i for i in issues):
        status = "rejected"                 # structurally broken -> never auto-approve
    elif min_conf < auto_threshold or issues:
        status = "needs_review"             # human-in-the-loop
    else:
        status = "auto_approved"
    return ExtractResult(data=data, confidence=field_conf, status=status, issues=issues)


# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    import json

    def ocr(doc_id):
        pages = {
            "clean.pdf":  ("Invoice INV-1042 Acme Corp Total 4200.00 USD Net 30", {"page": 0.99}),
            "blurry.pdf": ("Inv0ice INV-2001 Globex Total 15000.00 USD Net 7", {"page": 0.62}),
            "broken.pdf": ("scan failed", {"page": 0.40}),
        }
        return pages[doc_id]

    def extract(text):
        # Stub LLM: pulls fields + emits per-field confidence.
        m_no = re.search(r"INV-\d{4,}", text)
        m_amt = re.search(r"Total\s+([\d.]+)", text)
        m_cur = re.search(r"\b(USD|EUR|GBP)\b", text)
        m_net = re.search(r"Net\s+(\d+)", text)
        vendor = "Acme Corp" if "Acme" in text else ("Globex" if "Globex" in text else "")
        data, conf = {}, {}
        if m_no: data["invoice_no"], conf["invoice_no"] = m_no.group(0), 0.97
        data["vendor"], conf["vendor"] = vendor, (0.95 if vendor else 0.3)
        if m_amt: data["amount"], conf["amount"] = float(m_amt.group(1)), 0.9
        if m_cur: data["currency"], conf["currency"] = m_cur.group(1), 0.88
        if m_net: data["net_days"], conf["net_days"] = int(m_net.group(1)), 0.92
        return data, conf

    for doc in ["clean.pdf", "blurry.pdf", "broken.pdf"]:
        r = process(doc, ocr, extract)
        print(f"\n{doc}: {r.status.upper()}")
        print("  data:", json.dumps(r.data))
        if r.issues:
            print("  issues:", r.issues)
