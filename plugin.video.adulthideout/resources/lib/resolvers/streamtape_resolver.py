# -*- coding: utf-8 -*-
import re
import xbmc
# -*- coding: utf-8 -*-
import re
import xbmc
import urllib.parse
import requests
from resources.lib.resolvers import resolver_utils

def resolve(url, referer=None, headers=None):
    xbmc.log(f"[AdultHideout][streamtape] Resolving: {url}", xbmc.LOGINFO)
    
    try:
        import cloudscraper
        scraper = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "windows", "desktop": True}
        )
    except Exception:
        scraper = requests.Session()
    
    try:
        # Standardize URL (must be /e/ for embed)
        if '/v/' in url:
            url = url.replace('/v/', '/e/')
            
        request_headers = dict(headers or {})
        request_headers.setdefault("User-Agent", resolver_utils.get_ua())
        request_headers.setdefault("Referer", referer or url)
        resp = scraper.get(url, headers=request_headers, timeout=15)
        if resp.status_code != 200:
            xbmc.log(f"[AdultHideout][streamtape] HTTP {resp.status_code}", xbmc.LOGERROR)
            return None, {}
        html = resp.text
        
        # Streamtape logic: Find the robotlink element and the script that populates it
        match = re.search(
            r"document\.getElementById\(['\"]robotlink['\"]\)\.innerHTML\s*=\s*(.+?);",
            html,
        )
        parts = match.group(1) if match else ""
        
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
            # Current pages also contain a ready-to-use hidden link. This is
            # preferable to failing when StreamTape changes only its JS wrapper.
            static = re.search(
                r'<(?:div|span)\b[^>]*id=["\'](?:robotlink|botlink|ideoolink)["\'][^>]*>([^<]+)',
                html,
                re.I,
            )
            res = static.group(1).strip() if static else ""
        if not res or "nofile" in html.lower():
            xbmc.log("[AdultHideout][streamtape] playable link not found", xbmc.LOGERROR)
            return None, {}
            
        if not res.startswith('http'):
            if res.startswith('//'):
                res = 'https:' + res
            elif re.match(r'^/[^/]+\.[^/]+/', res):
                res = 'https:/' + res
            else:
                res = urllib.parse.urljoin(url, res)

        # Minor domain fix - Streamtape domains should resolve correctly normally
        # but let's ensure we have a valid domain.
        parsed = urllib.parse.urlparse(res)
        netloc = parsed.netloc
        if 'stream' in netloc and not any(netloc.endswith(t) for t in ['.com', '.to', '.pe', '.net']):
             # If it has a weird suffix from a failed extraction, fix it
             # But with the new loop above, this shouldn't be needed.
             pass

        stream_url = res if "stream=1" in res else res + "&stream=1"
        xbmc.log(f"[AdultHideout][streamtape] Final stream URL: {stream_url[:80]}", xbmc.LOGINFO)
        
        play_headers = {
            "User-Agent": request_headers["User-Agent"],
            "Referer": url
        }
        
        return stream_url, play_headers

    except Exception as e:
        xbmc.log(f"[AdultHideout][streamtape] Error: {e}", xbmc.LOGERROR)
        
    return None, {}
