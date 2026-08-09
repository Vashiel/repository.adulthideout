#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
import urllib.parse
import xbmcgui
import xbmcplugin
import xbmcaddon
import sys
import os
import html
from resources.lib.base_website import BaseWebsite

try:
    addon_path = xbmcaddon.Addon().getAddonInfo('path')
    vendor_path = os.path.join(addon_path, 'resources', 'lib', 'vendor')
    if vendor_path not in sys.path:
        sys.path.insert(0, vendor_path)
except Exception:
    pass

import cloudscraper


class CumLouder(BaseWebsite):
    
    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="cumlouder",
            base_url="https://www.cumlouder.com",
            search_url="https://www.cumlouder.com/search/?q={}",
            addon_handle=addon_handle,
            addon=addon
        )
        self.scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True})
        self.scraper.cookies.set('disclaimer-confirmed', '1', domain='www.cumlouder.com')
        
        self.logo = os.path.join(self.addon.getAddonInfo('path'), 'resources', 'logos', 'cumlouder.png')
        self.icons['default'] = self.logo
        self.icons['search'] = os.path.join(self.addon.getAddonInfo('path'), 'resources', 'logos', 'search.png')
        self.icons['categories'] = os.path.join(self.addon.getAddonInfo('path'), 'resources', 'logos', 'categories.png')

        # Sorting Options
        self.sort_options = ["Newest", "Most Viewed"]
        self.sort_paths = {
            "Newest": "/porn-videos/?orderBy=n",
            "Most Viewed": "/porn-videos/?orderBy=v"
        }

    def make_request(self, url):
        try:
            self.logger.info(f"Requesting: {url}")
            response = self.scraper.get(url, timeout=10)
            if response.status_code == 200:
                return response.text
            else:
                self.logger.error(f"Request failed: {response.status_code}")
                return None
        except Exception as e:
            self.logger.error(f"Request error: {e}")
            return None

    def get_listing(self, url, html_content=None):
        if url == "BOOTSTRAP":
            url, _ = self.get_start_url_and_label()

        if html_content is None:
            html_content = self.make_request(url)
        if not html_content:
            return []

        videos = []
        pattern = re.compile(
            r'<a\s+[^>]*href=["\'](https?://www\.cumlouder\.com/porn-video/[^"\']+|/porn-video/[^"\']+)["\'][^>]*>([\s\S]*?)</a>',
            re.IGNORECASE
        )
        seen = set()
        for match in pattern.finditer(html_content):
            video_url = urllib.parse.urljoin(self.base_url, html.unescape(match.group(1)))
            if video_url in seen:
                continue
            seen.add(video_url)

            block = match.group(2)
            img_match = re.search(r'<img\s+[^>]*src=["\']([^"\']+)["\']', block, re.IGNORECASE)
            if not img_match:
                img_match = re.search(r'<img\s+[^>]*data-src=["\']([^"\']+)["\']', block, re.IGNORECASE)
            thumb = img_match.group(1) if img_match else self.icons['default']

            title_match = re.search(r'alt=["\']([^"\']+)["\']', block, re.IGNORECASE)
            if not title_match:
                title_match = re.search(r'<h[1-6][^>]*>(.*?)</h[1-6]>', block, re.IGNORECASE | re.DOTALL)
            title = html.unescape(title_match.group(1)).strip() if title_match else "CumLouder Video"

            duration_match = re.search(r'class=["\']duration["\'][^>]*>(.*?)</span>', block, re.IGNORECASE | re.DOTALL)
            duration = duration_match.group(1).strip() if duration_match else ""

            label = f"{title} [COLOR lime]({duration})[/COLOR]" if duration else title
            videos.append({"label": label, "url": video_url, "thumb": thumb, "info": {"title": title, "plot": title}})
        return videos

    def process_content(self, url, page=1):
        if not url or url == "BOOTSTRAP":
            url, _ = self.get_start_url_and_label()

        if url == "SEARCH_MENU":
            self.add_dir("New Search", "SEARCH_EXEC", 5, self.icons['search'])
            self.end_directory()
            return

        html_content = self.make_request(url)
        if not html_content:
            self.notify_error("Failed to load page")
            self.end_directory()
            return

        videos = self.get_listing(url, html_content=html_content)
        for v in videos:
            self.add_link(v['label'], v['url'], 4, v['thumb'], self.fanart, info_tag=v['info'])

        next_page_match = re.search(r'<a\s+[^>]*href=["\']([^"\']+)["\'][^>]*>Next\s*&raquo;</a>', html_content, re.IGNORECASE)
        if next_page_match:
            next_url = urllib.parse.urljoin(self.base_url, html.unescape(next_page_match.group(1)))
            self.add_dir("Next Page >>", next_url, 2, self.icons['default'])

        self.end_directory()

    def play_video(self, url):
        html_content = self.make_request(url)
        if not html_content:
            self.notify_error("Failed to load video page")
            return

        video_match = re.search(r'<source\s+[^>]*src=["\']([^"\']+)["\']', html_content, re.IGNORECASE)
        if not video_match:
            video_match = re.search(r'file:\s*["\']([^"\']+)["\']', html_content, re.IGNORECASE)

        if video_match:
            stream_url = html.unescape(video_match.group(1))
            item = xbmcgui.ListItem(path=stream_url)
            item.setProperty('IsPlayable', 'true')
            item.setMimeType('video/mp4')
            xbmcplugin.setResolvedUrl(self.addon_handle, True, item)
        else:
            self.notify_error("Video stream not found")
