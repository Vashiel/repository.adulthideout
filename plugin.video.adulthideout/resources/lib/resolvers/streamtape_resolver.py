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
        
        # Streamtape logic: Evaluate dynamic JS assignments, prioritizing get_video
        candidates = []
        for elem_id in ("robotlink", "botlink", "ideoolink", "videoolink", "norobotlink"):
            m = re.search(
                rf"document\.getElementById\(['\"]{elem_id}['\"]\)\.innerHTML\s*=\s*(.+?);",
                html,
            )
            if m:
                candidates.append(m.group(1))

        for m in re.finditer(r"""document\.getElementById\(['"][a-zA-Z0-9]*link['"]\)\.innerHTML\s*=\s*(.+?);""", html):
            expr = m.group(1)
            if expr not in candidates:
                candidates.append(expr)

        res = ""
        for parts in candidates:
            cand_res = ""
            for segment in parts.split('+'):
                segment = segment.strip()
                str_match = re.search(r"""['"]([^'"]*)['"]""", segment)
                if str_match:
                    val = str_match.group(1)
                    for sub_match in re.findall(r"\.substring\((\d+)\)", segment):
                        skip = int(sub_match)
                        val = val[skip:]
                    cand_res += val
            if "get_video" in cand_res:
                res = cand_res
                break
            elif not res and ("get_vide" in cand_res or "token=" in cand_res):
                res = cand_res

        if res:
            res = re.sub(r"/get_vide[a-z0-9_]*\?", "/get_video?", res)

        if not res:
            static = re.search(
                r'<(?:div|span)\b[^>]*id=["\'](?:robotlink|botlink|ideoolink)["\'][^>]*>([^<]+)',
                html,
                re.I,
            )
            cand = static.group(1).strip() if static else ""
            if cand and cand.lower() not in ("robotlink", "botlink", "ideoolink", "videoolink", "norobotlink"):
                res = cand
                if "/get_vide" in res:
                    res = re.sub(r"/get_vide[a-z0-9_]*\?", "/get_video?", res)

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
