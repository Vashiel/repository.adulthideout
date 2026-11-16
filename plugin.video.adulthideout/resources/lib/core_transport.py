# -*- coding: utf-8 -*-
"""Routes page fetches of requests/cloudscraper sessions and urllib openers through the Rust Core.

Every plain GET for a page goes to the Core first (browser-like headers, shared Cloudflare
sessions). Anything the Core cannot serve falls back to the original requests path, so a
site never gets worse than before. POST, streams, media and local calls are untouched.
"""

import contextlib
import datetime
import http.client
import io
import json
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
_BYPASS_ATTR = "_adulthideout_core_bypass"


@contextlib.contextmanager
def bypass():
    """For callers that already asked the Core and now want the plain Python path."""
    # Kept on the thread, not in this module: Tactile may load this file twice under two names.
    thread = threading.current_thread()
    previous = getattr(thread, _BYPASS_ATTR, False)
    setattr(thread, _BYPASS_ATTR, True)
    try:
        yield
    finally:
        setattr(thread, _BYPASS_ATTR, previous)


def stats():
    with _STATS_LOCK:
        return dict(_STATS)


def _count(key):
    with _STATS_LOCK:
        _STATS[key] += 1


def record(used_core):
    """For callers that ask the Core themselves (resilient_http), so stats() sees every page."""
    _count("core" if used_core else "fallback")


def _eligible(method, url, headers):
    if getattr(threading.current_thread(), _BYPASS_ATTR, False) or method != "GET":
        return False
    if any(k.lower() == "range" for k in headers):
        return False  # partial media downloads
    parts = urllib.parse.urlsplit(url)
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


def _cookie_list(cookie_header, url):
    host = urllib.parse.urlsplit(url).hostname or ""
    cookies = []
    for pair in (cookie_header or "").split(";"):
        name, sep, value = pair.strip().partition("=")
        if sep and name:
            cookies.append({"name": name, "value": value, "domain": host})
    return cookies


def english_unless_set(headers):
    """The Core's browser profile asks for German pages. Modules parse English pages (zbporn served
    de.zbporn.com links its pattern misses), so ask for English unless the module chose a language."""
    if not any(k.lower() == "accept-language" for k in headers):
        headers["Accept-Language"] = "en-US,en;q=0.9"
    return headers


def _core_solution(url, headers, timeout):
    """The Core's answer for a page, or None when the caller should use its own path."""
    cookie_header = next((v for k, v in headers.items() if k.lower() == "cookie"), "")
    body = {
        "cmd": "request.get",
        "url": url,
        "maxTimeout": _timeout_ms(timeout),
        "headers": english_unless_set({k: str(v) for k, v in headers.items() if k.lower() not in _CORE_OWNED_HEADERS}),
        "cookies": _cookie_list(cookie_header, url),
    }
    # Plain http.client: this call must never pass through the requests or urllib hooks.
    parts = urllib.parse.urlsplit(CORE_ENDPOINT)
    connection = http.client.HTTPConnection(parts.hostname, parts.port, timeout=body["maxTimeout"] / 1000.0 + 2.0)
    try:
        connection.request("POST", parts.path, json.dumps(body), {"Content-Type": "application/json"})
        reply = connection.getresponse()
        if reply.status != 200:
            return None
        solution = (json.loads(reply.read().decode("utf-8")) or {}).get("solution") or {}
    finally:
        connection.close()
    status = int(solution.get("status") or 0)
    if not status or status in _FALLBACK_STATUSES or status >= 500:
        return None
    if status == 200 and not solution.get("response"):
        return None  # the Core could not decode the body (e.g. not UTF-8); Python can
    content_type = str((solution.get("headers") or {}).get("content-type", "text/html")).lower()
    if not any(kind in content_type for kind in _TEXT_TYPES):
        return None  # binary bodies do not survive the Core's text response
    return solution


def _try_core(url, headers, timeout):
    try:
        solution = _core_solution(url, headers, timeout)
    except Exception:
        solution = None
    _count("core" if solution is not None else "fallback")
    return solution


def _requests_response(request, solution):
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


def _urllib_response(request, solution):
    import urllib.response

    content = (solution.get("response") or "").encode("utf-8")
    headers = http.client.HTTPMessage()
    for name, value in (solution.get("headers") or {}).items():
        if name.lower() not in ("content-encoding", "content-length", "transfer-encoding", "set-cookie"):
            headers[name] = value
    headers["Content-Length"] = str(len(content))
    # As Set-Cookie headers, so the module's own HTTPCookieProcessor stores them like any response.
    for cookie in solution.get("cookies") or []:
        line = "{}={}; Path={}".format(cookie.get("name"), cookie.get("value"), cookie.get("path") or "/")
        if cookie.get("domain"):
            line += "; Domain=" + cookie["domain"]
        headers["Set-Cookie"] = line
    response = urllib.response.addinfourl(io.BytesIO(content), headers, solution.get("url") or request.full_url,
                                          int(solution.get("status") or 0))
    response.msg = "OK"
    return response


def install():
    """Hooks requests and urllib once per process. Safe to call repeatedly."""
    global _INSTALLED, _ORIGINAL_SEND, _ORIGINAL_OPEN
    if _INSTALLED:
        return
    import urllib.request

    _ORIGINAL_OPEN = urllib.request.OpenerDirector._open

    def _open(self, req, data=None):
        # _open runs after the request processors, so the module's cookies are already on req.
        headers = dict(req.header_items())
        if data is None and _eligible(req.get_method(), req.full_url, headers):
            solution = _try_core(req.full_url, headers, getattr(req, "timeout", None))
            if solution is not None:
                return _urllib_response(req, solution)
        return _ORIGINAL_OPEN(self, req, data)

    urllib.request.OpenerDirector._open = _open
    try:
        import requests.sessions
    except ImportError:
        _INSTALLED = True
        return
    _ORIGINAL_SEND = requests.sessions.Session.send

    def send(self, request, **kwargs):
        if not kwargs.get("stream") and _eligible(request.method, request.url, request.headers):
            solution = _try_core(request.url, dict(request.headers), kwargs.get("timeout"))
            if solution is not None:
                for cookie in solution.get("cookies") or []:
                    try:
                        where = {"path": cookie.get("path") or "/"}
                        if cookie.get("domain"):  # requests fails on domain=None, so only pass a real one
                            where["domain"] = cookie["domain"]
                        self.cookies.set(cookie["name"], cookie["value"], **where)
                    except Exception:
                        pass
                return _requests_response(request, solution)
        return _ORIGINAL_SEND(self, request, **kwargs)

    requests.sessions.Session.send = send
    _INSTALLED = True


_ORIGINAL_SEND = None
_ORIGINAL_OPEN = None
