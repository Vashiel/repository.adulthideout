#!/usr/bin/env python
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


_ACTIVE_PROXIES = []


class _XXThotsRangeProxy:
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
            server_version = "AHXXThotsRange/1.0"

            def log_message(self, fmt, *args):
                return

            def do_GET(self):
                controller._handle(self)

            def do_HEAD(self):
                controller._handle(self, head_only=True)

        self.httpd = ThreadingHTTPServer((self.host, self.port), Handler)
        self.port = self.httpd.server_port
        self.local_url = "http://{}:{}/stream".format(self.host, self.port)
        self.thread = threading.Thread(target=self.httpd.serve_forever, name="XXThotsRangeProxy", daemon=True)
        self.thread.start()
        xbmc.log("[XXTHOTS] Range proxy started: {}".format(self.local_url), xbmc.LOGINFO)
        return self.local_url

    def _handle(self, handler, head_only=False):
        headers = dict(self.headers)
        range_header = handler.headers.get("Range")
        if range_header:
            headers["Range"] = range_header

        response = None
        try:
            response = self.session.get(
                self.upstream_url,
                headers=headers,
                timeout=(8, 30),
                allow_redirects=True,
                stream=True,
            )
            handler.send_response(response.status_code)
            for key in ("Content-Type", "Content-Length", "Content-Range", "Accept-Ranges", "ETag", "Last-Modified"):
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
                    try:
                        handler.wfile.write(chunk)
                    except (BrokenPipeError, ConnectionResetError):
                        break
        except Exception as exc:
            xbmc.log("[XXTHOTS] Range proxy error: {}".format(exc), xbmc.LOGERROR)
            try:
                if not getattr(handler, "_headers_buffer", None):
                    handler.send_response(502)
                    handler.end_headers()
            except Exception:
                pass
        finally:
            if response is not None:
                response.close()


class Xxthots(BaseWebsite):
    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="xxthots",
            base_url="https://xxthots.com/",
            search_url="https://xxthots.com/search/{}/",
            addon_handle=addon_handle,
            addon=addon,
        )
        self.label = "XXThots"
        self.session = requests.Session()
        self.ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/126.0.0.0 Safari/537.36"
        )
        self.sort_options = ["Latest", "Top Rated", "Most Viewed"]
        self.sort_paths = {
            "Latest": "/latest-updates/",
            "Top Rated": "/top-rated/",
            "Most Viewed": "/most-popular/",
        }

    def _headers(self, referer=None, accept="text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"):
        return {
            "User-Agent": self.ua,
            "Referer": referer or self.base_url,
            "Accept": accept,
            "Accept-Language": "en-US,en;q=0.9",
        }

    def _get(self, url, referer=None, max_retries=3):
        last_error = None
        for attempt in range(1, max_retries + 1):
            try:
                response = self.session.get(url, headers=self._headers(referer), timeout=25)
                if response.status_code == 200:
                    return response.text
                last_error = "HTTP {}".format(response.status_code)
                self.logger.warning("XXThots HTTP %s for %s", response.status_code, url)
            except Exception as exc:
                last_error = exc
                self.logger.warning("XXThots request error for %s: %s", url, exc)
                self.session = requests.Session()

            if attempt < max_retries:
                xbmc.sleep(650 * attempt)

        self.logger.error("XXThots failed to fetch %s: %s", url, last_error)
        return ""

    def _absolute(self, value):
        if not value:
            return ""
        return urllib.parse.urljoin(self.base_url, html.unescape(value).strip())

    def _clean(self, value):
        value = re.sub(r"<[^>]+>", " ", value or "")
        return re.sub(r"\s+", " ", html.unescape(value)).strip()

    def _get_sort_key(self):
        try:
            idx = int(self.addon.getSetting("xxthots_sort_by") or "0")
        except Exception:
            idx = 0
        if not 0 <= idx < len(self.sort_options):
            idx = 0
        return self.sort_options[idx]

    def get_start_url_and_label(self):
        sort_key = self._get_sort_key()
        return self._absolute(self.sort_paths.get(sort_key, "/latest-updates/")), (
            "{} [COLOR yellow]{}[/COLOR]".format(self.label, sort_key)
        )

    def _context_menu(self, original_url=None):
        suffix = ""
        if original_url:
            suffix = "&original_url={}".format(urllib.parse.quote_plus(original_url))
        return [
            (
                "Sort by...",
                "RunPlugin({}?mode=7&action=select_sort&website={}{} )".format(
                    sys.argv[0], self.name, suffix
                ).replace(" )", ")"),
            )
        ]

    def _is_top_listing(self, url):
        parsed = urllib.parse.urlparse(url or "")
        return parsed.path.strip("/") in ("", "latest-updates")

    def _extract_videos(self, html_content):
        videos = []
        seen = set()
        for block in re.split(r'(?=<div\b[^>]+class=["\'][^"\']*(?:thumb|item)[^"\']*["\'])', html_content or "", flags=re.IGNORECASE):
            if "/video/" not in block:
                continue
            anchor_match = re.search(r"<a\b[^>]*>", block, re.IGNORECASE)
            if not anchor_match:
                continue
            anchor = anchor_match.group(0)
            href_match = re.search(r'\shref=["\']([^"\']+/video/[^"\']+)["\']', anchor, re.IGNORECASE)
            if not href_match:
                continue
            video_url = self._absolute(href_match.group(1))
            if not video_url or video_url in seen:
                continue
            seen.add(video_url)

            title_match = re.search(r'\stitle=["\']([^"\']+)["\']', anchor, re.IGNORECASE)
            img_match = re.search(r"<img\b[^>]*>", block, re.IGNORECASE)
            img_tag = img_match.group(0) if img_match else ""
            if not title_match:
                title_match = re.search(r'\salt=["\']([^"\']+)["\']', img_tag, re.IGNORECASE)
            thumb_match = re.search(r'\sdata-original=["\']([^"\']+)["\']', img_tag, re.IGNORECASE)
            if not thumb_match:
                thumb_match = re.search(r'\sdata-webp=["\']([^"\']+)["\']', img_tag, re.IGNORECASE)
            if not thumb_match:
                thumb_match = re.search(r'\sdata-src=["\']([^"\']+)["\']', img_tag, re.IGNORECASE)
            if not thumb_match:
                thumb_match = re.search(r'\ssrc=["\']([^"\']+)["\']', img_tag, re.IGNORECASE)

            duration_match = re.search(r'<div\b[^>]*class=["\'][^"\']*(?:time|duration)[^"\']*["\'][^>]*>([\s\S]*?)</div>', block, re.IGNORECASE)
            title = self._clean(title_match.group(1) if title_match else "")
            if not title:
                continue
            thumb = self._absolute(thumb_match.group(1)) if thumb_match else self.icon
            if thumb.startswith("data:image/"):
                thumb = self.icon
            duration = self._clean(duration_match.group(1)) if duration_match else ""
            label = "{} [COLOR lime]({})[/COLOR]".format(title, duration) if duration else title
            info = {"title": title, "plot": title}
            seconds = self.convert_duration(duration) if duration else 0
            if seconds:
                info["duration"] = seconds
            videos.append({"label": label, "url": video_url, "thumb": thumb or self.icon, "info": info})
        return videos

    def _extract_next_page(self, html_content, current_url):
        parsed = urllib.parse.urlparse(current_url or self.base_url)
        current = 1
        query_from = urllib.parse.parse_qs(parsed.query).get("from")
        if query_from:
            try:
                current = int(query_from[0])
            except (TypeError, ValueError):
                current = 1
        page_match = re.search(r"/(\d+)/?$", parsed.path)
        if page_match:
            current = int(page_match.group(1))

        ajax_candidates = []
        for ajax_match in re.finditer(
            r'<a\b(?=[^>]*data-action=["\']ajax["\'])(?=[^>]*data-block-id=["\']([^"\']+)["\'])(?=[^>]*data-parameters=["\']([^"\']*from:(\d+)[^"\']*)["\'])',
            html_content or "",
            re.IGNORECASE,
        ):
            try:
                ajax_page = int(ajax_match.group(3))
            except (TypeError, ValueError):
                continue
            if ajax_page <= current:
                continue

            block_id = html.unescape(ajax_match.group(1))
            params_raw = html.unescape(ajax_match.group(2))
            query = {
                "mode": "async",
                "function": "get_block",
                "block_id": block_id,
            }
            for part in params_raw.split(";"):
                if ":" not in part:
                    continue
                key, value = part.split(":", 1)
                query[key.strip()] = value.strip()

            base = urllib.parse.urlunparse(
                (
                    parsed.scheme or "https",
                    parsed.netloc or urllib.parse.urlparse(self.base_url).netloc,
                    parsed.path or "/",
                    "",
                    "",
                    "",
                )
            )
            ajax_candidates.append((ajax_page, "{}?{}".format(base, urllib.parse.urlencode(query))))

        if ajax_candidates:
            return sorted(ajax_candidates, key=lambda item: item[0])[0][1]

        candidates = []
        for href, num in re.findall(r'href=["\']([^"\']*/(\d+)/?)["\']', html_content or "", re.IGNORECASE):
            next_url = self._absolute(href)
            next_path = urllib.parse.urlparse(next_url).path
            if not any(segment in next_path for segment in ("/latest-updates/", "/top-rated/", "/most-popular/", "/categories/", "/search/")):
                continue
            try:
                page_num = int(num)
            except ValueError:
                continue
            if page_num > current:
                candidates.append((page_num, next_url))
        if not candidates:
            return None
        return sorted(candidates, key=lambda item: item[0])[0][1]

    def process_content(self, url, page=1):
        if not url or url == "BOOTSTRAP":
            url, _ = self.get_start_url_and_label()

        context_menu = self._context_menu(url)
        if self._is_top_listing(url):
            self.add_dir("Search", "", 5, self.icons.get("search", self.icon), context_menu=context_menu)
            self.add_dir("Categories", self._absolute("/categories/"), 8, self.icons.get("categories", self.icon), context_menu=context_menu)

        html_content = self._get(url)
        if not html_content:
            self.notify_error("Could not load XXThots listing")
            xbmcplugin.endOfDirectory(self.addon_handle, succeeded=False, updateListing=False, cacheToDisc=False)
            return

        videos = self._extract_videos(html_content)
        if not videos:
            self.notify_error("No XXThots videos found")
            return self.end_directory("videos")

        for item in videos:
            self.add_link(item["label"], item["url"], 4, item["thumb"], self.fanart, context_menu=context_menu, info_labels=item["info"])

        next_url = self._extract_next_page(html_content, url)
        if next_url:
            self.add_dir("Next Page", next_url, 2, self.icons.get("default", self.icon), context_menu=context_menu)

        self.end_directory("videos")

    def process_categories(self, url):
        html_content = self._get(url or self._absolute("/categories/"))
        if not html_content:
            self.notify_error("Could not load XXThots categories")
            xbmcplugin.endOfDirectory(self.addon_handle, succeeded=False, updateListing=False, cacheToDisc=False)
            return

        seen = set()
        for href, label_html in re.findall(
            r'<a\b[^>]*href=["\']([^"\']*/categories/[^"\']+)["\'][^>]*>([\s\S]*?)</a>',
            html_content,
            re.IGNORECASE,
        ):
            category_url = self._absolute(href)
            if not category_url or category_url in seen or urllib.parse.urlparse(category_url).path.rstrip("/") == "/categories":
                continue
            seen.add(category_url)
            title = self._clean(label_html)
            if not title:
                title = urllib.parse.urlparse(category_url).path.rstrip("/").rsplit("/", 1)[-1].replace("-", " ").title()
            self.add_dir(title, category_url, 2, self.icons.get("categories", self.icon), self.fanart)

        self.end_directory("videos")

    def search(self, query):
        if query:
            self.process_content(self.search_url.format(urllib.parse.quote_plus(query.strip())))

    def _extract_streams(self, html_content):
        streams = []
        for key, url in re.findall(r"(video_alt_url|video_url|event_reporting2):\s*'([^']+\.mp4/\?[^']+)'", html_content or "", re.IGNORECASE):
            stream_url = html.unescape(url).replace("\\/", "/")
            if "_preview" in stream_url or "preview.mp4" in stream_url:
                continue
            quality = 0
            if key == "video_alt_url":
                quality = 720
            if "_720p" in stream_url:
                quality = max(quality, 720)
            elif re.search(r"/\d+\.mp4/", stream_url):
                quality = max(quality, 480)
            streams.append((quality, stream_url))
        streams.sort(key=lambda item: item[0], reverse=True)
        return streams

    def _probe_stream(self, stream_url, headers):
        try:
            probe_headers = dict(headers)
            probe_headers["Range"] = "bytes=0-0"
            response = self.session.get(stream_url, headers=probe_headers, timeout=(8, 15), stream=True, allow_redirects=True)
            ctype = response.headers.get("Content-Type", "")
            ok = response.status_code in (200, 206) and "video" in ctype.lower()
            response.close()
            return ok
        except Exception as exc:
            self.logger.warning("XXThots stream probe failed for %s: %s", stream_url, exc)
            return False

    def resolve_recording_stream(self, url):
        html_content = self._get(url, referer=self.base_url)
        streams = self._extract_streams(html_content)
        if not streams:
            self.logger.info("XXThots no public stream on detail page: %s", url)
            return None

        headers = {
            "User-Agent": self.ua,
            "Referer": url,
            "Accept": "*/*",
        }
        cookie_header = "; ".join("{}={}".format(cookie.name, cookie.value) for cookie in self.session.cookies)
        if cookie_header:
            headers["Cookie"] = cookie_header

        selected = None
        for _quality, stream_url in streams:
            if self._probe_stream(stream_url, headers):
                selected = stream_url
                break
        if not selected:
            return None
        return {"url": selected, "headers": headers, "extension": "mp4"}

    def play_video(self, url):
        resolved = self.resolve_recording_stream(url)
        if not resolved:
            self.notify_error("Could not resolve XXThots stream")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return

        proxy = _XXThotsRangeProxy(self.session, resolved["url"], resolved.get("headers") or {})
        play_url = proxy.start()
        _ACTIVE_PROXIES.append(proxy)
        del _ACTIVE_PROXIES[:-4]

        list_item = xbmcgui.ListItem(path=play_url)
        list_item.setProperty("IsPlayable", "true")
        list_item.setMimeType("video/mp4")
        list_item.setContentLookup(False)
        xbmcplugin.setResolvedUrl(self.addon_handle, True, list_item)
