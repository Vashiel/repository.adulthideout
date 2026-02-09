import sys
import os
import re
import urllib.parse
import urllib.request
import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon
from resources.lib.base_website import BaseWebsite
from resources.lib.decoders.kvs_decoder import kvs_decode_url
from resources.lib.proxy_utils import ProxyController, PlaybackGuard

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

class Pervertium(BaseWebsite):
    NAME = 'pervertium'
    BASE_URL = "https://www.pervertium.com/"
    SEARCH_URL = "https://www.pervertium.com/search/{}/"
    
    RE_VIDEO_URL = re.compile(r'href="(?P<url>[^"]+/videos/\d+/[^"]*/?)"')
    RE_TITLE = re.compile(r'title="(?P<title>[^"]+)"')
    RE_TITLE_ALT = re.compile(r'<strong[^>]*>(?P<title>[^<]+)</strong>')
    RE_THUMB = re.compile(r'data-original="(?P<thumb>[^"]+)"')
    RE_DURATION = re.compile(r'(\d+:\d+)')
    RE_NEXT_PAGE = re.compile(r'<li[^>]*class="[^"]*next[^"]*"[^>]*>\s*<a[^>]+href="([^"]+)"', re.IGNORECASE)
    RE_NEXT_BTN = re.compile(r'<a[^>]+aria-label="next-btn"[^>]+href="([^"]+)"', re.IGNORECASE)
    RE_NEXT_TEXT = re.compile(r'<a[^>]+href="([^"]+)"[^>]*>\s*Next\s*</a>', re.IGNORECASE)
    RE_NEXT_PARAM = re.compile(r'<a[^>]+data-parameters="[^"]*from:(\d+)[^"]*"[^>]*>.*?icon-arr-right', re.IGNORECASE)
    RE_CAT_URL = re.compile(r'href="(?P<url>[^"]+/categories/[^"]*/?)"')
    
    def __init__(self, addon_handle, addon=None):
        super().__init__(self.NAME, self.BASE_URL, self.SEARCH_URL, addon_handle, addon=addon)
        self.sort_options = ["Latest Updates", "Most Popular", "Top Rated"]
        self.sort_paths = {
            "Latest Updates": "last-updates/",
            "Most Popular": "most-popular/",
            "Top Rated": "top-rated/"
        }

    def get_headers(self):
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Referer": self.BASE_URL,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5"
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
            xbmc.log(f"Pervertium: Request error: {e}", xbmc.LOGERROR)
            return None

    def play_video(self, url):
        xbmc.log(f"Pervertium: Playing video {url}", xbmc.LOGINFO)
        headers = self.get_headers()
        
        try:
            if _HAS_CF:
                xbmc.log("Pervertium: Creating cloudscraper...", xbmc.LOGINFO)
                scraper = cloudscraper.create_scraper(browser={'custom': headers['User-Agent']})
                r = scraper.get(url, headers=headers, timeout=20)
                html = r.text
                xbmc.log(f"Pervertium: Page loaded ({len(html)} bytes)", xbmc.LOGINFO)
            else:
                self.notify_error("Cloudscraper required")
                xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
                return
            
            if not html:
                self.notify_error("Failed to load video page")
                xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
                return
            
            video_url = None
            video_url_match = re.search(r'video_url\s*:\s*[\'"]([^\'"]+)[\'"]', html)
            if video_url_match:
                video_url = video_url_match.group(1)
                xbmc.log(f"Pervertium: Raw video URL match: {video_url}", xbmc.LOGINFO)
                
                if not video_url.startswith('http') or video_url.startswith('function/0/'):
                    license_match = re.search(r'license_code\s*:\s*[\'"]([^\'"]+)[\'"]', html)
                    if license_match:
                        video_url = kvs_decode_url(video_url, license_match.group(1))
                        xbmc.log(f"Pervertium: After KVS decode: {video_url}", xbmc.LOGINFO)
            
            if not video_url or not video_url.startswith('http'):
                source_match = re.search(r'<source src="([^"]+)" type="video/mp4"', html)
                if source_match:
                    video_url = source_match.group(1)
            
            if not video_url:
                self.notify_error("No video URL found")
                xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
                return
            
            xbmc.log(f"Pervertium: Proxying URL: {video_url}", xbmc.LOGINFO)
            
            controller = ProxyController(
                video_url, 
                upstream_headers=headers,
                session=scraper # Reuse scraper session containing cookies!
            )
            proxy_url = controller.start()
            
            monitor = xbmc.Monitor()
            player = xbmc.Player()
            guard = PlaybackGuard(player, monitor, proxy_url, controller)
            guard.start()
            
            xbmc.log(f"Pervertium: Proxy started at {proxy_url}", xbmc.LOGINFO)
            
            li = xbmcgui.ListItem(path=proxy_url)
            li.setProperty('IsPlayable', 'true')
            li.setMimeType('video/mp4')
            li.setContentLookup(False)
            xbmcplugin.setResolvedUrl(self.addon_handle, True, li)
                
        except Exception as e:
            xbmc.log(f"Pervertium play_video Error: {e}", xbmc.LOGERROR)
            self.notify_error(f"Playback error: {e}")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())

    def select_sort(self, original_url=None):
        import xbmcgui
        import xbmc
        current_sort = self.addon.getSetting('pervertium_sort_by')
        try:
            preselect_idx = self.sort_options.index(current_sort)
        except ValueError:
            preselect_idx = 0
        
        dialog = xbmcgui.Dialog()
        idx = dialog.select("Sort by...", self.sort_options, preselect=preselect_idx)
        if idx != -1:
            self.addon.setSetting('pervertium_sort_by', self.sort_options[idx])
            xbmc.executebuiltin('Container.Refresh')

    def get_start_url_and_label(self):
        current_sort = self.addon.getSetting('pervertium_sort_by')
        if current_sort not in self.sort_options:
            current_sort = "Latest Updates"
        sort_path = self.sort_paths.get(current_sort, "latest-updates/")
        return self.BASE_URL + sort_path, current_sort

    def process_content(self, url):
        xbmc.log(f"Pervertium: Processing URL: {url}", xbmc.LOGINFO)
        self.add_dir("Search", "SEARCH", 5, self.icons['search'])
        self.add_dir("Categories", self.BASE_URL + "categories/", 2, self.icons['categories'])
        
        if not url:
            url, _ = self.get_start_url_and_label()
        
        if "/categories/" in url and url.rstrip('/').endswith("/categories"):
            self.list_categories(url)
            return

        html = self.make_request(url)
        if not html:
            self.end_directory()
            return
        
        blocks = html.split('<div class="item')
        if len(blocks) > 1:
            blocks = blocks[1:]
        
        for block in blocks:
            url_match = self.RE_VIDEO_URL.search(block)
            if not url_match:
                continue
                
            video_url = url_match.group("url")
            if not video_url.startswith('http'):
                video_url = urllib.parse.urljoin(self.BASE_URL, video_url)
            
            title = ""
            title_match = self.RE_TITLE.search(block)
            if title_match:
                title = title_match.group("title").strip()
            
            if not title:
                title_match = self.RE_TITLE_ALT.search(block)
                if title_match:
                    title = title_match.group("title").strip()

            thumb = ""
            orig_match = self.RE_THUMB.search(block)
            if orig_match:
                thumb = orig_match.group("thumb")
                if not thumb.startswith('http'):
                    thumb = urllib.parse.urljoin(self.BASE_URL, thumb)

            dur_match = self.RE_DURATION.search(block)
            if dur_match:
                duration = dur_match.group(1).strip()
                title = f"[COLOR blue]{duration}[/COLOR] {title}"

            context_menu = [
                ('Sort by...', f'RunPlugin({sys.argv[0]}?mode=7&action=select_sort&website={self.name})')
            ]
            
            final_thumb = thumb if thumb else self.icons['default']
            self.add_link(title, video_url, 4, final_thumb, final_thumb, context_menu=context_menu)
        
        next_url = None
        next_match = self.RE_NEXT_PAGE.search(html)
        if not next_match:
            next_match = self.RE_NEXT_BTN.search(html)
        if not next_match:
            next_match = self.RE_NEXT_TEXT.search(html)
            
        if next_match:
            next_url = next_match.group(1)
            if not next_url.startswith('http'):
                next_url = urllib.parse.urljoin(self.BASE_URL, next_url)
        else:
            param_match = self.RE_NEXT_PARAM.search(html)
            if param_match:
                next_page = param_match.group(1)
                if "?" in url:
                    if "from=" in url:
                        next_url = re.sub(r'from=\d+', f'from={next_page}', url)
                    else:
                        next_url = f"{url}&from={next_page}"
                else:
                    if url.endswith('/'):
                        next_url = f"{url}?from={next_page}"
                    else:
                        next_url = f"{url}/?from={next_page}"
        
        if next_url:
            self.add_dir("[COLOR green]Next Page >>[/COLOR]", next_url, 2, self.icons['default'])
        
        self.end_directory()

    def resolve(self, url):
        html = self.make_request(url)
        if not html:
            return None
        
        video_url_match = re.search(r'video_url\s*:\s*[\'"]([^\'"]+)[\'"]', html)
        if not video_url_match:
            return None
        
        video_url = video_url_match.group(1)
        
        if video_url.startswith("function/0/"):
            video_url = video_url[len("function/0/"):]
        
        if not video_url.startswith('http'):
            license_match = re.search(r'license_code\s*:\s*[\'"]([^\'"]+)[\'"]', html)
            if license_match:
                license_code = license_match.group(1)
                video_url = kvs_decode_url(video_url, license_code)
        
        return video_url.rstrip('/')

    def FORMAT_SEARCH_QUERY(self, query):
        return urllib.parse.quote(query.strip().replace(' ', '-'))

    def list_categories(self, url):
        all_categories = []
        page = 1
        max_pages = 5
        
        while page <= max_pages:
            page_url = f"{self.BASE_URL}categories/{page}/" if page > 1 else f"{self.BASE_URL}categories/"
            html = self.make_request(page_url)
            if not html:
                break
            
            blocks = html.split('class="thumb"')[1:]
            for block in blocks:
                url_match = self.RE_CAT_URL.search(block)
                if not url_match:
                    continue
                
                cat_url = url_match.group("url")
                if not cat_url.startswith('http'):
                    cat_url = urllib.parse.urljoin(self.BASE_URL, cat_url)
                
                name = "Category"
                title_match = self.RE_TITLE.search(block)
                if title_match:
                    name = title_match.group("title").strip()
                elif 'thumb_string_nowrap' in block:
                    name_match = re.search(r'<span class="thumb_string_nowrap">([^<]+)</span>', block)
                    if name_match:
                        name = name_match.group(1).strip()
                
                thumb = ""
                orig_match = self.RE_THUMB.search(block)
                if orig_match:
                    thumb = orig_match.group("thumb")
                    if not thumb.startswith('http'):
                        thumb = urllib.parse.urljoin(self.BASE_URL, thumb)
                
                all_categories.append((name, cat_url, thumb))
            
            if not blocks or f'/categories/{page + 1}/' not in html:
                break
            page += 1
        
        for name, cat_url, thumb in all_categories:
            self.add_dir(name, cat_url, 2, thumb if thumb else self.icons['default'])
        
        self.end_directory()
