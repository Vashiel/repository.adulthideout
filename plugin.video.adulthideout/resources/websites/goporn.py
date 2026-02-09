
import re
import urllib.parse
import time
import math
import sys
import os
import xbmc
import xbmcaddon
from resources.lib.base_website import BaseWebsite
from resources.lib.decoders.kvs_decoder import kvs_decode_url

try:
    addon_path = xbmcaddon.Addon().getAddonInfo('path')
    vendor_path = os.path.join(addon_path, 'resources', 'lib', 'vendor')
    if vendor_path not in sys.path:
        sys.path.insert(0, vendor_path)
except Exception:
    pass

import cloudscraper

class GoPorn(BaseWebsite):
    NAME = "goporn"
    BASE_URL = "https://go.porn/"
    SEARCH_URL = "https://go.porn/search/{}/"
    UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    
    sort_options = ["Latest", "Top Rated", "Most Viewed"]
    sort_paths = {
        "Latest": "latest-updates/",
        "Top Rated": "top-rated/",
        "Most Viewed": "most-popular/"
    }

    def __init__(self, addon_handle):
        super().__init__(self.NAME, self.BASE_URL, self.SEARCH_URL, addon_handle)
        self.scraper = cloudscraper.create_scraper(browser={'custom': self.UA})

    def get_headers(self, url):
        return {
            "User-Agent": self.UA,
            "Referer": "https://go.porn/",
        }

    def make_request(self, url):
        try:
            headers = self.get_headers(url)
            r = self.scraper.get(url, headers=headers, timeout=20)
            return r.text
        except Exception as e:
            xbmc.log(f"[GoPorn] Request error: {e}", xbmc.LOGERROR)
            return None

    def get_listing(self, url):
        if url == "search":
             self.show_search_menu()
             return

        if url == self.BASE_URL:
            url = "https://go.porn/latest-updates/"

        self.process_content(url)

    def process_content(self, url):
        if "/categories/" in url and "from" not in url and not url.endswith("/categories/"):
             pass 
        
        if url.rstrip('/') == "https://go.porn/categories":
             self.list_categories(url)
             return

        html = self.make_request(url)
        if not html:
            return
            
        show_ui = True
        if "/categories/" in url:
             if url.rstrip('/').endswith('/categories'):
                 show_ui = False 
        
        if show_ui:
            self.add_dir("[COLOR yellow]Search[/COLOR]", "search", 5, self.icons['search'], self.fanart)
            if not "categories" in url:
                 self.add_dir("[COLOR yellow]Categories[/COLOR]", "https://go.porn/categories/", 2, self.icons['categories'], self.fanart)

        last_video_url = None
        
        blocks = html.split('class="item')
        for block in blocks[1:]:
            if 'label-sticky' in block or 'class="item sticky' in block:
                 continue
                 
            link_match = re.search(r'<a[^>]+href="(https://go\.porn/video[^"]+)"[^>]*title="([^"]+)"', block)
            if not link_match:
                continue
                
            video_url = link_match.group(1)
            
            if video_url == last_video_url:
                continue
            last_video_url = video_url
            
            title = link_match.group(2)
            
            thumb_match = re.search(r'data-original="([^"]+)"', block)
            if not thumb_match:
                 thumb_match = re.search(r'src="([^"]+)"', block)
            
            thumbnail = ""
            if thumb_match:
                candidate = thumb_match.group(1)
                if "data:image" not in candidate and "loader.gif" not in candidate:
                    thumbnail = candidate
            
            if not thumbnail:
                 fallback = re.search(r'(?:data-original|src)="([^"]+\.(?:jpg|png|jpeg|webp)[^"]*)"', block)
                 if fallback: thumbnail = fallback.group(1)

            dur_match = re.search(r'<span class="duration">([^<]+)</span>', block)
            duration = dur_match.group(1) if dur_match else ""
            
            self.add_link(
                name=title,
                url=video_url,
                mode=4,
                icon=thumbnail,
                fanart=self.fanart,
                info_labels={'duration': duration, 'mediatype': 'video'}
            )
            
        load_more = re.search(r'data-parameters="([^"]*(?:from|from_videos\+from_albums):(\d+)[^"]*)"', html)
        if load_more:
            param_str = load_more.group(1)
            next_page = load_more.group(2)
            
            query_key = 'from'
            if 'from_videos' in param_str:
                query_key = 'from_videos'

            if "?" in url:
                parsed = urllib.parse.urlparse(url)
                qs = urllib.parse.parse_qs(parsed.query)
                qs[query_key] = [next_page]
                new_query = urllib.parse.urlencode(qs, doseq=True)
                next_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}?{new_query}"
            else:
                next_url = f"{url}?{query_key}={next_page}"
                
            self.add_dir("[COLOR blue]Next Page[/COLOR]", next_url, 2, "DefaultFolder.png")
        
        self.end_directory()

    def list_categories(self, url):
        html = self.make_request(url)
        if not html:
            return

        self.add_dir("[COLOR yellow]Search[/COLOR]", "search", 5, self.icons['search'], self.fanart)

        blocks = html.split('class="item')
        for block in blocks[1:]:
            link_match = re.search(r'<a[^>]+href="(https://go\.porn/categories/[^"]+)"', block)
            if not link_match:
                continue
            
            cat_url = link_match.group(1)
            title_match = re.search(r'title="([^"]+)"', block)
            title = title_match.group(1) if title_match else "Unknown"
            
            thumb_match = re.search(r'(?:data-original|src)="([^"]+\.jpg[^"]*)"', block)
            thumbnail = thumb_match.group(1) if thumb_match else ""
            
            self.add_dir(title, cat_url, 2, thumbnail)
            
        self.end_directory()

    def _fetch_kt_player(self, html, scraper):
        """Extracts and fetches the kt_player.js content."""
        match = re.search(r'src="([^"]*kt_player\.js[^"]*)"', html)
        if match:
            js_url = match.group(1)
            if not js_url.startswith("http"):
                if js_url.startswith("//"):
                    js_url = "https:" + js_url
                elif js_url.startswith("/"):
                    js_url = "https://go.porn" + js_url
                else:
                    js_url = "https://go.porn/" + js_url
            
            self.logger.info(f"[GoPorn] Fetching kt_player.js: {js_url}")
            try:
                r = scraper.get(js_url, timeout=10)
                if r.status_code == 200:
                    return r.text
            except Exception as e:
                self.logger.error(f"[GoPorn] Failed to fetch kt_player: {e}")
        return None

    def _extract_obfuscation_array(self, js_content):
        """Extracts the obfuscation array 'f' from JS content."""
        if not js_content: return []
        match = re.search(r'var f=\[(.*?)\]', js_content)
        if not match: return []
        
        content = match.group(1)
        parts = []
        current = ""
        in_quote = False
        for char in content:
            if char == '"':
                in_quote = not in_quote
            elif char == ',' and not in_quote:
                parts.append(current.strip('"'))
                current = ""
                continue
            current += char
        parts.append(current.strip('"'))
        return parts

    def _decrypt_video_url(self, flashvars, f_array):
        """
        Decrypts video_url using the logic reverse-engineered from kt_player.js
        (dE, dC, dD functions).
        """
        if not f_array: return None
        
        def ca(a): return f_array[a-1]
        def bZ(a): return f_array[a+2]
        def cd(a): return f_array[a-4]
        def b_(a): return f_array[a+4]
        
        prefix = ca(32)
        key_char = bZ(22)
        marker_char = cd(28)
        split_char = b_(20) 
        
        target_val = None
        for k, v in flashvars.items():
            if v.startswith(prefix):
                b = v[8:]
                if b.startswith(key_char):
                    target_val = v
                    break
        
        if not target_val:
            return None
            
        val_str = target_val[8:][1:]
        
        h_idx = val_str.find(marker_char)
        i = 0
        if h_idx > 0:
            try:
                i = int(val_str[:h_idx])
            except:
                i = 0
                
        digit_sum = 0
        for char in val_str:
            if char.isdigit():
                digit_sum += int(char)
        
        bu = 0
        for c in range(12):
            g = i + c * digit_sum
            add_val = math.floor(g / 7)
            
            f_val = c * digit_sum
            sub_val = math.floor(f_val / 6)
            
            bu += add_val
            bu -= sub_val
            
        if bu >= 0:
            return None
            
        f_num = -bu
        f_str = str(f_num)
        for _ in range(4):
            f_str += f_str
            
        h_str = val_str[h_idx:][1:]
        h_parts = h_str.split(split_char)
        
        if len(h_parts) > 5:
            seg = list(h_parts[5])
            key = list(f_str)
            
            for c in range(len(seg)):
                g = c
                for d in range(c, len(key)):
                    g += int(key[d])
                
                g = g % len(seg)
                
                seg[c], seg[g] = seg[g], seg[c]
                
            h_parts[5] = "".join(seg)
            return "/".join(h_parts)
            
        return None

    def resolve(self, url):
        UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        
        try:
            import cloudscraper
            scraper = cloudscraper.create_scraper(browser={'custom': UA})
            r = scraper.get(url, timeout=15)
            html = r.text
            self.logger.info(f"[GoPorn] Page Fetch Status: {r.status_code}")
        except Exception as e:
            self.logger.error(f"[GoPorn] Pre-resolve failed: {e}")
            return None

        video_url = None
        video_id = None
        
        flashvars = {}
        flashvars_match = re.search(r'var flashvars = ({.*?});', html, re.DOTALL)
        if flashvars_match:
            fv_json = flashvars_match.group(1)
            
            for line in fv_json.split(','):
                kv = line.strip()
                m_kv = re.search(r"(['\"]?)([a-zA-Z0-9_]+)\1\s*:\s*['\"](.*?)['\"]", kv)
                if m_kv:
                    flashvars[m_kv.group(2)] = m_kv.group(3)
            
            video_url = flashvars.get('video_url')
            video_id = flashvars.get('video_id')

        if not video_url:
             mp4_match = re.search(r"video_url:\s*'([^']+\.mp4[^']*)'", html)
             if mp4_match: video_url = mp4_match.group(1)
        
        license_code = flashvars.get('license_code', '')
        if video_url and video_url.startswith('function/'):
            try:
                decoded_url = kvs_decode_url(video_url, license_code)
                if decoded_url and decoded_url != video_url:
                    video_url = decoded_url
                else:
                    parts = video_url.split('/')
                    if 'https:' in parts:
                        idx = parts.index('https:')
                        video_url = "/".join(parts[idx:])
            except Exception:
                parts = video_url.split('/')
                if 'https:' in parts:
                    idx = parts.index('https:')
                    video_url = "/".join(parts[idx:])


        if video_url:
             rnd_ms = str(int(time.time() * 1000))
             video_url = re.sub(r'[&?]rnd=\d+', '', video_url)
             sep = "&" if "?" in video_url else "?"
             if "br=" not in video_url:
                 video_url += f"{sep}br=9"
                 sep = "&"
             video_url += f"{sep}rnd={rnd_ms}"
             
             self.logger.info(f"[GoPorn] Resolved URL: {video_url}")
             
             try:
                 from resources.lib.proxy_utils import ProxyController, PlaybackGuard
                 import xbmc
                 
                 proxy_scraper = cloudscraper.create_scraper(browser={'custom': UA})
                 proxy_scraper.headers.update({
                    'User-Agent': UA,
                    'Accept': '*/*'
                 })
                 


                 ctrl = ProxyController(video_url, session=proxy_scraper)
                 proxy_url = ctrl.start()
                 self.logger.info(f"[GoPorn] Proxy started at: {proxy_url}")
                 
                 monitor = xbmc.Monitor()
                 player = xbmc.Player()
                 guard = PlaybackGuard(player, monitor, proxy_url, ctrl)
                 guard.start()
                 
                 return proxy_url
                 
             except Exception as e:
                 self.logger.error(f"[GoPorn] Proxy failed: {e}")
                 return f"{video_url}|User-Agent={urllib.parse.quote(UA)}&Referer={urllib.parse.quote(url)}"

        self.logger.error("[GoPorn] Failed to extract video_url")
        return None

    def play_video(self, url):
        import xbmcgui
        import xbmcplugin
        
        xbmc.log(f"[GoPorn] Playing video: {url}", xbmc.LOGINFO)
        video_url = self.resolve(url)
        
        if video_url:
            xbmc.log(f"[GoPorn] Resolved to: {video_url}", xbmc.LOGINFO)
            li = xbmcgui.ListItem(path=video_url)
            li.setProperty('IsPlayable', 'true')
            li.setMimeType('video/mp4')
            li.setContentLookup(False)
            xbmcplugin.setResolvedUrl(self.addon_handle, True, li)
        else:
            xbmc.log("[GoPorn] Resolution failed", xbmc.LOGERROR)
            self.notify_error("Could not resolve video")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
