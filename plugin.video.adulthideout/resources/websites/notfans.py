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


class Notfans(BaseWebsite):
    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="notfans",
            base_url="https://notfans.com/",
            search_url="https://notfans.com/search/{}/",
            addon_handle=addon_handle,
            addon=addon,
        )
        self.label = "NotFans"
        self.icon = self.addon.getAddonInfo("path") + "/resources/logos/notfans.png"
        self.session = requests.Session()
        self.ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        )
        self.sort_options = ["Latest", "Top Today", "Top Week", "Top Month", "Top Year"]
        self.sort_paths = {
            "Latest": "/latest-updates/",
            "Top Today": "/day/",
            "Top Week": "/week/",
            "Top Month": "/month/",
            "Top Year": "/year/",
        }

    def _headers(self, referer=None, accept="text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"):
        return {
            "User-Agent": self.ua,
            "Referer": referer or self.base_url,
            "Accept": accept,
            "Accept-Language": "en-US,en;q=0.9",
        }

    def _get(self, url, referer=None, max_retries=3):
        last_error = None
        for attempt in range(1, max_retries + 1):
            try:
                response = self.session.get(url, headers=self._headers(referer), timeout=25)
                if response.status_code == 200:
                    return response.text
                last_error = "HTTP {}".format(response.status_code)
                self.logger.warning("NotFans HTTP %s for %s", response.status_code, url)
            except Exception as exc:
                last_error = exc
                self.logger.warning("NotFans request error for %s: %s", url, exc)
                self.session = requests.Session()

            if attempt < max_retries:
                xbmc.sleep(650 * attempt)

        self.logger.error("NotFans failed to fetch %s: %s", url, last_error)
        return ""

    def _absolute(self, value):
        if not value:
            return ""
        return urllib.parse.urljoin(self.base_url, html.unescape(value).strip())

    def _clean(self, value):
        value = re.sub(r"<[^>]+>", " ", value or "")
        return re.sub(r"\s+", " ", html.unescape(value)).strip()

    def _get_sort_key(self):
        try:
            idx = int(self.addon.getSetting("notfans_sort_by") or "0")
        except Exception:
            idx = 0
        if not 0 <= idx < len(self.sort_options):
            idx = 0
        return self.sort_options[idx]

    def get_start_url_and_label(self):
        sort_key = self._get_sort_key()
        return self._absolute(self.sort_paths.get(sort_key, "/latest-updates/")), (
            "{} [COLOR yellow]{}[/COLOR]".format(self.label, sort_key)
        )

    def _context_menu(self, original_url=None):
        suffix = ""
        if original_url:
            suffix = "&original_url={}".format(urllib.parse.quote_plus(original_url))
        return [
            (
                "Sort by...",
                "RunPlugin({}?mode=7&action=select_sort&website={}{} )".format(
                    sys.argv[0], self.name, suffix
                ).replace(" )", ")"),
            )
        ]

    def _is_top_listing(self, url):
        parsed = urllib.parse.urlparse(url or "")
        return parsed.path.strip("/") in ("", "latest-updates")

    def _extract_videos(self, html_content):
        videos = []
        seen = set()
        for block in re.split(r'(?=<div\s+class=["\']item\b)', html_content or "", flags=re.IGNORECASE):
            if "/videos/" not in block:
                continue
            anchor_match = re.search(r"<a\b[^>]*>", block, re.IGNORECASE)
            if not anchor_match:
                continue
            anchor = anchor_match.group(0)
            href_match = re.search(r'\shref=["\']([^"\']+/videos/\d+/[^"\']*)["\']', anchor, re.IGNORECASE)
            if not href_match:
                continue
            video_url = self._absolute(href_match.group(1))
            if not video_url or video_url in seen:
                continue
            seen.add(video_url)

            title_match = re.search(r'\stitle=["\']([^"\']+)["\']', anchor, re.IGNORECASE)
            if not title_match:
                title_match = re.search(r'<strong\b[^>]*class=["\'][^"\']*title[^"\']*["\'][^>]*>([\s\S]*?)</strong>', block, re.IGNORECASE)
            img_match = re.search(r"<img\b[^>]*>", block, re.IGNORECASE)
            img_tag = img_match.group(0) if img_match else ""
            if not title_match:
                title_match = re.search(r'\salt=["\']([^"\']+)["\']', img_tag, re.IGNORECASE)
            thumb_match = re.search(r'\s(?:src|data-src)=["\']([^"\']+)["\']', img_tag, re.IGNORECASE)

            title = self._clean(title_match.group(1) if title_match else "")
            if not title:
                continue
            thumb = self._absolute(thumb_match.group(1)) if thumb_match else self.icon
            videos.append(
                {
                    "label": title,
                    "url": video_url,
                    "thumb": thumb or self.icon,
                    "info": {"title": title, "plot": title},
                }
            )
        return videos

    def _extract_next_page(self, html_content, current_url):
        parsed = urllib.parse.urlparse(current_url or self.base_url)
        current = 1
        page_match = re.search(r"/(\d+)/?$", parsed.path)
        if page_match:
            current = int(page_match.group(1))

        candidates = []
        for href, num in re.findall(r'href=["\']([^"\']*/(\d+)/?)["\']', html_content or "", re.IGNORECASE):
            next_url = self._absolute(href)
            try:
                page_num = int(num)
            except ValueError:
                continue
            if page_num > current:
                candidates.append((page_num, next_url))
        if not candidates:
            return None
        return sorted(candidates, key=lambda item: item[0])[0][1]

    def process_content(self, url, page=1):
        if not url or url == "BOOTSTRAP":
            url, _ = self.get_start_url_and_label()

        context_menu = self._context_menu(url)
        if self._is_top_listing(url):
            self.add_dir("Search", "", 5, self.icons.get("search", self.icon), context_menu=context_menu)
            self.add_dir("Categories", self.base_url, 8, self.icons.get("categories", self.icon), context_menu=context_menu)

        html_content = self._get(url)
        if not html_content:
            self.notify_error("Could not load NotFans listing")
            xbmcplugin.endOfDirectory(self.addon_handle, succeeded=False, updateListing=False, cacheToDisc=False)
            return

        videos = self._extract_videos(html_content)
        if not videos:
            self.notify_error("No NotFans videos found")
            return self.end_directory("videos")

        for item in videos:
            self.add_link(
                item["label"],
                item["url"],
                4,
                item["thumb"],
                self.fanart,
                context_menu=context_menu,
                info_labels=item["info"],
            )

        next_url = self._extract_next_page(html_content, url)
        if next_url:
            self.add_dir("Next Page", next_url, 2, self.icons.get("default", self.icon), context_menu=context_menu)

        self.end_directory("videos")

    def process_categories(self, url):
        html_content = self._get(url or self.base_url)
        if not html_content:
            self.notify_error("Could not load NotFans tags")
            xbmcplugin.endOfDirectory(self.addon_handle, succeeded=False, updateListing=False, cacheToDisc=False)
            return

        seen = set()
        for href, label_html in re.findall(
            r'<a\b[^>]*href=["\']([^"\']*/tags/[^"\']+)["\'][^>]*>([\s\S]*?)</a>',
            html_content,
            re.IGNORECASE,
        ):
            tag_url = self._absolute(href)
            if not tag_url or tag_url in seen:
                continue
            seen.add(tag_url)
            title = self._clean(label_html)
            if not title:
                title = urllib.parse.urlparse(tag_url).path.rstrip("/").rsplit("/", 1)[-1].replace("-", " ").title()
            self.add_dir(title, tag_url, 2, self.icons.get("categories", self.icon), self.fanart)

        self.end_directory("videos")

    def search(self, query):
        if query:
            self.process_content(self.search_url.format(urllib.parse.quote_plus(query.strip())))

    def _extract_stream_url(self, html_content):
        download_matches = re.findall(r'href=["\']([^"\']+/get_file/\d+/[^"\']+\.mp4/[^"\']*)["\']', html_content or "", re.IGNORECASE)
        if download_matches:
            for candidate in download_matches:
                if "download=true" in candidate:
                    return self._absolute(candidate)
            return self._absolute(download_matches[-1])

        flashvar_matches = re.findall(r"(?:video_url|video_url_hd|event_reporting2):\s*'([^']+)'", html_content or "", re.IGNORECASE)
        for candidate in flashvar_matches:
            candidate = html.unescape(candidate).replace("\\/", "/")
            if candidate.startswith("function/0/"):
                candidate = candidate.split("function/0/", 1)[1]
            if "/get_file/" in candidate and ".mp4" in candidate:
                return self._absolute(candidate)
        return None

    def resolve_recording_stream(self, url):
        html_content = self._get(url, referer=self.base_url)
        stream_url = self._extract_stream_url(html_content)
        if not stream_url:
            self.logger.info("NotFans no public stream on detail page: %s", url)
            return None
        headers = {
            "User-Agent": self.ua,
            "Referer": url,
            "Accept": "*/*",
        }
        cookie_header = "; ".join("{}={}".format(cookie.name, cookie.value) for cookie in self.session.cookies)
        if cookie_header:
            headers["Cookie"] = cookie_header
        return {"url": stream_url, "headers": headers, "extension": "mp4"}

    def play_video(self, url):
        resolved = self.resolve_recording_stream(url)
        if not resolved:
            self.notify_error("Could not resolve NotFans stream")
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
