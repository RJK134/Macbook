"""HTTP helpers — polite, retry-friendly client with sensible UA."""

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

DEFAULT_UA = (
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:122.0) "
    "Gecko/20100101 Firefox/122.0 (WorkhorseScanner/0.1)"
)

DEFAULT_HEADERS = {
    "User-Agent": DEFAULT_UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.9",
}


def client(timeout: float = 30.0) -> httpx.Client:
    return httpx.Client(
        headers=DEFAULT_HEADERS,
        timeout=timeout,
        follow_redirects=True,
        http2=True,
    )


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=20),
    retry=retry_if_exception_type((httpx.HTTPError, httpx.RemoteProtocolError)),
    reraise=True,
)
def get(url: str, *, timeout: float = 30.0, params: dict | None = None) -> httpx.Response:
    with client(timeout=timeout) as c:
        r = c.get(url, params=params)
        r.raise_for_status()
        return r
