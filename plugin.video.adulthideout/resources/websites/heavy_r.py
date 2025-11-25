import sys
import os
import xbmcaddon
import xbmcgui
import xbmcplugin
import re
import urllib.parse
import urllib.request
import urllib.error
import http.cookiejar
import html
import ssl

# --------------------------------------------------------------------------------
# Vendor-Pfad
# --------------------------------------------------------------------------------
try:
    _addon = xbmcaddon.Addon()
    _addon_path = _addon.getAddonInfo('path')
    _vendor_path = os.path.join(_addon_path, 'resources', 'lib', 'vendor')
    if _vendor_path not in sys.path:
        sys.path.insert(0, _vendor_path)
except Exception:
    pass

try:
    import cloudscraper
    HAS_CLOUDSCRAPER = True
except ImportError:
    HAS_CLOUDSCRAPER = False

from resources.lib.base_website import BaseWebsite

class HeavyRWebsite(BaseWebsite):
    def __init__(self, addon_handle):
        super().__init__(
            name="heavy-r",
            base_url="https://www.heavy-r.com",
            search_url="https://www.heavy-r.com/index.php",
            addon_handle=addon_handle
        )
        self.sort_options = ["Recent Uploads", "Most Viewed", "Top Rated", "Recent Favorites"]
        self.sort_paths = {
            "Recent Uploads": "/videos/recent/",
            "Most Viewed": "/videos/most_viewed/",
            "Top Rated": "/videos/top_rated/",
            "Recent Favorites": "/videos/recent_favorites/"
        }
        self.categories_url = f"{self.base_url}/categories/"
        
        self.cookie_jar = http.cookiejar.CookieJar()
        
        # Regex für Videos
        self.video_pattern = re.compile(
            r'<div class="[^"]*video-item[^"]*">.*?<a href="([^"]+)"[^>]*class="image[^"]*">.*?<img[^>]+src="([^"]+)"[^>]*alt="([^"]+)"',
            re.DOTALL | re.IGNORECASE
        )
        # Regex für Kategorien (nur Link und Name, Bild ignorieren wir für Speed)
        self.category_pattern = re.compile(
            r'<div class="video-item category">.*?<a href="([^"]+)"[^>]*class="image[^"]*">.*?alt="([^"]+)"',
            re.DOTALL | re.IGNORECASE
        )
        
        self.next_page_pattern = re.compile(r'<a[^>]+href="([^"]+)"[^>]*>\s*Next\s*</a>', re.IGNORECASE)
        self.video_source_pattern = re.compile(r'<source[^>]+src=["\']([^"\']+\.mp4)["\']', re.IGNORECASE)

    def _get_mobile_headers(self):
        return {
            'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Referer': self.base_url + '/',
            'Connection': 'keep-alive'
        }

    def _fetch_with_urllib(self, url, post_data=None):
        try:
            headers = self._get_mobile_headers()
            data = None
            if post_data:
                data = urllib.parse.urlencode(post_data).encode('utf-8')
            
            req = urllib.request.Request(url, data=data, headers=headers)
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            
            opener = urllib.request.build_opener(
                urllib.request.HTTPCookieProcessor(self.cookie_jar),
                urllib.request.HTTPSHandler(context=ctx)
            )
            
            with opener.open(req, timeout=15) as response:
                return response.read().decode('utf-8', errors='ignore')
        except Exception:
            return None

    def make_request(self, url, method='GET', post_data=None):
        if HAS_CLOUDSCRAPER:
            try:
                scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'mobile': True})
                scraper.headers.update(self._get_mobile_headers())
                
                if method == 'POST':
                    response = scraper.post(url, data=post_data, timeout=15)
                else:
                    response = scraper.get(url, timeout=15)
                
                if response.status_code == 200:
                    return response.text
            except Exception:
                pass 

        return self._fetch_with_urllib(url, post_data)

    def process_content(self, url):
        if not url or url == "BOOTSTRAP":
            url = self.base_url
        
        self.add_basic_dirs(url)
        content = self.make_request(url)
        
        if content:
            self.parse_video_list(content, url)
            self.add_next_button(content)
        else:
            self.notify_error("Inhalt konnte nicht geladen werden")
        
        self.end_directory()

    def add_basic_dirs(self, current_url):
        encoded_url = urllib.parse.quote_plus(current_url)
        context_menu = [('Sort by...', f'RunPlugin({sys.argv[0]}?mode=7&website={self.name}&action=select_sort&original_url={encoded_url})')]
        self.add_dir('[COLOR blue]Search[/COLOR]', '', 5, self.icons['search'], context_menu=context_menu)
        self.add_dir('Categories', self.categories_url, 8, self.icons['categories'], context_menu=context_menu)

    def process_categories(self, url):
        content = self.make_request(url)
        
        if content:
            matches = self.category_pattern.findall(content)
            if not matches:
                self.notify_info("Keine Kategorien gefunden")
            
            # Speed-Optimierung: Keine Bilder für Kategorien!
            # Wir nutzen einfach das Standard-Icon.
            thumb = self.icons['categories']
            
            for link, name in matches:
                full_url = urllib.parse.urljoin(self.base_url, link)
                self.add_dir(html.unescape(name.strip()), full_url, 2, thumb, self.fanart)
                
            self.add_next_button(content)
            
        self.end_directory()

    def parse_video_list(self, content, current_url):
        matches = self.video_pattern.findall(content)
        if not matches: return

        for video_url, thumb_url, title in matches:
            full_video_url = urllib.parse.urljoin(self.base_url, video_url)
            full_thumb_url = urllib.parse.urljoin(self.base_url, thumb_url)
            
            # Nur einfache HTTPS-Korrektur, keine komplexen Rewrites mehr
            full_thumb_url = full_thumb_url.replace("http://", "https://")
            
            self.add_link(html.unescape(title.strip()), full_video_url, 4, full_thumb_url, self.fanart)

    def add_next_button(self, content):
        match = self.next_page_pattern.search(content)
        if match:
            next_url = urllib.parse.urljoin(self.base_url, match.group(1))
            self.add_dir('[COLOR blue]Next Page >>>>[/COLOR]', next_url, 2, self.icons['default'], self.fanart)

    def play_video(self, url):
        content = self.make_request(url)
        if not content: return

        match = self.video_source_pattern.search(content)
        if match:
            video_url = match.group(1)
            if video_url.startswith('//'):
                video_url = 'https:' + video_url
            elif video_url.startswith('/'):
                video_url = urllib.parse.urljoin(self.base_url, video_url)
            
            video_url = video_url.replace("https://", "http://")
            li = xbmcgui.ListItem(path=video_url)
            li.setProperty("IsPlayable", "true")
            li.setMimeType("video/mp4")
            xbmcplugin.setResolvedUrl(self.addon_handle, True, li)
        else:
            self.notify_error("Keine Videoquelle gefunden")

    def search(self, query):
        if not query: return
        post_data = {'keyword': query, 'handler': 'search', 'action': 'do_search'}
        content = self.make_request(self.search_url, method='POST', post_data=post_data)
        if content:
            self.add_basic_dirs(self.search_url)
            self.parse_video_list(content, self.search_url)
            self.add_next_button(content)
        self.end_directory()