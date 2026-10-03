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
from resources.lib.proxy_utils import HlsProxyController, PlaybackGuard
from resources.lib.thumb_proxy import build_thumb_url


class HentaiCosplay(BaseWebsite):
    label = "Hentai Cosplay"
    sort_options = ["Latest", "Ranking"]
    sort_paths = {
        "Latest": "/search-video/",
        "Ranking": "/ranking-video/",
    }
    POPULAR_TAGS = [
        "Genshin Impact",
        "Honkai Star Rail",
        "Fate Grand Order",
        "Azur Lane",
        "Blue Archive",
        "NieR",
        "Final Fantasy",
        "League of Legends",
        "Dead or Alive",
        "Street Fighter",
        "Overwatch",
        "Chun-Li",
        "Tifa",
        "2B",
        "Bunny Girl",
        "Maid",
        "Schoolgirl",
        "JK",
        "Swimsuit",
        "Real Life",
    ]

    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="hentaicosplay",
            base_url="https://hentai-cosplay.com/",
            search_url="https://hentai-cosplay.com/search-video/keyword/{}/",
            addon_handle=addon_handle,
            addon=addon,
        )
        self.ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        )
        self.icon = os.path.join(
            self.addon.getAddonInfo("path"), "resources", "logos", "hentaicosplay.png"
        )
        self.icons["default"] = self.icon

    def _headers(self, referer=None, accept=None):
        return {
            "User-Agent": self.ua,
            "Referer": referer or self.base_url,
            "Accept": accept or "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,ja;q=0.8",
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
            self.logger.warning(f"[hentaicosplay] Request failed for {url}: {exc}")
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
        path = self.sort_paths.get(sort_key) or "/search-video/"
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
        items = re.findall(r'<div class=["\']image-list-item["\']>([\s\S]*?)</p>\s*</div>', html_content or "", re.I)
        if not items:
            items = re.findall(r'<div class=["\']image-list-item["\']>([\s\S]*?)</div>\s*</li>', html_content or "", re.I)

        for block in items:
            link_m = re.search(r'<a\b[^>]+href=["\'](/video/[^"\']+)["\']', block, re.I)
            if not link_m:
                continue
            video_url = urllib.parse.urljoin(self.base_url, link_m.group(1).strip())
            if video_url in seen:
                continue
            seen.add(video_url)

            # Title
            t_m = re.search(r'<p class=["\']image-list-item-title["\']>[\s\S]*?<a[^>]*>([^<]+)</a>', block, re.I)
            if t_m:
                title = self._clean(t_m.group(1))
            else:
                alt_m = re.search(r'alt=["\']([^"\']+)["\']', block, re.I)
                title = self._clean(alt_m.group(1)) if alt_m else "Video"

            # Thumb
            img_m = re.search(r'<img\b[^>]+src=["\']([^"\']+)["\']', block, re.I)
            thumb = img_m.group(1).strip() if img_m else ""
            if thumb:
                thumb = build_thumb_url(thumb, referer=self.base_url)
            else:
                thumb = self.icon

            # Date
            d_m = re.search(r'<p class=["\']image-list-item-regist-date["\']>[\s\S]*?<span>([^<]+)</span>', block, re.I)
            date = d_m.group(1).strip() if d_m else ""

            info = {"title": title, "plot": title}
            if date:
                info["date"] = date

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

        target_url = url
        parsed = urllib.parse.urlparse(url)
        if parsed.path in ("", "/"):
            target_url = urllib.parse.urljoin(self.base_url, "/search-video/")

        fetch_url = self.get_page_url(target_url, page)
        html_content = self._get(fetch_url, referer=self.base_url)
        videos = self._extract_videos(html_content)

        if not videos:
            self.notify_error("Could not load Hentai Cosplay videos")
            self.end_directory("videos")
            return

        for v in videos:
            self.add_link(
                v["label"], v["url"], 4, v["thumb"], self.fanart,
                info_labels=v["info"],
            )

        # Check next page
        has_next = f"/page/{page + 1}/" in (html_content or "") or f"/p/{page + 1}/" in (html_content or "")
        if has_next:
            self.add_dir("Next Page", target_url, 2, self.icons.get("default", self.icon), page=page + 1)
        self.end_directory("videos")

    def process_categories(self, url=None):
        for tag in self.POPULAR_TAGS:
            cat_url = self.search_url.format(urllib.parse.quote(tag))
            self.add_dir(tag, cat_url, 2, self.icons.get("categories", self.icon))
        self.end_directory("categories")

    def search(self, query):
        if query:
            search_target = self.search_url.format(urllib.parse.quote(query.strip()))
            self.process_content(search_target)

    def resolve_recording_stream(self, url):
        page_html = self._get(url, referer=self.base_url)
        m3u8_matches = re.findall(r'<source\b[^>]+src=["\']([^"\']+\.m3u8[^"\']*)["\']', page_html or "", re.I)
        if not m3u8_matches:
            m3u8_matches = re.findall(r'https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*', page_html or "", re.I)
        if not m3u8_matches:
            return None
        return {
            "url": html.unescape(m3u8_matches[0]).strip(),
            "headers": {
                "User-Agent": self.ua,
                "Referer": self.base_url,
            },
            "extension": "m3u8",
        }

    def play_video(self, url):
        resolved = self.resolve_recording_stream(url)
        if not resolved:
            self.notify_error("Could not resolve Hentai Cosplay stream")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return
        stream_url = resolved["url"]
        headers = resolved.get("headers") or {}
        controller = None
        try:
            controller = HlsProxyController(
                stream_url,
                headers=headers,
                preserve_query=True,
            )
            play_url = controller.start()
            self.logger.info("[hentaicosplay] Using in-process HLS proxy for playback")
        except Exception as exc:
            controller = None
            self.logger.warning(f"[hentaicosplay] HLS proxy failed, falling back direct: {exc}")
            headers_str = urllib.parse.urlencode(headers) if headers else ""
            play_url = f"{stream_url}|{headers_str}" if headers_str else stream_url

        item = xbmcgui.ListItem(path=play_url)
        item.setProperty("IsPlayable", "true")
        item.setMimeType("application/vnd.apple.mpegurl")
        item.setContentLookup(False)
        if controller is None and xbmc.getCondVisibility("System.HasAddon(inputstream.adaptive)"):
            item.setProperty("inputstream", "inputstream.adaptive")
            item.setProperty("inputstream.adaptive.manifest_type", "hls")
            if headers:
                hdr_enc = urllib.parse.urlencode(headers)
                item.setProperty("inputstream.adaptive.manifest_headers", hdr_enc)
                item.setProperty("inputstream.adaptive.stream_headers", hdr_enc)
        xbmcplugin.setResolvedUrl(self.addon_handle, True, item)
        if controller:
            PlaybackGuard(xbmc.Player(), xbmc.Monitor(), play_url, controller).start()
