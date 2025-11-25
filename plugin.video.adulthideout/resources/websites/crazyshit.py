#!/usr/bin/env python
# -*- coding: utf-8 -*-

# [CHANGELOG]
# - Switched to 'requests' library for better stability
# - Added vendor path registration to prevent import errors
# - Added URL encoding for safety
# - Hardened disclaimer setting retrieval
# - Optimized video resolving regex

import sys
import os
import xbmcaddon

# 1. Vendor-Pfad registrieren (WICHTIG für requests)
try:
    addon_path = xbmcaddon.Addon().getAddonInfo('path')
    vendor_path = os.path.join(addon_path, 'resources', 'lib', 'vendor')
    if vendor_path not in sys.path:
        sys.path.insert(0, vendor_path)
except Exception:
    pass

import re
import urllib.parse
import html
import xbmc
import xbmcgui
import xbmcplugin
import requests
from resources.lib.base_website import BaseWebsite

class CrazyshitWebsite(BaseWebsite):
    def __init__(self, addon_handle):
        super().__init__(
            name='crazyshit',
            base_url='https://crazyshit.com',
            search_url='https://crazyshit.com/search/?query={}',
            addon_handle=addon_handle
        )
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
            'Referer': self.base_url,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8'
        })

    def make_request(self, url):
        try:
            # Encoding fix für URLs mit Sonderzeichen
            url = urllib.parse.quote(url, safe=':/?=&%')
            self.logger.info(f"Fetching: {url}")
            
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            return response.text
        except Exception as e:
            self.logger.error(f"Request failed: {e}")
            self.notify_error(f"Failed to fetch URL: {url}")
            return None

    def process_content(self, url):
        # --- Disclaimer Logic ---
        setting_id = "show_crazyshit"
        disclaimer_setting = 'crazyshit_disclaimer_accepted'
        
        # Robust setting retrieval
        is_visible = self.addon.getSetting(setting_id) == 'true'
        disclaimer_accepted = self.addon.getSetting(disclaimer_setting) == 'true'

        if is_visible and not disclaimer_accepted:
            dialog = xbmcgui.Dialog()
            disclaimer_text = (
                "WARNING: CrazyShit contains extreme, violent, and disturbing content including graphic accidents, "
                "fights, gore, bizarre fetishes, and shocking material that may cause distress.\n\n"
                "Viewing is at your own risk. Do you wish to proceed?"
            )
            if not dialog.yesno("CrazyShit Content Warning", disclaimer_text):
                self.addon.setSetting(setting_id, 'false')
                dialog.notification("Access Denied", "CrazyShit has been disabled.", xbmcgui.NOTIFICATION_INFO, 5000)
                self.end_directory()
                return
            else:
                self.addon.setSetting(disclaimer_setting, 'true')
                dialog.notification("Confirmed", "You may now access CrazyShit content.", xbmcgui.NOTIFICATION_INFO, 3000)
        # ------------------------

        if not url or url == "BOOTSTRAP":
            url = f'{self.base_url}/videos/'
        
        content = self.make_request(url)
        
        # Basic Dirs manuell hinzufügen (da wir keine Sortierung für die Seite haben, brauchen wir kein Kontextmenü hier)
        self.add_dir('[COLOR blue]Search[/COLOR]', '', 5, self.icons['search'])
        self.add_dir('Categories', f'{self.base_url}/categories/', 8, self.icons['categories'])

        if content:
            if '/categories/' in url:
                self.parse_category_list(content)
            else:
                self.parse_video_list(content)
            self.add_next_button(content)
        
        self.end_directory()

    def process_categories(self, url):
        content = self.make_request(url)
        if content:
            self.add_dir('[COLOR blue]Search[/COLOR]', '', 5, self.icons['search'])
            self.parse_category_list(content)
            self.add_next_button(content)
        self.end_directory()

    def parse_video_list(self, content):
        video_pattern = r'<a href="([^"]+)" title="([^"]+)"\s+class="thumb">.*?<img src="([^"]+)" alt="[^"]+" class="image-thumb"'
        matches = re.findall(video_pattern, content, re.DOTALL)

        for video_url, title, thumbnail in matches:
            if "/out.php" in video_url:
                continue

            display_title = html.unescape(title.strip())
            # BaseWebsite fügt für Videos automatisch "Sort by" hinzu, falls vorhanden. 
            # Crazyshit hat keine Sortierung definiert, also passiert nichts falsches.
            self.add_link(display_title, video_url, 4, thumbnail, self.fanart)

    def parse_category_list(self, content):
        cat_pattern = r'<a href="([^"]+)" title="([^"]+)" class="thumb"[^>]*>.*?<div class="image-container">.*?<img src="([^"]+)" alt="[^"]+" class="image-thumb"'
        matches = re.findall(cat_pattern, content, re.DOTALL)
        
        for cat_url, cat_name, thumbnail in matches:
            full_url = urllib.parse.urljoin(self.base_url, cat_url)
            display_name = html.unescape(cat_name.strip())
            self.add_dir(display_name, full_url, 2, thumbnail, self.fanart)

    def add_next_button(self, content):
        next_page_match = re.search(r'<a href="([^"]+)" class="plugurl" title="next page">next</a>', content)
        if not next_page_match:
             next_page_match = re.search(r'<div class="prevnext">.*?<a href="([^"]+)"[^>]*>next</a>', content)

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
            self.notify_error("No playable stream found.")