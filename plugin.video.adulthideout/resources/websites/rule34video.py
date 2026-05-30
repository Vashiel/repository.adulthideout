#!/usr/bin/env python

import re
import sys
import urllib.parse
import html
import threading
import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon
import os
import json
from http.server import BaseHTTPRequestHandler, HTTPServer

try:
    from http.server import ThreadingHTTPServer
except ImportError:
    import socketserver

    class ThreadingHTTPServer(socketserver.ThreadingMixIn, HTTPServer):
        daemon_threads = True

try:
    addon_path = xbmcaddon.Addon().getAddonInfo('path')
    vendor_path = os.path.join(addon_path, 'resources', 'lib', 'vendor')
    if vendor_path not in sys.path:
        sys.path.insert(0, vendor_path)
except Exception as e:
    xbmc.log(f"[AdultHideout] Vendor path inject failed in rule34video.py: {e}", xbmc.LOGERROR)

try:
    import cloudscraper
    _HAS_CF = True
except Exception as e:
    xbmc.log(f"[Rule34video] cloudscraper import failed: {e}", xbmc.LOGERROR)
    _HAS_CF = False

from resources.lib.base_website import BaseWebsite
from resources.lib.lookup_info import choose_and_open, extract_html_items

_SESSION_CACHE = None
_SESSION_LOCK = threading.Lock()
_ACTIVE_PROXIES = []


class _Rule34VideoRangeProxy:
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
            server_version = "AHRule34VideoRange/1.0"

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
        self.thread = threading.Thread(target=self.httpd.serve_forever, name="Rule34VideoRangeProxy", daemon=True)
        self.thread.start()
        xbmc.log("[Rule34video] Range proxy started: {}".format(self.local_url), xbmc.LOGINFO)
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
            xbmc.log("[Rule34video] Range proxy error: {}".format(exc), xbmc.LOGERROR)
            try:
                handler.send_response(502)
                handler.end_headers()
            except Exception:
                pass
        finally:
            if response is not None:
                response.close()

class Rule34video(BaseWebsite):
    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name='rule34video',
            base_url='https://rule34video.com',
            search_url='https://rule34video.com/search/{}/',
            addon_handle=addon_handle,
            addon=addon
        )
        self.display_name = 'Rule34video'
        self.sort_options = ['Newest', 'Most Viewed', 'Top Rated', 'Longest', 'Random']
        self.content_options = ['All', 'Straight', 'Gay', 'Futa']
        self.setting_id_sort = "rule34video_sort_order"
        self.setting_id_content = "rule34video_content_type"
        
        self.content_params = {
            'All': None,
            'Straight': '2109',
            'Gay': '192',
            'Futa': '15' 
        }
        
        self.scraper = None
        self._scraper_ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/126.0.0.0 Safari/537.36"
        )
        self.timeout = 45

    def get_session(self):
        global _SESSION_CACHE, _SESSION_LOCK
        with _SESSION_LOCK:
            if self.scraper:
                return self.scraper
            
            if _SESSION_CACHE:
                self.logger.info(f"[{self.name}] Reusing cached Cloudscraper session.")
                self.scraper = _SESSION_CACHE
                return self.scraper

            self.logger.info(f"[{self.name}] Initializing new Cloudscraper object...")
            if not _HAS_CF:
                self.notify_error("Cloudscraper library missing.")
                return None

            try:
                scraper = cloudscraper.create_scraper(browser={'custom': self._scraper_ua}, delay=10)
                scraper.headers.update({
                    'User-Agent': self._scraper_ua,
                    'Referer': self.base_url,
                    'Accept-Language': 'en-US,en;q=0.9',
                })
                self.scraper = scraper
                _SESSION_CACHE = scraper
                return self.scraper
            except Exception as e:
                self.logger.error(f"[{self.name}] Failed to create scraper: {e}")
                return None

    def make_request(self, url, referer=None):
        scraper = self.get_session()
        if not scraper: return None
        try:
            headers = scraper.headers.copy()
            if referer: headers['Referer'] = referer
            resp = scraper.get(url, headers=headers, timeout=self.timeout)
            resp.raise_for_status()
            return resp.text
        except Exception as e:
            self.logger.error(f"Request failed for {url}: {e}")
            return None

    def _get_start_url(self):
        try:
            sort_idx = int(self.addon.getSetting(self.setting_id_sort))
            sort_key = self.sort_options[sort_idx]
        except:
            sort_key = 'Newest'
            
        try:
            content_idx = int(self.addon.getSetting(self.setting_id_content))
            content_key = self.content_options[content_idx]
        except:
            content_key = 'All'

        tag_id = self.content_params.get(content_key)
        if tag_id:
            base = f"/tags/{tag_id}/"
        else:
            base = "/latest-updates/"

        sort_map = {
            'Newest': 'post_date',
            'Most Viewed': 'video_viewed',
            'Top Rated': 'rating',
            'Longest': 'duration',
            'Random': 'pseudo_rand'
        }
        sort_val = sort_map.get(sort_key, 'post_date')
        
        url = urllib.parse.urljoin(self.base_url, base)
        url += f"?sort_by={sort_val}"
        
        return url

    def get_start_url_and_label(self):
        try:
            s_idx = int(self.addon.getSetting(self.setting_id_sort))
            c_idx = int(self.addon.getSetting(self.setting_id_content))
            label = f"{self.display_name} [COLOR yellow]({self.content_options[c_idx]} - {self.sort_options[s_idx]})[/COLOR]"
        except:
            label = self.display_name
        return self._get_start_url(), label

    def process_content(self, url):
        if not url: url = self._get_start_url()
        
        html_content = self.make_request(url)
        if not html_content:
            self.end_directory()
            return

        self.add_dir('[COLOR blue]Search[/COLOR]', '', 5, self.icons['search'], name_param=self.name)
        self.add_dir('[COLOR blue]Categories[/COLOR]', urllib.parse.urljoin(self.base_url, '/categories/'), 8, self.icons['categories'])

        video_pattern = re.compile(
            r'<div\s+class="item\s+thumb[^"]*"[^>]*>.*?'
            r'<a\s+class="[^"]*\bth\b[^"]*"[^>]+href="(?P<url>[^"]+)"[^>]*title="(?P<title>[^"]+)".*?'
            r'<img[^>]+(?:data-original|data-src|src)="(?P<thumb>[^"]+)".*?'
            r'<div\s+class="time">\s*(?P<duration>[^<]+)\s*</div>',
            re.DOTALL | re.IGNORECASE
        )

        found = False
        for match in video_pattern.finditer(html_content):
            found = True
            v_url = match.group('url')
            title = html.unescape(match.group('title').strip())
            thumb = match.group('thumb')
            duration = match.group('duration').strip()
            
            full_url = urllib.parse.urljoin(self.base_url, v_url)
            
            cm = [
                ('Explore similar', f'RunPlugin({sys.argv[0]}?mode=7&action=explore_similar&website={self.name}&original_url={urllib.parse.quote_plus(full_url)})'),
                ('Select Content...', f'RunPlugin({sys.argv[0]}?mode=7&action=select_content_type&website={self.name})'),
                ('Sort by...', f'RunPlugin({sys.argv[0]}?mode=7&action=select_sort_order&website={self.name})')
            ]
            
            info = {'title': title, 'duration': self._duration_to_seconds(duration), 'plot': title}
            self.add_link(f"{title} [COLOR yellow]({duration})[/COLOR]", full_url, 4, thumb, self.fanart, info_labels=info, context_menu=cm)

        if not found:
            self.logger.warning(f"[{self.name}] No videos found on {url}")

        next_match = re.search(r'<div\s+class="item\s+pager\s+next">\s*<a\s+href="(?P<next>[^"]+)"', html_content, re.IGNORECASE)
        if next_match:
            next_link = self._normalize_next_url(next_match.group('next'))
            self.add_dir('[COLOR yellow]Next Page >>[/COLOR]', next_link, 2, self.icons['default'])

        self.end_directory()

    def _normalize_next_url(self, next_url):
        next_link = urllib.parse.urljoin(self.base_url, html.unescape(next_url or ""))
        parsed = urllib.parse.urlparse(next_link)
        path = re.sub(r'/(latest-updates)/\1/', r'/\1/', parsed.path)
        return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, path, parsed.params, parsed.query, parsed.fragment))

    def process_categories(self, url):
        html_content = self.make_request(url)
        if not html_content:
            self.end_directory()
            return

        cat_pattern = re.compile(
            r'<a href="(?P<url>[^"]+)" class="item">\s*'
            r'.*?<img src="(?P<thumb>[^"]+)".*?'
            r'<div class="name">\s*(?P<title>[^<\n]+)',
            re.DOTALL | re.IGNORECASE
        )

        for match in cat_pattern.finditer(html_content):
            c_url = urllib.parse.urljoin(self.base_url, match.group('url'))
            thumb = match.group('thumb')
            title = html.unescape(match.group('title').strip())
            
            if "All Categories" in title: continue
            
            self.add_dir(title, c_url, 2, thumb, self.fanart)
            
        self.end_directory()

    def play_video(self, url):
        self.logger.info(f"[{self.name}] Resolving video: {url}")
        html_content = self.make_request(url)
        if not html_content:
            self.notify_error("Failed to load video page")
            return

        video_url = None
        
        mp4_matches = re.findall(r'["\'](https?://[^"\']+\.mp4[^"\']*)["\']', html_content)
        
        candidates = []
        for m in mp4_matches:
            if 'preview' in m: continue
            if 'get_file' in m: # KVS Secure link pattern
                candidates.append(m)
        
        if candidates:
            video_url = self._select_best_stream(candidates)
        elif mp4_matches:
            video_url = self._select_best_stream(mp4_matches)

        if video_url:
            video_url = video_url.replace(r'\/', '/')
            self.logger.info(f"[{self.name}] Found video URL: {video_url}")

            scraper = self.get_session()
            headers = {
                "User-Agent": self._scraper_ua,
                "Referer": url,
                "Accept": "*/*",
                "Connection": "close",
            }
            cookie_header = "; ".join(
                "{}={}".format(cookie.name, cookie.value) for cookie in getattr(scraper, "cookies", [])
            )
            if cookie_header:
                headers["Cookie"] = cookie_header
            proxy = _Rule34VideoRangeProxy(scraper, video_url, headers)
            play_url = proxy.start()
            _ACTIVE_PROXIES.append(proxy)
            del _ACTIVE_PROXIES[:-4]

            li = xbmcgui.ListItem(path=play_url)
            li.setProperty('IsPlayable', 'true')
            li.setMimeType('video/mp4')
            li.setContentLookup(False)
            xbmcplugin.setResolvedUrl(self.addon_handle, True, li)
        else:
            self.logger.error(f"[{self.name}] No video URL found in source.")
            self.notify_error("Video extraction failed")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())

    def _select_best_stream(self, urls):
        unique = []
        for stream_url in urls:
            stream_url = stream_url.replace(r'\/', '/')
            if stream_url not in unique:
                unique.append(stream_url)

        def score(stream_url):
            quality_score = 0
            quality_match = re.search(r'_(\d{3,4})p?\.mp4', stream_url)
            if quality_match:
                try:
                    quality_score = int(quality_match.group(1))
                except Exception:
                    quality_score = 0
            token_score = 10000 if 'v-acctoken=' in stream_url else 0
            download_penalty = -5000 if 'download=true' in stream_url else 0
            return token_score + quality_score + download_penalty

        if not unique:
            return None
        return sorted(unique, key=score, reverse=True)[0]

    def explore_similar(self, original_url=None):
        if not original_url:
            self.notify_info("No video URL available")
            return

        html_content = self.make_request(original_url)
        if not html_content:
            self.notify_error("Could not load video info")
            return

        patterns = [
            ("Artist", r'video_meta_pill"\s+href="(?:https://rule34video\.com)?(/models/[^"]+)">.+?alt="([^"]+)"', 2),
            ("Category", r'video_meta_pill"\s+href="(?:https://rule34video\.com)?(/categories/[^"]+)">.+?alt="([^"]+)"', 2),
            ("Uploader", r'video_meta_pill"\s+href="(?:https://rule34video\.com)?(/members/[^"]+)">.+?alt="([^"]+)"', 2),
            ("Tag", r'class="tag_item"\s+href="(?:https://rule34video\.com)?(/tags/[^"]+)">([^<]+)<', 2),
        ]
        items = extract_html_items(html_content, self.base_url, patterns)
        if not choose_and_open(items, self.name, "Explore similar"):
            self.logger.info("[rule34video] No lookup target selected for {}".format(original_url))

    def _duration_to_seconds(self, duration_str):
        try:
            parts = list(map(int, duration_str.split(':')))
            if len(parts) == 2:
                return parts[0] * 60 + parts[1]
            elif len(parts) == 3:
                return parts[0] * 3600 + parts[1] * 60 + parts[2]
        except:
            pass
        return 0

    def select_content_type(self, original_url=None):
        try:
            current_idx = int(self.addon.getSetting(self.setting_id_content) or 0)
        except: current_idx = 0
        
        dialog = xbmcgui.Dialog()
        idx = dialog.select("Select Content...", self.content_options, preselect=current_idx)
        if idx > -1:
            self.addon.setSetting(self.setting_id_content, str(idx))
            new_url, _ = self.get_start_url_and_label()
            xbmc.executebuiltin(f"Container.Update({sys.argv[0]}?mode=2&url={urllib.parse.quote_plus(new_url)}&website={self.name},replace)")

    def select_sort_order(self, original_url=None):
        try:
            current_idx = int(self.addon.getSetting(self.setting_id_sort) or 0)
        except: current_idx = 0
        
        dialog = xbmcgui.Dialog()
        idx = dialog.select("Sort by...", self.sort_options, preselect=current_idx)
        if idx > -1:
            self.addon.setSetting(self.setting_id_sort, str(idx))
            new_url, _ = self.get_start_url_and_label()
            xbmc.executebuiltin(f"Container.Update({sys.argv[0]}?mode=2&url={urllib.parse.quote_plus(new_url)}&website={self.name},replace)")
