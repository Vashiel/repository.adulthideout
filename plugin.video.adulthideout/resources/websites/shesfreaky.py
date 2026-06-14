#!/usr/bin/env python
# -*- coding: utf-8 -*-

import html
import re
import sys
import urllib.parse

import requests
import xbmcgui
import xbmcplugin

from resources.lib.base_website import BaseWebsite
from resources.lib.resilient_http import fetch_text


class ShesFreaky(BaseWebsite):
    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="shesfreaky",
            base_url="https://www.shesfreaky.com/",
            search_url="https://www.shesfreaky.com/search/videos/{}/page1.html",
            addon_handle=addon_handle,
            addon=addon,
        )
        self.label = "ShesFreaky"
        self.session = requests.Session()
        self.ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        )
        self.sort_options = ["Newest", "Featured", "Top Rated", "Most Viewed"]
        self.sort_paths = {
            "Newest": "/videos/",
            "Featured": "/featured/",
            "Top Rated": "/top-rated/",
            "Most Viewed": "/most-viewed/",
        }

    def _headers(self, referer=None, accept="text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"):
        return {
            "User-Agent": self.ua,
            "Accept": accept,
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "identity",
            "Referer": referer or self.base_url,
        }

    def _get(self, url, referer=None):
        try:
            response = self.session.get(url, headers=self._headers(referer), timeout=20)
            if response.status_code == 200:
                return response.text
            self.logger.warning("ShesFreaky HTTP %s for %s", response.status_code, url)
        except Exception as exc:
            self.logger.warning("ShesFreaky request failed for %s: %s", url, exc)
            self.session = requests.Session()

        return fetch_text(
            url,
            headers=self._headers(referer),
            logger=self.logger,
            timeout=20,
            use_windows_curl_fallback=True,
        ) or ""

    def _absolute(self, value, base=None):
        if not value:
            return ""
        value = html.unescape(value).strip()
        if value.startswith("//"):
            value = "https:" + value
        return urllib.parse.urljoin(base or self.base_url, value)

    def _clean(self, value):
        value = re.sub(r"<[^>]+>", " ", value or "")
        return re.sub(r"\s+", " ", html.unescape(value)).strip()

    def _slug(self, value):
        return urllib.parse.quote_plus((value or "").strip().lower())

    def _get_sort_key(self):
        try:
            idx = int(self.addon.getSetting("shesfreaky_sort_by") or "0")
        except Exception:
            idx = 0
        if idx < 0 or idx >= len(self.sort_options):
            idx = 0
        return self.sort_options[idx]

    def get_start_url_and_label(self):
        sort_key = self._get_sort_key()
        return self._absolute(self.sort_paths.get(sort_key, "/videos/")), "{} [COLOR yellow]{}[/COLOR]".format(self.label, sort_key)

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
        path = parsed.path
        if re.search(r"/page\d+\.html$", path, re.IGNORECASE):
            path = re.sub(r"/page\d+\.html$", "/page{}.html".format(page_num), path, flags=re.IGNORECASE)
        elif path.rstrip("/").endswith("/videos"):
            path = "/videos/page{}.html".format(page_num)
        else:
            path = path.rstrip("/") + "/page{}.html".format(page_num)
        return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, path, parsed.params, parsed.query, parsed.fragment))

    def _is_top_listing(self, url):
        path = urllib.parse.urlparse(url or self.base_url).path.rstrip("/")
        return path in ("", "/videos", "/featured", "/top-rated", "/most-viewed")

    def _extract_videos(self, html_content):
        videos = []
        seen = set()
        blocks = re.split(r'(?=<div\b[^>]+class=["\'][^"\']*\bitem\b)', html_content or "", flags=re.IGNORECASE)
        for block in blocks:
            href_match = re.search(r'<a\b[^>]+href=["\']([^"\']*/video/[^"\']+\.html)["\']', block, re.IGNORECASE)
            if not href_match:
                continue
            video_url = self._absolute(href_match.group(1))
            if video_url in seen:
                continue
            seen.add(video_url)

            title_match = re.search(r'<div\b[^>]+class=["\']item-title["\'][^>]*>\s*<a[^>]*>([\s\S]*?)</a>', block, re.IGNORECASE)
            title = self._clean(title_match.group(1) if title_match else "")
            if not title:
                slug = urllib.parse.urlparse(video_url).path.rsplit("/", 1)[-1]
                title = re.sub(r"-\d+\.html$", "", slug).replace("-", " ").title()

            img_match = re.search(r"<img\b[^>]*>", block, re.IGNORECASE)
            img_tag = img_match.group(0) if img_match else ""
            thumb = ""
            for attr in ("data-original", "data-src", "src"):
                thumb_match = re.search(r'\s{}=["\']([^"\']+)["\']'.format(attr), img_tag, re.IGNORECASE)
                if thumb_match:
                    thumb = self._absolute(thumb_match.group(1))
                    break

            duration_match = re.search(r'<span\b[^>]+class=["\']thumb-length["\'][^>]*>([\s\S]*?)</span>', block, re.IGNORECASE)
            duration = self._clean(duration_match.group(1)) if duration_match else ""
            seconds = self.convert_duration(duration)
            label = "{} [COLOR lime]({})[/COLOR]".format(title, duration) if duration else title
            info = {"title": title, "plot": title}
            if seconds:
                info["duration"] = seconds
            videos.append({"label": label, "url": video_url, "thumb": thumb or self.icon, "info": info})
        return videos

    def _extract_next_page(self, html_content, current_url, page):
        next_url = self.get_page_url(current_url, page + 1)
        next_path = urllib.parse.urlparse(next_url).path
        if re.search(r'href=["\'][^"\']*{}["\']'.format(re.escape(next_path)), html_content or "", re.IGNORECASE):
            return next_url
        if re.search(r'>\s*Next\s*(?:&raquo;|»)?\s*<', html_content or "", re.IGNORECASE):
            return next_url
        return None

    def process_content(self, url, page=1):
        if not url or url == "BOOTSTRAP":
            url, _ = self.get_start_url_and_label()
        target_url = self.get_page_url(url, page)
        html_content = self._get(target_url)
        if not html_content:
            self.notify_error("Could not load ShesFreaky listing")
            return self.end_directory("videos")

        context_menu = self._context_menu()
        if page == 1 and self._is_top_listing(url):
            self.add_dir("Search", "", 5, self.icons.get("search", self.icon), context_menu=context_menu)
            self.add_dir("Categories", self.base_url + "categories/", 8, self.icons.get("categories", self.icon), context_menu=context_menu)

        videos = self._extract_videos(html_content)
        if not videos:
            self.notify_error("No ShesFreaky videos found")
            return self.end_directory("videos")
        for item in videos:
            self.add_link(item["label"], item["url"], 4, item["thumb"], self.fanart, context_menu=context_menu, info_labels=item["info"])

        next_url = self._extract_next_page(html_content, target_url, page)
        if next_url:
            self.add_dir("Next Page", url, 2, self.icons.get("default", self.icon), context_menu=context_menu, page=page + 1)
        self.end_directory("videos")

    def process_categories(self, url):
        html_content = self._get(url or self.base_url)
        if not html_content:
            self.notify_error("Could not load ShesFreaky categories")
            return self.end_directory("videos")

        seen = set()
        for href, label in re.findall(r'<a\b[^>]+href=["\']([^"\']*search/videos/[^"\']+/page1\.html)["\'][^>]*>([\s\S]*?)</a>', html_content, re.IGNORECASE):
            category_url = self._absolute(href)
            if category_url in seen:
                continue
            seen.add(category_url)
            title = self._clean(label)
            if title:
                self.add_dir(title, category_url, 2, self.icons.get("categories", self.icon), self.fanart)
        self.end_directory("videos")

    def search(self, query):
        if query:
            self.process_content(self.search_url.format(self._slug(query)))

    def _extract_streams(self, html_content):
        streams = []
        for value in re.findall(r'<source\b[^>]+src=["\']([^"\']+\.mp4[^"\']*)["\']', html_content or "", re.IGNORECASE):
            streams.append(self._absolute(value))
        for value in re.findall(r'https?://[^"\']+\.mp4\?[^"\']+', html_content or "", re.IGNORECASE):
            if "/p_" not in value:
                streams.append(self._absolute(value))
        deduped = []
        seen = set()
        for stream_url in streams:
            if stream_url not in seen:
                seen.add(stream_url)
                deduped.append(stream_url)
        return deduped

    def resolve_recording_stream(self, url):
        html_content = self._get(url, referer=self.base_url)
        streams = self._extract_streams(html_content)
        if not streams:
            return None
        return {"url": streams[0], "headers": self._headers(url, accept="*/*"), "extension": "mp4"}

    def play_video(self, url):
        resolved = self.resolve_recording_stream(url)
        if not resolved:
            self.notify_error("Could not resolve ShesFreaky stream")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return
        play_url = resolved["url"]
        headers = resolved.get("headers") or {}
        if headers:
            play_url = "{}|{}".format(play_url, urllib.parse.urlencode(headers))
        item = xbmcgui.ListItem(path=play_url)
        item.setProperty("IsPlayable", "true")
        item.setMimeType("video/mp4")
        item.setContentLookup(False)
        xbmcplugin.setResolvedUrl(self.addon_handle, True, item)
