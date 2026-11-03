#!/usr/bin/env python
# -*- coding: utf-8 -*-

import html
import json
import os
import re
import sys
import urllib.parse
import requests
import xbmc
import xbmcgui
import xbmcplugin
import xbmcvfs

try:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    vendor_path = os.path.abspath(os.path.join(current_dir, "..", "lib", "vendor"))
    if os.path.exists(vendor_path) and vendor_path not in sys.path:
        sys.path.insert(0, vendor_path)
except Exception:
    pass

try:
    import cloudscraper
    _HAS_CF = True
except Exception:
    cloudscraper = None
    _HAS_CF = False

from resources.lib.base_website import BaseWebsite
from resources.lib.proxy_utils import HlsProxyController, PlaybackGuard
from resources.lib.resilient_http import fetch_text
from resources.lib.thumb_proxy import build_thumb_url


class Porner(BaseWebsite):
    def __init__(self, addon_handle, addon=None):
        super(Porner, self).__init__(
            name="porner",
            base_url="https://porner.tv",
            search_url="https://porner.tv/search?q={}",
            addon_handle=addon_handle,
            addon=addon,
        )
        self.provider = "Porner.TV"
        self.label = "Porner.TV"

        self.sort_options = ["Latest", "Most Viewed", "Most Liked"]
        self.sort_paths = {
            "Latest": "/hottest-videos",
            "Most Viewed": "/most-viewed-videos",
            "Most Liked": "/most-liked-videos",
        }

        self.ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        )
        self.session = self._build_session()

    def _build_session(self):
        if _HAS_CF:
            try:
                scraper = cloudscraper.create_scraper(
                    browser={"browser": "chrome", "platform": "windows", "desktop": True}
                )
                self.ua = scraper.headers.get("User-Agent", self.ua)
                return scraper
            except Exception as exc:
                self.logger.warning("Could not initialize cloudscraper: %s", exc)

        session = requests.Session()
        session.headers.update(self._headers())
        return session

    def _headers(self, referer=None):
        return {
            "User-Agent": self.ua,
            "Referer": referer or self.base_url,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

    def _img_url(self, url):
        if not url or not url.startswith("http"):
            return url
        return f"{url}|User-Agent={urllib.parse.quote(self.ua)}&Referer={urllib.parse.quote(self.base_url)}"

    def make_request(self, url, headers=None, is_json=False):
        req_headers = self._headers(referer=self.base_url)
        if headers:
            req_headers.update(headers)
        if is_json:
            req_headers["Accept"] = "application/json, text/plain, */*"

        for attempt in range(3):
            try:
                response = self.session.get(url, headers=req_headers, timeout=20)
                if response.status_code == 200:
                    return response.json() if is_json else response.text
                elif response.status_code == 404:
                    self.logger.warning("404 Not Found: %s", url)
                    return None
                elif response.status_code == 403:
                    self.logger.warning("Attempt %d: HTTP 403 on %s, trying resilient_http fallback", attempt + 1, url)
                    text = fetch_text(url, headers=req_headers, scraper=self.session, logger=self.logger)
                    if text:
                        if is_json:
                            try:
                                return json.loads(text)
                            except Exception:
                                pass
                        return text
                else:
                    self.logger.warning("Attempt %d: HTTP %d for %s", attempt + 1, response.status_code, url)
            except Exception as exc:
                self.logger.warning("Attempt %d failed for %s: %s", attempt + 1, url, exc)
            xbmc.sleep(500)

        # Final resilient fallback if session retries failed
        fallback_text = fetch_text(url, headers=req_headers, scraper=self.session, logger=self.logger)
        if fallback_text:
            if is_json:
                try:
                    return json.loads(fallback_text)
                except Exception:
                    return None
            return fallback_text
        return None

    def process_content(self, url, query=None, page=1):
        if not url or url == "BOOTSTRAP":
            url, _ = self.get_start_url_and_label()

        if url.endswith("/categories") or "/categories" in url:
            return self.process_categories(url)
        if url.endswith("/pornstars") or "/pornstars" in url:
            return self.process_pornstars(url)
        if url.endswith("/channels") or "/channels" in url:
            return self.process_channels(url)

        current_url = url
        if page > 1:
            if "/search" in url:
                if "?" in url:
                    base_part, query_part = url.split("?", 1)
                    current_url = f"{base_part.rstrip('/')}/page/{page}?{query_part}"
                else:
                    current_url = f"{url.rstrip('/')}/page/{page}"
            else:
                if "?" in url:
                    base_part, query_part = url.split("?", 1)
                    current_url = f"{base_part.rstrip('/')}/page/{page}?{query_part}"
                else:
                    current_url = f"{url.rstrip('/')}/page/{page}"

        page_html = self.make_request(current_url)
        if not page_html:
            self.logger.warning("Porner.TV empty HTML for %s", current_url)
            self.end_directory("videos")
            return

        # Add top-level navigation on first page when browsing main sections
        if page == 1 and not query and "/search" not in url:
            self.add_dir("Search", "", 5, self.icons.get("search"), name_param=self.name)
            self.add_dir("Categories", f"{self.base_url}/categories", 3, self.icons.get("categories"), name_param=self.name)
            self.add_dir("Pornstars", f"{self.base_url}/pornstars", 2, self.icons.get("pornstars"), name_param=self.name)
            self.add_dir("Channels", f"{self.base_url}/channels", 2, self.icons.get("groups", self.icon), name_param=self.name)

        pattern = r'<a class="SingleVideoItemLink" href="([^"]+)"[^>]*>(.*?)</a>'
        items = []
        thumb_urls = []

        for match in re.finditer(pattern, page_html, re.DOTALL):
            video_rel_url = match.group(1)
            block = match.group(2)

            video_url = urllib.parse.urljoin(self.base_url, video_rel_url)

            title_m = re.search(r'<div class="Title">\s*([^<]+)', block)
            if not title_m:
                continue
            video_title = html.unescape(title_m.group(1).strip())

            thumb_m = re.search(r'data-src="([^"]+)"', block) or re.search(r'src="([^"]+)"', block)
            raw_thumb = thumb_m.group(1) if thumb_m else None
            if raw_thumb and raw_thumb.startswith("http"):
                thumb_urls.append(raw_thumb)

            dur_m = re.search(r'<span class="Duration">.*?</i>\s*([\d:]+)', block, re.DOTALL)
            video_duration = dur_m.group(1).strip() if dur_m else ""

            items.append({
                "title": video_title,
                "url": video_url,
                "thumb": raw_thumb,
                "duration": video_duration,
            })

        found_count = 0

        for it in items:
            raw_thumb = it.get("thumb")
            effective_thumb = build_thumb_url(raw_thumb, referer=self.base_url) if raw_thumb else self.icons.get("default", self.icon)
            info = {
                "title": it["title"],
                "duration": self.convert_duration(it["duration"]),
            }

            self.add_link(
                name=it["title"],
                url=it["url"],
                mode=4,
                icon=effective_thumb,
                fanart=self.fanart,
                info_labels=info,
            )
            found_count += 1

        self.logger.info("Found %d videos on Porner.TV page %d", found_count, page)

        # Pagination
        has_next = (
            'aria-label="Next"' in page_html
            or f"/page/{page + 1}" in page_html
        )
        if has_next and found_count > 0:
            self.add_dir("Next Page >>", url, 2, self.icons.get("default", self.icon), name_param=self.name, page=page + 1)

        self.end_directory("videos")

    def process_categories(self, url):
        page_html = self.make_request(url)
        if not page_html:
            self.end_directory("videos")
            return

        pattern = r'<a[^>]+href="((?:https://porner\.tv)?/category/[^"]+)"[^>]*>(.*?)</a>'
        seen = set()
        items = []
        thumb_urls = []

        for match in re.finditer(pattern, page_html, re.DOTALL):
            cat_target = urllib.parse.urljoin(self.base_url, match.group(1))
            block = match.group(2)

            if cat_target in seen or "/page/" in cat_target:
                continue
            seen.add(cat_target)

            title_m = re.search(r'class="[^"]*Title"[^>]*>\s*([^<]+)', block)
            if title_m:
                cat_name = html.unescape(title_m.group(1).strip())
            else:
                slug = cat_target.rstrip("/").split("/")[-1]
                cat_name = slug.replace("-", " ").title()

            img_m = re.search(r'data-src="([^"]+)"', block) or re.search(r'src="([^"]+)"', block)
            raw_thumb = img_m.group(1) if img_m else None
            if raw_thumb and raw_thumb.startswith("http"):
                thumb_urls.append(raw_thumb)

            items.append({
                "name": cat_name,
                "url": cat_target,
                "thumb": raw_thumb,
            })

        for it in items:
            raw_thumb = it.get("thumb")
            effective_thumb = build_thumb_url(raw_thumb, referer=self.base_url) if raw_thumb else self.icons.get("categories", self.icon)
            self.add_dir(it["name"], it["url"], 2, icon=effective_thumb)

        self.end_directory("videos")

    def process_pornstars(self, url):
        page_html = self.make_request(url)
        if not page_html:
            self.end_directory("videos")
            return

        pattern = r'<a[^>]+href="((?:https://porner\.tv)?/pornstar/[^"]+)"[^>]*>(.*?)</a>'
        seen = set()
        items = []
        thumb_urls = []

        for match in re.finditer(pattern, page_html, re.DOTALL):
            star_target = urllib.parse.urljoin(self.base_url, match.group(1))
            block = match.group(2)

            if star_target in seen or "/page/" in star_target:
                continue
            seen.add(star_target)

            title_m = re.search(r'class="[^"]*Title"[^>]*>\s*([^<]+)', block) or re.search(r'alt="([^"]+)"', block)
            if title_m:
                star_name = html.unescape(title_m.group(1).strip())
            else:
                slug = star_target.rstrip("/").split("/")[-1]
                star_name = slug.replace("-", " ").title()

            img_m = re.search(r'data-src="([^"]+)"', block) or re.search(r'src="([^"]+)"', block)
            raw_thumb = img_m.group(1) if img_m else None
            if raw_thumb and raw_thumb.startswith("http"):
                thumb_urls.append(raw_thumb)

            items.append({
                "name": star_name,
                "url": star_target,
                "thumb": raw_thumb,
            })

        for it in items:
            raw_thumb = it.get("thumb")
            effective_thumb = build_thumb_url(raw_thumb, referer=self.base_url) if raw_thumb else self.icons.get("pornstars", self.icon)
            self.add_dir(it["name"], it["url"], 2, icon=effective_thumb)

        self.end_directory("videos")

    def process_channels(self, url):
        page_html = self.make_request(url)
        if not page_html:
            self.end_directory("videos")
            return

        pattern = r'<a[^>]+href="((?:https://porner\.tv)?/channel/[^"]+)"[^>]*>(.*?)</a>'
        seen = set()
        items = []
        thumb_urls = []

        for match in re.finditer(pattern, page_html, re.DOTALL):
            chan_target = urllib.parse.urljoin(self.base_url, match.group(1))
            block = match.group(2)

            if chan_target in seen or "/page/" in chan_target:
                continue
            seen.add(chan_target)

            title_m = re.search(r'class="[^"]*Title"[^>]*>\s*([^<]+)', block) or re.search(r'alt="([^"]+)"', block)
            if title_m:
                chan_name = html.unescape(title_m.group(1).strip())
            else:
                slug = chan_target.rstrip("/").split("/")[-1]
                chan_name = slug.replace("-", " ").title()

            img_m = re.search(r'data-src="([^"]+)"', block) or re.search(r'src="([^"]+)"', block)
            raw_thumb = img_m.group(1) if img_m else None
            if raw_thumb and raw_thumb.startswith("http"):
                thumb_urls.append(raw_thumb)

            items.append({
                "name": chan_name,
                "url": chan_target,
                "thumb": raw_thumb,
            })

        for it in items:
            raw_thumb = it.get("thumb")
            effective_thumb = build_thumb_url(raw_thumb, referer=self.base_url) if raw_thumb else self.icons.get("groups", self.icon)
            self.add_dir(it["name"], it["url"], 2, icon=effective_thumb)

        self.end_directory("videos")

    def search(self, query):
        if not query:
            return
        search_target = self.search_url.format(urllib.parse.quote_plus(query))
        self.process_content(search_target, query=query)

    def resolve_recording_stream(self, url):
        slug = url.rstrip("/").split("/")[-1].split("?")[0]
        api_url = f"https://porner.tv/api/videos/{slug}"

        data = self.make_request(api_url, is_json=True)
        if not data or not isinstance(data, dict):
            self.logger.warning("Failed to fetch Porner.TV video API for %s", slug)
            return None

        video_id = data.get("videoID")
        if not video_id:
            self.logger.warning("No videoID in Porner.TV API response for %s", slug)
            return None

        domain = data.get("videoDomain") or "prnrcdn.xyz"
        bucket = str((int(video_id) // 1000) * 1000).zfill(7)
        stream_url = f"https://{domain}/hls/{bucket}/{video_id}/master.m3u8"

        return {
            "url": stream_url,
            "headers": self._headers(referer=url),
            "extension": "mp4",
        }

    def play_video(self, url):
        resolved = self.resolve_recording_stream(url)
        if not resolved:
            self.notify_error("Could not resolve video stream")
            return xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())

        controller = HlsProxyController(
            resolved["url"],
            headers=resolved["headers"],
            session=self.session,
        )
        local_url = controller.start()

        item = xbmcgui.ListItem(path=local_url)
        item.setProperty("IsPlayable", "true")
        item.setMimeType("application/vnd.apple.mpegurl")
        item.setContentLookup(False)

        xbmcplugin.setResolvedUrl(self.addon_handle, True, item)
        PlaybackGuard(xbmc.Player(), xbmc.Monitor(), local_url, controller).start()
