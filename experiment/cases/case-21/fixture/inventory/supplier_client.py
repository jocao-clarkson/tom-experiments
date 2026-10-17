import logging
import os
import time

import requests

log = logging.getLogger(__name__)

RETRYABLE_STATUS = {502, 503, 504}


class SupplierError(Exception):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


class SupplierClient:
    """Thin client for the supplier REST API.

    All outbound calls to the supplier go through this class so that auth,
    timeouts and backoff are applied consistently.
    """

    def __init__(self, base_url: str, api_key: str, session=None,
                 timeout: float = 5.0, retries: int = 3, backoff: float = 0.5):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.session = session or requests.Session()
        self.timeout = timeout
        self.retries = retries
        self.backoff = backoff

    @classmethod
    def from_env(cls) -> "SupplierClient":
        return cls(os.environ["SUPPLIER_URL"], os.environ["SUPPLIER_API_KEY"])

    def request(self, method: str, path: str, json=None, retries: int | None = None) -> dict:
        attempts = (self.retries if retries is None else retries) + 1
        url = f"{self.base_url}{path}"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        last_exc: Exception | None = None
        for attempt in range(attempts):
            try:
                resp = self.session.request(method, url, json=json, headers=headers,
                                            timeout=self.timeout)
            except (requests.ConnectionError, requests.Timeout) as exc:
                last_exc = exc
                log.warning("supplier %s %s failed (attempt %d): %s", method, path, attempt + 1, exc)
            else:
                if resp.status_code not in RETRYABLE_STATUS:
                    if resp.status_code >= 400:
                        raise SupplierError(f"supplier returned {resp.status_code}", resp.status_code)
                    return resp.json()
                last_exc = SupplierError(f"supplier returned {resp.status_code}", resp.status_code)
            if attempt + 1 < attempts:
                time.sleep(self.backoff * (2 ** attempt))
        raise SupplierError(f"supplier unavailable: {last_exc}")

    def get(self, path: str) -> dict:
        return self.request("GET", path)

    def post(self, path: str, json: dict, retries: int | None = None) -> dict:
        return self.request("POST", path, json=json, retries=retries)
