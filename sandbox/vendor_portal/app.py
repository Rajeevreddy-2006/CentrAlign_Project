import json
import asyncio
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from fastapi import FastAPI, Request, Response, Form, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from sandbox.config import (
    VENDOR_USER,
    VENDOR_PASS,
    SECRET_KEY,
    VENDORS_FILE,
    INVOICES_DIR,
    CHAOS_SLOW_PAGES,
    CHAOS_DELAY_SECONDS,
    CHAOS_SESSION_EXPIRY,
    CHAOS_SESSION_MAX_REQUESTS
)

app = FastAPI(title="CentrAlign Sandbox - Vendor Portal (Port 8001)")

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Session tracking for chaos testing
SESSION_REQUEST_COUNTS: Dict[str, int] = {}

def get_vendors_data() -> list:
    if not VENDORS_FILE.exists():
        return []
    with open(VENDORS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def get_session_user(request: Request) -> Optional[str]:
    session_cookie = request.cookies.get("vp_session")
    if not session_cookie:
        return None
    try:
        parts = session_cookie.split(":")
        if len(parts) == 2 and parts[0] == VENDOR_USER:
            return parts[0]
    except Exception:
        pass
    return None

async def apply_chaos_if_enabled(request: Request, user: Optional[str]) -> Optional[Response]:
    """Applies latency injection and session expiry chaos."""
    if CHAOS_SLOW_PAGES:
        await asyncio.sleep(CHAOS_DELAY_SECONDS)

    if CHAOS_SESSION_EXPIRY and user:
        session_id = request.cookies.get("vp_session", "")
        count = SESSION_REQUEST_COUNTS.get(session_id, 0) + 1
        SESSION_REQUEST_COUNTS[session_id] = count
        if count > CHAOS_SESSION_MAX_REQUESTS:
            # Force session expiry
            resp = RedirectResponse(url="/login?error=Session+expired+due+to+inactivity.+Please+re-authenticate.", status_code=status.HTTP_303_SEE_OTHER)
            resp.delete_cookie("vp_session")
            SESSION_REQUEST_COUNTS.pop(session_id, None)
            return resp
    return None

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    user = get_session_user(request)
    if user:
        return RedirectResponse(url="/vendors", status_code=status.HTTP_303_SEE_OTHER)
    return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

@app.get("/login", response_class=HTMLResponse)
async def login_get(request: Request, error: Optional[str] = None):
    chaos_resp = await apply_chaos_if_enabled(request, None)
    if chaos_resp:
        return chaos_resp

    user = get_session_user(request)
    if user:
        return RedirectResponse(url="/vendors", status_code=status.HTTP_303_SEE_OTHER)

    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={
            "authenticated": False,
            "error": error,
            "username": ""
        }
    )

@app.post("/login", response_class=HTMLResponse)
async def login_post(
    request: Request,
    username: str = Form(...),
    password: str = Form(...)
):
    chaos_resp = await apply_chaos_if_enabled(request, None)
    if chaos_resp:
        return chaos_resp

    if username == VENDOR_USER and password == VENDOR_PASS:
        resp = RedirectResponse(url="/vendors", status_code=status.HTTP_303_SEE_OTHER)
        session_val = f"{username}:{int(datetime.now(timezone.utc).timestamp())}"
        resp.set_cookie(
            key="vp_session",
            value=session_val,
            httponly=True,
            samesite="lax"
        )
        SESSION_REQUEST_COUNTS[session_val] = 0
        return resp

    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={
            "authenticated": False,
            "error": "Invalid username or password.",
            "username": username
        },
        status_code=status.HTTP_401_UNAUTHORIZED
    )

@app.post("/logout")
@app.get("/logout")
async def logout(request: Request):
    resp = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    session_id = request.cookies.get("vp_session", "")
    SESSION_REQUEST_COUNTS.pop(session_id, None)
    resp.delete_cookie("vp_session")
    return resp

@app.get("/vendors", response_class=HTMLResponse)
async def list_vendors(request: Request):
    user = get_session_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    chaos_resp = await apply_chaos_if_enabled(request, user)
    if chaos_resp:
        return chaos_resp

    vendors = get_vendors_data()
    return templates.TemplateResponse(
        request=request,
        name="vendors.html",
        context={
            "authenticated": True,
            "user": user,
            "vendors": vendors
        }
    )

@app.get("/vendors/{slug}", response_class=HTMLResponse)
async def view_vendor_invoices(request: Request, slug: str):
    user = get_session_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    chaos_resp = await apply_chaos_if_enabled(request, user)
    if chaos_resp:
        return chaos_resp

    vendors = get_vendors_data()
    vendor = next((v for v in vendors if v["slug"] == slug), None)
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found.")

    template_name = "invoices_cards.html" if vendor.get("layout") == "cards" else "invoices_table.html"
    return templates.TemplateResponse(
        request=request,
        name=template_name,
        context={
            "authenticated": True,
            "user": user,
            "vendor": vendor
        }
    )

@app.get("/download/{vendor_slug}/{filename}")
async def download_invoice_pdf(request: Request, vendor_slug: str, filename: str):
    user = get_session_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    pdf_path = INVOICES_DIR / vendor_slug / filename
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="Invoice PDF file not found.")

    return FileResponse(
        path=str(pdf_path),
        filename=filename,
        media_type="application/pdf"
    )

# ==============================================================================
# GROUND TRUTH DEBUG ENDPOINT (FOR INDEPENDENT TEST HARNESS ONLY)
# ==============================================================================
@app.get("/api/debug/state", response_class=JSONResponse)
async def get_debug_state():
    """
    TESTING ONLY - Returns ground truth vendor catalog and calculated latest invoices.
    Autonomous agents must NOT query this endpoint.
    """
    vendors = get_vendors_data()

    ground_truth_latest = {}
    for v in vendors:
        invoices = v.get("invoices", [])
        if invoices:
            # Sort by issue_date descending to determine ground truth latest
            sorted_inv = sorted(
                invoices,
                key=lambda x: datetime.strptime(x["issue_date"], "%Y-%m-%d"),
                reverse=True
            )
            latest = sorted_inv[0]
            ground_truth_latest[v["name"]] = {
                "vendor_slug": v["slug"],
                "invoice_no": latest["invoice_no"],
                "issue_date": latest["issue_date"],
                "due_date": latest["due_date"],
                "amount": latest["amount"],
                "currency": latest["currency"],
                "status": latest["status"]
            }

    return {
        "_warning": "DEBUG ONLY: Testing harness ground truth verification. Autonomous agent must NOT use this endpoint.",
        "vendors_count": len(vendors),
        "invoices_total": sum(len(v.get("invoices", [])) for v in vendors),
        "ground_truth_latest_invoices": ground_truth_latest,
        "vendors": vendors,
        "chaos_config": {
            "slow_pages": CHAOS_SLOW_PAGES,
            "delay_seconds": CHAOS_DELAY_SECONDS,
            "session_expiry": CHAOS_SESSION_EXPIRY,
            "session_max_requests": CHAOS_SESSION_MAX_REQUESTS
        }
    }
