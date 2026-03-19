# -*- coding: utf-8 -*-
import html
import os
import re
import sys
import urllib.parse

import xbmcgui
import xbmcplugin
import xbmc

from resources.lib.base_website import BaseWebsite


class SuperPorn(BaseWebsite):
    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="superporn",
            base_url="https://www.superporn.com",
            search_url="https://www.superporn.com/search?q={}",
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

        import cloudscraper

        self._scraper = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "windows", "mobile": False}
        )
        self.content_options = ["Straight", "Gay"]
        self.content_paths = {
            "Straight": "/",
            "Gay": "/gay",
        }

    def get_current_content_key(self):
        try:
            content_index = int(self.addon.getSetting("superporn_content_type"))
        except (ValueError, TypeError):
            content_index = 0
        if not 0 <= content_index < len(self.content_options):
            content_index = 0
        return self.content_options[content_index]

    def _get_start_url(self):
        content_key = self.get_current_content_key()
        path = self.content_paths.get(content_key, "/")
        return urllib.parse.urljoin(self.base_url, path)

    def select_content_type(self, original_url=None):
        current_key = self.get_current_content_key()
        try:
            preselect_idx = self.content_options.index(current_key)
        except ValueError:
            preselect_idx = 0

        dialog = xbmcgui.Dialog()
        idx = dialog.select("Content Type...", self.content_options, preselect=preselect_idx)
        if idx == -1:
            return

        self.addon.setSetting("superporn_content_type", str(idx))
        new_url = self._get_start_url()
        update_command = (
            f"Container.Update({sys.argv[0]}?mode=2&website={self.name}"
            f"&url={urllib.parse.quote_plus(new_url)})"
        )
        xbmc.sleep(250)
        xbmc.executebuiltin(update_command)

    def make_request(self, url):
        try:
            self.logger.info(f"[SuperPorn] GET {url}")
            response = self._scraper.get(
                url,
                timeout=20,
                headers={"Referer": self.base_url, "User-Agent": "Mozilla/5.0"},
            )
            if response.status_code == 200:
                return response.text
            self.logger.error(f"[SuperPorn] HTTP {response.status_code} for {url}")
        except Exception as exc:
            self.logger.error(f"[SuperPorn] Request error: {exc}")
        return None

    def search(self, query):
        if not query:
            return

        if self.get_current_content_key() == "Gay":
            search_url = f"{self.base_url}/gay/search?q={urllib.parse.quote_plus(query)}"
        else:
            search_url = self.search_url.format(urllib.parse.quote_plus(query))
        self.process_content(search_url)

    def process_content(self, url):
        if url == "BOOTSTRAP":
            url = self._get_start_url()

        self.add_dir("Search", "", 5, self.icons.get("search", self.icon))
        self.add_dir(
            "Categories",
            urllib.parse.urljoin(self.base_url, "/categories"),
            8,
            self.icons.get("categories", self.icon),
        )

        self._render_listing(url)

    def _render_listing(self, url):
        html_content = self.make_request(url)
        if not html_content:
            return self.end_directory("videos")

        context_menu = [
            (
                "Select Content",
                f"RunPlugin({sys.argv[0]}?mode=7&action=select_content_type&website={self.name})",
            )
        ]

        seen = set()
        block_pattern = re.compile(
            r'<div class="thumb-video(?! thumb-categories)(?:[^"]*)".*?<div class="thumb-video__meta">.*?</div>\s*</div>',
            re.IGNORECASE | re.DOTALL,
        )

        for block in block_pattern.findall(html_content):
            video_match = re.search(
                r'<a href="([^"]+)" class="thumb-duracion">',
                block,
                re.IGNORECASE,
            )
            title_match = re.search(
                r'<a class="thumb-video__description" href="[^"]+">\s*([^<]+?)\s*</a>',
                block,
                re.IGNORECASE | re.DOTALL,
            )
            duration_match = re.search(
                r'<span class="duracion">\s*([^<]*)\s*</span>',
                block,
                re.IGNORECASE | re.DOTALL,
            )
            thumb_match = re.search(
                r'data-src="([^"]+)"',
                block,
                re.IGNORECASE,
            )
            if not thumb_match:
                thumb_match = re.search(
                    r'<img[^>]+src="([^"]+)"',
                    block,
                    re.IGNORECASE,
                )

            if not (video_match and title_match):
                continue

            video_url = urllib.parse.urljoin(self.base_url, video_match.group(1))
            if video_url in seen:
                continue
            seen.add(video_url)

            thumb = thumb_match.group(1).strip() if thumb_match else ""
            if thumb.startswith("//"):
                thumb = "https:" + thumb
            title = html.unescape(title_match.group(1).strip())

            info = {"title": title, "plot": title}
            duration = duration_match.group(1).strip() if duration_match else ""
            duration_seconds = self.convert_duration(duration)
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

        next_match = re.search(
            r'<li class="pagination_item pagination_item--next"[^>]*>.*?<a class="btn-pagination"[^>]+href="([^"]+)".*?<span>\s*Next',
            html_content,
            re.IGNORECASE | re.DOTALL,
        )
        if next_match:
            next_url = urllib.parse.urljoin(self.base_url, next_match.group(1))
            self.add_dir("Next Page", next_url, 2, self.icons.get("default", self.icon))

        self.end_directory("videos")

    def process_categories(self, url):
        html_content = self.make_request(url)
        if not html_content:
            return self.end_directory("videos")

        cat_pattern = re.compile(
            r'<div class="thumb-video thumb-categories[^"]*".*?'
            r'<a class="thumb-duracion[^"]*"[^>]*href="([^"]+)">.*?'
            r'data-src="([^"]+)".*?'
            r'<h3 class="category__name">\s*([^<]+?)\s*</h3>',
            re.IGNORECASE | re.DOTALL,
        )

        seen = set()
        for cat_url, thumb, title in cat_pattern.findall(html_content):
            cat_url = urllib.parse.urljoin(self.base_url, cat_url)
            if cat_url in seen:
                continue
            seen.add(cat_url)

            if thumb.startswith("//"):
                thumb = "https:" + thumb
            title = html.unescape(title.strip())
            self.add_dir(title, cat_url, 2, thumb or self.icons.get("categories", self.icon))

        next_match = re.search(
            r'<li class="pagination_item pagination_item--next"[^>]*>.*?<a class="btn-pagination"[^>]+href="([^"]+)".*?<span>\s*Next',
            html_content,
            re.IGNORECASE | re.DOTALL,
        )
        if next_match:
            next_url = urllib.parse.urljoin(self.base_url, next_match.group(1))
            self.add_dir("Next Page", next_url, 8, self.icons.get("default", self.icon))

        self.end_directory("videos")

    def play_video(self, url):
        html_content = self.make_request(url)
        if not html_content:
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return

        sources = re.findall(
            r'<source[^>]+src="([^"]+)"(?:[^>]+label="([^"]*)")?',
            html_content,
            re.IGNORECASE,
        )

        best_url = None
        best_quality = -1
        for src, label in sources:
            quality = 0
            match = re.search(r"(\d{3,4})", label or "")
            if match:
                quality = int(match.group(1))
            if quality >= best_quality:
                best_quality = quality
                best_url = src

        if not best_url:
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return

        if best_url.startswith("//"):
            best_url = "https:" + best_url

        list_item = xbmcgui.ListItem(path=best_url)
        list_item.setProperty("IsPlayable", "true")
        list_item.setMimeType("video/mp4")
        list_item.setContentLookup(False)
        xbmcplugin.setResolvedUrl(self.addon_handle, True, list_item)
