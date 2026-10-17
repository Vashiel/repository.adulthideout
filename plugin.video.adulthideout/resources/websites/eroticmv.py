# -*- coding: utf-8 -*-
import base64
import re
import urllib.request

from resources.lib.wordpress_api_tube import WordPressApiTube


class EroticMV(WordPressApiTube):
    show_pornstars = True

    def __init__(self, addon_handle, addon=None):
        super().__init__("eroticmv", "EroticMV", "https://eroticmv.com/", addon_handle, addon)

    def _get(self, url, referer=None):
        headers = self._headers(referer)
        headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36"
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=12) as response:
                return response.read().decode("utf-8", "replace")
        except Exception as exc:
            self.logger.warning("[eroticmv] HTML request failed: %s", exc)
            return ""

    def resolve_recording_stream(self, url):
        page_html = self._get(url, referer=self.base_url)
        match = re.search(r'"single_video_url"\s*:\s*"([A-Za-z0-9+/=_-]+)\.m3u8"', page_html or "")
        if not match:
            return None
        try:
            encoded = match.group(1).replace("-", "+").replace("_", "/")
            encoded += "=" * ((4 - len(encoded) % 4) % 4)
            stream_url = base64.b64decode(encoded).decode("utf-8", "replace")
        except Exception:
            return None
        if not stream_url.startswith(("http://", "https://")):
            return None
        return {"url": stream_url, "headers": self._headers(url), "extension": "m3u8"}
