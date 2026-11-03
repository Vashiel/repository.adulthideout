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

vendor_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "lib", "vendor")
if vendor_path not in sys.path:
    sys.path.insert(0, vendor_path)

try:
    import cloudscraper
    _HAS_CLOUDSCRAPER = True
except Exception:
    cloudscraper = None
    _HAS_CLOUDSCRAPER = False


class Nudez(BaseWebsite):
    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="nudez",
            base_url="https://nudez.com",
            search_url="https://nudez.com/search/{}/",
            addon_handle=addon_handle,
            addon=addon,
        )
        self.ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/126.0.0.0 Safari/537.36"
        )
        self.session = requests.Session()
        if _HAS_CLOUDSCRAPER:
            try:
                self.session = cloudscraper.create_scraper(browser={"custom": self.ua})
            except Exception:
                self.session = requests.Session()
        self.sort_options = ["Latest", "Top Rated", "Most Viewed"]
        self.sort_paths = {
            "Latest": "/latest-updates/",
            "Top Rated": "/top-rated/",
            "Most Viewed": "/most-popular/",
        }

    def make_request(self, url, referer=None):
        try:
            headers = {
                "User-Agent": self.ua,
                "Referer": referer or (self.base_url + "/"),
            }
            response = self.session.get(url, headers=headers, timeout=20)
            if response.status_code == 200:
                return response.text
            if response.status_code == 500 and "/videos/" in url and "var flashvars" in response.text:
                return response.text
            self.logger.error("[Nudez] HTTP %s for %s", response.status_code, url)
        except Exception as exc:
            self.logger.error("[Nudez] Request error: %s", exc)
        return None

    def _prime_session(self, video_url=None):
        cookie_dict = self.session.cookies.get_dict() or {}
        if cookie_dict.get("PHPSESSID") and cookie_dict.get("kt_ips"):
            return cookie_dict

        targets = [self.base_url + "/", urllib.parse.urljoin(self.base_url, "/latest-updates/")]
        if video_url:
            targets.append(video_url)

        for target in targets:
            try:
                response = self.session.get(
                    target,
                    headers={
                        "User-Agent": self.ua,
                        "Referer": self.base_url + "/",
                    },
                    timeout=20,
                )
                try:
                    self.session.cookies.update(response.cookies.get_dict())
                except Exception:
                    pass
                cookie_dict = self.session.cookies.get_dict() or {}
                if cookie_dict.get("PHPSESSID") and cookie_dict.get("kt_ips"):
                    return cookie_dict
            except Exception as exc:
                self.logger.warning("[Nudez] Session prime failed for %s: %s", target, exc)

        return self.session.cookies.get_dict() or {}

    def _get_sort_key(self):
        try:
            idx = int(self.addon.getSetting("nudez_sort_by") or "0")
        except Exception:
            idx = 0
        if not 0 <= idx < len(self.sort_options):
            idx = 0
        return self.sort_options[idx]

    def get_start_url_and_label(self):
        sort_key = self._get_sort_key()
        return urllib.parse.urljoin(self.base_url, self.sort_paths.get(sort_key, "/latest-updates/")), (
            f"Nudez [COLOR yellow]{sort_key}[/COLOR]"
        )

    def _get_context_menu(self):
        return [
            (
                "Sort by...",
                f"RunPlugin({sys.argv[0]}?mode=7&action=select_sort_order&website={self.name})",
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

        self.addon.setSetting("nudez_sort_by", str(idx))
        new_url, _ = self.get_start_url_and_label()
        xbmc.executebuiltin(
            f"Container.Update({sys.argv[0]}?mode=2&website={self.name}&url={urllib.parse.quote_plus(new_url)})"
        )

    def process_content(self, url):
        if not url or url == "BOOTSTRAP":
            url, _ = self.get_start_url_and_label()

        context_menu = self._get_context_menu()
        self.add_dir("Search", "", 5, self.icons.get("search", self.icon), context_menu=context_menu)
        self.add_dir(
            "Categories",
            urllib.parse.urljoin(self.base_url, "/categories/"),
            8,
            self.icons.get("categories", self.icon),
            context_menu=context_menu,
        )
        self._render_listing(url, context_menu=context_menu)

    def _render_listing(self, url, context_menu=None):
        html_content = self.make_request(url)
        if not html_content:
            return self.end_directory("videos")

        seen = set()
        item_pattern = re.compile(
            r'<div class="item\s*[^"]*">\s*<a href="(https://nudez\.com/videos/\d+/[^"]+/)" title="([^"]+)".*?'
            r'<img class="thumb lazy-load"[^>]+data-original="([^"]+)"[^>]+alt="([^"]+)".*?'
            r'<strong class="title">\s*([^<]+)\s*</strong>.*?'
            r'<div class="duration">([^<]+)</div>',
            re.IGNORECASE | re.DOTALL,
        )

        for video_url, title_attr, thumb, img_alt, title_text, duration in item_pattern.findall(html_content):
            if video_url in seen:
                continue
            seen.add(video_url)

            title = html.unescape((title_text or title_attr or img_alt).strip())
            thumb = thumb.strip() if thumb else self.icon
            if thumb.startswith("//"):
                thumb = "https:" + thumb
            elif thumb.startswith("/"):
                thumb = urllib.parse.urljoin(self.base_url, thumb)

            info = {"title": title, "plot": title}
            duration_seconds = self.convert_duration(duration.strip() if duration else "")
            if duration_seconds:
                info["duration"] = duration_seconds

            self.add_link(title, video_url, 4, thumb, self.fanart, context_menu=context_menu, info_labels=info)

        next_match = re.search(r'<a[^>]+href="([^"]+)"[^>]*>Next</a>', html_content, re.IGNORECASE)
        if next_match:
            next_href = html.unescape(next_match.group(1).strip())
            if next_href and not next_href.startswith("#"):
                next_url = urllib.parse.urljoin(url, next_href)
                self.add_dir("Next Page", next_url, 2, self.icons.get("default", self.icon), context_menu=context_menu)

        self.end_directory("videos")

    def process_categories(self, url):
        html_content = self.make_request(url)
        if not html_content:
            return self.end_directory("videos")

        pattern = re.compile(
            r'<a class="item" href="(https://nudez\.com/categories/[^"]+/)" title="([^"]+)">.*?'
            r'<strong class="title">([^<]+)</strong>.*?'
            r'<div class="videos">([^<]+)</div>',
            re.IGNORECASE | re.DOTALL,
        )
        seen = set()
        for cat_url, title_attr, title_text, count_text in pattern.findall(html_content):
            if cat_url in seen:
                continue
            seen.add(cat_url)
            label = html.unescape((title_text or title_attr).strip())
            count = " ".join(count_text.split())
            display = f"{label} ({count})" if count else label
            self.add_dir(display, cat_url, 2, self.icons.get("categories", self.icon))

        self.end_directory("videos")

    def search(self, query):
        if not query:
            return
        self.process_content(self.search_url.format(urllib.parse.quote(query)))

    def _build_header_url(self, stream_url, headers):
        parts = []
        for key, value in headers.items():
            parts.append(
                "{}={}".format(
                    urllib.parse.quote(str(key), safe=""),
                    urllib.parse.quote(str(value), safe=""),
                )
            )
        return stream_url + "|" + "&".join(parts)

    def play_video(self, url):
        vid_match = re.search(r"/videos/(\d+)/", url) or re.search(r"/embed/(\d+)", url)
        embed_url = f"{self.base_url}/embed/{vid_match.group(1)}" if vid_match else url

        html_content = self.make_request(embed_url, referer=self.base_url + "/")
        if not html_content or "var flashvars" not in html_content:
            html_content = self.make_request(url, referer=self.base_url + "/")

        if not html_content:
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return

        match = re.search(r"video_url:\s*'([^']+\.mp4/[^']*)'", html_content, re.IGNORECASE)
        license_match = re.search(r"license_code:\s*'([^']+)'", html_content, re.IGNORECASE)
        if not match:
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return

        stream_url = html.unescape(match.group(1).strip())
        license_code = license_match.group(1).strip() if license_match else ""
        if stream_url.startswith("function/0/") and license_code:
            stream_url = kvs_decode_url(stream_url, license_code)
        elif stream_url.startswith("function/0/"):
            stream_url = stream_url[len("function/0/") :]
        if stream_url.startswith("/"):
            stream_url = urllib.parse.urljoin(self.base_url, stream_url)

        headers = {
            "User-Agent": self.ua,
            "Referer": embed_url,
            "Origin": self.base_url,
            "Accept": "*/*",
            "Connection": "keep-alive",
        }
        playback_url = self._build_header_url(stream_url, headers)

        list_item = xbmcgui.ListItem(path=playback_url)
        list_item.setProperty("IsPlayable", "true")
        list_item.setMimeType("video/mp4")
        list_item.setContentLookup(False)
        xbmcplugin.setResolvedUrl(self.addon_handle, True, list_item)
