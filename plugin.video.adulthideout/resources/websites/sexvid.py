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


class SexVid(BaseWebsite):
    def __init__(self, addon_handle, addon=None):
        super().__init__("sexvid", "https://www.sexvid.xxx/", "https://www.sexvid.xxx/s/{}/", addon_handle, addon)
        self.label = "SexVid"
        self.icon = os.path.join(self.addon.getAddonInfo("path"), "resources", "logos", "sexvid.png")
        self.icons["default"] = self.icon
        self.session = requests.Session()
        self.ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        self.sort_options = ["Latest", "Top Rated", "Longest", "Most Commented", "Most Favourited"]
        self.sort_paths = {
            "Latest": "/",
            "Top Rated": "/p/rating/",
            "Longest": "/p/duration/",
            "Most Commented": "/p/most-commented/",
            "Most Favourited": "/p/most-favourited/",
        }

    def _headers(self, referer=None, accept="text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"):
        return {
            "User-Agent": self.ua,
            "Accept": accept,
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": referer or self.base_url,
        }

    def _get(self, url, referer=None):
        try:
            response = self.session.get(url, headers=self._headers(referer), timeout=25, allow_redirects=True)
            if response.status_code == 200:
                return response.text
            self.logger.warning("SexVid HTTP %s for %s", response.status_code, url)
        except Exception as exc:
            self.logger.warning("SexVid request failed for %s: %s", url, exc)
            self.session = requests.Session()
        return fetch_text(url, headers=self._headers(referer), logger=self.logger, timeout=25, use_windows_curl_fallback=True) or ""

    def _absolute(self, value):
        value = html.unescape(value or "").strip()
        if value.startswith("//"):
            value = "https:" + value
        return urllib.parse.urljoin(self.base_url, value)

    def _clean(self, value):
        return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", value or ""))).strip()

    def _get_sort_key(self):
        try:
            index = int(self.addon.getSetting("sexvid_sort_by") or "0")
        except Exception:
            index = 0
        return self.sort_options[index] if 0 <= index < len(self.sort_options) else self.sort_options[0]

    def get_start_url_and_label(self):
        key = self._get_sort_key()
        return self._absolute(self.sort_paths[key]), "{} [COLOR yellow]{}[/COLOR]".format(self.label, key)

    def _context_menu(self):
        return [("Sort by...", "RunPlugin({}?mode=7&action=select_sort&website={})".format(sys.argv[0], self.name))]

    def _is_top_listing(self, url):
        path = urllib.parse.urlparse(url or "").path.rstrip("/")
        return path in ("", "") or path == "" or path.startswith("/p/") or path == ""

    def get_page_url(self, base_url, page_num):
        if page_num <= 1:
            return base_url
        parsed = urllib.parse.urlparse(base_url)
        path = parsed.path.rstrip("/")
        if re.search(r"/\d+$", path):
            path = re.sub(r"/\d+$", "/{}".format(page_num), path)
        else:
            path = "{}/{}".format(path, page_num)
        path += "/"
        return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, path, parsed.params, parsed.query, parsed.fragment))

    def _items(self, content):
        items, seen = [], set()
        for match in re.finditer(r'<a\b[^>]*href="((?:https://(?:[a-z0-9-]+\.)?sexvid\.xxx|https://(?:www\.)?sexvid1\.com)?/[a-z0-9-]+\.html)"[^>]*>', content or "", re.IGNORECASE):
            video_url = self._absolute(match.group(1))
            if video_url in seen:
                continue
            seen.add(video_url)
            anchor_end = content.find("</a>", match.end())
            if anchor_end < 0 or anchor_end - match.start() > 5000:
                anchor_end = match.start() + 3000
            block = content[match.start():anchor_end + 4]

            title = ""
            t_match = re.search(r'<a\b[^>]+title="([^"]+)"', block, re.IGNORECASE)
            if not t_match:
                t_match = re.search(r'<img\b[^>]+alt="([^"]+)"', block, re.IGNORECASE)
            if t_match:
                title = self._clean(t_match.group(1))
            if not title:
                continue

            # The <picture> serves webp first (Kodi cannot decode it); the <img>
            # fallback inside it is a real JPEG, so take the <img src>.
            thumb = ""
            img_match = re.search(r'<img\b[^>]+src="([^"]+\.(?:jpg|jpeg|png)[^"]*)"', block, re.IGNORECASE)
            if img_match:
                thumb = self._absolute(img_match.group(1))

            dur_match = re.search(r'class="(?:duration|time)"[^>]*>([\s\S]*?)</', block, re.IGNORECASE)
            duration = ""
            if dur_match:
                time_match = re.search(r"\d{1,3}:\d{2}(?::\d{2})?", dur_match.group(1))
                duration = time_match.group(0) if time_match else ""

            info = {"title": title, "plot": title, "mediatype": "video"}
            seconds = self.convert_duration(duration)
            if seconds:
                info["duration"] = seconds
            label = "{} [COLOR lime]({})[/COLOR]".format(title, duration) if duration else title
            items.append((label, video_url, thumb or self.icon, info))
        return items

    def process_content(self, url, page=1):
        if not url or url == "BOOTSTRAP":
            url, _ = self.get_start_url_and_label()

        menu = self._context_menu()
        path = urllib.parse.urlparse(url).path.rstrip("/")
        if page == 1 and (path == "" or path.startswith("/p")):
            self.add_dir("Search", "", 5, self.icons.get("search", self.icon), context_menu=menu)
            self.add_dir("Categories", self.base_url + "c/", 8, self.icons.get("categories", self.icon), context_menu=menu)

        content = self._get(self.get_page_url(url, page))
        if not content:
            self.notify_error("Could not load SexVid")
            return self.end_directory("videos")

        items = self._items(content)
        if not items:
            self.notify_error("No SexVid videos found")
            return self.end_directory("videos")

        for label, item_url, thumb, info in items:
            self.add_link(label, item_url, 4, thumb, self.fanart, context_menu=menu, info_labels=info)

        next_path = urllib.parse.urlparse(self.get_page_url(url, page + 1)).path
        if (re.search(r'href="[^"]*{}"'.format(re.escape(next_path)), content) or
                re.search(r'data-from="from{}"'.format(page + 1), content, re.IGNORECASE)):
            self.add_dir("Next Page", url, 2, self.icons.get("default", self.icon), context_menu=menu, page=page + 1)

        self.end_directory("videos")

    def process_categories(self, url):
        content = self._get(url or (self.base_url + "c/"))
        if not content:
            self.notify_error("Could not load SexVid categories")
            return self.end_directory("videos")

        self.add_dir("Search", "", 5, self.icons.get("search", self.icon))
        seen = set()
        for match in re.finditer(r'href="((?:https://(?:[a-z0-9-]+\.)?sexvid\.xxx|https://(?:www\.)?sexvid1\.com)?/c/[a-z0-9-]+/)"', content, re.IGNORECASE):
            cat_url = self._absolute(match.group(1))
            slug = cat_url.rstrip("/").rsplit("/", 1)[-1]
            if cat_url in seen or slug == "c":
                continue
            seen.add(cat_url)
            block = content[match.start():match.start() + 300]
            t_match = re.search(r'>([^<]{2,40})</a>', block)
            title = self._clean(t_match.group(1)) if t_match else slug.replace("-", " ").title()
            self.add_dir(title, cat_url, 2, self.icons.get("categories", self.icon), self.fanart)
        self.end_directory("videos")

    def search(self, query):
        if query:
            self.process_content(self.search_url.format(urllib.parse.quote_plus(query.strip())))

    def resolve_recording_stream(self, url):
        content = self._get(url, referer=self.base_url)
        if not content:
            return None
        license_match = re.search(r"license_code:\s*'([^']+)'", content)
        license_code = license_match.group(1) if license_match else ""
        stream_url = ""
        for key in ("video_url", "video_alt_url"):
            match = re.search(r"{}:\s*'([^']+)'".format(key), content)
            if not match:
                continue
            value = html.unescape(match.group(1)).replace("\\/", "/").strip()
            if value.startswith("function/0/"):
                if license_code:
                    try:
                        value = kvs_decode_url(value, license_code)
                    except Exception as exc:
                        self.logger.warning("SexVid KVS decode failed: %s", exc)
                        value = value[len("function/0/"):]
                else:
                    value = value[len("function/0/"):]
            if value.startswith("http") and ".mp4" in value.lower():
                stream_url = value
                break
        if not stream_url:
            return None
        headers = self._headers(url, accept="*/*")
        cookies = self.session.cookies.get_dict() if self.session else {}
        if cookies:
            headers["Cookie"] = "; ".join("{}={}".format(k, v) for k, v in cookies.items())
        return {"url": stream_url, "headers": headers, "extension": "mp4"}

    def play_video(self, url):
        resolved = self.resolve_recording_stream(url)
        if not resolved:
            self.notify_error("Could not resolve SexVid stream")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return
        try:
            controller = ProxyController(
                resolved["url"],
                upstream_headers=resolved["headers"],
                cookies=self.session.cookies.get_dict() if self.session else None,
                use_urllib=True,
                probe_size=True,
            )
            play_url = controller.start()
            PlaybackGuard(xbmc.Player(), xbmc.Monitor(), play_url, controller).start()
            item = xbmcgui.ListItem(path=play_url)
            item.setProperty("IsPlayable", "true")
            item.setMimeType("video/mp4")
            item.setContentLookup(False)
            xbmcplugin.setResolvedUrl(self.addon_handle, True, item)
        except Exception as exc:
            self.logger.error("SexVid playback failed: %s", exc)
            self.notify_error("SexVid playback failed")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
