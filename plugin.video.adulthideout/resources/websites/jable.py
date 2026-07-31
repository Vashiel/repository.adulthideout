#!/usr/bin/env python
# -*- coding: utf-8 -*-

import html
import os
import re
import sys
import urllib.parse
import xml.etree.ElementTree as ElementTree

vendor_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "lib", "vendor")
if os.path.isdir(vendor_path) and vendor_path not in sys.path:
    sys.path.insert(0, vendor_path)

try:
    import cloudscraper
except Exception:
    cloudscraper = None
import requests
import xbmc
import xbmcgui
import xbmcplugin

from resources.lib.kvs_tube import KVSTubeWebsite


class Jable(KVSTubeWebsite):
    label = "Jable"
    sort_options = ["Latest", "Hot"]
    sort_paths = {
        "Latest": "/latest-updates/",
        "Hot": "/hot/",
    }
    search_path = "/search/{}/"
    categories_path = "/categories/"
    models_path = "/models/"
    video_path_markers = ("/videos/",)
    category_path_markers = ("/categories/",)
    next_page_full_count = 24
    request_retries = 4

    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="jable",
            base_url="https://jable.tv/",
            search_url="https://jable.tv/search/{}/",
            addon_handle=addon_handle,
            addon=addon,
        )
        self.ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
        self.session = self._build_session()

    def _build_session(self):
        if cloudscraper:
            try:
                session = cloudscraper.create_scraper(
                    browser={"browser": "chrome", "platform": "windows", "desktop": True}
                )
                session.headers.update(self._headers())
                return session
            except Exception as exc:
                self.logger.warning("Jable cloudscraper init failed: %s", exc)
        return requests.Session()

    def _headers(self, referer=None, accept=None):
        return {
            "User-Agent": self.ua,
            "Referer": referer or self.base_url,
            "Accept": accept or "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "identity",
        }

    def _is_challenge(self, content):
        lower = (content or "").lower()
        return (
            len(content or "") < 12000
            or "just a moment" in lower
            or "cf-chl-" in lower
            or "challenge-platform" in lower and "/videos/" not in lower
        )

    def _get(self, url, referer=None, max_retries=None):
        retries = max_retries or self.request_retries
        for attempt in range(retries):
            try:
                response = self.session.get(
                    url,
                    headers=self._headers(referer),
                    timeout=25,
                    allow_redirects=True,
                )
                content = response.text if response.status_code == 200 else ""
                if content and not self._is_challenge(content):
                    return content
                log_method = self.logger.error if attempt + 1 == retries else self.logger.debug
                log_method(
                    "Jable blocked response on attempt %s: HTTP %s, %s bytes",
                    attempt + 1,
                    response.status_code,
                    len(content),
                )
            except Exception as exc:
                log_method = self.logger.error if attempt + 1 == retries else self.logger.debug
                log_method("Jable request attempt %s failed: %s", attempt + 1, exc)
            self.session = self._build_session()
            if attempt + 1 < retries:
                xbmc.sleep(900 * (attempt + 1))
        parsed = urllib.parse.urlparse(url)
        if parsed.path.rstrip("/") in ("", "/latest-updates"):
            try:
                response = requests.get(
                    self._absolute("/rss/"),
                    headers=self._headers(self.base_url),
                    timeout=20,
                )
                if response.status_code == 200 and "<rss" in response.text:
                    self.logger.info("Jable using first-party RSS fallback")
                    return response.text
            except Exception:
                pass
        return ""

    def _extract_videos(self, content):
        if "<rss" not in (content or ""):
            return super()._extract_videos(content)
        videos = []
        try:
            root = ElementTree.fromstring(content)
        except ElementTree.ParseError:
            return videos
        for item in root.findall(".//item"):
            title = self._clean(item.findtext("title") or "")
            video_url = self._absolute(item.findtext("link") or "")
            description = item.findtext("description") or ""
            thumb_match = re.search(r'<img\b[^>]+src=["\']([^"\']+)["\']', description, re.IGNORECASE)
            thumb = self._absolute(thumb_match.group(1)) if thumb_match else self.icon
            if not title or not video_url or "/videos/" not in video_url:
                continue
            videos.append({
                "label": title,
                "url": video_url,
                "thumb": thumb,
                "info": {"title": title, "plot": title},
            })
        return videos

    def process_categories(self, url):
        current_url = url or self._absolute(self.categories_path)
        content = self._get(current_url, referer=self.base_url)
        if not content:
            self.notify_error("Could not load Jable directory")
            return self.end_directory("videos")

        models = "/models" in urllib.parse.urlparse(current_url).path
        marker = "/models/" if models else "/categories/"
        seen = set()
        for anchor in re.finditer(
            r'<a\b[^>]+href=["\']([^"\']+)["\'][^>]*>([\s\S]{0,1800}?)</a>',
            content,
            re.IGNORECASE,
        ):
            href = anchor.group(1)
            if marker not in href:
                continue
            target = self._absolute(href)
            path = urllib.parse.urlparse(target).path.rstrip("/")
            if path in ("/models", "/categories") or target in seen:
                continue
            body = anchor.group(2)
            title_match = re.search(
                r'class=["\'][^"\']*\btitle\b[^"\']*["\'][^>]*>([\s\S]{0,180}?)</',
                body,
                re.IGNORECASE,
            )
            image_match = re.search(r"<img\b[^>]*>", body, re.IGNORECASE)
            image_tag = image_match.group(0) if image_match else ""
            if not title_match:
                title_match = re.search(r'\s(?:alt|title)=["\']([^"\']+)["\']', image_tag, re.IGNORECASE)
            title = self._clean(title_match.group(1) if title_match else "")
            if not title:
                title = path.split("/")[-1].replace("-", " ").title()
            if not title:
                continue
            seen.add(target)
            icon = self._pick_thumb(image_tag) if image_tag else ""
            if not icon:
                icon = self.icons.get("pornstars" if models else "categories", self.icon)
            self.add_dir(title, target, 2, icon, self.fanart)

        next_match = re.search(
            r'<a\b[^>]+href=["\']([^"\']+)["\'][^>]*>\s*(?:Next|&raquo;|›)\s*</a>',
            content,
            re.IGNORECASE,
        )
        if next_match:
            self.add_dir("Next Page", self._absolute(next_match.group(1)), 8, self.icons.get("default", self.icon), self.fanart)
        self.end_directory("videos")

    def _extract_stream_url(self, content, referer=None):
        candidates = re.findall(
            r'https?://[^"\'\s<>\\]+\.m3u8[^"\'\s<>\\]*',
            (content or "").replace("\\/", "/"),
            re.IGNORECASE,
        )
        for candidate in candidates:
            candidate = html.unescape(candidate)
            if "/hls/" in candidate or "mushroomtrack.com" in candidate:
                return candidate
        return candidates[0] if candidates else None

    def resolve_recording_stream(self, url):
        content = self._get(url, referer=self.base_url)
        stream_url = self._extract_stream_url(content, referer=url)
        if not stream_url:
            return None
        return {
            "url": stream_url,
            "headers": self._headers(url, accept="*/*"),
            "extension": "m3u8",
        }

    def play_video(self, url):
        resolved = self.resolve_recording_stream(url)
        if not resolved:
            self.notify_error("Could not resolve Jable stream")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return
        play_url = "{}|{}".format(
            resolved["url"],
            urllib.parse.urlencode(resolved["headers"]),
        )
        item = xbmcgui.ListItem(path=play_url)
        item.setProperty("IsPlayable", "true")
        item.setMimeType("application/vnd.apple.mpegurl")
        item.setContentLookup(False)
        if xbmc.getCondVisibility("System.HasAddon(inputstream.adaptive)"):
            item.setProperty("inputstream", "inputstream.adaptive")
            item.setProperty("inputstream.adaptive.manifest_type", "hls")
        xbmcplugin.setResolvedUrl(self.addon_handle, True, item)
