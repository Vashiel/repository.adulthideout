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
from resources.lib.decoders.kvs_decoder import kvs_decode_url
from resources.lib.resilient_http import fetch_text


class Epawg(BaseWebsite):
    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="epawg",
            base_url="https://epawg.com/",
            search_url="https://epawg.com/search/{}/",
            addon_handle=addon_handle,
            addon=addon,
        )
        self.label = "Epawg"
        self.session = requests.Session()
        self.ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        )
        self.sort_options = ["Latest", "Trending", "Most Viewed"]
        self.sort_paths = {
            "Trending": "/",
            "Latest": "/latest-updates/",
            "Most Viewed": "/most-popular/",
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
            self.logger.warning("Epawg HTTP %s for %s", response.status_code, url)
        except Exception as exc:
            self.logger.warning("Epawg request failed for %s: %s", url, exc)
            self.session = requests.Session()

        fallback = fetch_text(
            url,
            headers=self._headers(referer),
            scraper=None,
            logger=self.logger,
            timeout=20,
            use_windows_curl_fallback=True,
        )
        return fallback or ""

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
        return re.sub(r"[^a-z0-9]+", "-", (value or "").lower()).strip("-")

    def _get_sort_key(self):
        try:
            idx = int(self.addon.getSetting("epawg_sort_by") or "0")
        except Exception:
            idx = 0
        if idx < 0 or idx >= len(self.sort_options):
            idx = 0
        return self.sort_options[idx]

    def get_start_url_and_label(self):
        sort_key = self._get_sort_key()
        return self._absolute(self.sort_paths.get(sort_key, "/")), "{} [COLOR yellow]{}[/COLOR]".format(self.label, sort_key)

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
        if parsed.path.startswith("/search/"):
            query = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
            query["from_videos"] = [str(page_num)]
            return urllib.parse.urlunparse(
                (
                    parsed.scheme,
                    parsed.netloc,
                    parsed.path,
                    parsed.params,
                    urllib.parse.urlencode(query, doseq=True),
                    parsed.fragment,
                )
            )
        path = parsed.path.rstrip("/")
        if re.search(r"/\d+$", path):
            path = re.sub(r"/\d+$", "/{}".format(page_num), path)
        else:
            path = path + "/{}".format(page_num)
        return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, path + "/", parsed.params, parsed.query, parsed.fragment))

    def _is_top_listing(self, url):
        parsed = urllib.parse.urlparse(url or self.base_url)
        return parsed.path.rstrip("/") in ("", "/latest-updates", "/most-popular")

    def _extract_videos(self, html_content):
        videos = []
        seen = set()
        blocks = re.split(r'(?=<div\b[^>]+class=["\']item["\'])', html_content or "", flags=re.IGNORECASE)
        for block in blocks:
            href_match = re.search(r'<a\b[^>]+href=["\']([^"\']*/videos/\d+/[^"\']+)["\']', block, re.IGNORECASE)
            if not href_match:
                continue
            video_url = self._absolute(href_match.group(1))
            if not video_url or video_url in seen:
                continue
            seen.add(video_url)

            img_match = re.search(r"<img\b[^>]*>", block, re.IGNORECASE)
            img_tag = img_match.group(0) if img_match else ""
            title_match = re.search(r'\s(?:alt|title)=["\']([^"\']+)["\']', img_tag, re.IGNORECASE)
            if not title_match:
                title_match = re.search(r'<strong\b[^>]+class=["\']title["\'][^>]*>([\s\S]*?)</strong>', block, re.IGNORECASE)
            title = self._clean(title_match.group(1) if title_match else "")
            if not title:
                continue

            thumb = ""
            for attr in ("data-original", "data-src", "src"):
                thumb_match = re.search(r'\s{}=["\']([^"\']+)["\']'.format(attr), img_tag, re.IGNORECASE)
                if thumb_match:
                    thumb = self._absolute(thumb_match.group(1))
                    break
            if thumb.startswith("data:image/"):
                thumb = self.icon

            duration_match = re.search(r'<div\b[^>]+class=["\']duration["\'][^>]*>([\s\S]*?)</div>', block, re.IGNORECASE)
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
        parsed_current = urllib.parse.urlparse(current_url)
        if parsed_current.path.startswith("/search/"):
            if re.search(r"from_videos(?:\+from_albums)?\s*:\s*{}".format(page + 1), html_content or "", re.IGNORECASE):
                return next_url
        escaped = re.escape(urllib.parse.urlparse(next_url).path.rstrip("/") + "/")
        if re.search(r'href=["\'][^"\']*{}["\']'.format(escaped), html_content or "", re.IGNORECASE):
            return next_url
        if re.search(r'>\s*{}\s*<'.format(page + 1), html_content or ""):
            return next_url
        return None

    def process_content(self, url, page=1):
        if not url or url == "BOOTSTRAP":
            url, _ = self.get_start_url_and_label()
        target_url = self.get_page_url(url, page)
        html_content = self._get(target_url)
        if not html_content:
            self.notify_error("Could not load Epawg listing")
            return self.end_directory("videos")

        context_menu = self._context_menu()
        if page == 1 and self._is_top_listing(url):
            self.add_dir("Search", "", 5, self.icons.get("search", self.icon), context_menu=context_menu)
            self.add_dir("Categories", self.base_url + "categories/", 8, self.icons.get("categories", self.icon), context_menu=context_menu)

        videos = self._extract_videos(html_content)
        if not videos:
            self.notify_error("No Epawg videos found")
            return self.end_directory("videos")
        for item in videos:
            self.add_link(item["label"], item["url"], 4, item["thumb"], self.fanart, context_menu=context_menu, info_labels=item["info"])

        next_url = self._extract_next_page(html_content, target_url, page)
        if next_url:
            self.add_dir("Next Page", url, 2, self.icons.get("default", self.icon), context_menu=context_menu, page=page + 1)
        self.end_directory("videos")

    def process_categories(self, url):
        html_content = self._get(url or self.base_url + "categories/")
        if not html_content:
            self.notify_error("Could not load Epawg categories")
            return self.end_directory("videos")

        seen = set()
        for href, label_html in re.findall(
            r'<a\b[^>]+href=["\']([^"\']*/categories/[^"\']+)["\'][^>]*>([\s\S]*?)</a>',
            html_content,
            re.IGNORECASE,
        ):
            category_url = self._absolute(href)
            if not category_url or category_url in seen or category_url.rstrip("/") == self.base_url.rstrip("/") + "/categories":
                continue
            seen.add(category_url)
            title = self._clean(label_html)
            if not title:
                title = urllib.parse.urlparse(category_url).path.rstrip("/").rsplit("/", 1)[-1].replace("-", " ").title()
            self.add_dir(title, category_url, 2, self.icons.get("categories", self.icon), self.fanart)
        self.end_directory("videos")

    def search(self, query):
        if query:
            self.process_content(self.search_url.format(self._slug(query.strip())))

    def _normalize_stream(self, value, base_url, license_code=""):
        value = html.unescape(value or "").replace("\\/", "/").strip()
        if value.startswith("function/0/") and license_code:
            value = kvs_decode_url(value, license_code)
        elif value.startswith("function/"):
            value = value.split("/", 2)[-1]
        value = re.sub(r"(\.mp4)/+$", r"\1", value, flags=re.IGNORECASE)
        if value.startswith("//"):
            value = "https:" + value
        return self._absolute(value, base_url)

    def _extract_streams(self, html_content, base_url):
        streams = []
        license_match = re.search(r"license_code\s*:\s*['\"]([^'\"]+)['\"]", html_content or "", re.IGNORECASE)
        license_code = html.unescape(license_match.group(1)).strip() if license_match else ""
        for key, value in re.findall(r"(video_url(?:_\d+p)?|video_alt_url(?:_\d+p)?)\s*:\s*['\"]([^'\"]+\.mp4[^'\"]*)['\"]", html_content or "", re.IGNORECASE):
            quality = 0
            q_match = re.search(r"_(\d+)p", key)
            if q_match:
                quality = int(q_match.group(1))
            streams.append((quality, self._normalize_stream(value, base_url, license_code)))
        for value in re.findall(r'https?://[^"\']+\.mp4(?:\?[^"\']*)?', html_content or "", re.IGNORECASE):
            if "preview" not in value.lower():
                streams.append((0, self._normalize_stream(value, base_url, license_code)))
        deduped = []
        seen = set()
        for quality, stream_url in sorted(streams, key=lambda item: item[0], reverse=True):
            if stream_url and stream_url not in seen:
                seen.add(stream_url)
                deduped.append((quality, stream_url))
        return [url for _, url in deduped]

    def resolve_recording_stream(self, url):
        detail_html = self._get(url, referer=self.base_url)
        streams = self._extract_streams(detail_html, url)
        if not streams:
            embed_match = re.search(r'<iframe\b[^>]+src=["\']([^"\']*/embed/\d+[^"\']*)["\']', detail_html or "", re.IGNORECASE)
            if embed_match:
                embed_url = self._absolute(embed_match.group(1), url)
                streams = self._extract_streams(self._get(embed_url, referer=url), embed_url)
        if not streams:
            return None
        return {"url": streams[0], "headers": self._headers(url, accept="*/*"), "extension": "mp4"}

    def play_video(self, url):
        resolved = self.resolve_recording_stream(url)
        if not resolved:
            self.notify_error("Could not resolve Epawg stream")
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
