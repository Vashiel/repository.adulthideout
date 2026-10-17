# -*- coding: utf-8 -*-

import re
import urllib.parse
import requests


def resolve(embed_url, referer=None, headers=None):
    headers = dict(headers) if headers else {}
    ua = headers.get("User-Agent") or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    session = requests.Session()
    req_headers = {"User-Agent": ua, "Referer": referer or embed_url}

    try:
        r = session.get(embed_url, headers=req_headers, timeout=15)
        html = r.text if r.status_code == 200 else ""
    except Exception:
        html = ""

    parsed = urllib.parse.urlparse(embed_url)
    domain = "{}://{}".format(parsed.scheme, parsed.netloc)

    code_match = re.search(r'/e/([a-zA-Z0-9]+)', parsed.path)
    code = code_match.group(1) if code_match else ""
    if not code and html:
        m = re.search(r'name=["\']file_code["\'][^>]*value=["\']([^"\']*)["\']', html)
        if m:
            code = m.group(1)

    if not code:
        return "", headers

    post_url = "{}/dl".format(domain)
    data = {
        "op": "embed",
        "file_code": code,
        "auto": "1",
        "referer": referer or "",
    }
    post_headers = {"User-Agent": ua, "Referer": embed_url}
    try:
        res = session.post(post_url, data=data, headers=post_headers, timeout=15)
        post_html = res.text if res.status_code == 200 else ""
    except Exception:
        post_html = ""

    stream_m = re.findall(r'(https?://[^\s"\'<>]+\.(?:mp4|m3u8)[^\s"\'<>]*)', post_html)
    out_headers = {
        "User-Agent": ua,
        "Referer": "{}/".format(domain),
    }
    for u in stream_m:
        if "preview" not in u.lower():
            return u.strip(), out_headers

    return "", headers
