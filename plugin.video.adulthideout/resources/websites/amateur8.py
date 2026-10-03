#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re

from resources.lib.kvs_tube import KVSTubeWebsite
from resources.lib.thumb_proxy import build_thumb_url


class Amateur8(KVSTubeWebsite):
    label = "Amateur8"
    sort_options = ["Latest", "Most Popular", "Top Rated", "Longest"]
    sort_paths = {
        "Latest": "/latest-updates/",
        "Most Popular": "/most-popular/",
        "Top Rated": "/top-rated/",
        "Longest": "/longest/",
    }
    categories_path = "/categories/"
    models_path = "/models/"
    video_path_markers = ("/videos/",)
    use_playback_proxy = True

    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="amateur8",
            base_url="https://www.amateur8.com/",
            search_url="https://www.amateur8.com/search/{}/",
            addon_handle=addon_handle,
            addon=addon,
        )

    def _is_video_href(self, href):
        return bool(href and "/videos/" in href and "/link/videos/" not in href)

    def _pick_thumb(self, img_tag):
        tag = img_tag or ""
        for attr in ("data-original", "data-src", "data-lazy-src", "src", "data-webp"):
            match = re.search(r'\s{}=["\']([^"\']+)'.format(attr), tag, re.IGNORECASE)
            if not match:
                continue
            value = match.group(1).strip()
            lowered = value.lower()
            if not value or lowered.startswith("data:image/"):
                continue
            if any(marker in lowered for marker in ("blank.gif", "spacer.gif", "placeholder", "loading.gif")):
                continue
            thumb = self._absolute(value)
            if thumb:
                return build_thumb_url(thumb, referer=self.base_url)
        return super()._pick_thumb(tag)

    def resolve_recording_stream(self, url):
        resolved = super().resolve_recording_stream(url)
        if not resolved or not resolved.get("url"):
            return resolved
        stream_url = resolved["url"]
        headers = resolved.get("headers") or {}
        try:
            resp = self.session.get(stream_url, headers=headers, allow_redirects=False, timeout=(5, 10))
            if resp.status_code in (301, 302, 303, 307) and resp.headers.get("Location"):
                resolved["url"] = resp.headers["Location"]
                self.logger.info("Amateur8 direct stream resolved: %s", resolved["url"])
        except Exception as exc:
            self.logger.warning("Amateur8 direct media resolution fallback: %s", exc)
        return resolved
