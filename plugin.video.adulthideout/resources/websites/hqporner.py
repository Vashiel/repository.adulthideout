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
import xbmcvfs
import os

from resources.lib.base_website import BaseWebsite

class HQPorner(BaseWebsite):
    def __init__(self, addon_handle):
        super(HQPorner, self).__init__(
            name='hqporner',
            base_url='https://hqporner.com',
            search_url='https://hqporner.com/?q={}',
            addon_handle=addon_handle
        )
        self.sort_options = ['Newest', 'Top Rated', 'Most Viewed (Month)', 'Most Viewed (Week)']
        self.sort_paths = {
            'Newest': '/',
            'Top Rated': '/top',
            'Most Viewed (Month)': '/top/month',
            'Most Viewed (Week)': '/top/week',
        }
        self.cookie_jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cookie_jar))
        self.opener.addheaders = [('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')]
        urllib.request.install_opener(self.opener)

    def _get_html(self, url, referer=None, extra_headers=None):
        max_retries = int(self.addon.getSetting('max_retry_attempts') or 3)
        for attempt in range(max_retries):
            try:
                headers = {
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                }
                if referer:
                    headers['Referer'] = referer
                if extra_headers:
                    headers.update(extra_headers)
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=30) as response:
                    if response.getcode() == 200:
                        return response.read().decode('utf-8', errors='ignore')
                    else:
                        self.logger.error(f"HQPorner: HTTP {response.getcode()} for {url}")
                        return None
            except urllib.error.HTTPError as e:
                self.logger.error(f"HQPorner: HTTP Error {e.code} for {url}: {e.reason}")
                if attempt < max_retries - 1:
                    self.logger.info(f"Retrying ({attempt + 1}/{max_retries})...")
                    continue
                return None
            except Exception as e:
                self.logger.error(f"HQPorner: Request failed for {url}: {e}")
                if attempt < max_retries - 1:
                    self.logger.info(f"Retrying ({attempt + 1}/{max_retries})...")
                    continue
                return None
        return None

    def _check_url(self, url, referer):
        try:
            req = urllib.request.Request(url, method='HEAD', headers={'Referer': referer})
            with urllib.request.urlopen(req, timeout=10) as response:
                return response.getcode() == 200
        except:
            return False

    def _save_debug_html(self, content, filename):
        debug_path = xbmcvfs.translatePath(self.addon.getAddonInfo('profile'))
        if not xbmcvfs.exists(debug_path):
            xbmcvfs.mkdirs(debug_path)
        with open(os.path.join(debug_path, filename), 'w', encoding='utf-8') as f:
            f.write(content)

    def _parse_duration(self, duration_str):
        seconds = 0
        try:
            parts = duration_str.strip().split()
            for part in parts:
                if 'h' in part: seconds += int(part.replace('h', '')) * 3600
                elif 'm' in part: seconds += int(part.replace('m', '')) * 60
                elif 's' in part: seconds += int(part.replace('s', ''))
        except (ValueError, TypeError): return 0
        return seconds

    def process_content(self, url):
        context_menu_items = [
            ('Sort by...', f'RunPlugin({sys.argv[0]}?mode=7&website={self.name}&action=select_sort&original_url={urllib.parse.quote_plus(url)})')
        ]

        self.add_dir('[COLOR blue]Search...[/COLOR]', self.base_url, 5, icon=self.icons['search'], fanart=self.fanart, context_menu=context_menu_items)
        self.add_dir('[COLOR blue]Categories...[/COLOR]', self.base_url, 8, icon=self.icons['categories'], fanart=self.fanart, context_menu=context_menu_items)

        html_content = self._get_html(url)
        if not html_content:
            self.notify_error("Failed to load page content.")
            self.end_directory()
            return

        try:
            video_pattern = re.compile(
                r'<a href="(/hdporn/[^"]+)".*?<img.*?src="([^"]+)".*?alt="([^"]+)".*?<span class="icon fa-clock-o meta-data">([^<]+)</span>',
                re.DOTALL
            )
            matches = video_pattern.findall(html_content)

            if not matches: self.notify_info("No videos found on this page.")

            for video_path, thumb_url, title, duration_str in matches:
                video_url = urllib.parse.urljoin(self.base_url, video_path)
                thumbnail = f"https:{thumb_url}"
                duration = self._parse_duration(duration_str)
                info_labels = {'title': title, 'duration': duration, 'plot': title}
                self.add_link(name=title, url=video_url, mode=4, icon=thumbnail, fanart=self.fanart, info_labels=info_labels, context_menu=context_menu_items)

            next_page_match = re.search(r'<li><a href="([^"]+)" class="button[^"]*?pagi-btn">Next</a></li>', html_content)
            if not next_page_match:
                 next_page_match = re.search(r'<a href="([^"]+)" class="button mobile-pagi pagi-btn">Next</a>', html_content)
            
            if next_page_match:
                next_url = next_page_match.group(1).replace('&amp;', '&')
                next_page_url = urllib.parse.urljoin(self.base_url, next_url)
                self.add_dir('[COLOR blue]Next Page >>[/COLOR]', next_page_url, 2, context_menu=context_menu_items)

        except Exception as e:
            self.logger.error(f"HQPorner: Error parsing content: {e}")
            self.notify_error("Failed to parse the webpage.")

        self.end_directory()

    def process_categories(self, url):
        categories_url = url or 'https://hqporner.com/categories'
        html_content = self._get_html(categories_url)
        if not html_content:
            self.notify_error("Failed to load categories page.")
            self.end_directory()
            return

        try:
            category_pattern = re.compile(
                r'<a href="(/category/[^"]+)"[^>]*>([^<]+)</a>',
                re.DOTALL | re.IGNORECASE
            )
            matches = category_pattern.findall(html_content)

            if not matches:
                self.notify_info("No categories found.")
                self.end_directory()
                return

            seen = set()
            for cat_path, cat_title in matches:
                cat_title = cat_title.strip()
                if not cat_title or cat_title.lower() in seen:
                    continue
                seen.add(cat_title.lower())
                cat_url = urllib.parse.urljoin(self.base_url, cat_path)
                self.add_dir(cat_title.capitalize(), cat_url, 2, icon=self.icons['categories'])

        except Exception as e:
            self.logger.error(f"HQPorner: Error parsing categories: {e}")
            self.notify_error("Failed to parse categories.")

        self.end_directory()

    def play_video(self, url):
        self.logger.info(f"HQPorner: Starting play_video for URL: {url}")
        
        self._get_html(self.base_url)
        hqporner_html = self._get_html(url, referer=self.base_url)  # Referer hinzugefügt
        if not hqporner_html:
            self.logger.error(f"HQPorner: Failed to load main video page. URL: {url}")
            self._save_debug_html("HQPorner: No HTML", f"debug_hqporner_{url[-10:]}.html")
            archive_url = url.replace('/hdporn/', '/archive/')
            self.logger.info(f"HQPorner: Trying archive URL: {archive_url}")
            hqporner_html = self._get_html(archive_url, referer=self.base_url)
            if not hqporner_html:
                self.logger.error(f"HQPorner: Failed to load archive video page. URL: {archive_url}")
                self._save_debug_html("HQPorner: No Archive HTML", f"debug_hqporner_archive_{url[-10:]}.html")
                self.notify_error("This video is no longer available (likely removed or archived).")
                xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
                return
            self._save_debug_html(hqporner_html, f"debug_hqporner_archive_{url[-10:]}.html")
            self.logger.debug(f"HQPorner: Archive video page HTML (first 500 chars): {hqporner_html[:500]}")
        else:
            self._save_debug_html(hqporner_html, f"debug_hqporner_{url[-10:]}.html")
            self.logger.debug(f"HQPorner: Main video page HTML (first 500 chars): {hqporner_html[:500]}")

        mydaddy_match = re.search(r'(?:src|nativeplayer\.php\?i=|altplayer\.php\?i=|player\.php\?i=)[\'"]?\s*([^\'"]*mydaddy\.cc/video/[a-f0-9]+/?(?:&alt)?)', hqporner_html, re.IGNORECASE | re.DOTALL)
        if not mydaddy_match:
            self.logger.error(f"HQPorner: No mydaddy match found in HTML: {hqporner_html[:1000]}")
            self.notify_error("Could not find the embedded video URL.")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return
            
        mydaddy_relative_url = mydaddy_match.group(1).strip()
        if not mydaddy_relative_url.startswith('//'):
            mydaddy_relative_url = '//' + mydaddy_relative_url
        mydaddy_url = 'https:' + mydaddy_relative_url
        self.logger.info(f"HQPorner: Extracted mydaddy URL: {mydaddy_url}")

        mydaddy_html = self._get_html(mydaddy_url, referer=url)
        if not mydaddy_html:
            self.logger.error(f"HQPorner: Failed to load embedded video page: {mydaddy_url}")
            self._save_debug_html("HQPorner: No mydaddy HTML", f"debug_mydaddy_{url[-10:]}.html")
            self.notify_error("Failed to load embedded video page.")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return
        self._save_debug_html(mydaddy_html, f"debug_mydaddy_{url[-10:]}.html")
        self.logger.debug(f"HQPorner: Mydaddy HTML (first 500 chars): {mydaddy_html[:500]}")

        source_matches = re.findall(r'<source\s+src=[\'"]([^\'"]+\.(?:bigcdn\.cc|othercdn\.com)/pubs/[a-f0-9.]+/(\d+)\.mp4)[\'"]', mydaddy_html, re.IGNORECASE | re.DOTALL)
        if source_matches:
            sources = {}
            for full_url, qual_num in source_matches:
                if full_url.startswith('//'):
                    full_url = 'https:' + full_url
                sources[int(qual_num)] = full_url
            self.logger.info(f"HQPorner: Parsed sources from <source> tags: {sources}")
            selected_quality_num = max(sources.keys())
            final_url = sources[selected_quality_num]
            self.logger.info(f"HQPorner: Selected quality: {selected_quality_num}p, URL: {final_url}")
        else:
            self.logger.warning("HQPorner: Could not find <source> tags. Falling back to old method.")
            comment_match = re.search(r'pu://s(\d+)\.(?:bigcdn\.cc|othercdn\.com)/pubs/([a-f0-9.]+?)/', mydaddy_html)
            if comment_match:
                cdn_num, pub_id = comment_match.groups()
                self.logger.info("HQPorner: Extracted from comment.")
            else:
                fallback_match = re.search(r'(?:href|src)=[\'"](//s(\d+)\.(?:bigcdn\.cc|othercdn\.com)/pubs/([a-f0-9.]+?)/\d+\.mp4)', mydaddy_html)
                if fallback_match:
                    cdn_num, pub_id = fallback_match.groups()[1:3]
                    self.logger.info("HQPorner: Extracted from fallback href/src.")
                else:
                    self.logger.error(f"HQPorner: No video path match found in comment or fallback. HTML: {mydaddy_html[:1000]}")
                    self.notify_error("Could not find the video base path.")
                    xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
                    return
            
            video_base_path = f'https://s{cdn_num}.bigcdn.cc/pubs/{pub_id}/'
            quality_matches = re.findall(r'(\d+)\.mp4', mydaddy_html)
            qualities = sorted([q for q in set(quality_matches) if q.isdigit()], key=int, reverse=True)
            for quality in qualities:
                final_url = f"{video_base_path}{quality}.mp4"
                if self._check_url(final_url, mydaddy_url):
                    self.logger.info(f"HQPorner: Valid quality found: {quality}p, URL: {final_url}")
                    break
            else:
                self.notify_error("No valid video qualities found (fallback).")
                xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
                return

        playback_url = f"{final_url}|Referer={mydaddy_url}"
        self.logger.info(f"HQPorner: Playback URL: {playback_url}")
        
        list_item = xbmcgui.ListItem(path=playback_url)
        xbmcplugin.setResolvedUrl(self.addon_handle, True, list_item)