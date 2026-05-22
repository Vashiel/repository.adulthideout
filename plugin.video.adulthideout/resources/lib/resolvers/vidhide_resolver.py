# -*- coding: utf-8 -*-
import html
import re
import sys
import os
import urllib.parse

try:
    import xbmc
except Exception:
    xbmc = None

try:
    addon_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    vendor_path = os.path.join(addon_root, "resources", "lib", "vendor")
    if os.path.isdir(vendor_path) and vendor_path not in sys.path:
        sys.path.insert(0, vendor_path)
except Exception:
    pass

try:
    import cloudscraper
except Exception:
    cloudscraper = None

import requests


UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/128.0.0.0 Safari/537.36"
)


def _log(message, level=None):
    if xbmc:
        xbmc.log("[AdultHideout][vidhide] {}".format(message), level or xbmc.LOGINFO)


def _make_session():
    if cloudscraper:
        try:
            return cloudscraper.create_scraper(
                browser={"browser": "chrome", "platform": "windows", "desktop": True}
            )
        except Exception:
            pass
    return requests.Session()


def _headers(referer=None, accept=None):
    headers = {
        "User-Agent": UA,
        "Accept": accept or "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    if referer:
        headers["Referer"] = referer
    return headers


def _int_to_base(value, base):
    chars = "0123456789abcdefghijklmnopqrstuvwxyz"
    if value == 0:
        return "0"
    result = ""
    while value:
        result = chars[value % base] + result
        value //= base
    return result


def _unpack_packer_block(block):
    match = re.search(
        r"eval\(function\(p,a,c,k,e,d\)\{.*?\}\('(.*?)',(\d+),(\d+),'(.*?)'\.split\('\|'\)\)",
        block,
        re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return ""

    payload, base, count, words = match.groups()
    try:
        base = int(base)
        count = int(count)
        words = words.split("|")
        payload = payload.encode("utf-8").decode("unicode_escape")
    except Exception:
        return ""

    unpacked = payload
    for idx in range(count - 1, -1, -1):
        if idx < len(words) and words[idx]:
            token = _int_to_base(idx, base)
            unpacked = re.sub(r"\b{}\b".format(re.escape(token)), words[idx], unpacked)
    return unpacked


def _unpack_all(page_html):
    unpacked = []
    for match in re.finditer(
        r"eval\(function\(p,a,c,k,e,d\)\{.*?\.split\('\|'\)\)\)",
        page_html or "",
        re.IGNORECASE | re.DOTALL,
    ):
        decoded = _unpack_packer_block(match.group(0))
        if decoded:
            unpacked.append(decoded)
    return unpacked


def _absolute_url(value, base_url):
    value = html.unescape(value or "").replace("\\/", "/").strip()
    if value.startswith("//"):
        return "https:" + value
    return urllib.parse.urljoin(base_url, value)


def _extract_links_object(text):
    match = re.search(r"\blinks\s*=\s*\{([\s\S]*?)\}\s*;", text or "", re.IGNORECASE)
    if not match:
        return {}

    links = {}
    for key, value in re.findall(r'["\']?([a-z0-9_]+)["\']?\s*:\s*["\']([^"\']+)["\']', match.group(1), re.IGNORECASE):
        links[key.lower()] = html.unescape(value).replace("\\/", "/")
    return links


def _pick_stream(page_html, embed_url):
    candidates = []
    for content in [page_html] + _unpack_all(page_html):
        links = _extract_links_object(content)
        for key in ("hls4", "hls3", "hls2", "hls"):
            if links.get(key):
                candidates.append(_absolute_url(links[key], embed_url))

        for match in re.findall(r'["\']([^"\']+\.m3u8[^"\']*)["\']', content or "", re.IGNORECASE):
            candidates.append(_absolute_url(match, embed_url))

    seen = set()
    unique = []
    for candidate in candidates:
        if candidate and candidate not in seen:
            seen.add(candidate)
            unique.append(candidate)

    if unique:
        # Vidhide's own player prefers hls4 first, because it is a local signed proxy path.
        unique.sort(key=lambda item: (0 if "/stream/" in item else 1, len(item)))
        return unique[0]
    return ""


def resolve(url, referer=None, headers=None):
    _log("Resolving: {}".format(url))
    session = _make_session()
    request_headers = _headers(referer or url)
    if headers:
        request_headers.update(headers)

    try:
        response = session.get(url, headers=request_headers, timeout=25, allow_redirects=True)
    except Exception as exc:
        _log("Request failed: {}".format(exc), getattr(xbmc, "LOGERROR", None))
        return "", {}

    if response.status_code != 200:
        _log("HTTP {} for {}".format(response.status_code, url), getattr(xbmc, "LOGERROR", None))
        return "", {}

    embed_url = response.url or url
    stream_url = _pick_stream(response.text, embed_url)
    if not stream_url:
        _log("No HLS source found", getattr(xbmc, "LOGERROR", None))
        return "", {}

    parsed = urllib.parse.urlparse(embed_url)
    origin = "{}://{}".format(parsed.scheme, parsed.netloc)
    stream_headers = {
        "User-Agent": request_headers.get("User-Agent", UA),
        "Referer": embed_url,
        "Origin": origin,
        "Accept": "*/*",
    }
    _log("Resolved via {}: {}".format(parsed.netloc, stream_url[:120]))
    return stream_url, stream_headers
