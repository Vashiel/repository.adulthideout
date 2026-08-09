#!/usr/bin/env python
# -*- coding: utf-8 -*-

import html
import re
import urllib.parse

import requests
import xbmcgui
import xbmcplugin

from resources.lib.base_website import BaseWebsite
from resources.lib.resolvers import resolver


class BestBondageVideos(BaseWebsite):
    label = "Best Bondage Videos"

    def __init__(self, addon_handle, addon=None):
        super().__init__("bestbondagevideos", "https://bestbondagevideos.com/", "https://bestbondagevideos.com/?s={}", addon_handle, addon)
        self.session = requests.Session()
        self.ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"

    def _headers(self, referer=None):
        return {"User-Agent": self.ua, "Referer": referer or self.base_url, "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8", "Accept-Language": "en-US,en;q=0.9", "Accept-Encoding": "identity"}

    def _get(self, url, referer=None):
        try:
            response = self.session.get(url, headers=self._headers(referer), timeout=20)
            return response.text if response.status_code == 200 else ""
        except Exception as exc:
            self.logger.warning("Best Bondage Videos request failed for %s: %s", url, exc)
            return ""

    def _page_url(self, url, page):
        if page <= 1:
            return url
        parsed = urllib.parse.urlparse(url)
        path = re.sub(r'/page/\d+/?$', '/', parsed.path).rstrip('/') + '/page/{}/'.format(page)
        return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, path, parsed.params, parsed.query, ""))

    def _extract_videos(self, content):
        videos, seen = [], set()
        for block in re.findall(r'<div\b[^>]+class=["\'][^"\']*video-block[^"\']*["\'][^>]*>([\s\S]{0,2400}?)</div>\s*</div>', content or "", re.I):
            link = re.search(r'<a\b[^>]+class=["\']thumb["\'][^>]+href=["\'](https://bestbondagevideos\.com/[^"\']+/)["\']', block, re.I)
            image = re.search(r'<img\b[^>]+(?:data-src|src)=["\']([^"\']+)["\'][^>]+alt=["\']([^"\']+)["\']', block, re.I)
            if not link or not image or link.group(1) in seen:
                continue
            seen.add(link.group(1))
            duration = re.search(r'class=["\']duration["\'][^>]*>\s*([0-9:]+)', block, re.I)
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
            url = self.base_url
        if page == 1 and self.is_primary_listing_url(url):
            self.add_dir("Search", "", 5, self.icons.get("search", self.icon))
            self.add_dir("Categories", urllib.parse.urljoin(self.base_url, "/category/bondage/"), 8, self.icons.get("categories", self.icon))
        content = self._get(self._page_url(url, page))
        videos = self._extract_videos(content)
        for item in videos:
            self.add_link(item["label"], item["url"], 4, item["thumb"], self.fanart, info_labels=item["info"])
        if videos and "/page/{}/".format(page + 1) in (content or ""):
            self.add_dir("Next Page", url, 2, self.icons.get("default", self.icon), page=page + 1)
        if not videos:
            self.notify_error("No Best Bondage Videos found")
        self.end_directory("videos")

    def process_categories(self, url):
        content = self._get(self.base_url)
        seen = set()
        for href, title in re.findall(r'<a\b[^>]+href=["\'](https://bestbondagevideos\.com/category/[^"\']+/)["\'][^>]*>([\s\S]{0,300}?)</a>', content or "", re.I):
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
        embeds = re.findall(r'<iframe\b[^>]+src=["\']([^"\']+)["\']', content or "", re.I)
        stream, headers, _ = resolver.resolve_first_working(embeds, referer=url, addon=self.addon)
        return {"url": stream, "headers": headers, "extension": "m3u8" if ".m3u8" in stream else "mp4"} if stream else None

    def play_video(self, url):
        resolved = self.resolve_recording_stream(url)
        if not resolved:
            self.notify_error("Could not resolve Best Bondage Videos stream")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return
        play_url = resolved["url"]
        if resolved.get("headers") and "|" not in play_url:
            play_url += "|" + urllib.parse.urlencode(resolved["headers"])
        item = xbmcgui.ListItem(path=play_url)
        item.setProperty("IsPlayable", "true")
        xbmcplugin.setResolvedUrl(self.addon_handle, True, item)
