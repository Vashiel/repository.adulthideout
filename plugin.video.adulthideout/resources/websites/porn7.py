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
from resources.lib.resilient_http import fetch_text


class Porn7(BaseWebsite):
    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="porn7",
            base_url="https://www.porn7.xxx",
            search_url="https://www.porn7.xxx/look?s={}",
            addon_handle=addon_handle,
            addon=addon
        )

        try:
            import xbmcaddon

            addon_path = xbmcaddon.Addon().getAddonInfo("path")
            vendor_path = os.path.join(addon_path, "resources", "lib", "vendor")
            if vendor_path not in sys.path:
                sys.path.insert(0, vendor_path)
        except Exception:
            pass

        self._scraper = None

        try:
            import cloudscraper

            self._scraper = cloudscraper.create_scraper(
                browser={"browser": "chrome", "platform": "windows", "mobile": False}
            )
        except Exception:
            self._scraper = None

        self.sort_options = ["Popular", "New"]
        self.sort_paths = {
            "Popular": "/videos",
            "New": "/videos?s=n",
        }

    def make_request(self, url, referer=None):
        self.logger.info(f"[Porn7] GET {url}")
        headers = {
            "Referer": referer or (self.base_url + "/"),
            "User-Agent": "Mozilla/5.0",
        }
        return fetch_text(
            url=url,
            headers=headers,
            scraper=self._scraper,
            logger=self.logger,
            timeout=20,
            use_windows_curl_fallback=True,
        )

    def _get_sort_index(self):
        try:
            idx = int(self.addon.getSetting("porn7_sort_by"))
        except (ValueError, TypeError):
            idx = 1
        if not 0 <= idx < len(self.sort_options):
            idx = 1
        return idx

    def _get_start_url(self):
        sort_key = self.sort_options[self._get_sort_index()]
        return urllib.parse.urljoin(self.base_url, self.sort_paths.get(sort_key, "/videos"))

    def select_sort(self, original_url=None):
        current_idx = self._get_sort_index()
        dialog = xbmcgui.Dialog()
        idx = dialog.select("Sort by...", self.sort_options, preselect=current_idx)
        if idx == -1:
            return
        self.addon.setSetting("porn7_sort_by", str(idx))
        update_command = (
            f"Container.Update({sys.argv[0]}?mode=2&website={self.name}"
            f"&url={urllib.parse.quote_plus('BOOTSTRAP')},replace)"
        )
        xbmc.sleep(250)
        xbmc.executebuiltin(update_command)

    def process_content(self, url):
        if url == "BOOTSTRAP":
            url = self._get_start_url()

        context_menu = [
            (
                "Sort by...",
                f"RunPlugin({sys.argv[0]}?mode=7&action=select_sort&website={self.name})",
            )
        ]

        self.add_dir("Search", "", 5, self.icons.get("search", self.icon), context_menu=context_menu)
        self.add_dir(
            "Categories",
            urllib.parse.urljoin(self.base_url, "/categories"),
            8,
            self.icons.get("categories", self.icon),
            context_menu=context_menu,
        )

        self._render_listing(url, context_menu)

    def _render_listing(self, url, context_menu=None):
        html_content = self.make_request(url)
        if not html_content:
            return self.end_directory("videos")

        seen = set()
        for block in html_content.split('<div class="b-item">')[1:]:
            link_match = re.search(
                r'<a[^>]+class="blk"[^>]+href="(https://www\.porn7\.xxx/v/[^"]+)"[^>]+title="([^"]+)"',
                block,
                re.IGNORECASE,
            )
            thumb_match = re.search(
                r'<img[^>]+(?:data-src|src)="([^"]+)"',
                block,
                re.IGNORECASE,
            )
            duration_match = re.search(
                r'<span class="item-time">([^<]+)</span>',
                block,
                re.IGNORECASE,
            )

            if not link_match:
                continue

            video_url = link_match.group(1)
            title = link_match.group(2)
            thumb = thumb_match.group(1) if thumb_match else ""
            duration = duration_match.group(1) if duration_match else ""

            if video_url in seen:
                continue
            seen.add(video_url)

            title = html.unescape(title.strip())
            thumb = thumb.strip()
            if thumb.startswith("//"):
                thumb = "https:" + thumb
            elif thumb.startswith("/"):
                thumb = urllib.parse.urljoin(self.base_url, thumb)

            info = {"title": title, "plot": title}
            duration_seconds = self.convert_duration(duration.strip())
            if duration_seconds:
                info["duration"] = duration_seconds

            self.add_link(
                title,
                video_url,
                4,
                thumb,
                self.fanart,
                info_labels=info,
                context_menu=context_menu,
            )

        next_url = None
        next_match = re.search(r'<link rel="next" href="([^"]+)"', html_content, re.IGNORECASE)
        if next_match:
            next_url = urllib.parse.urljoin(self.base_url, html.unescape(next_match.group(1)))
        else:
            pager_match = re.search(
                r"<li\s+class=['\"]next['\"][^>]*>\s*<a[^>]+href=['\"]([^'\"]+)['\"]",
                html_content,
                re.IGNORECASE,
            )
            if pager_match:
                next_url = urllib.parse.urljoin(self.base_url, html.unescape(pager_match.group(1)))

        if next_url:
            self.add_dir(
                "Next Page",
                next_url,
                2,
                self.icons.get("default", self.icon),
                context_menu=context_menu,
            )

        self.end_directory("videos")

    def process_categories(self, url):
        html_content = self.make_request(url)
        if not html_content:
            return self.end_directory("videos")

        seen = set()
        for block in html_content.split("<li>")[1:]:
            match = re.search(
                r'<a href="(https://www\.porn7\.xxx/categories/\d+/[^"]+)" title="([^"]+)">.*?</a><u>([^<]+)</u>',
                block,
                re.IGNORECASE | re.DOTALL,
            )
            if not match:
                continue

            cat_url, title, count = match.groups()
            if cat_url in seen:
                continue
            seen.add(cat_url)
            label = html.unescape(title.strip())
            count = count.strip()
            display = f"{label} ({count})" if count else label
            self.add_dir(display, cat_url, 2, self.icons.get("categories", self.icon))

        self.end_directory("videos")

    def play_video(self, url):
        html_content = self.make_request(url)
        if not html_content:
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return

        embed_match = re.search(r'"embedUrl":\s*"([^"]+)"', html_content, re.IGNORECASE)
        if not embed_match:
            embed_match = re.search(r'https://www\.porn7\.xxx/embed/\d+/?', html_content, re.IGNORECASE)

        embed_url = None
        if embed_match:
            embed_url = embed_match.group(1) if embed_match.lastindex else embed_match.group(0)
            embed_url = html.unescape(embed_url)

        if not embed_url:
            page_id_match = re.search(r'/v/(?:old-archive/)?(\d+)/', url)
            if page_id_match:
                embed_url = f"{self.base_url}/embed/{page_id_match.group(1)}/"

        if not embed_url:
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return

        embed_html = self.make_request(embed_url, referer=url)
        if not embed_html:
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return

        source_match = re.search(r'<source[^>]+src="([^"]+)"', embed_html, re.IGNORECASE)
        if not source_match:
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return

        best_url = html.unescape(source_match.group(1).strip())
        if best_url.startswith("//"):
            best_url = "https:" + best_url

        proxy_headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept": "*/*",
            "Accept-Encoding": "identity",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": embed_url,
            "Origin": self.base_url,
            "Sec-Fetch-Site": "cross-site",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Dest": "video",
            "Connection": "keep-alive",
        }

        try:
            controller = ProxyController(
                upstream_url=best_url,
                upstream_headers=proxy_headers,
                cookies=None,
                use_urllib=True,
            )
            local_url = controller.start()

            list_item = xbmcgui.ListItem(path=local_url)
            list_item.setProperty("IsPlayable", "true")
            list_item.setMimeType("video/mp4")
            list_item.setContentLookup(False)
            xbmcplugin.setResolvedUrl(self.addon_handle, True, list_item)

            PlaybackGuard(xbmc.Player(), xbmc.Monitor(), local_url, controller).start()
        except Exception as exc:
            self.logger.error(f"[Porn7] Proxy playback failed: {exc}")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
