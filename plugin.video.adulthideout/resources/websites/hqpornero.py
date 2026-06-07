#!/usr/bin/env python
# -*- coding: utf-8 -*-

import html
import re
import sys
import urllib.parse

import requests
import xbmc
import xbmcgui
import xbmcplugin

from resources.lib.base_website import BaseWebsite


class HQPornero(BaseWebsite):
    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="hqpornero",
            base_url="https://hqpornero.com/",
            search_url="https://hqpornero.com/search/{}.html",
            addon_handle=addon_handle,
            addon=addon,
        )
        self.label = "HQPornero"
        self.session = requests.Session()
        self.ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        )

    def _headers(self, referer=None, accept="text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"):
        return {
            "User-Agent": self.ua,
            "Referer": referer or self.base_url,
            "Accept": accept,
            "Accept-Language": "en-US,en;q=0.9",
        }

    def _get(self, url, referer=None, max_retries=2):
        last_error = None
        for attempt in range(1, max_retries + 1):
            try:
                response = self.session.get(url, headers=self._headers(referer), timeout=15)
                if response.status_code == 200:
                    return response.text
                last_error = "HTTP {}".format(response.status_code)
                self.logger.warning("HQPornero HTTP %s for %s", response.status_code, url)
            except Exception as exc:
                last_error = exc
                self.logger.warning("HQPornero request error for %s: %s", url, exc)
                self.session = requests.Session()
            if attempt < max_retries:
                xbmc.sleep(650 * attempt)
        self.logger.error("HQPornero failed to fetch %s: %s", url, last_error)
        return ""

    def _absolute(self, value, base=None):
        if not value:
            return ""
        value = html.unescape(value).strip()
        if value.startswith("//"):
            value = "https:" + value
        return urllib.parse.urljoin(base or self.base_url, value)

    def _clean(self, value):
        value = re.sub(r"<[^>]+>", " ", value or "")
        value = value.replace("-HQPORNERO.COM", "")
        return re.sub(r"\s+", " ", html.unescape(value)).strip()

    def _slug(self, query):
        return re.sub(r"[^a-z0-9]+", "-", (query or "").lower()).strip("-")

    def get_start_url_and_label(self):
        return self.base_url, self.label

    def _context_menu(self):
        return [
            (
                "Sort by...",
                "RunPlugin({}?mode=7&action=select_sort&website={})".format(sys.argv[0], self.name),
            )
        ]

    def get_page_url(self, base_url, page_num):
        if page_num <= 1:
            return base_url
        parsed = urllib.parse.urlparse(base_url)
        if parsed.path in ("", "/") or re.search(r"/page/\d+\.html$", parsed.path):
            return self._absolute("/page/{:02d}.html".format(page_num))
        return base_url

    def _extract_videos(self, html_content):
        videos = []
        seen = set()
        blocks = re.split(r'(?=<div\b[^>]+class=["\']thumb["\'])', html_content or "", flags=re.IGNORECASE)
        for block in blocks:
            href_match = re.search(r'<a\b[^>]+href=["\']([^"\']*/pornhd/[^"\']+\.html)["\']', block, re.IGNORECASE)
            if not href_match:
                continue
            video_url = self._absolute(href_match.group(1))
            if not video_url or video_url in seen:
                continue
            seen.add(video_url)

            title_match = re.search(r'class=["\']titlethumb["\'][^>]*(?:title=["\']([^"\']+)["\'])?[^>]*>([\s\S]*?)</div>', block, re.IGNORECASE)
            title = self._clean((title_match.group(1) or title_match.group(2)) if title_match else "")
            if not title:
                img_alt = re.search(r'\salt=["\']([^"\']+)["\']', block, re.IGNORECASE)
                title = self._clean(img_alt.group(1) if img_alt else "")
            if not title:
                continue

            thumb = ""
            img_match = re.search(r"<img\b[^>]*>", block, re.IGNORECASE)
            img_tag = img_match.group(0) if img_match else ""
            for attr in ("data-src", "src"):
                thumb_match = re.search(r'\s{}=["\']([^"\']+)["\']'.format(attr), img_tag, re.IGNORECASE)
                if thumb_match:
                    thumb = self._absolute(thumb_match.group(1))
                    break
            if "lazy-load" in thumb:
                thumb = self.icon

            videos.append({"label": title, "url": video_url, "thumb": thumb or self.icon, "info": {"title": title, "plot": title}})
        return videos

    def _extract_next_page(self, html_content, current_url, page):
        next_page = page + 1
        if re.search(r'href=["\']/page/{:02d}\.html["\']'.format(next_page), html_content or "", re.IGNORECASE):
            return self.get_page_url(current_url, next_page)
        return None

    def process_content(self, url, page=1):
        if not url or url == "BOOTSTRAP":
            url = self.base_url
        target_url = self.get_page_url(url, page)
        html_content = self._get(target_url)
        if not html_content:
            self.notify_error("Could not load HQPornero listing")
            self.end_directory("videos")
            return
        if page == 1 and urllib.parse.urlparse(url).path in ("", "/"):
            self.add_dir("Search", "", 5, self.icons.get("search", self.icon), context_menu=self._context_menu())
        videos = self._extract_videos(html_content)
        if not videos:
            self.notify_error("No HQPornero videos found")
            return self.end_directory("videos")
        for item in videos:
            self.add_link(item["label"], item["url"], 4, item["thumb"], self.fanart, context_menu=self._context_menu(), info_labels=item["info"])
        if self._extract_next_page(html_content, target_url, page):
            self.add_dir("Next Page", url, 2, self.icons.get("default", self.icon), context_menu=self._context_menu(), page=page + 1)
        self.end_directory("videos")

    def search(self, query):
        if query:
            self.process_content(self.search_url.format(self._slug(query.strip())))

    def _extract_streams(self, html_content, base_url):
        streams = []
        for src, quality in re.findall(r'<source\b[^>]+src=["\']([^"\']+\.mp4[^"\']*)["\'][^>]+title=["\']([^"\']+)["\']', html_content or "", re.IGNORECASE):
            q_match = re.search(r"(\d+)", quality)
            streams.append((int(q_match.group(1)) if q_match else 0, self._absolute(src, base_url)))
        for href, quality in re.findall(r'<a\b[^>]+href=["\']([^"\']+\.mp4[^"\']*)["\'][^>]*>([^<]+)</a>', html_content or "", re.IGNORECASE):
            q_match = re.search(r"(\d+)", quality)
            streams.append((int(q_match.group(1)) if q_match else 0, self._absolute(href, base_url)))
        streams.sort(key=lambda item: item[0], reverse=True)
        return [url for _, url in streams]

    def resolve_recording_stream(self, url):
        detail_html = self._get(url, referer=self.base_url)
        embed_match = re.search(r'<iframe\b[^>]+src=["\']([^"\']+)["\']', detail_html or "", re.IGNORECASE)
        if not embed_match:
            return None
        embed_url = self._absolute(embed_match.group(1), url)
        embed_html = self._get(embed_url, referer=url)
        player_match = re.search(r'<iframe\b[^>]+src=["\']([^"\']+)["\']', embed_html or "", re.IGNORECASE)
        if not player_match:
            return None
        player_url = self._absolute(player_match.group(1), embed_url)
        player_html = self._get(player_url, referer=embed_url)
        streams = self._extract_streams(player_html, player_url)
        if not streams:
            return None
        return {"url": streams[0], "headers": self._headers(player_url, accept="*/*"), "extension": "mp4"}

    def play_video(self, url):
        resolved = self.resolve_recording_stream(url)
        if not resolved:
            self.notify_error("Could not resolve HQPornero stream")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return
        play_url = resolved["url"]
        headers = resolved.get("headers") or {}
        if headers:
            play_url = "{}|{}".format(play_url, urllib.parse.urlencode(headers))
        list_item = xbmcgui.ListItem(path=play_url)
        list_item.setProperty("IsPlayable", "true")
        list_item.setMimeType("video/mp4")
        list_item.setContentLookup(False)
        xbmcplugin.setResolvedUrl(self.addon_handle, True, list_item)
