#!/usr/bin/env python
# -*- coding: utf-8 -*-

# [CHANGELOG]
# - Fixed: Added vendor library path registration to load 'requests' and 'cloudscraper'
# - Fixed: Removed duplicate "Sort by" context menu (handled by base class for videos)
# - Optimized regex to prevent duplicate entries from "Featured" sections
# - Refined session handling with optional Cloudscraper support
# - Improved play_video logic with robust proxy headers

import sys
import os
import xbmcaddon

# 1. ZUERST den Pfad zu den Bibliotheken (vendor) hinzufügen
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
from resources.lib.proxy_utils import ProxyController, PlaybackGuard

# Optional: Cloudscraper für Cloudflare-Schutz
try:
    import cloudscraper
    _HAS_CF = True
except ImportError:
    _HAS_CF = False

class AvjoyWebsite(BaseWebsite):
    def __init__(self, addon_handle):
        super().__init__(
            name="avjoy",
            base_url="https://en.avjoy.me",
            search_url="https://en.avjoy.me/search/videos/{}",
            addon_handle=addon_handle
        )
        self.display_name = "Avjoy"
        self.sort_options = ["Most Recent", "Most Viewed", "Top Rated", "Top Favorites", "Longest"]
        self.sort_paths = {
            "Most Recent": "/videos?o=mr",
            "Most Viewed": "/videos?o=mv",
            "Top Rated": "/videos?o=tr",
            "Top Favorites": "/videos?o=tf",
            "Longest": "/videos?o=lg"
        }
        self.setting_id_sort = "avjoy_sort_by" 
        self.timeout = 20
        self.user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36'
        self.session = self._init_session()

    def _init_session(self):
        """Initialisiert eine Session, vorzugsweise mit Cloudscraper."""
        if _HAS_CF:
            return cloudscraper.create_scraper(browser={'custom': self.user_agent})
        else:
            s = requests.Session()
            s.headers.update({'User-Agent': self.user_agent})
            return s

    def make_request(self, url):
        try:
            # Encoding fix für URLs mit Sonderzeichen
            url = urllib.parse.quote(url, safe=':/?=&%')
            self.logger.info(f"Fetching: {url}")
            
            resp = self.session.get(url, timeout=self.timeout)
            resp.raise_for_status()
            return resp.text
        except Exception as e:
            self.logger.error(f"Request failed: {e}")
            return None

    def get_start_url_and_label(self):
        try:
            idx = int(self.addon.getSetting(self.setting_id_sort) or 0)
        except ValueError: 
            idx = 0
        
        if idx < 0 or idx >= len(self.sort_options): 
            idx = 0
            
        sort_key = self.sort_options[idx]
        path = self.sort_paths.get(sort_key, "/videos?o=mr")
        
        full_url = urllib.parse.urljoin(self.base_url, path)
        return full_url, f"{self.display_name} [COLOR yellow]({sort_key})[/COLOR]"

    def process_content(self, url):
        if not url or url == "BOOTSTRAP":
            url, _ = self.get_start_url_and_label()
            
        content = self.make_request(url)
        if not content:
            self.notify_error("Failed to load content")
            self.end_directory()
            return

        # Für Ordner (add_dir) müssen wir das Kontextmenü manuell bauen
        encoded_url = urllib.parse.quote_plus(url)
        dir_context_menu = [('Sort by...', f'RunPlugin({sys.argv[0]}?mode=7&action=select_sort&website={self.name}&original_url={encoded_url})')]
        
        self.add_dir('[COLOR blue]Search[/COLOR]', '', 5, self.icons.get('search', ''), context_menu=dir_context_menu)
        self.add_dir('[COLOR blue]Categories[/COLOR]', f'{self.base_url}/categories', 8, self.icons.get('categories', ''), context_menu=dir_context_menu)

        self.parse_video_list(content, url)
        self.add_next_button(content, url)
        self.end_directory()

    def parse_video_list(self, content, current_url):
        # OPTIMIERUNG: Schneide "Featured" Bereich ab, um Duplikate zu vermeiden
        if 'class="well-filters"' in content:
            parts = content.split('class="well-filters"')
            content = parts[-1] # Nimm nur den Teil nach den Filtern
        elif 'Most Recent' in content: # Fallback Marker
            parts = content.split('Most Recent')
            content = parts[-1]

        # Regex angepasst für AVJoy Struktur
        pattern = r'<div class="[^"]*col-[^"]*">.*?<a href="([^"]+)">.*?<div class="thumb-overlay".*?>.*?<img src="([^"]+)" title="([^"]+)"'
        matches = re.findall(pattern, content, re.DOTALL | re.IGNORECASE)
        
        count = 0
        seen_urls = set() # Set um absolute Eindeutigkeit zu garantieren

        for video_path, thumb, title in matches:
            # Ignoriere alles was kein echtes Video ist
            if '/video/' not in video_path or '/videos/' in video_path:
                continue
            
            # Ignoriere Duplikate
            if video_path in seen_urls:
                continue
            seen_urls.add(video_path)

            full_url = urllib.parse.urljoin(self.base_url, video_path)
            thumb_url = urllib.parse.urljoin(self.base_url, thumb)
            clean_title = html.unescape(title.strip())
            
            # BaseWebsite fügt "Sort by" automatisch hinzu für add_link
            self.add_link(clean_title, full_url, 4, thumb_url, self.fanart, info_labels={'title': clean_title})
            count += 1
            
        self.logger.info(f"Found {count} videos")

    def add_next_button(self, content, current_url):
        next_url = None
        
        # Pattern 1: Standard Pagination Link
        match = re.search(r'<a [^>]*href="([^"]+)"[^>]*class="[^"]*prevnext"[^>]*>', content)
        if not match:
             # Pattern 2: Bootstrap Pagination
             match = re.search(r'<li class="page-item">\s*<a class="page-link" href="([^"]+)"[^>]*aria-label="Next"', content)
        
        if match:
            next_url = match.group(1)
        
        if next_url:
            full_next_url = urllib.parse.urljoin(self.base_url, html.unescape(next_url))
            self.add_dir('[COLOR blue]Next Page >>[/COLOR]', full_next_url, 2, self.icons.get('default', ''), self.fanart)

    def play_video(self, url):
        self.logger.info(f"Resolving video: {url}")
        content = self.make_request(url)
        
        if not content:
            self.notify_error("Failed to load video page")
            return

        match = re.search(r'<source src="([^"]+)" type=[\'"]video/mp4[\'"]', content)
        if match:
            video_url = match.group(1)
            
            # Proxy Setup für stabile Wiedergabe
            stream_session = requests.Session()
            stream_session.headers.update({
                'User-Agent': self.user_agent,
                'Referer': self.base_url + '/',
                'Accept': '*/*',
                'Connection': 'keep-alive'
            })
            stream_session.cookies.update(self.session.cookies)

            upstream_headers = {
                'User-Agent': self.user_agent,
                'Referer': self.base_url + '/'
            }
            
            proxy = ProxyController(
                upstream_url=video_url,
                upstream_headers=upstream_headers,
                session=stream_session
            )
            local_url = proxy.start()
            
            li = xbmcgui.ListItem(path=local_url)
            li.setProperty("IsPlayable", "true")
            li.setMimeType("video/mp4")
            xbmcplugin.setResolvedUrl(self.addon_handle, True, li)

            PlaybackGuard(xbmc.Player(), xbmc.Monitor(), local_url, proxy).start()

        else:
            self.logger.error("No playable stream found")
            self.notify_error("No playable stream found")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())

    def process_categories(self, url):
        content = self.make_request(url)
        if not content:
            self.end_directory()
            return
            
        pattern = r'<div class="[^"]*col-[^"]*">.*?<a href="([^"]+)">.*?<div class="thumb-overlay">.*?<img src="([^"]+)" title="([^"]+)"'
        matches = re.findall(pattern, content, re.DOTALL | re.IGNORECASE)
        
        encoded_url = urllib.parse.quote_plus(url)
        context_menu = [('Sort by...', f'RunPlugin({sys.argv[0]}?mode=7&action=select_sort&website={self.name}&original_url={encoded_url})')]
        
        for cat_path, thumb, name in matches:
            full_cat_url = urllib.parse.urljoin(self.base_url, cat_path)
            full_thumb = urllib.parse.urljoin(self.base_url, thumb)
            self.add_dir(html.unescape(name.strip()), full_cat_url, 2, full_thumb, self.fanart, context_menu=context_menu)
            
        self.end_directory()

    def select_sort(self, original_url=None):
        try:
            current_idx = int(self.addon.getSetting(self.setting_id_sort) or 0)
        except: current_idx = 0

        dialog = xbmcgui.Dialog()
        idx = dialog.select("Sort by...", self.sort_options, preselect=current_idx)
        
        if idx > -1:
            self.addon.setSetting(self.setting_id_sort, str(idx))
            new_url, _ = self.get_start_url_and_label()
            xbmc.executebuiltin(f"Container.Update({sys.argv[0]}?mode=2&url={urllib.parse.quote_plus(new_url)}&website={self.name},replace)")