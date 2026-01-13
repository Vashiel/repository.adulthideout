
import sys, os, re, urllib.parse, html
import xbmc, xbmcgui, xbmcplugin, xbmcaddon
from resources.lib.base_website import BaseWebsite

try:
    addon_path = xbmcaddon.Addon().getAddonInfo('path')
    vendor_path = os.path.join(addon_path, 'resources', 'lib', 'vendor')
    if vendor_path not in sys.path: sys.path.insert(0, vendor_path)
except: pass

import requests

class CrazyshitWebsite(BaseWebsite):
    def __init__(self, addon_handle):
        super().__init__(name='crazyshit', base_url='https://crazyshit.com', search_url='https://crazyshit.com/search/?query={}', addon_handle=addon_handle)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
            'Referer': self.base_url,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8'
        })

    def make_request(self, url):
        try:
            r = self.session.get(urllib.parse.quote(url, safe=':/?=&%'), timeout=15)
            r.raise_for_status()
            return r.text
        except: return None

    def process_content(self, url):
        if self.addon.getSetting("show_crazyshit") == 'true' and self.addon.getSetting('crazyshit_disclaimer_accepted') != 'true':
            if not xbmcgui.Dialog().yesno("CrazyShit Content Warning", "WARNING: Extreme, violent, and disturbing content.\n\nViewing is at your own risk. Do you wish to proceed?"):
                self.addon.setSetting("show_crazyshit", 'false')
                xbmcgui.Dialog().notification("Access Denied", "Disabled.", xbmcgui.NOTIFICATION_INFO, 5000)
                self.end_directory()
                return
            self.addon.setSetting('crazyshit_disclaimer_accepted', 'true')

        url = f'{self.base_url}/videos/' if not url or url == "BOOTSTRAP" else url
        content = self.make_request(url)
        self.add_dir('[COLOR blue]Search[/COLOR]', '', 5, self.icons['search'])
        self.add_dir('Categories', f'{self.base_url}/categories/', 8, self.icons['categories'])

        if content:
            if '/categories/' in url: self.parse_category_list(content)
            else: self.parse_video_list(content)
            
            next_p = re.search(r'<a href="([^"]+)" class="plugurl" title="next page">next</a>', content) or re.search(r'<div class="prevnext">.*?<a href="([^"]+)"[^>]*>next</a>', content)
            if next_p:
                self.add_dir('[COLOR blue]Next Page >>>>[/COLOR]', urllib.parse.urljoin(self.base_url, html.unescape(next_p.group(1))), 2, self.icons['default'], self.fanart)
        self.end_directory()

    def process_categories(self, url):
        content = self.make_request(url)
        if content:
            self.add_dir('[COLOR blue]Search[/COLOR]', '', 5, self.icons['search'])
            self.parse_category_list(content)
            next_p = re.search(r'<a href="([^"]+)" class="plugurl" title="next page">next</a>', content) or re.search(r'<div class="prevnext">.*?<a href="([^"]+)"[^>]*>next</a>', content)
            if next_p:
                self.add_dir('[COLOR blue]Next Page >>>>[/COLOR]', urllib.parse.urljoin(self.base_url, html.unescape(next_p.group(1))), 2, self.icons['default'], self.fanart)
        self.end_directory()

    def parse_video_list(self, content):
        for url, title, thumb in re.findall(r'<a href="([^"]+)" title="([^"]+)"\s+class="thumb">.*?<img src="([^"]+)" alt="[^"]+" class="image-thumb"', content, re.DOTALL):
            title = html.unescape(title.strip())
            if '/cnt/medias/' in url:
                self.add_link(title, url, 4, thumb, self.fanart)
            elif '/series/' in url:
                self.add_dir(title, urllib.parse.urljoin(self.base_url, url), 2, thumb, self.fanart)
            elif '/categories/' in url:
                 self.add_dir(title, urllib.parse.urljoin(self.base_url, url), 8, thumb, self.fanart)

    def parse_category_list(self, content):
        for url, name, thumb in re.findall(r'<a href="([^"]+)" title="([^"]+)" class="thumb"[^>]*>.*?<div class="image-container">.*?<img src="([^"]+)" alt="[^"]+" class="image-thumb"', content, re.DOTALL):
            self.add_dir(html.unescape(name.strip()), urllib.parse.urljoin(self.base_url, url), 2, thumb, self.fanart)

    def play_video(self, url):
        content = self.make_request(url)
        if content:
            m = re.search(r'<source src="([^"]+)" type="video/mp4">', content) or re.search(r'<video.*?src="([^"]+)"', content)
            if m:
                li = xbmcgui.ListItem(path=html.unescape(m.group(1)))
                li.setProperty('IsPlayable', 'true')
                li.setMimeType('video/mp4')
                xbmcplugin.setResolvedUrl(self.addon_handle, True, li)
                return
        self.notify_error("Video not found.")