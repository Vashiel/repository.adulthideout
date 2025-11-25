#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
import sys
import urllib.parse
import html
import threading
import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon
import os
import json

try:
    # Vendor-Pfad für Cloudscraper hinzufügen
    addon_path = xbmcaddon.Addon().getAddonInfo('path')
    vendor_path = os.path.join(addon_path, 'resources', 'lib', 'vendor')
    if vendor_path not in sys.path:
        sys.path.insert(0, vendor_path)
except Exception as e:
    xbmc.log(f"[AdultHideout] Vendor path inject failed in rule34video.py: {e}", xbmc.LOGERROR)

try:
    import cloudscraper
    _HAS_CF = True
except Exception as e:
    xbmc.log(f"[Rule34video] cloudscraper import failed: {e}", xbmc.LOGERROR)
    _HAS_CF = False

from resources.lib.base_website import BaseWebsite

# === SESSION CACHE ===
_SESSION_CACHE = None
_SESSION_LOCK = threading.Lock()
# =====================

class Rule34video(BaseWebsite):
    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name='rule34video',
            base_url='https://rule34video.com',
            search_url='https://rule34video.com/search/{}/',
            addon_handle=addon_handle,
            addon=addon
        )
        self.display_name = 'Rule34video'
        self.sort_options = ['Newest', 'Most Viewed', 'Top Rated', 'Longest', 'Random']
        self.content_options = ['All', 'Straight', 'Gay', 'Futa']
        self.setting_id_sort = "rule34video_sort_order"
        self.setting_id_content = "rule34video_content_type"
        
        # IDs basierend auf dem neuen Quelltext (data-tags)
        self.content_params = {
            'All': None,
            'Straight': '2109',
            'Gay': '192',
            'Futa': '15' 
        }
        
        self.scraper = None
        self._scraper_ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/126.0.0.0 Safari/537.36"
        )
        self.timeout = 45

    def get_session(self):
        global _SESSION_CACHE, _SESSION_LOCK
        with _SESSION_LOCK:
            if self.scraper:
                return self.scraper
            
            if _SESSION_CACHE:
                self.logger.info(f"[{self.name}] Reusing cached Cloudscraper session.")
                self.scraper = _SESSION_CACHE
                return self.scraper

            self.logger.info(f"[{self.name}] Initializing new Cloudscraper object...")
            if not _HAS_CF:
                self.notify_error("Cloudscraper library missing.")
                return None

            try:
                scraper = cloudscraper.create_scraper(browser={'custom': self._scraper_ua}, delay=10)
                scraper.headers.update({
                    'User-Agent': self._scraper_ua,
                    'Referer': self.base_url,
                    'Accept-Language': 'en-US,en;q=0.9',
                })
                self.scraper = scraper
                _SESSION_CACHE = scraper
                return self.scraper
            except Exception as e:
                self.logger.error(f"[{self.name}] Failed to create scraper: {e}")
                return None

    def make_request(self, url, referer=None):
        scraper = self.get_session()
        if not scraper: return None
        try:
            headers = scraper.headers.copy()
            if referer: headers['Referer'] = referer
            resp = scraper.get(url, headers=headers, timeout=self.timeout)
            resp.raise_for_status()
            return resp.text
        except Exception as e:
            self.logger.error(f"Request failed for {url}: {e}")
            return None

    def _get_start_url(self):
        # Einstellungen laden
        try:
            sort_idx = int(self.addon.getSetting(self.setting_id_sort))
            sort_key = self.sort_options[sort_idx]
        except:
            sort_key = 'Newest'
            
        try:
            content_idx = int(self.addon.getSetting(self.setting_id_content))
            content_key = self.content_options[content_idx]
        except:
            content_key = 'All'

        # Basis-URL bestimmen (Tag-Filter oder Latest)
        tag_id = self.content_params.get(content_key)
        if tag_id:
            # content type -> /tags/ID/
            base = f"/tags/{tag_id}/"
        else:
            # All -> /latest-updates/
            base = "/latest-updates/"

        # Sortierung anhängen (Query params für KVS)
        # Mappings basierend auf neuem HTML
        sort_map = {
            'Newest': 'post_date',
            'Most Viewed': 'video_viewed',
            'Top Rated': 'rating',
            'Longest': 'duration',
            'Random': 'pseudo_rand'
        }
        sort_val = sort_map.get(sort_key, 'post_date')
        
        # URL bauen
        url = urllib.parse.urljoin(self.base_url, base)
        url += f"?sort_by={sort_val}"
        
        return url

    def get_start_url_and_label(self):
        # Kleiner Helper für das Label im Hauptmenü
        try:
            s_idx = int(self.addon.getSetting(self.setting_id_sort))
            c_idx = int(self.addon.getSetting(self.setting_id_content))
            label = f"{self.display_name} [COLOR yellow]({self.content_options[c_idx]} - {self.sort_options[s_idx]})[/COLOR]"
        except:
            label = self.display_name
        return self._get_start_url(), label

    def process_content(self, url):
        if not url: url = self._get_start_url()
        
        html_content = self.make_request(url)
        if not html_content:
            self.end_directory()
            return

        # Menü-Links
        self.add_dir('[COLOR blue]Search[/COLOR]', '', 5, self.icons['search'], name_param=self.name)
        self.add_dir('[COLOR blue]Categories[/COLOR]', urllib.parse.urljoin(self.base_url, '/categories/'), 8, self.icons['categories'])

        # REGEX für die neue Struktur (basierend auf neu 1.txt)
        # Sucht nach <div class="item thumb ..."> ... <a href="..."> ... <img data-original="...">
        video_pattern = re.compile(
            r'<div class="item thumb[^"]*">.*?'
            r'<a class="th[^"]*" href="(?P<url>[^"]+)"[^>]*title="(?P<title>[^"]+)".*?'
            r'<img[^>]+data-original="(?P<thumb>[^"]+)".*?'
            r'<div class="time">(?P<duration>[^<]+)</div>',
            re.DOTALL | re.IGNORECASE
        )

        found = False
        for match in video_pattern.finditer(html_content):
            found = True
            v_url = match.group('url')
            title = html.unescape(match.group('title').strip())
            thumb = match.group('thumb')
            duration = match.group('duration').strip()
            
            full_url = urllib.parse.urljoin(self.base_url, v_url)
            
            # Kontextmenü
            cm = [
                ('Select Content...', f'RunPlugin({sys.argv[0]}?mode=7&action=select_content_type&website={self.name})'),
                ('Sort by...', f'RunPlugin({sys.argv[0]}?mode=7&action=select_sort_order&website={self.name})')
            ]
            
            info = {'title': title, 'duration': self._duration_to_seconds(duration), 'plot': title}
            self.add_link(f"{title} [COLOR yellow]({duration})[/COLOR]", full_url, 4, thumb, self.fanart, info_labels=info, context_menu=cm)

        if not found:
            self.logger.warning(f"[{self.name}] No videos found on {url}")

        # Pagination (Pager Next)
        # <div class="item pager next"><a href="...">
        next_match = re.search(r'<div class="item pager next">\s*<a href="(?P<next>[^"]+)"', html_content)
        if next_match:
            next_link = urllib.parse.urljoin(self.base_url, next_match.group('next'))
            self.add_dir('[COLOR yellow]Next Page >>[/COLOR]', next_link, 2, self.icons['default'])

        self.end_directory()

    def process_categories(self, url):
        html_content = self.make_request(url)
        if not html_content:
            self.end_directory()
            return

        # Regex für Kategorien (Sidebar-Stil oder Grid, KVS Standard)
        # <a href="..." class="item"><div class="image"><img src="..."></div><div class="name">...</div></a>
        cat_pattern = re.compile(
            r'<a href="(?P<url>[^"]+)" class="item">\s*'
            r'.*?<img src="(?P<thumb>[^"]+)".*?'
            r'<div class="name">\s*(?P<title>[^<\n]+)',
            re.DOTALL | re.IGNORECASE
        )

        for match in cat_pattern.finditer(html_content):
            c_url = urllib.parse.urljoin(self.base_url, match.group('url'))
            thumb = match.group('thumb')
            title = html.unescape(match.group('title').strip())
            
            # Filter "All Categories" link out usually
            if "All Categories" in title: continue
            
            self.add_dir(title, c_url, 2, thumb, self.fanart)
            
        self.end_directory()

    def play_video(self, url):
        self.logger.info(f"[{self.name}] Resolving video: {url}")
        html_content = self.make_request(url)
        if not html_content:
            self.notify_error("Failed to load video page")
            return

        # Generic KVS Video Extraction
        # Suche nach mp4 Links im Source, oft in flashvars oder <video> tags
        # Prio 1: Source Tags
        video_url = None
        
        # Suche nach direktem MP4 Link in Quotes
        # Oft: video_url: 'https://...' oder "video_url": "..."
        mp4_matches = re.findall(r'["\'](https?://[^"\']+\.mp4[^"\']*)["\']', html_content)
        
        # Filter logic: Wir wollen keine Preview/Thumbnail Videos, sondern das Main Video
        # Oft ist das längste URL oder hat bestimmte Keywords nicht
        candidates = []
        for m in mp4_matches:
            if 'preview' in m: continue
            if 'get_file' in m: # KVS Secure link pattern
                candidates.append(m)
        
        if candidates:
            # Nimm den ersten guten Kandidaten (oft highest quality)
            video_url = candidates[0]
        elif mp4_matches:
            # Fallback
            video_url = mp4_matches[0]

        if video_url:
            # URL cleanen (JSON slashes)
            video_url = video_url.replace(r'\/', '/')
            self.logger.info(f"[{self.name}] Found video URL: {video_url}")
            
            li = xbmcgui.ListItem(path=video_url)
            li.setProperty('IsPlayable', 'true')
            xbmcplugin.setResolvedUrl(self.addon_handle, True, li)
        else:
            self.logger.error(f"[{self.name}] No video URL found in source.")
            self.notify_error("Video extraction failed")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())

    def _duration_to_seconds(self, duration_str):
        try:
            parts = list(map(int, duration_str.split(':')))
            if len(parts) == 2:
                return parts[0] * 60 + parts[1]
            elif len(parts) == 3:
                return parts[0] * 3600 + parts[1] * 60 + parts[2]
        except:
            pass
        return 0

    # Helper für Kontextmenü-Funktionen (müssen existieren, damit RunPlugin funktioniert)
    def select_content_type(self, original_url=None):
        # Settings-Dialog Logik (wie gehabt, nur auf neue Content-Liste angepasst)
        try:
            current_idx = int(self.addon.getSetting(self.setting_id_content) or 0)
        except: current_idx = 0
        
        dialog = xbmcgui.Dialog()
        idx = dialog.select("Select Content...", self.content_options, preselect=current_idx)
        if idx > -1:
            self.addon.setSetting(self.setting_id_content, str(idx))
            new_url, _ = self.get_start_url_and_label()
            xbmc.executebuiltin(f"Container.Update({sys.argv[0]}?mode=2&url={urllib.parse.quote_plus(new_url)}&website={self.name},replace)")

    def select_sort_order(self, original_url=None):
        try:
            current_idx = int(self.addon.getSetting(self.setting_id_sort) or 0)
        except: current_idx = 0
        
        dialog = xbmcgui.Dialog()
        idx = dialog.select("Sort by...", self.sort_options, preselect=current_idx)
        if idx > -1:
            self.addon.setSetting(self.setting_id_sort, str(idx))
            new_url, _ = self.get_start_url_and_label()
            xbmc.executebuiltin(f"Container.Update({sys.argv[0]}?mode=2&url={urllib.parse.quote_plus(new_url)}&website={self.name},replace)")