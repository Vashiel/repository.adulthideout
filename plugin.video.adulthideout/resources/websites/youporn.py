#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
import urllib.parse
import urllib.error
import html
import sys
import json
import os
import threading

try:
    import xbmc
    import xbmcgui
    import xbmcplugin
    import xbmcaddon
except Exception:
    class _Dummy:
        def __getattr__(self, _): return lambda *a, **k: None
    xbmc = _Dummy(); xbmcgui = _Dummy(); xbmcplugin = _Dummy()
    class _Add:
        def getAddonInfo(self, _): return ""
    xbmcaddon = _Dummy(); xbmcaddon.Addon = _Add

from resources.lib.base_website import BaseWebsite
from resources.lib.proxy_utils import ProxyController, PlaybackGuard

try:
    addon_path = xbmcaddon.Addon().getAddonInfo('path')
    vendor_path = os.path.join(addon_path, 'resources', 'lib', 'vendor')
    if vendor_path not in sys.path:
        sys.path.insert(0, vendor_path)
except Exception:
    pass

try:
    import cloudscraper
    _HAS_CF = True
except Exception:
    _HAS_CF = False

_SESSION = None
_LOCK = threading.Lock()


class YouPornWebsite(BaseWebsite):

    def __init__(self, addon_handle):
        super().__init__(
            name="youporn",
            base_url="https://www.youporn.com",
            search_url="https://www.youporn.com/search/?query={}",
            addon_handle=addon_handle,
        )
        self.scraper = None
        self.ua = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/124.0 Safari/537.36")
        
        # Sort options
        self.sort_options = ["Videos", "Most Viewed", "Top Rated", "Longest"]
        self.sort_paths = {
            "Videos": "/browse/time/",
            "Most Viewed": "/most_viewed/",
            "Top Rated": "/top_rated/",
            "Longest": "/browse/duration/"
        }

    def _ensure_session(self):
        global _SESSION, _LOCK
        with _LOCK:
            if self.scraper:
                return self.scraper
            if _SESSION:
                self.scraper = _SESSION
                return self.scraper

            if not _HAS_CF:
                self.logger.error("[youporn] cloudscraper fehlt.")
                return None
            s = cloudscraper.create_scraper(browser={'custom': self.ua})
            
            host = "www.youporn.com"
            for ck_name, ck_value in (
                ("platform", "pc"),
                ("language", "en"),
            ):
                s.cookies.set(ck_name, ck_value, domain=host, path="/")
                s.cookies.set(ck_name, ck_value, domain=".youporn.com", path="/")

            self._warmup(s, f"https://{host}/")

            for dom in (host, ".youporn.com"):
                s.cookies.set("access", "1", domain=dom, path="/")
                s.cookies.set("cookieConsent", "5", domain=dom, path="/")
                s.cookies.set("necessary", "true", domain=dom, path="/")

            self._warmup(s, f"https://{host}/")

            self.scraper = s
            _SESSION = s
            return self.scraper

    def _warmup(self, s, url):
        try:
            self.logger.info(f"[youporn] WARMUP GET {url}")
            s.get(url, timeout=20, headers=self._std_headers())
        except Exception as e:
            self.logger.warning(f"[youporn] Warmup-Fehler: {e}")

    def _std_headers(self, referer=None):
        h = {
            "User-Agent": self.ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,de;q=0.8",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "DNT": "1",
            "Upgrade-Insecure-Requests": "1",
        }
        if referer:
            h["Referer"] = referer
        return h

    def _api_headers(self, referer):
        return {
            "User-Agent": self.ua,
            "Accept": "application/json, text/plain, */*",
            "Referer": referer,
            "Origin": "https://www.youporn.com",
            "X-Requested-With": "XMLHttpRequest",
        }

    def _get(self, url, as_json=False, headers=None):
        s = self._ensure_session()
        try:
            self.logger.info(f"[youporn] GET {url}")
            if _HAS_CF and s:
                r = s.get(url, timeout=30, headers=headers or self._std_headers(), allow_redirects=True)
                r.raise_for_status()
                return r.json() if as_json else r.text
            
            import urllib.request
            req = urllib.request.Request(url, headers=headers or self._std_headers())
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read()
                return json.loads(data.decode("utf-8", "ignore")) if as_json else data.decode("utf-8", "ignore")
        except Exception as e:
            self.logger.error(f"[youporn] Request-Fehler: {e}")
            return None

    @staticmethod
    def _looks_like_home(html_text):
        if not html_text:
            return False
        if "page_params.page_name = 'home'" in html_text or "page_params.page_name = 'home';" in html_text:
            return True
        if 'id="ageDisclaimerWrapper"' in html_text:
            return True
        return False

    @staticmethod
    def _extract_video_id(url, html_text):
        m = re.search(r'/watch/(\d+)', url)
        if m:
            return m.group(1)
        if html_text:
            m = re.search(r'"videoId"\s*:\s*"(\d+)"', html_text)
            if m:
                return m.group(1)
        return None

    def _find_all_m3u8(self, html_text):
        urls = re.findall(r'https?://[^\s\'"]+\.m3u8[^\s\'"]*', html_text, flags=re.I)
        for m in re.finditer(r'"hls"\s*:\s*"([^"]+\.m3u8[^"]*)"', html_text, flags=re.I):
            urls.append(html.unescape(m.group(1)))
        for m in re.finditer(r'"hls"\s*:\s*{\s*"url"\s*:\s*"([^"]+\.m3u8[^"]*)"', html_text, flags=re.I):
            urls.append(html.unescape(m.group(1)))
        
        seen, out = set(), []
        for u in urls:
            u = html.unescape(u)
            if u not in seen:
                seen.add(u); out.append(u)
        return out

    def _extract_media_definitions(self, html_text):
        res = []
        m = re.search(r'playerVars\s*=\s*({[\s\S]*?});', html_text)
        if not m:
            m = re.search(r'var\s+player_vars_\d+\s*=\s*({[\s\S]*?});', html_text)
        if m:
            txt = m.group(1)
            try:
                data = json.loads(txt)
                defs = data.get("mediaDefinitions") or data.get("media", {}).get("definitions") or []
                if isinstance(defs, list):
                    return defs
            except Exception:
                pass
        
        m = re.search(r'"mediaDefinitions"\s*:\s*(\[[\s\S]*?\])', html_text)
        if m:
            try:
                defs = json.loads(m.group(1))
                if isinstance(defs, list):
                    return defs
            except Exception:
                pass
        return res

    def _expand_remote_defs(self, defs, referer):
        out = []
        for d in defs:
            if not isinstance(d, dict):
                continue
            url = (d.get("videoUrl") or d.get("manifestUrl") or "").strip()
            if url.endswith(".json") and url.startswith("http"):
                js = self._get(url, as_json=True, headers=self._api_headers(referer))
                if isinstance(js, list):
                    out += [x for x in js if isinstance(x, dict)]
                elif isinstance(js, dict):
                    out.append(js)
            else:
                out.append(d)
        return out

    def _parse_jsonld_and_meta(self, html_text):
        cands = []
        for b in re.findall(r'<script[^>]+type="application/ld\+json"[^>]*>([\s\S]*?)</script>', html_text, re.I):
            try:
                data = json.loads(b)
            except Exception:
                continue
            objs = data if isinstance(data, list) else [data]
            for o in objs:
                if not isinstance(o, dict):
                    continue
                t = o.get("@type") or o.get("type") or ""
                if isinstance(t, list):
                    t = ",".join(t)
                if "VideoObject" in str(t):
                    cu = o.get("contentUrl") or ""
                    if cu:
                        cands.append({"format": "hls" if cu.endswith(".m3u8") else "mp4" if ".mp4" in cu else "", "videoUrl": cu, "quality": 0})
        
        m = re.search(r'<meta\s+property="og:video"\s+content="([^"]+)"', html_text, re.I)
        if m:
            v = html.unescape(m.group(1))
            cands.append({"format": "hls" if v.endswith(".m3u8") else "", "videoUrl": v, "quality": 0})
        m = re.search(r'<meta\s+name="twitter:player:stream"\s+content="([^"]+)"', html_text, re.I)
        if m:
            v = html.unescape(m.group(1))
            cands.append({"format": "hls" if v.endswith(".m3u8") else "", "videoUrl": v, "quality": 0})
        return cands

    def _extract_next_page(self, html_text, current_url):
        m = re.search(r'<a[^>]+href="([^"]+)"[^>]+aria-label="Next page"', html_text, re.I)
        if m:
            next_url = html.unescape(m.group(1))
            if next_url and next_url != "#":
                return urllib.parse.urljoin(self.base_url, next_url)
        return None

    def process_categories(self, url):
        """
        Robust parser für https://www.youporn.com/categories/
        - Kein Abbruch mehr, wenn es keinen <div id="pagination"> gibt.
        - Liest <a class="categoryBox ..."> Einträge innerhalb der categoriesList.
        """
        url = url or f"{self.base_url}/categories/"
        if not url.startswith("http"):
            url = urllib.parse.urljoin(self.base_url, url)

        html_text = self._get(url)
        if not html_text:
            self.notify_error("YouPorn: Failed to load categories.")
            self.end_directory()
            return

        # Umschalter zwischen 'Alphabetical' und 'Popularity'
        if "/categories/popular/" not in url:
            self.add_dir(
                "[COLOR blue]Sort: Popularity[/COLOR]",
                f"{self.base_url}/categories/popular/",
                8,
                self.icons.get("settings", ""),
                name_param=self.name,
            )
        if "/categories/popular/" in url or url.endswith("/categories/"):
            self.add_dir(
                "[COLOR blue]Sort: Alphabetical[/COLOR]",
                f"{self.base_url}/categories/",
                8,
                self.icons.get("settings", ""),
                name_param=self.name,
            )

        # 1) Versuche, nur den Categories-Block zu isolieren (ohne Pagination-Annahme)
        block = None
        m = re.search(
            r'<div\s+class="categoriesList[^"]*">(.*?)</div>\s*</div>',
            html_text,
            re.IGNORECASE | re.DOTALL,
        )
        if m:
            block = m.group(1)
        else:
            # 2) Alternativer Versuch: enger gefasst nur den inneren Block nehmen
            m2 = re.search(
                r'<div\s+class="categoriesList[^"]*">(.*)',
                html_text,
                re.IGNORECASE | re.DOTALL,
            )
            if m2:
                block = m2.group(1)
            else:
                # 3) Fallback: komplettes HTML durchsuchen (enthält auch Header-Dropdown,
                # ist aber besser als gar nichts zu listen)
                self.logger.warning("[youporn] categoriesList block not found; falling back to full HTML.")
                block = html_text

        # Einträge extrahieren (href, thumb, title)
        count = 0
        for m in re.finditer(
            r'<a\s+href="(/category/[^"]+)"\s+class="categoryBox[^"]*">[\s\S]*?'
            r'<img[^>]+(?:data-src|src)="([^"]+)"[^>]*alt="([^"]+)"[\s\S]*?</a>',
            block,
            re.IGNORECASE | re.DOTALL,
        ):
            cat_url = html.unescape(m.group(1))
            thumb = html.unescape(m.group(2))
            title = html.unescape(m.group(3)).strip()

            # data-src kann absolut oder relativ sein
            if not thumb.startswith("http"):
                thumb = urllib.parse.urljoin(self.base_url, thumb)

            full_url = urllib.parse.urljoin(self.base_url, cat_url)
            self.add_dir(title, full_url, 2, thumb, self.fanart)
            count += 1

        if count == 0:
            # Als letzte Rettung: noch großzügiger nur nach Links + Alt-Text suchen
            for m in re.finditer(
                r'<a\s+href="(/category/[^"]+)"[^>]*>[\s\S]*?'
                r'<img[^>]+(?:data-src|src)="([^"]+)"[^>]*alt="([^"]+)"',
                html_text,
                re.IGNORECASE | re.DOTALL,
            ):
                cat_url = html.unescape(m.group(1))
                thumb = html.unescape(m.group(2))
                title = html.unescape(m.group(3)).strip()
                if not thumb.startswith("http"):
                    thumb = urllib.parse.urljoin(self.base_url, thumb)
                full_url = urllib.parse.urljoin(self.base_url, cat_url)
                self.add_dir(title, full_url, 2, thumb, self.fanart)
                count += 1

        if count == 0:
            self.logger.error("[youporn] No categories found in page markup.")
            self.notify_error("YouPorn: Keine Kategorien gefunden.")
        self.end_directory()

    def process_actresses_list(self, url):
        url = url or f"{self.base_url}/pornstars/"
        if not url.startswith('http'):
            url = urllib.parse.urljoin(self.base_url, url)
            
        html_text = self._get(url)
        if not html_text:
            self.notify_error("YouPorn: Failed to load pornstars.")
            self.end_directory()
            return

        if '/pornstars/subscribers/' not in url:
            self.add_dir('[COLOR blue]Sort: Most Subscribed[/COLOR]', f"{self.base_url}/pornstars/subscribers/", 9, self.icons.get('settings', ''), name_param=self.name)
        if '/pornstars/alphabetical/' not in url:
            self.add_dir('[COLOR blue]Sort: Alphabetical[/COLOR]', f"{self.base_url}/pornstars/alphabetical/", 9, self.icons.get('settings', ''), name_param=self.name)
        if not url.endswith('/pornstars/') and '/pornstars/popular/' not in url:
             self.add_dir('[COLOR blue]Sort: Most Popular[/COLOR]', f"{self.base_url}/pornstars/", 9, self.icons.get('settings', ''), name_param=self.name)


        content_block_m = re.search(r'<div class="popularPornstars-wrapper[^"]*">([\s\S]+?)<div id="pagination"', html_text, re.DOTALL | re.I)
        if not content_block_m:
            self.logger.error("[youporn] Pornstar content block not found.")
            content_block = html_text
        else:
            content_block = content_block_m.group(1)

        for m in re.finditer(r'<div class=\'porn-star-list\'>.*?<a href="([^"]+)" class="tm_pornstar_thumb">.*?<img[^>]+(?:data-src|src)="([^"]+)"[^>]*alt="([^"]+)".*?<span>Rank: (\d+)</span>.*?<span class="video-count">(\d+)</span>', content_block, re.DOTALL | re.I):
            
            actress_url = html.unescape(m.group(1))
            thumb = html.unescape(m.group(2))
            name = html.unescape(m.group(3)).strip()
            rank = m.group(4)
            videos = m.group(5)
            
            if not thumb.startswith('http'):
                thumb = urllib.parse.urljoin(self.base_url, thumb)
            
            full_url = urllib.parse.urljoin(self.base_url, actress_url)
            
            label = f"{name} [COLOR gray](Rank: {rank} / Videos: {videos})[/COLOR]"
            
            self.add_dir(label, full_url, 2, thumb, self.fanart)

        next_url = self._extract_next_page(html_text, url)
        if next_url:
            self.add_dir('[COLOR green]Next Page >>[/COLOR]', next_url, 9, self.icons.get('default', ''), self.fanart)

        self.end_directory()

    def process_content(self, url):
        
        if not url or url.strip('/') == self.base_url.strip('/'):
            default_sort_path = self.sort_paths.get(self.sort_options[0], "/browse/time/")
            url = urllib.parse.urljoin(self.base_url, default_sort_path)
        
        html_text = self._get(url)
        if not html_text:
            self.notify_error("YouPorn: Seite konnte nicht geladen werden.")
            self.end_directory()
            return

        # Add Search at the top
        self.add_dir('[COLOR blue]Search[/COLOR]', '', 5, self.icons.get('search', ''), name_param=self.name)
        
        # Add Categories
        self.add_dir('[COLOR yellow]Categories[/COLOR]', f"{self.base_url}/categories/", 8, self.icons.get('categories', ''), name_param=self.name)

        # Add Pornstars
        self.add_dir('[COLOR yellow]Pornstars[/COLOR]', f"{self.base_url}/pornstars/", 9, self.icons.get('pornstars', ''), name_param=self.name)

        seen = set()
        for m in re.finditer(r'href="(/watch/\d+/[^"]*)"', html_text, flags=re.I):
            href = html.unescape(m.group(1))
            if href in seen:
                continue
            seen.add(href)
            title = ""
            thumb = ""
            
            # Context window around the link
            ctx_s = max(0, m.start() - 1500)
            ctx_e = min(len(html_text), m.end() + 1500)
            block = html_text[ctx_s:ctx_e]
            
            # Extract title
            t = re.search(r'\btitle="([^"]+)"', block, re.I)
            if not t:
                t = re.search(r'\baria-label="([^"]+)"', block, re.I)
            if not t:
                t = re.search(r'<img[^>]*\balt="([^"]+)"', block, re.I)
            if t:
                title = html.unescape(t.group(1)).strip()
            
            # Extract thumbnail - multiple patterns
            thumb_m = re.search(r'data-thumb="([^"]+)"', block, re.I)
            if thumb_m:
                thumb = html.unescape(thumb_m.group(1))
            
            if not thumb:
                thumb_m = re.search(r'data-poster="([^"]+)"', block, re.I)
                if thumb_m:
                    thumb = html.unescape(thumb_m.group(1))
            
            if not thumb:
                thumb_m = re.search(r'<img[^>]+src="([^"]+)"', block, re.I)
                if thumb_m:
                    thumb_url = html.unescape(thumb_m.group(1))
                    if any(x in thumb_url.lower() for x in ['thumb', 'poster', 'preview', '.jpg', '.webp']):
                        thumb = thumb_url
            
            if not thumb:
                thumb_m = re.search(r'data-src="([^"]+)"', block, re.I)
                if thumb_m:
                    thumb = html.unescape(thumb_m.group(1))
            
            # Extract duration
            dur = ""
            d = re.search(r'video-duration[^>]*>\s*<span>\s*([0-9:\s]+)\s*</span>', block, re.I | re.S)
            if not d:
                d = re.search(r'duration["\']?\s*[>:]\s*["\']?([0-9:]+)', block, re.I)
            if d:
                dur = d.group(1).strip()

            full_url = urllib.parse.urljoin(self.base_url, href)
            label = title or full_url
            if dur:
                label = f"{label} [COLOR gray]({dur})[/COLOR]"
            
            icon = thumb if thumb else self.icons.get('default', '')
            self.add_link(label, full_url, 4, icon, self.fanart)

        # Add Next Page button at the end
        next_url = self._extract_next_page(html_text, url)
        if next_url:
            self.add_dir('[COLOR green]Next Page >>[/COLOR]', next_url, 2, self.icons.get('default', ''), self.fanart)

        self.end_directory()

    def _resolve_hls_from_embed(self, video_id):
        emb = f"{self.base_url}/embed/{video_id}/"
        html_text = self._get(emb, headers=self._std_headers(referer=f"{self.base_url}/watch/{video_id}/"))
        if not html_text:
            return None
        m3u8s = self._find_all_m3u8(html_text)
        if m3u8s:
            self.logger.info(f"[youporn] EMBED HLS gefunden: {m3u8s[0]}")
            return m3u8s[0]
        
        for m in re.finditer(r'src"\s*:\s*"([^"]+)"\s*,\s*"type"\s*:\s*"(application/x-mpegURL|application/vnd.apple.mpegurl)"', html_text, re.I):
            return html.unescape(m.group(1))
        return None

    def play_video(self, url):
        html_text = self._get(url, headers=self._std_headers(self.base_url))
        if not html_text:
            self.notify_error("YouPorn: Seite nicht geladen.")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem(path=url))
            return

        if self._looks_like_home(html_text) and "/watch/" in url:
            self.logger.warning("[youporn] Watch-URL lieferte Home/Disclaimer – erzwungener Retry mit Cookie-Header.")
            hdr = self._std_headers(self.base_url)
            
            cj = self._ensure_session().cookies
            cookie_pairs = []
            for c in cj:
                if c.domain.endswith("youporn.com"):
                    cookie_pairs.append(f"{c.name}={c.value}")
            if cookie_pairs:
                hdr["Cookie"] = "; ".join(cookie_pairs)
            html_text = self._get(url, headers=hdr)

        if self._looks_like_home(html_text):
            self.notify_error("Zugriff von YouPorn auf Startseite umgeleitet (Age/Consent).")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem(path=url))
            return

        video_id = self._extract_video_id(url, html_text)
        self.logger.info(f"[youporn] VIDEO-ID: {video_id or 'unbekannt'}")

        hls_url = None
        if video_id:
            hls_url = self._resolve_hls_from_embed(video_id)

        if not hls_url:
            m3u8s = self._find_all_m3u8(html_text)
            if m3u8s:
                hls_url = m3u8s[0]
                self.logger.info(f"[youporn] WATCH HLS gefunden: {hls_url}")

        mp4_candidates = []
        if not hls_url:
            defs = self._extract_media_definitions(html_text)
            defs = self._expand_remote_defs(defs, referer=url)
            for d in defs:
                if not isinstance(d, dict):
                    continue
                v = (d.get("videoUrl") or d.get("manifestUrl") or "").strip()
                fmt = (d.get("format") or "").lower()
                q = d.get("quality") or d.get("label") or 0
                if not isinstance(q, int):
                    m = re.search(r"(\d{3,4})", str(q))
                    q = int(m.group(1)) if m else 0
                if v and v.lower().endswith(".m3u8"):
                    hls_url = v
                    break
                if v and (fmt == "mp4" or ".mp4" in v.lower().split("?")[0]):
                    mp4_candidates.append((q, v))

        if not hls_url:
            extras = self._parse_jsonld_and_meta(html_text)
            for e in extras:
                v = e.get("videoUrl") or e.get("contentUrl") or ""
                f = (e.get("format")or "").lower()
                if v.endswith(".m3u8"):
                    hls_url = v
                    break
                if v and (f == "mp4" or ".mp4" in v.lower().split("?")[0]):
                    mp4_candidates.append((e.get("quality") or 0, v))

        if hls_url:
            header_pipe = "|User-Agent={}&Referer={}&Origin={}".format(
                urllib.parse.quote(self.ua), urllib.parse.quote(url), urllib.parse.quote(self.base_url)
            )
            play_url = hls_url + header_pipe
            self.logger.info(f"[youporn] DECISION: HLS → inputstream.adaptive (ohne Proxy)")
            li = xbmcgui.ListItem(path=play_url)
            li.setProperty("IsPlayable", "true")
            li.setMimeType("application/vnd.apple.mpegurl")
            li.setContentLookup(False)
            try:
                li.setProperty("inputstream", "inputstream.adaptive")
                li.setProperty("inputstream.adaptive.manifest_type", "hls")
                li.setProperty("inputstream.adaptive.stream_headers",
                               "User-Agent=%s&Referer=%s&Origin=%s" % (urllib.parse.quote(self.ua), urllib.parse.quote(url), urllib.parse.quote(self.base_url)))
            except Exception:
                pass
            xbmcplugin.setResolvedUrl(self.addon_handle, True, li)
            return

        if mp4_candidates:
            best_q, mp4_url = max(mp4_candidates, key=lambda x: x[0])
            self.logger.info(f"[youporn] DECISION: MP4 via Proxy (Qualität={best_q})")
            sess = self._ensure_session()
            headers = {"Referer": url, "User-Agent": self.ua, "Origin": self.base_url}
            try:
                ctrl = ProxyController(
                    mp4_url, headers,
                    cookies=(sess.cookies if sess else None),
                    session=sess,
                    host="127.0.0.1", port=0
                )
                local_url = ctrl.start()
            except Exception as e:
                self.logger.error(f"[youporn] Proxy-Start fehlgeschlagen: {e}")
                self.notify_error("YouPorn: Proxy konnte nicht gestartet werden.")
                xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem(path=url))
                return

            li = xbmcgui.ListItem(path=local_url)
            li.setProperty("IsPlayable", "true")
            li.setMimeType("video/mp4")
            li.setContentLookup(False)
            xbmcplugin.setResolvedUrl(self.addon_handle, True, li)

            try:
                monitor = xbmc.Monitor()
                player = xbmc.Player()
                guard = PlaybackGuard(player, monitor, local_url, ctrl, idle_timeout=3600)
                guard.start()
            except Exception:
                pass
            return

        self.notify_error("YouPorn: Keine abspielbare Quelle gefunden.")
        xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem(path=url))