# -*- coding: utf-8 -*-
import base64
import html
import json
import os
import re
import sys
import urllib.parse

import xbmcgui
import xbmcplugin
from Cryptodome.Cipher import AES
from Cryptodome.Hash import SHA512
from Cryptodome.Protocol.KDF import PBKDF2
from Cryptodome.Util.Padding import unpad

from resources.lib.base_website import BaseWebsite


class Thepornbang(BaseWebsite):
    OK_API_PREFIX = (
        "https://api.ok.ru/fb.do?application_key=CBAFJIICABABABABA&"
        "fields=video.url_tiny%2Cvideo.url_low%2Cvideo.url_high%2Cvideo.url_medium%2C"
        "video.url_quadhd%2Cvideo.url_mobile%2Cvideo.url_ultrahd%2Cvideo.url_fullhd%2C&"
        "method=video.get&format=json&session_key="
    )
    OK_QUALITY_KEYS = [
        "url_ultrahd",
        "url_quadhd",
        "url_fullhd",
        "url_high",
        "url_medium",
        "url_low",
        "url_tiny",
        "url_mobile",
    ]

    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="thepornbang",
            base_url="https://www.thepornbang.com",
            search_url="https://www.thepornbang.com/search/{}/",
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
        self.sort_options = ["Latest", "Best"]
        self.sort_paths = {
            "Latest": "/videos_13/",
            "Best": "/top-rated_13/",
        }

    def make_request(self, url):
        try:
            self.logger.info(f"[ThePornBang] GET {url}")
            response = self._scraper.get(
                url,
                timeout=20,
                headers={"Referer": self.base_url + "/", "User-Agent": "Mozilla/5.0"},
            )
            if response.status_code == 200:
                return response.text
            self.logger.error(f"[ThePornBang] HTTP {response.status_code} for {url}")
        except Exception as exc:
            self.logger.error(f"[ThePornBang] Request error: {exc}")
        return None

    def get_start_url_and_label(self):
        try:
            current_idx = int(self.addon.getSetting("thepornbang_sort_by") or "0")
        except Exception:
            current_idx = 0

        if not 0 <= current_idx < len(self.sort_options):
            current_idx = 0

        sort_name = self.sort_options[current_idx]
        sort_path = self.sort_paths.get(sort_name, "/videos_13/")
        return urllib.parse.urljoin(self.base_url, sort_path), f"ThePornBang [COLOR yellow]{sort_name}[/COLOR]"

    def process_content(self, url):
        start_url, _ = self.get_start_url_and_label()
        parsed = urllib.parse.urlparse(url or "")
        path = parsed.path.rstrip("/")
        if url == "BOOTSTRAP" or path == "" or path == "/":
            url = start_url

        context_menu = [
            ("Sort by...", f"RunPlugin({sys.argv[0]}?mode=7&action=select_sort&website={self.name})")
        ]

        self.add_dir("Search", "", 5, self.icons.get("search", self.icon), context_menu=context_menu)
        self.add_dir(
            "Categories",
            urllib.parse.urljoin(self.base_url, "/categories_14/"),
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
        block_pattern = re.compile(
            r'<div class="row item">(.*?)</a>\s*</div>',
            re.IGNORECASE | re.DOTALL,
        )

        for block in block_pattern.findall(html_content):
            link_match = re.search(
                r'<a[^>]+class="[^"]*\bthumb\b[^"]*"[^>]+href="(https://www\.thepornbang\.com/video/[^"]+/)"[^>]+title="([^"]+)"',
                block,
                re.IGNORECASE | re.DOTALL,
            )
            thumb_match = re.search(
                r'<img[^>]+class="[^"]*\bthumb-img\b[^"]*"[^>]+data-original="([^"]+)"',
                block,
                re.IGNORECASE | re.DOTALL,
            )
            if not thumb_match:
                thumb_match = re.search(
                    r'<img[^>]+class="[^"]*\bthumb-img\b[^"]*"[^>]+src="([^"]+)"',
                    block,
                    re.IGNORECASE | re.DOTALL,
                )
            duration_match = re.search(
                r'<span class="duration">.*?<span class="value">\s*(\d{1,2}:\d{2})\s*</span>',
                block,
                re.IGNORECASE | re.DOTALL,
            )

            if not link_match:
                continue

            video_url, title_attr = link_match.groups()
            if video_url in seen:
                continue
            seen.add(video_url)

            title = html.unescape(title_attr.strip())
            thumb = thumb_match.group(1).strip() if thumb_match else ""
            if thumb.startswith("/"):
                thumb = urllib.parse.urljoin(self.base_url, thumb)

            info = {"title": title, "plot": title}
            duration_seconds = self.convert_duration(duration_match.group(1).strip() if duration_match else "")
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
        next_match = re.search(
            r'<li class="next">\s*<a[^>]+href="([^"]+)"',
            html_content,
            re.IGNORECASE,
        )
        if next_match:
            next_url = urllib.parse.urljoin(self.base_url, html.unescape(next_match.group(1)))
        else:
            next_match = re.search(
                r'<a[^>]+aria-label="Page right"[^>]+href="([^"]+)"',
                html_content,
                re.IGNORECASE,
            )
            if next_match:
                next_url = urllib.parse.urljoin(self.base_url, html.unescape(next_match.group(1)))

        if next_url:
            self.add_dir("Next Page", next_url, 2, self.icons.get("default", self.icon), context_menu=context_menu)

        self.end_directory("videos")

    def process_categories(self, url):
        html_content = self.make_request(url)
        if not html_content:
            return self.end_directory("videos")

        pattern = re.compile(
            r'<a href="(https://www\.thepornbang\.com/category/[^"]+/)"[^>]+title="([^"]+)"[^>]*>.*?'
            r'<img[^>]+src="([^"]+)"[^>]*>.*?'
            r'<span class="name"[^>]*>([^<]+)</span>',
            re.IGNORECASE | re.DOTALL,
        )

        seen = set()
        for cat_url, title_attr, thumb, title_text in pattern.findall(html_content):
            if cat_url in seen:
                continue
            seen.add(cat_url)

            label = html.unescape((title_text or title_attr).strip())
            thumb = thumb.strip()
            if thumb.startswith("/"):
                thumb = urllib.parse.urljoin(self.base_url, thumb)

            self.add_dir(label, cat_url, 2, thumb or self.icons.get("categories", self.icon))

        self.end_directory("videos")

    def search(self, query):
        if not query:
            return
        search_url = self.search_url.format(urllib.parse.quote_plus(query))
        self.process_content(search_url)

    def _decrypt_ok_session_key(self, encrypted_blob, password):
        payload = json.loads(base64.b64decode(encrypted_blob).decode("utf-8"))
        salt = bytes.fromhex(payload["salt"])
        iv = bytes.fromhex(payload["iv"])
        ciphertext = base64.b64decode(payload["ciphertext"])
        iterations = int(payload.get("iterations", 999))
        key = PBKDF2(password.encode("utf-8"), salt, dkLen=32, count=iterations, hmac_hash_module=SHA512)
        plain = AES.new(key, AES.MODE_CBC, iv).decrypt(ciphertext)
        return unpad(plain, AES.block_size).decode("utf-8")

    def _extract_ok_stream(self, html_content):
        generate_match = re.search(
            r"generate_mp4\('([^']+)',\s*'([^']+)',\s*'([^']+)',\s*'([^']+)'\)",
            html_content,
            re.IGNORECASE | re.DOTALL,
        )
        if not generate_match:
            return None

        encrypted_blob, password, vids, _ = generate_match.groups()

        try:
            session_key = self._decrypt_ok_session_key(encrypted_blob, password)
            api_url = f"{self.OK_API_PREFIX}{session_key}&vids={vids}"
            response = self._scraper.get(
                api_url,
                timeout=20,
                headers={"Referer": self.base_url + "/", "User-Agent": "Mozilla/5.0"},
            )
            if response.status_code != 200:
                self.logger.error(f"[ThePornBang] OK API HTTP {response.status_code}")
                return None

            data = response.json()
            videos = data.get("videos") or []
            for quality_key in self.OK_QUALITY_KEYS:
                for video in reversed(videos):
                    stream_url = video.get(quality_key)
                    if stream_url:
                        self.logger.info(f"[ThePornBang] OK stream selected: {quality_key}")
                        return stream_url
        except Exception as exc:
            self.logger.error(f"[ThePornBang] OK stream extraction failed: {exc}")

        return None

    def play_video(self, url):
        html_content = self.make_request(url)
        if not html_content:
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return

        ok_stream = self._extract_ok_stream(html_content)
        if ok_stream:
            list_item = xbmcgui.ListItem(path=f"{ok_stream}|User-Agent=Mozilla/5.0")
            list_item.setProperty("IsPlayable", "true")
            list_item.setMimeType("video/mp4")
            list_item.setContentLookup(False)
            xbmcplugin.setResolvedUrl(self.addon_handle, True, list_item)
            return

        sources = re.findall(
            r'(https://www\.thepornbang\.com/get_stream/\d+-\d+\.mp4\?md5=[^"\']+)',
            html_content,
            re.IGNORECASE,
        )

        best_url = None
        best_quality = -1
        for src in sources:
            quality = 0
            match = re.search(r'-(\d+)\.mp4', src, re.IGNORECASE)
            if match:
                quality = int(match.group(1))
            if quality >= best_quality:
                best_quality = quality
                best_url = src

        if not best_url:
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return

        proxy_headers = {
            "User-Agent": "Mozilla/5.0",
            "Referer": url,
            "Origin": self.base_url,
            "Accept": "*/*",
            "Accept-Encoding": "identity",
            "Accept-Language": "en-US,en;q=0.9",
            "Connection": "keep-alive",
        }

        try:
            header_string = "&".join(
                f"{urllib.parse.quote(k)}={urllib.parse.quote(v)}" for k, v in proxy_headers.items()
            )
            playback_url = f"{best_url}|{header_string}"

            list_item = xbmcgui.ListItem(path=playback_url)
            list_item.setProperty("IsPlayable", "true")
            list_item.setMimeType("video/mp4")
            list_item.setContentLookup(False)
            xbmcplugin.setResolvedUrl(self.addon_handle, True, list_item)
        except Exception as exc:
            self.logger.error(f"[ThePornBang] Playback setup failed: {exc}")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
