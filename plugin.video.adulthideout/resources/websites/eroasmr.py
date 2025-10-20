#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
import sys
import urllib.request
import urllib.parse
import urllib.error
import http.cookiejar
import xbmcgui
import xbmcplugin

from resources.lib.base_website import BaseWebsite

class EroASMR(BaseWebsite):
    def __init__(self, addon_handle):
        super(EroASMR, self).__init__(
            name='EroASMR',
            base_url='https://eroasmr.com/',
            search_url='https://eroasmr.com/?s={}',
            addon_handle=addon_handle
        )
        self.latest_url = 'https://eroasmr.com/recently-added-videos/'
        self.user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        
        cookie_jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookie_jar))
        self.opener.addheaders = [('User-Agent', self.user_agent)]
        urllib.request.install_opener(self.opener)

    def _get_html(self, url):
        max_retries = int(self.addon.getSetting('max_retry_attempts') or 3)
        for attempt in range(max_retries):
            try:
                req = urllib.request.Request(url)
                with self.opener.open(req, timeout=30) as response:
                    if response.getcode() == 200:
                        return response.read().decode('utf-8', errors='ignore')
            except Exception as e:
                self.logger.error(f"EroASMR: Request failed for {url}: {e}")
                if attempt < max_retries - 1:
                    self.logger.info(f"Retrying ({attempt + 1}/{max_retries})...")
        return None

    def _parse_duration(self, duration_str):
        seconds = 0
        try:
            parts = list(map(int, duration_str.split(':')))
            if len(parts) == 3:
                seconds = parts[0] * 3600 + parts[1] * 60 + parts[2]
            elif len(parts) == 2:
                seconds = parts[0] * 60 + parts[1]
        except (ValueError, TypeError): return 0
        return seconds

    def process_content(self, url):
        if url == self.base_url:
            self.add_dir('[COLOR blue]Search...[/COLOR]', self.base_url, 5, icon=self.icons['search'])
            self.add_dir('[COLOR blue]Categories...[/COLOR]', self.base_url, 8, icon=self.icons['categories'])
            html_content = self._get_html(self.latest_url)
            if html_content:
                video_pattern = re.compile(
                    r'<article[^>]+class="[^"]*?viem_video[^"]*?".*?<a class="dt-image-link" href="([^"]+)".*?src="([^"]+)".*?<span class="video-duration">([^<]+)</span>.*?<h2 class="post-title.*?<a [^>]+>([^<]+)</a>',
                    re.DOTALL
                )
                matches = video_pattern.findall(html_content)
                for video_url, thumb_url, duration_str, title in matches:
                    info_labels = {'title': title, 'duration': self._parse_duration(duration_str.strip()), 'plot': title}
                    self.add_link(name=title, url=video_url, mode=4, icon=thumb_url, fanart=self.fanart, info_labels=info_labels)
                
                next_page_match = re.search(r'<a class="next page-numbers" href="([^"]+)">', html_content)
                if next_page_match:
                    self.add_dir('[COLOR blue]Next Page >>[/COLOR]', next_page_match.group(1), 2)
            self.end_directory()
            return

        all_matches = []
        current_url_to_fetch = url
        next_page_for_button = None
        PAGES_TO_LOAD = 3 

        for i in range(PAGES_TO_LOAD):
            self.logger.info(f"EroASMR: Lade Seite {i+1}/{PAGES_TO_LOAD} von {current_url_to_fetch}")
            html_content = self._get_html(current_url_to_fetch)
            if not html_content:
                break

            video_pattern = re.compile(
                r'<article[^>]+class="[^"]*?viem_video[^"]*?".*?<a class="dt-image-link" href="([^"]+)".*?src="([^"]+)".*?<span class="video-duration">([^<]+)</span>.*?<h2 class="post-title.*?<a [^>]+>([^<]+)</a>',
                re.DOTALL
            )
            matches = video_pattern.findall(html_content)
            
            if not matches:
                break 
            
            all_matches.extend(matches)

            next_page_match = re.search(r'<a class="next page-numbers" href="([^"]+)">', html_content)
            if next_page_match:
                current_url_to_fetch = next_page_match.group(1)
                next_page_for_button = current_url_to_fetch
            else:
                next_page_for_button = None
                break
        
        if not all_matches:
            self.notify_info("No videos found.")

        for video_url, thumb_url, duration_str, title in all_matches:
            info_labels = {'title': title, 'duration': self._parse_duration(duration_str.strip()), 'plot': title}
            self.add_link(name=title, url=video_url, mode=4, icon=thumb_url, fanart=self.fanart, info_labels=info_labels)

        if next_page_for_button:
            self.add_dir('[COLOR blue]Next Page >>[/COLOR]', next_page_for_button, 2)

        self.end_directory()

    def process_categories(self, url):
        category_page_url = 'https://eroasmr.com/video-category/sex-roleplays/'
        html_content = self._get_html(category_page_url)
        
        if not html_content:
            self.notify_error("Failed to load page content for categories.")
            self.end_directory()
            return
        
        category_pattern = re.compile(r'<li class="cat-item.*?<a [^>]*?href="([^"]+/video-category/[^"]+)">([^<]+)</a>')
        matches = category_pattern.findall(html_content)
        
        if not matches:
            self.notify_info("No categories found.")
            self.end_directory()
            return

        seen = set()
        for cat_url, cat_title in matches:
            cat_title_clean = cat_title.strip().capitalize()
            if cat_title_clean and cat_title_clean.lower() not in seen:
                seen.add(cat_title_clean.lower())
                self.add_dir(cat_title_clean, cat_url, 2, icon=self.icons['categories'])

        self.end_directory()

    def play_video(self, url):
        self.logger.info(f"EroASMR: Lade Videoseite: {url}")
        html_content = self._get_html(url)
        if not html_content:
            self.notify_error("Failed to load video page.")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return

        source_match = re.search(r'(?:<video id="video-id"><source|<source)\s+src="([^"]+\.mp4)"', html_content)
        
        if source_match:
            initial_url = source_match.group(1)
            self.logger.info(f"EroASMR: Initialen Videostream gefunden: {initial_url}")
            
            final_url = initial_url
            if '/get_video/' in initial_url:
                self.logger.info("EroASMR: Redirect-Link erkannt, löse finale URL auf...")
                try:
                    req = urllib.request.Request(initial_url, method='HEAD')
                    with self.opener.open(req, timeout=15) as response:
                        final_url = response.geturl() 
                        self.logger.info(f"EroASMR: Aufgelöste finale URL: {final_url}")
                except Exception as e:
                    self.logger.error(f"EroASMR: Fehler beim Auflösen der Weiterleitung: {e}")
                    final_url = initial_url
            
            header_string = f"Referer={url}&User-Agent={self.user_agent}"
            play_path = f"{final_url}|{header_string}"
            
            self.logger.info(f"EroASMR: Finaler Wiedergabepfad: {play_path}")
            
            list_item = xbmcgui.ListItem(path=play_path)
            xbmcplugin.setResolvedUrl(self.addon_handle, True, list_item)
        else:
            self.logger.error(f"EroASMR: Konnte auf Seite {url} keine abspielbare URL finden.")
            self.notify_error("Could not find a playable video stream on the page.")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())