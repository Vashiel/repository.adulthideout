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
from resources.lib.thumb_proxy import build_thumb_url


class CosplayPornTube(BaseWebsite):
    label = "CosplayPornTube"
    sort_options = ["Latest", "Most Viewed", "Top Rated"]
    sort_paths = {
        "Latest": "/",
        "Most Viewed": "/?filter=most-viewed",
        "Top Rated": "/?filter=popular",
    }

    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="cosplayporntube",
            base_url="https://cosplayporntube.com/",
            search_url="https://cosplayporntube.com/?s={}",
            addon_handle=addon_handle,
            addon=addon,
        )
        self.session = requests.Session()
        self.ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/127.0.0.0 Safari/537.36"
        )

    def _headers(self, referer=None, accept=None):
        return {
            "User-Agent": self.ua,
            "Referer": referer or self.base_url,
            "Accept": accept or "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "identity",
        }

    def _get(self, url, referer=None):
        try:
            response = self.session.get(url, headers=self._headers(referer), timeout=20)
            if response.status_code == 200:
                return response.text
            self.logger.warning("CosplayPornTube HTTP %s for %s", response.status_code, url)
        except Exception as exc:
            self.logger.warning("CosplayPornTube request failed for %s: %s", url, exc)
            self.session = requests.Session()
        return ""

    def _absolute(self, value, base=None):
        return urllib.parse.urljoin(base or self.base_url, html.unescape(value or "").strip())

    def _clean(self, value):
        return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", value or ""))).strip()

    def _sort_index(self):
        try:
            return max(0, min(int(self.addon.getSetting("cosplayporntube_sort_by") or "0"), len(self.sort_options) - 1))
        except (TypeError, ValueError):
            return 0

    def get_start_url_and_label(self):
        option = self.sort_options[self._sort_index()]
        return self._absolute(self.sort_paths[option]), "{} [COLOR yellow]{}[/COLOR]".format(self.label, option)

    def get_page_url(self, url, page):
        if page <= 1:
            return url
        parsed = urllib.parse.urlparse(url)
        path = re.sub(r"/page/\d+/?$", "/", parsed.path)
        path = path.rstrip("/") + "/page/{}/".format(page)
        return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, path, parsed.params, parsed.query, parsed.fragment))

    def _extract_videos(self, content):
        items = []
        seen = set()
        blocks = re.split(
            r'(?=<div\b[^>]*\bid=["\']post-\d+["\'][^>]*class=["\'][^"\']*\bitem\b)',
            content or "",
            flags=re.IGNORECASE,
        )
        for block in blocks:
            if "/video/" not in block:
                continue
            block = block[:3200]
            link = re.search(r'<a\b[^>]+href=["\']([^"\']*/video/[^"\']+/?)["\']', block, re.IGNORECASE)
            if not link:
                continue
            video_url = self._absolute(link.group(1))
            if video_url in seen:
                continue
            title = re.search(r'<a\b[^>]+href=["\'][^"\']+/video/[^"\']+["\'][^>]+title=["\']([^"\']+)', block, re.IGNORECASE)
            if not title:
                title = re.search(r'class=["\'][^"\']*title-wrap[^"\']*["\'][^>]*>([\s\S]*?)</span>', block, re.IGNORECASE)
            clean_title = self._clean(title.group(1) if title else "")
            thumb = re.search(r'background-image\s*:\s*url\(([^)]+)\)', block, re.IGNORECASE)
            duration = re.search(r'class=["\'][^"\']*video-info[^"\']*["\'][^>]*>([^<]+)', block, re.IGNORECASE)
            duration_text = self._clean(duration.group(1)) if duration else ""
            if not clean_title:
                continue
            seen.add(video_url)
            info = {"title": clean_title, "plot": clean_title}
            seconds = self.convert_duration(duration_text)
            if seconds:
                info["duration"] = seconds
            label = "{} [COLOR lime]({})[/COLOR]".format(clean_title, duration_text) if duration_text else clean_title
            thumb_url = self._absolute(thumb.group(1).strip("'\"")) if thumb else self.icon
            if thumb_url != self.icon:
                thumb_url = build_thumb_url(thumb_url, referer=self.base_url)
            items.append({
                "label": label,
                "url": video_url,
                "thumb": thumb_url,
                "info": info,
            })
        return items

    def process_content(self, url, page=1):
        if not url or url == "BOOTSTRAP":
            url, _ = self.get_start_url_and_label()
        target = self.get_page_url(url, page)
        content = self._get(target)
        if self.is_primary_listing_url(url):
            self.add_dir("Search", "", 5, self.icons.get("search", self.icon))
            self.add_dir("Categories", self._absolute("/categories/"), 8, self.icons.get("categories", self.icon))
        items = self._extract_videos(content)
        for item in items:
            self.add_link(item["label"], item["url"], 4, item["thumb"], self.fanart, info_labels=item["info"])
        marker = "/page/{}/".format(page + 1)
        if items and marker in (content or ""):
            self.add_dir("Next Page", url, 2, self.icons.get("default", self.icon), page=page + 1)
        if not items:
            self.notify_error("No CosplayPornTube videos found")
        self.end_directory("videos")

    def process_categories(self, url):
        content = self._get(url or self._absolute("/categories/"))
        seen = set()
        for href, title in re.findall(
            r'<a\b[^>]+href=["\']([^"\']+/(?:category|categories)/[^"\']+/?)["\'][^>]*>([\s\S]{0,500}?)</a>',
            content or "",
            re.IGNORECASE,
        ):
            target = self._absolute(href)
            clean_title = self._clean(title)
            if target in seen or not clean_title:
                continue
            seen.add(target)
            self.add_dir(clean_title, target, 2, self.icons.get("categories", self.icon))
        self.end_directory("videos")

    def search(self, query):
        if query:
            self.process_content(self.search_url.format(urllib.parse.quote_plus(query.strip())))

    def resolve_recording_stream(self, url):
        content = self._get(url, referer=self.base_url)
        match = re.search(
            r'<meta\b[^>]+property=["\']og:video:url["\'][^>]+content=["\']([^"\']+)',
            content or "",
            re.IGNORECASE,
        )
        if not match:
            return None
        return {"url": self._absolute(match.group(1), url), "headers": self._headers(url, "*/*"), "extension": "mp4"}

    def play_video(self, url):
        resolved = self.resolve_recording_stream(url)
        if not resolved:
            self.notify_error("Could not resolve CosplayPornTube stream")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return
        controller = ProxyController(
            upstream_url=resolved["url"],
            upstream_headers=resolved["headers"],
            session=self.session,
            skip_resolve=True,
            probe_size=True,
            use_urllib=False,
        )
        proxy_url = controller.start()
        item = xbmcgui.ListItem(path=proxy_url)
        item.setProperty("IsPlayable", "true")
        item.setMimeType("video/mp4")
        item.setContentLookup(False)
        xbmcplugin.setResolvedUrl(self.addon_handle, True, item)
        PlaybackGuard(xbmc.Player(), xbmc.Monitor(), proxy_url, controller).start()
