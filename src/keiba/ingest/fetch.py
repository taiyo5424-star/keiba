"""polite なHTTPフェッチャ(標準ライブラリのみ)。

- ホストごとに最終アクセス時刻を覚え、min_interval 秒未満の連続アクセスを
  自動的に待機する(robots の Crawl-Delay 対応)
- User-Agent を明示
- CA バンドルは環境変数(REQUESTS_CA_BUNDLE / CURL_CA_BUNDLE)を尊重
"""

from __future__ import annotations

import os
import ssl
import time
import urllib.request
from urllib.parse import urlparse

USER_AGENT = "keiba-research/0.1 (personal analysis; polite fetcher)"

_last_access: dict[str, float] = {}


def _ssl_context() -> ssl.SSLContext:
    cafile = os.environ.get("REQUESTS_CA_BUNDLE") or os.environ.get("CURL_CA_BUNDLE")
    return ssl.create_default_context(cafile=cafile)


def polite_get(url: str, min_interval: float = 2.0, timeout: float = 30.0) -> bytes:
    """min_interval 秒のホスト別間隔を守って GET し、生バイト列を返す。"""
    host = urlparse(url).netloc
    now = time.monotonic()
    last = _last_access.get(host)
    if last is not None:
        wait = min_interval - (now - last)
        if wait > 0:
            time.sleep(wait)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout, context=_ssl_context()) as resp:
        body = resp.read()
    _last_access[host] = time.monotonic()
    return body
