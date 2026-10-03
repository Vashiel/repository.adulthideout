#!/usr/bin/env python
# -*- coding: utf-8 -*-

import html
import http.server
import os
import re
import threading
import time
import urllib.parse
import urllib.request

import requests
import xbmc
import xbmcgui
import xbmcplugin

from resources.lib.base_website import BaseWebsite
from resources.lib.thumb_proxy import build_thumb_url

from resources.lib.cyrillic_utils import CYRILLIC_TO_LATIN, RUSSIAN_WORDS_MAP, translate_cyrillic


class _X24ProxyHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-Type", "video/mp4")
        self.send_header("Content-Length", str(self.server.total_size))
        self.send_header("Accept-Ranges", "bytes")
        self.end_headers()

    def do_GET(self):
        rng = self.headers.get("Range")
        total = self.server.total_size
        start = 0
        end = total - 1
        if rng:
            m = re.match(r"bytes=(\d+)-(\d*)", rng)
            if m:
                start = int(m.group(1))
                if m.group(2):
                    end = int(m.group(2))

        req_len = end - start + 1
        self.send_response(206 if rng else 200)
        self.send_header("Content-Type", "video/mp4")
        self.send_header("Accept-Ranges", "bytes")
        if rng:
            self.send_header("Content-Range", f"bytes {start}-{end}/{total}")
        self.send_header("Content-Length", str(req_len))
        self.end_headers()

        curr = start
        while curr <= end and not getattr(self.server, '_shutting_down', False):
            chunk_end = min(curr + 4 * 1024 * 1024 - 1, end)
            req = urllib.request.Request(self.server.upstream_url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/133.0",
                "Referer": "https://playporn.click/",
                "Range": f"bytes={curr}-{chunk_end}"
            })
            try:
                with urllib.request.urlopen(req, timeout=12) as resp:
                    while curr <= end and not getattr(self.server, '_shutting_down', False):
                        buf = resp.read(64 * 1024)
                        if not buf:
                            break
                        self.wfile.write(buf)
                        curr += len(buf)
            except Exception:
                break


class X24ProxyController:
    def __init__(self, upstream_url):
        self.upstream_url = upstream_url
        self.total_size = 0
        try:
            req = urllib.request.Request(upstream_url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/133.0",
                "Referer": "https://playporn.click/",
                "Range": "bytes=0-1"
            })
            with urllib.request.urlopen(req, timeout=10) as resp:
                cr = resp.headers.get("Content-Range")
                if cr and "/" in cr:
                    self.total_size = int(cr.split("/")[-1].strip())
        except Exception:
            pass

        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _X24ProxyHandler)
        self.httpd.upstream_url = self.upstream_url
        self.httpd.total_size = self.total_size
        self.httpd._shutting_down = False
        self.port = self.httpd.server_port
        self.local_url = f"http://127.0.0.1:{self.port}/stream"
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    def start(self):
        self.thread.start()
        return self.local_url

    def stop(self):
        try:
            self.httpd._shutting_down = True
            self.httpd.shutdown()
            self.httpd.server_close()
        except Exception:
            pass


class X24Guard(threading.Thread):
    def __init__(self, kodi_player, monitor, target_url, controller):
        super().__init__(name="X24Guard", daemon=True)
        self.player = kodi_player
        self.monitor = monitor
        self.target = target_url
        self.ctrl = controller

    def run(self):
        start_ts = time.time()
        started = False
        while not self.monitor.abortRequested():
            time.sleep(1)
            elapsed = time.time() - start_ts
            if not started:
                if self.player.isPlayingVideo():
                    started = True
                elif elapsed > 25:
                    break
            else:
                if not self.player.isPlayingVideo():
                    break
        self.ctrl.stop()


class X24Video(BaseWebsite):
    label = "X24Video"
    sort_options = ["Newest", "All Movies"]

    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="x24video",
            base_url="https://x24video.xyz",
            search_url="https://x24video.xyz/search/{}/",
            addon_handle=addon_handle,
            addon=addon,
        )
        self.icon = os.path.join(self.addon.getAddonInfo("path"), "resources", "logos", "x24video.png")
        self.icons["default"] = self.icon
        self.session = requests.Session()
        self.ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/133.0.0.0 Safari/537.36"
        )

    def _headers(self, referer=None):
        return {
            "User-Agent": self.ua,
            "Referer": referer or self.base_url,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

    def _get(self, url, referer=None):
        try:
            r = self.session.get(url, headers=self._headers(referer), timeout=15)
            if r.status_code == 200:
                return r.text
        except Exception as exc:
            self.logger.warning("%s fetch error for %s: %s", self.name, url, exc)
        return ""

    def get_start_url_and_label(self):
        try:
            idx = int(self.addon.getSetting(f"{self.name}_sort_by") or "0")
        except Exception:
            idx = 0
        if idx == 1:
            return f"{self.base_url}/filmy/", f"{self.label} [COLOR yellow]All Movies[/COLOR]"
        return f"{self.base_url}/filmy/new/", f"{self.label} [COLOR yellow]Newest[/COLOR]"

    def search(self, query):
        if query:
            encoded = urllib.parse.quote_plus(query.strip())
            self.process_content(f"{self.base_url}/search/{encoded}/")

    def get_page_url(self, url, page):
        if page <= 1:
            return url
        parsed = urllib.parse.urlparse(url)
        path = parsed.path.rstrip("/")
        if re.search(r"/\d+$", path):
            path = re.sub(r"/\d+$", f"/{page}", path)
        else:
            path = f"{path}/{page}/"
        return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, path, parsed.params, parsed.query, parsed.fragment))

    def _extract_videos(self, html_content):
        videos = []
        seen = set()

        cards = re.findall(
            r'<div\b[^>]*class=["\'][^"\']*\bvideo-thumb\b[^"\']*["\'][^>]*>([\s\S]*?)(?:<div\b[^>]*class=["\'][^"\']*\bvideo-thumb\b|\Z)',
            html_content or "",
            re.I,
        )
        if not cards:
            cards = re.findall(
                r'<div\b[^>]*class=["\'][^"\']*\b(?:thumbs__item|vthumb)\b[^"\']*["\'][^>]*>([\s\S]*?)(?:<div\b[^>]*class=["\'][^"\']*\b(?:thumbs__item|vthumb)\b|\Z)',
                html_content or "",
                re.I,
            )

        for card in cards:
            link_m = re.search(r'<a\b[^>]*href=["\']([^"\']+\.html)["\']', card, re.I)
            if not link_m:
                continue
            href = link_m.group(1).strip()
            video_url = urllib.parse.urljoin(self.base_url, href)
            if video_url in seen:
                continue
            seen.add(video_url)

            # Title
            raw_title = ""
            title_m = re.search(r'<h[1-4]\b[^>]*>([\s\S]*?)</h[1-4]>', card, re.I)
            if title_m:
                raw_title = html.unescape(re.sub(r'<[^>]+>', '', title_m.group(1))).strip()
            if not raw_title:
                alt_m = re.search(r'<img\b[^>]*alt=["\']([^"\']+)["\']', card, re.I)
                if alt_m:
                    raw_title = html.unescape(alt_m.group(1)).strip()

            if not raw_title:
                continue

            # Clean and translate to English / Latin alphabet
            title = translate_cyrillic(raw_title)

            # Thumbnail: match first non-greedy src attribute
            thumb = ""
            img_m = re.search(r'<img\b[^>]*?\ssrc=["\']([^"\']+)["\']', card, re.I)
            if img_m:
                raw_thumb = urllib.parse.urljoin(self.base_url, img_m.group(1).strip())
                if "no-image" not in raw_thumb:
                    thumb = build_thumb_url(raw_thumb, referer=self.base_url)

            dur_m = re.search(r'icon-clock[^>]*></i>\s*(\d{1,2}:\d{2}(?::\d{2})?)', card, re.I)
            duration = dur_m.group(1).strip() if dur_m else ""
            seconds = self.convert_duration(duration)

            label = f"{title} [COLOR lime]({duration})[/COLOR]" if duration else title

            year_m = re.search(r'\b(19\d\d|20\d\d)\b', title)
            year = year_m.group(1) if year_m else ""

            info = {"title": title, "plot": title}
            if seconds:
                info["duration"] = seconds
            if year:
                try:
                    info["year"] = int(year)
                except Exception:
                    pass

            videos.append({
                "label": label,
                "url": video_url,
                "thumb": thumb or self.icon,
                "info": info,
            })
        return videos

    def _extract_next_page(self, html_content, current_url, page):
        next_page = page + 1
        pattern = rf'class=["\'][^"\']*\bpagination__link\b[^"\']*["\'][^>]*href=["\']([^"\']+)["\'][^>]*>(?:{next_page}|&gt;|>)</a>'
        m = re.search(pattern, html_content or "", re.I)
        if m:
            return urllib.parse.urljoin(self.base_url, m.group(1))
        if rf'/{next_page}/' in (html_content or ""):
            return self.get_page_url(current_url, next_page)
        return None

    def process_content(self, url, page=1):
        if not url or url == "BOOTSTRAP":
            url, _ = self.get_start_url_and_label()

        if url.endswith("/filmy/") or url.endswith("/filmy/new/"):
            self.add_dir("Search", "", 5, self.icons.get("search", self.icon))

        target_url = self.get_page_url(url, page)
        html_content = self._get(target_url)
        if not html_content:
            self.notify_error(f"Could not load {self.label} listing")
            self.end_directory("videos")
            return

        videos = self._extract_videos(html_content)
        if not videos:
            self.notify_error(f"No {self.label} videos found")
            return self.end_directory("videos")

        for item in videos:
            self.add_link(
                item["label"],
                item["url"],
                4,
                item["thumb"],
                self.fanart,
                info_labels=item["info"],
            )

        next_url = self._extract_next_page(html_content, target_url, page)
        if next_url:
            self.add_dir("Next Page", url, 2, self.icons.get("default", self.icon), page=page + 1)

        self.end_directory("videos")

    def play_video(self, url):
        html_content = self._get(url, referer=self.base_url)
        if not html_content:
            self.notify_error("Could not load video page")
            return

        stream_url = None
        # 1. Direct video tag
        v_m = re.search(r'<video\b[^>]*src=["\']([^"\']+\.mp4[^"\']*)["\']', html_content, re.I)
        if v_m:
            stream_url = v_m.group(1)

        # 2. Source tag
        if not stream_url:
            s_m = re.search(r'<source\b[^>]*src=["\']([^"\']+\.mp4[^"\']*)["\']', html_content, re.I)
            if s_m:
                stream_url = s_m.group(1)

        # 3. Iframe embed
        if not stream_url:
            ifr_m = re.search(r'<iframe\b[^>]*src=["\']([^"\']+)["\']', html_content, re.I)
            if ifr_m:
                ifr_url = urllib.parse.urljoin(url, ifr_m.group(1))
                ifr_html = self._get(ifr_url, referer=url)
                v2_m = re.search(r'<(?:video|source)\b[^>]*src=["\']([^"\']+\.mp4[^"\']*)["\']', ifr_html, re.I)
                if v2_m:
                    stream_url = v2_m.group(1)

        if stream_url:
            stream_url = urllib.parse.urljoin(url, stream_url)

            # Follow 302 redirect directly in Python to storage server
            try:
                resp = self.session.get(
                    stream_url,
                    headers=self._headers(referer="https://playporn.click/"),
                    allow_redirects=False,
                    timeout=(5, 10),
                )
                if resp.status_code in (301, 302, 303, 307) and resp.headers.get("Location"):
                    stream_url = resp.headers["Location"]
            except Exception:
                pass

            try:
                ctrl = X24ProxyController(stream_url)
                local_url = ctrl.start()

                guard = X24Guard(xbmc.Player(), xbmc.Monitor(), local_url, ctrl)
                guard.start()

                li = xbmcgui.ListItem(path=local_url)
                li.setProperty("IsPlayable", "true")
                li.setMimeType("video/mp4")
                li.setContentLookup(False)

                xbmcplugin.setResolvedUrl(self.addon_handle, True, li)
                return
            except Exception as exc:
                self.logger.warning("%s proxy playback failed: %s", self.name, exc)

        self.notify_error("Video stream not found")
        xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
