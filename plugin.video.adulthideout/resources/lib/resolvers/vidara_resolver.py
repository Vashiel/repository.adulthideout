# -*- coding: utf-8 -*-

import json
import re
import urllib.parse
import urllib.request
import urllib.error

DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"


def resolve(embed_url, referer=None, headers=None):
    headers = dict(headers) if headers else {}
    ua = headers.get("User-Agent", DEFAULT_USER_AGENT)

    match = re.search(r"/(?:e|embed|v)/([a-zA-Z0-9_-]+)", embed_url or "")
    if not match:
        return "", headers
    filecode = match.group(1)

    parsed = urllib.parse.urlparse(embed_url)
    origin = "{}://{}".format(parsed.scheme or "https", parsed.netloc)
    api_url = "{}/api/stream".format(origin)

    payload = json.dumps({
        "filecode": filecode,
        "device": "desktop",
        "codecs": ["h264", "aac"],
    }).encode("utf-8")

    req_headers = {
        "User-Agent": ua,
        "Referer": embed_url,
        "Origin": origin,
        "Content-Type": "application/json",
        "Accept": "application/json, text/plain, */*",
    }

    try:
        req = urllib.request.Request(api_url, data=payload, headers=req_headers, method="POST")
        with urllib.request.urlopen(req, timeout=12) as response:
            if response.status == 200:
                data = json.loads(response.read().decode("utf-8", "replace"))
                stream_url = (data.get("streaming_url") or "").strip()
                if stream_url:
                    out_headers = {
                        "User-Agent": ua,
                        "Referer": origin + "/",
                    }
                    return stream_url, out_headers
    except Exception:
        pass

    return "", headers
