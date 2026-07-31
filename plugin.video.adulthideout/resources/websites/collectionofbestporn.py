# -*- coding: utf-8 -*-
import html
import re
import urllib.parse

import requests
import xbmc
import xbmcgui
import xbmcplugin

from resources.lib.base_website import BaseWebsite
from resources.lib.proxy_utils import PlaybackGuard, ProxyController
from resources.lib.resilient_http import fetch_text


class CollectionOfBestPorn(BaseWebsite):
    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="collectionofbestporn",
            base_url="https://collectionofbestporn.com/",
            search_url="https://collectionofbestporn.com/search/{}",
            addon_handle=addon_handle,
            addon=addon,
        )
        self.label = "CollectionOfBestPorn"
        self.disabled = True
        self.ua = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self.ua, "Referer": self.base_url})
        self.sort_options = ["Latest", "Most Viewed", "Top Rated", "Longest"]
        self.sort_paths = {
            "Latest": "/",
            "Most Viewed": "/most-viewed/month",
            "Top Rated": "/top-rated/month",
            "Longest": "/longest/month",
        }
        self.categories_url = f"{self.base_url}tags"

    def _show_offline(self):
        self.notify_error("CollectionOfBestPorn is currently offline")
        self.end_directory()

    def _headers(self, referer=None, accept="text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"):
        return {
            "User-Agent": self.ua,
            "Accept": accept,
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": referer or self.base_url,
        }

    def make_request(self, url, referer=None):
        try:
            response = self.session.get(url, headers=self._headers(referer), timeout=25, allow_redirects=True)
            if response.status_code == 200:
                return response.text
            self.logger.warning("CollectionOfBestPorn HTTP %s for %s", response.status_code, url)
        except Exception as exc:
            self.logger.warning("CollectionOfBestPorn request failed for %s: %s", url, exc)
            self.session = requests.Session()
        return fetch_text(url, headers=self._headers(referer), logger=self.logger,
                          timeout=25, use_windows_curl_fallback=True) or ""

    def _page_url(self, url, page):
        if page <= 1:
            return url
        base = url.rstrip("/")
        base = re.sub(r"/page/\d+$", "", base)
        return "{}/page/{}".format(base, page)

    def process_content(self, url, page=1, **kwargs):
        if self.disabled:
            return self._show_offline()
        if not url or url == "BOOTSTRAP":
            url, _ = self.get_start_url_and_label()

        if page == 1:
            self.add_dir('[COLOR blue]Search[/COLOR]', '', 5, self.icons['search'])
            self.add_dir('[COLOR yellow]Categories[/COLOR]', self.categories_url, 8, self.icons['categories'])

        content = self.make_request(self._page_url(url, page))
        if not content:
            self.notify_error("Could not load CollectionOfBestPorn")
            return self.end_directory()

        count = self._render_video_list(content)
        if count:
            self.add_dir('[COLOR blue]Next Page >>[/COLOR]', url, 2, self.icons['default'], page=page + 1)

        self.end_directory()

    def _render_video_list(self, content):
        pattern = (
            r'<a href="(https://collectionofbestporn\.com/video/[^"]+\.html)"[^>]*>'
            r'[\s\S]*?<img src="([^"]+\.jpg)"[^>]*alt="([^"]*)"'
            r'[\s\S]*?<span class="time">\s*([\d:]+)\s*</span>'
        )
        seen = set()
        count = 0
        for video_url, thumb, title, duration in re.findall(pattern, content):
            if video_url in seen:
                continue
            seen.add(video_url)
            display_title = html.unescape(title.strip()) or "Untitled"
            thumb = html.unescape(thumb)
            label = "{} [COLOR lime]({})[/COLOR]".format(display_title, duration)
            info = {"title": display_title, "mediatype": "video"}
            seconds = self.convert_duration(duration)
            if seconds:
                info["duration"] = seconds
            self.add_link(label, video_url, 4, thumb, self.fanart, info_labels=info)
            count += 1
        return count

    def process_categories(self, url):
        if self.disabled:
            return self._show_offline()
        content = self.make_request(url or self.categories_url)
        if not content:
            return self.end_directory(content_type='files')

        self.add_dir('[COLOR blue]Search[/COLOR]', '', 5, self.icons['search'])
        # the tag cloud uses relative links with the name as the anchor text,
        # e.g. <a href="/tag/anal">anal</a>; ignore icon-only featured links.
        pattern = r'<a href="((?:https://collectionofbestporn\.com)?/tag/[a-z0-9-]+)"[^>]*>([^<>]{2,40})</a>'
        seen = set()
        for cat_url, name in re.findall(pattern, content):
            slug = cat_url.rstrip('/').rsplit('/', 1)[-1]
            if slug in seen or not name.strip():
                continue
            seen.add(slug)
            abs_url = urllib.parse.urljoin(self.base_url, cat_url.rstrip('/') + "/newest")
            label = html.unescape(name.strip())
            self.add_dir(label, abs_url, 2, self.icons['categories'])

        self.end_directory(content_type='files')

    def search(self, query):
        if self.disabled:
            return self._show_offline()
        if query:
            self.process_content(self.search_url.format(urllib.parse.quote_plus(query.strip())))

    def _resolve_stream(self, url):
        content = self.make_request(url, referer=self.base_url)
        if not content:
            return None
        # video.js <source> tags carry a signed URL directly in the page HTML;
        # pick the highest advertised resolution.
        sources = re.findall(r'<source src="([^"]+)"[^>]*res=[\'"]?(\d+)', content)
        if not sources:
            return None
        best = max(sources, key=lambda s: int(s[1]))
        return html.unescape(best[0])

    def play_video(self, url):
        if self.disabled:
            self.notify_error("CollectionOfBestPorn is currently offline")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return
        stream_url = self._resolve_stream(url)
        if not stream_url:
            self.notify_error("Could not resolve stream")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return

        # the signed .mp4 URL is time-limited (validfrom/validto) and IP-bound;
        # route it through the local proxy so the add-on's own session serves it.
        controller = ProxyController(
            stream_url,
            upstream_headers={
                'User-Agent': self.ua,
                'Referer': self.base_url,
            },
            session=self.session,
            skip_resolve=True,
        )
        local_url = controller.start()

        guard = PlaybackGuard(xbmc.Player(), xbmc.Monitor(), local_url, controller)
        guard.start()

        li = xbmcgui.ListItem(path=local_url)
        li.setProperty('IsPlayable', 'true')
        li.setMimeType('video/mp4')
        li.setContentLookup(False)
        xbmcplugin.setResolvedUrl(self.addon_handle, True, li)
        guard.join()
