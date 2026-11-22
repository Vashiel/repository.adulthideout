#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re

from resources.lib.kvs_tube import KVSTubeWebsite

# Anything smaller than this is a placeholder clip, not a video.
MIN_VIDEO_BYTES = 1024 * 1024
IP_LIMIT_MESSAGE = "justporn is blocking downloads from this connection (IP limit). Try another network."


class JustPorn(KVSTubeWebsite):
    label = "JustPorn"
    sort_options = ["Latest", "Popular", "Top Rated"]
    sort_paths = {
        "Latest": "/latest-updates/",
        "Popular": "/most-popular/",
        "Top Rated": "/top-rated/",
    }
    categories_path = "/categories/"
    models_path = "/models/"
    next_page_full_count = 48
    use_playback_proxy = True

    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="justporn",
            base_url="https://www.justporn.com/",
            search_url="https://www.justporn.com/search/{}/",
            addon_handle=addon_handle,
            addon=addon,
        )

    def _check_download_stream(self, stream_url, referer):
        # Follow the redirects like a real download would. The site answers blocked clients with a
        # 302 to static/ip-limit.mp4, so the final URL and the file size decide whether it is real.
        headers = self._headers(referer, accept="*/*")
        headers["Range"] = "bytes=0-1023"
        try:
            response = self.session.get(stream_url, headers=headers, timeout=15, stream=True, allow_redirects=True)
            try:
                final_url = response.url
                ctype = response.headers.get("Content-Type", "").lower()
                # Range replies say "bytes 0-1023/<total>"; a plain reply only has Content-Length.
                content_range = response.headers.get("Content-Range", "")
                size_text = content_range.rsplit("/", 1)[-1] if "/" in content_range else response.headers.get("Content-Length", "")
                total = int(size_text) if size_text.isdigit() else 0
            finally:
                response.close()
        except Exception as exc:
            self.logger.warning("%s download probe failed for %s: %s", self.label or self.name, stream_url, exc)
            return None
        if response.status_code not in (200, 206):
            return None
        if "ip-limit" in final_url.lower():
            self.logger.warning("%s stream redirected to a limit placeholder: %s", self.label or self.name, final_url)
            self.download_error = IP_LIMIT_MESSAGE
            return None
        if "video" not in ctype and "octet-stream" not in ctype:
            return None
        if total and total < MIN_VIDEO_BYTES:
            self.logger.warning("%s stream too small to be a video (%s bytes): %s", self.label or self.name, total, final_url)
            return None
        return final_url

    def resolve_recording_stream(self, url):
        # Download entry point. The KVS player variables are missing on this site, so the page's
        # JSON-LD "contentUrl" (a get_file link) is the only stream. Note: play_video shares this.
        self.download_error = ""
        html_content = self._get(url, referer=self.base_url)
        candidates = []
        for pattern in (
            r'"contentUrl"\s*:\s*"([^"]+)"',
            r'(?:href|src)=["\']([^"\']*/get_file/[^"\']+\.mp4/?)["\']',
        ):
            for value in re.findall(pattern, html_content or "", re.IGNORECASE):
                stream_url = self._normalize_stream(value)
                if self._is_stream_candidate(stream_url) and stream_url not in candidates:
                    candidates.append(stream_url)
        final_url = None
        for stream_url in candidates:
            final_url = self._check_download_stream(stream_url, url)
            if final_url:
                break
        if not final_url:
            return None
        headers = self._headers(url, accept="*/*")
        cookies = self.session.cookies.get_dict() if self.session else {}
        if cookies:
            headers["Cookie"] = "; ".join("{}={}".format(key, value) for key, value in cookies.items())
        return {"url": final_url, "headers": headers, "extension": "mp4", "hls_proxy": False}
