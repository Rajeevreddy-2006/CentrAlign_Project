import re
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

class TaskPlanner:
    """
    Decomposes natural language instructions into high-level sub-goals,
    resolves target entities, compares invoice dates, and formulates recovery strategies.
    """
    @staticmethod
    def extract_vendor_query(task_text: str) -> Optional[str]:
        """
        Extracts candidate vendor/company name from task text.
        e.g. "Find the latest invoice from Acme Cloud Corp..." -> "Acme Cloud Corp"
        """
        patterns = [
            r'(?:from|for|vendor|company)\s+["\']?([A-Za-z0-9\s&]+?)(?:["\']|\s*,\s*|\s+and\b|\s+extract|\s+in\b|$)',
            r'latest invoice (?:of|from)\s+([A-Za-z0-9\s&]+)',
        ]
        for p in patterns:
            match = re.search(p, task_text, re.IGNORECASE)
            if match:
                candidate = match.group(1).strip()
                # Exclude common stopwords
                if candidate.lower() not in ("company x", "the company", "our", "a vendor", "company"):
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
    def select_latest_invoice(invoices: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Sorts invoices strictly by issue date to identify the chronologically latest invoice.
        Never assumes the first row in a table is the latest.
        """
        if not invoices:
            return None

        def parse_date(inv: Dict[str, Any]) -> datetime:
            date_str = inv.get("issue_date", "")
            try:
                return datetime.strptime(date_str, "%Y-%m-%d")
            except (ValueError, TypeError):
                return datetime.min

        sorted_invoices = sorted(invoices, key=parse_date, reverse=True)
        return sorted_invoices[0]
