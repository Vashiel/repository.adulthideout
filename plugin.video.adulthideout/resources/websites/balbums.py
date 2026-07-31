#!/usr/bin/env python
# -*- coding: utf-8 -*-

import html
import json
import os
import re
import sys
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

import xbmc
import xbmcgui
import xbmcplugin

from resources.lib.base_website import BaseWebsite
from resources.lib.proxy_utils import ProxyController, PlaybackGuard


class BalbumsWebsite(BaseWebsite):
    """Bunkr album archive with direct playback from Bunkr CDN files."""

    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="balbums",
            base_url="https://balbums.st",
            search_url="https://balbums.st/?search={}&mode=broad&per=20&sort=latest&page=1",
            addon_handle=addon_handle,
            addon=addon,
        )
        self.sort_options = ["Latest", "Oldest", "Most Files"]
        self.sort_values = ["latest", "oldest", "files"]
        self.sort_paths = {
            "Latest": "/?search=&mode=broad&per=20&sort=latest&page=1",
            "Oldest": "/?search=&mode=broad&per=20&sort=oldest&page=1",
            "Most Files": "/?search=&mode=broad&per=20&sort=files&page=1",
        }
        self.icon = os.path.join(self.addon.getAddonInfo("path"), "resources", "logos", "balbums.png")
        self._sign_cache = {}

    def get_headers(self, referer=None):
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Encoding": "identity",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": referer or "https://bunkr.cr/",
        }

    def make_request(self, url):
        vendor_path = os.path.join(self.addon.getAddonInfo("path"), "resources", "lib", "vendor")
        if vendor_path not in sys.path:
            sys.path.insert(0, vendor_path)
        try:
            import requests
            if not hasattr(self, "_session"):
                self._session = requests.Session()
            response = self._session.get(url, headers=self.get_headers(url), timeout=20)
            response.raise_for_status()
            self.logger.info("[Balbums] Request %s -> %s", url, response.status_code)
            return response.text
        except Exception as exc:
            self.logger.error("[Balbums] Request failed for %s: %s", url, exc)
            return None

    def get_start_url_and_label(self):
        try:
            index = int(self.addon.getSetting("balbums_sort_by") or "0")
        except (TypeError, ValueError):
            index = 0
        index = max(0, min(index, len(self.sort_options) - 1))
        return self.base_url + self.sort_paths[self.sort_options[index]], "Balbums - " + self.sort_options[index]

    def process_content(self, url, page=1):
        if not url or url == "BOOTSTRAP" or url.rstrip("/") == self.base_url:
            url, _ = self.get_start_url_and_label()
        content = self.make_request(url)
        if not content:
            self.notify_error("Failed to load page")
            self.end_directory()
            return

        if re.search(r"/a/[A-Za-z0-9]+", urllib.parse.urlparse(url).path):
            self.process_album(content, url)
        else:
            self.add_basic_dirs()
            self.process_album_list(content, url)
        self.end_directory()

    def add_basic_dirs(self):
        self.add_dir("[COLOR blue]Search[/COLOR]", "", 5, self.icons.get("search", self.icon), self.fanart)
        self.add_dir("[COLOR yellow]Top Albums[/COLOR]", "https://balbums.st/topalbums", 2, self.icon, self.fanart)

    def process_album_list(self, content, current_url):
        seen = set()
        count = 0
        pattern = re.compile(
            r'<a[^>]+href=["\'](https?://bunkr\.cr/a/[A-Za-z0-9]+|/a/[A-Za-z0-9]+)["\'][^>]*>(.*?)</a>',
            re.IGNORECASE | re.DOTALL,
        )
        for match in pattern.finditer(content):
            album_url = urllib.parse.urljoin("https://bunkr.cr/", html.unescape(match.group(1)))
            if album_url in seen:
                continue
            seen.add(album_url)
            block = match.group(2)
            title_match = re.search(r'<h[1-6][^>]*>(.*?)</h[1-6]>|alt=["\']([^"\']+)', block, re.I | re.S)
            title = next((html.unescape(value).strip() for value in title_match.groups() if value), "Bunkr Album") if title_match else "Bunkr Album"
            count_match = re.search(r'(\d+)\s+files?', block, re.I)
            if count_match:
                title = "%s (%s files)" % (title, count_match.group(1))
            thumb_values = re.findall(r'(?:data-src|src)=["\']([^"\']+)', block, re.I)
            thumb = self.icon
            for thumb_value in thumb_values:
                candidate = urllib.parse.urljoin(current_url, html.unescape(thumb_value))
                if "/img/bunkr.svg" not in candidate.lower():
                    thumb = candidate
                    break
            context = [
                ("Play Album", "RunPlugin(%s?mode=7&action=play_album&website=%s&original_url=%s)" % (sys.argv[0], self.name, urllib.parse.quote_plus(album_url))),
                ("Play All From Here", "RunPlugin(%s?mode=7&action=play_all_from_here&website=%s&original_url=%s)" % (sys.argv[0], self.name, urllib.parse.quote_plus(album_url + "|" + current_url))),
                ("Sort by...", "RunPlugin(%s?mode=7&action=select_sort&website=%s)" % (sys.argv[0], self.name)),
            ]
            self.add_dir(title, album_url, 2, thumb, self.fanart, context_menu=context)
            count += 1

        match = re.search(r'[?&]page=(\d+)', current_url)
        current_page = int(match.group(1)) if match else 1
        next_page = current_page + 1
        next_pattern = re.compile(r'href=["\']([^"\']*page=' + str(next_page) + r'\b[^"\']*)["\']', re.I)
        next_match = next_pattern.search(content)
        if not next_match:
            next_match = re.search(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>[\s\S]*?(?:Next|›)[\s\S]*?</a>', content, re.I)
        if next_match:
            next_url = urllib.parse.urljoin(current_url, html.unescape(next_match.group(1)))
            self.add_dir("[COLOR blue]Next Page >>[/COLOR]", next_url, 2, self.icon, self.fanart)
        self.logger.info("[Balbums] Found %s albums", count)

    def _extract_media(self, content):
        urls = re.findall(r'var\s+jsCDN\s*=\s*["\']([^"\']+)', content, re.I)
        urls += re.findall(r'<source[^>]+src=["\']([^"\']+)', content, re.I)
        urls += re.findall(r'<video[^>]+src=["\']([^"\']+)', content, re.I)
        result = []
        for url in urls:
            url = html.unescape(url).replace(r"\/", "/").replace("\\/", "/").strip()
            if url.startswith("https://") and url not in result and (".mp4" in url or "/storage/" in url):
                result.append(url)
        return result

    def _extract_file_links(self, content):
        links = re.findall(r'href=["\']((?:https?://bunkr\.cr)?/f/[A-Za-z0-9]+)["\']', content, re.I)
        result = []
        for link in links:
            full = urllib.parse.urljoin("https://bunkr.cr/", html.unescape(link))
            if full not in result:
                result.append(full)
        return result

    def _sign_media_url(self, media_url):
        if not media_url or "token=" in media_url:
            return media_url
        parsed = urllib.parse.urlparse(media_url)
        path = parsed.path
        if path in self._sign_cache:
            token, expires = self._sign_cache[path]
            separator = "&" if "?" in media_url else "?"
            return "%s%stoken=%s&ex=%s" % (media_url, separator, urllib.parse.quote(str(token)), urllib.parse.quote(str(expires)))
        try:
            sign_url = "https://glb-apisign.cdn.cr/sign?path=" + urllib.parse.quote(path, safe="")
            session = getattr(self, "_session", None) or getattr(self, "session", None)
            response = session.get(sign_url, headers=self.get_headers("https://bunkr.cr/"), timeout=10)
            if response.status_code == 200:
                data = response.json()
                token = data.get("token")
                expires = data.get("ex")
                if token and expires:
                    self._sign_cache[path] = (token, expires)
                    separator = "&" if "?" in media_url else "?"
                    return "%s%stoken=%s&ex=%s" % (media_url, separator, urllib.parse.quote(str(token)), urllib.parse.quote(str(expires)))
        except Exception as exc:
            self.logger.warning("[Balbums] CDN signing failed: %s", exc)
        return media_url

    def _fetch_single_file(self, file_url):
        file_content = self.make_request(file_url)
        if not file_content:
            return None
        thumb_match = re.search(r'var\s+videoCoverUrl\s*=\s*["\']([^"\']+)', file_content, re.I)
        thumb = html.unescape(thumb_match.group(1)).replace(r"\/", "/").replace("\\/", "/") if thumb_match else self.icon
        thumb = urllib.parse.urljoin(file_url, thumb)
        extracted = self._extract_media(file_content)
        if extracted:
            return [(self._sign_media_url(media_url), thumb) for media_url in extracted]
        return None

    def process_album(self, content, album_url):
        title_match = re.search(r'<h1[^>]*>(.*?)</h1>|property=["\']og:title["\'][^>]+content=["\']([^"\']+)', content, re.I | re.S)
        album_title = next((html.unescape(value).strip() for value in title_match.groups() if value), "Bunkr Album") if title_match else "Bunkr Album"
        action_url = "%s?mode=7&action=play_album&website=%s&original_url=%s" % (
            sys.argv[0], self.name, urllib.parse.quote_plus(album_url)
        )
        action_item = xbmcgui.ListItem("[COLOR green]Play All Videos[/COLOR]")
        action_item.setArt({"thumb": self.icon, "icon": self.icon, "fanart": self.fanart})
        xbmcplugin.addDirectoryItem(
            handle=self.addon_handle,
            url=action_url,
            listitem=action_item,
            isFolder=False,
        )
        
        file_links = self._extract_file_links(content)
        if file_links:
            for index, file_url in enumerate(file_links, 1):
                title = "%s - File %d" % (album_title, index)
                self.add_link(html.unescape(title), file_url, 4, self.icon, self.fanart)
            self.logger.info("[Balbums] Rendered %s files in album instantly", len(file_links))
        else:
            media = self._extract_media(content)
            for index, url in enumerate(media, 1):
                title = album_title if len(media) == 1 else "%s - Video %d" % (album_title, index)
                signed = self._sign_media_url(url)
                self.add_link(html.unescape(title), signed, 4, self.icon, self.fanart)

    def play_video(self, url):
        target_stream = url
        if "/f/" in url or "bunkr.cr" in url:
            file_results = self._fetch_single_file(url)
            if file_results and file_results[0]:
                target_stream = file_results[0][0]

        if not target_stream or not target_stream.startswith("http"):
            self.notify_error("Could not resolve video stream")
            return

        session = getattr(self, "_session", None) or getattr(self, "session", None)
        controller = ProxyController(
            target_stream,
            upstream_headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Referer": "https://bunkr.cr/",
            },
            session=session,
            skip_resolve=True,
        )
        local_url = controller.start()
        PlaybackGuard(xbmc.Player(), xbmc.Monitor(), local_url, controller)

        item = xbmcgui.ListItem(path=local_url)
        item.setProperty("IsPlayable", "true")
        item.setMimeType("video/mp4")
        xbmcplugin.setResolvedUrl(self.addon_handle, True, item)

    def play_album(self, url):
        content = self.make_request(url)
        if content:
            file_links = self._extract_file_links(content)
            if file_links:
                self._playlist_for_albums(file_links, "files")
            else:
                self._playlist_for_albums([url], "album")

    def _playlist_for_albums(self, items, label):
        playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
        playlist.clear()
        progress = xbmcgui.DialogProgress()
        progress.create("Balbums", "Loading album items...")
        added = 0
        total = len(items)
        session = getattr(self, "_session", None) or getattr(self, "session", None)
        for index, item_url in enumerate(items):
            if progress.iscanceled():
                break
            progress.update(int(index * 100 / max(1, total)), "Loading file %d of %d..." % (index + 1, total))
            if "/f/" in item_url:
                res = self._fetch_single_file(item_url)
                if res and res[0]:
                    media_url, thumb = res[0]
                    controller = ProxyController(
                        media_url,
                        upstream_headers={
                            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                            "Referer": "https://bunkr.cr/",
                        },
                        session=session,
                        skip_resolve=True,
                    )
                    play_url = controller.start()
                    listItem = xbmcgui.ListItem(f"Video {index + 1}")
                    listItem.setProperty("IsPlayable", "true")
                    listItem.setMimeType("video/mp4")
                    if thumb:
                        listItem.setArt({"thumb": thumb, "icon": thumb})
                    listItem.setPath(play_url)
                    playlist.add(url=play_url, listitem=listItem)
                    added += 1
            else:
                content = self.make_request(item_url)
                if not content:
                    continue
                album_media = self._extract_media(content)
                for video_index, media_url in enumerate(album_media, 1):
                    signed = self._sign_media_url(media_url)
                    controller = ProxyController(
                        signed,
                        upstream_headers={
                            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                            "Referer": "https://bunkr.cr/",
                        },
                        session=session,
                        skip_resolve=True,
                    )
                    play_url = controller.start()
                    listItem = xbmcgui.ListItem(f"Video {video_index}")
                    listItem.setProperty("IsPlayable", "true")
                    listItem.setMimeType("video/mp4")
                    listItem.setPath(play_url)
                    playlist.add(url=play_url, listitem=listItem)
                    added += 1
        progress.close()
        if added:
            self.logger.info("[Balbums] Playing playlist with %s videos", added)
            xbmc.Player().play(playlist)
        else:
            self.notify_error("No videos found")

    def play_all_from_here(self, packed_url):
        if not packed_url or "|" not in packed_url:
            return
        start_url, page_url = packed_url.split("|", 1)
        content = self.make_request(page_url)
        if not content:
            self.notify_error("Failed to load page")
            return
        albums = []
        for match in re.findall(r'href=["\'](https?://bunkr\.cr/a/[A-Za-z0-9]+|/a/[A-Za-z0-9]+)["\']', content, re.I):
            full = urllib.parse.urljoin("https://bunkr.cr/", html.unescape(match))
            if full not in albums:
                albums.append(full)
        if start_url in albums:
            albums = albums[albums.index(start_url):]
        self._playlist_for_albums(albums, "albums")

    def select_sort(self, original_url=None):
        index = xbmcgui.Dialog().select("Sort by...", self.sort_options)
        if index >= 0:
            self.addon.setSetting("balbums_sort_by", str(index))
            xbmc.executebuiltin("Container.Update(%s?mode=2&website=%s&url=BOOTSTRAP,replace)" % (sys.argv[0], self.name))

    def search(self, query):
        if query:
            self.process_content(self.search_url.format(urllib.parse.quote_plus(query)))
        else:
            self.end_directory()
