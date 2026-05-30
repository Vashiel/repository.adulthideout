#!/usr/bin/env python
# -*- coding: utf-8 -*-

import html
import json
import re
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar
from http.server import BaseHTTPRequestHandler, HTTPServer

try:
    from http.server import ThreadingHTTPServer
except ImportError:
    import socketserver

    class ThreadingHTTPServer(socketserver.ThreadingMixIn, HTTPServer):
        daemon_threads = True

import requests

import xbmcaddon
import xbmcgui
import xbmcplugin

from resources.lib.base_website import BaseWebsite


_ACTIVE_PROXIES = []


class _HStreamRangeProxy:
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
            server_version = "AHHStreamRange/1.0"

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
        self.thread = threading.Thread(target=self.httpd.serve_forever, name="HStreamRangeProxy", daemon=True)
        self.thread.start()
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
            try:
                import xbmc
                xbmc.log("[HStream] Range proxy error: {}".format(exc), xbmc.LOGERROR)
            except Exception:
                pass
            try:
                if not getattr(handler, "_headers_buffer", None):
                    handler.send_response(502)
                    handler.end_headers()
            except Exception:
                pass
        finally:
            if response is not None:
                response.close()


class HStreamWebsite(BaseWebsite):
    def __init__(self, addon_handle):
        addon = xbmcaddon.Addon()
        name = "hstream"
        base_url = "https://hstream.moe/"
        search_url = "https://hstream.moe/search?search={}&order=recently-uploaded"
        super(HStreamWebsite, self).__init__(
            name, base_url, search_url, addon_handle, addon=addon
        )
        self.label = "HStream"
        self.sort_options = ["Recently Uploaded", "Recently Released", "Most Views"]
        self.sort_values = ["recently-uploaded", "recently-released", "view-count"]
        self.cookie_jar = CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cookie_jar)
        )
        self.session = requests.Session()
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/126.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

    def get_start_url_and_label(self):
        sort_value, sort_label = self._current_sort()
        return (
            self.base_url + "search?order=" + urllib.parse.quote_plus(sort_value),
            "%s - %s" % (self.label, sort_label),
        )

    def process_content(self, url):
        current_url = url if url and url != "BOOTSTRAP" else self.get_start_url_and_label()[0]

        context_menu = [
            (
                "Sort by...",
                "RunPlugin(%s?mode=7&action=select_sort&website=%s&original_url=%s)"
                % (sys.argv[0], self.name, urllib.parse.quote_plus(current_url)),
            )
        ]
        self.add_dir("[COLOR blue]Search[/COLOR]", "", 5, self.icons["search"])
        self.add_dir("[COLOR blue]Categories[/COLOR]", self.base_url, 8, self.icons["categories"])

        page = self._http_get(current_url)
        if not page:
            self.notify_error("Failed to load page.")
            self.end_directory()
            return

        items = self._parse_listing(page)
        for item in items:
            self.add_link(
                item["title"],
                item["url"],
                4,
                item.get("thumb") or self.icon,
                self.fanart,
                context_menu,
                info_labels={"title": item["title"]},
            )

        if not items:
            self.notify_info("No videos found.")

        if len(items) >= 25:
            self.add_dir(
                "[COLOR blue]Next Page >>>>[/COLOR]",
                self._next_page_url(current_url),
                2,
                self.icons["default"],
                self.fanart,
                context_menu,
            )

        self.end_directory()

    def process_categories(self, url=None):
        page = self._http_get(url or self.base_url)
        if not page:
            self.notify_error("Failed to load categories.")
            self.end_directory()
            return

        seen = set()
        for href, label in re.findall(
            r'<a[^>]+href=["\']([^"\']*tags%5B0%5D=[^"\']+)["\'][^>]*>(.*?)</a>',
            page,
            re.IGNORECASE | re.DOTALL,
        ):
            title = self._clean_text(label)
            full_url = urllib.parse.urljoin(self.base_url, html.unescape(href))
            if title and full_url not in seen:
                seen.add(full_url)
                self.add_dir(title, full_url, 2, self.icons["categories"])

        if not seen:
            for tag in self._extract_tags_from_search(page):
                url = self.base_url + "search?order=recently-uploaded&tags%5B0%5D=" + urllib.parse.quote_plus(tag)
                self.add_dir(self._title_from_slug(tag), url, 2, self.icons["categories"])

        self.end_directory()

    def play_video(self, url):
        page = self._http_get(url, referer=self.base_url)
        episode_id = self._match_first(page, r'id=["\']e_id["\'][^>]+value=["\']([^"\']+)')
        token = self._match_first(page, r'name=["\']_token["\']\s+value=["\']([^"\']+)')
        if not episode_id or not token:
            self.notify_error("Failed to read player data.")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem(path=url))
            return

        data = self._player_api(episode_id, token, url)
        stream_url = self._select_stream(data)
        if not stream_url:
            self.notify_error("No playable stream found.")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem(path=url))
            return

        headers = {
            "User-Agent": self.headers["User-Agent"],
            "Referer": url,
        }
        proxy = _HStreamRangeProxy(self.session, stream_url, headers)
        play_url = proxy.start()
        _ACTIVE_PROXIES.append(proxy)

        li = xbmcgui.ListItem(path=play_url)
        li.setProperty("IsPlayable", "true")
        li.setMimeType("video/mp4")
        li.setContentLookup(False)
        xbmcplugin.setResolvedUrl(self.addon_handle, True, li)

    def search(self, query):
        if not query:
            return
        self.process_content(self.search_url.format(urllib.parse.quote_plus(query)))

    def select_sort(self, original_url=None):
        current_idx = 0
        try:
            current_idx = int(self.addon.getSetting("%s_sort_by" % self.name) or "0")
        except ValueError:
            current_idx = 0
        idx = xbmcgui.Dialog().select("Sort by...", self.sort_options, preselect=current_idx)
        if idx == -1:
            return
        self.addon.setSetting("%s_sort_by" % self.name, str(idx))
        sort_value = self.sort_values[idx]
        target = original_url or self.get_start_url_and_label()[0]
        parsed = urllib.parse.urlparse(target)
        params = urllib.parse.parse_qs(parsed.query)
        params["order"] = [sort_value]
        params.pop("page", None)
        query = urllib.parse.urlencode(params, doseq=True)
        update_url = urllib.parse.urlunparse(parsed._replace(query=query))
        import xbmc
        xbmc.executebuiltin(
            "Container.Update(%s?mode=2&url=%s&website=%s,replace)"
            % (sys.argv[0], urllib.parse.quote_plus(update_url), self.name)
        )

    def _http_get(self, url, referer=None, timeout=25):
        target = urllib.parse.urljoin(self.base_url, url or self.base_url)
        headers = self.headers.copy()
        headers["Referer"] = referer or self.base_url
        try:
            request = urllib.request.Request(target, headers=headers)
            with self.opener.open(request, timeout=timeout) as response:
                return response.read().decode("utf-8", errors="ignore")
        except urllib.error.HTTPError as exc:
            self.logger.warning("HTTP %s while loading %s", exc.code, target)
        except Exception as exc:
            self.logger.warning("Request failed for %s: %s", target, exc)
        return ""

    def _player_api(self, episode_id, token, referer):
        payload = json.dumps({"episode_id": episode_id}).encode("utf-8")
        headers = {
            "User-Agent": self.headers["User-Agent"],
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "X-Requested-With": "XMLHttpRequest",
            "X-CSRF-TOKEN": token,
            "Origin": self.base_url.rstrip("/"),
            "Referer": referer,
        }
        try:
            request = urllib.request.Request(
                urllib.parse.urljoin(self.base_url, "/player/api"),
                data=payload,
                headers=headers,
                method="POST",
            )
            with self.opener.open(request, timeout=25) as response:
                return json.loads(response.read().decode("utf-8", errors="ignore"))
        except Exception as exc:
            self.logger.warning("Player API failed for episode %s: %s", episode_id, exc)
        return {}

    def _select_stream(self, data):
        stream_path = data.get("stream_url")
        domains = data.get("stream_domains") or []
        if not stream_path or not domains:
            return ""
        domain = str(domains[0]).rstrip("/")
        stream_path = str(stream_path).strip("/")
        return "%s/%s/x264.720p.mp4" % (domain, stream_path)

    def _parse_listing(self, page):
        items = []
        seen = set()
        pattern = re.compile(
            r'<a\s+href=["\'](https://hstream\.moe/hentai/[^"\']+)["\'][^>]*>(.*?)</a>',
            re.IGNORECASE | re.DOTALL,
        )
        for href, block in pattern.findall(page):
            href = html.unescape(href)
            if href in seen:
                continue
            seen.add(href)
            title = self._match_first(block, r'<img[^>]+alt=["\']([^"\']+)')
            if not title:
                title = self._match_first(block, r"<h3[^>]*>(.*?)</h3>")
            thumb = self._match_first(block, r'<img[^>]+(?:data-src|src)=["\']([^"\']+)')
            title = self._clean_text(title) or self._title_from_slug(href.rstrip("/").split("/")[-1])
            thumb = urllib.parse.urljoin(self.base_url, html.unescape(thumb or ""))
            items.append({"title": title, "url": href, "thumb": thumb})
        return items

    def _next_page_url(self, url):
        parsed = urllib.parse.urlparse(url)
        params = urllib.parse.parse_qs(parsed.query)
        try:
            page = int(params.get("page", ["1"])[0])
        except ValueError:
            page = 1
        params["page"] = [str(page + 1)]
        if "order" not in params:
            params["order"] = [self._current_sort()[0]]
        query = urllib.parse.urlencode(params, doseq=True)
        return urllib.parse.urlunparse(parsed._replace(query=query))

    def _current_sort(self):
        try:
            idx = int(self.addon.getSetting("%s_sort_by" % self.name) or "0")
        except ValueError:
            idx = 0
        if idx < 0 or idx >= len(self.sort_values):
            idx = 0
        return self.sort_values[idx], self.sort_options[idx]

    def _extract_tags_from_search(self, page):
        tags = []
        for tag in re.findall(r'name=["\']tags\[\]["\'][^>]+value=["\']([^"\']+)["\']', page, re.IGNORECASE):
            if tag not in tags:
                tags.append(tag)
        return tags

    def _match_first(self, text, pattern):
        match = re.search(pattern, text or "", re.IGNORECASE | re.DOTALL)
        return html.unescape(match.group(1)) if match else ""

    def _clean_text(self, value):
        value = html.unescape(value or "")
        value = re.sub(r"<[^>]+>", " ", value)
        value = re.sub(r"\s+", " ", value)
        return value.strip()

    def _title_from_slug(self, slug):
        words = [part for part in re.split(r"[-_]+", slug or "") if part]
        return " ".join(word.capitalize() for word in words) or slug
