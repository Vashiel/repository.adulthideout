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
from resources.lib.resilient_http import fetch_text


_ACTIVE_PROXIES = []


class _AllowFlashRangeProxy:
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
            server_version = "AHAllowFlashRange/1.0"

            def log_message(self, fmt, *args):
                return

            def do_GET(self):
                controller._handle(self)

            def do_HEAD(self):
                controller._handle(self, head_only=True)

        self.httpd = ThreadingHTTPServer((self.host, self.port), Handler)
        self.port = self.httpd.server_port
        self.local_url = "http://{}:{}/stream".format(self.host, self.port)
        self.thread = threading.Thread(target=self.httpd.serve_forever, name="AllowFlashRangeProxy", daemon=True)
        self.thread.start()
        xbmc.log("[ALLOWFLASH] Range proxy started: {}".format(self.local_url), xbmc.LOGINFO)
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
                timeout=30,
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
            xbmc.log("[ALLOWFLASH] Range proxy error: {}".format(exc), xbmc.LOGERROR)
            try:
                if not getattr(handler, "_headers_buffer", None):
                    handler.send_response(502)
                    handler.end_headers()
            except Exception:
                pass
        finally:
            if response is not None:
                response.close()


class Allowflash(BaseWebsite):
    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="allowflash",
            base_url="https://www.allowflash.com/",
            search_url="https://www.allowflash.com/?search={}",
            addon_handle=addon_handle,
            addon=addon,
        )
        self.label = "AllowFlash"
        self.session = requests.Session()
        self.ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        )
        self.sort_options = ["Newest", "Trending"]
        self.sort_paths = {
            "Newest": "/?order_by=newest",
            "Trending": "/?order_by=trending",
        }

    def _headers(self, referer=None, accept="text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"):
        return {
            "User-Agent": self.ua,
            "Referer": referer or self.base_url,
            "Accept": accept,
            "Accept-Language": "en-US,en;q=0.9",
        }

    def _get(self, url, referer=None, max_retries=4):
        last_error = None
        for attempt in range(1, max_retries + 1):
            try:
                response = self.session.get(url, headers=self._headers(referer), timeout=25)
                if response.status_code == 200:
                    return response.text
                last_error = "HTTP {}".format(response.status_code)
                self.logger.warning(
                    "AllowFlash HTTP %s for %s (attempt %s/%s)",
                    response.status_code,
                    url,
                    attempt,
                    max_retries,
                )
            except Exception as exc:
                last_error = exc
                self.logger.warning(
                    "AllowFlash request error for %s (attempt %s/%s): %s",
                    url,
                    attempt,
                    max_retries,
                    exc,
                )
                self.session = requests.Session()

            if attempt < max_retries:
                xbmc.sleep(750 * attempt)

        self.logger.error("AllowFlash failed to fetch %s after %s attempts: %s", url, max_retries, last_error)
        fallback = fetch_text(
            url,
            headers=self._headers(referer),
            scraper=None,
            logger=self.logger,
            timeout=25,
            use_windows_curl_fallback=True,
        )
        return fallback or ""

    def _end_failed_directory(self):
        xbmcplugin.endOfDirectory(self.addon_handle, succeeded=False, updateListing=False, cacheToDisc=False)

    def _absolute(self, value):
        if not value:
            return ""
        value = html.unescape(value).strip()
        return urllib.parse.urljoin(self.base_url, value)

    def _clean(self, value):
        value = re.sub(r"<[^>]+>", " ", value or "")
        return re.sub(r"\s+", " ", html.unescape(value)).strip()

    def get_start_url_and_label(self):
        sort_key = self._get_sort_key()
        return self._absolute(self.sort_paths.get(sort_key, "/?order_by=newest")), (
            "{} [COLOR yellow]{}[/COLOR]".format(self.label, sort_key)
        )

    def _get_sort_key(self):
        try:
            idx = int(self.addon.getSetting("allowflash_sort_by") or "0")
        except Exception:
            idx = 0
        if not 0 <= idx < len(self.sort_options):
            idx = 0
        return self.sort_options[idx]

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
        query = urllib.parse.parse_qs(parsed.query)
        return not parsed.path.strip("/") and "page" not in query and "search" not in query

    def _extract_videos(self, html_content):
        videos = []
        seen = set()
        for block in re.findall(r"<article\b[\s\S]*?</article>", html_content or "", re.IGNORECASE):
            href_match = re.search(r'href=["\']([^"\']*/view/\d+/[^"\']+)["\']', block, re.IGNORECASE)
            if not href_match:
                continue

            video_url = self._absolute(href_match.group(1))
            if not video_url or video_url in seen:
                continue
            seen.add(video_url)

            img_match = re.search(r"<img\b[^>]*>", block, re.IGNORECASE)
            img_tag = img_match.group(0) if img_match else ""
            thumb_match = re.search(r'\s(?:src|data-src)=["\']([^"\']+)["\']', img_tag, re.IGNORECASE)
            title_match = re.search(r'\s(?:alt|title)=["\']([^"\']+)["\']', img_tag, re.IGNORECASE)
            if not title_match:
                title_match = re.search(r"<h2\b[^>]*>[\s\S]*?<a\b[^>]*>([\s\S]*?)</a>", block, re.IGNORECASE)

            title = self._clean(title_match.group(1) if title_match else "")
            if not title:
                continue

            thumb = self._absolute(thumb_match.group(1)) if thumb_match else self.icon
            duration_match = re.search(r">\s*(\d{1,2}:\d{2}(?::\d{2})?)\s*</div>", block)
            duration = duration_match.group(1) if duration_match else ""
            duration_seconds = self.convert_duration(duration)
            label = "{} [COLOR lime]({})[/COLOR]".format(title, duration) if duration else title
            info_labels = {"title": title, "plot": title}
            if duration_seconds:
                info_labels["duration"] = duration_seconds

            videos.append(
                {
                    "label": label,
                    "url": video_url,
                    "thumb": thumb or self.icon,
                    "info": info_labels,
                    "is_premium": self._has_premium_marker(block),
                }
            )
        return self._filter_premium_items(videos)

    def _has_premium_marker(self, block):
        return "bg-amber" in (block or "") or "text-amber-400" in (block or "")

    def _filter_premium_items(self, videos):
        filtered = []
        skipped = 0
        for item in videos:
            if item.get("is_premium"):
                skipped += 1
                continue
            item.pop("is_premium", None)
            filtered.append(item)

        if skipped:
            self.logger.info("AllowFlash skipped %d premium entries", skipped)
        return filtered

    def _extract_next_page(self, html_content, current_url):
        parsed = urllib.parse.urlparse(current_url or self.base_url)
        current_page = int(urllib.parse.parse_qs(parsed.query).get("page", ["1"])[0] or "1")
        candidates = []
        for href in re.findall(r'href=["\']([^"\']*page=(\d+)[^"\']*)["\']', html_content or "", re.IGNORECASE):
            next_url = self._absolute(href[0])
            try:
                page_num = int(href[1])
            except ValueError:
                continue
            if page_num > current_page:
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
            self.add_dir("Categories", self.base_url, 8, self.icons.get("categories", self.icon), context_menu=context_menu)

        html_content = self._get(url)
        if not html_content:
            self.notify_error("Could not load AllowFlash listing")
            return self._end_failed_directory()

        videos = self._extract_videos(html_content)
        if not videos:
            self.notify_error("No AllowFlash videos found")
            return self.end_directory("videos")

        for item in videos:
            self.add_link(
                item["label"],
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
        html_content = self._get(url or self.base_url)
        if not html_content:
            self.notify_error("Could not load AllowFlash categories")
            return self._end_failed_directory()

        seen = set()
        for href, label_html in re.findall(
            r'<a\b[^>]*href=["\']([^"\']*/category/[^"\']+)["\'][^>]*>([\s\S]*?)</a>',
            html_content,
            re.IGNORECASE,
        ):
            category_url = self._absolute(href)
            if not category_url or category_url in seen:
                continue
            if "/category/premium" in urllib.parse.urlparse(category_url).path:
                continue
            seen.add(category_url)
            title = self._clean(label_html)
            if not title:
                slug = urllib.parse.urlparse(category_url).path.rstrip("/").rsplit("/", 1)[-1]
                title = slug.replace("-", " ").title()
            self.add_dir(title, category_url, 2, self.icons.get("categories", self.icon), self.fanart)

        self.end_directory("videos")

    def search(self, query):
        if query:
            self.process_content(self.search_url.format(urllib.parse.quote_plus(query.strip())))

    def _extract_stream_url(self, html_content):
        patterns = [
            r'<source\b[^>]+src=["\']([^"\']+\.mp4[^"\']*)["\']',
            r'<meta\s+property=["\']og:video["\'][^>]+content=["\']([^"\']+)["\']',
            r'https?://[^"\']+\.mp4(?:\?[^"\']*)?',
        ]
        for pattern in patterns:
            match = re.search(pattern, html_content or "", re.IGNORECASE)
            if not match:
                continue
            stream_url = match.group(1) if match.lastindex else match.group(0)
            stream_url = html.unescape(stream_url).replace("\\/", "/").strip()
            if stream_url.startswith("//"):
                stream_url = "https:" + stream_url
            elif stream_url.startswith("/"):
                stream_url = urllib.parse.urljoin(self.base_url, stream_url)
            if stream_url.startswith("http"):
                return stream_url
        return None

    def resolve_recording_stream(self, url):
        html_content = self._get(url, referer=self.base_url)
        stream_url = self._extract_stream_url(html_content)
        if not stream_url:
            self.logger.info("AllowFlash no public stream on detail page: %s", url)
            return None

        headers = {
            "User-Agent": self.ua,
            "Referer": url,
            "Accept": "*/*",
        }
        cookie_header = "; ".join("{}={}".format(cookie.name, cookie.value) for cookie in self.session.cookies)
        if cookie_header:
            headers["Cookie"] = cookie_header
        return {"url": stream_url, "headers": headers, "extension": "mp4"}

    def play_video(self, url):
        resolved = self.resolve_recording_stream(url)
        if not resolved:
            self.notify_error("Could not resolve AllowFlash stream")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return

        proxy = _AllowFlashRangeProxy(self.session, resolved["url"], resolved.get("headers") or {})
        play_url = proxy.start()
        _ACTIVE_PROXIES.append(proxy)
        del _ACTIVE_PROXIES[:-4]

        list_item = xbmcgui.ListItem(path=play_url)
        list_item.setProperty("IsPlayable", "true")
        list_item.setMimeType("video/mp4")
        list_item.setContentLookup(False)
        xbmcplugin.setResolvedUrl(self.addon_handle, True, list_item)
