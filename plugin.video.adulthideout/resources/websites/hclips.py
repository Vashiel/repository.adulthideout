# -*- coding: utf-8 -*-
import base64
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


class Hclips(BaseWebsite):
    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="hclips",
            base_url="https://hclips.com",
            search_url="https://hclips.com/search/1/?s={}",
            addon_handle=addon_handle,
            addon=addon,
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
        self.sort_options = ["Latest", "Popular", "Top Rated", "Most Commented"]
        self.sort_paths = {
            "Latest": "latest-updates",
            "Popular": "most-popular",
            "Top Rated": "top-rated",
            "Most Commented": "most-commented",
        }
        self._cyrillic_map = {
            0x0410: "A",
            0x0412: "B",
            0x0415: "E",
            0x041C: "M",
            0x0421: "C",
            0x041D: "H",
            0x041A: "K",
            0x0420: "P",
            0x0422: "T",
            0x041E: "O",
            0x0425: "X",
        }

    def get_start_url_and_label(self):
        try:
            current_idx = int(self.addon.getSetting("hclips_sort_by") or "0")
        except Exception:
            current_idx = 0

        if not 0 <= current_idx < len(self.sort_options):
            current_idx = 0

        sort_name = self.sort_options[current_idx]
        return self._build_listing_url(sort_key=self.sort_paths[sort_name]), f"HClips [COLOR yellow]{sort_name}[/COLOR]"

    def _build_listing_url(self, sort_key="latest-updates", page=1, category=None, search=None):
        params = {"sort": sort_key, "page": str(page)}
        if category:
            params["category"] = category
        if search:
            params["search"] = search
        return "hclips://listing?" + urllib.parse.urlencode(params)

    def _parse_listing_url(self, url):
        parsed = urllib.parse.urlparse(url or "")
        query = urllib.parse.parse_qs(parsed.query)
        return {
            "sort": query.get("sort", ["latest-updates"])[0] or "latest-updates",
            "page": max(1, int(query.get("page", ["1"])[0] or "1")),
            "category": query.get("category", [""])[0].strip(),
            "search": query.get("search", [""])[0].strip(),
        }

    def _get_json(self, url, referer=None):
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Referer": referer or (self.base_url + "/"),
            "X-Requested-With": "XMLHttpRequest",
        }
        self.logger.info(f"[HClips] GET {url}")
        response = self._scraper.get(url, timeout=20, headers=headers)
        response.raise_for_status()
        return response.json()

    def _fetch_listing(self, sort_key, page, category="", search=""):
        if search:
            api_url = (
                f"{self.base_url}/api/videos2.php?params=86400/str/relevance/60/"
                f"search.0.{page}.all...&s={urllib.parse.quote_plus(search)}"
            )
            referer = f"{self.base_url}/search/{page}/?s={urllib.parse.quote_plus(search)}"
        elif category:
            api_url = (
                f"{self.base_url}/api/json/videos2/86400/str/{sort_key}/60/"
                f"categories.{category}.{page}.all...json"
            )
            referer = f"{self.base_url}/categories/{category}/"
        else:
            api_url = f"{self.base_url}/api/json/videos2/86400/str/{sort_key}/60/.0.{page}.all...json"
            referer = f"{self.base_url}/videos/{sort_key}/{page}/"
        return self._get_json(api_url, referer=referer)

    def process_content(self, url):
        if url == "BOOTSTRAP":
            url, _ = self.get_start_url_and_label()

        listing = self._parse_listing_url(url)
        context_menu = [
            ("Sort by...", f"RunPlugin({sys.argv[0]}?mode=7&action=select_sort&website={self.name})")
        ]

        self.add_dir("Search", "", 5, self.icons.get("search", self.icon), context_menu=context_menu)
        self.add_dir(
            "Categories",
            f"{self.base_url}/categories/",
            8,
            self.icons.get("categories", self.icon),
            context_menu=context_menu,
        )

        try:
            data = self._fetch_listing(
                sort_key=listing["sort"],
                page=listing["page"],
                category=listing["category"],
                search=listing["search"],
            )
        except Exception as exc:
            self.logger.error(f"[HClips] Listing fetch failed: {exc}")
            return self.end_directory("videos")

        videos = data.get("videos") or []
        for video in videos:
            video_id = str(video.get("video_id") or "").strip()
            video_dir = str(video.get("dir") or "").strip()
            if not (video_id and video_dir):
                continue

            title = html.unescape((video.get("title") or "").strip())
            thumb = (video.get("scr") or "").strip()
            info = {"title": title, "plot": title}
            duration_seconds = self.convert_duration(str(video.get("duration") or "").strip())
            if duration_seconds:
                info["duration"] = duration_seconds

            video_url = f"{self.base_url}/videos/{video_id}/{video_dir}/"
            self.add_link(
                title,
                video_url,
                4,
                thumb or self.icon,
                self.fanart,
                context_menu=context_menu,
                info_labels=info,
            )

        current_page = listing["page"]
        total_pages = int(data.get("pages") or 0)
        if total_pages and current_page < total_pages:
            next_url = self._build_listing_url(
                sort_key=listing["sort"],
                page=current_page + 1,
                category=listing["category"] or None,
                search=listing["search"] or None,
            )
            self.add_dir("Next Page", next_url, 2, self.icons.get("default", self.icon), context_menu=context_menu)

        self.end_directory("videos")

    def process_categories(self, url):
        try:
            data = self._get_json(f"{self.base_url}/api/json/categories/14400/str.all.en.json")
        except Exception as exc:
            self.logger.error(f"[HClips] Categories fetch failed: {exc}")
            return self.end_directory("videos")

        for category in data.get("categories") or []:
            category_dir = str(category.get("dir") or "").strip()
            title = html.unescape((category.get("title") or "").strip())
            count = str(category.get("total_videos") or "").strip()
            if not (category_dir and title):
                continue
            label = f"{title} ({count})" if count else title
            cat_url = self._build_listing_url(sort_key="latest-updates", page=1, category=category_dir)
            self.add_dir(label, cat_url, 2, self.icons.get("categories", self.icon))

        self.end_directory("videos")

    def search(self, query):
        if not query:
            return
        self.process_content(self._build_listing_url(sort_key="relevance", page=1, search=query))

    def _decode_video_url(self, encoded_url):
        normalized = "".join(self._cyrillic_map.get(ord(ch), ch) for ch in encoded_url or "")
        normalized = normalized.replace(",", "+").replace("~", "=")
        if len(normalized) % 4:
            normalized += "=" * ((4 - len(normalized) % 4) % 4)
        decoded = base64.b64decode(normalized).decode("utf-8", "replace")
        decoded = decoded.replace("/>", "/?")
        if ">" in decoded:
            decoded = decoded.replace(">", "?", 1)
        return urllib.parse.urljoin(self.base_url, decoded)

    def play_video(self, url):
        match = re.search(r"/videos/(\d+)/", url)
        if not match:
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return

        video_id = match.group(1)
        try:
            sources = self._get_json(f"{self.base_url}/api/videofile.php?video_id={video_id}", referer=url)
        except Exception as exc:
            self.logger.error(f"[HClips] Videofile fetch failed: {exc}")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return

        if not sources:
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return

        best_source = None
        best_quality = -1
        for source in sources:
            encoded_url = source.get("video_url")
            fmt = str(source.get("format") or "")
            if not encoded_url:
                continue
            quality = 0
            if "_hq" in fmt:
                quality = 720
            elif "_sq" in fmt:
                quality = 480
            elif "_lq" in fmt:
                quality = 360
            elif source.get("is_default"):
                quality = 999
            if quality >= best_quality:
                best_quality = quality
                best_source = encoded_url

        if not best_source:
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return

        stream_url = self._decode_video_url(best_source)
        proxy_headers = {
            "User-Agent": "Mozilla/5.0",
            "Referer": url,
            "Accept": "*/*",
            "Accept-Encoding": "identity",
            "Accept-Language": "en-US,en;q=0.9",
            "Connection": "keep-alive",
        }

        try:
            controller = ProxyController(
                upstream_url=stream_url,
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
            self.logger.error(f"[HClips] Proxy playback failed: {exc}")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
