import os
import random
import asyncio
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from fastapi import FastAPI, Request, Response, Form, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from sandbox.config import (
    FINANCE_USER,
    FINANCE_PASS,
    SECRET_KEY,
    FINANCE_DB_PATH,
    CHAOS_SLOW_PAGES,
    CHAOS_DELAY_SECONDS,
    CHAOS_500_ON_SUBMIT,
    CHAOS_ERROR_RATE,
    CHAOS_SESSION_EXPIRY,
    CHAOS_SESSION_MAX_REQUESTS,
    ENFORCE_DUPLICATE_CHECK
)
from sandbox.finance_system.db import (
    init_db,
    get_payables,
    get_payable_by_id,
    add_payable,
    clear_payables
)

app = FastAPI(title="CentrAlign Sandbox - Internal Finance System (Port 8002)")

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Initialize SQLite database on module import
init_db()

# Session tracking for chaos testing
SESSION_REQUEST_COUNTS: Dict[str, int] = {}

def get_session_user(request: Request) -> Optional[str]:
    session_cookie = request.cookies.get("finance_session")
    if not session_cookie:
        return None
    try:
        parts = session_cookie.split(":")
        if len(parts) == 2 and parts[0] == FINANCE_USER:
            return parts[0]
    except Exception:
        pass
    return None

async def apply_chaos_if_enabled(request: Request, user: Optional[str]) -> Optional[Response]:
    """Applies latency injection and session expiry chaos."""
    slow_pages = os.getenv("CHAOS_SLOW_PAGES", "false").lower() in ("true", "1", "yes") or CHAOS_SLOW_PAGES
    delay_secs = float(os.getenv("CHAOS_DELAY_SECONDS", str(CHAOS_DELAY_SECONDS)))
    session_expiry = os.getenv("CHAOS_SESSION_EXPIRY", "false").lower() in ("true", "1", "yes") or CHAOS_SESSION_EXPIRY
    max_reqs = int(os.getenv("CHAOS_SESSION_MAX_REQUESTS", str(CHAOS_SESSION_MAX_REQUESTS)))

    if slow_pages and delay_secs > 0:
        await asyncio.sleep(delay_secs)

    if session_expiry and user:
        session_id = request.cookies.get("finance_session", "")
        count = SESSION_REQUEST_COUNTS.get(session_id, 0) + 1
        SESSION_REQUEST_COUNTS[session_id] = count
        if count > max_reqs:
            resp = RedirectResponse(
                url="/login?error=Session+expired+due+to+inactivity.+Please+re-authenticate.",
                status_code=status.HTTP_303_SEE_OTHER
            )
            resp.delete_cookie("finance_session")
            SESSION_REQUEST_COUNTS.pop(session_id, None)
            return resp
    return None

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    user = get_session_user(request)
    if user:
        return RedirectResponse(url="/payables", status_code=status.HTTP_303_SEE_OTHER)
    return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

@app.get("/login", response_class=HTMLResponse)
async def login_get(request: Request, error: Optional[str] = None):
    chaos_resp = await apply_chaos_if_enabled(request, None)
    if chaos_resp:
        return chaos_resp

    user = get_session_user(request)
    if user:
        return RedirectResponse(url="/payables", status_code=status.HTTP_303_SEE_OTHER)

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

    if username == FINANCE_USER and password == FINANCE_PASS:
        resp = RedirectResponse(url="/payables", status_code=status.HTTP_303_SEE_OTHER)
        session_val = f"{username}:{int(datetime.now(timezone.utc).timestamp())}"
        resp.set_cookie(
            key="finance_session",
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
    session_id = request.cookies.get("finance_session", "")
    SESSION_REQUEST_COUNTS.pop(session_id, None)
    resp.delete_cookie("finance_session")
    return resp

@app.get("/payables", response_class=HTMLResponse)
async def list_payables(request: Request, success: Optional[str] = None):
    user = get_session_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    chaos_resp = await apply_chaos_if_enabled(request, user)
    if chaos_resp:
        return chaos_resp

    payables = get_payables()
    success_msg = None
    if success == "added":
        success_msg = "Successfully entered and recorded payable invoice into the ledger."

    return templates.TemplateResponse(
        request=request,
        name="payables.html",
        context={
            "authenticated": True,
            "user": user,
            "payables": payables,
            "success_message": success_msg
        }
    )

@app.get("/payables/add", response_class=HTMLResponse)
async def add_payable_get(request: Request):
    user = get_session_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    chaos_resp = await apply_chaos_if_enabled(request, user)
    if chaos_resp:
        return chaos_resp

    return templates.TemplateResponse(
        request=request,
        name="add_payable.html",
        context={
            "authenticated": True,
            "user": user,
            "error": None,
            "form_data": {}
        }
    )

@app.post("/payables/add", response_class=HTMLResponse)
async def add_payable_post(
    request: Request,
    vendor: str = Form(...),
    invoice_no: str = Form(...),
    amount: float = Form(...),
    due_date: str = Form(...),
    notes: Optional[str] = Form(None)
):
    user = get_session_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    chaos_resp = await apply_chaos_if_enabled(request, user)
    if chaos_resp:
        return chaos_resp

    form_payload = {
        "vendor": vendor,
        "invoice_no": invoice_no,
        "amount": amount,
        "due_date": due_date,
        "notes": notes or ""
    }

    # Chaos Injection: Simulated transient 500 error on form submit
    chaos_500 = os.getenv("CHAOS_500_ON_SUBMIT", "false").lower() in ("true", "1", "yes") or CHAOS_500_ON_SUBMIT
    error_rate = float(os.getenv("CHAOS_ERROR_RATE", str(CHAOS_ERROR_RATE)))
    if chaos_500 and (random.random() < error_rate):
        # We raise a 500 to test the agent's ability to retry or detect transient errors
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal Server Error: Transient database lock / network timeout during transaction commit. Please retry."
        )

    # Attempt insertion with duplicate check
    payable_id, error = add_payable(
        vendor=vendor,
        invoice_no=invoice_no,
        amount=amount,
        due_date=due_date,
        notes=notes
    )

    if error:
        # Check if it was duplicate or validation
        status_code = status.HTTP_409_CONFLICT if "duplicate" in error.lower() else status.HTTP_400_BAD_REQUEST
        return templates.TemplateResponse(
            request=request,
            name="add_payable.html",
            context={
                "authenticated": True,
                "user": user,
                "error": error,
                "form_data": form_payload
            },
            status_code=status_code
        )

    return RedirectResponse(
        url=f"/payables/{payable_id}?created=true",
        status_code=status.HTTP_303_SEE_OTHER
    )

@app.get("/payables/{payable_id}", response_class=HTMLResponse)
async def view_payable_detail(request: Request, payable_id: int):
    user = get_session_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    chaos_resp = await apply_chaos_if_enabled(request, user)
    if chaos_resp:
        return chaos_resp

    payable = get_payable_by_id(payable_id)
    if not payable:
        raise HTTPException(status_code=404, detail="Payable record not found.")

    return templates.TemplateResponse(
        request=request,
        name="payable_detail.html",
        context={
            "authenticated": True,
            "user": user,
            "payable": payable
        }
    )

# ==============================================================================
# GROUND TRUTH DEBUG ENDPOINT (FOR INDEPENDENT TEST HARNESS ONLY)
# ==============================================================================
@app.get("/api/debug/state", response_class=JSONResponse)
async def get_debug_state():
    """
    TESTING ONLY - Returns ground truth SQLite payables records.
    Autonomous agents must NOT query this endpoint.
    """
    payables = get_payables()
    return {
        "_warning": "DEBUG ONLY: Testing harness ground truth verification. Autonomous agent must NOT use this endpoint.",
        "payables_count": len(payables),
        "payables": payables,
        "enforce_duplicate_check": ENFORCE_DUPLICATE_CHECK,
        "chaos_config": {
            "slow_pages": CHAOS_SLOW_PAGES,
            "delay_seconds": CHAOS_DELAY_SECONDS,
            "transient_500_on_submit": CHAOS_500_ON_SUBMIT,
            "error_rate": CHAOS_ERROR_RATE,
            "session_expiry": CHAOS_SESSION_EXPIRY,
            "session_max_requests": CHAOS_SESSION_MAX_REQUESTS
        }
    }
