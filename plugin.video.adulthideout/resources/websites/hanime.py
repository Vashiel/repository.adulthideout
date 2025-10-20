#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
import urllib.request
from urllib.error import URLError, HTTPError
import urllib.parse
import html
import base64
import os
import sys
import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
import xbmcvfs
from resources.lib.base_website import BaseWebsite

class Hanime(BaseWebsite):
    def __init__(self, addon_handle):
        addon = xbmcaddon.Addon()
        base_url = 'https://hanime.red/'
        search_url = urllib.parse.urljoin(base_url, '?s={}')

        super().__init__(
            name='Hanime',
            base_url=base_url,
            search_url=search_url,
            addon_handle=addon_handle,
            addon=addon
        )
        
        self.sort_options = [
            "Recent Upload", "Old Upload", "Most Views", "Least Views",
            "Most Likes", "Least Likes", "Alphabetical (A-Z)", "Alphabetical (Z-A)"
        ]
        self.sort_paths = {
            "Recent Upload": "recent-hentai/",
            "Old Upload": "old-videos/",
            "Most Views": "most-views/",
            "Least Views": "least-views/",
            "Most Likes": "most-likes/",
            "Least Likes": "least-likes/",
            "Alphabetical (A-Z)": "alphabetical-a-z/",
            "Alphabetical (Z-A)": "alphabetical-z-a/"
        }

    def select_sort(self, original_url=None):
        if not hasattr(self, 'sort_options') or not self.sort_options:
            self.notify_info("This site does not support sorting.")
            return

        try:
            current_setting_idx = int(self.addon.getSetting(f"{self.name.lower()}_sort_by"))
        except (ValueError, TypeError):
            current_setting_idx = 0
        
        if not (0 <= current_setting_idx < len(self.sort_options)):
            current_setting_idx = 0

        dialog = xbmcgui.Dialog()
        idx = dialog.select("Sort by...", self.sort_options, preselect=current_setting_idx)

        if idx == -1: return

        self.addon.setSetting(f"{self.name.lower()}_sort_by", str(idx))
        xbmc.executebuiltin('Container.Refresh')

    def _get_html(self, url, referer=None):
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
            if referer:
                headers['Referer'] = referer
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as response:
                if 200 <= response.status < 300:
                    return response.read().decode('utf-8', errors='ignore')
        except Exception as e:
            self.logger.error(f"An unexpected error occurred in _get_html for {url}: {e}")
            self.notify_error("An unexpected error occurred.")
        return None

    def process_content(self, url):
        parsed_url = urllib.parse.urlparse(url)
        path = parsed_url.path
        
        is_main_menu = not path or path == '/' or any(sort_path in path for sort_path in self.sort_paths.values())
        
        if is_main_menu and not parsed_url.query and '/page/' not in path:
            try:
                saved_sort_idx = int(self.addon.getSetting(f"{self.name.lower()}_sort_by") or '0')
                sort_option = self.sort_options[saved_sort_idx]
                sort_path = self.sort_paths[sort_option]
                url = urllib.parse.urljoin(self.base_url, sort_path)
            except (ValueError, IndexError):
                url = urllib.parse.urljoin(self.base_url, self.sort_paths[self.sort_options[0]])

        context_menu = [('Sort by...', f'RunPlugin({sys.argv[0]}?mode=7&website={self.name}&action=select_sort)')]

        if is_main_menu:
            self.add_dir('[COLOR yellow]Search[/COLOR]', '', 5, self.icons['search'], context_menu=context_menu)
            tag_url = urllib.parse.urljoin(self.base_url, 'tags-page/')
            self.add_dir('[COLOR yellow]Tags[/COLOR]', tag_url, 8, self.icons['categories'], context_menu=context_menu)

        html_content = self._get_html(url)
        if not html_content:
            self.notify_info("Page not found or could not be loaded.")
            self.end_directory()
            return
        
        def get_safe_thumb_url(thumb_url):
            try:
                parsed_thumb = urllib.parse.urlparse(thumb_url)
                safe_path = urllib.parse.quote(parsed_thumb.path)
                return parsed_thumb._replace(path=safe_path).geturl()
            except Exception:
                return thumb_url

        current_path = urllib.parse.urlparse(url).path
        video_items = []

        if '/tag/' in current_path:
            video_blocks = re.findall(r'<a href="([^"]+)".*?<h2[^>]+>([^<]+)</h2>.*?<img[^>]+src="([^"]+)"[^>]+class="[^"]*wp-post-image', html_content, re.DOTALL)
            for video_url, title, thumb_url in video_blocks:
                if not thumb_url.lower().endswith('.svg'):
                    video_items.append({'url': video_url, 'title': title, 'thumb': thumb_url})
        else:
            video_blocks = re.findall(r'<a href="([^"]+)".*?<figure class="main-figure">.*?<img[^>]+src="([^"]+)"[^>]*>.*?</figure>.*?<h2[^>]+>([^<]+)</h2>', html_content, re.DOTALL)
            for video_url, thumb_url, title in video_blocks:
                if not thumb_url.lower().endswith('.svg'):
                    video_items.append({'url': video_url, 'title': title, 'thumb': thumb_url})

        if not video_items and not is_main_menu:
            self.notify_info("No videos found on this page.")
        else:
            for item in video_items:
                safe_thumb = get_safe_thumb_url(item['thumb'])
                self.add_link(html.unescape(item['title'].strip()), item['url'], 4, safe_thumb, self.fanart, context_menu=context_menu)

        next_page_match = re.search(r'<a[^>]+href="([^"]+)"\s*>Next</a>', html_content, re.IGNORECASE)
        if next_page_match:
            next_page_url = html.unescape(next_page_match.group(1))
            self.add_dir('Next Page >>', next_page_url, 2, context_menu=context_menu)

        self.end_directory()

    def process_categories(self, url):
        html_content = self._get_html(url)
        if not html_content:
            self.end_directory()
            return

        tag_blocks = re.findall(r'<a class="bg-tr".*?</a>', html_content, re.DOTALL)

        if not tag_blocks:
            self.notify_info("No tags found on the page.")
        else:
            for block in tag_blocks:
                url_match = re.search(r'href="([^"]+)"', block)
                title_match = re.search(r'<h2[^>]+>([^<]+)</h2>', block)
                icon_match = re.search(r'<img[^>]+src="([^"]*)"', block)

                if url_match and title_match and icon_match:
                    tag_url = url_match.group(1)
                    title = html.unescape(title_match.group(1).strip())
                    icon_url = icon_match.group(1)

                    if not icon_url or icon_url.lower().endswith('.svg'):
                        icon_url = self.icons['default']
                    
                    display_title = title.capitalize()
                    
                    self.add_dir(display_title, tag_url, 2, icon_url, self.fanart)

        self.end_directory()

    def play_video(self, url):
        main_page_html = self._get_html(url)
        if not main_page_html:
            self.notify_error("Could not load the main video page.")
            return

        iframe_match = re.search(r'src="(https://nhplayer\.com/v/[^"]+)"', main_page_html)
        if not iframe_match:
            self.notify_error("Player iframe (nhplayer.com/v/...) not found.")
            return
        
        iframe_url = html.unescape(iframe_match.group(1))

        iframe_html = self._get_html(iframe_url, referer=url)
        if not iframe_html:
            self.notify_error("Could not load the player page.")
            return

        real_player_match = re.search(r'[\'"]([^\'"]*player\.php\?u=[^\'"]+)[\'"]', iframe_html)
        if not real_player_match:
            self.notify_error("Could not find the real player URL (player.php).")
            return
            
        real_player_url = html.unescape(real_player_match.group(1))
        if not real_player_url.startswith('http'):
            real_player_url = urllib.parse.urljoin('https://nhplayer.com/', real_player_url)

        try:
            parsed_url = urllib.parse.urlparse(real_player_url)
            query_params = urllib.parse.parse_qs(parsed_url.query)
            
            if 'u' not in query_params:
                self.notify_error("Video parameter 'u' not found in player URL.")
                return

            base64_string = query_params['u'][0]
            base64_string += '=' * (-len(base64_string) % 4)
            decoded_bytes = base64.b64decode(base64_string)
            stream_url = decoded_bytes.decode('utf-8')

        except Exception as e:
            self.logger.error(f"Failed to decode video URL from Base64: {e}")
            self.notify_error("Could not decode the video URL.")
            return
        
        final_path = f"{stream_url}|Referer=https://nhplayer.com/"
        
        list_item = xbmcgui.ListItem(path=final_path)
        xbmcplugin.setResolvedUrl(self.addon_handle, True, list_item)