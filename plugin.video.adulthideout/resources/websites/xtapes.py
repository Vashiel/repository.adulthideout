# -*- coding: utf-8 -*-
import html
import os
import re
import sys
import urllib.parse

import requests
import xbmc
import xbmcgui
import xbmcplugin

from resources.lib.base_website import BaseWebsite
from resources.lib.proxy_utils import HlsProxyController, PlaybackGuard
from resources.lib.resolvers import eightyeightz_resolver, hglink_resolver, resolver


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
            base_url="https://xtapes.org/",
            search_url="https://xtapes.org/?s={}",
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
        absolute = urllib.parse.urljoin(self.base_url, html.unescape(url).strip())
        parsed = urllib.parse.urlparse(absolute)
        if parsed.hostname and (parsed.hostname == "xtapes.tw" or parsed.hostname.endswith(".xtapes.tw")):
            absolute = urllib.parse.urlunparse(
                ("https", "xtapes.org", parsed.path, parsed.params, parsed.query, parsed.fragment)
            )
        return absolute

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
            if parsed.hostname != "xtapes.org":
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
            next_url = self._absolute(next_match.group(1))
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
            if parsed.hostname != "xtapes.org" or "gay" in title.lower():
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

    def _extract_embed_urls(self, page_html):
        """Return candidate embed iframe URLs ordered from the player container."""
        container_match = re.search(
            r'<div\b[^>]+class=["\'][^"\']*video-embed[^"\']*["\'][^>]*>([\s\S]*?)</div>',
            page_html or "",
            re.IGNORECASE,
        )
        scope = container_match.group(1) if container_match else (page_html or "")
        embeds = []
        seen = set()
        for raw_src in re.findall(r'<iframe\b[^>]+src=["\']([^"\']+)["\']', scope, re.IGNORECASE):
            candidate = urllib.parse.urljoin(self.base_url, html.unescape(raw_src).strip())
            if candidate in seen or not candidate.startswith(("http://", "https://")):
                continue
            if resolver.resolver_entry_for_url(candidate):
                seen.add(candidate)
                embeds.append(candidate)
        return embeds

    def _extract_embed_url(self, page_html):
        embeds = self._extract_embed_urls(page_html)
        return embeds[0] if embeds else ""

    def resolve_recording_stream(self, url):
        page_html = self._get(url)
        if not page_html:
            return None
        embeds = resolver.sort_urls_by_resolver_preference(
            self._extract_embed_urls(page_html), self.addon
        )
        req_headers = {"User-Agent": self.ua, "Referer": url}
        for embed_url in embeds:
            if not resolver.is_resolver_enabled(embed_url, self.addon):
                continue
            key = resolver.resolver_key_for_url(embed_url)
            if key == "88z":
                stream_url, headers = eightyeightz_resolver.resolve(embed_url, referer=url, headers=req_headers)
            elif key == "hglink":
                stream_url, headers = hglink_resolver.resolve(embed_url, referer=url, headers=req_headers)
            else:
                stream_url, headers = resolver.resolve(embed_url, referer=url, headers=req_headers)

            if not stream_url or not stream_url.startswith("http"):
                continue
            if key not in ("88z",) and resolver.resolver_preflight_enabled(self.addon):
                if not resolver.probe_resolved_stream(stream_url, headers):
                    continue

            lowered = stream_url.lower().split("?", 1)[0]
            is_hls = (
                ".m3u8" in lowered
                or "cf-master" in lowered
                or lowered.endswith(".txt")
                or "/hls" in lowered
            )
            return {
                "url": stream_url,
                "headers": headers or {},
                "extension": "m3u8" if is_hls else "mp4",
                "hls_proxy": is_hls,
            }
        return None

    def play_video(self, url):
        resolved = self.resolve_recording_stream(url)
        if not resolved:
            self.notify_error("Could not resolve Xtapes stream")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return

        stream_url = resolved["url"]
        headers = resolved.get("headers") or {}
        if resolved.get("extension") == "m3u8":
            controller = None
            try:
                controller = HlsProxyController(
                    stream_url,
                    headers=headers,
                    session=self.session,
                    force_local=True,
                )
                play_url = controller.start()
            except Exception as exc:
                controller = None
                self.logger.warning("[xtapes] HLS proxy failed, falling back direct: %s", exc)
                header_str = urllib.parse.urlencode(headers) if headers else ""
                play_url = f"{stream_url}|{header_str}" if header_str else stream_url

            list_item = xbmcgui.ListItem(path=play_url)
            list_item.setProperty("IsPlayable", "true")
            list_item.setMimeType("application/vnd.apple.mpegurl")
            list_item.setContentLookup(False)
            if controller is None and xbmc.getCondVisibility("System.HasAddon(inputstream.adaptive)"):
                list_item.setProperty("inputstream", "inputstream.adaptive")
                list_item.setProperty("inputstream.adaptive.manifest_type", "hls")
                if headers:
                    encoded_headers = urllib.parse.urlencode(headers)
                    list_item.setProperty("inputstream.adaptive.manifest_headers", encoded_headers)
                    list_item.setProperty("inputstream.adaptive.stream_headers", encoded_headers)
            xbmcplugin.setResolvedUrl(self.addon_handle, True, list_item)
            if controller:
                PlaybackGuard(xbmc.Player(), xbmc.Monitor(), play_url, controller).start()
            return

        header_str = urllib.parse.urlencode(headers) if headers else ""
        play_url = f"{stream_url}|{header_str}" if "|" not in stream_url and header_str else stream_url
        list_item = xbmcgui.ListItem(path=play_url)
        list_item.setProperty("IsPlayable", "true")
        list_item.setMimeType("video/mp4")
        list_item.setContentLookup(False)
        xbmcplugin.setResolvedUrl(self.addon_handle, True, list_item)
