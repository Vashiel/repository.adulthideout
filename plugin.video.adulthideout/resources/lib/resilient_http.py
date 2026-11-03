# -*- coding: utf-8 -*-
"""Resilient HTTP fetching engine integrated with service.adulthideout.core."""

import json
import socket
import ssl
import threading
import urllib.parse
import urllib.request
import requests

CORE_ENDPOINT = "http://127.0.0.1:8191/v1"
_IPV4_LOCK = threading.Lock()


def _ipv4_call(callback):
    """Run one network call with IPv4 DNS results without changing global state permanently."""
    with _IPV4_LOCK:
        original = socket.getaddrinfo

        def ipv4_only(*args, **kwargs):
            return [entry for entry in original(*args, **kwargs) if entry[0] == socket.AF_INET]

        socket.getaddrinfo = ipv4_only
        try:
            return callback()
        finally:
            socket.getaddrinfo = original


def _log(logger, level, message):
    if not logger:
        return
    log_fn = getattr(logger, level, None)
    if callable(log_fn):
        log_fn(message)


def fetch_text(
    url,
    headers=None,
    scraper=None,
    logger=None,
    timeout=120,
    use_windows_curl_fallback=True,
    prefer_ipv4=False,
):
    request_headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": url,
    }
    if headers:
        request_headers.update(headers)

    # 1. Primary path: High-speed Rust Core Engine with browser-compatible session handling
    try:
        core_headers = {k: str(v) for k, v in request_headers.items() if k.lower() != "user-agent"}
        req_body = {
            "cmd": "request.get",
            "url": url,
            "maxTimeout": int(timeout * 1000),
            "headers": core_headers,
        }
        resp = requests.post(CORE_ENDPOINT, json=req_body, timeout=max(3.0, float(timeout) + 1.5))
        if resp.status_code == 200:
            sol = resp.json().get("solution", {})
            body = sol.get("response", "")
            if body and sol.get("status") in (200, 206):
                _log(logger, "debug", "HTTP response accepted via service.adulthideout.core")
                if scraper is not None and hasattr(scraper, "cookies"):
                    try:
                        netloc = urllib.parse.urlsplit(url).netloc
                        parts = netloc.split(".")
                        root_domain = "." + ".".join(parts[-2:]) if len(parts) >= 2 else netloc
                        for c in sol.get("cookies", []):
                            scraper.cookies.set(c["name"], c["value"], domain=root_domain)
                            scraper.cookies.set(c["name"], c["value"])
                    except Exception:
                        pass
                return body
    except Exception as exc:
        _log(logger, "debug", f"Core engine bypassed: {exc}")

    fallback_timeout = min(float(timeout), 3.0) if timeout <= 6 else timeout

    # 2. Secondary path: Direct scraper session if provided
    if scraper is not None:
        try:
            request = lambda: scraper.get(url, timeout=fallback_timeout, headers=request_headers)
            response = _ipv4_call(request) if prefer_ipv4 else request()
            if response.status_code == 200:
                _log(logger, "debug", "HTTP response accepted via scraper")
                return response.text
            _log(logger, "error", f"HTTP {response.status_code} for {url}")
        except Exception as exc:
            _log(logger, "warning", f"Scraper request failed: {exc}")

    # 3. Tertiary path: Standard library urllib (skip redundant attempt when fast timeout <= 6 and scraper already ran)
    if scraper is not None and timeout <= 6:
        return None
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(url, headers=request_headers)
        request = lambda: urllib.request.urlopen(req, timeout=fallback_timeout, context=ctx)
        response = _ipv4_call(request) if prefer_ipv4 else request()
        with response:
            if 200 <= response.status < 300:
                _log(logger, "debug", "HTTP response accepted via urllib")
                return response.read().decode("utf-8", errors="ignore")
            _log(logger, "error", f"urllib HTTP {response.status} for {url}")
    except Exception as exc:
        _log(logger, "warning", f"urllib request failed: {exc}")

    return None


def fetch_windows_text(url, headers=None, logger=None, timeout=120, prefer_ipv4=False):
    """Backward compatibility alias: delegates directly to fetch_text without subprocesses."""
    return fetch_text(
        url=url,
        headers=headers,
        logger=logger,
        timeout=timeout,
        prefer_ipv4=prefer_ipv4,
    )


def fetch_text_with_solution(url, headers=None, logger=None, timeout=120):
    """Fetch URL and return full solution object (response, cookies, userAgent) from core engine."""
    try:
        req_body = {
            "cmd": "request.get",
            "url": url,
            "maxTimeout": int(timeout * 1000),
        }
        resp = requests.post(CORE_ENDPOINT, json=req_body, timeout=timeout + 5)
        if resp.status_code == 200:
            sol = resp.json().get("solution", {})
            if sol.get("status") in (200, 206) and sol.get("response"):
                _log(logger, "debug", "HTTP response solution accepted via service.adulthideout.core")
                return sol
    except Exception as exc:
        _log(logger, "debug", f"Core engine error: {exc}")

    body = fetch_text(url, headers=headers, logger=logger, timeout=timeout)
    if body:
        return {"response": body, "status": 200, "cookies": [], "userAgent": ""}
    return None


WARMUP_ENDPOINT = "http://127.0.0.1:8191/warmup"


def get_warmup_status():
    """Query service.adulthideout.core for active Cloudflare/Turnstile warmup pool status."""
    try:
        resp = requests.get(WARMUP_ENDPOINT, timeout=2.0)
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return None


def register_warmup_domain(domain, url=None):
    """Register a new domain to be monitored and pre-warmed by service.adulthideout.core."""
    try:
        payload = {"domain": domain}
        if url:
            payload["url"] = url
        resp = requests.post(f"{WARMUP_ENDPOINT}/register", json=payload, timeout=2.0)
        return resp.status_code == 200
    except Exception:
        return False


def trigger_warmup(domain=None):
    """Trigger immediate background solving/warming of a domain or all registered domains."""
    try:
        payload = {"domain": domain} if domain else {}
        resp = requests.post(f"{WARMUP_ENDPOINT}/trigger", json=payload, timeout=10.0)
        return resp.status_code == 200
    except Exception:
        return False


