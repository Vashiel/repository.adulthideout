#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
import urllib.parse
import urllib.request
import html
import xbmcgui
import xbmcplugin
import xbmcaddon
from resources.lib.base_website import BaseWebsite

class CrazyshitWebsite(BaseWebsite):
    def __init__(self, addon_handle):
        super().__init__(
            name='crazyshit',
            base_url='https://crazyshit.com',
            search_url='https://crazyshit.com/search/?query={}',
            addon_handle=addon_handle
        )

    def make_request(self, url, max_retries=3, retry_wait=5000):
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
            'Referer': self.base_url,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8'
        }
        for attempt in range(max_retries):
            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=60) as response:
                    return response.read().decode('utf-8', errors='ignore')
            except Exception as e:
                self.logger.error(f"Error requesting {url} (Attempt {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    xbmc.sleep(retry_wait)
        self.notify_error(f"Could not retrieve URL: {url}")
        return ""

    def add_basic_dirs(self, current_url=""):
        self.add_dir('[COLOR blue]Search[/COLOR]', '', 5, self.icons['search'], name_param=self.name)
        self.add_dir('Categories', f'{self.base_url}/categories/', 8, self.icons['categories'])

    def process_content(self, url):
        addon = self.addon
        setting_id = "show_crazyshit"
        disclaimer_setting = 'crazyshit_disclaimer_accepted'
        
        try:
            is_visible = addon.getSettingBool(setting_id)
            disclaimer_accepted = addon.getSettingBool(disclaimer_setting)
        except:
            is_visible = False
            disclaimer_accepted = False

        if is_visible and not disclaimer_accepted:
            dialog = xbmcgui.Dialog()
            disclaimer_text = (
                "WARNING: CrazyShit contains extreme, violent, and disturbing content including graphic accidents, "
                "fights, gore, bizarre fetishes, and shocking material that may cause distress.\n\n"
                "Viewing is at your own risk. Do you wish to proceed?"
            )
            if not dialog.yesno("CrazyShit Content Warning", disclaimer_text):
                addon.setSetting(setting_id, 'false')
                dialog.notification("Access Denied", "CrazyShit has been disabled.", xbmcgui.NOTIFICATION_INFO, 5000)
                self.end_directory()
                return
            else:
                addon.setSetting(disclaimer_setting, 'true')
                dialog.notification("Confirmed", "You may now access CrazyShit content.", xbmcgui.NOTIFICATION_INFO, 3000)

        if not url or url == self.base_url:
            url = f'{self.base_url}/videos/'
        
        content = self.make_request(url)
        if content:
            self.add_basic_dirs(url)
            if '/categories/' in url:
                self.parse_category_list(content, url)
            else:
                self.parse_video_list(content, url)
            self.add_next_button(content, url)
        
        self.end_directory()

    def process_categories(self, url):
        content = self.make_request(url)
        if content:
            self.add_basic_dirs(url)
            self.parse_category_list(content, url)
            self.add_next_button(content, url)
        self.end_directory()

    def parse_video_list(self, content, current_url):
        video_pattern = r'<a href="([^"]+)" title="([^"]+)"\s+class="thumb">.*?<img src="([^"]+)" alt="[^"]+" class="image-thumb"'
        matches = re.findall(video_pattern, content, re.DOTALL)

        if not matches:
            self.notify_info("No videos found on this page.")
            return

        for video_url, title, thumbnail in matches:
            if "/out.php" in video_url:
                continue

            display_title = html.unescape(title.strip())
            self.add_link(display_title, video_url, 4, thumbnail, self.fanart)

    def parse_category_list(self, content, current_url):
        cat_pattern = r'<a href="([^"]+)" title="([^"]+)" class="thumb"[^>]*>.*?<div class="image-container">.*?<img src="([^"]+)" alt="[^"]+" class="image-thumb"'
        matches = re.findall(cat_pattern, content, re.DOTALL)
        if not matches:
            self.notify_info("No categories found.")
            return
        for cat_url, cat_name, thumbnail in matches:
            full_url = urllib.parse.urljoin(self.base_url, cat_url)
            display_name = html.unescape(cat_name.strip())
            self.add_dir(display_name, full_url, 2, thumbnail, self.fanart)

    def add_next_button(self, content, current_url):
        next_page_match = re.search(r'<a href="([^"]+)"><i class="fa fa-angle-right"></i></a>', content)
        if next_page_match:
            next_url_path = html.unescape(next_page_match.group(1))
            next_url = urllib.parse.urljoin(self.base_url, next_url_path)
            self.add_dir('[COLOR blue]Next Page >>>>[/COLOR]', next_url, 2, self.icons['default'], self.fanart)

    def play_video(self, url):
        content = self.make_request(url)
        if not content:
            self.notify_error("Could not load the video page.")
            return
        
        media_match = re.search(r'<source src="([^"]+)" type="video/mp4">', content)
        if not media_match:
            media_match = re.search(r'<video.*?src="([^"]+)"', content)

        if media_match:
            stream_url = html.unescape(media_match.group(1))
            li = xbmcgui.ListItem(path=stream_url)
            li.setProperty('IsPlayable', 'true')
            li.setMimeType('video/mp4')
            xbmcplugin.setResolvedUrl(self.addon_handle, True, li)
        else:
            self.notify_error("No playable stream found. The pattern in 'play_video' needs to be adjusted.")