import os
import re
import sys
import urllib.parse
import urllib.request

import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon

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
    _HAS_CLOUDSCRAPER = True
except Exception:
    _HAS_CLOUDSCRAPER = False


class Fapality(BaseWebsite):
    NAME = "fapality"
    BASE_URL = "https://fapality.com/"
    SEARCH_URL = "https://fapality.com/search/?q={}"

    RE_ITEM = re.compile(
        r'<li\b[^>]*(?:\buser_video\b|\bdata-id="\d+")[^>]*>(?P<body>.*?)</li>',
        re.IGNORECASE | re.DOTALL,
    )
    RE_VIDEO_LINK = re.compile(
        r'<a\b(?P<attrs>[^>]*\bhref="(?P<url>(?:https?://(?:www\.)?fapality\.com)?/\d+/?)"[^>]*)>',
        re.IGNORECASE,
    )
    RE_NEXT = re.compile(r'href="([^"]+)"[^>]*>\s*(?:Next|›|»)', re.IGNORECASE)
    RE_CAT = re.compile(r'href="(/categories/[^"]+|/pornstars/[^"]+|/channels/[^"]+)"[^>]*>([^<]+)</a>', re.IGNORECASE)
    RE_STREAM = re.compile(
        r'(?:source|file|video_url|src)\s*[:=]\s*["\'](?P<url>https?://[^"\']+?\.mp4[^"\']*)["\']',
        re.IGNORECASE,
    )

    def __init__(self, addon_handle):
        super().__init__(self.NAME, self.BASE_URL, self.SEARCH_URL, addon_handle)
        self.use_playback_proxy = True

    def _headers(self, referer=None):
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "identity",
        }
        if referer:
            headers["Referer"] = referer
        return headers

    def _fetch(self, url, referer=None):
        try:
            headers = self._headers(referer)
            if _HAS_CLOUDSCRAPER:
                scraper = cloudscraper.create_scraper()
                response = scraper.get(url, headers=headers, timeout=25)
                return response.text
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=25) as resp:
                return resp.read().decode("utf-8", errors="ignore")
        except Exception as exc:
            self.logger.error(f"Fapality fetch failed for {url}: {exc}")
            return None

    def _thumb(self, thumb):
        if not thumb:
            return self.icon
        if thumb.startswith("//"):
            return "https:" + thumb
        if thumb.startswith("/"):
            return urllib.parse.urljoin(self.BASE_URL, thumb)
        return thumb

    def _add_standard_nav(self):
        self.add_dir("[COLOR blue]Search[/COLOR]", "", 5, self.icons["search"], fanart=self.fanart)
        self.add_dir("[COLOR blue]Categories[/COLOR]", self.BASE_URL + "categories/", 8, self.icons["categories"], fanart=self.fanart)
        self.add_dir("[COLOR blue]Pornstars[/COLOR]", self.BASE_URL + "pornstars/", 9, self.icons["pornstars"], fanart=self.fanart)
        self.add_dir("[COLOR blue]Channels[/COLOR]", self.BASE_URL + "channels/", 10, self.icons["groups"], fanart=self.fanart)

    def _add_video_block(self, title, url, thumb):
        info = {"title": title, "plot": title}
        self.add_link(title, url, 4, thumb, self.fanart, info_labels=info)

    def _parse_list(self, html):
        seen = set()
        for match in self.RE_ITEM.finditer(html):
            body = match.group("body") or ""
            link = self.RE_VIDEO_LINK.search(body)
            if not link:
                continue
            attrs = link.group("attrs") or ""
            rel = link.group("url") or ""
            title_match = re.search(r'\btitle="([^"]+)"', attrs, re.IGNORECASE)
            if not title_match:
                title_match = re.search(r'<span\b[^>]*class="[^"]*\btitle\b[^"]*"[^>]*>(.*?)</span>', body, re.IGNORECASE | re.DOTALL)
            title = re.sub(r'<[^>]+>', '', title_match.group(1)).strip() if title_match else ""
            if not title or not rel:
                continue
            if rel in seen:
                continue
            seen.add(rel)
            url = urllib.parse.urljoin(self.BASE_URL, rel)
            thumb_match = re.search(
                r'<(?:img|video)\b[^>]*(?:data-src|src|poster)="([^"]+)"',
                body,
                re.IGNORECASE,
            )
            thumb = self._thumb(thumb_match.group(1) if thumb_match else "")
            self._add_video_block(title, url, thumb)

    def process_content(self, url, page=1):
        if not url or url == "BOOTSTRAP":
            url = self.BASE_URL

        self._add_standard_nav()

        html = self._fetch(url, referer=self.BASE_URL)
        if not html:
            self.notify_error("Failed to load page content.")
            self.end_directory()
            return

        self._parse_list(html)

        next_match = self.RE_NEXT.search(html)
        if next_match:
            next_url = urllib.parse.urljoin(self.BASE_URL, next_match.group(1))
            self.add_dir("[COLOR green]Next Page >>[/COLOR]", next_url, 2, self.icons["default"], fanart=self.fanart)

        self.end_directory()

    def process_categories(self, url):
        target = url or self.BASE_URL + "categories/"
        html = self._fetch(target, referer=self.BASE_URL)
        if not html:
            self.notify_error("Failed to load categories.")
            self.end_directory()
            return

        self.add_dir("[COLOR blue]Search[/COLOR]", "", 5, self.icons["search"], fanart=self.fanart)

        seen = set()
        for cat_url, cat_title in self.RE_CAT.findall(html):
            title = re.sub(r"\s+", " ", cat_title).strip()
            if not title:
                continue
            key = title.lower()
            if key in seen:
                continue
            seen.add(key)
            self.add_dir(title, urllib.parse.urljoin(self.BASE_URL, cat_url), 2, self.icons["categories"], fanart=self.fanart)

        self.end_directory()

    def process_pornstars(self, url):
        self.process_categories(url or self.BASE_URL + "pornstars/")

    def process_channels(self, url):
        self.process_categories(url or self.BASE_URL + "channels/")

    def play_video(self, url):
        html = self._fetch(url, referer=self.BASE_URL)
        if not html:
            self.notify_error("Failed to load video page.")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return

        sources = []
        for match in re.finditer(r'https?://[^"\']+?\.mp4[^"\']*', html, re.IGNORECASE):
            source = match.group(0)
            if source not in sources:
                sources.append(source)

        if not sources:
            for match in self.RE_STREAM.finditer(html):
                source = match.group("url")
                if source not in sources:
                    sources.append(source)

        if not sources:
            self.notify_error("No playable MP4 source found.")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return

        def quality_score(u):
            m = re.search(r'(\d{3,4})p', u, re.IGNORECASE)
            return int(m.group(1)) if m else 0

        best = sorted(sources, key=quality_score, reverse=True)[0]
        headers = self._headers(referer=url)

        try:
            ctrl = ProxyController(
                best,
                upstream_headers=headers,
                use_urllib=True,
                probe_size=True,
            )
            local_url = ctrl.start()
            PlaybackGuard(xbmc.Player(), xbmc.Monitor(), local_url, ctrl).start()
            li = xbmcgui.ListItem(path=local_url)
            li.setProperty("IsPlayable", "true")
            li.setMimeType("video/mp4")
            li.setContentLookup(False)
            xbmcplugin.setResolvedUrl(self.addon_handle, True, li)
        except Exception as exc:
            self.logger.error(f"Fapality playback failed: {exc}")
            self.notify_error("Playback failed.")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
