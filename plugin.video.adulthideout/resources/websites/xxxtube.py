# -*- coding: utf-8 -*-
import html
import re
import sys
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

try:
    from http.server import ThreadingHTTPServer
except ImportError:
    import socketserver

    class ThreadingHTTPServer(socketserver.ThreadingMixIn, HTTPServer):
        daemon_threads = True

import requests
import xbmc
import xbmcgui
import xbmcplugin

from resources.lib.base_website import BaseWebsite
from resources.lib.decoders.kvs_decoder import kvs_decode_url


_ACTIVE_PROXIES = []


class _XXXTubeRangeProxy:
    def __init__(self, session, upstream_url, headers, host="127.0.0.1", port=0):
        self.session = session
        self.upstream_url = upstream_url
        self.headers = dict(headers or {})
        self.host = host
        self.port = port
        self.httpd = None
        self.thread = None
        self.local_url = None

    def start(self):
        controller = self

        class Handler(BaseHTTPRequestHandler):
            server_version = "AHXXXTubeRange/1.0"

            def log_message(self, fmt, *args):
                return

            def do_GET(self):
                controller._handle(self)

            def do_HEAD(self):
                controller._handle(self, head_only=True)

        self.httpd = ThreadingHTTPServer((self.host, self.port), Handler)
        self.port = self.httpd.server_port
        self.local_url = "http://{}:{}/stream?u={}".format(
            self.host,
            self.port,
            urllib.parse.quote(self.upstream_url, safe=""),
        )
        self.thread = threading.Thread(target=self.httpd.serve_forever, name="XXXTubeRangeProxy", daemon=True)
        self.thread.start()
        xbmc.log("[XXXTUBE] Range proxy started: {}".format(self.local_url), xbmc.LOGINFO)
        return self.local_url

    def _handle(self, handler, head_only=False):
        parsed = urllib.parse.urlparse(handler.path)
        upstream_url = urllib.parse.parse_qs(parsed.query).get("u", [self.upstream_url])[0]
        headers = dict(self.headers)
        range_header = handler.headers.get("Range")
        if range_header:
            headers["Range"] = range_header

        response = None
        try:
            response = self.session.get(
                upstream_url,
                headers=headers,
                timeout=30,
                allow_redirects=True,
                stream=True,
            )
            handler.send_response(response.status_code)
            for key in ("Content-Type", "Content-Length", "Content-Range", "Accept-Ranges"):
                value = response.headers.get(key)
                if value:
                    handler.send_header(key, value)
            if not response.headers.get("Accept-Ranges"):
                handler.send_header("Accept-Ranges", "bytes")
            handler.send_header("Cache-Control", "no-store")
            handler.end_headers()

            if head_only:
                return

            for chunk in response.iter_content(chunk_size=65536):
                if chunk:
                    handler.wfile.write(chunk)
        except Exception as exc:
            xbmc.log("[XXXTUBE] Range proxy error: {}".format(exc), xbmc.LOGERROR)
            try:
                if not getattr(handler, "_headers_buffer", None):
                    handler.send_response(502)
                    handler.end_headers()
            except Exception:
                pass
        finally:
            if response is not None:
                response.close()


class XxxTube(BaseWebsite):
    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="xxxtube",
            base_url="https://x-x-x.tube",
            search_url="https://x-x-x.tube/search/{}/",
            addon_handle=addon_handle,
            addon=addon,
        )
        self.session = requests.Session()
        self.ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/128.0.0.0 Safari/537.36"
        )
        self.sort_options = ["Latest", "Top Rated"]
        self.sort_paths = {
            "Latest": "/videos/",
            "Top Rated": "/videos/?by=rating",
        }

    def _headers(self, referer=None):
        return {
            "User-Agent": self.ua,
            "Referer": referer or (self.base_url + "/"),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

    def make_request(self, url, referer=None):
        try:
            response = self.session.get(url, headers=self._headers(referer), timeout=25)
            if response.status_code == 200:
                return response.text
            self.logger.error("[XXXTUBE] HTTP %s for %s", response.status_code, url)
        except Exception as exc:
            self.logger.error("[XXXTUBE] Request error for %s: %s", url, exc)
        return None

    def _clean(self, value):
        value = re.sub(r"<[^>]+>", " ", value or "")
        return re.sub(r"\s+", " ", html.unescape(value)).strip()

    def _absolute(self, value):
        if not value:
            return ""
        return urllib.parse.urljoin(self.base_url + "/", html.unescape(value.strip()))

    def _normalize_thumb(self, value):
        value = self._absolute(value)
        return value if value and not value.startswith("data:image/") else self.icon

    def _get_sort_key(self):
        try:
            idx = int(self.addon.getSetting("xxxtube_sort_by") or "0")
        except Exception:
            idx = 0
        if not 0 <= idx < len(self.sort_options):
            idx = 0
        return self.sort_options[idx]

    def get_start_url_and_label(self):
        sort_key = self._get_sort_key()
        return self._absolute(self.sort_paths.get(sort_key, "/videos/")), "XXXTube [COLOR yellow]{}[/COLOR]".format(sort_key)

    def _context_menu(self, original_url=None):
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
            preselect = self.sort_options.index(self._get_sort_key())
        except ValueError:
            preselect = 0
        idx = xbmcgui.Dialog().select("Sort by...", self.sort_options, preselect=preselect)
        if idx == -1:
            return

        self.addon.setSetting("xxxtube_sort_by", str(idx))
        new_url = self._absolute(self.sort_paths.get(self.sort_options[idx], "/videos/"))
        xbmc.executebuiltin(
            "Container.Update({}?mode=2&website={}&url={})".format(
                sys.argv[0], self.name, urllib.parse.quote_plus(new_url)
            )
        )

    def process_content(self, url, page=1):
        if not url or url == "BOOTSTRAP":
            url, _ = self.get_start_url_and_label()

        context_menu = self._context_menu(url)
        self.add_dir("Search", "", 5, self.icons.get("search", self.icon), context_menu=context_menu)
        self.add_dir(
            "Categories",
            self.base_url + "/categories/",
            8,
            self.icons.get("categories", self.icon),
            context_menu=context_menu,
        )
        self.add_dir(
            "Models",
            self.base_url + "/models/",
            9,
            self.icons.get("pornstars", self.icon),
            context_menu=context_menu,
        )
        self._render_listing(url, context_menu=context_menu)

    def _extract_videos(self, html_content):
        videos = []
        seen = set()
        pattern = re.compile(
            r'<a\s+href="(https://x-x-x\.tube/videos/\d+/[^"]+/)"\s+title="([^"]+)"[^>]*>.*?'
            r'<img[^>]+(?:src|data-src)="([^"]+)"[^>]+alt="([^"]*)".*?'
            r'<div\s+class="duration">\s*([^<]+)\s*</div>',
            re.IGNORECASE | re.DOTALL,
        )
        for video_url, title_attr, thumb, alt_text, duration in pattern.findall(html_content or ""):
            if video_url in seen:
                continue
            seen.add(video_url)
            title = self._clean(title_attr or alt_text)
            if not title:
                continue
            duration_text = self._clean(duration)
            info = {"title": title, "plot": title}
            duration_seconds = self.convert_duration(duration_text)
            if duration_seconds:
                info["duration"] = duration_seconds
            label = "{} [COLOR lime]({})[/COLOR]".format(title, duration_text) if duration_text else title
            videos.append(
                {
                    "title": label,
                    "url": video_url,
                    "thumb": self._normalize_thumb(thumb),
                    "info": info,
                }
            )
        return videos

    def _extract_next_page(self, html_content, current_url):
        pagination = re.search(r'<ul[^>]+class="pagination"[\s\S]*?</ul>', html_content or "", re.IGNORECASE)
        source = pagination.group(0) if pagination else (html_content or "")
        matches = re.findall(r'<li[^>]+class="[^"]*pager(?![^"]*not-active)[^"]*"[\s\S]*?<a\s+href="([^"]+)"', source, re.IGNORECASE)
        if not matches:
            matches = re.findall(r'<a\s+href="([^"]+)"[^>]*>\s*(?:Next|>)\s*</a>', source, re.IGNORECASE)
        for candidate in matches:
            next_url = self._absolute(candidate)
            if next_url and next_url != current_url:
                return next_url
        return None

    def _render_listing(self, url, context_menu=None):
        html_content = self.make_request(url)
        if not html_content:
            return self.end_directory("videos")

        videos = self._extract_videos(html_content)
        if not videos:
            self.notify_error("No XXXTube videos found")
            return self.end_directory("videos")

        for item in videos:
            self.add_link(
                item["title"],
                item["url"],
                4,
                item["thumb"],
                self.fanart,
                context_menu=context_menu,
                info_labels=item["info"],
            )

        next_url = self._extract_next_page(html_content, url)
        if next_url:
            self.add_dir("Next Page", next_url, 2, self.icons.get("default", self.icon), context_menu=context_menu)

        self.end_directory("videos")

    def process_categories(self, url):
        url = url or (self.base_url + "/categories/")
        html_content = self.make_request(url)
        if not html_content:
            return self.end_directory("videos")

        seen = set()
        pattern = re.compile(
            r'<a\s+href="(https://x-x-x\.tube/categories/[^"]+/)"\s+title="([^"]+)"[^>]*>.*?'
            r'<img[^>]+src="([^"]+)"[^>]+alt="([^"]*)"',
            re.IGNORECASE | re.DOTALL,
        )
        for cat_url, title_attr, thumb, alt_text in pattern.findall(html_content):
            if cat_url in seen:
                continue
            seen.add(cat_url)
            title = self._clean(title_attr or alt_text)
            if title:
                self.add_dir(title, cat_url, 2, self._normalize_thumb(thumb), self.fanart, context_menu=self._context_menu(cat_url))

        next_url = self._extract_next_page(html_content, url)
        if next_url:
            self.add_dir("Next Page", next_url, 8, self.icons.get("default", self.icon))

        self.end_directory("videos")

    def process_pornstars(self, url):
        url = url or (self.base_url + "/models/")
        html_content = self.make_request(url)
        if not html_content:
            return self.end_directory("videos")

        seen = set()
        pattern = re.compile(
            r'<a\s+href="(https://x-x-x\.tube/models/[^"]+/)"\s+title="([^"]+)"[^>]*>.*?'
            r'(?:<img[^>]+src="([^"]+)"[^>]+alt="([^"]*)"|<div\s+class="title">\s*([^<]+)\s*</div>)',
            re.IGNORECASE | re.DOTALL,
        )
        for model_url, title_attr, thumb, alt_text, title_text in pattern.findall(html_content):
            if model_url in seen:
                continue
            seen.add(model_url)
            title = self._clean(title_attr or alt_text or title_text)
            if title:
                self.add_dir(title, model_url, 2, self._normalize_thumb(thumb), self.fanart, context_menu=self._context_menu(model_url))

        next_url = self._extract_next_page(html_content, url)
        if next_url:
            self.add_dir("Next Page", next_url, 9, self.icons.get("default", self.icon))

        self.end_directory("videos")

    def search(self, query):
        if query:
            self.process_content(self.search_url.format(urllib.parse.quote_plus(query.strip())))

    def _extract_stream_url(self, html_content):
        license_code = ""
        license_match = re.search(r"license_code\s*:\s*'([^']+)'", html_content or "", re.IGNORECASE)
        if not license_match:
            license_match = re.search(r'license_code\s*:\s*"([^"]+)"', html_content or "", re.IGNORECASE)
        if license_match:
            license_code = html.unescape(license_match.group(1)).strip()

        patterns = [
            r"video_url\s*:\s*'([^']+)'",
            r'video_url\s*:\s*"([^"]+)"',
            r'<meta\s+property="og:video"[^>]+content="([^"]+)"',
            r'<source[^>]+src="([^"]+\.mp4[^"]*)"',
        ]
        for pattern in patterns:
            match = re.search(pattern, html_content or "", re.IGNORECASE)
            if not match:
                continue
            stream_url = html.unescape(match.group(1)).replace("\\/", "/").strip()
            if stream_url.startswith("function/0/") and license_code:
                stream_url = kvs_decode_url(stream_url, license_code)
            elif stream_url.startswith("function/0/"):
                stream_url = stream_url.split("function/0/", 1)[1]
            if stream_url.startswith("//"):
                stream_url = "https:" + stream_url
            elif stream_url.startswith("/"):
                stream_url = urllib.parse.urljoin(self.base_url, stream_url)
            if stream_url.startswith("http"):
                return stream_url
        return None

    def play_video(self, url):
        html_content = self.make_request(url)
        stream_url = self._extract_stream_url(html_content)
        if not stream_url:
            self.notify_error("Could not resolve XXXTube stream")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return

        headers = {
            "User-Agent": self.ua,
            "Referer": url,
            "Accept": "*/*",
            "Connection": "close",
        }
        cookie_header = "; ".join(
            "{}={}".format(cookie.name, cookie.value) for cookie in self.session.cookies
        )
        if cookie_header:
            headers["Cookie"] = cookie_header
        proxy = _XXXTubeRangeProxy(self.session, stream_url, headers)
        play_url = proxy.start()
        _ACTIVE_PROXIES.append(proxy)
        del _ACTIVE_PROXIES[:-4]
        list_item = xbmcgui.ListItem(path=play_url)
        list_item.setProperty("IsPlayable", "true")
        list_item.setMimeType("video/mp4")
        list_item.setContentLookup(False)
        xbmcplugin.setResolvedUrl(self.addon_handle, True, list_item)
