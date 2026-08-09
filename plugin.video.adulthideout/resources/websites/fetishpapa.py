#!/usr/bin/env python
# -*- coding: utf-8 -*-

import html
import re
import urllib.parse

import requests
import xbmc
import xbmcgui
import xbmcplugin

from resources.lib.base_website import BaseWebsite


class FetishPapa(BaseWebsite):
    label = "FetishPapa"
    sort_options = ["Latest", "Most Popular", "Top Rated", "Longest"]
    sort_paths = {
        "Latest": "/",
        "Most Popular": "/?sort=most-popular",
        "Top Rated": "/?sort=top-rated",
        "Longest": "/?sort=longest",
    }

    def __init__(self, addon_handle, addon=None):
        super().__init__("fetishpapa", "https://www.fetishpapa.com/", "https://www.fetishpapa.com/search/?q={}", addon_handle, addon)
        self.session = requests.Session()
        self.ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"

    def _headers(self, referer=None, accept="text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"):
        return {"User-Agent": self.ua, "Referer": referer or self.base_url, "Accept": accept, "Accept-Language": "en-US,en;q=0.9", "Accept-Encoding": "identity"}

    def _get(self, url, referer=None):
        try:
            response = self.session.get(url, headers=self._headers(referer), timeout=20)
            return response.text if response.status_code == 200 else ""
        except Exception as exc:
            self.logger.warning("FetishPapa request failed for %s: %s", url, exc)
            return ""

    def _absolute(self, value):
        return urllib.parse.urljoin(self.base_url, html.unescape(value or ""))

    def _sort_index(self):
        try:
            return max(0, min(int(self.addon.getSetting("fetishpapa_sort_by") or "0"), len(self.sort_options) - 1))
        except (TypeError, ValueError):
            return 0

    def get_start_url_and_label(self):
        option = self.sort_options[self._sort_index()]
        return self._absolute(self.sort_paths[option]), "{} [COLOR yellow]{}[/COLOR]".format(self.label, option)

    def get_page_url(self, url, page):
        if page <= 1:
            return url
        parsed = urllib.parse.urlparse(url)
        query = urllib.parse.parse_qs(parsed.query)
        query["page"] = [str(page)]
        return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, urllib.parse.urlencode(query, doseq=True), ""))

    def _extract_videos(self, content):
        videos, seen = [], set()
        pattern = re.compile(r'<a\b[^>]+href=["\'](/videos/\d+/[^"\']+/)["\'][^>]+title=["\']([^"\']+)["\'][^>]*>([\s\S]{0,2200}?)</a>', re.I)
        for href, title, body in pattern.findall(content or ""):
            target = self._absolute(href)
            if target in seen:
                continue
            seen.add(target)
            image = re.search(r'<img\b[^>]+(?:src|data-src)=["\']([^"\']+)["\']', body, re.I)
            duration = re.search(r'info-item-length[^>]*>\s*([0-9:]+)', body, re.I)
            duration_text = duration.group(1) if duration else ""
            clean_title = html.unescape(title).strip()
            info = {"title": clean_title, "plot": clean_title}
            seconds = self.convert_duration(duration_text)
            if seconds:
                info["duration"] = seconds
            label = "{} [COLOR lime]({})[/COLOR]".format(clean_title, duration_text) if duration_text else clean_title
            videos.append({"label": label, "url": target, "thumb": self._absolute(image.group(1)) if image else self.icon, "info": info})
        return videos

    def process_content(self, url, page=1):
        if not url or url == "BOOTSTRAP":
            url, _ = self.get_start_url_and_label()
        if page == 1 and self.is_primary_listing_url(url):
            self.add_dir("Search", "", 5, self.icons.get("search", self.icon))
        content = self._get(self.get_page_url(url, page))
        videos = self._extract_videos(content)
        for item in videos:
            self.add_link(item["label"], item["url"], 4, item["thumb"], self.fanart, info_labels=item["info"])
        if videos and re.search(r'[?&]page={}(["\'&]|$)'.format(page + 1), content or "", re.I):
            self.add_dir("Next Page", url, 2, self.icons.get("default", self.icon), page=page + 1)
        if not videos:
            self.notify_error("No FetishPapa videos found")
        self.end_directory("videos")

    def search(self, query):
        if query:
            self.process_content(self.search_url.format(urllib.parse.quote_plus(query.strip())))

    def resolve_recording_stream(self, url):
        content = self._get(url, self.base_url)
        sources = re.search(r'sources\s*:\s*\{"hls"\s*:\s*\[([\s\S]*?)\]\s*\}', content or "", re.I)
        if not sources:
            return None
        candidates = []
        for stream, quality in re.findall(r'"src"\s*:\s*"([^"]+)"\s*,\s*"quality"\s*:\s*"([^"]+)"', sources.group(1), re.I):
            stream = html.unescape(stream).replace("\\/", "/")
            height = int(re.search(r'\d+', quality).group()) if re.search(r'\d+', quality) else 0
            candidates.append((height, stream))
        if not candidates:
            return None
        stream_url = sorted(candidates, reverse=True)[0][1]
        return {"url": stream_url, "headers": self._headers(url, "*/*"), "extension": "m3u8"}

    def play_video(self, url):
        resolved = self.resolve_recording_stream(url)
        if not resolved:
            self.notify_error("Could not resolve FetishPapa stream")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return
        encoded_headers = urllib.parse.urlencode(resolved["headers"])
        adaptive = xbmc.getCondVisibility("System.HasAddon(inputstream.adaptive)")
        play_url = resolved["url"] if adaptive else resolved["url"] + "|" + encoded_headers
        item = xbmcgui.ListItem(path=play_url)
        item.setProperty("IsPlayable", "true")
        item.setMimeType("application/vnd.apple.mpegurl")
        item.setContentLookup(False)
        if adaptive:
            item.setProperty("inputstream", "inputstream.adaptive")
            item.setProperty("inputstream.adaptive.manifest_type", "hls")
            item.setProperty("inputstream.adaptive.manifest_headers", encoded_headers)
            item.setProperty("inputstream.adaptive.stream_headers", encoded_headers)
        xbmcplugin.setResolvedUrl(self.addon_handle, True, item)
