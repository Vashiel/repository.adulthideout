#!/usr/bin/env python
# -*- coding: utf-8 -*-

import html
import re
import urllib.parse
import urllib.request
import ssl

import requests
import xbmc
import xbmcgui
import xbmcplugin

from resources.lib.base_website import BaseWebsite
from resources.lib.thumb_proxy import build_thumb_url
from resources.lib.proxy_utils import PlaybackGuard, ProxyController


class SFMCompile(BaseWebsite):
    label = "SFM Compile"
    sort_options = ["Latest", "Top Animations", "Trending", "Longer Clips"]
    sort_paths = {
        "Latest": "/",
        "Top Animations": "/tag/sound/?order=most_views",
        "Trending": "/?filter-by=trending",
        "Longer Clips": "/tag/longer-clips/",
    }

    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="sfmcompile",
            base_url="https://sfmcompile.club",
            search_url="https://sfmcompile.club/?s={}",
            addon_handle=addon_handle,
            addon=addon,
        )
        self.session = requests.Session()
        self.ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        )
        self.session.headers.update({"User-Agent": self.ua})

    def _fetch(self, url, referer=None):
        headers = {
            "User-Agent": self.ua,
            "Referer": referer or self.base_url + "/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
        try:
            resp = self.session.get(url, headers=headers, timeout=12)
            if resp.status_code == 200:
                return resp.text
            self.logger.warning("[%s] HTTP %s for %s", self.name, resp.status_code, url)
        except Exception as exc:
            self.logger.warning("[%s] Request failed for %s: %s", self.name, url, exc)
        return ""

    def get_start_url_and_label(self):
        try:
            index = int(self.addon.getSetting(self.name + "_sort_by") or "0")
        except (TypeError, ValueError):
            index = 0
        index = index if 0 <= index < len(self.sort_options) else 0
        option = self.sort_options[index]
        return urllib.parse.urljoin(self.base_url + "/", self.sort_paths[option].lstrip("/")), f"{self.label} [COLOR yellow]{option}[/COLOR]"

    def process_content(self, url, page=1):
        start_url, _ = self.get_start_url_and_label()
        is_root = (
            not url
            or url == "BOOTSTRAP"
            or url.rstrip("/") == self.base_url.rstrip("/")
            or url.rstrip("/") == start_url.rstrip("/")
        )

        if not url or url == "BOOTSTRAP":
            url = start_url

        is_search = "?s=" in url or "&s=" in url
        is_category = "/category/" in url or "/tag/" in url

        if is_root or (not is_search and not is_category):
            self.add_dir("Search", "", 5, self.icons.get("search", self.icon), name_param=self.name)
            self.add_dir("Categories", "CATEGORIES", 8, self.icons.get("categories", self.icon))
            self.add_dir("Top Animations", urllib.parse.urljoin(self.base_url, "/tag/sound/?order=most_views"), 2, self.icons.get("default", self.icon))
            self.add_dir("Trending", urllib.parse.urljoin(self.base_url, "/?filter-by=trending"), 2, self.icons.get("default", self.icon))
            self.add_dir("Longer Clips", urllib.parse.urljoin(self.base_url, "/tag/longer-clips/"), 2, self.icons.get("default", self.icon))

        page_html = self._fetch(url)
        if not page_html:
            self.end_directory("videos")
            return

        articles = re.findall(r'<article[^>]*id="post-(\d+)"[^>]*>(.*?)</article>', page_html, re.DOTALL)
        seen = set()

        for pid, content in articles:
            title_m = re.search(r'<h2[^>]*class="[^"]*entry-title"[^>]*><a href="([^"]+)"[^>]*>(.*?)</a>', content, re.DOTALL)
            if not title_m:
                continue

            post_url = title_m.group(1).strip()
            if post_url in seen:
                continue
            seen.add(post_url)

            raw_title = re.sub(r'<[^>]+>', '', title_m.group(2)).strip()
            title = html.unescape(raw_title)

            # Poster image (prefer JPEG over webp for Kodi compatibility)
            poster_m = (
                re.search(r'data-poster-image="([^"]+)"', content)
                or re.search(r'poster="([^"]+)"', content)
                or re.search(r'data-poster-webp="([^"]+)"', content)
                or re.search(r'<img[^>]+src="([^"]+)"', content)
            )
            thumb = poster_m.group(1).strip() if poster_m else self.icon
            thumb = build_thumb_url(thumb, referer=self.base_url)

            # Category / Tag
            cat_m = re.search(r'class="entry-categories-inner">[\s\S]*?<a[^>]*>([^<]+)</a>', content)
            tag = f" [COLOR gray][{html.unescape(cat_m.group(1).strip())}][/COLOR]" if cat_m else ""

            info = {"title": title, "plot": title}
            self.add_link(f"{title}{tag}", post_url, 4, thumb, self.fanart, info_labels=info)

        # Pagination: /page/{page}/
        next_m = re.search(r'<a[^>]+class="[^"]*next[^"]*"[^>]+href="([^"]+)"', page_html, re.I)
        if next_m:
            next_url = next_m.group(1).strip()
            self.add_dir("[COLOR blue]Next Page >>>[/COLOR]", next_url, 2, self.icons.get("default", self.icon))

        self.end_directory("videos")

    def process_categories(self, url):
        cats_url = urllib.parse.urljoin(self.base_url, "/all-category/")
        page_html = self._fetch(cats_url)
        cats = re.findall(r'<a href="(https://sfmcompile\.club/category/[^"]+)"[^>]*>([^<]+)</a>', page_html or "")

        seen = set()
        for cat_url, cat_name in cats:
            name = html.unescape(cat_name).strip()
            if cat_url in seen or not name:
                continue
            seen.add(cat_url)
            self.add_dir(name, cat_url, 2, self.icons.get("categories", self.icon))

        self.end_directory("categories")

    def search(self, query):
        if query:
            clean_query = query.strip()
            search_page = self.search_url.format(urllib.parse.quote_plus(clean_query))
            self.process_content(search_page)

    def play_video(self, url):
        stream_url = ""
        if url.endswith(".mp4"):
            stream_url = url
        else:
            page_html = self._fetch(url)
            stream_m = (
                re.search(r'<source[^>]+src="([^"]+\.mp4[^"]*)"', page_html)
                or re.search(r'<video[^>]+src="([^"]+\.mp4[^"]*)"', page_html)
                or re.search(r'href="([^"]+\.mp4[^"]*)"', page_html)
            )
            if stream_m:
                stream_url = stream_m.group(1).strip()

        if not stream_url:
            self.notify_error("Video stream not found")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return

        headers = {
            "User-Agent": self.ua,
            "Referer": url,
        }

        try:
            controller = ProxyController(stream_url, headers=headers, buffer_size=1024 * 1024)
            PlaybackGuard(xbmc.Player(), xbmc.Monitor(), stream_url, controller).start()
            final_url = controller.proxy_url
        except Exception:
            header_str = f"|User-Agent={urllib.parse.quote(self.ua)}&Referer={urllib.parse.quote(url)}"
            final_url = stream_url + header_str

        list_item = xbmcgui.ListItem(path=final_url)
        list_item.setProperty("IsPlayable", "true")
        list_item.setMimeType("video/mp4")
        xbmcplugin.setResolvedUrl(self.addon_handle, True, list_item)
