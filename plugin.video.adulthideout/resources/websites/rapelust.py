
import sys
import os
import re
import urllib.parse
import json
import html as html_module
import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon
from resources.lib.base_website import BaseWebsite

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

class Rapelust(BaseWebsite):
    NAME = "Rapelust"
    BASE_URL = "https://rapelust.com/"
    SEARCH_URL = BASE_URL + "?s=%s"
    
    sort_options = ['Date', 'Views', 'Likes']
    sort_paths = {
        'Date': '',
        'Views': '?sortby=post_views_count',
        'Likes': '?sortby=votes_count'
    }

    def __init__(self, addon_handle, addon=None):
        xbmc.log("Rapelust: Instantiating class...", xbmc.LOGINFO)
        super(Rapelust, self).__init__(self.NAME, self.BASE_URL, self.SEARCH_URL, addon_handle, addon=addon)

    def get_headers(self):
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": self.BASE_URL,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
    
    def make_request(self, url, method='GET', data=None, headers=None):
        xbmc.log(f"Rapelust: make_request url={url}", xbmc.LOGINFO)
        if not headers:
            headers = self.get_headers()
            
        try:
            if _HAS_CF:
                scraper = cloudscraper.create_scraper(browser={'custom': headers['User-Agent']})
                if method == 'GET':
                    r = scraper.get(url, headers=headers, timeout=20)
                else:
                    r = scraper.post(url, data=data, headers=headers, timeout=20)
                return r
            else:
                xbmc.log("Rapelust: Cloudscraper missing", xbmc.LOGERROR)
                return None
        except Exception as e:
            xbmc.log(f"Rapelust Request Error: {e}", xbmc.LOGERROR)
            return None

    def get_listing(self, url):
        return self.process_content(url)

    def process_content(self, url):
        if url == "SEARCH":
             self.show_search_menu()
             return
             
        self.add_dir("Search", "SEARCH", 5, self.icons['search'])
             
        r = self.make_request(url)
        if not r: return
        html = r.text
        
        items = []
        pattern = r'class=["\']videoPost["\'][^>]*>.*?class=["\']thumbDuration["\'][^>]*>([^<]+)</div>.*?<a[^>]+href=["\']([^"\']+)["\'][^>]*>.*?<img[^>]+src=["\']([^"\']+)["\'][^>]*>.*?class=["\']videoLink["\'][^>]*>([^<]+)</a>'
        matches = re.finditer(pattern, html, re.DOTALL | re.IGNORECASE)
        
        for match in matches:
            duration, link, thumb, title = match.groups()
            self.add_link(f"[COLOR blue]{duration.strip()}[/COLOR] {title.strip()}", link, 4, thumb, self.fanart)
            items.append(link)

        if items:
            page_match = re.search(r'/page/(\d+)/', url)
            current_page = int(page_match.group(1)) if page_match else 1
            next_page = current_page + 1
            
            if 'next page-numbers' in html or f'/page/{next_page}/' in html:
                 if page_match:
                     next_url = re.sub(r'/page/\d+/', f'/page/{next_page}/', url)
                 else:
                     if '?' in url:
                         parts = url.split('?')
                         next_url = f"{parts[0]}page/{next_page}/?{parts[1]}"
                     else:
                         next_url = url.rstrip('/') + f'/page/{next_page}/'
                 
                 self.add_dir("[COLOR green]Next Page >>[/COLOR]", next_url, 2, self.icons['default'])

        self.end_directory()

    def resolve(self, url):
        xbmc.log(f"Rapelust: Resolving {url}", xbmc.LOGINFO)
        r = self.make_request(url)
        if not r: return None
        html_content = r.text
        
        video_url = None
        
        data_item_match = re.search(r'data-item=["\']([^"\']+)["\']', html_content)
        if not data_item_match:
            data_item_match = re.search(r'data-item="([^"]*(?:&quot;|&#34;)[^"]*)"', html_content)
        
        if data_item_match:
            try:
                raw_data = data_item_match.group(1)
                decoded_data = html_module.unescape(raw_data)
                data = json.loads(decoded_data)
                if 'sources' in data and len(data['sources']) > 0:
                    video_url = data['sources'][0].get('src')
                    xbmc.log(f"Rapelust: Found via data-item: {video_url}", xbmc.LOGINFO)
            except Exception as e:
                xbmc.log(f"Rapelust: JSON parse error: {e}", xbmc.LOGWARNING)

        if not video_url:
            mp4_match = re.search(r'(https?://[^\s"\'<>]+\.mp4)', html_content)
            if mp4_match:
                video_url = mp4_match.group(1)
                xbmc.log(f"Rapelust: Found raw MP4: {video_url}", xbmc.LOGINFO)

        if video_url:
             headers = self.get_headers()
             return f"{video_url}|User-Agent={urllib.parse.quote(headers['User-Agent'])}&Referer={urllib.parse.quote(self.BASE_URL)}"
             
        return None

    def play_video(self, url):
        video_url = self.resolve(url)
        if video_url:
            li = xbmcgui.ListItem(path=video_url)
            li.setProperty('IsPlayable', 'true')
            xbmcplugin.setResolvedUrl(self.addon_handle, True, li)
        else:
            self.notify_error("Video resolution failed")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
