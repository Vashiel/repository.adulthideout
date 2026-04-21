# -*- coding: utf-8 -*-
import html
import concurrent.futures
import os
import random
import re
import string
import sys
import threading
import time
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

try:
    addon_path = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    vendor_path = os.path.join(addon_path, "resources", "lib", "vendor")
    if vendor_path not in sys.path:
        sys.path.insert(0, vendor_path)
    import cloudscraper
except Exception:
    cloudscraper = None


class _CamCapsHlsProxy:
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
            server_version = "AHCamCapsHLS/1.0"

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
        self.thread = threading.Thread(target=self.httpd.serve_forever, name="CamCapsHlsProxy", daemon=True)
        self.thread.start()
        xbmc.log("[CamCaps] HLS proxy started: {}".format(self.local_url), xbmc.LOGINFO)
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
        query = urllib.parse.parse_qs(parsed.query)
        upstream_url = query.get("u", [self.upstream_url])[0]
        headers = dict(self.headers)
        range_header = handler.headers.get("Range")
        if range_header:
            headers["Range"] = range_header

        try:
            is_playlist_url = ".m3u8" in upstream_url
            response = self.session.get(
                upstream_url,
                headers=headers,
                stream=is_playlist_url,
                timeout=30,
                allow_redirects=True,
            )
            content_type = response.headers.get("Content-Type", "")
            is_playlist = is_playlist_url or "mpegurl" in content_type.lower()
            body = response.content if is_playlist else None

            handler.send_response(response.status_code)
            if is_playlist:
                handler.send_header("Content-Type", "application/vnd.apple.mpegurl")
            else:
                body = response.content
                for key in ("Content-Type", "Content-Length", "Content-Range", "Accept-Ranges"):
                    value = response.headers.get(key)
                    if value:
                        handler.send_header(key, value)
                if not response.headers.get("Content-Length"):
                    handler.send_header("Content-Length", str(len(body)))
            handler.end_headers()

            if response.status_code not in (200, 206):
                if body:
                    handler.wfile.write(body)
                response.close()
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
                response.close()
                return

            try:
                handler.wfile.write(body)
            except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
                pass
            response.close()
        except Exception as exc:
            xbmc.log("[CamCaps] HLS proxy error for {}: {}".format(upstream_url, exc), xbmc.LOGWARNING)
            try:
                handler.send_error(502, "Proxy error")
            except Exception:
                pass


class CamcapsWebsite(BaseWebsite):
    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="camcaps",
            base_url="https://camcaps.tv",
            search_url="https://camcaps.tv/search/videos/{}",
            addon_handle=addon_handle,
            addon=addon,
        )
        self.session = requests.Session()
        self.embed_session = (
            cloudscraper.create_scraper(browser={"browser": "chrome", "platform": "windows", "desktop": True})
            if cloudscraper else self.session
        )
        self.ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/128.0.0.0 Safari/537.36"
        )
        self.sort_options = [
            "Most Recent",
            "Featured",
            "Most Viewed",
            "Top Rated",
            "Top Favorites",
            "Being Watched",
        ]
        self.sort_paths = {
            "Most Recent": "/videos?o=mr",
            "Featured": "/videos?type=featured",
            "Most Viewed": "/videos?o=mv",
            "Top Rated": "/videos?o=tr",
            "Top Favorites": "/videos?o=tf",
            "Being Watched": "/videos?o=bw",
        }

    def get_start_url_and_label(self):
        label = "Camcaps"
        default_sort = "Most Recent"
        saved_sort_setting = self.addon.getSetting("camcaps_sort_by")

        sort_option = default_sort
        try:
            sort_idx = int(saved_sort_setting)
            if 0 <= sort_idx < len(self.sort_options):
                sort_option = self.sort_options[sort_idx]
        except (ValueError, TypeError):
            if saved_sort_setting in self.sort_options:
                sort_option = saved_sort_setting

        sort_path = self.sort_paths.get(sort_option, self.sort_paths[default_sort])
        url = urllib.parse.urljoin(self.base_url, sort_path)
        final_label = "{} [COLOR yellow]{}[/COLOR]".format(label, sort_option)
        return url, final_label

    def make_request(self, url, referer=None):
        try:
            headers = {
                "User-Agent": self.ua,
                "Referer": referer or (self.base_url + "/"),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            }
            response = self.embed_session.get(url, headers=headers, timeout=30)
            if response.status_code == 200:
                return response.text
            self.logger.error("[CamCaps] HTTP %s for %s", response.status_code, url)
        except Exception as exc:
            self.logger.error("[CamCaps] Request error for %s: %s", url, exc)
        return None

    def make_embed_request(self, url, referer=None):
        try:
            headers = {
                "User-Agent": self.ua,
                "Referer": referer or (self.base_url + "/"),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            }
            response = self.embed_session.get(url, headers=headers, timeout=30)
            if response.status_code == 200:
                return response.text, response.url
            self.logger.error("[CamCaps] Embed HTTP %s for %s", response.status_code, url)
        except Exception as exc:
            self.logger.error("[CamCaps] Embed request error for %s: %s", url, exc)
        return None, None

    def _absolute(self, url):
        if not url:
            return ""
        return urllib.parse.urljoin(self.base_url, html.unescape(url.strip()))

    def _extract_next_url(self, html_content):
        matches = re.findall(r'href="(https://camcaps\.tv/[^"]*page=\d+[^"]*)"', html_content, re.IGNORECASE)
        if not matches:
            return None
        seen = set()
        for candidate in matches:
            if candidate not in seen:
                seen.add(candidate)
                return candidate
        return None

    def _extract_iframe_urls(self, html_content, base_url):
        urls = []
        seen = set()
        for iframe_src in re.findall(r'<iframe[^>]+src=["\']([^"\']+)["\']', html_content or "", re.IGNORECASE):
            iframe_url = html.unescape(iframe_src).strip()
            if iframe_url.startswith("//"):
                iframe_url = "https:" + iframe_url
            iframe_url = urllib.parse.urljoin(base_url, iframe_url)
            parsed = urllib.parse.urlparse(iframe_url)
            host = parsed.netloc.lower()
            path = parsed.path.lower()
            if host == "c.player.camcaps.to" or (host.endswith("player.camcaps.to") and path == "/468.html"):
                continue
            if iframe_url and iframe_url not in seen:
                seen.add(iframe_url)
                urls.append(iframe_url)
        return urls

    def _rank_embed_candidate(self, embed_url):
        host = urllib.parse.urlparse(embed_url).netloc.lower()
        if "luluvdo" in host or "lulu" in host:
            return 0
        if "clicknplay" in host:
            return 1
        if "vtube" in host or "vtplayer" in host or "lvturbo" in host:
            return 2
        if "player.camcaps.to" in host:
            return 3
        if "camcaps.tv" in host:
            return 8
        if "vidello.net" in host or "playmogo" in host:
            return 9
        return 4

    def _extract_videos(self, html_content):
        listing_html = html_content
        listing_start = html_content.find('<div class="well-info">')
        if listing_start >= 0:
            listing_end = html_content.find('<ul class="pagination"', listing_start)
            listing_html = html_content[listing_start:listing_end if listing_end > listing_start else len(html_content)]

        blocks = re.findall(
            r'(<a href="/video/\d+/[^"]+".*?<span class="content-title">.*?</span>.*?</div>\s*</div>\s*</div>)',
            listing_html,
            re.IGNORECASE | re.DOTALL,
        )
        videos = []
        seen = set()

        for block in blocks:
            url_match = re.search(r'<a href="(/video/\d+/[^"]+)"', block, re.IGNORECASE)
            title_match = re.search(r'<span class="content-title">\s*(.*?)\s*</span>', block, re.IGNORECASE | re.DOTALL)
            thumb_match = re.search(r'<img src="([^"]+)"[^>]+class="img-responsive', block, re.IGNORECASE)
            duration_match = re.search(r'<div class="duration">\s*([0-9:]+)\s*</div>', block, re.IGNORECASE)
            views_match = re.search(r'<span class="content-views">\s*([^<]+)', block, re.IGNORECASE)

            if not url_match or not title_match:
                continue

            video_url = self._absolute(url_match.group(1))
            if video_url in seen:
                continue
            seen.add(video_url)

            title = re.sub(r"\s+", " ", html.unescape(title_match.group(1))).strip()
            thumb = self._absolute(thumb_match.group(1)) if thumb_match else self.icon
            duration = duration_match.group(1).strip() if duration_match else ""
            views = re.sub(r"\s+", " ", views_match.group(1)).strip() if views_match else ""

            info = {"title": title, "plot": title}
            if views:
                info["plot"] = "{} | {}".format(title, views)
            duration_seconds = self.convert_duration(duration)
            if duration_seconds:
                info["duration"] = duration_seconds

            videos.append(
                {
                    "title": title,
                    "url": video_url,
                    "thumb": thumb,
                    "info": info,
                }
            )

        return videos

    def _extract_video_embeds_for_listing(self, video_url, referer):
        try:
            headers = {
                "User-Agent": self.ua,
                "Referer": referer or self.base_url + "/",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            }
            response = self.embed_session.get(video_url, headers=headers, timeout=8)
            if response.status_code != 200:
                return []
            embeds = self._extract_iframe_urls(response.text, video_url)
            embeds.sort(key=self._rank_embed_candidate)
            return embeds
        except Exception:
            return []

    def _is_unplayable_embed_only_entry(self, video_url, referer):
        embeds = self._extract_video_embeds_for_listing(video_url, referer)
        if not embeds:
            return False

        real_hosts = []
        for embed_url in embeds:
            parsed = urllib.parse.urlparse(embed_url)
            host = parsed.netloc.lower()
            if host.endswith("camcaps.tv") and parsed.path.startswith("/embed/"):
                continue
            real_hosts.append(host)

        if not real_hosts:
            return False
        return all(
            (
                "vtube.to" in host
                or "vtplayer" in host
                or "lvturbo" in host
                or "vidello.net" in host
                or "playmogo" in host
            )
            for host in real_hosts
        )

    def _filter_unplayable_embed_only_videos(self, videos, referer):
        if not videos:
            return []

        def check_video(video):
            try:
                if self._is_unplayable_embed_only_entry(video["url"], referer):
                    self.logger.info("[CamCaps] Hiding unsupported host-only entry: %s", video["url"])
                    return None
            except Exception as exc:
                self.logger.info("[CamCaps] Listing host check failed for %s: %s", video["url"], exc)
            return video

        filtered = []
        max_workers = min(8, len(videos))
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            for result in executor.map(check_video, videos):
                if result:
                    filtered.append(result)
        return filtered

    def process_content(self, url):
        if not url or url == "BOOTSTRAP" or url.rstrip("/") == self.base_url.rstrip("/"):
            url, _ = self.get_start_url_and_label()

        self.add_dir("Search", "", 5, self.icons.get("search", self.icon))
        self.add_dir("Categories", urllib.parse.urljoin(self.base_url, "/categories"), 8, self.icons.get("categories", self.icon))
        self.add_dir("Performers", urllib.parse.urljoin(self.base_url, "/users"), 9, self.icons.get("pornstars", self.icon))

        html_content = self.make_request(url)
        if not html_content:
            self.end_directory("videos")
            return

        videos = self._extract_videos(html_content)
        if not videos:
            self.notify_error("No CamCaps videos found")
            self.end_directory("videos")
            return

        for video in videos:
            self.add_link(
                video["title"],
                video["url"],
                4,
                video["thumb"],
                self.fanart,
                info_labels=video["info"],
            )

        next_url = self._extract_next_url(html_content)
        if next_url and next_url != url:
            self.add_dir("Next Page", next_url, 2, self.icons.get("default", self.icon))

        self.end_directory("videos")

    def process_categories(self, url):
        html_content = self.make_request(url or urllib.parse.urljoin(self.base_url, "/categories"))
        if not html_content:
            self.end_directory("videos")
            return

        seen = set()
        for href, label in re.findall(
            r'<a class="tagHover" href="(/search/videos/[^"]+)"[^>]*>(?:<i[^>]*></i>)?\s*([^<]+)\s*</a>',
            html_content,
            re.IGNORECASE | re.DOTALL,
        ):
            category_url = self._absolute(href)
            if category_url in seen:
                continue
            seen.add(category_url)
            title = re.sub(r"\s+", " ", html.unescape(label)).strip()
            self.add_dir(title, category_url, 2, self.icons.get("categories", self.icon))

        self.end_directory("videos")

    def process_pornstars(self, url):
        html_content = self.make_request(url or urllib.parse.urljoin(self.base_url, "/users"))
        if not html_content:
            self.end_directory("videos")
            return

        seen = set()
        matches = re.findall(
            r'<a href="(/user/[^"]+)">\s*<div class="thumb-overlay">\s*<img src="([^"]+)"[^>]*>\s*</div>\s*</a>\s*<div class="content-info">\s*<a href="/user/[^"]+">\s*<span class="content-truncate\s*">\s*([^<]+)\s*</span>',
            html_content,
            re.IGNORECASE | re.DOTALL,
        )
        for href, thumb_src, name_raw in matches:
            profile_url = self._absolute(href.rstrip("/") + "/videos")
            if profile_url in seen:
                continue
            seen.add(profile_url)

            name = html.unescape(name_raw).strip()
            thumb = self._absolute(thumb_src) if thumb_src else self.icons.get("pornstars", self.icon)
            self.add_dir(name, profile_url, 2, thumb, self.fanart)

        next_url = self._extract_next_url(html_content)
        if next_url and next_url != url:
            self.add_dir("Next Page", next_url, 9, self.icons.get("default", self.icon))

        self.end_directory("videos")

    def search(self, query):
        if not query:
            return
        search_url = self.search_url.format(urllib.parse.quote(query.strip()))
        self.process_content(search_url)

    def _unpack_packer(self, packed_text):
        match = re.search(
            r"eval\(function\(p,a,c,k,e,d\)\{while\(c--\)if\(k\[c\]\)p=p\.replace\(new RegExp\('\\\\b'\+c\.toString\(a\)\+'\\\\b','g'\),k\[c\]\);return p\}\('(.*?)',(\d+),(\d+),'(.*?)'\.split\('\|'\)\)\)",
            packed_text,
            re.IGNORECASE | re.DOTALL,
        )
        if not match:
            return ""

        payload, base, count, words = match.groups()
        base = int(base)
        count = int(count)
        words = words.split("|")
        payload = payload.encode("utf-8").decode("unicode_escape")

        def to_base36(number, radix):
            chars = "0123456789abcdefghijklmnopqrstuvwxyz"
            if number == 0:
                return "0"
            result = ""
            while number:
                result = chars[number % radix] + result
                number //= radix
            return result

        unpacked = payload
        for idx in range(count - 1, -1, -1):
            if idx < len(words) and words[idx]:
                unpacked = re.sub(r"\b" + re.escape(to_base36(idx, base)) + r"\b", words[idx], unpacked)
        return unpacked

    def _complete_playmogo_url(self, base_url, embed_html, pass_url):
        if "makePlay" not in embed_html:
            return base_url

        token_match = re.search(r"\?token=([^\"'&]+)&expiry=", embed_html, re.IGNORECASE)
        token = html.unescape(token_match.group(1)).strip() if token_match else ""
        if not token:
            token = urllib.parse.urlparse(pass_url).path.rstrip("/").split("/")[-1]
        if not token:
            return base_url

        alphabet = string.ascii_letters + string.digits
        random_part = "".join(random.choice(alphabet) for _ in range(10))
        return "{}{}?token={}&expiry={}".format(
            base_url,
            random_part,
            urllib.parse.quote(token, safe=""),
            int(time.time() * 1000),
        )

    def _is_generic_playmogo_embed(self, embed_url, embed_html):
        parsed = urllib.parse.urlparse(embed_url)
        if parsed.netloc.lower().endswith("playmogo.com") and parsed.path.rstrip("/") == "/e/92e84a3j1r58":
            return True
        if "0i44255hq4mjbgd3ezm4n source" in embed_html:
            return True
        return False

    def _extract_hls_from_embed(self, embed_url, referer, visited=None, depth=0):
        visited = visited or set()
        if not embed_url or embed_url in visited or depth >= 4:
            return None, None
        visited.add(embed_url)

        host = urllib.parse.urlparse(embed_url).netloc.lower()
        if (
            "dood" in host
            or "dsvplay" in host
            or "myvidplay" in host
            or "vtube" in host
            or "vtplay" in host
            or "vtbe" in host
            or "vidello.net" in host
            or "playmogo" in host
        ):
            try:
                from resources.lib.resolvers import resolver

                resolved_url, resolved_headers = resolver.resolve(
                    embed_url,
                    referer=referer,
                    headers={"User-Agent": self.ua},
                )
                if resolved_url:
                    if "|" in resolved_url:
                        resolved_url = resolved_url.split("|", 1)[0]
                    resolved_referer = (resolved_headers or {}).get("Referer") or embed_url
                    return resolved_url, resolved_referer
            except Exception as exc:
                self.logger.warning("[CamCaps] Dood resolver failed for %s: %s", embed_url, exc)

        embed_html, final_embed_url = self.make_embed_request(embed_url, referer=referer)
        if not embed_html:
            return None, None
        embed_url = final_embed_url or embed_url
        if self._is_generic_playmogo_embed(embed_url, embed_html):
            self.logger.info("[CamCaps] Skipping generic Playmogo/Vidello source for %s", embed_url)
            return None, None

        pass_match = re.search(
            r"\$\.get\('([^']+)'[^)]*function\(data\).*?src\s*:\s*data",
            embed_html,
            re.IGNORECASE | re.DOTALL,
        )
        if pass_match:
            pass_url = urllib.parse.urljoin(embed_url, html.unescape(pass_match.group(1)))
            try:
                response = self.embed_session.get(
                    pass_url,
                    headers={
                        "User-Agent": self.ua,
                        "Referer": embed_url,
                        "X-Requested-With": "XMLHttpRequest",
                    },
                    timeout=20,
                )
                if response.status_code == 200 and response.text.strip().startswith("http"):
                    stream_url = self._complete_playmogo_url(response.text.strip(), embed_html, pass_url)
                    return stream_url, embed_url
                self.logger.error("[CamCaps] pass_md5 HTTP %s for %s", response.status_code, pass_url)
            except Exception as exc:
                self.logger.error("[CamCaps] pass_md5 error for %s: %s", pass_url, exc)

        for nested_url in self._extract_iframe_urls(embed_html, embed_url):
            if nested_url == embed_url:
                continue
            stream_url, stream_referer = self._extract_hls_from_embed(
                nested_url,
                referer=embed_url,
                visited=visited,
                depth=depth + 1,
            )
            if stream_url:
                return stream_url, stream_referer

        for pattern in (
            r'<source[^>]+src="([^"]+\.(?:m3u8|mp4)[^"]*)"',
            r'https?://[^"\']+\.(?:m3u8|mp4)[^"\']*',
        ):
            match = re.search(pattern, embed_html, re.IGNORECASE)
            if match:
                stream_url = match.group(1) if match.groups() else match.group(0)
                return html.unescape(stream_url).strip(), embed_url

        unpacked = self._unpack_packer(embed_html)
        if not unpacked:
            return None, None

        for pattern in (
            r'src:"([^"]+master\.m3u8[^"]*)"',
            r'file:"([^"]+\.mp4[^"]*)"',
            r"file:'([^']+\.mp4[^']*)'",
            r'https?://[^"\']+\.m3u8[^"\']*',
            r'https?://[^"\']+\.mp4[^"\']*',
        ):
            match = re.search(pattern, unpacked, re.IGNORECASE)
            if match:
                stream_url = match.group(1) if match.groups() else match.group(0)
                return html.unescape(stream_url).strip(), embed_url

        return None, None

    def play_video(self, url):
        html_content = self.make_request(url, referer=self.base_url + "/")
        if not html_content:
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return

        candidates = []
        seen_candidates = set()

        def add_candidate(candidate):
            if candidate and candidate not in seen_candidates:
                seen_candidates.add(candidate)
                candidates.append(candidate)

        for iframe_url in self._extract_iframe_urls(html_content, url):
            add_candidate(iframe_url)

        for candidate in list(candidates):
            parsed = urllib.parse.urlparse(candidate)
            if parsed.netloc.lower().endswith("camcaps.tv") and parsed.path.startswith("/embed/"):
                camcaps_embed_html = self.make_request(candidate, referer=url)
                for nested_url in self._extract_iframe_urls(camcaps_embed_html, candidate):
                    add_candidate(nested_url)

        candidates.sort(key=self._rank_embed_candidate)
        if not candidates:
            self.notify_error("No CamCaps stream embed found")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return

        stream_url = None
        stream_referer = None
        for embed_url in candidates:
            stream_url, stream_referer = self._extract_hls_from_embed(embed_url, url)
            if stream_url:
                break

        if not stream_url:
            self.notify_error("No CamCaps stream found")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return

        origin = "{}://{}".format(urllib.parse.urlparse(stream_referer).scheme, urllib.parse.urlparse(stream_referer).netloc)
        headers = {
            "User-Agent": self.ua,
            "Referer": stream_referer,
            "Origin": origin,
            "Accept": "*/*",
        }
        proxy_controller = None
        playback_url = stream_url
        if ".m3u8" in stream_url:
            try:
                proxy_controller = _CamCapsHlsProxy(self.embed_session, stream_url, headers)
                playback_url = proxy_controller.start()
            except Exception as exc:
                self.logger.warning("[CamCaps] HLS proxy failed, using direct URL: %s", exc)
                playback_url = stream_url + "|" + "&".join(
                    "{}={}".format(
                        urllib.parse.quote(str(key), safe=""),
                        urllib.parse.quote(str(value), safe=""),
                    )
                    for key, value in headers.items()
                )
        else:
            stream_host = urllib.parse.urlparse(stream_url).netloc.lower()
            if "clicknplay" in stream_host:
                try:
                    from resources.lib.proxy_utils import ProxyController

                    proxy_controller = ProxyController(
                        stream_url,
                        upstream_headers=headers,
                        skip_resolve=True,
                        use_urllib=True,
                        probe_size=False,
                    )
                    playback_url = proxy_controller.start()
                except Exception as exc:
                    self.logger.warning("[CamCaps] Clicknplay proxy failed, using direct URL: %s", exc)
                    playback_url = stream_url + "|" + "&".join(
                        "{}={}".format(
                            urllib.parse.quote(str(key), safe=""),
                            urllib.parse.quote(str(value), safe=""),
                        )
                        for key, value in headers.items()
                    )
            else:
                playback_url = stream_url + "|" + "&".join(
                    "{}={}".format(
                        urllib.parse.quote(str(key), safe=""),
                        urllib.parse.quote(str(value), safe=""),
                    )
                    for key, value in headers.items()
                )

        list_item = xbmcgui.ListItem(path=playback_url)
        list_item.setProperty("IsPlayable", "true")
        list_item.setMimeType("application/vnd.apple.mpegurl" if ".m3u8" in stream_url else "video/mp4")
        if ".m3u8" in stream_url:
            list_item.setProperty("inputstream", "inputstream.adaptive")
            list_item.setProperty("inputstream.adaptive.manifest_type", "hls")
        list_item.setContentLookup(False)
        xbmcplugin.setResolvedUrl(self.addon_handle, True, list_item)
        if proxy_controller is not None:
            try:
                from resources.lib.proxy_utils import PlaybackGuard

                PlaybackGuard(xbmc.Player(), xbmc.Monitor(), playback_url, proxy_controller).start()
            except Exception as exc:
                self.logger.warning("[CamCaps] Proxy guard failed: %s", exc)
