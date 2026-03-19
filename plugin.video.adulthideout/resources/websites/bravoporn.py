# -*- coding: utf-8 -*-
import html
import re
import sys
import urllib.parse

import requests
import xbmc
import xbmcgui
import xbmcplugin

from resources.lib.base_website import BaseWebsite
from resources.lib.proxy_utils import PlaybackGuard, ProxyController
from resources.lib.resilient_http import fetch_text


class Bravoporn(BaseWebsite):
    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="bravoporn",
            base_url="https://www.bravoporn.com",
            search_url="https://www.bravoporn.com/s/?q={}",
            addon_handle=addon_handle,
            addon=addon,
        )
        self.categories_url = "https://www.bravotube.net/categories/"
        self.sort_options = ["Latest", "Popular"]
        self.sort_paths = {
            "Latest": "https://www.bravoporn.com/latest-updates/",
            "Popular": "https://www.bravoporn.com/most-popular/",
        }
        self.ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/126.0.0.0 Safari/537.36"
        )
        self.session = requests.Session()

    def get_start_url_and_label(self):
        try:
            current_idx = int(self.addon.getSetting("bravoporn_sort_by") or "0")
        except Exception:
            current_idx = 0

        if not 0 <= current_idx < len(self.sort_options):
            current_idx = 0

        sort_name = self.sort_options[current_idx]
        return self.sort_paths[sort_name], f"BravoPorn [COLOR yellow]{sort_name}[/COLOR]"

    def make_request(self, url):
        try:
            self.logger.info(f"[BravoPorn] GET {url}")
            response = self.session.get(
                url,
                headers={"User-Agent": self.ua, "Referer": self.base_url + "/"},
                timeout=20,
                allow_redirects=True,
            )
            response.raise_for_status()
            return response.text
        except Exception as exc:
            self.logger.warning(f"[BravoPorn] Session request failed for {url}: {exc}")

        content = fetch_text(
            url,
            headers={"User-Agent": self.ua, "Referer": self.base_url + "/"},
            scraper=self.session,
            logger=self.logger,
            timeout=20,
        )
        if not content:
            self.logger.error(f"[BravoPorn] Request failed for {url}")
        return content

    def _extract_video_id(self, text):
        rt_match = re.search(r'data-rt=["\']([^"\']+)["\']', text, re.IGNORECASE)
        if not rt_match:
            return None

        parts = [part.strip() for part in rt_match.group(1).replace("pqr=", "").split(":")]
        for part in reversed(parts):
            if part.isdigit() and len(part) >= 4:
                return part
        return None

    def _extract_entries(self, content):
        patterns = [
            r'<div class="video_block[^"]*">(.*?)</div>\s*<div class="video_block|<div class="clear|<div class="pagination|</body>',
            r"<div class='video_block[^']*'>(.*?)</div>\s*<div class='video_block|<div class='clear|<div class='pagination|</body>",
        ]
        for pattern in patterns:
            entries = re.findall(pattern, content, re.IGNORECASE | re.DOTALL)
            if entries:
                return entries

        return re.findall(
            r'(<a href=["\']/videos/[^"\']+/["\'].*?(?:class=["\']video_desc["\']|</strong>).*?</em>)',
            content,
            re.IGNORECASE | re.DOTALL,
        )

    def _extract_title(self, block):
        title_match = re.search(r'class=["\']video_desc["\']>([^<]+)</a>', block, re.IGNORECASE)
        if not title_match:
            title_match = re.search(r'<strong>([^<]+)</strong>', block, re.IGNORECASE)
        if not title_match:
            title_match = re.search(r'alt=["\']([^"\']+)["\']', block, re.IGNORECASE)
        if not title_match:
            return None
        return html.unescape(title_match.group(1).strip())

    def _extract_sources(self, content):
        sources = re.findall(r'(https://www\.bravoporn\.com/get_file/[^"\']+)', content, re.IGNORECASE)
        if not sources:
            rel_sources = re.findall(r'(["\'])(/??get_file/[^"\']+)\1', content, re.IGNORECASE)
            sources = [urllib.parse.urljoin(self.base_url + "/", src[1].lstrip("/")) for src in rel_sources]
        return sources

    def _fetch_video_page(self, url):
        headers = {"User-Agent": self.ua, "Referer": self.base_url + "/"}
        try:
            self.logger.info(f"[BravoPorn] GET {url}")
            response = self.session.get(url, headers=headers, timeout=20, allow_redirects=True)
            response.raise_for_status()
            return response.text, response.url
        except Exception as exc:
            self.logger.warning(f"[BravoPorn] Video page request failed for {url}: {exc}")

        content = fetch_text(url, headers=headers, scraper=self.session, logger=self.logger, timeout=20)
        return content, url

    def _resolve_playback_page(self, url, content, final_url):
        candidates = []

        canonical_match = re.search(r'rel=["\']canonical["\'][^>]*href=["\']([^"\']+)["\']', content, re.IGNORECASE)
        if canonical_match:
            candidates.append(html.unescape(canonical_match.group(1)))

        for match in re.findall(r'https://www\.bravoporn\.com/videos/\d+/', content, re.IGNORECASE):
            candidates.append(match)

        watch_match = re.search(
            r'href=["\']([^"\']+)["\'][^>]*>\s*Watch\s+this\s+video\s+on',
            content,
            re.IGNORECASE,
        )
        if watch_match:
            candidates.append(html.unescape(watch_match.group(1)))

        normalized = []
        for candidate in candidates:
            if candidate and candidate not in normalized and candidate != final_url:
                normalized.append(candidate)

        for candidate in normalized:
            retry_content, retry_final_url = self._fetch_video_page(candidate)
            if retry_content and self._extract_sources(retry_content):
                return retry_content, retry_final_url

        return content, final_url

    def search(self, query):
        if not query:
            return
        self.process_content(self.search_url.format(urllib.parse.quote_plus(query)))

    def process_content(self, url):
        start_url, _ = self.get_start_url_and_label()
        if url == "BOOTSTRAP":
            url = start_url

        context_menu = [
            ("Sort by...", f"RunPlugin({sys.argv[0]}?mode=7&action=select_sort&website={self.name})")
        ]

        self.add_dir("Search", "", 5, self.icons.get("search", self.icon), context_menu=context_menu)
        self.add_dir(
            "Categories",
            self.categories_url,
            8,
            self.icons.get("categories", self.icon),
            context_menu=context_menu,
        )

        self._list_videos(url, context_menu=context_menu)

    def _list_videos(self, url, context_menu=None):
        content = self.make_request(url)
        if not content:
            return self.end_directory("videos")

        is_bravotube_category = "bravotube.net/categories/" in url

        seen = set()
        blocks = self._extract_entries(content)

        for block in blocks:
            link_match = re.search(r'<a href=["\'](/videos/[^"\']+/)["\']', block, re.IGNORECASE)
            if not link_match:
                continue

            video_url = urllib.parse.urljoin(url, link_match.group(1))
            if is_bravotube_category:
                video_id = self._extract_video_id(block)
                if video_id:
                    video_url = f"{self.base_url}/videos/{video_id}/"

            if video_url in seen:
                continue
            seen.add(video_url)

            title = self._extract_title(block)
            if not title:
                continue

            thumb_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', block, re.IGNORECASE)
            duration_match = re.search(r'<span class=["\']time["\']>([^<]+)</span>', block, re.IGNORECASE)

            thumb = thumb_match.group(1).strip() if thumb_match else ""
            if thumb.startswith("//"):
                thumb = "https:" + thumb
            elif thumb.startswith("/"):
                thumb = urllib.parse.urljoin(url, thumb)

            info = {"title": title, "plot": title}
            duration = duration_match.group(1).strip() if duration_match else ""
            duration_seconds = self.convert_duration(duration)
            if duration_seconds:
                info["duration"] = duration_seconds

            self.add_link(
                title,
                video_url,
                4,
                thumb or self.icon,
                self.fanart,
                context_menu=context_menu,
                info_labels=info,
            )

        next_url = None
        next_match = re.search(r'href=["\']([^"\']+)["\'][^>]*>\s*Next\s*</a>', content, re.IGNORECASE)
        if next_match:
            next_url = urllib.parse.urljoin(url, html.unescape(next_match.group(1)))

        if next_url:
            self.add_dir("Next Page", next_url, 2, self.icons.get("default", self.icon), context_menu=context_menu)

        self.end_directory("videos")

    def process_categories(self, url):
        if url != self.categories_url and "/categories/" in url:
            return self._list_videos(url)

        content = self.make_request(self.categories_url)
        if not content:
            return self.end_directory("videos")

        seen = set()
        pattern = re.compile(
            r'<a href="(/categories/[^"#]+/)".*?<img src="([^"]+)"[^>]*alt="([^"]+)"',
            re.IGNORECASE | re.DOTALL,
        )
        for path, thumb, title in pattern.findall(content):
            full_url = urllib.parse.urljoin(self.categories_url, path)
            if full_url in seen:
                continue
            seen.add(full_url)

            if thumb.startswith("//"):
                thumb = "https:" + thumb
            elif thumb.startswith("/"):
                thumb = urllib.parse.urljoin(self.categories_url, thumb)

            self.add_dir(html.unescape(title.strip()), full_url, 2, thumb or self.icons.get("categories", self.icon))

        self.end_directory("videos")

    def play_video(self, url):
        content, final_url = self._fetch_video_page(url)
        if not content:
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return

        sources = self._extract_sources(content)
        if not sources:
            content, final_url = self._resolve_playback_page(url, content, final_url)
            sources = self._extract_sources(content)

        if not sources:
            self.logger.error("[BravoPorn] No get_file sources found")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return

        def score(source_url):
            source_url = source_url.lower()
            if "_4k" in source_url:
                return 5
            if "_hq" in source_url:
                return 4
            if "1080" in source_url:
                return 3
            if "720" in source_url:
                return 2
            if "360" in source_url:
                return 1
            return 0

        best_url = max(sources, key=score)
        proxy_headers = {
            "User-Agent": self.ua,
            "Referer": final_url or url,
            "Accept": "*/*",
            "Accept-Encoding": "identity",
        }

        try:
            controller = ProxyController(
                upstream_url=best_url,
                upstream_headers=proxy_headers,
                use_urllib=True,
            )
            local_url = controller.start()

            list_item = xbmcgui.ListItem(path=local_url)
            list_item.setProperty("IsPlayable", "true")
            list_item.setMimeType("video/mp4")
            list_item.setContentLookup(False)
            xbmcplugin.setResolvedUrl(self.addon_handle, True, list_item)

            player = xbmc.Player()
            monitor = xbmc.Monitor()
            guard = PlaybackGuard(player, monitor, local_url, controller)
            guard.start()
        except Exception as exc:
            self.logger.error(f"[BravoPorn] Playback setup failed: {exc}")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
