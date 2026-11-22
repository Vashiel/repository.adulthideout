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


class PornXP(BaseWebsite):
    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="pornxp",
            base_url="https://pxp.news/",
            # the site's own search box just redirects to /tags/<query>
            search_url="https://pxp.news/tags/{}",
            addon_handle=addon_handle,
            addon=addon,
        )
        self.label = "PornXP"
        self.ua = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self.ua, "Referer": self.base_url})
        self.sort_options = ["Latest", "New Releases", "HD", "Most Watched"]
        self.sort_paths = {
            "Latest": "/",
            "New Releases": "/released/",
            "HD": "/hd/",
            "Most Watched": "/best/",
        }

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
            self.logger.warning("PornXP HTTP %s for %s", response.status_code, url)
        except Exception as exc:
            self.logger.warning("PornXP request failed for %s: %s", url, exc)
            self.session = requests.Session()
        return fetch_text(url, headers=self._headers(referer), logger=self.logger,
                          timeout=25, use_windows_curl_fallback=True) or ""

    def _page_url(self, url, page):
        if page <= 1:
            return url
        parsed = urllib.parse.urlparse(url)
        query = dict(urllib.parse.parse_qsl(parsed.query))
        query["page"] = str(page)
        return urllib.parse.urlunparse(parsed._replace(query=urllib.parse.urlencode(query)))

    def process_content(self, url, page=1, **kwargs):
        if not url or url == "BOOTSTRAP":
            url, _ = self.get_start_url_and_label()

        if page == 1:
            self.add_dir('[COLOR blue]Search[/COLOR]', '', 5, self.icons['search'])
            self.add_dir('[COLOR yellow]Categories[/COLOR]', self.base_url, 8, self.icons['categories'])

        content = self.make_request(self._page_url(url, page))
        if not content:
            self.notify_error("Could not load PornXP")
            return self.end_directory()

        count = self._render_video_list(content)
        if count:
            self.add_dir('[COLOR blue]Next Page >>[/COLOR]', url, 2, self.icons['default'], page=page + 1)

        self.end_directory()

    def _render_video_list(self, content):
        pattern = (
            r'<a href="(/videos/\d+)">[\s\S]*?<img[^>]*?(?:data-src|src)="([^"]+\.jpg)"'
            r'[\s\S]*?<div class="item_dur">\s*([\d:]+)\s*</div>'
            r'[\s\S]*?<div class="item_title">([^<]+)<'
        )
        seen = set()
        count = 0
        for path, thumb, duration, title in re.findall(pattern, content):
            if path in seen:
                continue
            seen.add(path)
            video_url = urllib.parse.urljoin(self.base_url, path)
            thumb_url = urllib.parse.urljoin(self.base_url, html.unescape(thumb))
            display_title = html.unescape(title.strip()) or "Untitled"
            label = "{} [COLOR lime]({})[/COLOR]".format(display_title, duration)
            info = {"title": display_title, "mediatype": "video"}
            seconds = self.convert_duration(duration)
            if seconds:
                info["duration"] = seconds
            self.add_link(label, video_url, 4, thumb_url, self.fanart, info_labels=info)
            count += 1
        return count

    def process_categories(self, url):
        # No dedicated tag index page; every card carries its studio/performer
        # tags, so aggregate the unique /tags/ links from the front page.
        content = self.make_request(url or self.base_url)
        if not content:
            return self.end_directory(content_type='files')

        self.add_dir('[COLOR blue]Search[/COLOR]', '', 5, self.icons['search'])
        tags = {}
        for path in re.findall(r'href="(/tags/[^"]+)"', content):
            name = html.unescape(urllib.parse.unquote(path.rsplit('/', 1)[-1])).strip()
            if name:
                tags[name] = urllib.parse.urljoin(self.base_url, path)
        for name in sorted(tags, key=str.lower):
            self.add_dir(name, tags[name], 2, self.icons['categories'])

        self.end_directory(content_type='files')

    def search(self, query):
        if query:
            self.process_content(self.search_url.format(urllib.parse.quote(query.strip())))

    def _resolve_stream(self, url):
        content = self.make_request(url, referer=self.base_url)
        if not content:
            return None
        best_url, best_res = None, -1
        for src in re.findall(r'<source[^>]+src="([^"]+\.mp4)"', content):
            stream = html.unescape(src).strip()
            if stream.startswith("//"):
                stream = "https:" + stream
            res_match = re.search(r'/(\d{3,4})\.mp4', stream)
            res = int(res_match.group(1)) if res_match else 0
            if res > best_res:
                best_res, best_url = res, stream
        return best_url

    def play_video(self, url):
        stream_url = self._resolve_stream(url)
        if not stream_url:
            self.notify_error("Could not resolve PornXP stream")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return

        # The <source> URLs are already signed, direct CDN mp4 links (no get_file
        # redirect), so let the proxy stream them directly without re-resolving.
        controller = ProxyController(
            stream_url,
            upstream_headers={
                'User-Agent': self.ua,
                'Referer': self.base_url,
            },
            cookies=self.session.cookies.get_dict() if self.session else None,
            session=self.session,
            use_urllib=True,
            probe_size=True,
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

    def resolve_recording_stream(self, url):
        # Download entry point: the same signed CDN mp4 that play_video() streams.
        stream_url = self._resolve_stream(url)
        if not stream_url:
            return None
        headers = {"User-Agent": self.ua, "Referer": self.base_url}
        return {"url": stream_url, "headers": headers, "extension": "mp4", "hls_proxy": False}
