#!/usr/bin/env python
# -*- coding: utf-8 -*-

import html
import os
import re
import sys
import urllib.parse

import xbmc
import xbmcgui
import xbmcplugin

from resources.lib.base_website import BaseWebsite
from resources.lib.proxy_utils import PlaybackGuard, ProxyController
from resources.lib.thumb_proxy import build_thumb_url


class DeutschePornos(BaseWebsite):
    label = "Deutsche Pornos"
    sort_options = ["Latest", "Most Viewed", "Popular", "Longest"]
    sort_paths = {
        "Latest": "/?filter=latest",
        "Most Viewed": "/?filter=most-viewed",
        "Popular": "/?filter=popular",
        "Longest": "/?filter=longest",
    }
    categories_path = "/porno-kategorien/"
    use_playback_proxy = True

    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="deutschepornos",
            base_url="https://www.deutsche-pornos.me/",
            search_url="https://www.deutsche-pornos.me/?s={}",
            addon_handle=addon_handle,
            addon=addon,
        )
        self.ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        )
        self.icon = os.path.join(
            self.addon.getAddonInfo("path"), "resources", "logos", "deutschepornos.png"
        )
        self.icons["default"] = self.icon

    def _headers(self, referer=None, accept=None):
        return {
            "User-Agent": self.ua,
            "Referer": referer or self.base_url,
            "Accept": accept or "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
        }

    def _get(self, url, referer=None):
        import urllib.request
        import ssl
        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            req = urllib.request.Request(url, headers=self._headers(referer))
            with urllib.request.urlopen(req, context=ctx, timeout=20) as resp:
                return resp.read().decode("utf-8", errors="ignore")
        except Exception as exc:
            self.logger.warning(f"[deutschepornos] Request failed for {url}: {exc}")
        return ""

    def _clean(self, value):
        value = re.sub(r"<[^>]+>", " ", value or "")
        return re.sub(r"\s+", " ", html.unescape(value)).strip()

    def get_start_url_and_label(self):
        setting_id = f"{self.name}_sort_by"
        saved = self.addon.getSetting(setting_id)
        try:
            idx = int(saved)
        except (ValueError, TypeError):
            try:
                idx = self.sort_options.index(saved)
            except (ValueError, TypeError):
                idx = 0
        if 0 <= idx < len(self.sort_options):
            sort_key = self.sort_options[idx]
        else:
            sort_key = self.sort_options[0]
        path = self.sort_paths.get(sort_key) or "/?filter=latest"
        url = urllib.parse.urljoin(self.base_url, path)
        return url, f"{self.label} [COLOR yellow]{sort_key}[/COLOR]"

    def _context_menu(self, original_url=None):
        suffix = ""
        if original_url:
            suffix = f"&original_url={urllib.parse.quote_plus(original_url)}"
        return [
            (
                "Sort by...",
                f"RunPlugin({sys.argv[0]}?mode=7&action=select_sort&website={self.name}{suffix})",
            )
        ]

    def get_page_url(self, base_url, page_num):
        if page_num <= 1:
            return base_url
        parsed = urllib.parse.urlparse(base_url)
        path = re.sub(r"/page/\d+/?$", "/", parsed.path or "/")
        path = path.rstrip("/") + f"/page/{page_num}/"
        return urllib.parse.urlunparse(
            (parsed.scheme, parsed.netloc, path, parsed.params, parsed.query, parsed.fragment)
        )

    def _extract_videos(self, html_content):
        videos = []
        seen = set()
        articles = re.findall(r'<article\b[^>]*>([\s\S]*?)</article>', html_content or "", re.I)
        for art in articles:
            link_m = re.search(r'<a\b[^>]+href=["\'](https?://[^"\']*/video/[^"\']+)["\']', art, re.I)
            if not link_m:
                continue
            video_url = urllib.parse.urljoin(self.base_url, link_m.group(1).strip())
            if video_url in seen:
                continue
            seen.add(video_url)

            # Title
            title_m = re.search(r'<header class=["\']entry-header["\']>[\s\S]*?<span>([^<]+)</span>', art, re.I)
            if title_m:
                title = self._clean(title_m.group(1))
            else:
                t2 = re.search(r'title=["\']([^"\']+)["\']', art, re.I)
                title = self._clean(t2.group(1)) if t2 else "Video"

            # Thumb
            poster_m = re.search(r'data-poster=["\']([^"\']+)["\']', art, re.I)
            if not poster_m:
                poster_m = re.search(r'poster=["\']([^"\']+)["\']', art, re.I)
            if not poster_m:
                poster_m = re.search(r'<img\b[^>]+src=["\']([^"\']+)["\']', art, re.I)
            thumb = poster_m.group(1).strip() if poster_m else ""
            if thumb:
                thumb = build_thumb_url(thumb, referer=self.base_url)
            else:
                thumb = self.icon

            # Duration
            dur_m = re.search(r'<span class=["\']duration["\']>[\s\S]*?(\d+:\d+(?::\d+)?)', art, re.I)
            duration = dur_m.group(1).strip() if dur_m else ""

            info = {"title": title, "plot": title}
            if duration:
                info["duration"] = duration

            videos.append({
                "label": title,
                "url": video_url,
                "thumb": thumb,
                "info": info,
            })
        return videos

    def process_content(self, url, page=1):
        url = self.base_url if not url or url == "BOOTSTRAP" else url
        if self.is_primary_listing_url(url):
            self.add_dir("Search", "", 5, self.icons.get("search", self.icon))
            self.add_dir("Categories", "CATEGORIES", 8, self.icons.get("categories", self.icon))

        fetch_url = self.get_page_url(url, page)
        html_content = self._get(fetch_url, referer=self.base_url)
        videos = self._extract_videos(html_content)

        if not videos:
            self.notify_error("Could not load Deutsche Pornos videos")
            self.end_directory("videos")
            return

        for v in videos:
            self.add_link(
                v["label"], v["url"], 4, v["thumb"], self.fanart,
                info_labels=v["info"],
            )

        # Check next page
        has_next = f"/page/{page + 1}/" in (html_content or "")
        if has_next:
            self.add_dir("Next Page", url, 2, self.icons.get("default", self.icon), page=page + 1)
        self.end_directory("videos")

    def process_categories(self, url=None):
        cat_url = urllib.parse.urljoin(self.base_url, self.categories_path)
        html_content = self._get(cat_url, referer=self.base_url)
        cats = re.findall(
            r'<a[^>]+href=["\'](https://www\.deutsche-pornos\.me/kategorien/deutsche-pornos/[^"\']+)["\'][^>]*>([\s\S]*?)</a>',
            html_content or "",
        )
        seen = set()
        for href, text in cats:
            clean_name = self._clean(text)
            if not clean_name or href in seen:
                continue
            seen.add(href)
            self.add_dir(clean_name, href, 2, self.icons.get("categories", self.icon))
        self.end_directory("categories")

    def search(self, query):
        if query:
            search_target = self.search_url.format(urllib.parse.quote_plus(query.strip()))
            self.process_content(search_target)

    def resolve_recording_stream(self, url):
        page_html = self._get(url, referer=self.base_url)
        sources = re.findall(r'<source\b[^>]+src=["\']([^"\']+\.mp4[^"\']*)["\']', page_html or "", re.I)
        full_sources = [s for s in sources if "-trailer" not in s]
        stream_url = full_sources[0] if full_sources else (sources[0] if sources else None)
        if not stream_url:
            metas = re.findall(r'<meta\b[^>]+content=["\'](https?://[^"\']+\.mp4[^"\']*)["\']', page_html or "", re.I)
            full_metas = [m for m in metas if "-trailer" not in m]
            stream_url = full_metas[0] if full_metas else (metas[0] if metas else None)
        if not stream_url:
            return None
        return {
            "url": html.unescape(stream_url).strip(),
            "headers": {
                "User-Agent": self.ua,
                "Referer": self.base_url,
            },
            "extension": "mp4",
        }

    def play_video(self, url):
        resolved = self.resolve_recording_stream(url)
        if not resolved:
            self.notify_error("Could not resolve Deutsche Pornos stream")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return
        play_url = resolved["url"]
        headers = resolved.get("headers") or {}
        playback_controller = None
        if self.use_playback_proxy:
            try:
                playback_controller = ProxyController(
                    upstream_url=play_url,
                    upstream_headers=headers,
                    skip_resolve=True,
                    probe_size=True,
                    use_urllib=True,
                )
                play_url = playback_controller.start()
            except Exception as exc:
                playback_controller = None
                self.logger.warning(f"[deutschepornos] ProxyController failed: {exc}")
        if headers and playback_controller is None:
            play_url = f"{play_url}|{urllib.parse.urlencode(headers)}"

        item = xbmcgui.ListItem(path=play_url)
        item.setProperty("IsPlayable", "true")
        item.setMimeType("video/mp4")
        item.setContentLookup(False)
        xbmcplugin.setResolvedUrl(self.addon_handle, True, item)
        if playback_controller:
            PlaybackGuard(xbmc.Player(), xbmc.Monitor(), play_url, playback_controller).start()
