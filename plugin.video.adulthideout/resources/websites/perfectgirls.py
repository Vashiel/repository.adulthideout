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

try:
    import xbmcaddon
    addon_path = xbmcaddon.Addon().getAddonInfo('path')
    vendor_path = os.path.join(addon_path, 'resources', 'lib', 'vendor')
    if vendor_path not in sys.path:
        sys.path.insert(0, vendor_path)
except Exception:
    pass

import cloudscraper

class PerfectGirls(BaseWebsite):
    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="perfectgirls",
            base_url="https://www.perfectgirls.xxx",
            search_url="https://www.perfectgirls.xxx/search/{}/?sort={}",
            addon_handle=addon_handle,
            addon=addon
        )
        self.sort_options = [
            "Latest",
            "Popular",
            "Trending"
        ]
        self.sort_paths = {
            "Latest": "",
            "Popular": "popular/",
            "Trending": "trending/"
        }
        
        self.categories = [
            ("Teen", "teen"),
            ("Amateur", "amateur"),
            ("Solo", "solo"),
            ("Blowjob", "blowjob"),
            ("Compilation", "compilation"),
            ("MILF", "milf"),
            ("Creampie", "creampie"),
            ("Anal", "anal"),
            ("Big Tits", "big-tits"),
            ("Asian", "asian"),
            ("Lesbian", "lesbian"),
            ("Hardcore", "hardcore"),
            ("POV", "pov")
        ]
    
    def _get_sort_param(self):
        saved = self.addon.getSetting(f"{self.name}_sort_by")
        try:
            sort_idx = int(saved)
            opt = self.sort_options[sort_idx]
            return self.sort_paths[opt]
        except Exception:
            return ""

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
        cards = re.split(r'<div[^>]*class=["\'](?:[^"\']* )?thumb-video(?: [^"\']*)?["\'][^>]*>', html_content)[1:]
        
        for card in cards:
            # href
            href_m = re.search(r'<a[^>]*href=["\']([^"\']+)["\']', card, re.IGNORECASE)
            if not href_m: continue
            href = href_m.group(1)
            
            # thumbnail
            thumb = ""
            img_m = re.search(r'data-original=["\']([^"\']+)["\']', card, re.IGNORECASE)
            if img_m:
                thumb = img_m.group(1)
            else:
                img_m = re.search(r'data-src=["\']([^"\']+)["\']', card, re.IGNORECASE)
                if img_m:
                    thumb = img_m.group(1)
                else:
                    img_m2 = re.search(r'<img[^>]*src=["\']([^"\']+)["\']', card, re.IGNORECASE)
                    thumb = img_m2.group(1) if img_m2 else ""
            
            if thumb.startswith("//"):
                thumb = "https:" + thumb
                
            if "base64" in thumb:
                thumb = ""
                
            # title
            title = ""
            title_m = re.search(r'title=["\']([^"\']+)["\']', card, re.IGNORECASE)
            if title_m:
                title = title_m.group(1).strip()
            else:
                title_m2 = re.search(r'alt=["\']([^"\']+)["\']', card, re.IGNORECASE)
                title = title_m2.group(1).strip() if title_m2 else "Video"
            
            # duration
            dur_m = re.search(r'<span[^>]*class=["\']duration_item["\'][^>]*>(.*?)</span>', card, re.IGNORECASE | re.DOTALL)
            dur = f"[{dur_m.group(1).strip()}] " if dur_m else ""
            
            vid_url = self.base_url + href if href.startswith('/') else href
            
            # If the card is just a promo or redirect that shouldn't be matched
            if '/video/' not in vid_url:
                continue
                
            videos.append({
                'title': html.unescape(dur + title).strip(),
                'url': vid_url,
                'thumb': thumb or self.icons.get('default', self.icon)
            })
            
        next_url = None
        next_match = re.search(
            r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>\s*Next',
            html_content,
            re.IGNORECASE
        )
        if next_match:
            next_url = urllib.parse.urljoin(self.base_url, next_match.group(1))

        if videos and next_url:
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
                # URL is /search/slug/
                cat_url = f"{self.base_url}/search/{slug}/"
                self.add_dir(name, cat_url, 2, self.icons.get('categories', self.icon))
            self.end_directory("videos")
            return
            
        if url == "BOOTSTRAP":
            url = self.base_url + "/"

        videos = self.extract_videos(url)
        
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

    def play_video(self, url):
        scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False})
        try:
            self.logger.info(f"Extracting video from {url}")
            resp = scraper.get(url, timeout=10)
            html_content = resp.text
            
            # Extract video sources
            sources = re.findall(r'<source[^>]+src=["\']([^"\']+)["\'][^>]*title=["\'](.*?)["\']', html_content, re.IGNORECASE)
            
            if not sources:
                # Try without title
                sources_no_title = re.findall(r'<source[^>]+src=["\']([^"\']+)["\'][^>]*>', html_content, re.IGNORECASE)
                if sources_no_title:
                    sources = [(sources_no_title[0], 'Auto')]
            
            if not sources:
                self.logger.error("PerfectGirls get_file URL not found!")
                xbmcgui.Dialog().notification("PerfectGirls", "Video stream not found", xbmcgui.NOTIFICATION_ERROR)
                xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
                return
                
            resolutions = {}
            for src, title in sources:
                if src.startswith('//'):
                    src = 'https:' + src
                if not src.startswith('http'):
                    src = 'https://' + src
                res_val = 0
                if '1080' in title: res_val = 1080
                elif '720' in title: res_val = 720
                elif '480' in title: res_val = 480
                elif '360' in title: res_val = 360
                
                if 'Auto' not in title:
                    resolutions[res_val] = src
                else:
                    if -1 not in resolutions:
                        resolutions[-1] = src

            if resolutions:
                best_url = max(resolutions.items(), key=lambda x: x[0])[1]
            else:
                best_url = sources[0][0]
                if best_url.startswith('//'):
                    best_url = 'https:' + best_url

            self.logger.info(f"Resolved video URL: {best_url}")
            
            li = xbmcgui.ListItem(path=best_url)
            li.setProperty('IsPlayable', 'true')
            li.setMimeType('video/mp4')
            li.setContentLookup(False)
            
            xbmcplugin.setResolvedUrl(self.addon_handle, True, li)
            
        except Exception as e:
            self.logger.error(f"PLAYBACK ERROR: {e}")
            xbmcgui.Dialog().notification("PerfectGirls", f"Error: {e}", xbmcgui.NOTIFICATION_ERROR)
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())

