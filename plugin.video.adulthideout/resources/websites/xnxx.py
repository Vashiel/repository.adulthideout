#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
import sys
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar
from io import BytesIO
import gzip
import html
import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon
from resources.lib.base_website import BaseWebsite

try:
    addon_path = xbmcaddon.Addon().getAddonInfo('path')
    vendor_path = os.path.join(addon_path, 'resources', 'lib', 'vendor')
    if vendor_path not in sys.path:
        sys.path.insert(0, vendor_path)
except Exception:
    pass

import requests


class Xnxx(BaseWebsite):
    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name='xnxx',
            base_url='https://www.xnxx.com',
            search_url='https://www.xnxx.com/search/{}',
            addon_handle=addon_handle,
            addon=addon
        )
        self.display_name = 'XNXX'
        
        self.sort_options = ['Relevance', 'Best / Hits', 'Newest (Date)', 'This Month', 'This Year', 'Random']
        self.duration_options = ['All Durations', 'Short (0-10 min)', 'Medium (10-20 min)', 'Long (10 min+)', 'Extra Long (20 min+)']
        self.quality_options = ['All Qualities', '720p+ (HD)', '1080p+ (Full HD)']
        self.content_options = ['Straight', 'Gay', 'Trans']
        
        self.setting_id_sort = "xnxx_sort_order"
        self.setting_id_content = "xnxx_content_type"
        self.setting_id_duration = "xnxx_duration"
        self.setting_id_quality = "xnxx_quality"

        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': self.base_url
        })

    def make_request(self, url, headers=None):
        try:
            req_headers = {'Referer': self.base_url}
            if headers:
                req_headers.update(headers)
            res = self.session.get(url, headers=req_headers, timeout=20)
            if res.status_code == 200:
                return res.text
        except Exception as exc:
            self.logger.error(f"[XNXX] Request failed for {url}: {exc}")
        return None

    def get_current_content_key(self):
        try:
            content_index = int(self.addon.getSetting(self.setting_id_content) or '0')
        except (ValueError, TypeError):
            content_index = 0
        if not 0 <= content_index < len(self.content_options):
            content_index = 0
        return content_index

    def get_current_sort_idx(self):
        try:
            sort_index = int(self.addon.getSetting(self.setting_id_sort) or '0')
        except (ValueError, TypeError):
            sort_index = 0
        if not 0 <= sort_index < len(self.sort_options):
            sort_index = 0
        return sort_index

    def get_current_duration_idx(self):
        try:
            dur_index = int(self.addon.getSetting(self.setting_id_duration) or '0')
        except (ValueError, TypeError):
            dur_index = 0
        if not 0 <= dur_index < len(self.duration_options):
            dur_index = 0
        return dur_index

    def get_current_quality_idx(self):
        try:
            qual_index = int(self.addon.getSetting(self.setting_id_quality) or '0')
        except (ValueError, TypeError):
            qual_index = 0
        if not 0 <= qual_index < len(self.quality_options):
            qual_index = 0
        return qual_index

    def build_search_path(self, query="", page=1):
        content_idx = self.get_current_content_key()
        sort_idx = self.get_current_sort_idx()
        dur_idx = self.get_current_duration_idx()
        qual_idx = self.get_current_quality_idx()

        dur_map = {1: "0-10min", 2: "10-20min", 3: "10min+", 4: "20min+"}
        qual_map = {1: "hd-only", 2: "fullhd"}
        sort_map = {0: "relevance", 1: "hits", 2: "date", 3: "month", 4: "year", 5: "random"}

        filters = []
        if qual_idx in qual_map:
            filters.append(qual_map[qual_idx])
        if dur_idx in dur_map:
            filters.append(dur_map[dur_idx])
        if sort_idx in sort_map and sort_map[sort_idx] != "relevance":
            filters.append(sort_map[sort_idx])

        query_str = urllib.parse.quote_plus(query) if query else ""
        
        if filters:
            filter_path = "/".join(filters)
            if query_str:
                if page > 1:
                    path = f"/search/{filter_path}/{query_str}/{page - 1}"
                else:
                    path = f"/search/{filter_path}/{query_str}"
            else:
                if page > 1:
                    path = f"/search/{filter_path}/{page - 1}"
                else:
                    path = f"/search/{filter_path}"
        else:
            if query_str:
                if page > 1:
                    path = f"/search/{query_str}/{page - 1}"
                else:
                    path = f"/search/{query_str}"
            else:
                if content_idx == 1:
                    base_browse = "/gay"
                elif content_idx == 2:
                    base_browse = "/shemale"
                else:
                    base_browse = "/search/hits"

                if page > 1:
                    path = f"{base_browse}/{page - 1}"
                else:
                    path = base_browse

        return path

    def get_start_url_and_label(self):
        content_key = self.content_options[self.get_current_content_key()]
        sort_key = self.sort_options[self.get_current_sort_idx()]
        url = urllib.parse.urljoin(self.base_url, self.build_search_path())
        label = f"{self.display_name} [COLOR yellow]({content_key} - {sort_key})[/COLOR]"
        return url, label

    def get_global_context_menu(self, current_url=""):
        encoded_url = urllib.parse.quote_plus(current_url or self.base_url)
        return [
            ('Select Sort...', f'RunPlugin({sys.argv[0]}?mode=7&action=select_sort&website={self.name}&original_url={encoded_url})'),
            ('Select Duration...', f'RunPlugin({sys.argv[0]}?mode=7&action=select_duration&website={self.name}&original_url={encoded_url})'),
            ('Select Quality...', f'RunPlugin({sys.argv[0]}?mode=7&action=select_quality&website={self.name}&original_url={encoded_url})'),
            ('Select Content Type...', f'RunPlugin({sys.argv[0]}?mode=7&action=select_content_type&website={self.name}&original_url={encoded_url})')
        ]

    def add_basic_dirs(self, current_url):
        context_menu = self.get_global_context_menu(current_url)
        self.add_dir('[COLOR blue]Search[/COLOR]', '', 5, self.icons['search'], self.fanart, context_menu=context_menu)

    def process_content(self, url):
        if not url or url == "BOOTSTRAP" or url.rstrip('/') == self.base_url:
            url, _ = self.get_start_url_and_label()

        self.add_basic_dirs(url)

        content = self.make_request(url)
        if not content:
            self.notify_error("Failed to load page")
            self.end_directory()
            return

        self.process_video_list(content, url)
        self.end_directory()

    def process_video_list(self, content, current_url):
        context_menu = self.get_global_context_menu(current_url)
        items = []
        seen = set()

        blocks = re.split(r'<div[^>]*class="[^"]*thumb-block[^"]*"', content)[1:]

        for b in blocks:
            href_m = re.search(r'href="(/video-[^"]+)"', b)
            if not href_m: continue
            href = href_m.group(1)
            full_url = urllib.parse.urljoin(self.base_url, href)
            if full_url in seen: continue
            seen.add(full_url)

            title_m = re.search(r'class="title"[^>]*title="([^"]+)"', b)
            if not title_m:
                title_m = re.search(r'class="title"[^>]*>([^<]+)<', b)
            if not title_m:
                title_m = re.search(r'title="([^"]+)"', b)
            title = html.unescape(title_m.group(1).strip()) if title_m else "XNXX Video"

            thumb_m = re.search(r'data-src="([^"]+)"', b)
            if not thumb_m or 'blank.gif' in thumb_m.group(1):
                thumb_m = re.search(r'src="([^"]+)"', b)
            thumb = thumb_m.group(1) if thumb_m else ""

            dur_m = re.search(r'class="metadata">\s*<span class="left">\s*([^<\s]+)', b)
            if not dur_m:
                dur_m = re.search(r'class="duration">([^<]+)', b)
            dur = dur_m.group(1).strip() if dur_m else ""

            items.append((full_url, title, thumb, dur))

        if not items:
            anchors = re.findall(r'<a[^>]+href="(/video-[^"]+)"[^>]*title="([^"]+)".*?(?:data-src|src)="([^"]+)"', content, re.DOTALL | re.IGNORECASE)
            for href, title, thumb in anchors:
                full_url = urllib.parse.urljoin(self.base_url, href)
                if full_url not in seen:
                    seen.add(full_url)
                    items.append((full_url, html.unescape(title.strip()), thumb, ""))

        added = 0
        for full_url, title, thumb, dur_str in items:
            display_title = title
            if dur_str:
                display_title = f"{title} [COLOR yellow]({dur_str})[/COLOR]"

            info = {'mediatype': 'video'}
            if dur_str:
                info['plot'] = f"Duration: {dur_str}"

            self.add_link(display_title, full_url, 4, thumb, self.fanart, info_labels=info, context_menu=context_menu)
            added += 1

        self.logger.info(f"[XNXX] Found {added} videos")

        # Next page detection
        next_match = re.search(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*class=["\'][^"\']*\bnext\b[^"\']*["\']', content, re.I)
        if not next_match:
            next_match = re.search(r'<a[^>]+class=["\'][^"\']*\bnext\b[^"\']*["\'][^>]*href=["\']([^"\']+)["\']', content, re.I)
        if not next_match:
            next_match = re.search(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>\s*Next\s*</a>', content, re.I)
        
        if next_match:
            next_url = urllib.parse.urljoin(self.base_url, html.unescape(next_match.group(1)))
            self.add_dir('[COLOR blue]Next Page >>>>[/COLOR]', next_url, 2, self.icons['default'], self.fanart, context_menu=context_menu)

    def select_sort(self, original_url=None):
        dialog = xbmcgui.Dialog()
        idx = dialog.select("Select Sort...", self.sort_options, preselect=self.get_current_sort_idx())
        if idx != -1:
            self.addon.setSetting(self.setting_id_sort, str(idx))
            xbmc.executebuiltin(f'Container.Update({sys.argv[0]}?mode=2&url=BOOTSTRAP&website={self.name},replace)')

    def select_duration(self, original_url=None):
        dialog = xbmcgui.Dialog()
        idx = dialog.select("Select Duration...", self.duration_options, preselect=self.get_current_duration_idx())
        if idx != -1:
            self.addon.setSetting(self.setting_id_duration, str(idx))
            xbmc.executebuiltin(f'Container.Update({sys.argv[0]}?mode=2&url=BOOTSTRAP&website={self.name},replace)')

    def select_quality(self, original_url=None):
        dialog = xbmcgui.Dialog()
        idx = dialog.select("Select Quality...", self.quality_options, preselect=self.get_current_quality_idx())
        if idx != -1:
            self.addon.setSetting(self.setting_id_quality, str(idx))
            xbmc.executebuiltin(f'Container.Update({sys.argv[0]}?mode=2&url=BOOTSTRAP&website={self.name},replace)')

    def select_content_type(self, original_url=None):
        dialog = xbmcgui.Dialog()
        idx = dialog.select("Select Content Type...", self.content_options, preselect=self.get_current_content_key())
        if idx != -1:
            self.addon.setSetting(self.setting_id_content, str(idx))
            xbmc.executebuiltin(f'Container.Update({sys.argv[0]}?mode=2&url=BOOTSTRAP&website={self.name},replace)')

    def play_video(self, url):
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': url
        }
        content = self.make_request(url, headers=headers)
        if not content:
            return self.notify_error("Failed to load video page")

        high_url = re.search(r"html5player\.setVideoUrlHigh\('([^']+)'\)", content)
        low_url = re.search(r"html5player\.setVideoUrlLow\('([^']+)'\)", content)
        hls_url = re.search(r"html5player\.setVideoHLS\('([^']+)'\)", content)

        stream_url = None
        if high_url:
            stream_url = high_url.group(1)
        elif hls_url:
            stream_url = hls_url.group(1)
        elif low_url:
            stream_url = low_url.group(1)

        if stream_url:
            item = xbmcgui.ListItem(path=stream_url)
            item.setProperty('IsPlayable', 'true')
            item.setMimeType('video/mp4' if not stream_url.endswith('.m3u8') else 'application/x-mpegURL')
            xbmcplugin.setResolvedUrl(self.addon_handle, True, item)
        else:
            self.notify_error("Could not find video stream URL")

    def search(self, query):
        if query:
            search_path = self.build_search_path(query=query)
            search_url = urllib.parse.urljoin(self.base_url, search_path)
            self.process_content(search_url)
        else:
            self.end_directory()
