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
from resources.lib.proxy_utils import PlaybackGuard, ProxyController


class BondageValley(BaseWebsite):
    label = "Bondage Valley"
    sort_options = ["Latest", "Trending", "Top"]
    sort_paths = {"Latest": "/videos/latest", "Trending": "/videos/trending", "Top": "/videos/top"}

    def __init__(self, addon_handle, addon=None):
        super().__init__("bondagevalley", "https://bondagevalley.cc/", "https://bondagevalley.cc/search?keyword={}", addon_handle, addon)
        self.session = requests.Session()
        self.ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"

    def _headers(self, referer=None, accept="text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"):
        return {"User-Agent": self.ua, "Referer": referer or self.base_url, "Accept": accept, "Accept-Language": "en-US,en;q=0.9", "Accept-Encoding": "identity"}

    def _get(self, url, referer=None):
        try:
            response = self.session.get(url, headers=self._headers(referer), timeout=20)
            return response.text if response.status_code == 200 else ""
        except Exception as exc:
            self.logger.warning("Bondage Valley request failed for %s: %s", url, exc)
            return ""

    def _sort_index(self):
        try:
            return max(0, min(int(self.addon.getSetting("bondagevalley_sort_by") or "0"), len(self.sort_options) - 1))
        except (TypeError, ValueError):
            return 0

    def get_start_url_and_label(self):
        option = self.sort_options[self._sort_index()]
        return urllib.parse.urljoin(self.base_url, self.sort_paths[option]), "{} [COLOR yellow]{}[/COLOR]".format(self.label, option)

    def _extract_videos(self, content):
        videos, seen = [], set()
        for block in re.findall(r'<div\b[^>]+class=["\'][^"\']*video-wrapper[^"\']*["\'][^>]*>([\s\S]{0,2600}?)</div>\s*</div>\s*</div>', content or "", re.I):
            link = re.search(r'<a\b[^>]+href=["\'](https://bondagevalley\.cc/watch/[^"\']+\.html)["\']', block, re.I)
            image = re.search(r'<img\b[^>]+src=["\']([^"\']+)["\'][^>]+alt=["\']([^"\']+)["\']', block, re.I)
            if not link or not image or link.group(1) in seen:
                continue
            seen.add(link.group(1))
            duration = re.search(r'video-duration[^>]*>\s*([0-9:]+)', block, re.I)
            duration_text = duration.group(1) if duration else ""
            title = html.unescape(image.group(2)).strip()
            info = {"title": title, "plot": title}
            seconds = self.convert_duration(duration_text)
            if seconds:
                info["duration"] = seconds
            label = "{} [COLOR lime]({})[/COLOR]".format(title, duration_text) if duration_text else title
            videos.append({"label": label, "url": link.group(1), "thumb": image.group(1), "info": info})
        return videos

    def process_content(self, url, page=1):
        if not url or url == "BOOTSTRAP":
            url, _ = self.get_start_url_and_label()
        if page == 1 and self.is_primary_listing_url(url):
            self.add_dir("Search", "", 5, self.icons.get("search", self.icon))
            self.add_dir("Categories", urllib.parse.urljoin(self.base_url, "/videos/category"), 8, self.icons.get("categories", self.icon))
            self.add_dir("Models", urllib.parse.urljoin(self.base_url, "/videos/model"), 8, self.icons.get("pornstars", self.icon))
        parsed = urllib.parse.urlparse(url)
        query = urllib.parse.parse_qs(parsed.query)
        if page > 1:
            query["page_id"] = [str(page)]
        target = urllib.parse.urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, urllib.parse.urlencode(query, doseq=True), ""))
        content = self._get(target)
        videos = self._extract_videos(content)
        for item in videos:
            self.add_link(item["label"], item["url"], 4, item["thumb"], self.fanart, info_labels=item["info"])
        if videos and "page_id={}".format(page + 1) in (content or ""):
            self.add_dir("Next Page", url, 2, self.icons.get("default", self.icon), page=page + 1)
        if not videos:
            self.notify_error("No Bondage Valley videos found")
        self.end_directory("videos")

    def process_categories(self, url):
        content = self._get(url)
        seen = set()
        for href, title in re.findall(r'<a\b[^>]+href=["\'](https://bondagevalley\.cc/videos/(?:category|model)/[^"\']+)["\'][^>]*>([\s\S]{0,500}?)</a>', content or "", re.I):
            title = re.sub(r'<[^>]+>', ' ', title)
            title = re.sub(r'\s+', ' ', html.unescape(title)).strip()
            if title and href not in seen:
                seen.add(href)
                self.add_dir(title, href, 2, self.icons.get("categories", self.icon), self.fanart)
        self.end_directory("videos")

    def search(self, query):
        if query:
            self.process_content(self.search_url.format(urllib.parse.quote_plus(query.strip())))

    def resolve_recording_stream(self, url):
        content = self._get(url, self.base_url)
        streams = re.findall(r'https://f\.bondagevalley\.cc/[^"\'\s]+\.mp4[^"\'\s<]*', content or "", re.I)
        if not streams:
            return None
        return {"url": html.unescape(streams[0]).replace("\\/", "/"), "headers": self._headers(url, "*/*"), "extension": "mp4"}

    def play_video(self, url):
        resolved = self.resolve_recording_stream(url)
        if not resolved:
            self.notify_error("Could not resolve Bondage Valley stream")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return
        controller = ProxyController(upstream_url=resolved["url"], upstream_headers=resolved["headers"], session=self.session, skip_resolve=True, probe_size=True, use_urllib=False)
        proxy_url = controller.start()
        item = xbmcgui.ListItem(path=proxy_url)
        item.setProperty("IsPlayable", "true")
        item.setMimeType("video/mp4")
        item.setContentLookup(False)
        xbmcplugin.setResolvedUrl(self.addon_handle, True, item)
        PlaybackGuard(xbmc.Player(), xbmc.Monitor(), proxy_url, controller).start()
