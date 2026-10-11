import sqlite3
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any, Tuple
from pathlib import Path
from sandbox.config import FINANCE_DB_PATH, ENFORCE_DUPLICATE_CHECK

def get_connection() -> sqlite3.Connection:
    FINANCE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(FINANCE_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db() -> None:
    conn = get_connection()
    with conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS payables (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vendor TEXT NOT NULL,
                invoice_no TEXT NOT NULL,
                amount REAL NOT NULL,
                currency TEXT NOT NULL DEFAULT 'USD',
                due_date TEXT NOT NULL,
                notes TEXT,
                status TEXT NOT NULL DEFAULT 'RECORDED',
                source TEXT NOT NULL DEFAULT 'AI_TASK_WORKER',
                created_at TEXT NOT NULL,
                UNIQUE(vendor, invoice_no)
            )
        """)
    conn.close()

def get_payables() -> List[Dict[str, Any]]:
    init_db()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM payables ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_payable_by_id(payable_id: int) -> Optional[Dict[str, Any]]:
    init_db()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM payables WHERE id = ?", (payable_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_payable_by_vendor_and_invoice(vendor: str, invoice_no: str) -> Optional[Dict[str, Any]]:
    init_db()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM payables WHERE LOWER(TRIM(vendor)) = LOWER(TRIM(?)) AND LOWER(TRIM(invoice_no)) = LOWER(TRIM(?))",
        (vendor, invoice_no)
    )
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def add_payable(
    vendor: str,
    invoice_no: str,
    amount: float,
    due_date: str,
    notes: Optional[str] = None,
    currency: str = "USD"
) -> Tuple[Optional[int], Optional[str]]:
    """
    Inserts a new payable record.
    Returns (payable_id, None) on success or (None, error_message) on failure.
    """
    init_db()
    vendor = vendor.strip()
    invoice_no = invoice_no.strip()
    due_date = due_date.strip()
    notes = (notes or "").strip()

    if not vendor:
        return None, "Vendor name is required."
    if not invoice_no:
        return None, "Invoice number is required."
    if amount <= 0:
        return None, "Invoice amount must be greater than zero."
    if not due_date:
        return None, "Due date is required."

    # Duplicate check
    if ENFORCE_DUPLICATE_CHECK:
        existing = get_payable_by_vendor_and_invoice(vendor, invoice_no)
        if existing:
            return None, f"Duplicate invoice rejected: Invoice '{invoice_no}' from vendor '{vendor}' is already registered (Payable #{existing['id']})."

    now_iso = datetime.now(timezone.utc).isoformat()
    conn = get_connection()
    try:
        with conn:
            cursor = conn.execute("""
                INSERT INTO payables (vendor, invoice_no, amount, currency, due_date, notes, status, source, created_at)
                VALUES (?, ?, ?, ?, ?, ?, 'RECORDED', 'AUTOMATED_AGENT', ?)
            """, (vendor, invoice_no, amount, currency, due_date, notes, now_iso))
            payable_id = cursor.lastrowid
        return payable_id, None
    except sqlite3.IntegrityError:
        return None, f"Database integrity error: Invoice '{invoice_no}' from vendor '{vendor}' already exists in records."
    except Exception as e:
        return None, f"Database error: {str(e)}"
    finally:
        conn.close()

def clear_payables() -> None:
    init_db()
    conn = get_connection()
    with conn:
        conn.execute("DELETE FROM payables")
    conn.close()
