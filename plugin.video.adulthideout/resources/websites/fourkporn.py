#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import subprocess
import urllib.parse

try:
    import xbmc
    _vendor = os.path.join(os.path.dirname(os.path.dirname(__file__)), "lib", "vendor")
    if _vendor not in sys.path:
        sys.path.insert(0, _vendor)
    import cloudscraper
except Exception as exc:
    cloudscraper = None
    try:
        xbmc.log("[AdultHideout][4kPorn] cloudscraper import failed: {}".format(exc), xbmc.LOGERROR)
    except Exception:
        pass

from resources.lib.kvs_tube import KVSTubeWebsite
from resources.lib.resilient_http import fetch_text, fetch_windows_text


class FourKPorn(KVSTubeWebsite):
    label = "4kPorn"
    sort_options = ["Latest", "Most Viewed", "Top Rated", "Longest"]
    sort_paths = {
        "Latest": "/latest-updates/",
        "Most Viewed": "/popular-videos/",
        "Top Rated": "/best-videos/",
        "Longest": "/latest-updates/?sort_by=duration",
    }
    categories_path = "/categories/"
    models_path = "/models/"
    video_path_markers = ("/videos/",)
    category_path_markers = ("/categories/", "/category/", "/models/")
    next_page_full_count = 24
    use_playback_proxy = True

    def _pick_thumb(self, img_tag):
        thumb = super()._pick_thumb(img_tag)
        if not thumb or not thumb.startswith("http"):
            return thumb
        try:
            from resources.lib.thumb_proxy import build_thumb_url
            return build_thumb_url(thumb, referer=self.base_url)
        except Exception:
            return thumb

    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="fourkporn",
            base_url="https://4kporn.xxx/",
            search_url="https://4kporn.xxx/search/{}/",
            addon_handle=addon_handle,
            addon=addon,
        )
        self._reset_scraper()

    def _reset_scraper(self):
        if not cloudscraper:
            return False
        try:
            # Let cloudscraper select its bundled profile. Forcing a Windows
            # profile changes the TLS cipher set and fails in Kodi on Android.
            self.session = cloudscraper.create_scraper()
            self.session.headers.update(self._headers())
            return True
        except Exception as exc:
            self.logger.warning("4kPorn cloudscraper initialization failed: %s", exc)
            return False

    def _get(self, url, referer=None, max_retries=None):
        attempts = max_retries or 2
        last_error = ""
        for attempt in range(attempts):
            if os.name == "nt":
                content = fetch_windows_text(url, headers=self._headers(referer), timeout=8)
            else:
                content = fetch_text(
                    url, headers=self._headers(referer), scraper=self.session,
                    timeout=8, use_windows_curl_fallback=False,
                )
            if content:
                if "<title>just a moment" not in content.lower():
                    return content
                last_error = "Cloudflare challenge returned instead of website content"
            else:
                last_error = "all request methods failed"
            if attempt + 1 < attempts:
                self._reset_scraper()
                xbmc.sleep(250)
        self.logger.error("4kPorn failed to fetch %s: %s", url, last_error)
        return ""

    def resolve_recording_stream(self, url):
        resolved = super().resolve_recording_stream(url)
        if not resolved or os.name != "nt":
            return resolved
        source = urllib.parse.urlsplit(resolved["url"])
        if source.hostname != urllib.parse.urlsplit(self.base_url).hostname or "/get_file/" not in source.path:
            return resolved
        # Resolve the protected redirect with the same transport as the page.
        # The resulting CDN URL can then use the normal, seekable Range proxy.
        for attempt in range(2):
            direct_url = self._resolve_curl_stream(resolved["url"], url)
            if direct_url:
                resolved["url"] = direct_url
                return resolved
            if attempt == 0:
                xbmc.sleep(250)
        return None

    def _resolve_curl_stream(self, stream, referer):
        command = ["curl.exe", "-L", "--fail", "--silent", "--show-error",
                   "--connect-timeout", "4", "--max-time", "8",
                   "--range", "0-1023", "--max-filesize", "1048576",
                   "--output", "-", "--write-out", "\nAH_META%{http_code}|%{url_effective}|%{content_type}"]
        for name, value in self._headers(referer, accept="*/*").items():
            command.extend(["--header", "{}: {}".format(name, value)])
        command.append(stream)
        try:
            result = subprocess.run(command, capture_output=True, timeout=10,
                                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            prefix, _, metadata = result.stdout.rpartition(b"\nAH_META")
            status, final_url, content_type = metadata.decode("utf-8", errors="replace").split("|", 2)
            if result.returncode != 0 or status not in ("200", "206") or b"ftyp" not in prefix[:64]:
                self.logger.warning("4kPorn protected stream request failed: HTTP %s, curl %s",
                                    status, result.returncode)
                return None
            if urllib.parse.urlsplit(final_url).scheme not in ("http", "https"):
                return None
            headers = self._headers(referer, accept="*/*")
            headers["Range"] = "bytes=0-63"
            response = self.session.get(final_url, headers=headers, stream=True, timeout=6)
            try:
                if response.status_code not in (200, 206):
                    return None
                prefix = next(response.iter_content(chunk_size=64), b"")
                if b"ftyp" not in prefix[:64]:
                    return None
            finally:
                response.close()
            self.logger.info("4kPorn resolved protected stream to %s", urllib.parse.urlsplit(final_url).hostname)
            return final_url
        except Exception as exc:
            self.logger.warning("4kPorn protected stream resolution failed: %s", exc)
            return None

