# -*- coding: utf-8 -*-
import glob
import html
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


class Pornwhite(BaseWebsite):
    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="pornwhite",
            base_url="https://www.pornwhite.com",
            search_url="https://www.pornwhite.com/search/?q={}",
            addon_handle=addon_handle,
            addon=addon,
        )
        self.session = requests.Session()
        self.ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/126.0.0.0 Safari/537.36"
        )
        self.sort_options = ["Latest", "Popular", "Top Rated"]
        self.sort_paths = {
            "Latest": "/latest-updates/",
            "Popular": "/most-popular/",
            "Top Rated": "/top-rated/",
        }
        self.pornstar_sort_options = [
            ("Alphabet", "/pornstars/?sort_by=title"),
            ("Top Rated", "/pornstars/?sort_by=rating"),
            ("Most Viewed", "/pornstars/?sort_by=model_viewed"),
            ("Most Videos", "/pornstars/?sort_by=total_videos"),
            ("Video Rating", "/pornstars/?sort_by=avg_videos_rating"),
            ("Video Popularity", "/pornstars/?sort_by=avg_videos_popularity"),
        ]

    def _find_system_python(self):
        local_app_data = os.environ.get("LOCALAPPDATA", "")
        pattern = os.path.join(local_app_data, "Programs", "Python", "Python*", "python.exe")
        for candidate in sorted(glob.glob(pattern), reverse=True):
            if os.path.isfile(candidate):
                return candidate
        return "python"

    def _start_external_proxy(self, stream_url, video_url):
        helper_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "lib", "system_stream_proxy.py")
        )
        if not os.path.isfile(helper_path):
            return None, None

        python_exe = self._find_system_python()
        command = [
            python_exe,
            "-u",
            helper_path,
            "--url",
            stream_url,
            "--referer",
            video_url,
            "--origin",
            self.base_url,
            "--user-agent",
            self.ua,
        ]

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

        try:
            local_url = process.stdout.readline().strip()
        except Exception:
            local_url = ""

        if not local_url:
            try:
                error_output = process.stderr.read().strip()
                if error_output:
                    self.logger.error("[Pornwhite] External proxy stderr: %s", error_output)
            except Exception:
                pass
            try:
                process.terminate()
            except Exception:
                pass
            return None, None

        return process, local_url

    def _start_process_guard(self, process):
        class _ProcessGuard(threading.Thread):
            def __init__(self, kodi_player, monitor, proxy_process):
                super(_ProcessGuard, self).__init__(name="PornwhiteProxyGuard", daemon=True)
                self.player = kodi_player
                self.monitor = monitor
                self.proxy_process = proxy_process

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

        _ProcessGuard(xbmc.Player(), xbmc.Monitor(), process).start()

    def _normalize_thumb_url(self, thumb_url):
        if not thumb_url:
            return self.icon
        thumb_url = thumb_url.strip()
        if thumb_url.startswith("//"):
            thumb_url = "https:" + thumb_url
        elif thumb_url.startswith("/"):
            thumb_url = urllib.parse.urljoin(self.base_url, thumb_url)

        # Pornwhite's 342x192 "?ver=3" images are often WebP bytes mislabeled as JPEG.
        # The 235x132 variant is a real JPEG and renders correctly in Kodi.
        thumb_url = re.sub(r"/342x192/\d+\.jpg(?:\?[^\"']*)?$", lambda m: m.group(0).split("/342x192/")[0] + "/235x132/" + m.group(0).split("/342x192/")[1].split("?")[0], thumb_url)
        thumb_url = thumb_url.replace("?ver=3", "")
        return thumb_url

    def make_request(self, url, referer=None):
        try:
            headers = {
                "User-Agent": self.ua,
                "Referer": referer or (self.base_url + "/"),
            }
            response = self.session.get(url, headers=headers, timeout=20)
            if response.status_code == 200:
                return response.text
            self.logger.error("[Pornwhite] HTTP %s for %s", response.status_code, url)
        except Exception as exc:
            self.logger.error("[Pornwhite] Request error: %s", exc)
        return None

    def _get_sort_key(self):
        try:
            idx = int(self.addon.getSetting("pornwhite_sort_by") or "0")
        except Exception:
            idx = 0
        if not 0 <= idx < len(self.sort_options):
            idx = 0
        return self.sort_options[idx]

    def get_start_url_and_label(self):
        sort_key = self._get_sort_key()
        return urllib.parse.urljoin(self.base_url, self.sort_paths.get(sort_key, "/latest-updates/")), (
            f"Pornwhite [COLOR yellow]{sort_key}[/COLOR]"
        )

    def _get_context_menu(self):
        return [
            (
                "Sort by...",
                f"RunPlugin({sys.argv[0]}?mode=7&action=select_sort_order&website={self.name})",
            )
        ]

    def _get_pornstar_context_menu(self, current_url):
        return [
            (
                "Sort Pornstars by...",
                f"RunPlugin({sys.argv[0]}?mode=7&action=select_pornstar_sort&website={self.name}&original_url={urllib.parse.quote_plus(current_url)})",
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

        self.addon.setSetting("pornwhite_sort_by", str(idx))
        new_url, _ = self.get_start_url_and_label()
        xbmc.executebuiltin(
            f"Container.Update({sys.argv[0]}?mode=2&website={self.name}&url={urllib.parse.quote_plus(new_url)})"
        )

    def select_pornstar_sort(self, original_url=None):
        labels = [label for label, _ in self.pornstar_sort_options]
        current_url = original_url or urllib.parse.urljoin(self.base_url, "/pornstars/")
        idx = xbmcgui.Dialog().select("Sort Pornstars by...", labels)
        if idx == -1:
            return

        target_url = urllib.parse.urljoin(self.base_url, self.pornstar_sort_options[idx][1])
        xbmc.executebuiltin(
            f"Container.Update({sys.argv[0]}?mode=9&website={self.name}&url={urllib.parse.quote_plus(target_url)})"
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
        self.add_dir(
            "Pornstars",
            urllib.parse.urljoin(self.base_url, "/pornstars/"),
            9,
            self.icons.get("pornstars", self.icon),
            context_menu=self._get_pornstar_context_menu(urllib.parse.urljoin(self.base_url, "/pornstars/")),
        )
        self._render_listing(url, context_menu=context_menu)

    def _render_listing(self, url, context_menu=None):
        html_content = self.make_request(url)
        if not html_content:
            return self.end_directory("videos")

        seen = set()
        block_pattern = re.compile(r'<div class="thumb"[^>]*>(.*?)</div>\s*</div>', re.IGNORECASE | re.DOTALL)
        for block in block_pattern.findall(html_content):
            url_match = re.search(r'<a href="(https://www\.pornwhite\.com/videos/\d+/[^"]+/)"', block, re.IGNORECASE)
            thumb_match = re.search(r'data-poster="([^"]+)"', block, re.IGNORECASE)
            if not thumb_match:
                thumb_match = re.search(r'data-original="([^"]+)"', block, re.IGNORECASE)
            if not thumb_match:
                thumb_match = re.search(r'<meta itemprop="thumbnailUrl" content="([^"]+)"', block, re.IGNORECASE)
            title_match = re.search(r'<span class="title"><a href="https://www\.pornwhite\.com/videos/\d+/[^"]+/">([^<]+)</a></span>', block, re.IGNORECASE)
            if not title_match:
                title_match = re.search(r'alt="([^"]+)"', block, re.IGNORECASE)
            duration_match = re.search(r'<span class="length">([^<]+)</span>', block, re.IGNORECASE)
            if not url_match or not thumb_match or not title_match:
                continue

            video_url = url_match.group(1)
            if video_url in seen:
                continue
            seen.add(video_url)

            title = html.unescape(title_match.group(1).strip())
            thumb = self._normalize_thumb_url(thumb_match.group(1)) if thumb_match else self.icon
            duration = duration_match.group(1).strip() if duration_match else ""
            info = {"title": title, "plot": title}
            duration_seconds = self.convert_duration(duration)
            if duration_seconds:
                info["duration"] = duration_seconds

            self.add_link(title, video_url, 4, thumb, self.fanart, context_menu=context_menu, info_labels=info)

        next_match = re.search(r'<link href="([^"]+)" rel="next">', html_content, re.IGNORECASE)
        if next_match:
            next_url = urllib.parse.urljoin(self.base_url, html.unescape(next_match.group(1)))
            if next_url != url:
                self.add_dir("Next Page", next_url, 2, self.icons.get("default", self.icon), context_menu=context_menu)

        self.end_directory("videos")

    def process_categories(self, url):
        if not url or url.rstrip("/") == self.base_url + "/categories":
            url = urllib.parse.urljoin(self.base_url, "/categories/alphabetical/")

        html_content = self.make_request(url)
        if not html_content:
            return self.end_directory("videos")

        utility_paths = {
            "/categories/alphabetical/",
            "/categories/videos/",
            "/categories/videos-rating/",
            "/categories/videos-popularity/",
        }
        seen = set()
        pattern = re.compile(
            r'<a href="(https://www\.pornwhite\.com/categories/[^"]+/)"[^>]*>.*?(?:<img[^>]+src="([^"]+)"[^>]+alt="([^"]+)")?.*?(?:<span class="title">([^<]+)</span>)?',
            re.IGNORECASE | re.DOTALL,
        )
        for cat_url, thumb, img_alt, title_text in pattern.findall(html_content):
            parsed_path = urllib.parse.urlparse(cat_url).path
            if parsed_path in utility_paths:
                continue
            if cat_url in seen:
                continue
            seen.add(cat_url)
            label = html.unescape((title_text or img_alt or parsed_path.rstrip("/").split("/")[-1].replace("-", " ")).strip()).title()
            icon = self._normalize_thumb_url(thumb) if thumb else self.icons.get("categories", self.icon)
            self.add_dir(label, cat_url, 2, icon)

        self.end_directory("videos")

    def process_pornstars(self, url):
        if not url or url == "BOOTSTRAP":
            url = urllib.parse.urljoin(self.base_url, "/pornstars/")

        html_content = self.make_request(url)
        if not html_content:
            return self.end_directory("videos")

        context_menu = self._get_pornstar_context_menu(url)
        seen = set()
        alpha_links = re.findall(r'https://www\.pornwhite\.com/pornstars/([a-z0-9])/+', html_content, re.IGNORECASE)
        if urllib.parse.urlparse(url).path.rstrip("/") == "/pornstars":
            for letter in sorted(set(alpha_links)):
                alpha_url = urllib.parse.urljoin(self.base_url, f"/pornstars/{letter}/")
                self.add_dir(
                    f"[COLOR gold]{letter.upper()}[/COLOR]",
                    alpha_url,
                    9,
                    self.icons.get("pornstars", self.icon),
                    context_menu=context_menu,
                )

        thumb_pattern = re.compile(
            r'<div class="thumb">\s*<a href="(https://www\.pornwhite\.com/pornstars/[^"]+/)">\s*'
            r'<span class="img"[^>]*data-poster="([^"]+)"[^>]*>\s*'
            r'<img src="([^"]+)" alt="([^"]+)">.*?'
            r'<span class="thumb-info">\s*<b>([^<]+)</b>',
            re.IGNORECASE | re.DOTALL,
        )
        for star_url, poster_url, img_src, img_alt, title_text in thumb_pattern.findall(html_content):
            slug = urllib.parse.urlparse(star_url).path.rstrip("/").split("/")[-1]
            if len(slug) == 1 and slug.isalnum():
                continue
            if star_url in seen:
                continue
            seen.add(star_url)
            label = html.unescape((title_text or img_alt).strip())
            icon = self._normalize_thumb_url(img_src or poster_url)
            self.add_dir(label, star_url, 2, icon, context_menu=context_menu)

        pattern = re.compile(
            r'<a href="(https://www\.pornwhite\.com/pornstars/[^"]+/)" title="([^"]+)">.*?(?:<img[^>]+src="([^"]+)"[^>]+alt="([^"]+)")?.*?(?:<span class="title">([^<]+)</span>)?',
            re.IGNORECASE | re.DOTALL,
        )
        for star_url, title_attr, thumb, img_alt, title_text in pattern.findall(html_content):
            slug = urllib.parse.urlparse(star_url).path.rstrip("/").split("/")[-1]
            if len(slug) == 1 and slug.isalnum():
                continue
            if star_url in seen:
                continue
            seen.add(star_url)
            label = html.unescape((title_text or title_attr or img_alt).strip())
            icon = self._normalize_thumb_url(thumb) if thumb else self.icons.get("pornstars", self.icon)
            self.add_dir(label, star_url, 2, icon, context_menu=context_menu)

        next_match = re.search(r'<link href="([^"]+)" rel="next">', html_content, re.IGNORECASE)
        if next_match:
            next_url = urllib.parse.urljoin(self.base_url, html.unescape(next_match.group(1)))
            if next_url != url:
                self.add_dir("Next Page", next_url, 9, self.icons.get("default", self.icon), context_menu=context_menu)

        self.end_directory("videos")

    def search(self, query):
        if not query:
            return
        search_url = self.search_url.format(urllib.parse.quote_plus(query))
        self.process_content(search_url)

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
        html_content = self.make_request(url)
        if not html_content:
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return

        source_map = {}
        for key in ("video_url", "video_alt_url"):
            match = re.search(r"%s:\s*'([^']+\.mp4[^']*)'" % key, html_content, re.IGNORECASE)
            if match:
                source_map[key] = html.unescape(match.group(1).strip())

        best_url = None
        best_quality = -1
        for key, src in source_map.items():
            quality = 0
            quality_match = re.search(r'_(\d{3,4})p\.mp4', src, re.IGNORECASE)
            if quality_match:
                quality = int(quality_match.group(1))
            elif key == "video_url":
                quality = 1000
            else:
                quality = 360
            if quality >= best_quality:
                best_quality = quality
                best_url = src

        if not best_url:
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return

        stream_headers = {
            "User-Agent": self.ua,
            "Referer": url,
            "Origin": self.base_url,
            "Accept": "*/*",
            "Accept-Encoding": "identity",
            "Accept-Language": "en-US,en;q=0.9",
            "Connection": "keep-alive",
        }

        try:
            # Pre-resolve Pornwhite's signed CDN redirect so Kodi seeks against the
            # final mjedge MP4 directly instead of re-walking the get_file redirect.
            redirect_response = self.session.get(
                best_url,
                headers=stream_headers,
                timeout=15,
                allow_redirects=False,
            )
            final_url = redirect_response.headers.get("Location") or best_url
            playback_path = self._build_header_url(final_url, stream_headers)

            if os.name == "nt":
                proxy_process, local_url = self._start_external_proxy(final_url, url)
                if proxy_process and local_url:
                    playback_path = local_url
                    self._start_process_guard(proxy_process)

            list_item = xbmcgui.ListItem(path=playback_path)
            list_item.setProperty("IsPlayable", "true")
            list_item.setMimeType("video/mp4")
            list_item.setContentLookup(False)
            xbmcplugin.setResolvedUrl(self.addon_handle, True, list_item)
        except Exception as exc:
            self.logger.error("[Pornwhite] Playback resolution failed: %s", exc)
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
