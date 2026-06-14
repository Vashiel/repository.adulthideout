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
from resources.lib.proxy_utils import PlaybackGuard, ProxyController
from resources.lib.resilient_http import fetch_text


class JizzBerry(BaseWebsite):
    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="jizzberry",
            base_url="https://jizzberry.com/",
            search_url="https://jizzberry.com/s/{}/",
            addon_handle=addon_handle,
            addon=addon,
        )
        self.label = "JizzBerry"
        self.session = requests.Session()
        self.ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        )
        self.sort_options = ["Newest", "Top"]
        self.sort_paths = {
            "Newest": "/newest/",
            "Top": "/top/",
        }
        self.blocked_category_terms = ("gay", "boy", "male", "indian", "hindi", "desi")

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
            response = self.session.get(url, headers=self._headers(referer), timeout=20, allow_redirects=True)
            if response.status_code == 200:
                return response.text
            self.logger.warning("JizzBerry HTTP %s for %s", response.status_code, url)
        except Exception as exc:
            self.logger.warning("JizzBerry request failed for %s: %s", url, exc)
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

    def _search_slug(self, value):
        return urllib.parse.quote_plus((value or "").strip().replace(" ", "+"))

    def _get_sort_key(self):
        try:
            idx = int(self.addon.getSetting("jizzberry_sort_by") or "0")
        except Exception:
            idx = 0
        if idx < 0 or idx >= len(self.sort_options):
            idx = 0
        return self.sort_options[idx]

    def get_start_url_and_label(self):
        sort_key = self._get_sort_key()
        return self._absolute(self.sort_paths.get(sort_key, "/newest/")), "{} [COLOR yellow]{}[/COLOR]".format(self.label, sort_key)

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
        path = parsed.path.rstrip("/")
        if re.search(r"/\d+$", path):
            path = re.sub(r"/\d+$", "/{}".format(page_num), path)
        else:
            path = path + "/{}".format(page_num)
        return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, path + "/", parsed.params, parsed.query, parsed.fragment))

    def _is_top_listing(self, url):
        parsed = urllib.parse.urlparse(url or self.base_url)
        return parsed.path.rstrip("/") in ("", "/newest", "/top")

    def _extract_videos(self, html_content):
        videos = []
        seen = set()
        blocks = re.split(r'(?=<div\b[^>]+class=["\'][^"\']*\bitem\b)', html_content or "", flags=re.IGNORECASE)
        for block in blocks:
            href_match = re.search(r'<a\b[^>]+href=["\']([^"\']*/video/\d+/[^"\']+/)["\']', block, re.IGNORECASE)
            if not href_match:
                continue
            video_url = self._absolute(href_match.group(1))
            if not video_url or video_url in seen:
                continue

            img_match = re.search(r"<img\b[^>]*>", block, re.IGNORECASE)
            img_tag = img_match.group(0) if img_match else ""
            title_match = re.search(r'\s(?:alt|title)=["\']([^"\']+)["\']', img_tag, re.IGNORECASE)
            if not title_match:
                title_match = re.search(r'<strong\b[^>]+class=["\'][^"\']*\btitle\b[^"\']*["\'][^>]*>([\s\S]*?)</strong>', block, re.IGNORECASE)
            title = self._clean(title_match.group(1) if title_match else "")
            if not title:
                continue

            seen.add(video_url)
            thumb = ""
            for attr in ("data-src", "data-original", "src"):
                thumb_match = re.search(r'\s{}=["\']([^"\']+)["\']'.format(attr), img_tag, re.IGNORECASE)
                if thumb_match:
                    thumb = self._absolute(thumb_match.group(1), video_url)
                    break
            if thumb.startswith("data:image/"):
                thumb = self.icon

            duration_match = re.search(r'<span\b[^>]+class=["\'][^"\']*\bthumb-duration\b[^"\']*["\'][^>]*>([\s\S]*?)</span>', block, re.IGNORECASE)
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
        parsed_next = urllib.parse.urlparse(next_url)
        if re.search(r'href=["\'][^"\']*{}["\']'.format(re.escape(parsed_next.path)), html_content or "", re.IGNORECASE):
            return next_url
        if re.search(r'>\s*0?{}\s*<'.format(page + 1), html_content or ""):
            return next_url
        return None

    def process_content(self, url, page=1):
        if not url or url == "BOOTSTRAP":
            url, _ = self.get_start_url_and_label()
        target_url = self.get_page_url(url, page)
        html_content = self._get(target_url)
        if not html_content:
            self.notify_error("Could not load JizzBerry listing")
            return self.end_directory("videos")

        context_menu = self._context_menu()
        if page == 1 and self._is_top_listing(url):
            self.add_dir("Search", "", 5, self.icons.get("search", self.icon), context_menu=context_menu)
            self.add_dir("Categories", self.base_url + "categories/", 8, self.icons.get("categories", self.icon), context_menu=context_menu)

        videos = self._extract_videos(html_content)
        if not videos:
            self.notify_error("No JizzBerry videos found")
            return self.end_directory("videos")

        for item in videos:
            self.add_link(item["label"], item["url"], 4, item["thumb"], self.fanart, context_menu=context_menu, info_labels=item["info"])

        if self._extract_next_page(html_content, target_url, page):
            self.add_dir("Next Page", url, 2, self.icons.get("default", self.icon), context_menu=context_menu, page=page + 1)
        self.end_directory("videos")

    def process_categories(self, url):
        html_content = self._get(url or self.base_url + "categories/")
        if not html_content:
            self.notify_error("Could not load JizzBerry categories")
            return self.end_directory("videos")

        seen = set()
        blocks = re.split(r'(?=<div\b[^>]+class=["\'][^"\']*\bitem\b)', html_content or "", flags=re.IGNORECASE)
        for block in blocks:
            if "/categories/" not in block:
                continue
            href_match = re.search(r'<a\b[^>]+href=["\']([^"\']*/categories/[^"\']+/)["\']', block, re.IGNORECASE)
            if not href_match:
                continue
            category_url = self._absolute(href_match.group(1))
            parsed = urllib.parse.urlparse(category_url)
            title_match = re.search(r'<div\b[^>]+class=["\'][^"\']*\bimg-title\b[^"\']*["\'][^>]*>([\s\S]*?)</div>', block, re.IGNORECASE)
            if not title_match:
                title_match = re.search(r'\stitle=["\']([^"\']+)["\']', block, re.IGNORECASE)
            title = self._clean(title_match.group(1) if title_match else "")
            marker = "{} {}".format(title, parsed.path).lower()
            if parsed.netloc != "jizzberry.com" or category_url in seen:
                continue
            if any(term in marker for term in self.blocked_category_terms):
                continue
            seen.add(category_url)
            if title:
                self.add_dir(title, category_url, 2, self.icons.get("categories", self.icon), self.fanart)
        self.end_directory("videos")

    def search(self, query):
        if query:
            self.process_content(self.search_url.format(self._search_slug(query)))

    def _extract_streams(self, html_content):
        streams = []
        for source_match in re.finditer(r"<source\b[^>]*>", html_content or "", re.IGNORECASE):
            tag = source_match.group(0)
            src_match = re.search(r'\ssrc=["\']([^"\']+\.mp4[^"\']*)["\']', tag, re.IGNORECASE)
            if not src_match:
                continue
            title_match = re.search(r'\s(?:title|label)=["\']([^"\']+)["\']', tag, re.IGNORECASE)
            quality = 0
            if title_match:
                quality_match = re.search(r"(\d{3,4})", title_match.group(1))
                if quality_match:
                    quality = int(quality_match.group(1))
            streams.append((quality, self._absolute(src_match.group(1))))

        deduped = []
        seen = set()
        for _, stream_url in sorted(streams, key=lambda item: item[0], reverse=True):
            if stream_url and stream_url not in seen:
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
            self.notify_error("Could not resolve JizzBerry stream")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return
        headers = resolved.get("headers") or {}
        controller = ProxyController(
            resolved["url"],
            upstream_headers=headers,
            use_urllib=True,
            probe_size=True,
        )
        play_url = controller.start()
        PlaybackGuard(xbmc.Player(), xbmc.Monitor(), play_url, controller).start()
        item = xbmcgui.ListItem(path=play_url)
        item.setProperty("IsPlayable", "true")
        item.setMimeType("video/mp4")
        item.setContentLookup(False)
        xbmcplugin.setResolvedUrl(self.addon_handle, True, item)
