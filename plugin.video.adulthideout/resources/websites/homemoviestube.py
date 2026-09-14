import html
import re

from resources.lib.kvs_tube import KVSTubeWebsite
from resources.lib.thumb_proxy import build_thumb_url


class HomeMoviesTube(KVSTubeWebsite):
    label = "HomeMoviesTube"
    sort_options = ["Latest", "Most Viewed", "Top Rated", "Longest"]
    sort_paths = {"Latest": "/?tab=recent", "Most Viewed": "/?tab=mostviewed", "Top Rated": "/?tab=toprated", "Longest": "/?tab=longest"}
    search_path = "/search?q={}"
    categories_path = None
    models_path = None
    video_path_markers = ("/videos/",)
    category_path_markers = ("/categories/",)
    use_playback_proxy = True
    next_page_full_count = 50

    def _extract_videos(self, html_content):
        videos = []
        seen = set()
        for block in re.findall(r'<article\b[^>]*class=["\'][^"\']*video-card[^"\']*["\'][^>]*>(.*?)</article>', html_content or "", re.I | re.S):
            link = re.search(r'<a\b[^>]*href=["\']([^"\']+/videos/[^"\']+)["\'][^>]*title=["\']([^"\']+)["\']', block, re.I)
            image = re.search(r'<img\b[^>]*>', block, re.I)
            duration = re.search(r'class=["\'][^"\']*duration-badge[^"\']*["\'][^>]*>([^<]+)', block, re.I)
            if not link:
                continue
            video_url = self._absolute(link.group(1))
            if video_url in seen:
                continue
            seen.add(video_url)
            title = html.unescape(link.group(2)).strip()
            duration_text = self._clean(duration.group(1)) if duration else ""
            info = {"title": title, "plot": title}
            seconds = self.convert_duration(duration_text)
            if seconds:
                info["duration"] = seconds
            label = "{} [COLOR lime]({})[/COLOR]".format(title, duration_text) if duration_text else title
            thumb = self._pick_thumb(image.group(0)) if image else self.icon
            if thumb and "thumbs.cdn.homemoviestube.com" in thumb:
                thumb = build_thumb_url(thumb, referer=self.base_url)
            videos.append({"label": label, "url": video_url, "thumb": thumb, "info": info})
        return videos

    def __init__(self, addon_handle, addon=None):
        super().__init__(name="homemoviestube", base_url="https://www.homemoviestube.com/", search_url="https://www.homemoviestube.com/search?q={}", addon_handle=addon_handle, addon=addon)

    def get_page_url(self, base_url, page_num):
        if page_num <= 1:
            return base_url
        import urllib.parse
        parsed = urllib.parse.urlparse(base_url)
        query = urllib.parse.parse_qs(parsed.query)
        query["page"] = [str(page_num)]
        return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, urllib.parse.urlencode(query, doseq=True), parsed.fragment))
