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


class PornoAffe(BaseWebsite):
    label = "PornoAffe"
    sort_options = ["Latest", "Most Viewed", "Top Rated"]
    sort_paths = {
        "Latest": "/neue-videos/",
        "Most Viewed": "/meist-gesehene-pornoclips/",
        "Top Rated": "/best-bewertete-pornoclips/",
    }
    categories_path = "/"
    use_playback_proxy = True

    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="pornoaffe",
            base_url="https://www.pornoaffe.net/",
            search_url="https://www.pornoaffe.net/suche/?k={}",
            addon_handle=addon_handle,
            addon=addon,
        )
        self.ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        )
        self.icon = os.path.join(
            self.addon.getAddonInfo("path"), "resources", "logos", "pornoaffe.png"
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
        import ssl
        import urllib.request
        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            req = urllib.request.Request(url, headers=self._headers(referer))
            with urllib.request.urlopen(req, context=ctx, timeout=20) as resp:
                return resp.read().decode("utf-8", errors="ignore")
        except Exception as exc:
            self.logger.warning(f"[pornoaffe] Request failed for {url}: {exc}")
        return ""

    def _clean(self, value):
        if not value:
            return ""
        value = re.sub(r"<[^>]+>", " ", value)
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
        path = self.sort_paths.get(sort_key) or "/neue-videos/"
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
            ),
        ]

    def select_sort(self, original_url=None):
        dialog = xbmcgui.Dialog()
        selected = dialog.select("Select Sort", self.sort_options)
        if selected < 0:
            return
        setting_id = f"{self.name}_sort_by"
        self.addon.setSetting(setting_id, str(selected))
        sort_key = self.sort_options[selected]
        path = self.sort_paths.get(sort_key) or "/neue-videos/"
        target_url = urllib.parse.urljoin(self.base_url, path)
        encoded_url = urllib.parse.quote_plus(target_url)
        xbmc.executebuiltin(f"Container.Update({sys.argv[0]}?mode=2&url={encoded_url})")

    def is_primary_listing_url(self, url):
        if not url or url == "BOOTSTRAP":
            return True
        parsed = urllib.parse.urlparse(url)
        path = parsed.path.rstrip("/")
        valid_paths = ["", "/neue-videos", "/meist-gesehene-pornoclips", "/best-bewertete-pornoclips"]
        return path in valid_paths

    def get_page_url(self, base_url, page):
        if page <= 1:
            return base_url
        if "?" in base_url:
            return f"{base_url}&p={page}"
        return f"{base_url.rstrip('/')}/?p={page}"

    def _normalize_thumb(self, src):
        if not src:
            return ""
        src = src.strip()
        if src.startswith("//"):
            return f"https:{src}"
        return urllib.parse.urljoin(self.base_url, src)

    def _extract_videos(self, html_content):
        videos = []
        if not html_content:
            return videos

        seen = set()
        parts = re.split(r'<div[^>]+class=["\']grid_box["\']', html_content)
        for chunk in parts[1:]:
            chunk = chunk[:2000]
            href_match = re.search(r'href=["\'](/videos/[^"\']+)["\']', chunk)
            if not href_match:
                continue
            v_path = href_match.group(1).strip()
            v_url = urllib.parse.urljoin(self.base_url, v_path)
            if v_url in seen:
                continue
            seen.add(v_url)

            title_m = re.search(r'class=["\']title["\'][^>]*>\s*<a[^>]*>([^<]+)</a>', chunk)
            if not title_m:
                title_m = re.search(r'alt=["\']([^"\']+)["\']', chunk) or re.search(r'title=["\']([^"\']+)["\']', chunk)
            title = self._clean(title_m.group(1)) if title_m else ""
            if not title:
                continue

            thumb_m = re.search(r'data-src=["\']([^"\']+)["\']', chunk) or re.search(r'src=["\']([^"\']+)["\']', chunk)
            thumb = self._normalize_thumb(thumb_m.group(1)) if thumb_m else ""
            if thumb:
                thumb = build_thumb_url(thumb, referer=self.base_url)

            dur_m = re.search(r'class=["\'][^"\']*duration[^"\']*["\'][^>]*>([^<]+)</div>', chunk)
            duration = self._clean(dur_m.group(1)) if dur_m else None

            rating_m = re.search(r'class=["\'][^"\']*rating[^"\']*["\'][^>]*>([^<]+)</div>', chunk)
            if not rating_m:
                rating_m = re.search(r'title=["\'](\d+%)["\']', chunk)
            rating = rating_m.group(1).strip() if rating_m else ""

            info = {"title": title, "plot": title}
            if duration:
                info["duration"] = duration
            if rating:
                info["rating"] = rating

            videos.append({
                "label": title,
                "url": v_url,
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
            self.notify_error("Could not load PornoAffe videos")
            self.end_directory("videos")
            return

        c_menu = self._context_menu(url)
        for v in videos:
            self.add_link(
                v["label"],
                v["url"],
                4,
                v["thumb"],
                self.fanart,
                info_labels=v["info"],
                context_menu=c_menu,
            )

        has_next = f"?p={page + 1}" in html_content or f"&p={page + 1}" in html_content or f"&amp;p={page + 1}" in html_content
        if has_next:
            self.add_dir("Next Page", url, 2, self.icons.get("default", self.icon), page=page + 1)
        self.end_directory("videos")

    def process_categories(self, url=None):
        cat_url = urllib.parse.urljoin(self.base_url, self.categories_path)
        html_content = self._get(cat_url, referer=self.base_url)
        matches = re.findall(r'<a[^>]+href=["\'](/kategorie/[^"\']+)["\'][^>]*>([\s\S]*?)</a>', html_content or "")
        seen = {}
        for path, inner in matches:
            alt = re.search(r'alt=["\']([^"\']+)["\']', inner)
            title = alt.group(1) if alt else re.sub(r'<[^>]+>', ' ', inner)
            title = self._clean(title)
            if not title:
                continue
            img = re.search(r'src=["\']([^"\']+)["\']', inner)
            thumb = self._normalize_thumb(img.group(1)) if img else ""
            if thumb:
                thumb = build_thumb_url(thumb, referer=self.base_url)

            if path not in seen or (not seen[path][1] and thumb):
                seen[path] = (title, thumb)

        for path, (title, thumb) in sorted(seen.items(), key=lambda item: item[1][0].lower()):
            full_url = urllib.parse.urljoin(self.base_url, path)
            cat_icon = thumb or self.icons.get("categories", self.icon)
            self.add_dir(title, full_url, 2, cat_icon)
        self.end_directory("categories")

    def search(self, query):
        if query:
            search_target = self.search_url.format(urllib.parse.quote_plus(query.strip()))
            self.process_content(search_target)

    def resolve_recording_stream(self, url):
        page_html = self._get(url, referer=self.base_url)
        sources = re.findall(r'<source\b[^>]+src=["\']([^"\']+\.mp4[^"\']*)["\']', page_html or "", re.I)
        s720 = [s for s in sources if "720p" in s]
        stream_url = s720[0] if s720 else (sources[0] if sources else None)
        if not stream_url:
            metas = re.findall(r'<meta\b[^>]+content=["\'](https?://[^"\']+\.mp4[^"\']*)["\']', page_html or "", re.I)
            stream_url = metas[0] if metas else None
        if not stream_url:
            return None
        stream_url = html.unescape(stream_url).strip()
        if stream_url.startswith("//"):
            stream_url = f"https:{stream_url}"
        return {
            "url": stream_url,
            "headers": {
                "User-Agent": self.ua,
                "Referer": self.base_url,
            },
            "extension": "mp4",
        }

    def play_video(self, url):
        resolved = self.resolve_recording_stream(url)
        if not resolved:
            self.notify_error("Could not resolve PornoAffe stream")
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
                self.logger.warning(f"[pornoaffe] ProxyController failed: {exc}")
        if headers and playback_controller is None:
            play_url = f"{play_url}|{urllib.parse.urlencode(headers)}"

        item = xbmcgui.ListItem(path=play_url)
        item.setProperty("IsPlayable", "true")
        item.setMimeType("video/mp4")
        item.setContentLookup(False)
        xbmcplugin.setResolvedUrl(self.addon_handle, True, item)
        if playback_controller:
            PlaybackGuard(xbmc.Player(), xbmc.Monitor(), play_url, playback_controller).start()
