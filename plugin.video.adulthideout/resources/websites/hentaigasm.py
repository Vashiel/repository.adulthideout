#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
import urllib.parse
import urllib.request
import sys
import html
import os
import xbmcgui
import xbmcplugin
from resources.lib.base_website import BaseWebsite

class HentaigasmWebsite(BaseWebsite):
    config = {
        "name": "hentaigasm",
        "base_url": "https://hentaigasm.com",
        "search_url": "https://hentaigasm.com/?s={}"
    }

    def __init__(self, addon_handle):
        super().__init__(
            name=self.config["name"],
            base_url=self.config["base_url"],
            search_url=self.config["search_url"],
            addon_handle=addon_handle
        )
        self.sort_options = ['Date', 'Views', 'Likes', 'Title', 'Random']
        self.sort_paths = {
            'Date': '/?orderby=date',
            'Views': '/?orderby=views',
            'Likes': '/?orderby=likes',
            'Title': '/?orderby=title',
            'Random': '/?orderby=rand'
        }

    def get_headers(self):
        return {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        }

    def make_request(self, url):
        try:
            headers = self.get_headers()
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=60) as response:
                return response.read().decode('utf-8', errors='ignore')
        except Exception as e:
            self.logger.error(f"Failed to fetch URL {url}: {e}")
            self.notify_error(f"Failed to load page: {e}")
        return None

    def process_content(self, url):
        if not urllib.parse.urlparse(url).query and 's=' not in url:
            saved_sort_idx = int(self.addon.getSetting('hentaigasm_sort_by') or '0')
            sort_option = self.sort_options[saved_sort_idx]
            url = urllib.parse.urljoin(self.base_url, self.sort_paths[sort_option])

        content = self.make_request(url)
        if not content:
            self.end_directory()
            return

        context_menu = [('Sort by...', f'RunPlugin({sys.argv[0]}?mode=7&website={self.name}&action=select_sort&original_url={urllib.parse.quote_plus(url)})')]
        self.add_dir('[COLOR blue]Search[/COLOR]', self.search_url, 5, self.icons['search'], context_menu=context_menu)

        item_pattern = r'(<div id="post-[\s\S]+?</div>\s*</div>)'
        video_blocks = re.findall(item_pattern, content)

        if not video_blocks:
            self.logger.error(f"No video blocks found on {url}")
            self.end_directory()
            return

        for block in video_blocks:
            title_match = re.search(r'<h2 class="title"><a href="([^"]+)"[^>]+title="[^"]+">([^<]+)</a></h2>', block)
            thumb_match = re.search(r'<img src="([^"]+)"', block)
            views_match = re.search(r'<span class="views"><i class="count">([^<]+)</i>', block)

            if title_match and thumb_match:
                video_url, title = title_match.groups()
                preview_thumbnail_url = thumb_match.group(1)
                
                path_part = urllib.parse.urlsplit(preview_thumbnail_url).path
                filename = os.path.basename(path_part).replace('.webp', '.jpg').replace('.gif', '.jpg')
                final_thumb_url = f"https://hentaigasm.com/thumbnail/{filename}"
                safe_thumb_url = urllib.parse.quote(final_thumb_url, safe=':/')
                
                display_title = html.unescape(title)
                if views_match:
                    views = views_match.group(1).strip()
                    display_title += f" [COLOR yellow]({views} Views)[/COLOR]"
                
                if "AI JERK OFF" in display_title:
                    continue

                self.add_link(display_title, video_url, 4, safe_thumb_url, self.fanart, context_menu=context_menu)

        self.add_next_button(content, url)
        self.end_directory()

    def add_next_button(self, content, current_url):
        next_match = re.search(r'<a class="nextpostslink" rel="next"[^>]+href="([^"]+)">', content)
        if next_match:
            next_url = html.unescape(next_match.group(1))
            self.add_dir('[COLOR blue]Next Page >>>>[/COLOR]', next_url, 2, self.icons['default'])

    def play_video(self, url):
        content = self.make_request(url)
        if not content:
            return

        video_url_match = re.search(r'file:\s*"([^"]+)"', content)
        if video_url_match:
            video_url_raw = video_url_match.group(1)
            
            parsed_video = urllib.parse.urlparse(video_url_raw)
            clean_path = parsed_video.path.lstrip('.')
            video_url = urllib.parse.urlunparse(parsed_video._replace(path=urllib.parse.quote(clean_path)))
            
            li = xbmcgui.ListItem(path=video_url)
            li.setProperty('IsPlayable', 'true')
            xbmcplugin.setResolvedUrl(self.addon_handle, True, li)
        else:
            self.notify_error("Video source not found.")