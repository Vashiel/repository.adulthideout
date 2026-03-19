# -*- coding: utf-8 -*-
import re
import xbmc
import urllib.parse
from resources.lib.resolvers import resolver_utils

def resolve(url, referer=None, headers=None):
    xbmc.log(f"[AdultHideout][streamtape] Resolving: {url}", xbmc.LOGINFO)
    
    import cloudscraper
    scraper = cloudscraper.create_scraper(
        browser={"browser": "chrome", "platform": "windows", "desktop": True}
    )
    
    try:
        # Standardize URL (must be /e/ for embed)
        if '/v/' in url:
            url = url.replace('/v/', '/e/')
            
        resp = scraper.get(url, timeout=15)
        html = resp.text
        
        # Streamtape logic: Find the robotlink element and the script that populates it
        match = re.search(r"document\.getElementById\(['\"]robotlink['\"]\)\.innerHTML\s*=\s*(.+?);", html)
        if not match:
            xbmc.log("[AdultHideout][streamtape] robotlink script not found", xbmc.LOGERROR)
            return None, {}
            
        parts = match.group(1)
        
        # Robust extraction: process the JS expression piece by piece
        # Pieces are usually: 'string' + 'string'.substring(1) + 'string'.substring(2).substring(1)
        res = ""
        # Find all segments: either a string literal or a substring call
        # We'll split the expression by '+' and process each segment
        for segment in parts.split('+'):
            segment = segment.strip()
            # Find the string literal first
            str_match = re.search(r"['\"]([^'\"]*)['\"]", segment)
            if str_match:
                val = str_match.group(1)
                # Now find ALL substring calls in this same segment
                for sub_match in re.findall(r"\.substring\((\d+)\)", segment):
                    skip = int(sub_match)
                    val = val[skip:]
                res += val
        
        if not res:
            return None, {}
            
        if not res.startswith('http'):
            res = 'https:' + res if res.startswith('//') else 'https://' + res

        # Minor domain fix - Streamtape domains should resolve correctly normally
        # but let's ensure we have a valid domain.
        parsed = urllib.parse.urlparse(res)
        netloc = parsed.netloc
        if 'stream' in netloc and not any(netloc.endswith(t) for t in ['.com', '.to', '.pe', '.net']):
             # If it has a weird suffix from a failed extraction, fix it
             # But with the new loop above, this shouldn't be needed.
             pass

        stream_url = res + "&stream=1"
        xbmc.log(f"[AdultHideout][streamtape] Final stream URL: {stream_url[:80]}", xbmc.LOGINFO)
        
        play_headers = {
            "User-Agent": scraper.headers.get('User-Agent', resolver_utils.get_ua()),
            "Referer": url
        }
        
        return stream_url, play_headers

    except Exception as e:
        xbmc.log(f"[AdultHideout][streamtape] Error: {e}", xbmc.LOGERROR)
        
    return None, {}
