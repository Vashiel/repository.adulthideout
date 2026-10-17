# -*- coding: utf-8 -*-

import html
import re
import urllib.parse
from resources.lib.resolvers.resolver_utils import http_get


def resolve(embed_url, referer=None, headers=None):
    headers = dict(headers) if headers else {}
    ua = headers.get("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
    headers["Referer"] = embed_url

    page_html = http_get(embed_url, headers=headers)
    if not page_html:
        return "", headers

    source_match = re.search(r'<source\b[^>]+src=["\']([^"\']+)["\']', page_html, re.I)
    if source_match:
        src = html.unescape(source_match.group(1)).strip()
        parsed = urllib.parse.urlparse(embed_url)
        origin = "{}://{}/".format(parsed.scheme or "https", parsed.netloc)
        return src, {"User-Agent": ua, "Referer": origin}

    # Fallback for any media url inside video tags
    video_matches = re.findall(r'https?://[^\s"\'<>]+\.(?:mp4|m3u8)[^\s"\'<>]*', page_html, re.I)
    for m in video_matches:
        if "preview" not in m.lower():
            parsed = urllib.parse.urlparse(embed_url)
            origin = "{}://{}/".format(parsed.scheme or "https", parsed.netloc)
            return html.unescape(m).strip(), {"User-Agent": ua, "Referer": origin}

    return "", headers
