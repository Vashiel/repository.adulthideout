# -*- coding: utf-8 -*-
import html
import os
import re
import sys
import urllib.parse
import requests
import xbmcgui
import xbmcplugin
import xbmcaddon

from resources.lib.base_website import BaseWebsite
from resources.lib.resolvers import resolver


class PornoBae(BaseWebsite):
    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="pornobae",
            base_url="https://pornobae.com/",
            search_url="https://pornobae.com/?s={}",
            addon_handle=addon_handle,
            addon=addon,
        )
        self.session = requests.Session()
        self.ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/126.0.0.0 Safari/537.36"
        )
        self.icon = os.path.join(self.addon.getAddonInfo("path"), "resources", "logos", "pornobae.png")
        self.icons["default"] = self.icon

    def _headers(self, referer=None, accept="text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"):
        return {
            "User-Agent": self.ua,
            "Accept": accept,
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "identity",
            "Referer": referer or self.base_url,
        }

    def _get(self, url, referer=None):
        try:
            response = self.session.get(url, headers=self._headers(referer), timeout=20)
            if response.status_code == 200:
                return response.text
            self.logger.warning("[pornobae] HTTP %s for %s", response.status_code, url)
        except Exception as exc:
            self.logger.warning("[pornobae] Request failed for %s: %s", url, exc)
        return ""

    def _absolute(self, url):
        if not url:
            return ""
        return urllib.parse.urljoin(self.base_url, html.unescape(url).strip())

    def _clean(self, value):
        value = html.unescape(value or "")
        value = re.sub(r"<[^>]+>", " ", value)
        value = re.sub(r"\s+", " ", value)
        return value.strip()

    def _is_top_listing(self, url):
        parsed = urllib.parse.urlparse(url or self.base_url)
        query = urllib.parse.parse_qs(parsed.query)
        return parsed.path.strip("/") in ("", "page/1") and "s" not in query

    def get_page_url(self, base_url, page_num):
        if page_num <= 1:
            return base_url
        parsed = urllib.parse.urlparse(base_url)
        path = parsed.path or "/"
        path = re.sub(r"/page/\d+/?$", "/", path)
        if path == "/":
            path = "/page/{}/".format(page_num)
        else:
            path = path.rstrip("/") + "/page/{}/".format(page_num)
        return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, path, parsed.params, parsed.query, ""))

    def _extract_videos(self, html_content):
        chunks = html_content.split('<div class="post-thumbnail">')
        videos = []
        seen = set()
        
        for i in range(1, len(chunks)):
            prev_part = chunks[i-1]
            curr_part = chunks[i]
            
            a_matches = list(re.finditer(
                r'<a\b[^>]+href=["\'](https?://pornobae\.com/[^"\']+)["\'][^>]*title=["\']([^"\']+)["\']',
                prev_part,
                re.IGNORECASE
            ))
            if not a_matches:
                continue
            
            last_a = a_matches[-1]
            video_url = last_a.group(1)
            title = self._clean(last_a.group(2))
            
            if video_url in seen:
                continue
            seen.add(video_url)
            
            img_match = re.search(r'<img\b[^>]+src=["\']([^"\']+)["\']', curr_part, re.IGNORECASE)
            thumb = self._absolute(img_match.group(1)) if img_match else ""
            
            duration_match = re.search(r'class=["\']duration["\'][^>]*>([\s\S]*?)</span>', curr_part, re.IGNORECASE)
            duration = self._clean(duration_match.group(1)) if duration_match else ""
            
            seconds = self.convert_duration(duration)
            label = "{} [COLOR lime]({})[/COLOR]".format(title, duration) if duration else title
            
            info = {"title": title, "plot": title}
            if seconds:
                info["duration"] = seconds
                
            videos.append({
                "label": label,
                "url": video_url,
                "thumb": thumb or self.icon,
                "info": info
            })
            
        return videos

    def _extract_next_page(self, page_html, current_url, page):
        next_url = self.get_page_url(current_url, page + 1)
        next_parsed = urllib.parse.urlparse(next_url)
        next_path = next_parsed.path
        if next_path in page_html or urllib.parse.quote(next_path) in page_html:
            return next_url
        return ""

    def process_content(self, url, page=1):
        if not url or url == "BOOTSTRAP":
            url = self.base_url

        if page == 1 and self._is_top_listing(url):
            self.add_dir("Search", "", 5, self.icons.get("search", self.icon))
            self.add_dir("Categories", self._absolute("/categories/"), 8, self.icons.get("categories", self.icon))

        target_url = self.get_page_url(url, page)
        page_html = self._get(target_url)
        if not page_html:
            self.notify_error("Could not load PornoBae content")
            self.end_directory("videos")
            return

        videos = self._extract_videos(page_html)
        if not videos:
            self.notify_error("No PornoBae videos found")
            self.end_directory("videos")
            return

        for item in videos:
            self.add_link(
                item["label"],
                item["url"],
                4,
                item["thumb"],
                self.fanart,
                info_labels=item["info"]
            )

        next_url = self._extract_next_page(page_html, url, page)
        if next_url:
            self.add_dir("Next Page", url, 2, self.icons.get("default", self.icon), page=page + 1)

        self.end_directory("videos")

    def process_categories(self, url):
        current_url = url or self._absolute("/categories/")
        page_html = self._get(current_url)
        if not page_html:
            self.notify_error("Could not load PornoBae categories")
            self.end_directory("videos")
            return

        seen = set()
        matches = re.findall(
            r'<a\b[^>]+href=["\'](https?://pornobae\.com/category/[^"\']+)["\'][^>]*>([\s\S]*?)</a>',
            page_html,
            re.IGNORECASE
        )
        for link, label in matches:
            href = self._absolute(link)
            title = self._clean(label)
            if not href or not title or href in seen:
                continue
            seen.add(href)
            self.add_dir(title, href, 2, self.icons.get("default", self.icon), self.fanart)

        self.end_directory("videos")

    def play_video(self, url):
        page_html = self._get(url)
        if not page_html:
            self.notify_error("Could not load video detail page")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return

        iframes = re.findall(r'<iframe\b[^>]+src=["\']([^"\']+)["\']', page_html, re.IGNORECASE)
        embed_url = None
        for iframe in iframes:
            if "tubexplayer.com" in iframe:
                embed_url = html.unescape(iframe).strip()
                break

        if not embed_url:
            self.notify_error("Could not find TubexPlayer embed iframe")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return

        stream_url, play_headers = resolver.resolve(embed_url, referer=url)
        if not stream_url:
            self.notify_error("Could not resolve stream from TubexPlayer")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return

        header_str = urllib.parse.urlencode(play_headers) if play_headers else ""
        play_url = stream_url
        if "|" not in play_url and header_str:
            play_url += "|" + header_str

        list_item = xbmcgui.ListItem(path=play_url)
        list_item.setProperty("IsPlayable", "true")
        list_item.setMimeType("application/vnd.apple.mpegurl")
        list_item.setContentLookup(False)

        import xbmc
        if xbmc.getCondVisibility("System.HasAddon(inputstream.adaptive)"):
            list_item.setProperty("inputstream", "inputstream.adaptive")
            list_item.setProperty("inputstream.adaptive.manifest_type", "hls")
            if header_str:
                list_item.setProperty("inputstream.adaptive.manifest_headers", header_str)
                list_item.setProperty("inputstream.adaptive.stream_headers", header_str)

        xbmcplugin.setResolvedUrl(self.addon_handle, True, list_item)
