# -*- coding: utf-8 -*-

import re
import urllib.parse
import requests
from resources.lib.resolvers.resolver_utils import http_get


def _base_to_int(value, base):
    chars = "0123456789abcdefghijklmnopqrstuvwxyz"
    total = 0
    for char in value.lower():
        if char not in chars[:base]:
            raise ValueError("invalid base token")
        total = total * base + chars.index(char)
    return total


def _unpack_packed_js(page_html):
    match = re.search(
        r"eval\(function\(p,a,c,k,e,d\).*?\}\('(?P<p>[\s\S]*?)',(?P<a>\d+),(?P<c>\d+),'(?P<k>[\s\S]*?)'\.split\('\|'\)\)\)",
        page_html or "",
        re.DOTALL,
    )
    if not match:
        return ""

    payload = match.group("p")
    base = int(match.group("a"))
    keywords = match.group("k").split("|")

    def replace_token(token_match):
        token = token_match.group(0)
        try:
            idx = _base_to_int(token, base)
        except ValueError:
            return token
        if 0 <= idx < len(keywords) and keywords[idx]:
            return keywords[idx]
        return token

    try:
        return re.sub(r"\b\w+\b", replace_token, payload)
    except Exception:
        return ""


def resolve(embed_url, referer, headers):
    headers = dict(headers) if headers else {}
    ua = headers.get("User-Agent") or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    req_headers = {
        "User-Agent": ua,
        "Referer": referer or embed_url,
    }
    
    html = ""
    # Lulu/TNMR flags cloudscraper TLS fingerprints and generates 403 tokens;
    # use a clean requests.Session first for legitimate stream token generation.
    try:
        session = requests.Session()
        resp = session.get(embed_url, headers=req_headers, timeout=15)
        if resp.status_code == 200:
            html = resp.text
    except Exception:
        html = ""

    if not html:
        headers["Referer"] = embed_url
        html = http_get(embed_url, headers=headers)
    if not html:
        return "", headers

    parsed = urllib.parse.urlparse(embed_url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    out_headers = dict(headers)
    out_headers["User-Agent"] = ua
    out_headers["Referer"] = origin + "/"
    out_headers["Origin"] = origin

    m = re.search(r'(https?://[^\s"\']+\.(?:mp4|m3u8)[^\s"\']*)', html, re.IGNORECASE)
    if m:
        return m.group(1).strip(), out_headers

    unpacked = _unpack_packed_js(html)
    if unpacked:
        m = re.search(r'(https?://[^\s"\']+\.(?:mp4|m3u8)[^\s"\']*)', unpacked, re.IGNORECASE)
        if m:
            return m.group(1).strip(), out_headers

    return "", headers
