#!/usr/bin/env python
# -*- coding: utf-8 -*-

import hashlib
import html
import os
import re

import xbmcvfs

from resources.lib.kvs_tube import KVSTubeWebsite


class CamgirlFap(KVSTubeWebsite):
    label = "CamgirlFap"
    sort_options = ["Latest", "Most Viewed", "Top Rated"]
    sort_paths = {
        "Latest": "/latest-updates/",
        "Most Viewed": "/most-popular/",
        "Top Rated": "/top-rated/",
    }
    categories_path = "/categories/"
    models_path = "/models/"
    next_page_full_count = 20
    use_playback_proxy = True
    skip_category_titles = {
        "de", "fr", "es", "it", "pt", "zh", "ja", "ru", "tr", "en", "ko", "pl", "nl",
        "albums", "next page", "prev page", "previous page", "next", "prev", "previous", "last"
    }

    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="camgirlfap",
            base_url="https://camgirlfap.com/",
            search_url="https://camgirlfap.com/search/{}/",
            addon_handle=addon_handle,
            addon=addon,
        )
        self.icon = os.path.join(self.addon.getAddonInfo("path"), "resources", "logos", "camgirlfap.png")
        self.icons["default"] = self.icon
        self._thumb_cache_dir = self._init_thumb_cache()

    def _headers(self, referer=None, accept="text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"):
        headers = super()._headers(referer=referer, accept=accept)
        headers["Accept-Encoding"] = "identity"
        return headers

    def _init_thumb_cache(self):
        try:
            profile = xbmcvfs.translatePath(self.addon.getAddonInfo("profile"))
            cache_dir = os.path.join(profile, "thumbs", self.name)
            xbmcvfs.mkdirs(cache_dir)
            return cache_dir
        except Exception as exc:
            self.logger.warning("[camgirlfap] Thumbnail cache unavailable: %s", exc)
            return ""

    def _detect_image_extension(self, data, fallback_url):
        if data.startswith(b"\xff\xd8\xff"):
            return ".jpg"
        if data.startswith(b"\x89PNG\r\n\x1a\n"):
            return ".png"
        if data[:6] in (b"GIF87a", b"GIF89a"):
            return ".gif"
        if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
            return ".webp"
        _, ext = os.path.splitext(fallback_url.split("?", 1)[0])
        return ext.lower() if ext.lower() in (".jpg", ".jpeg", ".png", ".gif", ".webp") else ".jpg"

    def _cache_thumbnail(self, thumb_url, referer=None):
        if not self._thumb_cache_dir or not thumb_url or thumb_url == self.icon:
            return thumb_url
        try:
            digest = hashlib.sha256(thumb_url.encode("utf-8")).hexdigest()
            base_path = os.path.join(self._thumb_cache_dir, digest)
            for ext in (".jpg", ".png", ".gif", ".webp", ".jpeg"):
                candidate = base_path + ext
                if xbmcvfs.exists(candidate):
                    return candidate

            response = self.session.get(
                thumb_url,
                headers=self._headers(referer or self.base_url, accept="image/avif,image/webp,image/apng,image/*,*/*;q=0.8"),
                timeout=15,
            )
            if response.status_code != 200 or not response.content:
                return thumb_url

            ext = self._detect_image_extension(response.content[:32], thumb_url)
            target = base_path + ext
            handle = xbmcvfs.File(target, "wb")
            try:
                handle.write(response.content)
            finally:
                handle.close()
            return target
        except Exception as exc:
            self.logger.warning("[camgirlfap] Thumbnail cache failed for %s: %s", thumb_url, exc)
            return thumb_url

    def _extract_videos(self, html_content):
        videos = super()._extract_videos(html_content)
        for item in videos:
            item["thumb"] = self._cache_thumbnail(item.get("thumb"), item.get("url"))
        return videos

    def _probe_stream(self, stream_url, referer):
        # camgirlfap delivers both quality-tagged URLs (e.g. _1080p.mp4) AND
        # plain numeric MP4s (e.g. 710072.mp4) — both are valid.  We only skip
        # URLs that don't look like MP4 at all (e.g. HLS / unknown format).
        url = stream_url or ""
        is_mp4 = bool(re.search(r'\.mp4/?(?:$|\?)', url, re.IGNORECASE))
        if not is_mp4:
            self.logger.warning("[camgirlfap] Skipping non-MP4 stream candidate")
            return False
        has_quality = bool(re.search(r"_\d{3,4}p\.mp4/?(?:$|\?)", url, re.IGNORECASE))
        try:
            headers = self._headers(referer, accept="*/*")
            headers["Range"] = "bytes=0-4095"
            response = self.session.get(stream_url, headers=headers, timeout=15, stream=True, allow_redirects=True)
            data = response.raw.read(4096, decode_content=False)
            response.close()
            ctype = response.headers.get("Content-Type", "").lower()
            if response.status_code not in (200, 206) or "video" not in ctype:
                self.logger.warning("[camgirlfap] Stream probe rejected (status=%s, ct=%s)",
                                    response.status_code, ctype)
                return False
            return b"ftyp" in data[:64]
        except Exception as exc:
            self.logger.warning("[camgirlfap] Stream probe failed for %s: %s", stream_url, exc)
            return False

    def _extract_stream_url(self, html_content, referer=None):
        urls = {}
        license_match = re.search(r'license_code\s*:\s*[\'"]([^\'"]+)[\'"]', html_content or "", re.IGNORECASE)
        license_code = html.unescape(license_match.group(1)).strip() if license_match else ""
        for key, value in re.findall(r'(video_url|video_alt_url\d*):\s*[\'"]([^\'"]+)["\']', html_content or "", re.IGNORECASE):
            stream_url = self._normalize_stream(value, license_code)
            if self._is_stream_candidate(stream_url):
                urls[key] = stream_url

        order = ["video_alt_url5", "video_alt_url4", "video_alt_url3", "video_alt_url2", "video_alt_url", "video_url"]
        for key in order:
            stream_url = urls.get(key)
            if stream_url and self._probe_stream(stream_url, referer or self.base_url):
                return stream_url
        return None
