import html
import re

from resources.lib.kvs_tube import KVSTubeWebsite
from resources.lib.resilient_http import _ipv4_call


class Porno24(KVSTubeWebsite):
    label = "Porno24"
    sort_options = ["Latest", "Most Viewed", "Top Rated"]
    sort_paths = {"Latest": "/latest-updates/", "Most Viewed": "/most-popular/", "Top Rated": "/top-rated/"}
    search_path = "/search/{}/"
    categories_path = "/categories/"
    models_path = "/models/"
    video_path_markers = ("/video/",)
    category_path_markers = ("/categories/",)
    use_playback_proxy = True
    next_page_full_count = 20

    def __init__(self, addon_handle, addon=None):
        super().__init__(name="porno24", base_url="https://porno24.to/", search_url="https://porno24.to/search/{}/", addon_handle=addon_handle, addon=addon)

    def resolve_recording_stream(self, url):
        try:
            response = _ipv4_call(lambda: self.session.get(url, headers=self._headers(self.base_url), timeout=8))
            if response.status_code != 200:
                return None
            page = response.text
        except Exception as exc:
            self.logger.warning("Porno24 detail request failed: %s", exc)
            return None

        match = re.search(r'video_url\s*:\s*["\']([^"\']+)["\']', page, re.I)
        if not match:
            match = re.search(r'event_reporting2\s*:\s*["\']([^"\']+)["\']', page, re.I)
        if not match:
            return None
        stream_url = self._absolute(html.unescape(match.group(1)).replace("\\/", "/"))
        return {"url": stream_url, "headers": self._headers(url, accept="*/*"), "extension": "mp4"}
