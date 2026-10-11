from typing import Dict, Any, Optional, List
from agent.browser_client import BrowserClient
from agent.config import FINANCE_SYSTEM_BASE
from agent.models import VerificationReport, VerificationStatus, VerificationEvidence

class IndependentVerifier:
    """
    Independent Verification Layer.
    Does NOT trust the agent's internal monologue or claims.
    Spawns an isolated session, connects to the destination system,
    and inspects ground-truth records against the source invoice facts.
    """
    def __init__(self, finance_base_url: str = FINANCE_SYSTEM_BASE):
        self.finance_base = finance_base_url
        self.client = BrowserClient()

    def verify_payable_entry(
        self,
        expected_vendor: str,
        expected_invoice_no: str,
        expected_amount: float,
        expected_due_date: str
    ) -> VerificationReport:
        """
        Independently navigates the Finance System to verify the recorded payable.
        Returns PASS, FAIL, or UNCERTAIN.
        """
        # 1. Authenticate to Finance System
        login_res = self.client.login("finance", self.finance_base)
        if not login_res.success:
            return VerificationReport(
                status=VerificationStatus.UNCERTAIN,
                message=f"Independent verifier failed to authenticate to Finance ERP: {login_res.error}"
            )

        # 2. Navigate to Payables Ledger
        ledger_url = f"{self.finance_base}/payables"
        nav_res = self.client.navigate(ledger_url)
        if not nav_res.success:
            return VerificationReport(
                status=VerificationStatus.UNCERTAIN,
                message=f"Independent verifier could not load /payables: {nav_res.error}"
            )

        soup = self.client.last_soup
        if not soup:
            return VerificationReport(
                status=VerificationStatus.UNCERTAIN,
                message="Independent verifier received empty DOM."
            )

        # 3. Locate the payable record in table
        rows = soup.select("tr.payable-row")
        matching_row = None
        for row in rows:
            inv_no_elem = row.select_one(".payable-invoice-no")
            vendor_elem = row.select_one(".payable-vendor")
            if inv_no_elem and vendor_elem:
                row_inv = inv_no_elem.get_text(strip=True)
                row_vendor = vendor_elem.get_text(strip=True)
                if (row_inv.lower() == expected_invoice_no.lower()) and (expected_vendor.lower() in row_vendor.lower() or row_vendor.lower() in expected_vendor.lower()):
                    matching_row = row
                    break

        evidence = VerificationEvidence(
            source_vendor=expected_vendor,
            source_invoice_no=expected_invoice_no,
            source_amount=expected_amount,
            source_due_date=expected_due_date
        )

        if not matching_row:
            evidence.discrepancies.append(
                f"Payable for '{expected_vendor}' invoice '{expected_invoice_no}' was NOT found in the ledger."
            )
            return VerificationReport(
                status=VerificationStatus.FAIL,
                message=f"Verification FAIL: Invoice '{expected_invoice_no}' from '{expected_vendor}' is missing in the destination ERP.",
                evidence=evidence,
                verifier_dom_snapshot=self.client.get_page_text_summary(max_chars=1000)
            )

        # 4. Extract fields from matching row
        payable_id_str = matching_row.get("data-payable-id", "0")
        try:
            evidence.destination_payable_id = int(payable_id_str)
        except ValueError:
            evidence.destination_payable_id = None

        dest_vendor_elem = matching_row.select_one(".payable-vendor")
        dest_inv_elem = matching_row.select_one(".payable-invoice-no")
        dest_amount_elem = matching_row.select_one(".payable-amount")
        dest_due_elem = matching_row.select_one(".payable-due-date")

        evidence.destination_vendor = dest_vendor_elem.get_text(strip=True) if dest_vendor_elem else ""
        evidence.destination_invoice_no = dest_inv_elem.get_text(strip=True) if dest_inv_elem else ""
        evidence.destination_due_date = dest_due_elem.get_text(strip=True) if dest_due_elem else ""

        amount_raw = dest_amount_elem.get_text(strip=True).replace(",", "").replace("$", "") if dest_amount_elem else "0"
        try:
            evidence.destination_amount = float(amount_raw)
        except ValueError:
            evidence.destination_amount = 0.0

        # 5. Check discrepancy details
        discrepancies = []
        if evidence.source_invoice_no.lower() != evidence.destination_invoice_no.lower():
            discrepancies.append(
                f"Invoice Number mismatch: expected '{evidence.source_invoice_no}', found '{evidence.destination_invoice_no}'"
            )

        if abs(evidence.source_amount - evidence.destination_amount) > 0.01:
            discrepancies.append(
                f"Amount mismatch: expected {evidence.source_amount:.2f}, found {evidence.destination_amount:.2f}"
            )

        if evidence.source_due_date.strip() != evidence.destination_due_date.strip():
            discrepancies.append(
                f"Due Date mismatch: expected '{evidence.source_due_date}', found '{evidence.destination_due_date}'"
            )

        evidence.discrepancies = discrepancies

        if discrepancies:
            return VerificationReport(
                status=VerificationStatus.FAIL,
                message=f"Verification FAIL: Mismatches in payable record #{evidence.destination_payable_id}: {'; '.join(discrepancies)}",
                evidence=evidence,
                verifier_dom_snapshot=self.client.get_page_text_summary(max_chars=1000)
            )

        return VerificationReport(
            status=VerificationStatus.PASS,
            message=(
                f"Verification PASS: Ground-truth record #{evidence.destination_payable_id} confirmed in Finance ERP. "
                f"Vendor: {evidence.destination_vendor}, Invoice: {evidence.destination_invoice_no}, "
                f"Amount: ${evidence.destination_amount:,.2f}, Due Date: {evidence.destination_due_date}."
            ),
            evidence=evidence,
            verifier_dom_snapshot=self.client.get_page_text_summary(max_chars=1000)
        )
