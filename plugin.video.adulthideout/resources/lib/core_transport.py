# -*- coding: utf-8 -*-
"""Routes page fetches of requests/cloudscraper sessions through the Rust Core.

Every plain GET for a page goes to the Core first (browser-like headers, shared Cloudflare
sessions). Anything the Core cannot serve falls back to the original requests path, so a
site never gets worse than before. POST, streams, media and local calls are untouched.
"""

import contextlib
import datetime
import threading
import urllib.parse

CORE_ENDPOINT = "http://127.0.0.1:8191/v1"
_MEDIA_SUFFIXES = (
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".avif", ".svg", ".ico",
    ".mp4", ".m4v", ".webm", ".mkv", ".ts", ".m3u8", ".mpd", ".mp3", ".m4a", ".zip",
)
_TEXT_TYPES = ("text/", "json", "xml", "javascript")
# Core answers that another client may still pass: challenges and server errors.
_FALLBACK_STATUSES = {403, 429, 503}
_LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1", ""}
# The Core sets these itself. Forwarding requests' "Accept-Encoding: gzip" makes sites send
# compressed bodies the Core cannot unpack, which arrive here as empty pages.
_CORE_OWNED_HEADERS = {"cookie", "user-agent", "accept-encoding", "connection", "host", "content-length"}
_STATS = {"core": 0, "fallback": 0}
_STATS_LOCK = threading.Lock()
_INSTALLED = False
_LOCAL = threading.local()


@contextlib.contextmanager
def bypass():
    """For callers that already asked the Core and now want the plain Python path."""
    previous = getattr(_LOCAL, "bypass", False)
    _LOCAL.bypass = True
    try:
        yield
    finally:
        _LOCAL.bypass = previous


def stats():
    with _STATS_LOCK:
        return dict(_STATS)


def _count(key):
    with _STATS_LOCK:
        _STATS[key] += 1


def _eligible(request, kwargs):
    if getattr(_LOCAL, "bypass", False) or request.method != "GET" or kwargs.get("stream"):
        return False
    parts = urllib.parse.urlsplit(request.url)
    if parts.scheme not in ("http", "https") or parts.hostname in _LOCAL_HOSTS:
        return False
    return not parts.path.lower().endswith(_MEDIA_SUFFIXES)


def _timeout_ms(timeout):
    if isinstance(timeout, (tuple, list)):
        timeout = sum(t for t in timeout if t)
    try:
        seconds = float(timeout) if timeout else 15.0
    except (TypeError, ValueError):
        seconds = 15.0
    return int(min(max(seconds, 3.0), 30.0) * 1000)


def _core_cookies(request):
    header = request.headers.get("Cookie") or ""
    host = urllib.parse.urlsplit(request.url).hostname or ""
    cookies = []
    for pair in header.split(";"):
        name, sep, value = pair.strip().partition("=")
        if sep and name:
            cookies.append({"name": name, "value": value, "domain": host})
    return cookies


def _build_response(request, solution):
    import requests
    from requests.structures import CaseInsensitiveDict

    response = requests.Response()
    response.status_code = int(solution.get("status") or 0)
    response.headers = CaseInsensitiveDict(solution.get("headers") or {})
    response.headers.pop("content-encoding", None)  # the Core already decoded the body
    response._content = (solution.get("response") or "").encode("utf-8")
    response.encoding = "utf-8"
    response.url = solution.get("url") or request.url
    response.request = request
    response.reason = "OK" if response.status_code == 200 else ""
    response.elapsed = datetime.timedelta(0)
    response._content_consumed = True
    return response


def english_unless_set(headers):
    """The Core's browser profile asks for German pages. Modules parse English pages (zbporn served
    de.zbporn.com links its pattern misses), so ask for English unless the module chose a language."""
    if not any(k.lower() == "accept-language" for k in headers):
        headers["Accept-Language"] = "en-US,en;q=0.9"
    return headers


def _send_via_core(session, request, kwargs):
    import requests

    headers = english_unless_set({k: str(v) for k, v in request.headers.items() if k.lower() not in _CORE_OWNED_HEADERS})
    body = {
        "cmd": "request.get",
        "url": request.url,
        "maxTimeout": _timeout_ms(kwargs.get("timeout")),
        "headers": headers,
        "cookies": _core_cookies(request),
    }
    # The original send, so this Core call never loops back into the hook.
    reply = _ORIGINAL_SEND(requests.Session(), requests.Request("POST", CORE_ENDPOINT, json=body).prepare(),
                           timeout=body["maxTimeout"] / 1000.0 + 2.0)
    if reply.status_code != 200:
        return None
    solution = (reply.json() or {}).get("solution") or {}
    status = int(solution.get("status") or 0)
    if not status or status in _FALLBACK_STATUSES or status >= 500:
        return None
    if status == 200 and not solution.get("response"):
        return None  # the Core could not decode the body (e.g. not UTF-8); Python can
    content_type = str((solution.get("headers") or {}).get("content-type", "text/html")).lower()
    if not any(kind in content_type for kind in _TEXT_TYPES):
        return None  # binary bodies do not survive the Core's text response
    for cookie in solution.get("cookies") or []:
        try:
            session.cookies.set(cookie["name"], cookie["value"], domain=cookie.get("domain") or None,
                                path=cookie.get("path") or "/")
        except Exception:
            pass
    return _build_response(request, solution)


def install():
    """Hooks requests.Session.send once per process. Safe to call repeatedly."""
    global _INSTALLED, _ORIGINAL_SEND
    if _INSTALLED:
        return
    try:
        import requests.sessions
    except ImportError:
        return
    _ORIGINAL_SEND = requests.sessions.Session.send

    def send(self, request, **kwargs):
        if _eligible(request, kwargs):
            try:
                response = _send_via_core(self, request, kwargs)
            except Exception:
                response = None
            if response is not None:
                _count("core")
                return response
            _count("fallback")
        return _ORIGINAL_SEND(self, request, **kwargs)

    requests.sessions.Session.send = send
    _INSTALLED = True


_ORIGINAL_SEND = None
