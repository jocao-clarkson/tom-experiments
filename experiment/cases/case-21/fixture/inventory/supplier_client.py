import logging
import os

import requests

from .transport import build_session

log = logging.getLogger(__name__)


class SupplierError(Exception):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


class SupplierClient:
    """Thin client for the supplier REST API.

    All outbound calls to the supplier go through this class so that auth,
    timeouts and error handling are applied consistently.
    """

    def __init__(self, base_url: str, api_key: str, session=None, timeout: float = 5.0):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.session = session or build_session()
        self.timeout = timeout

    @classmethod
    def from_env(cls) -> "SupplierClient":
        return cls(os.environ["SUPPLIER_URL"], os.environ["SUPPLIER_API_KEY"])

    def request(self, method: str, path: str, json=None) -> dict:
        url = f"{self.base_url}{path}"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        try:
            resp = self.session.request(method, url, json=json, headers=headers,
                                        timeout=self.timeout)
        except (requests.ConnectionError, requests.Timeout) as exc:
            log.warning("supplier %s %s failed: %s", method, path, exc)
            raise SupplierError(f"supplier unavailable: {exc}") from exc
        if resp.status_code >= 400:
            log.warning("supplier %s %s returned %d", method, path, resp.status_code)
            raise SupplierError(f"supplier returned {resp.status_code}", resp.status_code)
        log.info("supplier %s %s -> %d", method, path, resp.status_code)
        return resp.json()

    def get(self, path: str) -> dict:
        return self.request("GET", path)

    def post(self, path: str, json: dict) -> dict:
        return self.request("POST", path, json=json)
