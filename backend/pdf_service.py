"""PDF generation for Estimates and Invoices using ReportLab."""
from io import BytesIO
from datetime import datetime, timezone
from typing import List, Optional

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.units import inch
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.colors import HexColor


def _money(v: float) -> str:
    return f"${v:,.2f}"


def _draw_header(c: Canvas, W: float, H: float, company: dict, kind: str, primary: str):
    c.setFillColor(HexColor(primary))
    c.rect(0, H - 0.9 * inch, W, 0.9 * inch, fill=1, stroke=0)
    c.setFillColor(HexColor("#FFFFFF"))
    c.setFont("Helvetica-Bold", 22)
    c.drawString(0.6 * inch, H - 0.55 * inch, company.get("name", "A1 Field Pro"))
    c.setFont("Helvetica", 10)
    c.drawString(0.6 * inch, H - 0.75 * inch, f"{company.get('industry','')} · {kind.upper()}")


def _draw_meta_block(c: Canvas, W: float, H: float, doc: dict, kind: str):
    c.setFillColor(HexColor("#0F172A"))
    c.setFont("Helvetica-Bold", 14)
    c.drawString(0.6 * inch, H - 1.4 * inch, kind.upper())
    c.setFont("Helvetica", 10)
    c.drawString(0.6 * inch, H - 1.6 * inch, f"#: {doc.get('number') or doc['id'][:8].upper()}")
    c.drawString(0.6 * inch, H - 1.75 * inch,
                 f"Date: {datetime.now(timezone.utc).strftime('%b %d, %Y')}")
    if doc.get("expires_at"):
        c.drawString(0.6 * inch, H - 1.90 * inch,
                     f"Valid until: {doc['expires_at'][:10]}")
    if doc.get("due_at"):
        c.drawString(0.6 * inch, H - 1.90 * inch, f"Due: {doc['due_at'][:10]}")


def _draw_bill_to(c: Canvas, H: float, doc: dict):
    c.setFont("Helvetica-Bold", 11)
    c.drawString(0.6 * inch, H - 2.2 * inch, "BILL TO")
    c.setFont("Helvetica", 10)
    y = H - 2.4 * inch
    for line in [
        doc.get("customer_name") or "Customer",
        doc.get("address") or "",
        doc.get("customer_phone") or "",
        doc.get("customer_email") or "",
    ]:
        if line:
            c.drawString(0.6 * inch, y, line[:80])
            y -= 0.15 * inch


def _draw_line_items(c: Canvas, W: float, y: float, items: List[dict]) -> float:
    c.setFillColor(HexColor("#F1F5F9"))
    c.rect(0.6 * inch, y - 0.05 * inch, W - 1.2 * inch, 0.3 * inch, fill=1, stroke=0)
    c.setFillColor(HexColor("#0F172A"))
    c.setFont("Helvetica-Bold", 10)
    c.drawString(0.7 * inch, y + 0.05 * inch, "DESCRIPTION")
    c.drawString(W - 3.0 * inch, y + 0.05 * inch, "QTY")
    c.drawString(W - 2.2 * inch, y + 0.05 * inch, "PRICE")
    c.drawRightString(W - 0.7 * inch, y + 0.05 * inch, "AMOUNT")
    y -= 0.35 * inch
    c.setFont("Helvetica", 10)
    for it in items:
        qty = float(it.get("qty", 0))
        up = float(it.get("unit_price", 0))
        amt = qty * up
        desc = (it.get("description") or "")[:60]
        c.drawString(0.7 * inch, y, desc)
        c.drawString(W - 3.0 * inch, y, f"{qty:g}")
        c.drawString(W - 2.2 * inch, y, _money(up))
        c.drawRightString(W - 0.7 * inch, y, _money(amt))
        y -= 0.22 * inch
        if y < 1.5 * inch:
            c.showPage()
            y = LETTER[1] - 1.0 * inch
            c.setFont("Helvetica", 10)
    return y


def _draw_totals(c: Canvas, W: float, y: float, totals: dict, primary: str, paid: float = 0.0,
                 deposit_amount: float = 0.0, label_total: str = "TOTAL"):
    c.setStrokeColor(HexColor("#E2E8F0"))
    c.line(W - 3.5 * inch, y, W - 0.6 * inch, y)
    y -= 0.25 * inch
    c.setFont("Helvetica", 10)
    rows = [("Subtotal", _money(totals["subtotal"]))]
    if totals.get("discount_amount", 0) > 0:
        rows.append(("Discount", f"-{_money(totals['discount_amount'])}"))
    if totals.get("tax_amount", 0) > 0:
        rows.append(("Tax", _money(totals["tax_amount"])))
    if deposit_amount > 0:
        rows.append(("Deposit required", _money(deposit_amount)))
    if paid > 0:
        rows.append(("Paid", f"-{_money(paid)}"))
    for label, val in rows:
        c.setFillColor(HexColor("#475569"))
        c.drawRightString(W - 1.8 * inch, y, label)
        c.setFillColor(HexColor("#0F172A"))
        c.drawRightString(W - 0.7 * inch, y, val)
        y -= 0.20 * inch

    y -= 0.05 * inch
    c.setStrokeColor(HexColor("#0F172A"))
    c.line(W - 3.5 * inch, y + 0.05 * inch, W - 0.6 * inch, y + 0.05 * inch)
    y -= 0.25 * inch
    c.setFont("Helvetica-Bold", 13)
    c.drawRightString(W - 1.8 * inch, y, label_total)
    c.setFillColor(HexColor(primary))
    final_total = totals["total"] - paid
    c.drawRightString(W - 0.7 * inch, y, _money(max(final_total, 0)))
    c.setFillColor(HexColor("#0F172A"))
    return y


def _draw_footer(c: Canvas, W: float, company: dict, terms: Optional[str] = ""):
    if terms:
        c.setFont("Helvetica-Oblique", 8)
        c.setFillColor(HexColor("#64748B"))
        y = 1.2 * inch
        c.drawString(0.6 * inch, y, "Terms:")
        for line in (terms or "")[:600].split("\n")[:4]:
            y -= 0.13 * inch
            c.drawString(0.6 * inch, y, line[:100])
    c.setFont("Helvetica", 8)
    c.setFillColor(HexColor("#94A3B8"))
    c.drawString(0.6 * inch, 0.5 * inch, f"Thank you — {company.get('name','')}")
    c.drawRightString(W - 0.6 * inch, 0.5 * inch, "Powered by A1 Field Pro")


# -------------------- Public API --------------------
def estimate_pdf(estimate: dict, company: dict, totals_by_tier: dict) -> bytes:
    primary = (company.get("branding") or {}).get("primary_color") or "#1D4ED8"
    buf = BytesIO()
    c = Canvas(buf, pagesize=LETTER)
    W, H = LETTER

    _draw_header(c, W, H, company, "estimate", primary)
    _draw_meta_block(c, W, H, estimate, "ESTIMATE")
    _draw_bill_to(c, H, estimate)

    y = H - 3.6 * inch
    c.setFillColor(HexColor("#0F172A"))
    c.setFont("Helvetica-Bold", 13)
    c.drawString(0.6 * inch, y, estimate.get("title", "Estimate"))
    y -= 0.25 * inch
    if estimate.get("intro"):
        c.setFont("Helvetica", 10)
        c.setFillColor(HexColor("#475569"))
        for line in (estimate["intro"] or "")[:300].split("\n")[:3]:
            c.drawString(0.6 * inch, y, line[:100])
            y -= 0.15 * inch
        c.setFillColor(HexColor("#0F172A"))
    y -= 0.2 * inch

    # If approved tier exists, show only that. Else show all tiers stacked.
    selected = estimate.get("selected_tier")
    tiers = estimate.get("tiers") or []
    if selected:
        tiers = [t for t in tiers if t.get("key") == selected]

    for tier in tiers:
        c.setFillColor(HexColor("#F8FAFC"))
        c.rect(0.6 * inch, y - 0.05 * inch, W - 1.2 * inch, 0.3 * inch, fill=1, stroke=0)
        c.setFillColor(HexColor("#0F172A"))
        c.setFont("Helvetica-Bold", 11)
        c.drawString(0.7 * inch, y + 0.05 * inch, tier.get("name", "").upper())
        t_total = totals_by_tier.get(tier.get("key"), {}).get("total", 0)
        c.drawRightString(W - 0.7 * inch, y + 0.05 * inch, _money(t_total))
        y -= 0.35 * inch
        if tier.get("summary"):
            c.setFont("Helvetica-Oblique", 9)
            c.setFillColor(HexColor("#64748B"))
            c.drawString(0.7 * inch, y, tier["summary"][:110])
            y -= 0.22 * inch
        c.setFillColor(HexColor("#0F172A"))
        y = _draw_line_items(c, W, y, tier.get("line_items") or [])
        y -= 0.1 * inch
        if y < 2.0 * inch:
            c.showPage()
            y = LETTER[1] - 1.0 * inch

    if selected and totals_by_tier.get(selected):
        deposit_amount = totals_by_tier[selected].get("deposit_amount", 0)
        y = _draw_totals(c, W, y - 0.1 * inch, totals_by_tier[selected], primary,
                         deposit_amount=deposit_amount, label_total="TOTAL")

    # Signature block if signed
    sig = estimate.get("signature")
    if sig and sig.get("data_url"):
        y = max(y - 0.6 * inch, 1.6 * inch)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(0.6 * inch, y, "Approved & signed by:")
        c.setFont("Helvetica", 10)
        c.drawString(0.6 * inch, y - 0.18 * inch, sig.get("signer_name", ""))
        c.setFont("Helvetica-Oblique", 8)
        c.setFillColor(HexColor("#64748B"))
        c.drawString(0.6 * inch, y - 0.32 * inch,
                     f"Signed on {(sig.get('signed_at') or '')[:19].replace('T',' ')} UTC")
        c.setFillColor(HexColor("#0F172A"))

    _draw_footer(c, W, company, estimate.get("terms"))
    c.showPage()
    c.save()
    return buf.getvalue()


def invoice_pdf(invoice: dict, company: dict, totals: dict, paid: float) -> bytes:
    primary = (company.get("branding") or {}).get("primary_color") or "#1D4ED8"
    buf = BytesIO()
    c = Canvas(buf, pagesize=LETTER)
    W, H = LETTER

    _draw_header(c, W, H, company, "invoice", primary)
    _draw_meta_block(c, W, H, invoice, "INVOICE")
    _draw_bill_to(c, H, invoice)

    y = H - 3.6 * inch
    c.setFont("Helvetica-Bold", 13)
    c.drawString(0.6 * inch, y, invoice.get("title") or "Services rendered")
    y -= 0.3 * inch

    y = _draw_line_items(c, W, y, invoice.get("line_items") or [])

    y = _draw_totals(c, W, y - 0.1 * inch, totals, primary, paid=paid,
                     deposit_amount=totals.get("deposit_amount", 0),
                     label_total="BALANCE DUE" if paid > 0 else "TOTAL")

    if (totals["total"] - paid) <= 0.01:
        c.setFillColor(HexColor("#16A34A"))
        c.setFont("Helvetica-Bold", 22)
        c.drawString(0.7 * inch, y - 0.3 * inch, "PAID")
        c.setFillColor(HexColor("#0F172A"))

    _draw_footer(c, W, company, invoice.get("terms"))
    c.showPage()
    c.save()
    return buf.getvalue()
