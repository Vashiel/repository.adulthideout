# -*- coding: utf-8 -*-
import html
import os
import re
import struct
import sys
import tempfile
import threading
import urllib.parse
import zlib
from http.server import BaseHTTPRequestHandler, HTTPServer

try:
    from http.server import ThreadingHTTPServer
except ImportError:
    import socketserver

    class ThreadingHTTPServer(socketserver.ThreadingMixIn, HTTPServer):
        daemon_threads = True

import requests
import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
import xbmcvfs

from resources.lib.base_website import BaseWebsite
from resources.lib.resolvers import resolver

try:
    addon_path = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    vendor_path = os.path.join(addon_path, "resources", "lib", "vendor")
    if vendor_path not in sys.path:
        sys.path.insert(0, vendor_path)
    import cloudscraper
except Exception:
    cloudscraper = None


ACTION_NAV_BACK = getattr(xbmcgui, "ACTION_NAV_BACK", 92)
ACTION_PREVIOUS_MENU = getattr(xbmcgui, "ACTION_PREVIOUS_MENU", 10)
ACTION_SELECT_ITEM = getattr(xbmcgui, "ACTION_SELECT_ITEM", 7)


def _png_chunk(tag, payload):
    return struct.pack("!I", len(payload)) + tag + payload + struct.pack("!I", zlib.crc32(tag + payload) & 0xFFFFFFFF)


def _captcha_background_path():
    try:
        profile = xbmcaddon.Addon().getAddonInfo("profile")
        try:
            profile = xbmcvfs.translatePath(profile)
        except AttributeError:
            profile = xbmc.translatePath(profile)
        if profile and not xbmcvfs.exists(profile):
            xbmcvfs.mkdirs(profile)
    except Exception:
        profile = tempfile.gettempdir()

    path = os.path.join(profile or tempfile.gettempdir(), "pornhoarder_captcha_bg.png")
    if os.path.exists(path):
        return path

    # 1x1 black PNG used as a scalable dialog backdrop.
    raw = b"\x00\x00\x00\x00\xff"
    png = (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", struct.pack("!IIBBBBB", 1, 1, 8, 6, 0, 0, 0))
        + _png_chunk(b"IDAT", zlib.compress(raw))
        + _png_chunk(b"IEND", b"")
    )
    with open(path, "wb") as handle:
        handle.write(png)
    return path


class _PornHoarderCaptchaWindow(xbmcgui.WindowDialog):
    def __init__(self, question, images):
        super(_PornHoarderCaptchaWindow, self).__init__()
        self.question = question
        self.images = images
        self.selected = set()
        self.finished = False
        self.image_buttons = {}
        self.button_controls = []
        self.status_labels = {}
        self.ok_button = None
        self.cancel_button = None
        self._build_controls()

    def _build_controls(self):
        width = self.getWidth()
        height = self.getHeight()
        cell = min(180, max(120, (width - 160) // 4))
        image_size = cell - 26
        grid_width = cell * 4
        start_x = max(20, (width - grid_width) // 2)
        start_y = max(90, (height - (cell * 2) - 150) // 2)
        bg = _captcha_background_path()
        panel_x = max(20, start_x - 35)
        panel_y = max(12, start_y - 84)
        panel_w = min(width - 40, grid_width + 70)
        panel_h = min(height - (panel_y * 2), (cell * 2) + 170)

        self.addControl(xbmcgui.ControlImage(0, 0, width, height, bg, 0, "0xCCFFFFFF"))
        self.addControl(xbmcgui.ControlImage(panel_x, panel_y, panel_w, panel_h, bg, 0, "0xF5FFFFFF"))

        self.addControl(
            xbmcgui.ControlLabel(
                40,
                max(20, start_y - 72),
                width - 80,
                44,
                "PornHoarder verification: {}".format(self.question),
                textColor="0xFFFFFFFF",
                alignment=6,
            )
        )
        self.addControl(
            xbmcgui.ControlLabel(
                40,
                max(58, start_y - 36),
                width - 80,
                30,
                "Select all matching images, then press OK.",
                textColor="0xFFCCCCCC",
                alignment=6,
            )
        )

        for idx, item in enumerate(self.images):
            col = idx % 4
            row = idx // 4
            x = start_x + (col * cell) + 10
            y = start_y + (row * cell)
            value = item["value"]

            image_control = xbmcgui.ControlImage(x, y, image_size, image_size, item["path"])
            self.addControl(image_control)

            button = xbmcgui.ControlButton(
                x,
                y + image_size + 4,
                image_size,
                34,
                "[ ] {}".format(idx + 1),
                textColor="0xFFFFFFFF",
                alignment=6,
            )
            self.addControl(button)
            self.image_buttons[button.getId()] = value
            self.button_controls.append(button)
            self.status_labels[value] = button

        button_y = min(height - 86, start_y + (cell * 2) + 35)
        self.ok_button = xbmcgui.ControlButton(
            (width // 2) - 190,
            button_y,
            170,
            56,
            "OK",
            textColor="0xFF9FFB05",
            alignment=6,
        )
        self.cancel_button = xbmcgui.ControlButton(
            (width // 2) + 20,
            button_y,
            170,
            56,
            "Cancel",
            textColor="0xFFFF7777",
            alignment=6,
        )
        self.addControl(self.ok_button)
        self.addControl(self.cancel_button)
        self._wire_navigation(4)
        try:
            self.setFocus(next(iter(self.status_labels.values())))
        except Exception:
            pass

    def _safe_nav(self, control, up=None, down=None, left=None, right=None):
        try:
            if up:
                control.controlUp(up)
            if down:
                control.controlDown(down)
            if left:
                control.controlLeft(left)
            if right:
                control.controlRight(right)
        except Exception:
            pass

    def _wire_navigation(self, columns):
        buttons = list(self.button_controls)
        if not buttons:
            return
        for idx, button in enumerate(buttons):
            col = idx % columns
            left = buttons[idx - 1] if col > 0 else button
            right = buttons[idx + 1] if (idx + 1) < len(buttons) and ((idx + 1) % columns) != 0 else button
            up = buttons[idx - columns] if idx - columns >= 0 else button
            down = buttons[idx + columns] if idx + columns < len(buttons) else self.ok_button
            self._safe_nav(button, up=up, down=down, left=left, right=right)
        self._safe_nav(self.ok_button, up=buttons[-1], left=self.ok_button, right=self.cancel_button)
        self._safe_nav(self.cancel_button, up=buttons[-1], left=self.ok_button, right=self.cancel_button)

    def _toggle(self, value):
        if value in self.selected:
            self.selected.remove(value)
        else:
            self.selected.add(value)
        button = self.status_labels.get(value)
        if button:
            try:
                number = self.images[[item["value"] for item in self.images].index(value)].get("number", "")
                button.setLabel("[X] {}".format(number) if value in self.selected else "[ ] {}".format(number))
            except Exception:
                button.setLabel("[X]" if value in self.selected else "[ ]")

    def onAction(self, action):
        action_id = action.getId() if hasattr(action, "getId") else action
        if action_id in (ACTION_NAV_BACK, ACTION_PREVIOUS_MENU):
            self.close()
        elif action_id == ACTION_SELECT_ITEM:
            focus = self.getFocus()
            if focus:
                self.onControl(focus)

    def onControl(self, control):
        control_id = control.getId()
        if control_id in self.image_buttons:
            self._toggle(self.image_buttons[control_id])
        elif self.ok_button and control_id == self.ok_button.getId():
            self.finished = True
            self.close()
        elif self.cancel_button and control_id == self.cancel_button.getId():
            self.close()


class _PornHoarderHlsProxy:
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
            server_version = "AHPornHoarderHLS/1.0"

            def log_message(self, fmt, *args):
                return

            def do_GET(self):
                controller._handle(self)

        self.httpd = ThreadingHTTPServer((self.host, self.port), Handler)
        self.port = self.httpd.server_port
        self.local_url = "http://{}:{}/stream?u={}".format(
            self.host,
            self.port,
            urllib.parse.quote(self.upstream_url, safe=""),
        )
        self.thread = threading.Thread(target=self.httpd.serve_forever, name="PornHoarderHlsProxy", daemon=True)
        self.thread.start()
        xbmc.log("[PornHoarder] HLS proxy started: {}".format(self.local_url), xbmc.LOGINFO)
        return self.local_url

    def stop(self):
        try:
            if self.httpd:
                self.httpd.shutdown()
                self.httpd.server_close()
        except Exception:
            pass

    def _handle(self, handler):
        parsed = urllib.parse.urlparse(handler.path)
        upstream_url = urllib.parse.parse_qs(parsed.query).get("u", [self.upstream_url])[0]
        headers = dict(self.headers)
        range_header = handler.headers.get("Range")
        if range_header:
            headers["Range"] = range_header

        try:
            response = self.session.get(upstream_url, headers=headers, timeout=30, allow_redirects=True)
            content_type = response.headers.get("Content-Type", "")
            is_playlist = ".m3u8" in upstream_url or "mpegurl" in content_type.lower()
            body = response.content

            handler.send_response(response.status_code)
            if is_playlist:
                handler.send_header("Content-Type", "application/vnd.apple.mpegurl")
                handler.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
            else:
                for key in ("Content-Type", "Content-Length", "Content-Range", "Accept-Ranges"):
                    value = response.headers.get(key)
                    if value:
                        handler.send_header(key, value)
                if not response.headers.get("Content-Length"):
                    handler.send_header("Content-Length", str(len(body)))
            handler.end_headers()

            if response.status_code not in (200, 206):
                handler.wfile.write(body)
                return

            if is_playlist:
                text = body.decode("utf-8", errors="replace")
                base_url = response.url or upstream_url
                rewritten = []
                for line in text.splitlines():
                    stripped = line.strip()
                    if 'URI="' in line:
                        def replace_uri(match):
                            absolute = urllib.parse.urljoin(base_url, match.group(1))
                            proxied = "http://{}:{}/stream?u={}".format(
                                self.host,
                                self.port,
                                urllib.parse.quote(absolute, safe=""),
                            )
                            return 'URI="{}"'.format(proxied)

                        line = re.sub(r'URI="([^"]+)"', replace_uri, line)
                    if stripped and not stripped.startswith("#"):
                        absolute = urllib.parse.urljoin(base_url, stripped)
                        line = "http://{}:{}/stream?u={}".format(
                            self.host,
                            self.port,
                            urllib.parse.quote(absolute, safe=""),
                        )
                    rewritten.append(line)
                handler.wfile.write(("\n".join(rewritten) + "\n").encode("utf-8"))
                return

            handler.wfile.write(body)
        except Exception as exc:
            xbmc.log("[PornHoarder] HLS proxy error for {}: {}".format(upstream_url, exc), xbmc.LOGWARNING)
            try:
                handler.send_error(502, "Proxy error")
            except Exception:
                pass


class PornhoarderWebsite(BaseWebsite):
    NETU_ONLY_HOSTS = ("dirtyvideo", "netu", "waaw", "hqq")
    HOST_PRIORITY = [
        "lulustream",
        "luluvdo",
        "playmogo",
        "vidello",
        "vidhide",
        "minochinos",
        "callistanise",
        "sunflowercreativeworks",
        "streamtape",
        "dood",
        "voe",
        "mixdrop",
        "bigwarp",
        "dirtyvideo",
        "netu",
        "waaw",
        "hqq",
    ]

    SORT_OPTIONS = ["Latest", "Trending", "Random"]
    SORT_PATHS = {
        "Latest": "/search/?search=&sort=0",
        "Trending": "/trending-videos/",
        "Random": "/random-videos/",
    }

    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="pornhoarder",
            base_url="https://pornhoarder.tv",
            search_url="https://pornhoarder.tv/search/",
            addon_handle=addon_handle,
            addon=addon,
        )
        self.ajax_search_url = "https://pornhoarder.tv/ajax_search.php"
        self.player_base = "https://pornhoarder.net"
        self.session = requests.Session()
        # Lulu/TNMR HLS currently rejects cloudscraper's TLS/client fingerprint with 403,
        # while a plain requests session succeeds. Keep the HLS proxy on requests.
        self.hls_session = requests.Session()
        self.ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/128.0.0.0 Safari/537.36"
        )

    def _headers(self, referer=None):
        return {
            "User-Agent": self.ua,
            "Referer": referer or (self.base_url + "/"),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

    def _make_request(self, url, referer=None, method="GET", data=None):
        try:
            if method == "POST":
                headers = self._headers(referer)
                headers["Origin"] = self.player_base
                headers["Content-Type"] = "application/x-www-form-urlencoded"
                response = self.session.post(url, headers=headers, data=data or {}, timeout=25)
            else:
                response = self.session.get(url, headers=self._headers(referer), timeout=25)
            if response.status_code == 200:
                return response.text
            self.logger.error("[PornHoarder] HTTP %s for %s", response.status_code, url)
        except Exception as exc:
            self.logger.error("[PornHoarder] Request error for %s: %s", url, exc)
        return None

    def _clean(self, value):
        value = re.sub(r"<[^>]+>", " ", value or "")
        return re.sub(r"\s+", " ", html.unescape(value)).strip()

    def _absolute(self, value, base=None):
        if not value:
            return ""
        return urllib.parse.urljoin((base or self.base_url) + "/", html.unescape(value.strip()))

    def _get_sort_index(self):
        try:
            idx = int(self.addon.getSetting("pornhoarder_sort_by") or "0")
            if 0 <= idx < len(self.SORT_OPTIONS):
                return idx
        except (ValueError, TypeError):
            pass
        return 0

    def get_start_url_and_label(self):
        sort_option = self.SORT_OPTIONS[self._get_sort_index()]
        return self.base_url + self.SORT_PATHS[sort_option], "PornHoarder [COLOR yellow]{}[/COLOR]".format(sort_option)

    def _build_context_menu(self):
        return [
            (
                "Sort by...",
                "RunPlugin({}?mode=7&action=select_sort&website={})".format(sys.argv[0], self.name),
            )
        ]

    def _add_navigation_entries(self, context_menu=None):
        self.add_dir("Search", "", 5, self.icons.get("search", self.icon), context_menu=context_menu)
        self.add_dir("Pornstars", self.base_url + "/porn-stars/", 9, self.icons.get("pornstars", self.icon), context_menu=context_menu)
        self.add_dir("Studios", self.base_url + "/porn-studios/", 10, self.icons.get("pornstars", self.icon), context_menu=context_menu)

    def select_sort(self, original_url=None):
        idx = xbmcgui.Dialog().select("Sort by...", self.SORT_OPTIONS, preselect=self._get_sort_index())
        if idx == -1:
            return
        self.addon.setSetting("pornhoarder_sort_by", str(idx))
        new_url, _ = self.get_start_url_and_label()
        xbmc.executebuiltin(
            "Container.Update({}?mode=2&website={}&url={},replace)".format(
                sys.argv[0], self.name, urllib.parse.quote_plus(new_url)
            )
        )

    def _extract_videos(self, page_html):
        items = []
        seen = set()
        for block in re.findall(r"<article>\s*([\s\S]*?)</article>", page_html or "", re.IGNORECASE):
            link_match = re.search(r'<a[^>]+href="([^"]*/pornvideo/[^"]+)"[^>]*class="[^"]*video-link[^"]*"', block, re.IGNORECASE)
            if not link_match:
                continue
            video_url = self._absolute(link_match.group(1))
            if video_url in seen:
                continue
            seen.add(video_url)

            title_match = re.search(r"<h1>(.*?)</h1>", block, re.IGNORECASE | re.DOTALL)
            title = self._clean(title_match.group(1)) if title_match else ""
            if not title:
                title = urllib.parse.unquote(video_url.rstrip("/").split("/")[-2]).replace("-", " ").title()

            thumb = self.icon
            thumb_match = re.search(r'data-src="([^"]+)"', block, re.IGNORECASE)
            if thumb_match:
                thumb = self._absolute(thumb_match.group(1))

            duration_text = ""
            duration_match = re.search(r'<div[^>]+class="[^"]*video-length[^"]*"[^>]*>(.*?)</div>', block, re.IGNORECASE | re.DOTALL)
            if duration_match:
                duration_text = self._clean(duration_match.group(1))

            meta = []
            hosters = []
            for meta_match in re.findall(r'<div[^>]+class="[^"]*item[^"]*"[^>]*>(.*?)</div>', block, re.IGNORECASE | re.DOTALL):
                is_server_meta = "/img/server_icons/" in meta_match
                text = self._clean(meta_match)
                if is_server_meta and text:
                    hosters.append(text.lower())
                if text and text.lower() not in ("already watched",):
                    meta.append(text)

            label = title
            if duration_text:
                label = "{} [COLOR lime]({})[/COLOR]".format(title, duration_text)

            info = {"title": title, "plot": " | ".join([title] + meta)}
            duration = self.convert_duration(duration_text)
            if duration:
                info["duration"] = duration

            items.append({"title": label, "url": video_url, "thumb": thumb, "info": info, "hosters": hosters})
        return items

    def _is_netu_only_item(self, item):
        hosters = [hoster.lower() for hoster in item.get("hosters", []) if hoster]
        if not hosters:
            return False
        return all(any(netu_host in hoster for netu_host in self.NETU_ONLY_HOSTS) for hoster in hosters)

    def _filter_netu_only(self, videos):
        visible = [item for item in videos if not self._is_netu_only_item(item)]
        hidden = len(videos) - len(visible)
        if hidden:
            self.logger.info("[PornHoarder] Hidden %s Netu-only entries from listing", hidden)
        return visible, hidden

    def _next_page_url(self, url, next_page):
        parsed = urllib.parse.urlparse(url or self.base_url)
        path_parts = [part for part in (parsed.path or "/").split("/") if part]
        if path_parts and path_parts[-1].isdigit():
            path_parts[-1] = str(next_page)
        else:
            path_parts.append(str(next_page))
        next_path = "/" + "/".join(path_parts) + "/"
        return urllib.parse.urlunparse((parsed.scheme or "https", parsed.netloc or urllib.parse.urlparse(self.base_url).netloc, next_path, "", parsed.query, ""))

    def _add_next_page(self, url, page, context_menu=None):
        next_page = int(page or 1) + 1
        next_url = url if "/search/" in (url or "") else self._next_page_url(url, next_page)
        self.add_dir(
            "[COLOR blue]Next Page ({}) >>[/COLOR]".format(next_page),
            next_url,
            2,
            self.icons.get("default", self.icon),
            context_menu=context_menu,
            page=next_page,
        )

    def _extract_links(self, page_html, path_prefix):
        links = []
        seen = set()
        pattern = r'<a[^>]+href="([^"]*%s[^"]*)"[^>]*>([\s\S]*?)</a>' % re.escape(path_prefix)
        for href, inner in re.findall(pattern, page_html or "", re.IGNORECASE):
            target = self._absolute(href)
            title_match = re.search(r"<h2>(.*?)</h2>", inner, re.IGNORECASE | re.DOTALL)
            label = self._clean(title_match.group(1) if title_match else inner)
            if not target or target in seen or not label:
                continue
            seen.add(target)
            links.append((label, target))
        return links

    def _extract_category_links(self, page_html):
        links = []
        seen = set()
        for block in re.findall(r"<article>\s*([\s\S]*?)</article>", page_html or "", re.IGNORECASE):
            href_match = re.search(r'<a[^>]+href="([^"]*/search/\?search=[^"]+)"', block, re.IGNORECASE)
            title_match = re.search(r"<h2>(.*?)</h2>", block, re.IGNORECASE | re.DOTALL)
            if not href_match or not title_match:
                continue
            target = self._absolute(href_match.group(1))
            label = self._clean(title_match.group(1))
            if target and label and target not in seen:
                seen.add(target)
                links.append((label, target))
        return links

    def process_content(self, url, page=1):
        if not url or url == "BOOTSTRAP":
            url, _ = self.get_start_url_and_label()

        if "/search/" in url and "search=" in url:
            parsed = urllib.parse.urlparse(url)
            query = urllib.parse.parse_qs(parsed.query).get("search", [""])[0]
            sort = urllib.parse.parse_qs(parsed.query).get("sort", ["0"])[0]
            self.search(query.replace(" :: ", " "), page=page, sort=sort)
            return

        page_html = self._make_request(url)
        if not page_html:
            self.notify_error("Could not load PornHoarder page")
            self.end_directory("videos")
            return

        context_menu = self._build_context_menu()
        if "/pornvideo/" not in url:
            self._add_navigation_entries(context_menu=context_menu)

        videos = self._extract_videos(page_html)
        if not videos:
            self.notify_error("No PornHoarder videos found")
            self.end_directory("videos")
            return

        videos, hidden = self._filter_netu_only(videos)
        if not videos and hidden:
            self.notify_error("Only Netu-only entries hidden on this page")

        for item in videos:
            self.add_link(item["title"], item["url"], 4, item["thumb"], self.fanart, context_menu=context_menu, info_labels=item["info"])

        self._add_next_page(url, page, context_menu=context_menu)
        self.end_directory("videos")

    def process_categories(self, url):
        page_html = self._make_request(url or (self.base_url + "/categories/"))
        if not page_html:
            self.end_directory("videos")
            return
        for label, target in self._extract_category_links(page_html):
            self.add_dir(label, target, 2, self.icons.get("categories", self.icon))
        self.end_directory("videos")

    def process_pornstars(self, url):
        page_html = self._make_request(url or (self.base_url + "/porn-stars/"))
        if not page_html:
            self.end_directory("videos")
            return
        for label, target in self._extract_links(page_html, "/porn-star/"):
            self.add_dir(label, target, 2, self.icons.get("pornstars", self.icon))
        self.end_directory("videos")

    def process_channels(self, url):
        page_html = self._make_request(url or (self.base_url + "/porn-studios/"))
        if not page_html:
            self.end_directory("videos")
            return
        for label, target in self._extract_links(page_html, "/porn-studio/"):
            self.add_dir(label, target, 2, self.icons.get("pornstars", self.icon))
        self.end_directory("videos")

    def search(self, query, page=1, sort="0"):
        if query is None:
            return
        data = [
            ("search", query.strip()),
            ("sort", str(sort or "0")),
            ("date", "0"),
            ("author", "0"),
            ("page", str(page or 1)),
        ]
        for server in ("47", "21", "40", "45", "12", "25", "41", "44", "42", "43", "48", "29"):
            data.append(("servers[]", server))
        page_html = self._make_request(self.ajax_search_url, referer=self.search_url, method="POST", data=data)
        if not page_html:
            self.notify_error("PornHoarder search failed")
            self.end_directory("videos")
            return
        context_menu = self._build_context_menu()
        if not query.strip():
            self._add_navigation_entries(context_menu=context_menu)
        videos, hidden = self._filter_netu_only(self._extract_videos(page_html))
        if not videos and hidden:
            self.notify_error("Only Netu-only entries hidden on this page")
        for item in videos:
            self.add_link(item["title"], item["url"], 4, item["thumb"], self.fanart, context_menu=context_menu, info_labels=item["info"])
        search_url = "{}?search={}&sort={}".format(self.search_url, urllib.parse.quote_plus(query.strip()), urllib.parse.quote_plus(str(sort or "0")))
        self._add_next_page(search_url, page, context_menu=context_menu)
        self.end_directory("videos")

    def _normalize_hoster_url(self, url):
        url = html.unescape(url or "").replace("\\/", "/").strip()
        url = re.sub(r"(doodstream\.\w+|dood\.\w+|dsvplay\.\w+|myvidplay\.\w+|dooood\.\w+)/d/", r"\1/e/", url)
        url = re.sub(r"(streamtape\.\w+)/v/", r"\1/e/", url)
        url = re.sub(r"(mixdrop\.\w+)/f/", r"\1/e/", url)
        return url

    def _extract_player_url(self, page_html):
        match = re.search(r'<iframe[^>]+src="([^"]*pornhoarder\.net/player\.php\?video=[^"]+)"', page_html or "", re.IGNORECASE)
        if match:
            return self._absolute(match.group(1), self.player_base)
        match = re.search(r'https://pornhoarder\.net/player\.php\?video=[^\s"\'<>]+', page_html or "", re.IGNORECASE)
        return html.unescape(match.group(0)) if match else ""

    def _extract_host_links(self, page_html):
        links = []
        seen = set()
        patterns = [
            r'<iframe[^>]+src="([^"]+)"',
            r'<source[^>]+src="([^"]+)"',
            r'https?://[^\s"\'<>]+',
        ]
        for pattern in patterns:
            for raw_url in re.findall(pattern, page_html or "", re.IGNORECASE):
                url = self._normalize_hoster_url(raw_url)
                lower = url.lower()
                if not url.startswith("http") or "pornhoarder." in lower or "pictures" in lower:
                    continue
                if any(host in lower for host in self.HOST_PRIORITY) and "api/" not in lower and "://api." not in lower and url not in seen:
                    seen.add(url)
                    links.append(url)

        def priority(value):
            lower = value.lower()
            for idx, host in enumerate(self.HOST_PRIORITY):
                if host in lower:
                    return idx
            return len(self.HOST_PRIORITY)

        links.sort(key=priority)
        return links

    def _hoster_unavailable_reason(self, embed_url):
        try:
            embed_html = self._make_request(embed_url, referer=self.player_base + "/")
        except Exception:
            embed_html = None
        if not embed_html:
            return ""

        text = re.sub(r"<[^>]+>", " ", embed_html)
        text = re.sub(r"\s+", " ", html.unescape(text)).strip()
        lowered = text.lower()
        unavailable_markers = (
            "file is no longer available",
            "expired or has been deleted",
            "file was deleted",
            "file has been deleted",
            "video has been deleted",
            "video is no longer available",
            "file not found",
            "404 not found",
        )
        if any(marker in lowered for marker in unavailable_markers):
            return text[:180] or "Hoster file is no longer available"
        return ""

    def _profile_path(self):
        try:
            path = xbmcaddon.Addon().getAddonInfo("profile")
            try:
                path = xbmcvfs.translatePath(path)
            except AttributeError:
                path = xbmc.translatePath(path)
            if path and not xbmcvfs.exists(path):
                xbmcvfs.mkdirs(path)
            return path
        except Exception:
            return tempfile.gettempdir()

    def _html_attr(self, tag, name):
        match = re.search(r'\b{}\s*=\s*(["\'])(.*?)\1'.format(re.escape(name)), tag or "", re.IGNORECASE)
        return html.unescape(match.group(2)) if match else ""

    def _is_captcha_page(self, page_html):
        lowered = (page_html or "").lower()
        return "captcha_answer[]" in lowered and "captcha_id" in lowered

    def _write_temp_image(self, filename, content):
        safe_name = re.sub(r"[^a-zA-Z0-9_.-]+", "_", filename or "captcha.jpg")
        path = os.path.join(self._profile_path(), "pornhoarder_{}".format(safe_name))
        try:
            if os.path.exists(path):
                os.remove(path)
        except Exception:
            pass
        with open(path, "wb") as handle:
            handle.write(content)
        return path

    def _remove_temp_files(self, paths):
        for path in paths or []:
            try:
                if path and os.path.exists(path):
                    os.remove(path)
            except Exception:
                pass

    def _extract_captcha(self, page_html, player_url):
        question = "Select the matching images"
        question_match = re.search(
            r'id=["\']captcha-message["\'][^>]*>([\s\S]*?)</span>',
            page_html or "",
            re.IGNORECASE,
        )
        if question_match:
            question = self._clean(question_match.group(1)) or question

        captcha_id = ""
        answer_values = []
        for tag in re.findall(r"<input[^>]+>", page_html or "", re.IGNORECASE):
            name = self._html_attr(tag, "name")
            value = self._html_attr(tag, "value")
            if name == "captcha_id":
                captcha_id = value
            elif name == "captcha_answer[]" and value:
                answer_values.append(value)

        image_sources = re.findall(
            r'<img[^>]+src=(["\'])([^"\']*captcha/testing/[^"\']+)\1',
            page_html or "",
            re.IGNORECASE,
        )
        image_sources = [src for _, src in image_sources]
        if not captcha_id or not answer_values or not image_sources:
            return question, captcha_id, []

        items = []
        temp_files = []
        for idx, (value, image_src) in enumerate(zip(answer_values, image_sources), 1):
            image_url = urllib.parse.urljoin(player_url, html.unescape(image_src))
            try:
                response = self.session.get(image_url, headers=self._headers(player_url), timeout=20)
                if response.status_code != 200 or not response.content:
                    continue
                path = self._write_temp_image("captcha_{}_{}.jpg".format(idx, value), response.content)
                temp_files.append(path)
                items.append({"number": idx, "value": value, "path": path})
            except Exception as exc:
                self.logger.warning("[PornHoarder] Failed to load captcha image %s: %s", image_url, exc)
        return question, captcha_id, items, temp_files

    def _solve_player_captcha(self, page_html, player_url):
        current_html = page_html
        for attempt in range(2):
            extracted = self._extract_captcha(current_html, player_url)
            if len(extracted) == 3:
                question, captcha_id, items = extracted
                temp_files = []
            else:
                question, captcha_id, items, temp_files = extracted

            if not captcha_id or not items:
                self.notify_error("PornHoarder verification required")
                return ""

            window = _PornHoarderCaptchaWindow(question, items)
            try:
                window.doModal()
                if not window.finished:
                    self.notify_error("PornHoarder verification cancelled")
                    return ""
                selected = list(window.selected)
            finally:
                self._remove_temp_files(temp_files)

            if not selected:
                self.notify_error("No verification images selected")
                return ""

            data = [("captcha_id", captcha_id)]
            for value in selected:
                data.append(("captcha_answer[]", value))

            current_html = self._make_request(player_url, referer=player_url, method="POST", data=data)
            if current_html and not self._is_captcha_page(current_html):
                return current_html
            if attempt == 0:
                xbmcgui.Dialog().notification(
                    "PornHoarder",
                    "Verification failed, please try once more",
                    xbmcgui.NOTIFICATION_WARNING,
                    3000,
                )

        self.notify_error("PornHoarder verification failed")
        return ""

    def play_video(self, url):
        video_html = self._make_request(url)
        if not video_html:
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return

        player_url = self._extract_player_url(video_html)
        if not player_url:
            self.notify_error("No PornHoarder player found")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return

        player_html = self._make_request(player_url, referer=url)
        if self._is_captcha_page(player_html):
            player_html = self._solve_player_captcha(player_html, player_url)
        host_links = self._extract_host_links(player_html)
        if not host_links:
            self.logger.info("[PornHoarder] Initial player page had no hoster links, trying play POST")
            player_html = self._make_request(player_url, referer=player_url, method="POST", data={"play": ""})
            if self._is_captcha_page(player_html):
                player_html = self._solve_player_captcha(player_html, player_url)
            host_links = self._extract_host_links(player_html)
        if not host_links:
            self.notify_error("No playable hoster found")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return

        stream_url = None
        stream_headers = {}
        for link in host_links:
            try:
                self.logger.info("[PornHoarder] Trying hoster: %s", link[:100])
                result = resolver.resolve(link, referer=player_url, headers={"User-Agent": self.ua, "Referer": player_url})
                if isinstance(result, tuple):
                    candidate, headers = result
                else:
                    candidate, headers = result, {}
                if candidate and candidate.startswith("http"):
                    stream_url = candidate
                    stream_headers = headers or {}
                    break
            except Exception as exc:
                self.logger.warning("[PornHoarder] Resolver failed for %s: %s", link[:80], exc)

        if not stream_url:
            if any(any(host in link.lower() for host in ("dirtyvideo", "netu", "waaw", "hqq")) for link in host_links):
                self.notify_error("Netu/DirtyVideo has no reachable CDN fallback")
                xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
                return
            if any(any(host in link.lower() for host in ("playmogo", "dood", "dsvplay", "myvidplay")) for link in host_links):
                self.notify_error("Dood/Playmogo blocked or requires verification")
                xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
                return
            for link in host_links:
                reason = self._hoster_unavailable_reason(link)
                if reason:
                    self.logger.warning("[PornHoarder] Hoster unavailable for %s: %s", link[:100], reason)
                    self.notify_error("Hoster file expired or deleted")
                    xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
                    return
            self.notify_error("Could not resolve PornHoarder stream")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return

        proxy_controller = None
        play_url = stream_url
        if ".m3u8" in stream_url:
            try:
                referer = stream_headers.get("Referer") or player_url
                parsed_referer = urllib.parse.urlparse(referer)
                origin = "{}://{}".format(parsed_referer.scheme, parsed_referer.netloc) if parsed_referer.netloc else self.player_base
                referer_host = parsed_referer.netloc.lower()
                if any(host in referer_host for host in ("dirtyvideo", "netu", "waaw", "hqq")):
                    self.logger.info("[PornHoarder] Using direct HLS for Netu/DirtyVideo hoster")
                else:
                    hls_headers = {
                        "User-Agent": stream_headers.get("User-Agent", self.ua),
                        "Referer": referer,
                        "Origin": origin,
                        "Accept": "*/*",
                    }
                    proxy_controller = _PornHoarderHlsProxy(self.hls_session, stream_url, hls_headers)
                    play_url = proxy_controller.start()
            except Exception as exc:
                self.logger.warning("[PornHoarder] HLS proxy failed, using direct URL: %s", exc)

        if "|" not in play_url and stream_headers and play_url == stream_url:
            play_url = play_url + "|" + urllib.parse.urlencode(stream_headers)

        list_item = xbmcgui.ListItem(path=play_url)
        list_item.setProperty("IsPlayable", "true")
        if ".m3u8" in stream_url:
            list_item.setMimeType("application/vnd.apple.mpegurl")
            list_item.setProperty("inputstream", "inputstream.adaptive")
            list_item.setProperty("inputstream.adaptive.manifest_type", "hls")
        else:
            list_item.setMimeType("video/mp4")
        list_item.setContentLookup(False)
        xbmcplugin.setResolvedUrl(self.addon_handle, True, list_item)
        if proxy_controller is not None:
            try:
                from resources.lib.proxy_utils import PlaybackGuard

                PlaybackGuard(xbmc.Player(), xbmc.Monitor(), play_url, proxy_controller).start()
            except Exception as exc:
                self.logger.warning("[PornHoarder] Proxy guard failed: %s", exc)
