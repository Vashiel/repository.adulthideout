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


class Wowxxx(BaseWebsite):
    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="wowxxx",
            base_url="https://www.wow.xxx/",
            search_url="https://www.wow.xxx/search/{}/",
            addon_handle=addon_handle,
            addon=addon,
        )
        self.label = "WOW.xxx"
        self.session = requests.Session()
        self.ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        )
        self.sort_options = ["Latest", "Top Rated", "Most Viewed"]
        self.sort_paths = {
            "Latest": "/latest-updates/",
            "Top Rated": "/top-rated/",
            "Most Viewed": "/most-popular/",
        }
        self.quality_options = ["Highest", "2160p", "1080p", "720p", "480p"]

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
                self.logger.warning("WOW.xxx HTTP %s for %s", response.status_code, url)
            except Exception as exc:
                last_error = exc
                self.logger.warning("WOW.xxx request error for %s: %s", url, exc)
                self.session = requests.Session()

            if attempt < max_retries:
                xbmc.sleep(650 * attempt)

        self.logger.error("WOW.xxx failed to fetch %s: %s", url, last_error)
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
            idx = int(self.addon.getSetting("wowxxx_sort_by") or "0")
        except Exception:
            idx = 0
        if not 0 <= idx < len(self.sort_options):
            idx = 0
        return self.sort_options[idx]

    def _get_quality_preference(self):
        try:
            idx = int(self.addon.getSetting("wowxxx_quality") or "0")
        except Exception:
            idx = 0
        if not 0 <= idx < len(self.quality_options):
            idx = 0
        return self.quality_options[idx]

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
        for block in re.split(r'(?=<div\b[^>]+class=["\'][^"\']*item[^"\']*["\'])', html_content or "", flags=re.IGNORECASE):
            if "/videos/" not in block:
                continue
            anchor_match = re.search(r"<a\b[^>]*>", block, re.IGNORECASE)
            if not anchor_match:
                continue
            anchor = anchor_match.group(0)
            href_match = re.search(r'\shref=["\']([^"\']+/videos/[^"\']+)["\']', anchor, re.IGNORECASE)
            if not href_match:
                continue
            video_url = self._absolute(href_match.group(1))
            if not video_url or video_url in seen:
                continue
            seen.add(video_url)

            title_match = re.search(r'\stitle=["\']([^"\']+)["\']', anchor, re.IGNORECASE)
            img_match = re.search(r"<img\b[^>]*>", block, re.IGNORECASE)
            img_tag = img_match.group(0) if img_match else ""
            if not title_match:
                title_match = re.search(r'\salt=["\']([^"\']+)["\']', img_tag, re.IGNORECASE)
            thumb_match = re.search(r'\sdata-src=["\']([^"\']+)["\']', img_tag, re.IGNORECASE)
            if not thumb_match:
                thumb_match = re.search(r'\ssrc=["\']([^"\']+)["\']', img_tag, re.IGNORECASE)
            duration_match = re.search(r'<span\b[^>]*class=["\'][^"\']*duration[^"\']*["\'][^>]*>([\s\S]*?)</span>', block, re.IGNORECASE)

            title = self._clean(title_match.group(1) if title_match else "")
            if not title:
                continue
            thumb = self._absolute(thumb_match.group(1)) if thumb_match else self.icon
            if thumb.startswith("data:image/"):
                thumb = self.icon
            duration = self._clean(duration_match.group(1)) if duration_match else ""
            label = "{} [COLOR lime]({})[/COLOR]".format(title, duration) if duration else title
            info = {"title": title, "plot": title}
            seconds = self.convert_duration(duration.replace("Full Video", "").strip()) if duration else 0
            if seconds:
                info["duration"] = seconds
            videos.append({"label": label, "url": video_url, "thumb": thumb or self.icon, "info": info})
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
            next_path = urllib.parse.urlparse(next_url).path
            if not any(segment in next_path for segment in ("/latest-updates/", "/top-rated/", "/most-popular/", "/categories/", "/search/")):
                continue
            next_url = re.sub(r"/0/(\d+)/?$", r"/\1/", next_url)
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
            self.add_dir("Categories", self._absolute("/categories/"), 8, self.icons.get("categories", self.icon), context_menu=context_menu)

        html_content = self._get(url)
        if not html_content:
            self.notify_error("Could not load WOW.xxx listing")
            xbmcplugin.endOfDirectory(self.addon_handle, succeeded=False, updateListing=False, cacheToDisc=False)
            return

        videos = self._extract_videos(html_content)
        if not videos:
            self.notify_error("No WOW.xxx videos found")
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
        html_content = self._get(url or self._absolute("/categories/"))
        if not html_content:
            self.notify_error("Could not load WOW.xxx categories")
            xbmcplugin.endOfDirectory(self.addon_handle, succeeded=False, updateListing=False, cacheToDisc=False)
            return

        seen = set()
        for href, label_html in re.findall(
            r'<a\b[^>]*href=["\']([^"\']*/categories/[^"\']+)["\'][^>]*>([\s\S]*?)</a>',
            html_content,
            re.IGNORECASE,
        ):
            category_url = self._absolute(href)
            if not category_url or category_url in seen or urllib.parse.urlparse(category_url).path.rstrip("/") == "/categories":
                continue
            seen.add(category_url)
            title = self._clean(label_html)
            if not title:
                title = urllib.parse.urlparse(category_url).path.rstrip("/").rsplit("/", 1)[-1].replace("-", " ").title()
            self.add_dir(title, category_url, 2, self.icons.get("categories", self.icon), self.fanart)

        self.end_directory("videos")

    def search(self, query):
        if query:
            self.process_content(self.search_url.format(urllib.parse.quote_plus(query.strip())))

    def _extract_sources(self, html_content):
        sources = []
        for tag in re.findall(r"<source\b[^>]+>", html_content or "", re.IGNORECASE):
            src_match = re.search(r'\ssrc=["\']([^"\']+\.mp4/?)["\']', tag, re.IGNORECASE)
            if not src_match:
                continue
            label_match = re.search(r'\slabel=["\']([^"\']+)["\']', tag, re.IGNORECASE)
            label = label_match.group(1) if label_match else ""
            quality_match = re.search(r"(\d{3,4})", label)
            if not quality_match:
                quality_match = re.search(r"_(\d{3,4})m\.mp4", src_match.group(1), re.IGNORECASE)
            quality = int(quality_match.group(1)) if quality_match else 0
            sources.append({"quality": quality, "url": self._absolute(src_match.group(1))})
        return sources

    def _select_stream_url(self, sources):
        if not sources:
            return None
        preference = self._get_quality_preference()
        sources = sorted(sources, key=lambda item: item["quality"], reverse=True)
        if preference == "Highest":
            return sources[0]["url"]
        wanted = int(re.sub(r"\D", "", preference) or "0")
        exact = [item for item in sources if item["quality"] == wanted]
        if exact:
            return exact[0]["url"]
        lower = [item for item in sources if item["quality"] and item["quality"] <= wanted]
        if lower:
            return sorted(lower, key=lambda item: item["quality"], reverse=True)[0]["url"]
        return sources[0]["url"]

    def resolve_recording_stream(self, url):
        html_content = self._get(url, referer=self.base_url)
        stream_url = self._select_stream_url(self._extract_sources(html_content))
        if not stream_url:
            self.logger.info("WOW.xxx no public stream on detail page: %s", url)
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
            self.notify_error("Could not resolve WOW.xxx stream")
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
