# -*- coding: utf-8 -*-
import re
import xbmc
from resources.lib.resolvers import resolver_utils

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
