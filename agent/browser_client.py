import hashlib
from typing import Dict, Any, Optional, List, Tuple
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import requests

from agent.safety import validate_url, get_authorized_credentials, wrap_untrusted_content
from agent.models import ActionResult, ActionType

class BrowserClient:
    """
    Lightweight, fast, and rock-solid web execution client.
    Maintains cookie sessions, parses DOM structures (tables and card grids),
    computes state hashes, and detects login redirects and error banners.
    """
    def __init__(self, timeout: float = 10.0):
        self.session = requests.Session()
        self.timeout = timeout
        self.current_url: Optional[str] = None
        self.last_status_code: Optional[int] = None
        self.last_html: Optional[str] = None
        self.last_soup: Optional[BeautifulSoup] = None

    def _compute_state_hash(self, html: str) -> str:
        """Computes SHA-256 hash of normalized body text to detect stagnant progress."""
        if not html:
            return ""
        soup = BeautifulSoup(html, "html.parser")
        body = soup.find("body")
        text = body.get_text(separator=" ", strip=True) if body else html
        return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]

    def _detect_error_banner(self, soup: Optional[BeautifulSoup]) -> Optional[str]:
        """Detects visible error banners or alerts in the rendered DOM."""
        if not soup:
            return None
        # Check standard alert classes
        for selector in [".alert-danger", "#form-error", "#login-error", ".alert", ".error"]:
            elem = soup.select_one(selector)
            if elem and elem.get_text(strip=True):
                return elem.get_text(strip=True)
        return None

    def _is_login_page(self, url: str, soup: Optional[BeautifulSoup]) -> bool:
        """Determines if the current page is a login page (e.g. following session expiry)."""
        if "/login" in url.lower():
            return True
        if soup and soup.find("input", {"type": "password"}):
            return True
        return False

    def navigate(self, url: str) -> ActionResult:
        """Navigates to an allowlisted URL and returns parsed DOM state."""
        try:
            safe_url = validate_url(url)
            resp = self.session.get(safe_url, timeout=self.timeout)
            self.current_url = str(resp.url)
            self.last_status_code = resp.status_code
            self.last_html = resp.text
            self.last_soup = BeautifulSoup(resp.text, "html.parser")

            state_hash = self._compute_state_hash(resp.text)
            error_banner = self._detect_error_banner(self.last_soup)
            is_login = self._is_login_page(self.current_url, self.last_soup)

            is_transient = resp.status_code in (500, 502, 503, 504)

            parsed_data = {
                "url": self.current_url,
                "status_code": resp.status_code,
                "title": self.last_soup.title.string.strip() if self.last_soup.title else "",
                "is_login_page": is_login,
                "error_banner": error_banner,
                "state_hash": state_hash,
                "text_summary": self.get_page_text_summary()
            }

            success = resp.status_code < 400 and not error_banner

            return ActionResult(
                action_type=ActionType.NAVIGATE,
                success=success,
                data=parsed_data,
                error=error_banner if not success else None,
                is_transient=is_transient,
                status_code=resp.status_code,
                state_hash=state_hash,
                current_url=self.current_url,
                error_banner=error_banner
            )
        except requests.exceptions.Timeout as e:
            return ActionResult(
                action_type=ActionType.NAVIGATE,
                success=False,
                error=f"Navigation timeout after {self.timeout}s: {str(e)}",
                is_transient=True,
                current_url=url
            )
        except requests.exceptions.RequestException as e:
            return ActionResult(
                action_type=ActionType.NAVIGATE,
                success=False,
                error=f"Navigation request failed: {str(e)}",
                is_transient=True,
                current_url=url
            )
        except Exception as e:
            return ActionResult(
                action_type=ActionType.NAVIGATE,
                success=False,
                error=str(e),
                is_transient=False,
                current_url=url
            )

    def login(self, service: str, base_url: str) -> ActionResult:
        """
        Executes authentication using authorized environment credentials.
        """
        try:
            username, password = get_authorized_credentials(service)
            login_url = urljoin(base_url, "/login")
            safe_login_url = validate_url(login_url)

            payload = {
                "username": username,
                "password": password
            }
            resp = self.session.post(safe_login_url, data=payload, timeout=self.timeout)
            self.current_url = str(resp.url)
            self.last_status_code = resp.status_code
            self.last_html = resp.text
            self.last_soup = BeautifulSoup(resp.text, "html.parser")

            state_hash = self._compute_state_hash(resp.text)
            error_banner = self._detect_error_banner(self.last_soup)
            is_login = self._is_login_page(self.current_url, self.last_soup)

            success = resp.status_code < 400 and not is_login and not error_banner

            return ActionResult(
                action_type=ActionType.LOGIN,
                success=success,
                data={
                    "url": self.current_url,
                    "authenticated_user": username,
                    "service": service
                },
                error=error_banner if not success else None,
                status_code=resp.status_code,
                state_hash=state_hash,
                current_url=self.current_url,
                error_banner=error_banner
            )
        except Exception as e:
            return ActionResult(
                action_type=ActionType.LOGIN,
                success=False,
                error=f"Login failed: {str(e)}",
                is_transient=True,
                current_url=base_url
            )

    def submit_form(self, url: str, form_data: Dict[str, Any]) -> ActionResult:
        """
        Submits form data via HTTP POST to an allowlisted endpoint.
        Detects transient 500 errors, duplicate rejections (409), and field errors.
        """
        try:
            safe_url = validate_url(url)
            resp = self.session.post(safe_url, data=form_data, timeout=self.timeout)
            self.current_url = str(resp.url)
            self.last_status_code = resp.status_code
            self.last_html = resp.text
            self.last_soup = BeautifulSoup(resp.text, "html.parser")

            state_hash = self._compute_state_hash(resp.text)
            error_banner = self._detect_error_banner(self.last_soup)

            is_transient = resp.status_code in (500, 502, 503, 504)
            is_duplicate = resp.status_code == 409 or (error_banner and "duplicate" in error_banner.lower())
            is_login = self._is_login_page(self.current_url, self.last_soup)

            success = resp.status_code in (200, 201, 302, 303) and not error_banner and not is_login

            error_msg = None
            if not success:
                if is_login:
                    error_msg = "Session expired during submission. Re-authentication required."
                elif error_banner:
                    error_msg = error_banner
                elif is_transient:
                    error_msg = f"HTTP {resp.status_code} Transient Server Error on submit: {resp.text[:200]}"
                else:
                    error_msg = f"Form submission rejected with HTTP {resp.status_code}"

            return ActionResult(
                action_type=ActionType.SUBMIT_FORM,
                success=success,
                data={
                    "submitted_url": safe_url,
                    "resulting_url": self.current_url,
                    "status_code": resp.status_code,
                    "is_duplicate": is_duplicate,
                    "is_session_expired": is_login,
                    "text_summary": self.get_page_text_summary()
                },
                error=error_msg,
                is_transient=is_transient,
                status_code=resp.status_code,
                state_hash=state_hash,
                current_url=self.current_url,
                error_banner=error_banner
            )
        except requests.exceptions.Timeout as e:
            return ActionResult(
                action_type=ActionType.SUBMIT_FORM,
                success=False,
                error=f"Timeout submitting form: {str(e)}",
                is_transient=True,
                current_url=url
            )
        except requests.exceptions.RequestException as e:
            return ActionResult(
                action_type=ActionType.SUBMIT_FORM,
                success=False,
                error=f"Request failure submitting form: {str(e)}",
                is_transient=True,
                current_url=url
            )
        except Exception as e:
            return ActionResult(
                action_type=ActionType.SUBMIT_FORM,
                success=False,
                error=str(e),
                is_transient=False,
                current_url=url
            )

    def download_file(self, url: str) -> Tuple[Optional[bytes], Optional[str]]:
        """
        Downloads a file (e.g. invoice PDF) and returns (bytes, error).
        """
        try:
            safe_url = validate_url(url)
            resp = self.session.get(safe_url, timeout=self.timeout)
            if resp.status_code == 200:
                return resp.content, None
            return None, f"Download failed with status {resp.status_code}"
        except Exception as e:
            return None, f"Download error: {str(e)}"

    def get_page_text_summary(self, max_chars: int = 4000) -> str:
        """Returns sanitized, untrusted text extracted from the current page."""
        if not self.last_soup:
            return ""
        # Strip script and style elements
        for s in self.last_soup(["script", "style", "nav", "footer"]):
            s.decompose()
        text = self.last_soup.get_text(separator="\n", strip=True)
        return text[:max_chars]

    def extract_invoices_from_page(self) -> List[Dict[str, Any]]:
        """
        Extracts invoice records from both standard table and card layouts.
        Demonstrates DOM layout generalization.
        """
        if not self.last_soup:
            return []

        invoices = []

        # 1. Try standard table layout (Acme, Global Logistics, etc.)
        table = self.last_soup.find("table", {"id": "invoices-table"}) or self.last_soup.find("table")
        if table:
            rows = table.find_all("tr")[1:]  # Skip header
            for row in rows:
                cols = [td.get_text(strip=True) for td in row.find_all("td")]
                if len(cols) >= 5:
                    inv_no = cols[0]
                    issue_date = cols[1]
                    due_date = cols[2]
                    amount_str = cols[3].replace(",", "").replace("$", "").replace("USD", "").strip()
                    currency = cols[4] if len(cols) > 4 else "USD"

                    # Find download link
                    pdf_link = None
                    a_tag = row.find("a", href=True)
                    if a_tag:
                        pdf_link = urljoin(self.current_url or "", a_tag["href"])

                    try:
                        amount = float(amount_str)
                    except ValueError:
                        amount = 0.0

                    # Status badge
                    status_elem = row.find("span", class_="badge")
                    inv_status = status_elem.get_text(strip=True) if status_elem else (cols[5] if len(cols) > 5 else "Open")

                    invoices.append({
                        "invoice_no": inv_no,
                        "issue_date": issue_date,
                        "due_date": due_date,
                        "amount": amount,
                        "currency": currency,
                        "status": inv_status,
                        "pdf_url": pdf_link,
                        "source_layout": "table"
                    })

        # 2. Try card grid layout (Vertex Analytics)
        cards = self.last_soup.select(".invoice-card")
        if cards:
            for card in cards:
                num_elem = card.select_one(".invoice-card-number")
                inv_no = num_elem.get_text(strip=True) if num_elem else "UNKNOWN"

                issue_elem = card.select_one(".issue-date")
                issue_date = issue_elem.get_text(strip=True) if issue_elem else ""

                due_elem = card.select_one(".due-date")
                due_date = due_elem.get_text(strip=True) if due_elem else ""

                status_elem = card.select_one(".badge")
                inv_status = status_elem.get_text(strip=True) if status_elem else "Open"

                amount_elem = card.select_one(".amount")
                amount_str = amount_elem.get_text(strip=True) if amount_elem else "0"
                amount_clean = amount_str.replace("USD", "").replace("$", "").replace(",", "").strip()

                pdf_link = None
                a_tag = card.find("a", href=True)
                if a_tag:
                    pdf_link = urljoin(self.current_url or "", a_tag["href"])

                try:
                    amount = float(amount_clean)
                except ValueError:
                    amount = 0.0

                invoices.append({
                    "invoice_no": inv_no,
                    "issue_date": issue_date,
                    "due_date": due_date,
                    "amount": amount,
                    "currency": "USD",
                    "status": inv_status,
                    "pdf_url": pdf_link,
                    "source_layout": "cards"
                })

        return invoices
