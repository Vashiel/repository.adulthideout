# -*- coding: utf-8 -*-
import re
import time
import random
import logging
from resources.lib.resolvers.resolver_utils import http_get
# Falls packer im lib Ordner ist:
try:
    from resources.lib.modules import packer 
except:
    pass

try:
    import cloudscraper
except:
    pass

# FIX: Signatur angepasst, um mit resolver.py kompatibel zu sein
def resolve(url, referer=None, headers=None):
    
    # Falls Cloudscraper vorhanden, nutzen wir ihn für den ersten Request
    try:
        scraper = cloudscraper.create_scraper()
        html = scraper.get(url).text
    except:
        # Fallback
        html = http_get(url)

    if not html:
        return "", {}

    # Suche nach gepacktem Code (Dean Edwards Packer)
    packed_data = re.search(r"eval\(function\(p,a,c,k,e,d\).*?\.split\('\|'\)\)\)", html)
    
    unpacked = ""
    if packed_data:
        try:
            unpacked = packer.unpack(packed_data.group())
        except:
            pass
    
    # Suche in unpacked oder original html nach .mp4
    sources = []
    content_to_search = unpacked if unpacked else html
    
    # Suche nach file: "url" Muster
    r = re.search(r'file\s*:\s*["\']([^"\']+\.mp4[^"\']*)["\']', content_to_search)
    if r:
        return r.group(1), {}
        
    # Einfacher Regex Fallback
    r = re.search(r'["\'](https?://[^"\']+\.mp4[^"\']*)["\']', content_to_search)
    if r:
        return r.group(1), {}

    return "", {}