# -*- coding: utf-8 -*-
import html
import os
import re
import sys
import urllib.parse

import requests
import xbmc
import xbmcgui
import xbmcplugin

from resources.lib.base_website import BaseWebsite
from resources.lib.decoders.kvs_decoder import kvs_decode_url
from resources.lib.proxy_utils import PlaybackGuard, ProxyController
from resources.lib.resilient_http import fetch_text


class YourLesbians(BaseWebsite):
    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="yourlesbians",
            base_url="https://yourlesbians.com",
            search_url="https://yourlesbians.com/search/{}/",
            addon_handle=addon_handle,
            addon=addon,
        )
        self.session = requests.Session()
        self.ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/128.0.0.0 Safari/537.36"
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

        self.sort_options = ["Newest", "Most Viewed", "Top Rated"]
        self.sort_paths = {
            "Newest": "/",
            "Most Viewed": "/most-popular/",
            "Top Rated": "/top-rated/",
        }

    def make_request(self, url, referer=None):
        headers = {
            "User-Agent": self.ua,
            "Referer": referer or (self.base_url + "/"),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
        return fetch_text(
            url=url,
            headers=headers,
            scraper=self._scraper,
            logger=self.logger,
            timeout=20,
            use_windows_curl_fallback=True,
        )

    def _get_sort_key(self):
        try:
            idx = int(self.addon.getSetting("yourlesbians_sort_by") or "0")
        except Exception:
            idx = 0
        if not 0 <= idx < len(self.sort_options):
            idx = 0
        return self.sort_options[idx]

    def get_start_url_and_label(self):
        sort_key = self._get_sort_key()
        start_url = urllib.parse.urljoin(self.base_url, self.sort_paths.get(sort_key, "/"))
        return start_url, "YourLesbians [COLOR yellow]{}[/COLOR]".format(sort_key)

    def _get_context_menu(self, original_url=None):
        suffix = ""
        if original_url:
            suffix = "&original_url={}".format(urllib.parse.quote_plus(original_url))
        return [
            (
                "Sort by...",
                "RunPlugin({}?mode=7&action=select_sort_order&website={}{} )".format(
                    sys.argv[0], self.name, suffix
                ).replace(" )", ")"),
            )
        ]

    def select_sort_order(self, original_url=None):
        try:
            preselect_idx = self.sort_options.index(self._get_sort_key())
        except ValueError:
            preselect_idx = 0

        idx = xbmcgui.Dialog().select("Sort by...", self.sort_options, preselect=preselect_idx)
        if idx == -1:
            return

        self.addon.setSetting("yourlesbians_sort_by", str(idx))
        new_url, _ = self.get_start_url_and_label()
        xbmc.executebuiltin(
            "Container.Update({}?mode=2&website={}&url={})".format(
                sys.argv[0], self.name, urllib.parse.quote_plus(new_url)
            )
        )

    def process_content(self, url):
        if not url or url == "BOOTSTRAP":
            url, _ = self.get_start_url_and_label()

        context_menu = self._get_context_menu(url)
        self.add_dir("Search", "", 5, self.icons.get("search", self.icon), context_menu=context_menu)
        self.add_dir(
            "Categories",
            urllib.parse.urljoin(self.base_url, "/categories/"),
            8,
            self.icons.get("categories", self.icon),
            context_menu=context_menu,
        )
        self.add_dir(
            "Pornstars",
            urllib.parse.urljoin(self.base_url, "/models/"),
            9,
            self.icons.get("pornstars", self.icon),
            context_menu=context_menu,
        )
        self._render_listing(url, context_menu=context_menu)

    def _normalize_thumb(self, thumb):
        thumb = html.unescape((thumb or "").strip())
        if not thumb or thumb.startswith("data:image/"):
            return self.icon
        if thumb.startswith("//"):
            return "https:" + thumb
        if thumb.startswith("/"):
            return urllib.parse.urljoin(self.base_url, thumb)
        return thumb

    def _duration_label(self, duration):
        duration = " ".join((duration or "").split())
        return duration if duration and duration != "0:00" else ""

    def _extract_videos(self, html_content):
        anchor_pattern = re.compile(
            r'<a\s+href=["\'](?P<url>https://yourlesbians\.com/video/[^"\']+/)["\']'
            r'[^>]*title=["\'](?P<title>[^"\']+)["\'][^>]*>(?P<body>[\s\S]{0,6000}?)</a>',
            re.IGNORECASE,
        )
        seen = set()
        videos = []
        for match in anchor_pattern.finditer(html_content):
            video_url = html.unescape(match.group("url").strip())
            if video_url in seen:
                continue
            body = match.group("body")
            img_match = re.search(
                r'<img[^>]+(?:data-original|data-src|src)=["\']([^"\']+)["\']',
                body,
                re.IGNORECASE,
            )
            duration_match = re.search(
                r'<div\s+class=["\']time["\']\s*>([^<]+)</div>',
                body,
                re.IGNORECASE,
            )
            if not img_match or not duration_match:
                continue
            quality_match = re.search(
                r'<div\s+class=["\']qualtiy["\']\s*>([^<]+)</div>',
                body,
                re.IGNORECASE,
            )
            seen.add(video_url)
            videos.append(
                {
                    "url": video_url,
                    "title": html.unescape(match.group("title").strip()),
                    "thumb": self._normalize_thumb(img_match.group(1)),
                    "duration": self._duration_label(duration_match.group(1)),
                    "quality": html.unescape(quality_match.group(1).strip()) if quality_match else "",
                }
            )
        return videos

    def _build_next_url(self, current_url, next_from):
        parsed = urllib.parse.urlparse(current_url)
        query = urllib.parse.parse_qs(parsed.query)
        query["from"] = [str(next_from)]
        if parsed.path in ("", "/") and "sort_by" not in query:
            query["sort_by"] = ["post_date"]
        return urllib.parse.urlunparse(
            (
                parsed.scheme or "https",
                parsed.netloc or "yourlesbians.com",
                parsed.path or "/",
                "",
                urllib.parse.urlencode(query, doseq=True),
                "",
            )
        )

    def _extract_next_page(self, html_content, current_url):
        match = re.search(
            r'class=["\'][^"\']*\bnext\b[^"\']*["\'][^>]+href=["\']#more["\'][^>]+'
            r'data-parameters=["\'][^"\']*from:(\d+)',
            html_content,
            re.IGNORECASE,
        )
        if match:
            return self._build_next_url(current_url, match.group(1))

        match = re.search(r'<li class=["\']next["\']>\s*<a href=["\']([^"\']+)["\']', html_content, re.IGNORECASE)
        if match:
            candidate = html.unescape(match.group(1).strip())
            if candidate and not candidate.startswith("#"):
                return urllib.parse.urljoin(self.base_url, candidate)
        return None

    def _render_listing(self, url, context_menu=None):
        html_content = self.make_request(url)
        if not html_content:
            return self.end_directory("videos")

        for video in self._extract_videos(html_content):
            title = video["title"]
            label = title
            if video["duration"]:
                label = "{} [COLOR lime]({})[/COLOR]".format(title, video["duration"])
            info = {"title": title, "plot": title}
            duration_seconds = self.convert_duration(video["duration"])
            if duration_seconds:
                info["duration"] = duration_seconds
            self.add_link(
                label,
                video["url"],
                4,
                video["thumb"],
                self.fanart,
                context_menu=context_menu,
                info_labels=info,
            )

        next_url = self._extract_next_page(html_content, url)
        if next_url and next_url != url:
            self.add_dir("Next Page", next_url, 2, self.icons.get("default", self.icon), context_menu=context_menu)

        self.end_directory("videos")

    def _render_card_directory(self, html_content, path_prefix, mode, icon):
        pattern = re.compile(
            r'<a\s+href=["\'](https://yourlesbians\.com/{}/[^"\']+/)["\']'
            r'[^>]*title=["\']([^"\']+)["\'][\s\S]{{0,1800}}?</a>'.format(path_prefix),
            re.IGNORECASE,
        )
        seen = set()
        for item_url, title in pattern.findall(html_content):
            if item_url in seen:
                continue
            seen.add(item_url)
            clean_title = html.unescape(title.strip())
            if clean_title:
                self.add_dir(clean_title, item_url, mode, icon, self.fanart, context_menu=self._get_context_menu())
        self.end_directory("videos")

    def process_categories(self, url):
        html_content = self.make_request(url)
        if not html_content:
            return self.end_directory("videos")
        path = urllib.parse.urlparse(url).path.rstrip("/") + "/"
        if path == "/categories/":
            return self._render_card_directory(html_content, "categories", 8, self.icons.get("categories", self.icon))
        self._render_listing(url, context_menu=self._get_context_menu(url))

    def process_pornstars(self, url):
        html_content = self.make_request(url)
        if not html_content:
            return self.end_directory("videos")
        path = urllib.parse.urlparse(url).path.rstrip("/") + "/"
        if path == "/models/":
            return self._render_card_directory(html_content, "models", 9, self.icons.get("pornstars", self.icon))
        self._render_listing(url, context_menu=self._get_context_menu(url))

    def search(self, query):
        if not query:
            return
        self.process_content(self.search_url.format(urllib.parse.quote(query)))

    def _stream_headers(self, referer):
        return {
            "User-Agent": self.ua,
            "Referer": referer,
            "Origin": self.base_url,
            "Accept": "*/*",
            "Accept-Encoding": "identity",
            "Accept-Language": "en-US,en;q=0.9",
            "Connection": "keep-alive",
        }

    def _build_header_url(self, stream_url, headers):
        header_subset = {
            "User-Agent": headers["User-Agent"],
            "Referer": headers["Referer"],
            "Origin": headers["Origin"],
            "Accept": headers["Accept"],
        }
        return stream_url + "|" + urllib.parse.urlencode(header_subset)

    def _resolve_final_stream_url(self, stream_url, referer):
        if "/get_file/" not in stream_url:
            return stream_url
        try:
            response = self.session.head(
                stream_url,
                headers=self._stream_headers(referer),
                timeout=15,
                allow_redirects=True,
            )
            if response.url and response.url.startswith("http"):
                return response.url
        except Exception as exc:
            self.logger.error("[YourLesbians] Final URL resolve failed for %s: %s", stream_url, exc)
        return stream_url

    def resolve(self, url):
        html_content = self.make_request(url)
        if not html_content:
            return None

        video_match = re.search(r"video_url\s*:\s*'([^']+)'", html_content, re.IGNORECASE)
        license_match = re.search(r"license_code\s*:\s*'([^']+)'", html_content, re.IGNORECASE)
        if not video_match:
            video_match = re.search(r'["\'](https://yourlesbians\.com/get_file/[^"\']+?\.mp4/[^"\']*)["\']', html_content)
        if not video_match:
            return None

        video_url = html.unescape(video_match.group(1).replace("\\/", "/").strip())
        if license_match:
            video_url = kvs_decode_url(video_url, license_match.group(1).strip())
        if not video_url.startswith("http"):
            return None
        return self._resolve_final_stream_url(video_url, url)

    def play_video(self, url):
        video_url = self.resolve(url)
        if not video_url:
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return

        playback_controller = None
        final_url = video_url
        headers = self._stream_headers(url)
        try:
            playback_controller = ProxyController(
                upstream_url=final_url,
                upstream_headers=headers,
                use_urllib=True,
                probe_size=True,
            )
            final_url = playback_controller.start()
            xbmc.log("[YourLesbians] Using internal Range proxy for playback", xbmc.LOGINFO)
        except Exception as exc:
            xbmc.log("[YourLesbians] Proxy failed, falling back direct: {}".format(exc), xbmc.LOGWARNING)
            final_url = self._build_header_url(video_url, headers)

        list_item = xbmcgui.ListItem(path=final_url)
        list_item.setProperty("IsPlayable", "true")
        list_item.setMimeType("video/mp4")
        list_item.setContentLookup(False)
        xbmcplugin.setResolvedUrl(self.addon_handle, True, list_item)
        if playback_controller:
            PlaybackGuard(xbmc.Player(), xbmc.Monitor(), final_url, playback_controller).start()
