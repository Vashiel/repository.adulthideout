# -*- coding: utf-8 -*-
import re
import urllib.parse
import sys
import os
import xbmc
import xbmcgui
import xbmcplugin
import html
from resources.lib.base_website import BaseWebsite
from resources.lib.proxy_utils import ProxyController

try:
    import xbmcaddon
    addon_path = xbmcaddon.Addon().getAddonInfo('path')
    vendor_path = os.path.join(addon_path, 'resources', 'lib', 'vendor')
    if vendor_path not in sys.path:
        sys.path.insert(0, vendor_path)
except Exception:
    pass

import cloudscraper

class FullPorner(BaseWebsite):
    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="fullporner",
            base_url="https://fullporner.com",
            search_url="https://fullporner.com/search/{}/?sort={}",
            addon_handle=addon_handle,
            addon=addon
        )
        self.sort_options = [
            "Latest",
            "Most Viewed",
            "Top Rated"
        ]
        self.sort_paths = {
            "Latest": "recent",
            "Most Viewed": "views",
            "Top Rated": "rating"
        }
        
        self.categories = [
            ("Amateur", "amateur"),
            ("Anal", "anal"),
            ("Asian", "asian"),
            ("Babe", "babe"),
            ("Big Ass", "big-ass"),
            ("Big Tits", "big-tits"),
            ("Blonde", "blonde"),
            ("Blowjob", "blowjob"),
            ("Brunette", "brunette"),
            ("Compilation", "compilation"),
            ("Creampie", "creampie"),
            ("Cumshot", "cumshot"),
            ("Double Penetration", "double-penetration"),
            ("Ebony", "ebony"),
            ("Hardcore", "hardcore"),
            ("Interracial", "interracial"),
            ("Latina", "latina"),
            ("Lesbian", "lesbian"),
            ("Masturbation", "masturbation"),
            ("Mature", "mature"),
            ("MILF", "milf"),
            ("POV", "pov"),
            ("Threesome", "threesome"),
            ("Teen", "teen")
        ]

    def _normalize_thumb(self, thumb):
        if not thumb:
            return self.icons.get('default', self.icon)

        thumb = html.unescape(thumb.strip())
        if thumb.startswith('//'):
            thumb = 'https:' + thumb
        elif thumb.startswith('/'):
            thumb = self.base_url + thumb
        elif thumb.startswith('aoshenke.net/'):
            thumb = 'https://' + thumb
        elif thumb.startswith('imgs.xiaoshenke.net/'):
            thumb = 'https://' + thumb

        thumb = re.sub(
            r'^https?://aoshenke\.net/thumb/(\d+)\.jpg$',
            r'https://imgs.xiaoshenke.net/thumb/\1.jpg',
            thumb,
            flags=re.IGNORECASE,
        )

        if thumb.startswith('http'):
            thumb += "|User-Agent=Mozilla%2F5.0&Referer=https%3A%2F%2Ffullporner.com%2F"
        return thumb
    
    def _get_sort_param(self):
        saved = self.addon.getSetting(f"{self.name}_sort_by")
        try:
            sort_idx = int(saved)
            opt = self.sort_options[sort_idx]
            return self.sort_paths[opt]
        except Exception:
            return "recent"

    def search(self, query):
        if not query: 
            return
        sort_param = self._get_sort_param()
        search_url = self.search_url.format(urllib.parse.quote_plus(query), sort_param)
        self.process_content(search_url)

    def extract_videos(self, url):
        scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False})
        try:
            self.logger.info(f"Fetching: {url}")
            resp = scraper.get(url, timeout=10)
            html_content = resp.text
        except Exception as e:
            self.logger.error(f"Error fetching {url}: {e}")
            return []
            
        videos = []
        cards = re.split(r'<div[^>]*class=["\']video-card-image["\'][^>]*>', html_content)[1:]
        
        for card in cards:
            chunk = card.split('video-view')[0] if 'video-view' in card else card
            
            href_match = re.search(r'href=["\'](/watch/[^"\']+)["\']', chunk, re.IGNORECASE)
            if not href_match: continue
            href = href_match.group(1)
            
            title_match = re.search(r'<div class=["\']video-title["\'][^>]*>\s*<a[^>]*>(.*?)</a>', chunk, re.DOTALL | re.IGNORECASE)
            title = title_match.group(1).strip() if title_match else ""
            
            if not title:
                alt_match = re.search(r'alt=["\']([^"\']+)["\']', chunk, re.IGNORECASE)
                title = alt_match.group(1) if alt_match else "Video"
                
            thumb = ""
            data_src = re.search(r'data-src=["\']([^"\']+)["\']', chunk, re.IGNORECASE)
            if data_src:
                thumb = data_src.group(1)
            else:
                src_match = re.search(r'src=["\']([^"\']+)["\']', chunk, re.IGNORECASE)
                if src_match and "blank.gif" not in src_match.group(1):
                    thumb = src_match.group(1)
            
            if href.startswith('/'): 
                href = self.base_url + href
            thumb = self._normalize_thumb(thumb)
            
            videos.append({
                'title': html.unescape(title).strip(),
                'url': href,
                'thumb': thumb
            })
            
        # Pagination
        if '?' in url:
            base_url_part, query = url.split('?', 1)
        else:
            base_url_part, query = url, ""
            
        base_url_part = base_url_part.rstrip('/')
        page_match = re.search(r'/(\d+)$', base_url_part)
        if page_match:
            current_page = int(page_match.group(1))
            base_without_page = base_url_part[:page_match.start()]
            next_page = current_page + 1
            next_url_part = f"{base_without_page}/{next_page}/"
        else:
            next_page = 2
            next_url_part = f"{base_url_part}/{next_page}/"
            
        if query:
            next_url = f"{next_url_part}?{query}"
        else:
            next_url = next_url_part
            
        if videos:
            videos.append({
                'title': 'Next Page',
                'url': next_url,
                'type': 'next_page',
                'icon': self.icons.get('default', self.icon)
            })
            
        return videos

    def process_content(self, url):
        if url == "categories":
            self.add_dir("Search", "", 5, self.icons.get('search', self.icon))
            for name, slug in self.categories:
                cat_url = f"{self.base_url}/category/{slug}/"
                self.add_dir(name, cat_url, 2, self.icons.get('categories', self.icon))
            self.end_directory("videos")
            return
            
        if url == "BOOTSTRAP":
            url = self.base_url + "/"

        videos = self.extract_videos(url)
        
        # KVAT requirement: Search, then Categories
        self.add_dir("Search", "", 5, self.icons.get('search', self.icon))
        self.add_dir("Categories", "categories", 2, self.icons.get('categories', self.icon))
        
        for v in videos:
            if v.get('type') == 'next_page':
                self.add_dir(v['title'], v['url'], 2, v['icon'])
            else:
                self.add_link(
                    name=v['title'],
                    url=v['url'],
                    mode=4,
                    icon=v['thumb'],
                    fanart=self.fanart,
                    info_labels={'plot': v['title']}
                )
        self.end_directory("videos")

    def _btq(self, f):
        if isinstance(f, str): 
            f = int(f)
        res = []
        if f & 1: res.append(360)
        if f & 2: res.append(480)
        if f & 4: res.append(720)
        if f & 8: res.append(1080)
        return res

    def play_video(self, url):
        scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False})
        try:
            self.logger.info(f"Extracting player from {url}")
            resp = scraper.get(url, timeout=10)
            html_content = resp.text
            
            iframe_match = re.search(r'src=["\'](//xiaoshenke\.net/video/([a-z0-9]+)/(\d+))["\']', html_content, re.IGNORECASE)
            if not iframe_match:
                self.logger.error("Xiaoshenke iframe not found!")
                xbmcgui.Dialog().notification("FullPorner", "Video not found", xbmcgui.NOTIFICATION_ERROR)
                xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
                return
                
            iframe_src = 'https:' + iframe_match.group(1)
            video_id = iframe_match.group(2)
            quality_flag = int(iframe_match.group(3))
            
            self.logger.info(f"Found iframe {iframe_src} with ID {video_id} and flag {quality_flag}")
            
            reversed_id = video_id[::-1]
            qualities = self._btq(quality_flag)
            
            if not qualities:
                self.logger.error(f"No valid qualities from boolean flag {quality_flag}")
                xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
                return
                
            best_q = max(qualities)
            stream_url = f"https://xiaoshenke.net/vid/{reversed_id}/{best_q}"
            
            self.logger.info(f"Resolved best stream URL: {stream_url}")
            
            proxy_headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': 'https://xiaoshenke.net/',
                'Accept': '*/*, video/mp4',
            }
            
            ctrl = ProxyController(
                upstream_url=stream_url,
                upstream_headers=proxy_headers,
                use_urllib=True
            )
            local_url = ctrl.start()
            
            self.logger.info(f"Proxy started at {local_url}")
            
            li = xbmcgui.ListItem(path=local_url)
            li.setProperty('IsPlayable', 'true')
            li.setMimeType('video/mp4')
            li.setContentLookup(False)
            
            xbmcplugin.setResolvedUrl(self.addon_handle, True, li)
            
            player = xbmc.Player()
            monitor = xbmc.Monitor()
            from resources.lib.proxy_utils import PlaybackGuard
            guard = PlaybackGuard(player, monitor, local_url, ctrl)
            guard.start()
            
        except Exception as e:
            self.logger.error(f"PLAYBACK ERROR: {e}")
            xbmcgui.Dialog().notification("FullPorner", f"Error: {e}", xbmcgui.NOTIFICATION_ERROR)
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
