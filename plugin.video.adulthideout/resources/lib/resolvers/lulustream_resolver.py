# -*- coding: utf-8 -*-

import re
from resources.lib.resolvers.resolver_utils import http_get

def resolve(embed_url, referer, headers):
    # FIX: Sicherstellen, dass headers ein Dictionary ist, auch wenn None übergeben wurde
    headers = dict(headers) if headers else {}
    
    headers["Referer"] = embed_url
    html = http_get(embed_url, headers=headers)
    if not html:
        return "", headers

    m = re.search(r'(https?://[^\s"\']+\.(?:mp4|m3u8)[^\s"\']*)', html, re.IGNORECASE)
    if m:
        return m.group(1).strip(), headers

    return "", headers