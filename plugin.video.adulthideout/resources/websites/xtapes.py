# -*- coding: utf-8 -*-
import html
import os
import re
import sys
import urllib.parse

import requests
import xbmcgui
import xbmcplugin

from resources.lib.base_website import BaseWebsite
from resources.lib.resolvers import resolver


class Xtapes(BaseWebsite):
    sort_options = ["Latest", "Most Viewed", "Top Rated"]
    sort_paths = {
        "Latest": "/?filtre=date&cat=0",
        "Most Viewed": "/?filtre=views&cat=0",
        "Top Rated": "/?filtre=rate&cat=0",
    }

    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="xtapes",
            base_url="https://ww3.xtapes.tw/",
            search_url="https://ww3.xtapes.tw/?s={}",
            addon_handle=addon_handle,
            addon=addon,
        )
        self.session = requests.Session()
        self.ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/126.0.0.0 Safari/537.36"
        )
        self.icon = os.path.join(self.addon.getAddonInfo("path"), "resources", "logos", "xtapes.png")
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
            self.logger.warning("[xtapes] HTTP %s for %s", response.status_code, url)
        except Exception as exc:
            self.logger.warning("[xtapes] Request failed for %s: %s", url, exc)
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

    def _content_section(self, page_html):
        match = re.search(r'<div\b[^>]+id=["\']content["\'][^>]*>([\s\S]*?)</div>\s*<!--\s*#content\s*-->', page_html or "", re.IGNORECASE)
        return match.group(1) if match else page_html

    def _context_menu(self, original_url=None):
        suffix = ""
        if original_url:
            suffix = "&original_url={}".format(urllib.parse.quote_plus(original_url))
        return [
            (
                "Sort by...",
                "RunPlugin({}?mode=7&action=select_sort&website={}{} )".format(
                    sys.argv[0], self.name, suffix
                ).replace(" )", ")"),
            )
        ]

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

    def _extract_videos(self, page_html):
        page_html = self._content_section(page_html)
        search_title = re.search(r"<h1\b[^>]*>\s*Search results for[\s\S]{0,300}?</h1>", page_html or "", re.IGNORECASE)
        if search_title and not re.search(r"\(\s*\d+\s+videos?\s*\)", self._clean(search_title.group(0)), re.IGNORECASE):
            return []
        videos = []
        seen = set()
        blocks = re.split(r"(?=<li\b[^>]+class=[\"'][^\"']*border-radius-5[^\"']*[\"'])", page_html or "", flags=re.IGNORECASE)
        for block in blocks:
            if "all_videos" in block or "listing-infos" not in block:
                continue
            href_match = re.search(r'<a\b[^>]+href=["\']([^"\']+)["\'][^>]*title=["\']([^"\']+)["\']', block, re.IGNORECASE)
            if not href_match:
                continue
            video_url = self._absolute(href_match.group(1))
            title = self._clean(href_match.group(2))
            if not video_url or video_url in seen or not title:
                continue
            parsed = urllib.parse.urlparse(video_url)
            if not parsed.netloc.endswith("xtapes.tw"):
                continue
            if len([part for part in parsed.path.split("/") if part]) < 2:
                continue
            seen.add(video_url)

            img_tag = ""
            img_match = re.search(r"<img\b[^>]*>", block, re.IGNORECASE)
            if img_match:
                img_tag = img_match.group(0)
                img_title = re.search(r'\s(?:alt|title)=["\']([^"\']+)["\']', img_tag, re.IGNORECASE)
                if img_title:
                    title = self._clean(img_title.group(1)) or title

            thumb = ""
            for attr in ("data-src", "data-original", "src"):
                thumb_match = re.search(r'\s{}=["\']([^"\']+)["\']'.format(attr), img_tag, re.IGNORECASE)
                if thumb_match:
                    thumb = self._absolute(thumb_match.group(1))
                    break

            duration_match = re.search(r'class=["\'][^"\']*time-infos[^"\']*["\'][^>]*>([\s\S]*?)<span', block, re.IGNORECASE)
            duration = self._clean(duration_match.group(1)) if duration_match else ""
            views_match = re.search(r'class=["\'][^"\']*views-infos[^"\']*["\'][^>]*>([\s\S]*?)<span', block, re.IGNORECASE)
            views = self._clean(views_match.group(1)) if views_match else ""
            seconds = self.convert_duration(duration)
            label = "{} [COLOR lime]({})[/COLOR]".format(title, duration) if duration else title
            plot = title
            if views:
                plot += "\nViews: {}".format(views)
            info = {"title": title, "plot": plot}
            if seconds:
                info["duration"] = seconds
            videos.append({"label": label, "url": video_url, "thumb": thumb or self.icon, "info": info})
        return videos

    def _extract_next_page(self, page_html, current_url, page):
        next_match = re.search(r'<a\b[^>]+class=["\'][^"\']*next page-numbers[^"\']*["\'][^>]+href=["\']([^"\']+)["\']', page_html or "", re.IGNORECASE)
        if next_match:
            next_url = html.unescape(next_match.group(1))
            parsed = urllib.parse.urlparse(next_url)
            return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, parsed.query, ""))
        next_url = self.get_page_url(current_url, page + 1)
        next_path = urllib.parse.urlparse(next_url).path
        if re.search(r'href=["\'][^"\']*{}[^"\']*["\']'.format(re.escape(next_path)), page_html or "", re.IGNORECASE):
            return next_url
        return ""

    def process_content(self, url, page=1):
        if not url or url == "BOOTSTRAP":
            url, _ = self.get_start_url_and_label()
        context_menu = self._context_menu(url)
        if page == 1 and self._is_top_listing(url):
            self.add_dir("Search", "", 5, self.icons.get("search", self.icon), context_menu=context_menu)
            self.add_dir("Categories", self._absolute("/categories/"), 8, self.icons.get("categories", self.icon), context_menu=context_menu)

        target_url = self.get_page_url(url, page)
        page_html = self._get(target_url)
        if not page_html:
            self.notify_error("Could not load Xtapes listing")
            self.end_directory("videos")
            return

        videos = self._extract_videos(page_html)
        if not videos:
            self.notify_error("No Xtapes videos found")
            self.end_directory("videos")
            return

        for item in videos:
            self.add_link(item["label"], item["url"], 4, item["thumb"], self.fanart, context_menu=context_menu, info_labels=item["info"])

        next_url = self._extract_next_page(page_html, target_url, page)
        if next_url:
            self.add_dir("Next Page", url, 2, self.icons.get("default", self.icon), context_menu=context_menu, page=page + 1)
        self.end_directory("videos")

    def process_categories(self, url):
        current_url = url or self._absolute("/categories/")
        page_html = self._get(current_url)
        if not page_html:
            self.notify_error("Could not load Xtapes categories")
            self.end_directory("videos")
            return

        section_match = re.search(r'<ul\b[^>]+class=["\'][^"\']*listing-cat[^"\']*["\'][^>]*>([\s\S]*?)</ul>', page_html, re.IGNORECASE)
        section = section_match.group(1) if section_match else page_html
        seen = set()
        for block in re.findall(r"<li\b[\s\S]*?</li>", section, re.IGNORECASE):
            href_match = re.search(r'<a\b[^>]+href=["\']([^"\']+)["\'][^>]*title=["\']([^"\']+)["\']', block, re.IGNORECASE)
            if not href_match:
                continue
            href = self._absolute(href_match.group(1))
            title = self._clean(href_match.group(2))
            if not href or not title or href in seen:
                continue
            parsed = urllib.parse.urlparse(href)
            if not parsed.netloc.endswith("xtapes.tw") or "gay" in title.lower():
                continue
            seen.add(href)
            img_match = re.search(r"<img\b[^>]*>", block, re.IGNORECASE)
            img_tag = img_match.group(0) if img_match else ""
            thumb_match = re.search(r'\ssrc=["\']([^"\']+)["\']', img_tag, re.IGNORECASE)
            thumb = self._absolute(thumb_match.group(1)) if thumb_match else self.icon
            count_match = re.search(r'class=["\'][^"\']*nb_cat[^"\']*["\'][^>]*>([\s\S]*?)</span>', block, re.IGNORECASE)
            count = self._clean(count_match.group(1)) if count_match else ""
            label = "{} [COLOR lime]{}[/COLOR]".format(title, count) if count else title
            self.add_dir(label, href, 2, thumb, self.fanart)

        self.end_directory("videos")

    def _extract_embed_url(self, page_html):
        match = re.search(r'<iframe\b[^>]+src=["\']([^"\']*88z\.io/[^"\']+)["\']', page_html or "", re.IGNORECASE)
        return html.unescape(match.group(1)).strip() if match else ""

    def resolve_recording_stream(self, url):
        page_html = self._get(url)
        if not page_html:
            return None
        embed_url = self._extract_embed_url(page_html)
        if not embed_url:
            return None
        stream_url, headers = resolver.resolve(embed_url, referer=url, headers={"User-Agent": self.ua, "Referer": url})
        if stream_url and stream_url.startswith("http"):
            return {"url": stream_url, "headers": headers or {}, "extension": "mp4"}
        return None

    def play_video(self, url):
        resolved = self.resolve_recording_stream(url)
        if not resolved:
            self.notify_error("Could not resolve Xtapes/88z stream")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return

        stream_url = resolved["url"]
        headers = resolved.get("headers") or {}
        play_url = stream_url
        header_str = urllib.parse.urlencode(headers) if headers else ""
        if "|" not in play_url and header_str:
            play_url += "|" + header_str

        list_item = xbmcgui.ListItem(path=play_url)
        list_item.setProperty("IsPlayable", "true")
        
        # Identify HLS streams (either .m3u8 or .txt Cloudflare master playlists)
        is_hls = ".m3u8" in stream_url.lower() or "cf-master" in stream_url.lower() or ".txt" in stream_url.lower()
        if is_hls:
            list_item.setMimeType("application/vnd.apple.mpegurl")
            list_item.setContentLookup(False)

        xbmcplugin.setResolvedUrl(self.addon_handle, True, list_item)
