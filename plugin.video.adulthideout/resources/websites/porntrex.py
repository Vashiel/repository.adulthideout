import re
import urllib.parse
import json
import xbmcgui
import xbmcplugin
import xbmcaddon
import xbmc
import xbmcvfs
import sys
import os
import html
from resources.lib.base_website import BaseWebsite

try:
    addon_path = xbmcaddon.Addon().getAddonInfo('path')
    vendor_path = os.path.join(addon_path, 'resources', 'lib', 'vendor')
    if vendor_path not in sys.path:
        sys.path.insert(0, vendor_path)
except Exception:
    pass

import cloudscraper

class PornTrex(BaseWebsite):
    
    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="porntrex",
            base_url="https://www.porntrex.com",
            search_url="https://www.porntrex.com/search/{}/",
            addon_handle=addon_handle,
            addon=addon
        )
        self.scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True})
        self.scraper.cookies.set('kt_tpa_show_n', '1', domain='www.porntrex.com')
        
        self.logo = os.path.join(self.addon.getAddonInfo('path'), 'resources', 'logos', 'porntrex.png')
        self.icons['default'] = self.logo
        self.icons['search'] = os.path.join(self.addon.getAddonInfo('path'), 'resources', 'logos', 'search.png')
        self.icons['categories'] = os.path.join(self.addon.getAddonInfo('path'), 'resources', 'logos', 'categories.png')

    def make_request(self, url):
        try:
            self.logger.info(f"Requesting: {url}")
            response = self.scraper.get(url, timeout=15)
            if response.status_code == 200:
                return response.text
            else:
                self.logger.error(f"Request failed: {response.status_code}")
                return None
        except Exception as e:
            self.logger.error(f"Request error: {e}")
            return None

    def get_listing(self, url):
        html_content = self.make_request(url)
        if not html_content:
            return []

        videos = []
        item_pattern = r'<a[^>]*href=\"([^\"]*video/\d+/[^\"]*)\"[^>]*>.*?<img[^>]*data-src=\"([^\"]+)\"[^>]*alt=\"([^\"]+)\"'
        
        items = re.findall(item_pattern, html_content, re.DOTALL)
        
        for link, thumb, title in items:
            if link.startswith('//'):
                link = "https:" + link
            elif link.startswith('/'):
                link = self.base_url + link
                
            if thumb.startswith('//'):
                thumb = "https:" + thumb
                
            duration = ""
            dur_match = re.search(r'class=\"duration\"[^>]*>([\d:]+)</div>', html_content)

            videos.append({
                "title": html.unescape(title.strip()),
                "url": link,
                "thumb": thumb,
                "duration": duration
            })

        mx = re.search(r'<li[^>]+class="next"[^>]*>.*?<a[^>]+href="([^"]+)"', html_content, re.DOTALL)
        next_url = ""
        if mx:
            extracted_url = mx.group(1)
            if not extracted_url.startswith('#') and 'javascript' not in extracted_url:
                next_url = extracted_url
                if next_url.startswith('//'):
                    next_url = "https:" + next_url
                elif next_url.startswith('/'):
                    next_url = self.base_url + next_url

        if not next_url and len(videos) > 0:
            current_page = 1
            page_match = re.search(r'/search/[^/]+/(\d+)/', url)
            if not page_match:
                 page_match = re.search(r'/categories/[^/]+/(\d+)/', url)
            if not page_match:
                 page_match = re.search(r'/most-recent/(\d+)/', url)
            
            if page_match:
                current_page = int(page_match.group(1))
            
            next_page = current_page + 1

            if '/search/' in url:
                if re.search(r'/\d+/$', url):
                    next_url = re.sub(r'/\d+/$', f'/{next_page}/', url.rstrip('/') + '/')
                else:
                    next_url = url.rstrip('/') + f'/{next_page}/'
            elif '/categories/' in url:
                if re.search(r'/\d+/$', url):
                    next_url = re.sub(r'/\d+/$', f'/{next_page}/', url.rstrip('/') + '/')
                else:
                     next_url = url.rstrip('/') + f'/{next_page}/'
            else:
                if '/latest-updates/' in url:
                    next_url = re.sub(r'/\d+/$', f'/{next_page}/', url.rstrip('/') + '/')
                elif url == self.base_url or url == self.base_url + '/':
                    next_url = self.base_url + f"/latest-updates/{next_page}/"

        if next_url:
            icon = self.icons['default']
            next_icon_path = os.path.join(self.addon.getAddonInfo('path'), 'resources', 'logos', 'next.png')
            if os.path.exists(next_icon_path):
                 icon = next_icon_path

            videos.append({
                "title": "Next Page",
                "url": next_url,
                "type": "next_page",
                "icon": icon
            })

        return videos

    def get_categories(self):
        url = f"{self.base_url}/categories/"
        html_content = self.make_request(url)
        if not html_content:
            return []

        cats = []
        cat_pattern = r'<a[^>]*href=\"([^\"]*categories/[^\"]*)\"[^>]*>.*?<img[^>]*(?:src|data-src)=\"([^\"]+)\"[^>]*>.*?<(?:p|span)[^>]*>(.*?)</(?:p|span)>'
        
        items = re.findall(cat_pattern, html_content, re.DOTALL)
        for link, thumb, title in items:
            if link.startswith('//'):
                link = "https:" + link
            elif link.startswith('/'):
                link = self.base_url + link
                
            if thumb.startswith('//'):
                thumb = "https:" + thumb
            
            clean_title = re.sub(r'<[^>]+>', '', title).strip()
            
            cats.append({
                "title": html.unescape(clean_title),
                "url": link,
                "thumb": thumb
            })
            
        return cats

    def resolve(self, url):
        html_content = self.make_request(url)
        if not html_content:
            return None, None

        flashvars_match = re.search(r'var flashvars = (\{.*?\});', html_content, re.DOTALL)
        if flashvars_match:
            flashvars_str = flashvars_match.group(1)
            video_url_match = re.search(r"video_url:\s*['\"]([^'\"]+)['\"]", flashvars_str)
            if video_url_match:
                video_url = video_url_match.group(1)
                video_hd_match = re.search(r"video_hd_url:\s*['\"]([^'\"]+)['\"]", flashvars_str)
                if video_hd_match:
                    video_url = video_hd_match.group(1)
                
                return video_url, url

        return None, None

    def play_video(self, url):
        resolved_url, referer = self.resolve(url)
        if resolved_url:
            ua = self.scraper.headers.get('User-Agent', '')
            final_url = resolved_url + f"|User-Agent={urllib.parse.quote(ua)}&Referer={urllib.parse.quote(referer)}"
            
            li = xbmcgui.ListItem(path=final_url)
            li.setMimeType('video/mp4')
            li.setProperty('IsPlayable', 'true')
            xbmcplugin.setResolvedUrl(self.addon_handle, True, li)
        else:
            xbmcgui.Dialog().notification('AdultHideout', 'Could not resolve video URL', xbmcgui.NOTIFICATION_ERROR, 3000)
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())

    def process_content(self, url):
        if url == "categories":
            self.add_dir("Search", "", 5, self.icons['search'])
            cats = self.get_categories()
            for cat in cats:
                self.add_dir(cat['title'], cat['url'], 2, cat['thumb'])
            self.end_directory("videos")
            return

        videos = self.get_listing(url)
        
        self.add_dir("Search", "", 5, self.icons['search'])
        self.add_dir("Categories", "categories", 2, self.icons['categories'])

        for v in videos:
            if v.get('type') == 'next_page':
                self.add_dir(v['title'], v['url'], 2, v.get('icon', self.icons['default']))
            else:
                self.add_link(
                    name=v['title'],
                    url=v['url'],
                    mode=4,
                    icon=v.get('thumb'),
                    fanart=self.fanart,
                    info_labels={'plot': v['title']}
                )

        self.end_directory("videos")
