import re
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

class TaskPlanner:
    """
    Decomposes natural language instructions into high-level sub-goals,
    resolves target entities, compares invoice dates, and formulates recovery strategies.
    """
    @staticmethod
    def classify_task_intent(task_text: str) -> Dict[str, Any]:
        """
        Decomposes natural language task into structured execution parameters:
        - intent: 'ENTER_INVOICES', 'REPORT_OVERDUE', 'REPORT_HIGHEST_UNPAID', 'REPORT_GENERAL'
        - vendor_query: candidate vendor name or None
        - count: number of invoices to target (default 1 for 'latest', or N for '2 most recent')
        - requires_entry: boolean whether the task modifies the finance system
        - filter_type: 'latest', 'overdue', 'all'
        """
        text = task_text.strip()
        text_lower = text.lower()

        # 1. Check for Highest Unpaid / Highest Balance Query
        if ("highest unpaid" in text_lower or "highest open" in text_lower or "highest balance" in text_lower or "most unpaid" in text_lower):
            return {
                "intent": "REPORT_HIGHEST_UNPAID",
                "vendor_query": None,
                "count": 0,
                "requires_entry": False,
                "filter_type": "highest_unpaid"
            }

        # 2. Check for Overdue aggregation/report
        if "overdue" in text_lower and ("total" in text_lower or "list" in text_lower or "report" in text_lower or "sum" in text_lower):
            vendor = TaskPlanner.extract_vendor_query(text)
            return {
                "intent": "REPORT_OVERDUE",
                "vendor_query": vendor,
                "count": 0,
                "requires_entry": False,
                "filter_type": "overdue"
            }

        # 3. Check for Multi-Invoice or Top N Entry
        # e.g., "Enter the 2 most recent invoices from Acme..."
        count = 1
        count_match = re.search(r'\b(?:enter|input|record|add)\s+(?:the\s+)?(\d+|two|three|four)\s+(?:most\s+recent|latest)\b', text, re.IGNORECASE)
        if count_match:
            c_str = count_match.group(1).lower()
            word_map = {"two": 2, "three": 3, "four": 4}
            count = word_map.get(c_str, int(c_str) if c_str.isdigit() else 2)

        # 4. Check if task explicitly forbids entry ("enter nothing", "just report", "do not enter")
        requires_entry = True
        if "enter nothing" in text_lower or "just report" in text_lower or "do not enter" in text_lower or "only report" in text_lower:
            requires_entry = False

        vendor = TaskPlanner.extract_vendor_query(text)

        intent = "ENTER_INVOICES" if requires_entry else "REPORT_GENERAL"
        return {
            "intent": intent,
            "vendor_query": vendor,
            "count": count,
            "requires_entry": requires_entry,
            "filter_type": "latest"
        }

    @staticmethod
    def extract_vendor_query(task_text: str) -> Optional[str]:
        """
        Extracts candidate vendor/company name from task text.
        e.g. "Find the latest invoice from Acme Cloud Corp..." -> "Acme Cloud Corp"
        """
        patterns = [
            r'(?:from|for|vendor|company)\s+["\']?([A-Za-z0-9\s&]+?)(?:["\']|\s*,\s*|\s+and\b|\s+extract|\s+in\b|\s+that\b|\s+into\b|$)',
            r'latest invoice (?:of|from)\s+([A-Za-z0-9\s&]+)',
        ]
        for p in patterns:
            match = re.search(p, task_text, re.IGNORECASE)
            if match:
                candidate = match.group(1).strip()
                # Exclude common stopwords
                if candidate.lower() not in (
                    "company x", "the company", "our", "a vendor", "vendor",
                    "company", "the finance system", "a supplier", "supplier", "the supplier"
                ):
                    return candidate

        return None

    @staticmethod
    def match_vendor(query: str, vendors: List[Dict[str, Any]]) -> Tuple[Optional[Dict[str, Any]], List[str]]:
        """
        Matches a query string against available vendors in the directory.
        Returns (matched_vendor, list_of_candidate_names_if_ambiguous).
        """
        query_norm = query.lower().strip()
        exact_matches = []
        partial_matches = []

        for v in vendors:
            v_name = v.get("name", "").lower()
            v_slug = v.get("slug", "").lower()
            if query_norm == v_name or query_norm == v_slug:
                exact_matches.append(v)
            elif query_norm in v_name or v_slug in query_norm:
                partial_matches.append(v)

        if len(exact_matches) == 1:
            return exact_matches[0], []
        if len(exact_matches) > 1:
            return None, [v["name"] for v in exact_matches]

        if len(partial_matches) == 1:
            return partial_matches[0], []
        if len(partial_matches) > 1:
            return None, [v["name"] for v in partial_matches]

        return None, []

    @staticmethod
    def sort_invoices_by_date(invoices: List[Dict[str, Any]], reverse: bool = True) -> List[Dict[str, Any]]:
        """
        Sorts invoices strictly by issue date.
        """
        def parse_date(inv: Dict[str, Any]) -> datetime:
            date_str = inv.get("issue_date", "")
            try:
                return datetime.strptime(date_str, "%Y-%m-%d")
            except (ValueError, TypeError):
                return datetime.min

        return sorted(invoices, key=parse_date, reverse=reverse)

    @staticmethod
    def select_latest_invoice(invoices: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Sorts invoices strictly by issue date to identify the chronologically latest invoice.
        Never assumes the first row in a table is the latest.
        """
        sorted_invoices = TaskPlanner.sort_invoices_by_date(invoices, reverse=True)
        return sorted_invoices[0] if sorted_invoices else None

    @staticmethod
    def filter_overdue_invoices(invoices: List[Dict[str, Any]], reference_date: str = "2026-10-11") -> List[Dict[str, Any]]:
        """
        Filters invoices that have status 'Overdue' or due date strictly prior to reference date
        and not marked 'Paid'.
        """
        ref_dt = datetime.strptime(reference_date, "%Y-%m-%d")
        overdue = []
        for inv in invoices:
            status = str(inv.get("status", "")).strip().lower()
            due_str = inv.get("due_date", "")
            try:
                due_dt = datetime.strptime(due_str, "%Y-%m-%d")
            except (ValueError, TypeError):
                due_dt = datetime.max

            if status == "overdue":
                overdue.append(inv)
            elif status != "paid" and due_dt < ref_dt:
                overdue.append(inv)

        return overdue
