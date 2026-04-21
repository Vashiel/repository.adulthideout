# -*- coding: utf-8 -*-
import re
import xbmc
from resources.lib.resolvers import resolver_utils


def _unpack_packer(html_text):
    match = re.search(
        r"eval\(function\(p,a,c,k,e,d\)\{.*?\}\('(.*?)',(\d+),(\d+),'(.*?)'\.split\('\|'\),0,\{\}\)\)",
        html_text,
        re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return ""

    payload, base, count, words = match.groups()
    base = int(base)
    count = int(count)
    words = words.split("|")
    payload = payload.encode("utf-8").decode("unicode_escape")

    unpacked = payload
    for idx in range(count - 1, -1, -1):
        if idx < len(words) and words[idx]:
            unpacked = re.sub(r"\b{}\b".format(re.escape(str(idx))), words[idx], unpacked)
    return unpacked


def resolve(url, referer=None, headers=None):
    xbmc.log(f"[AdultHideout][mixdrop] Resolving: {url}", xbmc.LOGINFO)
    
    import cloudscraper
    scraper = cloudscraper.create_scraper(
        browser={"browser": "chrome", "platform": "windows", "desktop": True}
    )
    
    try:
        # Standardize URL
        if '/f/' in url:
            url = url.replace('/f/', '/e/')
            
        resp = scraper.get(url, timeout=15)
        html = resp.text
        
        # Look for MDCore.wurl or VSMP4.url
        # Mixdrop often uses packed JS, but the URL is often partially visible
        
        # 1. Try to find the stream URL directly in the page if it's not packed
        match = re.search(r'(?:MDCore\.wurl|VSMP4\.url)\s*=\s*["\']([^"\']+)["\']', html)
        if match:
            stream_url = match.group(1)
            if stream_url.startswith('//'):
                stream_url = 'https:' + stream_url
            xbmc.log(f"[AdultHideout][mixdrop] Found direct URL: {stream_url[:80]}", xbmc.LOGINFO)
            return stream_url, {"User-Agent": scraper.headers.get('User-Agent', resolver_utils.get_ua()), "Referer": url}

        unpacked = _unpack_packer(html)
        if unpacked:
            match = re.search(r'(?:MDCore\.wurl|VSMP4\.url)\s*=\s*["\']?([^"\';]+)', unpacked)
            if match:
                stream_url = match.group(1).strip()
                if stream_url.startswith('//'):
                    stream_url = 'https:' + stream_url
                xbmc.log(f"[AdultHideout][mixdrop] Found packed URL: {stream_url[:80]}", xbmc.LOGINFO)
                return stream_url, {"User-Agent": scraper.headers.get('User-Agent', resolver_utils.get_ua()), "Referer": url}

        # 2. Try to find the packed block and extract pieces
        # MixDrop's packer often contains the delivery URL pieces
        # Example: MDCore.wurl="//"+removetred+"."+deliverydomain+"..."
        
        # Let's search for any //...delivery... patterns
        delivery = re.search(r'["\'](//[^"\']+?delivery[^"\']+)["\']', html)
        if delivery:
             stream_url = "https:" + delivery.group(1)
             return stream_url, {"User-Agent": scraper.headers.get('User-Agent', resolver_utils.get_ua()), "Referer": url}

    except Exception as e:
        xbmc.log(f"[AdultHideout][mixdrop] Error: {e}", xbmc.LOGERROR)
        
    return None, {}
