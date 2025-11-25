#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Changelog:
# - Final release version
# - Added Categories (Top/Popular) and Models support
# - Fixed video playback (single quote support in source tag)
# - Added required Referer header to stream URL
# - Enabled sorting and pagination

import re
import sys
import urllib.parse
import urllib.request
import html
import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
import json
from resources.lib.base_website import BaseWebsite

class PornGoWebsite(BaseWebsite):
    def __init__(self, addon_handle):
        super().__init__(
            name='porngo',
            base_url='https://www.porngo.com',
            search_url='https://www.porngo.com/search/{}/',
            addon_handle=addon_handle
        )
        self.sort_options = ["Newest", "Top Rated", "Most Viewed"]
        self.sort_paths = {
            "Newest": "/latest-updates/",
            "Top Rated": "/top-rated/",
            "Most Viewed": "/most-popular/"
        }

    def get_headers(self):
        return {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Referer': self.base_url + '/'
        }

    def make_request(self, url):
        try:
            headers = self.get_headers()
            req = urllib.request.Request(url, headers=headers)
            
            import ssl
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE

            with urllib.request.urlopen(req, context=ctx, timeout=20) as response:
                return response.read().decode('utf-8', errors='ignore')
        except Exception:
            return None

    def process_content(self, url):
        if not url or url == "BOOTSTRAP":
            url = self.base_url + "/latest-updates/"
            
            if '/search/' not in url:
                saved_sort_idx = int(self.addon.getSetting('porngo_sort_by') or '0')
                if 0 <= saved_sort_idx < len(self.sort_options):
                    sort_option = self.sort_options[saved_sort_idx]
                    path = self.sort_paths.get(sort_option)
                    if path:
                        url = urllib.parse.urljoin(self.base_url, path)

        self.add_basic_dirs(url)
        content = self.make_request(url)
        
        if not content:
            self.end_directory()
            return

        pattern = re.compile(r'<div class="thumb item.*?<a href="([^"]+)".*?data-preview="([^"]+)".*?src="([^"]+)".*?alt="([^"]+)".*?class="thumb__duration">([^<]+)<', re.DOTALL)
        matches = re.findall(pattern, content)

        if not matches:
            self.notify_info("No videos found.")
            self.end_directory()
            return

        for video_path, preview, thumb, title, duration in matches:
            video_url = urllib.parse.urljoin(self.base_url, video_path)
            display_title = f"{html.unescape(title.strip())} [COLOR yellow]({duration.strip()})[/COLOR]"
            self.add_link(display_title, video_url, 4, thumb, self.fanart)

        next_page_match = re.search(r'<div class="pagination__item"><a class="pagination__link" href="([^"]+)">Next</a></div>', content)
        if next_page_match:
            next_url = next_page_match.group(1)
            self.add_dir('[COLOR blue]Next Page >>>>[/COLOR]', next_url, 2, self.icons['default'], self.fanart)

        self.end_directory()

    def add_basic_dirs(self, current_url):
        self.add_dir('[COLOR blue]Search[/COLOR]', '', 5, self.icons['search'], self.fanart)
        self.add_dir('Categories', f"{self.base_url}/categories/", 8, self.icons['categories'], self.fanart)
        self.add_dir('Models', f"{self.base_url}/models/", 9, self.icons['pornstars'], self.fanart)

    def process_categories(self, url):
        content = self.make_request(url)
        if not content:
            self.end_directory()
            return
        
        cat_pattern = re.compile(r'<a href="([^"]+)" class="letter-block__link">\s*<span>([^<]+)</span>', re.DOTALL)
        cats = re.findall(cat_pattern, content)
        
        if not cats:
            self.notify_info("No categories found.")
            self.end_directory()
            return
        
        for cat_url, title in cats[:50]:
            full_url = urllib.parse.urljoin(self.base_url, cat_url)
            self.add_dir(html.unescape(title.strip()), full_url, 2, self.icons['categories'], self.fanart)
            
        self.end_directory()

    def process_actresses_list(self, url):
        content = self.make_request(url)
        if not content:
            self.end_directory()
            return
        
        model_pattern = re.compile(r'<a href="([^"]+)" class="thumb__top" title="([^"]+)".*?<img src="([^"]+)"', re.DOTALL)
        models = re.findall(model_pattern, content)
        
        if not models:
            self.notify_info("No models found.")
            self.end_directory()
            return
        
        for model_url, title, thumb in models:
            full_url = urllib.parse.urljoin(self.base_url, model_url)
            self.add_dir(html.unescape(title.strip()), full_url, 2, thumb, self.fanart)
        
        next_page_match = re.search(r'<a class="pagination__link" href="([^"]+)">Next</a>', content)
        if next_page_match:
            next_url = urllib.parse.urljoin(self.base_url, next_page_match.group(1))
            self.add_dir('[COLOR blue]Next Page >>>>[/COLOR]', next_url, 9, self.icons['pornstars'], self.fanart)
            
        self.end_directory()

    def play_video(self, url):
        content = self.make_request(url)
        if not content: 
            self.notify_error("Could not load video page.")
            return

        video_url = None

        source_match = re.search(r'<source\s+src=["\']([^"\']+)["\']', content)
        if source_match:
            video_url = source_match.group(1)

        if not video_url:
            flashvars_match = re.search(r'flashvars\s*=\s*(\{.*?\});?\s*(?:var|function|<|$)', content, re.DOTALL)
            if flashvars_match:
                try:
                    json_str = flashvars_match.group(1)
                    json_str = re.sub(r',\s*}', '}', json_str)
                    json_str = re.sub(r',\s*]', ']', json_str)
                    data = json.loads(json_str)
                    video_url = data.get('video_url') or data.get('video_alt_url') or data.get('video_url_hd')
                    if video_url and not video_url.startswith('http'):
                        video_url = data.get(video_url)
                except json.JSONDecodeError:
                    pass

        if not video_url:
            sources_match = re.search(r'sources\s*:\s*\[\s*\{[^}]*src\s*:\s*["\']([^"\']+)["\']', content)
            if sources_match:
                video_url = sources_match.group(1)

        if not video_url:
            file_match = re.search(r'["\']?file["\']?\s*:\s*["\']([^"\']+\.(?:mp4|m3u8)[^"\']*)["\']', content)
            if file_match:
                video_url = file_match.group(1)

        if not video_url:
            video_tag_match = re.search(r'<video[^>]+src=["\']([^"\']+)["\']', content)
            if video_tag_match:
                video_url = video_tag_match.group(1)

        if video_url:
            if not video_url.startswith('http'):
                video_url = urllib.parse.urljoin(self.base_url, video_url)
            
            video_url += f"|Referer={urllib.parse.quote(url)}"
            
            li = xbmcgui.ListItem(path=video_url)
            li.setProperty('IsPlayable', 'true')
            xbmcplugin.setResolvedUrl(self.addon_handle, True, li)
        else:
            xbmc.log(f"[PornGO] No video URL found for: {url}", xbmc.LOGERROR)
            self.notify_error("No playable stream found.")

    def search(self, query):
        if query:
            self.process_content(self.search_url.format(urllib.parse.quote_plus(query)))

    def select_sort(self, original_url=None):
        if not original_url: 
            return self.notify_error("Cannot sort, original URL not provided.")
        
        if original_url.startswith('plugin://'):
             try:
                 params = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(original_url).query))
                 if 'url' in params and params['url'] != 'BOOTSTRAP':
                     original_url = params['url']
                 elif params.get('url') == 'BOOTSTRAP':
                     original_url = self.base_url + "/latest-updates/"
             except:
                 pass

        dialog = xbmcgui.Dialog()
        idx = dialog.select("Sort by...", self.sort_options)
        
        if idx != -1:
            sort_key = self.sort_options[idx]
            self.addon.setSetting('porngo_sort_by', str(idx))
            path = self.sort_paths[sort_key]
            new_url = urllib.parse.urljoin(self.base_url, path)
            xbmc.executebuiltin(f'Container.Update({sys.argv[0]}?mode=2&url={urllib.parse.quote_plus(new_url)}&website={self.name},replace)')