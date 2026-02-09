import sys
import os
import re
import urllib.parse
import urllib.request
import xbmc
import xbmcgui
import xbmcplugin
import xbmcvfs
import xbmcaddon
import json

try:
    addon_path = xbmcaddon.Addon().getAddonInfo('path')
    vendor_path = os.path.join(addon_path, 'resources', 'lib', 'vendor')
    if vendor_path not in sys.path:
        sys.path.insert(0, vendor_path)
except Exception:
    pass

try:
    import cloudscraper
    _HAS_CF = True
except ImportError:
    _HAS_CF = False

from resources.lib.base_website import BaseWebsite
from resources.lib.decoders.kvs_decoder import kvs_decode_url
from resources.lib.proxy_utils import ProxyController, PlaybackGuard

class BoundHub(BaseWebsite):
    NAME = "BoundHub"
    BASE_URL = "https://www.boundhub.com/"
    SEARCH_URL = BASE_URL + "search/%s/"
    CATEGORIES_URL = BASE_URL + "categories/"

    sort_options = ['Latest', 'Top Rated', 'Most Viewed']
    sort_paths = {
        'Latest': 'latest-updates/',
        'Top Rated': 'top-rated/',
        'Most Viewed': 'most-popular/'
    }

    def __init__(self, addon_handle):
        super(BoundHub, self).__init__(
            name="boundhub",
            base_url=self.BASE_URL,
            search_url=self.SEARCH_URL,
            addon_handle=addon_handle
        )
    
    def get_headers(self):
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
            "Referer": self.BASE_URL,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7"
        }

    def make_request(self, url):
        try:
            headers = self.get_headers()
            if _HAS_CF:
                scraper = cloudscraper.create_scraper(browser={'custom': headers['User-Agent']})
                r = scraper.get(url, headers=headers, timeout=20)
                return r.text
            else:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=15) as response:
                    return response.read().decode('utf-8')
        except Exception as e:
            xbmc.log(f"BoundHub: Request error: {e}", xbmc.LOGERROR)
            return None

    def resolve(self, url):
        xbmc.log(f"BoundHub: Resolving {url}", xbmc.LOGINFO)
        headers = self.get_headers()
            
        try:
            if _HAS_CF:
                scraper = cloudscraper.create_scraper(browser={'custom': headers['User-Agent']})
                r = scraper.get(url, headers=headers, timeout=20)
                html = r.text
                cookies = scraper.cookies.get_dict()
            else:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=15) as response:
                    html = response.read().decode('utf-8')
                cookies = {}
            
            if not html:
                return None
            
            video_url_match = re.search(r"video_url\s*:\s*[\'\\\"']([^\'\\\"]+)[\'\\\"']", html)
            license_match = re.search(r"license_code\s*:\s*[\'\\\"']([^\'\\\"]+)[\'\\\"']", html)
            
            if video_url_match:
                video_url = video_url_match.group(1)
                xbmc.log(f"BoundHub: Extracted KVS URL: {video_url}", xbmc.LOGINFO)
                
                if not video_url.startswith('http') and license_match:
                    license_code = license_match.group(1)
                    xbmc.log(f"BoundHub: Found encrypted URL, decoding with KVS...", xbmc.LOGINFO)
                    video_url = kvs_decode_url(video_url, license_code)
                    xbmc.log(f"BoundHub: Decoded URL: {video_url}", xbmc.LOGINFO)
                
                if not video_url or not video_url.startswith('http'):
                    flashvars_match = re.search(r'flashvars\s*=\s*({.*?});', html, re.DOTALL)
                    if flashvars_match:
                        try:
                            data = json.loads(flashvars_match.group(1))
                            if 'video_url' in data:
                                v = data['video_url']
                                l = data.get('license_code')
                                video_url = kvs_decode_url(v, l) if l else v
                        except:
                            pass
                
                if video_url and video_url.startswith('http'):
                    ua = urllib.parse.quote(headers['User-Agent'])
                    referer = urllib.parse.quote(url)
                    origin = urllib.parse.quote('https://www.boundhub.com')
                    cookie_str = "; ".join([f"{k}={v}" for k, v in cookies.items()])
                    cookie_encoded = urllib.parse.quote(cookie_str) if cookie_str else ""
                    
                    kodi_url = f"{video_url}|User-Agent={ua}&Referer={referer}&Origin={origin}"
                    if cookie_encoded:
                        kodi_url += f"&Cookie={cookie_encoded}"
                    
                    xbmc.log(f"BoundHub: Resolved to {kodi_url[:100]}...", xbmc.LOGINFO)
                    return kodi_url

            source_match = re.search(r'<source src="([^"]+)" type="video/mp4"', html)
            if source_match:
                video_url = source_match.group(1)
                xbmc.log(f"BoundHub: Extracted Source URL: {video_url}", xbmc.LOGINFO)
                ua = urllib.parse.quote(headers['User-Agent'])
                referer = urllib.parse.quote(url)
                origin = urllib.parse.quote('https://www.boundhub.com')
                cookie_str = "; ".join([f"{k}={v}" for k, v in cookies.items()])
                cookie_encoded = urllib.parse.quote(cookie_str) if cookie_str else ""
                
                kodi_url = f"{video_url}|User-Agent={ua}&Referer={referer}&Origin={origin}"
                if cookie_encoded:
                    kodi_url += f"&Cookie={cookie_encoded}"
                return kodi_url
                
        except Exception as e:
            xbmc.log(f"BoundHub Resolve Error: {e}", xbmc.LOGERROR)
            import traceback
            traceback.print_exc()
            
        return None

    def get_listing(self, url):
        xbmc.log(f"BoundHub: Fetching listing {url}", xbmc.LOGINFO)
        html = self.make_request(url)

        if not html:
            xbmc.log("BoundHub: No HTML content received.", xbmc.LOGERROR)
            return []
            
        xbmc.log(f"BoundHub: Got HTML content ({len(html)} bytes)", xbmc.LOGINFO)
        
        debug_path = xbmcvfs.translatePath('special://temp/boundhub_listing.html')
        with open(debug_path, 'w', encoding='utf-8') as f:
            f.write(html)

        items = []
        item_pattern = re.compile(r'<div class=\"item\s*[^\"]*\">', re.DOTALL)
        starts = [m.start() for m in item_pattern.finditer(html)]
        xbmc.log(f"BoundHub: Found {len(starts)} item blocks.", xbmc.LOGINFO)
        
        for i, start in enumerate(starts):
            end = starts[i+1] if i+1 < len(starts) else len(html)
            block = html[start:end]
            
            try:
                link_m = re.search(r'<a[^>]+href=\"([^\"]+)\"[^>]*title=\"([^\"]+)\"', block)
                if not link_m:
                    continue
                    
                link = link_m.group(1)
                title = link_m.group(2).strip()
                
                thumb_m = re.search(r'data-original=\"([^\"]+)\"', block)
                if not thumb_m:
                    thumb_m = re.search(r'src=\"([^\"]+)\"', block)
                thumb = thumb_m.group(1) if thumb_m else ""
                
                dur_m = re.search(r'<div class=\"duration\">([^<]+)</div>', block)
                duration = dur_m.group(1).strip() if dur_m else ""
                
                if not link.startswith('http'):
                    link = urllib.parse.urljoin(self.BASE_URL, link)
                if thumb and not thumb.startswith('http'):
                    thumb = urllib.parse.urljoin(self.BASE_URL, thumb)
                    
                items.append({
                    'title': title,
                    'url': link,
                    'thumb': thumb,
                    'duration': duration
                })
            except Exception as e:
                xbmc.log(f"BoundHub: Error parsing item chunk {i}: {e}", xbmc.LOGWARNING)

        return items

    def search(self, query):
        if not query: 
            return
        q = query.replace(' ', '+')
        url = urllib.parse.urljoin(self.BASE_URL, f'/search/{q}/')
        self.process_content(url)

    def process_content(self, url):
        if url and ('categories' in url or 'channels' in url):
            if 'videos' not in url:
                if url.rstrip('/').endswith('categories') or '/categories/page' in url:
                    self.add_basic_dirs(show_categories=False)
                    self.process_categories(url)
                    return

        self.add_basic_dirs(show_categories=True)
            
        if url == "sort_menu":
            self.end_directory()
            return

        items = self.get_listing(url)
        for item in items:
            title = item['title']
            if item.get('duration'):
                title = f"{title} ({item['duration']})"
            self.add_link(title, item['url'], 4, item.get('thumb', self.icon), self.fanart)
            
        try:
            debug_path = xbmcvfs.translatePath('special://temp/boundhub_listing.html')
            with open(debug_path, 'r', encoding='utf-8') as f:
                html = f.read()
                
            if re.search(r'class=\"next\"', html) or re.search(r'>\s*Next\s*<', html, re.IGNORECASE):
                next_url = None
                match_page = re.search(r'/(\d+)/?$', url)
                if match_page:
                    current_page = int(match_page.group(1))
                    next_page = current_page + 1
                    next_url = re.sub(r'/(\d+)/?$', f"/{next_page}/", url)
                else:
                    next_url = url + "2/" if url.endswith('/') else url + "/2/"
                
                if next_url:
                    self.add_dir('[COLOR blue]Next Page >>>>[/COLOR]', next_url, 2, self.icons.get('default'), self.fanart)
        except:
            pass

        self.end_directory()

    def add_basic_dirs(self, show_categories=True):
        self.add_dir('Search', "", mode=5, icon=self.icons.get('search'), fanart=self.fanart)
        if show_categories:
            self.add_dir('Categories', self.CATEGORIES_URL, mode=8, icon=self.icons.get('categories'), fanart=self.fanart)

    def process_categories(self, url):
        self.add_basic_dirs(show_categories=False)
        xbmc.log(f"BoundHub: Fetching Categories {url}", xbmc.LOGINFO)
        html = self.make_request(url)

        if not html:
            xbmc.log("BoundHub: No Categories HTML content.", xbmc.LOGERROR)
            return

        xbmc.log(f"BoundHub: Got Categories HTML content ({len(html)} bytes)", xbmc.LOGINFO)

        debug_path = xbmcvfs.translatePath('special://temp/boundhub_categories.html')
        with open(debug_path, 'w', encoding='utf-8') as f:
            f.write(html)
        
        pattern = r'<a\s+class="item[^"]*"\s+href="([^"]+)"\s+title="([^"]+)"[^>]*>.*?<img\s+[^>]*src="([^"]+)"'
        pattern_lazy = r'<a\s+class="item[^"]*"\s+href="([^"]+)"\s+title="([^"]+)"[^>]*>.*?<img\s+[^>]*data-original="([^"]+)"'
        
        matches = re.findall(pattern, html, re.DOTALL)
        if not matches:
            matches = re.findall(pattern_lazy, html, re.DOTALL)
             
        for link, title, thumb in matches:
            if not link.startswith('http'): 
                link = urllib.parse.urljoin(self.BASE_URL, link)
            if not thumb.startswith('http'): 
                thumb = urllib.parse.urljoin(self.BASE_URL, thumb)
            self.add_dir(title, link, 2, thumb, self.fanart)
        
        if re.search(r'class=\"next\"', html) or re.search(r'>\s*Next\s*<', html, re.IGNORECASE) or re.search(r'class=\"pagination\"', html):
            next_url = None
            match_page = re.search(r'/(\d+)/?$', url)
            if match_page:
                current_page = int(match_page.group(1))
                next_page = current_page + 1
                next_url = re.sub(r'/(\d+)/?$', f"/{next_page}/", url)
            else:
                next_url = url + "2/" if url.endswith('/') else url + "/2/"
                 
            if next_url:
                self.add_dir('[COLOR blue]Next Page >>>>[/COLOR]', next_url, 8, self.icons.get('default'), self.fanart)
             
        self.end_directory()

    def play_video(self, url):
        xbmc.log(f"BoundHub: Playing video {url}", xbmc.LOGINFO)
        headers = self.get_headers()
        
        try:
            if _HAS_CF:
                scraper = cloudscraper.create_scraper(browser={'custom': headers['User-Agent']})
                r = scraper.get(url, headers=headers, timeout=20)
                html = r.text
            else:
                self.notify_error("Cloudscraper required for BoundHub")
                xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
                return
            
            if not html:
                self.notify_error("Failed to load video page")
                xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
                return
            
            video_url = None
            video_url_match = re.search(r"video_url\s*:\s*['\\\"]([^'\\\"]+)['\\\"]" , html)
            if video_url_match:
                video_url = video_url_match.group(1)
                xbmc.log(f"BoundHub: Extracted video URL: {video_url}", xbmc.LOGINFO)
                
                if not video_url.startswith('http'):
                    license_match = re.search(r"license_code\s*:\s*['\\\"]([^'\\\"]+)['\\\"]" , html)
                    if license_match:
                        video_url = kvs_decode_url(video_url, license_match.group(1))
            
            if not video_url or not video_url.startswith('http'):
                source_match = re.search(r'<source src="([^"]+)" type="video/mp4"', html)
                if source_match:
                    video_url = source_match.group(1)
            
            if not video_url:
                self.notify_error("No video URL found")
                xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
                return
            
            xbmc.log(f"BoundHub: Using proxy for: {video_url}", xbmc.LOGINFO)
            
            try:
                ctrl = ProxyController(
                    video_url,
                    {'Referer': url, 'User-Agent': headers['User-Agent']},
                    cookies=scraper.cookies,
                    session=scraper,
                    host="127.0.0.1",
                    port=0
                )
                local_url = ctrl.start()
                xbmc.log(f"BoundHub: Proxy started at: {local_url}", xbmc.LOGINFO)
            except Exception as e:
                xbmc.log(f"BoundHub: Proxy failed: {e}", xbmc.LOGERROR)
                self.notify_error(f"Proxy failed: {e}")
                xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
                return
            
            li = xbmcgui.ListItem(path=local_url)
            li.setProperty('IsPlayable', 'true')
            li.setMimeType('video/mp4')
            li.setContentLookup(False)
            xbmcplugin.setResolvedUrl(self.addon_handle, True, li)
            
            try:
                monitor = xbmc.Monitor()
                player = xbmc.Player()
                guard = PlaybackGuard(player, monitor, local_url, ctrl, idle_timeout=60*60)
                guard.start()
            except Exception:
                pass
                
        except Exception as e:
            xbmc.log(f"BoundHub play_video Error: {e}", xbmc.LOGERROR)
            self.notify_error(f"Playback error: {e}")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())

