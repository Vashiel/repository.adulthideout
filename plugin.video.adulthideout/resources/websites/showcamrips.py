# -*- coding: utf-8 -*-
import base64
import html
import io
import os
import re
import urllib.parse

import requests
import xbmcgui
import xbmcplugin
import xbmcvfs

from resources.lib.base_website import BaseWebsite
from resources.lib.proxy_utils import PlaybackGuard, ProxyController

try:
    from PIL import Image
    HAS_PIL = True
except Exception:
    HAS_PIL = False


class ShowCamRips(BaseWebsite):
    supports_uploader_lookup = True
    uploader_lookup_patterns = (
        (r'href=["\']([^"\']*/model/en/[^"\']+)["\'][^>]*>(.*?)</a>', 1, 2),
    )

    def __init__(self, addon_handle, addon=None):
        super().__init__(
            "showcamrips",
            "https://www.showcamrips.com/en/",
            "https://www.showcamrips.com/search.php?Src={}&l=en",
            addon_handle,
            addon,
        )
        self.session = requests.Session()
        self.ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131 Safari/537.36"
        )
        self.icon = os.path.join(
            self.addon.getAddonInfo("path"), "resources", "logos", "showcamrips.png"
        )
        self.icons["default"] = self.icon
        self._temp_dir = xbmcvfs.translatePath("special://temp")

    def _headers(self, referer=None):
        return {
            "User-Agent": self.ua,
            "Referer": referer or self.base_url,
            "Accept-Encoding": "identity",
        }

    def _get(self, url, referer=None):
        try:
            response = self.session.get(
                url, headers=self._headers(referer), timeout=(7, 20)
            )
            return response.text if response.status_code == 200 else ""
        except Exception as exc:
            self.logger.warning("ShowCamRips request failed: %s", exc)
            return ""

    def _clear_old_thumbnails(self):
        try:
            for name in os.listdir(self._temp_dir):
                if name.startswith("adulthideout_showcamrips_") and (
                    name.endswith(".webp") or name.endswith(".jpg")
                ):
                    os.remove(os.path.join(self._temp_dir, name))
        except OSError:
            pass

    def _thumbnail_file(self, video_id, encoded):
        ext = ".jpg" if HAS_PIL else ".webp"
        path = os.path.join(
            self._temp_dir, "adulthideout_showcamrips_{}{}".format(video_id, ext)
        )
        if os.path.exists(path):
            return path
        try:
            padded = re.sub(r"\s+", "", encoded)
            while len(padded) % 4 != 0:
                padded += "="
            raw = base64.b64decode(padded)
            if HAS_PIL:
                img = Image.open(io.BytesIO(raw))
                out = io.BytesIO()
                img.convert("RGB").save(out, format="JPEG", quality=85)
                with open(path, "wb") as handle:
                    handle.write(out.getvalue())
                return path
            else:
                with open(path, "wb") as handle:
                    handle.write(raw)
                return path
        except Exception:
            return self.icon


    def _items(self, content):
        pattern = re.compile(
            r'<a\b[^>]*href=["\'](https?://www\.showcamrips\.com/'
            r'show-cam-sex-movies/([^/"\']+))["\'][^>]*data-id=["\'](\d+)["\']'
            r'[^>]*title=["\']([^"\']+)["\'][^>]*>\s*<img\b[^>]*'
            r'(?:data-tn|src)=["\']data:image/[^;]+;base64,\s*([^"\']+)',
            re.IGNORECASE,
        )
        seen = set()
        for match in pattern.finditer(content or ""):
            url, slug, video_id, title, encoded = match.groups()
            if video_id in seen:
                continue
            seen.add(video_id)
            title = re.sub(r"\s+", " ", html.unescape(title)).strip()
            uploader = re.sub(
                r"\s+(?:Chaturbate|Stripchat|Bongacams|Cam4|Camsoda)\s+webcam\s+rip.*$", "", title, flags=re.I
            ).strip(" -")
            username_match = re.search(r"^\s*([A-Za-z0-9_.-]+)", uploader)
            username = username_match.group(1) if username_match else uploader
            if username:
                thumb = "http://roomimg.stream.highwebmedia.com/ri/{}.jpg|verifypeer=false".format(
                    urllib.parse.quote(username)
                )
            else:
                thumb = self._thumbnail_file(video_id, encoded)

            yield title or slug.replace("-", " "), url, video_id, thumb, uploader

    def process_content(self, url, page=1):
        if not url or url == "BOOTSTRAP":
            url = self.base_url
        primary = self.is_primary_listing_url(url)
        if primary:
            self.add_dir("Search", "", 5, self.icons.get("search", self.icon))
            self.add_dir(
                "Categories", self.base_url, 8, self.icons.get("categories", self.icon)
            )
            self.add_dir(
                "Models",
                "https://www.showcamrips.com/cat/en/allmodels/",
                8,
                self.icons.get("pornstars", self.icon),
            )
        content = self._get(url)
        self._clear_old_thumbnails()
        count = 0
        for title, item_url, video_id, thumb, uploader in self._items(content):
            uploader_url = ""
            model_match = re.search(
                r'href=["\'](https?://www\.showcamrips\.com/model/en/[^"\']+)',
                content[content.find(item_url):content.find(item_url) + 24000],
                re.I,
            )
            if model_match:
                uploader_url = html.unescape(model_match.group(1))
            self.add_link(
                title,
                item_url,
                4,
                thumb or self.icon,
                self.fanart,
                info_labels={"title": title, "plot": title},
                uploader_name=uploader,
                uploader_url=uploader_url,
            )
            count += 1


        next_match = re.search(
            r'href=["\'](https?://www\.showcamrips\.com/(?:en/\d+-pg/|'
            r'(?:model|cat)/en/[^"\']+/\d+-pg/|search\.php\?[^"\']*\bpage=\d+[^"\']*))'
            r'["\'][^>]*>(?:\s*(?:Next|&gt;|»)|[^<]*&#9658;)',
            content or "",
            re.I,
        )
        if not next_match:
            current = re.search(r"/(\d+)-pg/?$", urllib.parse.urlparse(url).path)
            wanted = int(current.group(1)) + 1 if current else 2
            next_match = re.search(
                r'href=["\'](https?://www\.showcamrips\.com/[^"\']*/{}-pg/)["\']'.format(wanted),
                content or "",
                re.I,
            )
        if next_match:
            self.add_dir("Next Page", html.unescape(next_match.group(1)), 2, self.icon)
        if not count:
            self.notify_info("No videos found")
        self.end_directory("videos")

    def process_categories(self, url):
        content = self._get(url or self.base_url)
        seen = set()
        if "allmodels" in (url or ""):
            pattern = r'href=["\'](https?://www\.showcamrips\.com/model/en/[^"\']+/)["\'][^>]*>([^<]+)</a>'
        else:
            pattern = r'href=["\'](https?://www\.showcamrips\.com/cat/en/(?!allmodels)[^"\']+/)["\'][^>]*>([^<]+)</a>'
        for target, label in re.findall(pattern, content or "", re.I):
            label = re.sub(r"\s+", " ", html.unescape(label)).strip()
            if not label or target in seen:
                continue
            seen.add(target)
            self.add_dir(label, target, 2, self.icon)
        next_match = re.search(
            r'href=["\'](https?://www\.showcamrips\.com/[^"\']+/\d+-pg/)["\'][^>]*>\s*(?:Next|&gt;|»)',
            content or "",
            re.I,
        )
        if next_match:
            self.add_dir("Next Page", next_match.group(1), 8, self.icon)
        self.end_directory("videos")

    def search(self, query):
        if query:
            self.process_content(self.search_url.format(urllib.parse.quote_plus(query)))

    def resolve_recording_stream(self, url):
        root = "https://www.showcamrips.com/"
        content = self._get(url, self.base_url)
        iframe = re.search(
            r'<iframe\b[^>]*src=["\']([^"\']*loading_video\.php\?[^"\']+)',
            content or "",
            re.I,
        )
        if not iframe:
            return None
        player_url = urllib.parse.urljoin(root, html.unescape(iframe.group(1)))
        player = self._get(player_url, url)
        play_match = re.search(
            r'window\.location\.href\s*=\s*[\'"](play\.php\?[^\'"]+)[\'"]',
            player or "",
            re.I,
        )
        if play_match:
            real_play_url = urllib.parse.urljoin(root, html.unescape(play_match.group(1)))
            player = self._get(real_play_url, player_url)
            player_url = real_play_url

        stream = re.search(r'<video\b[^>]*\bsrc=["\']([^"\']+)["\']', player or "", re.I)
        if not stream:
            stream = re.search(r'<source\b[^>]*\bsrc=["\']([^"\']+)["\']', player or "", re.I)
        if not stream:
            stream = re.search(r'(https?://[^\s"\'<>]+\.mp4[^\s"\'<>]*)', player or "", re.I)
        if not stream:
            return None
        return {
            "url": html.unescape(stream.group(1)),
            "headers": self._headers(player_url),
            "extension": "mp4",
        }



    def play_video(self, url):
        resolved = self.resolve_recording_stream(url)
        if not resolved:
            return xbmcplugin.setResolvedUrl(
                self.addon_handle, False, xbmcgui.ListItem()
            )
        controller = ProxyController(
            resolved["url"],
            upstream_headers=resolved["headers"],
            session=self.session,
            skip_resolve=True,
            probe_size=True,
            use_urllib=False,
        )
        local_url = controller.start()
        item = xbmcgui.ListItem(path=local_url)
        item.setProperty("IsPlayable", "true")
        item.setMimeType("video/mp4")
        item.setContentLookup(False)
        xbmcplugin.setResolvedUrl(self.addon_handle, True, item)
        PlaybackGuard(
            __import__("xbmc").Player(), __import__("xbmc").Monitor(), local_url, controller
        ).start()
