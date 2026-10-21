import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from . import config

USER_AGENT = "inventory-service/1.8"


def build_session(retries: int | None = None) -> requests.Session:
    """Session used for outbound HTTP, with connection pooling and backoff."""
    retry = Retry(
        total=config.HTTP_RETRY_TOTAL if retries is None else retries,
        backoff_factor=config.HTTP_RETRY_BACKOFF,
        status_forcelist=config.HTTP_RETRY_STATUSES,
        allowed_methods=config.HTTP_RETRY_METHODS,
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_maxsize=config.HTTP_POOL_SIZE)
    session = requests.Session()
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers["User-Agent"] = USER_AGENT
    return session
