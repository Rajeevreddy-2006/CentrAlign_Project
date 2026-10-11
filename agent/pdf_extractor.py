import io
import re
from typing import Dict, Any, Optional
from pypdf import PdfReader

class PDFInvoiceExtractor:
    """
    Parses authentic PDF invoices and extracts ground-truth facts:
    invoice number, due date, issue date, and amount.
    """
    @staticmethod
    def extract_from_bytes(pdf_bytes: bytes) -> Dict[str, Any]:
        """Reads PDF binary data and extracts invoice fields."""
        reader = PdfReader(io.BytesIO(pdf_bytes))
        full_text = ""
        for page in reader.pages:
            full_text += (page.extract_text() or "") + "\n"

        return PDFInvoiceExtractor.extract_from_text(full_text)

    @staticmethod
    def extract_from_text(text: str) -> Dict[str, Any]:
        """Extracts structured values from text using regex heuristics."""
        data = {
            "invoice_no": None,
            "due_date": None,
            "issue_date": None,
            "amount": None,
            "currency": "USD",
            "raw_text": text
        }

        # 1. Invoice Number (e.g. INV-ACME-1004, INV-GL-505)
        inv_match = re.search(r'Invoice\s*#?:\s*(INV-[A-Z0-9-]+)', text, re.IGNORECASE)
        if not inv_match:
            inv_match = re.search(r'\b(INV-[A-Z0-9-]+)\b', text)
        if inv_match:
            data["invoice_no"] = inv_match.group(1).strip()

        # 2. Due Date (e.g. 2026-10-30)
        due_match = re.search(r'Due\s*Date:\s*([0-9]{4}-[0-9]{2}-[0-9]{2})', text, re.IGNORECASE)
        if due_match:
            data["due_date"] = due_match.group(1).strip()

        # 3. Issue Date (e.g. 2026-09-30)
        issue_match = re.search(r'Issue\s*Date:\s*([0-9]{4}-[0-9]{2}-[0-9]{2})', text, re.IGNORECASE)
        if issue_match:
            data["issue_date"] = issue_match.group(1).strip()

        # 4. Total Amount (e.g. Total Due: USD 2,490.75 or 2,490.75)
        amount_match = re.search(r'(?:Total\s*Due|Total\s*Amount):\s*(?:USD|\$)?\s*([0-9,]+\.[0-9]{2})', text, re.IGNORECASE)
        if not amount_match:
            amount_match = re.search(r'(?:USD|\$)\s*([0-9,]+\.[0-9]{2})', text)
        if amount_match:
            clean_str = amount_match.group(1).replace(",", "").strip()
            try:
                data["amount"] = float(clean_str)
            except ValueError:
                data["amount"] = None

        return data
