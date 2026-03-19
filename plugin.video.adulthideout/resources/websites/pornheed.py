# -*- coding: utf-8 -*-
import html
import re
import sys
import urllib.parse

import requests
import xbmc
import xbmcgui
import xbmcplugin

from resources.lib.base_website import BaseWebsite
from resources.lib.proxy_utils import PlaybackGuard, ProxyController
from resources.lib.resilient_http import fetch_text


class Pornheed(BaseWebsite):
    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="pornheed",
            base_url="https://www.pornheed.com",
            search_url="https://www.pornheed.com/search/{}",
            addon_handle=addon_handle,
            addon=addon,
        )
        self.session = requests.Session()
        self.ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/126.0.0.0 Safari/537.36"
        )
        self.sort_options = ["Recent", "Most Viewed", "Runtime"]
        self.sort_map = {
            "Recent": "recently-added",
            "Most Viewed": "most-viewed",
            "Runtime": "runtime",
        }

    def make_request(self, url, referer=None):
        headers = {
            "User-Agent": self.ua,
            "Referer": referer or (self.base_url + "/"),
        }
        return fetch_text(
            url,
            headers=headers,
            scraper=self.session,
            logger=self.logger,
            timeout=20,
        )

    def _get_sort_key(self):
        try:
            idx = int(self.addon.getSetting("pornheed_sort_by") or "0")
        except Exception:
            idx = 0
        if not 0 <= idx < len(self.sort_options):
            idx = 0
        return self.sort_options[idx]

    def _build_sort_url(self, page_num=1):
        sort_path = self.sort_map.get(self._get_sort_key(), "recently-added")
        return urllib.parse.urljoin(
            self.base_url,
            f"/search/{sort_path}/all-time/all-tubes/all-words/all-duration/explore/{page_num}",
        )

    def get_start_url_and_label(self):
        sort_key = self._get_sort_key()
        return self._build_sort_url(1), f"Pornheed [COLOR yellow]({sort_key})[/COLOR]"

    def _get_context_menu(self):
        return [
            (
                "Sort by...",
                f"RunPlugin({sys.argv[0]}?mode=7&action=select_sort_order&website={self.name})",
            )
        ]

    def _add_main_dirs(self, context_menu):
        self.add_dir("Search", "", 5, self.icons.get("search", self.icon), context_menu=context_menu)
        self.add_dir(
            "Categories",
            urllib.parse.urljoin(self.base_url, "/categories"),
            8,
            self.icons.get("categories", self.icon),
            context_menu=context_menu,
        )

    def select_sort_order(self, original_url=None):
        try:
            preselect_idx = self.sort_options.index(self._get_sort_key())
        except ValueError:
            preselect_idx = 0

        idx = xbmcgui.Dialog().select("Sort by...", self.sort_options, preselect=preselect_idx)
        if idx == -1:
            return

        self.addon.setSetting("pornheed_sort_by", str(idx))
        new_url, _ = self.get_start_url_and_label()
        xbmc.executebuiltin(
            f"Container.Update({sys.argv[0]}?mode=2&website={self.name}&url={urllib.parse.quote_plus(new_url)})"
        )

    def search(self, query):
        if not query:
            return
        search_url = urllib.parse.urljoin(self.base_url, f"/search/{urllib.parse.quote_plus(query)}")
        self.process_content(search_url)

    def process_content(self, url):
        if not url or url == "BOOTSTRAP":
            url, _ = self.get_start_url_and_label()

        context_menu = self._get_context_menu()
        self._add_main_dirs(context_menu)
        self._list_videos(url, context_menu=context_menu)

    def _list_videos(self, url, context_menu=None):
        content = self.make_request(url)
        if not content:
            return self.end_directory("videos")

        blocks = re.split(r'<li id="\d+" class="video-item"', content)[1:]
        seen = set()
        current_ids = []

        for block in blocks:
            url_match = re.search(r'<a href="(/video/\d+/[^"]+)"', block, re.IGNORECASE)
            title_match = re.search(r'<h4>([^<]+)</h4>', block, re.IGNORECASE | re.DOTALL)
            thumb_match = re.search(r'<img [^>]*src="([^"]+)"', block, re.IGNORECASE)
            duration_match = re.search(r'<div class="runtime">([^<]+)</div>', block, re.IGNORECASE)
            if not (url_match and title_match):
                continue

            video_url = urllib.parse.urljoin(self.base_url, url_match.group(1))
            if video_url in seen:
                continue
            seen.add(video_url)
            current_ids.append(url_match.group(1).split("/")[2])

            title = html.unescape(title_match.group(1).strip())
            thumb = thumb_match.group(1).strip() if thumb_match else ""
            if thumb.startswith("//"):
                thumb = "https:" + thumb
            elif thumb.startswith("/"):
                thumb = urllib.parse.urljoin(self.base_url, thumb)

            info = {"title": title, "plot": title}
            duration = duration_match.group(1).strip() if duration_match else ""
            duration_seconds = self.convert_duration(duration)
            if duration_seconds:
                info["duration"] = duration_seconds

            self.add_link(
                title,
                video_url,
                4,
                thumb or self.icon,
                self.fanart,
                info_labels=info,
                context_menu=context_menu,
            )

        next_url = self._get_next_page_url(url, current_ids)
        if next_url:
            self.add_dir("Next Page", next_url, 2, self.icons.get("default", self.icon), context_menu=context_menu)

        self.end_directory("videos")

    def _get_next_page_url(self, url, current_ids):
        if not current_ids:
            return None

        match = re.search(r"/(\d+)$", urllib.parse.urlparse(url).path)
        current_page = int(match.group(1)) if match else 1
        base_url = re.sub(r"/\d+$", "", url.rstrip("/"))
        next_url = f"{base_url}/{current_page + 1}"

        next_content = self.make_request(next_url, referer=url)
        if not next_content:
            return None

        next_ids = []
        for video_id in re.findall(r'/video/(\d+)/', next_content, re.IGNORECASE):
            if video_id not in next_ids:
                next_ids.append(video_id)

        if not next_ids or next_ids[:5] == current_ids[:5]:
            return None
        return next_url

    def process_categories(self, url):
        content = self.make_request(url)
        if not content:
            return self.end_directory("videos")

        seen = set()
        for path, title in re.findall(
            r'<a class="fl" href="(/search/[^"]+)">([^<]+)</a>',
            content,
            re.IGNORECASE | re.DOTALL,
        ):
            full_url = urllib.parse.urljoin(self.base_url, path)
            if full_url in seen:
                continue
            seen.add(full_url)
            self.add_dir(html.unescape(title.strip()), full_url, 2, self.icons.get("categories", self.icon))

        self.end_directory("videos")

    def _preflight_stream(self, stream_url, headers):
        probe_headers = dict(headers)
        probe_headers["Range"] = "bytes=0-1"

        for attempt in range(3):
            try:
                response = self.session.get(
                    stream_url,
                    headers=probe_headers,
                    stream=True,
                    timeout=15,
                    verify=False,
                    allow_redirects=True,
                )
                response.raise_for_status()
                chunk_iter = response.iter_content(chunk_size=2)
                try:
                    next(chunk_iter, b"")
                finally:
                    response.close()
                self.logger.info(
                    "[Pornheed] Stream preflight ok on attempt %d: %s",
                    attempt + 1,
                    response.url,
                )
                return response.url or stream_url
            except Exception as exc:
                self.logger.warning(
                    "[Pornheed] Stream preflight failed on attempt %d for %s: %s",
                    attempt + 1,
                    stream_url,
                    exc,
                )
                xbmc.sleep(500)
        return stream_url

    def play_video(self, url):
        page_html = self.make_request(url, referer=self.base_url + "/")
        if not page_html:
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return

        embed_match = re.search(r'<iframe[^>]+src=[\'"](/embed/\d+)[\'"]', page_html, re.IGNORECASE)
        embed_url = urllib.parse.urljoin(self.base_url, embed_match.group(1)) if embed_match else url
        embed_html = self.make_request(embed_url, referer=url)
        if not embed_html:
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return

        source_match = re.search(r'<source[^>]+src="([^"]+)"', embed_html, re.IGNORECASE)
        if not source_match:
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return

        stream_url = html.unescape(source_match.group(1).strip())
        proxy_headers = {
            "User-Agent": self.ua,
            "Accept": "*/*",
            "Accept-Encoding": "identity",
            "Accept-Language": "en-US,en;q=0.9",
            "Connection": "keep-alive",
            "Sec-Fetch-Dest": "video",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "cross-site",
            "Referer": embed_url,
            "Origin": self.base_url,
        }
        stream_url = self._preflight_stream(stream_url, proxy_headers)

        controller = ProxyController(
            upstream_url=stream_url,
            upstream_headers=proxy_headers,
            cookies=None,
            session=self.session,
            use_urllib=False,
        )
        local_url = controller.start()

        list_item = xbmcgui.ListItem(path=local_url)
        list_item.setProperty("IsPlayable", "true")
        list_item.setMimeType("video/mp4")
        list_item.setContentLookup(False)
        xbmcplugin.setResolvedUrl(self.addon_handle, True, list_item)

        player = xbmc.Player()
        monitor = xbmc.Monitor()
        PlaybackGuard(player, monitor, local_url, controller).start()
