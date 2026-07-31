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
from resources.lib.resolvers import resolver
from resources.lib.thumb_proxy import build_thumb_url


class HypnoPorn(BaseWebsite):
    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="hypnoporn",
            base_url="https://hypnoporn.net/",
            search_url="https://hypnoporn.net/?s={}",
            addon_handle=addon_handle,
            addon=addon,
        )
        self.label = "HypnoPorn"
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
            self.logger.warning("HypnoPorn HTTP %s for %s", response.status_code, url)
        except Exception as exc:
            self.logger.warning("HypnoPorn request failed for %s: %s", url, exc)
            self.session = requests.Session()
        return ""

    def _absolute(self, value, base=None):
        return urllib.parse.urljoin(base or self.base_url, html.unescape(value or "").strip())

    def _clean(self, value):
        return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", value or ""))).strip()

    def get_start_url_and_label(self):
        return self.base_url, self.label

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
        for block in re.findall(
            r'<div\b[^>]*class=["\'][^"\']*\bitem\b[^"\']*\bpost\b[^"\']*["\'][^>]*>[\s\S]{0,3200}?</div>\s*</div>',
            content or "",
            re.IGNORECASE,
        ):
            match = re.search(r'<a\b[^>]+href=["\'](https?://hypnoporn\.net/[^"\']+/)["\']', block, re.IGNORECASE)
            if not match:
                continue
            target = self._absolute(match.group(1))
            if target in seen:
                continue
            title = re.search(r'\stitle=["\']([^"\']+)["\']', block, re.IGNORECASE)
            image = re.search(r'<img\b[^>]+\bsrc=["\']([^"\']+)["\'][^>]*>', block, re.IGNORECASE)
            clean_title = self._clean(title.group(1) if title else "")
            if not clean_title:
                continue
            seen.add(target)
            thumb_url = self._absolute(image.group(1)) if image else self.icon
            if thumb_url != self.icon:
                thumb_url = build_thumb_url(thumb_url, referer=self.base_url)
            items.append({
                "title": clean_title,
                "url": target,
                "thumb": thumb_url,
                "info": {"title": clean_title, "plot": clean_title},
            })
        return items

    def process_content(self, url, page=1):
        url = self.base_url if not url or url == "BOOTSTRAP" else url
        target = self.get_page_url(url, page)
        content = self._get(target)
        if self.is_primary_listing_url(url):
            self.add_dir("Search", "", 5, self.icons.get("search", self.icon))
            self.add_dir("Categories", self._absolute("/category/"), 8, self.icons.get("categories", self.icon))
        items = self._extract_videos(content)
        for item in items:
            self.add_link(item["title"], item["url"], 4, item["thumb"], self.fanart, info_labels=item["info"])
        marker = "/page/{}/".format(page + 1)
        if items and marker in (content or ""):
            self.add_dir("Next Page", url, 2, self.icons.get("default", self.icon), page=page + 1)
        if not items:
            self.notify_error("No HypnoPorn videos found")
        self.end_directory("videos")

    def process_categories(self, url):
        data_url = self._absolute("wp-json/wp/v2/categories?per_page=100&hide_empty=true&orderby=count&order=desc")
        try:
            response = self.session.get(data_url, headers=self._headers(self.base_url, "application/json"), timeout=20)
            categories = response.json() if response.status_code == 200 else []
        except Exception as exc:
            self.logger.warning("HypnoPorn categories failed: %s", exc)
            categories = []
        for category in categories:
            name = self._clean(category.get("name"))
            link = self._absolute(category.get("link"))
            if name and link and name.lower() != "uncategorized":
                self.add_dir(name, link, 2, self.icons.get("categories", self.icon))
        self.end_directory("videos")

    def search(self, query):
        if query:
            self.process_content(self.search_url.format(urllib.parse.quote_plus(query.strip())))

    def _resolve_mirrors(self, url):
        content = self._get(url, referer=self.base_url)
        mirrors = []
        for value in re.findall(r'<iframe\b[^>]+\bsrc=["\']([^"\']+)["\']', content or "", re.IGNORECASE):
            target = self._absolute(value, url)
            if resolver.resolver_entry_for_url(target) and target not in mirrors:
                mirrors.append(target)
        for mirror in resolver.sort_urls_by_resolver_preference(mirrors, self.addon):
            if not resolver.is_resolver_enabled(mirror, self.addon):
                continue
            stream_url, stream_headers = resolver.resolve(mirror, referer=url, headers=self._headers(url))
            if not stream_url or not stream_url.startswith("http"):
                continue
            try:
                headers = dict(stream_headers or {})
                headers.setdefault("User-Agent", self.ua)
                headers["Range"] = "bytes=0-1023"
                probe = self.session.get(stream_url, headers=headers, timeout=18, stream=True)
                usable = probe.status_code in (200, 206)
                probe.close()
                if usable:
                    return stream_url, stream_headers or {}, mirror
            except Exception as exc:
                self.logger.warning("HypnoPorn mirror probe failed for %s: %s", mirror, exc)
        return "", {}, ""

    def resolve_recording_stream(self, url):
        stream_url, headers, _ = self._resolve_mirrors(url)
        if not stream_url:
            return None
        return {
            "url": stream_url,
            "headers": headers,
            "extension": "m3u8" if ".m3u8" in stream_url.lower() else "mp4",
        }

    def play_video(self, url):
        resolved = self.resolve_recording_stream(url)
        if not resolved:
            self.notify_error("Could not resolve HypnoPorn stream")
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
        item.setMimeType("application/vnd.apple.mpegurl" if resolved["extension"] == "m3u8" else "video/mp4")
        item.setContentLookup(False)
        xbmcplugin.setResolvedUrl(self.addon_handle, True, item)
        PlaybackGuard(xbmc.Player(), xbmc.Monitor(), proxy_url, controller).start()
