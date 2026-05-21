"""Direct test of handle_invoice_payment webhook hook (motor binds to one loop)."""
import sys
import uuid
import pytest

sys.path.insert(0, "/app/backend")


@pytest.mark.asyncio
async def test_handle_invoice_payment_flow():
    """Combines full + partial scenarios into one event loop (motor client binding)."""
    from deps import db, now_iso
    from routers.invoices import handle_invoice_payment

    # ---- FULL payment ----
    iid = str(uuid.uuid4())
    await db.invoices.insert_one({
        "id": iid, "number": "I-9999", "company_id": "TEST_COMPANY_HOOK",
        "public_token": "tok_" + uuid.uuid4().hex,
        "line_items": [{"description": "Svc", "qty": 1, "unit_price": 100, "taxable": True}],
        "tax_rate": 0, "discount": {"type": "percent", "value": 0},
        "deposit": {"type": "none", "value": 0},
        "status": "sent", "payments": [],
        "created_at": now_iso(), "updated_at": now_iso(),
    })
    try:
        await handle_invoice_payment({
            "invoice_id": iid, "amount": 100.0, "currency": "usd",
            "session_id": "sess_test", "pay_type": "full",
        })
        after = await db.invoices.find_one({"id": iid}, {"_id": 0})
        assert after["status"] == "paid"
        assert after["paid_at"]
        assert len(after["payments"]) == 1
        assert after["payments"][0]["status"] == "paid"
    finally:
        await db.invoices.delete_one({"id": iid})

    # ---- Deposit then balance ----
    iid2 = str(uuid.uuid4())
    await db.invoices.insert_one({
        "id": iid2, "number": "I-9998", "company_id": "TEST_COMPANY_HOOK2",
        "public_token": "tok_" + uuid.uuid4().hex,
        "line_items": [{"description": "Svc", "qty": 1, "unit_price": 200, "taxable": True}],
        "tax_rate": 0, "discount": {"type": "percent", "value": 0},
        "deposit": {"type": "percent", "value": 25},
        "status": "sent", "payments": [],
        "created_at": now_iso(), "updated_at": now_iso(),
    })
    try:
        await handle_invoice_payment({
            "invoice_id": iid2, "amount": 50.0, "currency": "usd",
            "session_id": "sess_dep", "pay_type": "deposit",
        })
        after1 = await db.invoices.find_one({"id": iid2}, {"_id": 0})
        assert after1["status"] == "partial"
        await handle_invoice_payment({
            "invoice_id": iid2, "amount": 150.0, "currency": "usd",
            "session_id": "sess_bal", "pay_type": "balance",
        })
        after2 = await db.invoices.find_one({"id": iid2}, {"_id": 0})
        assert after2["status"] == "paid"
        assert len(after2["payments"]) == 2
    finally:
        await db.invoices.delete_one({"id": iid2})
