from fastapi import APIRouter, Depends
from typing import List, Optional
from datetime import datetime, timezone
from collections import defaultdict
from app.schemas.common import FirestoreOut
from app.infra.firestore.client import get_db
from app.core.tenant import get_current_tenant
from app.core.rbac import require_permission

router = APIRouter()


def _month_key(iso) -> str:
    """Group key from an ISO timestamp or datetime -> YYYY-MM."""
    if isinstance(iso, datetime):
        return iso.strftime("%Y-%m")
    if isinstance(iso, str) and iso:
        return iso[:7]
    return "Unknown"


def _billed_total(inv: dict) -> float:
    """Recompute the original billed amount (items exclude GST) + GST breakup."""
    items = inv.get("items") or []
    item_sum = sum(float(i.get("amount", 0)) for i in items)
    breakup = inv.get("gst_breakup") or {}
    gst = float(breakup.get("igst") or 0) + float(breakup.get("cgst") or 0) + float(breakup.get("sgst") or 0)
    return round(item_sum + gst, 2) if (items or breakup) else float(inv.get("total", 0))


def _collected(inv: dict) -> float:
    """Amount received = billed - current outstanding (payments reduce 'total')."""
    billed = _billed_total(inv)
    outstanding = float(inv.get("total", billed))
    return round(max(billed - outstanding, 0), 2)


@router.get("/receivables-aging")
async def receivables_aging(
    _: None = Depends(require_permission("reports", "view"))
):
    """Receivables aging (doc §5.6): outstanding amount + count per bucket 0-30/31-60/61-90/90+."""
    db = get_db()
    tenant_id = get_current_tenant()
    docs = list(db.collection("invoices").where("tenant_id", "==", tenant_id).stream())
    clients = {d.id: d.to_dict().get("name", "Unknown") for d in db.collection("clients").where("tenant_id", "==", tenant_id).stream()}

    buckets = {"0-30": {"amount": 0.0, "count": 0, "invoices": []},
               "31-60": {"amount": 0.0, "count": 0, "invoices": []},
               "61-90": {"amount": 0.0, "count": 0, "invoices": []},
               "90+": {"amount": 0.0, "count": 0, "invoices": []}}
    today = datetime.now().date()

    for d in docs:
        data = d.to_dict()
        outstanding = float(data.get("total", 0))
        if outstanding <= 0:
            continue
        due = data.get("due_date") or ""
        try:
            due_date = datetime.strptime(due[:10], "%Y-%m-%d").date()
        except (ValueError, TypeError):
            continue
        delta = (today - due_date).days
        if delta <= 0:
            continue
        elif delta <= 30:
            key = "0-30"
        elif delta <= 60:
            key = "31-60"
        elif delta <= 90:
            key = "61-90"
        else:
            key = "90+"
        buckets[key]["amount"] += outstanding
        buckets[key]["count"] += 1
        buckets[key]["invoices"].append({
            "id": d.id,
            "invoice_number": data.get("invoice_number"),
            "client_id": data.get("client_id"),
            "client_name": clients.get(data.get("client_id", ""), "Unknown"),
            "outstanding": round(outstanding, 2),
            "due_date": due,
        })

    summary = {k: {"amount": round(v["amount"], 2), "count": v["count"]} for k, v in buckets.items()}
    total_amount = round(sum(v["amount"] for v in buckets.values()), 2)
    return {
        "summary": summary,
        "total_outstanding": total_amount,
        "total_invoices": sum(v["count"] for v in buckets.values()),
        "detail": buckets,
    }


@router.get("/revenue-by-client")
async def revenue_by_client(
    _: None = Depends(require_permission("reports", "view"))
):
    """Revenue by client — billed, collected and outstanding per client (doc §5.6)."""
    db = get_db()
    tenant_id = get_current_tenant()
    docs = list(db.collection("invoices").where("tenant_id", "==", tenant_id).stream())
    clients = {d.id: d.to_dict().get("name", "Unknown") for d in db.collection("clients").where("tenant_id", "==", tenant_id).stream()}

    by_client: dict[str, dict] = defaultdict(lambda: {"billed": 0.0, "collected": 0.0, "outstanding": 0.0, "invoice_count": 0})
    for d in docs:
        data = d.to_dict()
        cid = data.get("client_id", "")
        billed = _billed_total(data)
        collected = _collected(data)
        by_client[cid]["billed"] += billed
        by_client[cid]["collected"] += collected
        by_client[cid]["outstanding"] += round(billed - collected, 2)
        by_client[cid]["invoice_count"] += 1

    rows = [
        {
            "client_id": cid,
            "client_name": clients.get(cid, "Unknown"),
            "billed": round(v["billed"], 2),
            "collected": round(v["collected"], 2),
            "outstanding": round(v["outstanding"], 2),
            "invoice_count": v["invoice_count"],
        }
        for cid, v in sorted(by_client.items(), key=lambda x: -x[1]["billed"])
    ]
    grand_total = round(sum(r["billed"] for r in rows), 2)
    return {"rows": rows, "grand_total": grand_total}


@router.get("/revenue-by-service")
async def revenue_by_service(
    _: None = Depends(require_permission("reports", "view"))
):
    """Revenue by service — grouped by SAC code / description (doc §5.6)."""
    db = get_db()
    tenant_id = get_current_tenant()
    docs = list(db.collection("invoices").where("tenant_id", "==", tenant_id).stream())

    by_service: dict[str, dict] = defaultdict(lambda: {"sac_code": "", "amount": 0.0, "gst": 0.0, "invoice_count": 0, "clients": []})
    for d in docs:
        data = d.to_dict()
        for item in data.get("items") or []:
            desc = (item.get("description") or "Unknown").strip()
            sac = item.get("sac_code") or ""
            key = f"{sac}·{desc}"
            by_service[key]["sac_code"] = sac
            by_service[key]["amount"] += float(item.get("amount", 0))
            by_service[key]["gst"] += float(item.get("amount", 0)) * float(item.get("gst_rate", 18)) / 100
            by_service[key]["invoice_count"] += 1
            cname = data.get("client_id", "")
            if cname not in by_service[key]["clients"]:
                by_service[key]["clients"].append(cname)

    rows = [
        {
            "service": k.split("·", 1)[1] if "·" in k else k,
            "sac_code": v["sac_code"],
            "amount": round(v["amount"], 2),
            "gst": round(v["gst"], 2),
            "total": round(v["amount"] + v["gst"], 2),
            "invoice_count": v["invoice_count"],
        }
        for k, v in sorted(by_service.items(), key=lambda x: -x[1]["amount"])
    ]
    grand_total = round(sum(r["total"] for r in rows), 2)
    return {"rows": rows, "grand_total": grand_total}


@router.get("/gst-liability")
async def gst_liability(
    _: None = Depends(require_permission("reports", "view"))
):
    """GST liability summary — CGST/SGST/IGST breakup with monthly view (doc §5.6)."""
    db = get_db()
    tenant_id = get_current_tenant()
    docs = list(db.collection("invoices").where("tenant_id", "==", tenant_id).stream())

    totals = {"cgst": 0.0, "sgst": 0.0, "igst": 0.0}
    by_month: dict[str, dict] = defaultdict(lambda: {"cgst": 0.0, "sgst": 0.0, "igst": 0.0, "count": 0})
    for d in docs:
        data = d.to_dict()
        breakup = data.get("gst_breakup") or {}
        cgst = float(breakup.get("cgst") or 0)
        sgst = float(breakup.get("sgst") or 0)
        igst = float(breakup.get("igst") or 0)
        totals["cgst"] += cgst
        totals["sgst"] += sgst
        totals["igst"] += igst
        mk = _month_key(data.get("created_at"))
        by_month[mk]["cgst"] += cgst
        by_month[mk]["sgst"] += sgst
        by_month[mk]["igst"] += igst
        by_month[mk]["count"] += 1

    monthly = [
        {"month": mk, **{"cgst": round(v["cgst"], 2), "sgst": round(v["sgst"], 2), "igst": round(v["igst"], 2),
         "total": round(v["cgst"] + v["sgst"] + v["igst"], 2), "invoice_count": v["count"]}}
        for mk, v in sorted(by_month.items())
    ]
    grand_total = round(totals["cgst"] + totals["sgst"] + totals["igst"], 2)
    return {
        "totals": {"cgst": round(totals["cgst"], 2), "sgst": round(totals["sgst"], 2), "igst": round(totals["igst"], 2), "total": grand_total},
        "monthly": monthly,
    }


@router.get("/monthly-mis")
async def monthly_mis(
    _: None = Depends(require_permission("reports", "view"))
):
    """Monthly MIS — invoiced vs collected per month (doc §5.6)."""
    db = get_db()
    tenant_id = get_current_tenant()
    docs = list(db.collection("invoices").where("tenant_id", "==", tenant_id).stream())

    by_month: dict[str, dict] = defaultdict(lambda: {"billed": 0.0, "collected": 0.0, "outstanding": 0.0, "invoice_count": 0})
    for d in docs:
        data = d.to_dict()
        mk = _month_key(data.get("created_at"))
        billed = _billed_total(data)
        collected = _collected(data)
        by_month[mk]["billed"] += billed
        by_month[mk]["collected"] += collected
        by_month[mk]["outstanding"] += round(billed - collected, 2)
        by_month[mk]["invoice_count"] += 1

    rows = [
        {"month": mk, "billed": round(v["billed"], 2), "collected": round(v["collected"], 2),
         "outstanding": round(v["outstanding"], 2), "invoice_count": v["invoice_count"],
         "collection_rate": round(v["collected"] / v["billed"] * 100, 1) if v["billed"] else 0}
        for mk, v in sorted(by_month.items(), reverse=True)
    ]
    tot_billed = round(sum(r["billed"] for r in rows), 2)
    tot_collected = round(sum(r["collected"] for r in rows), 2)
    return {
        "rows": rows,
        "totals": {
            "billed": tot_billed,
            "collected": tot_collected,
            "outstanding": round(tot_billed - tot_collected, 2),
            "collection_rate": round(tot_collected / tot_billed * 100, 1) if tot_billed else 0,
        },
    }