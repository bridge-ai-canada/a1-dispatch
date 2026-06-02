"""CSV exports for jobs, customers, payments. Owner/accountant only."""
import csv
import io
from typing import Optional
from fastapi import APIRouter, Depends, Query, Response

from deps import db, require_role


router = APIRouter()


def _csv_response(rows: list, filename: str, columns: list[str]) -> Response:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=columns, extrasaction="ignore")
    w.writeheader()
    for r in rows:
        w.writerow({c: r.get(c, "") for c in columns})
    return Response(
        content=buf.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _date_clause(field: str, frm: Optional[str], to: Optional[str]) -> dict:
    cond: dict = {}
    if frm:
        cond["$gte"] = frm
    if to:
        cond["$lte"] = to
    return {field: cond} if cond else {}


@router.get("/exports/jobs.csv")
async def export_jobs_csv(
    user: dict = Depends(require_role("owner", "accountant", "super_admin")),
    frm: Optional[str] = Query(None, alias="from"),
    to: Optional[str] = Query(None),
):
    q = {"company_id": user["company_id"]}
    q.update(_date_clause("created_at", frm, to))
    rows = await db.jobs.find(q, {"_id": 0}).sort("created_at", -1).to_list(10000)
    cols = ["id", "created_at", "status", "title", "customer_name", "customer_phone",
            "customer_email", "address", "job_type", "assigned_to",
            "scheduled_at", "duration_min", "price", "tip", "paid", "paid_at",
            "rating", "source"]
    return _csv_response(rows, "jobs.csv", cols)


@router.get("/exports/customers.csv")
async def export_customers_csv(
    user: dict = Depends(require_role("owner", "accountant", "super_admin")),
    frm: Optional[str] = Query(None, alias="from"),
    to: Optional[str] = Query(None),
):
    q = {"company_id": user["company_id"]}
    q.update(_date_clause("created_at", frm, to))
    rows = await db.customers.find(q, {"_id": 0}).sort("created_at", -1).to_list(10000)
    for r in rows:
        r["tags"] = ",".join(r.get("tags", []) or [])
    cols = ["id", "created_at", "name", "phone", "email", "address",
            "status", "tags", "source", "notes"]
    return _csv_response(rows, "customers.csv", cols)


@router.get("/exports/payments.csv")
async def export_payments_csv(
    user: dict = Depends(require_role("owner", "accountant", "super_admin")),
    frm: Optional[str] = Query(None, alias="from"),
    to: Optional[str] = Query(None),
):
    q = {"company_id": user["company_id"]}
    q.update(_date_clause("created_at", frm, to))
    rows = await db.payment_transactions.find(q, {"_id": 0}).sort("created_at", -1).to_list(10000)
    cols = ["id", "created_at", "session_id", "job_id", "user_id",
            "amount", "currency", "payment_status", "status", "type", "processed"]
    return _csv_response(rows, "payments.csv", cols)
