import time

import requests

from .logging_utils import get_logger

log = get_logger(__name__)

RETRYABLE_STATUS = {500, 502, 503, 504}


class ResilientClient:
    """Shared client for calls to internal and partner HTTP services."""

    def __init__(self, base_url, api_key, *, timeout=5.0, max_retries=0,
                 backoff_base=0.25, session=None):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self.session = session or requests.Session()

    def request(self, method, path, *, json=None, params=None):
        url = f"{self.base_url}/{path.lstrip('/')}"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        attempt = 0
        while True:
            try:
                resp = self.session.request(
                    method, url, json=json, params=params,
                    headers=headers, timeout=self.timeout,
                )
                if resp.status_code not in RETRYABLE_STATUS:
                    return resp
                log.warning("retryable status", extra={"status": resp.status_code, "url": url})
            except (requests.ConnectionError, requests.Timeout) as exc:
                log.warning("transport error", extra={"error": str(exc), "url": url})
                if attempt >= self.max_retries:
                    raise
            else:
                if attempt >= self.max_retries:
                    return resp
            time.sleep(self.backoff_base * (2 ** attempt))
            attempt += 1

    def get(self, path, **kw):
        return self.request("GET", path, **kw)

    def post(self, path, **kw):
        return self.request("POST", path, **kw)
