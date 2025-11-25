#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os
import re
import html
import urllib.parse
import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon

# === START PROXY IMPORTS ===
import threading
# === ENDE PROXY IMPORTS ===

try:
    addon_path = xbmcaddon.Addon().getAddonInfo('path')
    vendor_path = os.path.join(addon_path, 'resources', 'lib', 'vendor')
    if vendor_path not in sys.path:
        sys.path.insert(0, vendor_path)
except Exception as e:
    xbmc.log(f"[AdultHideout] Vendor path inject failed in punishworld.py: {e}", xbmc.LOGERROR)

try:
    import cloudscraper
    _HAS_CF = True
except Exception as e:
    xbmc.log(f"[PunishWorld] cloudscraper import failed: {e}", xbmc.LOGERROR)
    _HAS_CF = False

import requests
from resources.lib.base_website import BaseWebsite
# === NEUER PROXY-IMPORT ===
from resources.lib.proxy_utils import ProxyController, PlaybackGuard

# === SESSION CACHE ===
_SESSION_CACHE = None
_SESSION_LOCK = threading.Lock()
# =====================


class PunishWorld(BaseWebsite):

    def __init__(self, addon_handle):
        super().__init__(
            name="punishworld",
            base_url="https://punishworld.com",
            search_url="https://punishworld.com/?s={}",
            addon_handle=addon_handle
        )
        self.label = 'PunishWorld'
        self._scraper_ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/126.0.0.0 Safari/537.36"
        )
        
        self.scraper = None

        self.sort_options = ["Newest", "Most viewed", "Best", "Longest"]
        self.sort_paths = {
            "Newest": "/?filter=latest",
            "Most viewed": "/?filter=most-viewed",
            "Best": "/?filter=popular",
            "Longest": "/?filter=longest"
        }

    def get_session(self):
        """
        Holt die Cloudscraper-Sitzung. Verwendet einen globalen Cache,
        um die Sitzung über mehrere Kodi-Skriptaufrufe hinweg wiederzuverwenden.
        """
        global _SESSION_CACHE, _SESSION_LOCK
        
        # 1. Lock holen, um Thread-sicher zu sein
        with _SESSION_LOCK:
            # 2. Prüfen, ob diese Instanz bereits eine Sitzung hat
            if self.scraper:
                return self.scraper
            
            # 3. Prüfen, ob eine global gecachte Sitzung existiert
            if _SESSION_CACHE:
                self.logger.info(f"[{self.name}] Reusing cached Cloudscraper session.")
                self.scraper = _SESSION_CACHE
                return self.scraper

            # 4. Neue Sitzung erstellen
            self.logger.info(f"[{self.name}] Initializing new Cloudscraper session...")
            
            if not _HAS_CF:
                self.logger.error(f"[{self.name}] Cloudscraper library is not available.")
                self.notify_error("Cloudscraper library missing.")
                
                class _NoCF:
                    def get(self, *a, **kw): raise RuntimeError("cloudscraper not available")
                    def head(self, *a, **kw): raise RuntimeError("cloudscraper not available")
                    @property
                    def cookies(self): from requests.cookies import RequestsCookieJar; return RequestsCookieJar()
                self.scraper = _NoCF()
                return self.scraper

            try:
                scraper = cloudscraper.create_scraper(
                    browser={'custom': self._scraper_ua},
                    delay=5
                )
                scraper.headers.update({
                    'User-Agent': self._scraper_ua,
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Connection': 'keep-alive',
                })

                # 5. Sitzung in der Instanz UND im globalen Cache speichern
                self.scraper = scraper 
                _SESSION_CACHE = scraper
                return self.scraper
                
            except Exception as e:
                self.logger.error(f"[{self.name}] Failed to create scraper session: {e}")
                self.notify_error(f"Failed to start session: {e}")
                
                class _NoCF:
                    def get(self, *a, **kw): raise RuntimeError(f"Scraper init failed: {e}")
                    def head(self, *a, **kw): raise RuntimeError(f"Scraper init failed: {e}")
                    @property
                    def cookies(self): from requests.cookies import RequestsCookieJar; return RequestsCookieJar()
                self.scraper = _NoCF()
                return self.scraper

    def make_request(self, url, referer=None):
        scraper = self.get_session()
        
        if not hasattr(scraper, 'get'):
            self.notify_error("Cloudscraper session is not valid.")
            return None
            
        try:
            headers = {}
            if referer:
                headers['Referer'] = referer
            
            self.logger.info(f"[{self.name}] Making request to {url} (may be slow if first run)...")
            resp = scraper.get(url, headers=headers, timeout=20)

            if resp.status_code == 404:
                self.logger.error(f"Request failed for {url}: 404 Not Found")
                self.notify_error("This link appears to be broken (404).")
                return None

            resp.raise_for_status()
            content = resp.content.decode('utf-8', 'ignore')

            if "Just a moment..." in content or "cf-browser-verification" in content:
                self.logger.error("Cloudflare block detected.")
                self.notify_error("Cloudflare block detected.")
                return None

            return content
        except Exception as e:
            self.logger.error(f"Failed to load data from {url}: {e}")
            self.notify_error(f"Failed to load data: {e}")
            return None

    def _preflight_stream(self, stream_url, page_url):
        scraper = self.get_session()
        if not hasattr(scraper, 'get'):
             return {'Referer': page_url} 
             
        headers = {'Referer': page_url, 'User-Agent': self._scraper_ua, 'Range': 'bytes=0-1'}
        try:
            self.logger.debug(f"Starting Preflight GET to {stream_url} (this may take 20s)...")
            with scraper.get(stream_url, headers=headers, allow_redirects=True, stream=True, timeout=30) as r:
                r.raise_for_status()
                _ = r.content[:1]
                if r.status_code in (200, 206):
                    return {'Referer': page_url, 'User-Agent': self._scraper_ua}
        except Exception as e:
            self.logger.error(f"Preflight GET failed: {e}")
        self.logger.error("All preflight checks failed.")
        return None

    def process_content(self, url):
        content = self.make_request(url)
        if not content:
            self.end_directory()
            return

        self.add_dir('[COLOR blue]Search[/COLOR]', '', 5, self.icons['search'], name_param=self.name)
        self.add_dir('[COLOR blue]Categories[/COLOR]', urllib.parse.urljoin(self.base_url, '/categories/'), 8, self.icons['categories'])

        video_blocks = re.findall(
            r'(<div\s+class="video-block video-with-trailer"\s+data-trailer-url="[^"]+".*?</a>\s*</div>)',
            content, re.DOTALL | re.IGNORECASE
        )
        for item_html in video_blocks:
            try:
                href = re.search(r'<a\s+class="thumb[^>]+href="([^"]+)"', item_html, re.IGNORECASE)
                title = re.search(r'<span\s+class="title">([^<]+)</span>', item_html, re.IGNORECASE)
                thumb = re.search(r'<img[^>]+data-src="([^"]+)"', item_html, re.IGNORECASE) or \
                        re.search(r'<img[^>]+src="([^"]+)"', item_html, re.IGNORECASE)
                dur = re.search(r'<span\s+class="duration[^>]*">([^<]+?)</span>', item_html, re.IGNORECASE)

                if not (href and title and thumb):
                    continue

                video_url = html.unescape(href.group(1).strip())
                title_txt = html.unescape(title.group(1).strip())
                thumb_url_raw = html.unescape(thumb.group(1).strip())
                thumb_url = urllib.parse.urljoin(self.base_url, thumb_url_raw)
                duration_str = dur.group(1).strip() if dur else ""

                label = f"{title_txt}"
                if duration_str:
                    label += f" [COLOR lime]({duration_str})[/COLOR]"

                seconds = 0
                try:
                    if 'min' in duration_str:
                        seconds = int(duration_str.split(' ')[0]) * 60
                    elif 'sec' in duration_str:
                        seconds = int(duration_str.split(' ')[0])
                except Exception:
                    seconds = 0

                info_labels = {'title': title_txt, 'duration': seconds}
                self.add_link(label, video_url, 4, thumb_url, self.fanart, info_labels=info_labels)
            except Exception as e:
                self.logger.error(f"Error parsing video block: {e}")

        nxt = re.search(r'<a\s+class="next page-link"\s+href="([^"]+)"', content, re.IGNORECASE)
        if nxt:
            next_url_abs = urllib.parse.urljoin(url, html.unescape(nxt.group(1)))
            self.add_dir('[COLOR blue]Next Page >>>>[/COLOR]', next_url_abs, 2, self.icons['default'])

        self.end_directory()

    def process_categories(self, url):
        cat_url = urllib.parse.urljoin(self.base_url, '/categories/')
        if not url or '/categories' not in (url or ''):
            url = cat_url

        content = self.make_request(url)
        if not content:
            self.end_directory()
            return

        pattern = re.compile(
            r'<div\s+class="video-block\s+video-block-cat">.*?'
            r'<a\s+class="thumb[^"]*"[^>]*href="([^"]+)"[^>]*>.*?'
            r'(?:data-src|src)="([^"]+)"[^>]*>.*?'
            r'<a\s+class="infos[^"]*"[^>]*>.*?'
            r'<span\s+class="title">([^<]+)</span>.*?'
            r'(?:<div\s+class="video-datas-category-count">([^<]+)</div>)?'
            r'.*?</div>',
            re.IGNORECASE | re.DOTALL
        )

        count_blocks = 0
        for m in pattern.finditer(content):
            count_blocks += 1
            cat_href = html.unescape(m.group(1).strip())
            img_src = html.unescape(m.group(2).strip())
            title_txt = html.unescape(m.group(3).strip())
            count_txt = (m.group(4) or '').strip()

            cat_href = urllib.parse.urljoin(self.base_url, cat_href)
            img_src = urllib.parse.urljoin(self.base_url, img_src)

            label = title_txt if not count_txt else f"{title_txt} [COLOR yellow]{count_txt}[/COLOR]"
            self.add_dir(label, cat_href, 2, img_src, self.fanart)

        self.logger.debug(f"PunishWorld: categories matched: {count_blocks} on {url}")
        if count_blocks == 0:
            self.notify_info("No categories found (layout changed?).")

        self.end_directory(content_type="videos")

    def play_video(self, url):
        self.logger.debug(f"Playing video from: {url}")
        
        content = self.make_request(url)
        if not content:
            self.notify_error("Failed to load video page.")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem(path=url))
            return

        stream_url = None

        m = re.search(r'var\s+videoHigh\s*=\s*"([^"]+)"', content, re.IGNORECASE)
        if m:
            stream_url = html.unescape(m.group(1).strip())

        if not stream_url:
            m = re.search(r'<source\s+src="([^"]+)"\s+type="video/mp4"\s+title="high"', content, re.IGNORECASE)
            if m:
                stream_url = html.unescape(m.group(1).strip())

        if not stream_url:
            m = re.search(r'"contentUrl"\s*:\s*"([^"]+\.mp4[^"]*)"', content, re.IGNORECASE)
            if m:
                stream_url = html.unescape(m.group(1).strip().replace(r'\/', '/'))

        if not stream_url:
            self.logger.error(f"Could not find any stream URL on page: {url}")
            self.notify_error("Could not find playable stream URL.")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem(path=url))
            return

        if "nosofiles.com" in stream_url and "?verify=" not in stream_url:
            self.logger.error(f"Found stream URL but missing ?verify=: {stream_url}")
            self.notify_error("Failed to get valid (signed) stream URL.")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem(path=url))
            return
            
        self.logger.debug(f"Resolved stream URL: {stream_url}")

        hdrs = {'Referer': url}
        self.logger.debug(f"Using manual headers for proxy: {hdrs}")

        # Sicherstellen, dass die Session existiert, bevor wir Cookies holen
        scraper_session = self.get_session()
        if not scraper_session:
            self.notify_error("Failed to get scraper session for proxy.")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem(path=url))
            return
            
        try:
            cj_len = sum(1 for _ in getattr(scraper_session, "cookies", []))
        except Exception:
            cj_len = 0
        self.logger.debug(f"Extracted {cj_len} cookies (CookieJar) and will reuse the same cloudscraper session for proxy.")

        try:
            ctrl = ProxyController(
                stream_url,
                hdrs,
                cookies=scraper_session.cookies, 
                session=scraper_session,     
                host="127.0.0.1",
                port=0
            )
            local_url = ctrl.start()
        except Exception as e:
            self.logger.error(f"Failed to start local proxy: {e}")
            self.notify_error("Failed to start local proxy.")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem(path=url))
            return

        li = xbmcgui.ListItem(path=local_url)
        li.setProperty('IsPlayable', 'true')
        li.setMimeType('video/mp4')
        li.setContentLookup(False)

        xbmcplugin.setResolvedUrl(self.addon_handle, True, li)

        try:
            monitor = xbmc.Monitor()
            player = xbmc.Player()
            guard = PlaybackGuard(player, monitor, local_url, ctrl, idle_timeout=60*60)
            guard.start()
        except Exception:
            pass