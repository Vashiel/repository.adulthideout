# -*- coding: utf-8 -*-
import html
import glob
import os
import re
import subprocess
import sys
import threading
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

    def _find_system_python(self):
        local_app_data = os.environ.get("LOCALAPPDATA", "")
        pattern = os.path.join(local_app_data, "Programs", "Python", "Python*", "python.exe")
        for candidate in sorted(glob.glob(pattern), reverse=True):
            if os.path.isfile(candidate):
                return candidate
        return "python"

    def _start_external_proxy(self, stream_url, video_url, cookie_dict):
        helper_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "lib", "system_stream_proxy.py"))
        if not os.path.isfile(helper_path):
            return None, None

        python_exe = self._find_system_python()
        cookie_string = "; ".join("{}={}".format(str(k), str(v)) for k, v in (cookie_dict or {}).items())
        command = [
            python_exe,
            "-u",
            helper_path,
            "--referer",
            video_url,
            "--origin",
            self.base_url,
            "--user-agent",
            self.ua,
            "--cookie",
            cookie_string,
            "--prime-url",
            video_url,
            "--page-url",
            video_url,
        ]

        if stream_url:
            command.extend(["--url", stream_url])

        startupinfo = None
        creationflags = 0
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            text=True,
            bufsize=1,
            startupinfo=startupinfo,
            creationflags=creationflags,
        )

        local_url = None
        try:
            local_url = process.stdout.readline().strip()
        except Exception:
            local_url = None

        if not local_url:
            try:
                process.terminate()
            except Exception:
                pass
            return None, None

        return process, local_url

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

    def _start_process_guard(self, process, target_path):
        class _ProcessGuard(threading.Thread):
            def __init__(self, kodi_player, monitor, proxy_process, expected_target):
                super(_ProcessGuard, self).__init__(name="NudezProxyGuard", daemon=True)
                self.player = kodi_player
                self.monitor = monitor
                self.proxy_process = proxy_process
                self.expected_target = expected_target

            def run(self):
                started = False
                while not self.monitor.abortRequested():
                    if self.player.isPlaying():
                        started = True
                    elif started:
                        break
                    if self.proxy_process.poll() is not None:
                        break
                    self.monitor.waitForAbort(1)

                if self.proxy_process.poll() is None:
                    try:
                        self.proxy_process.terminate()
                    except Exception:
                        pass

        _ProcessGuard(xbmc.Player(), xbmc.Monitor(), process, target_path).start()

    def play_video(self, url):
        cookie_dict = self._prime_session(url)

        local_url = None
        if os.name == "nt":
            proxy_process, local_url = self._start_external_proxy("", url, cookie_dict)
            if proxy_process and local_url:
                self._start_process_guard(proxy_process, local_url)

        if not local_url:
            html_content = self.make_request(url)
            if not html_content:
                xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
                return

            match = re.search(r"video_url:\s*'([^']+\.mp4/)'", html_content, re.IGNORECASE)
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
                "Referer": url,
                "Origin": self.base_url,
                "Accept": "*/*",
                "Accept-Language": "en-US,en;q=0.9",
                "Connection": "keep-alive",
            }
            from resources.lib.proxy_utils import PlaybackGuard, ProxyController

            controller = ProxyController(
                stream_url,
                upstream_headers=headers,
                cookies=cookie_dict,
                session=self.session,
                skip_resolve=True,
            )
            local_url = controller.start()
            PlaybackGuard(xbmc.Player(), xbmc.Monitor(), local_url, controller).start()

        list_item = xbmcgui.ListItem(path=local_url)
        list_item.setProperty("IsPlayable", "true")
        list_item.setMimeType("video/mp4")
        list_item.setContentLookup(False)
        xbmcplugin.setResolvedUrl(self.addon_handle, True, list_item)
