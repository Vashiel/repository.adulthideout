import base64
import codecs
import html
import json
import os
import re
import ssl
import sys
import urllib.parse
import urllib.request

import requests
import xbmcaddon
import xbmcgui
import xbmcplugin

from resources.lib.base_website import BaseWebsite


class HentaidudeWebsite(BaseWebsite):
    def __init__(self, addon_handle):
        addon = xbmcaddon.Addon()
        super().__init__(
            name="hentaidude",
            base_url="https://hentaidude.xxx/",
            search_url="https://hentaidude.xxx/?s={}",
            addon_handle=addon_handle,
            addon=addon,
        )
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/135.0.0.0 Safari/537.36"
                ),
                "Accept-Language": "en-US,en;q=0.9",
            }
        )

    def _fetch(self, url, referer=None):
        headers = {}
        if referer:
            headers["Referer"] = referer
        response = self.session.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        return response.text

    def _split_items(self, html_content):
        marker = '<div class="item vraven_item'
        if marker not in html_content:
            return []
        parts = html_content.split(marker)
        return [marker + chunk for chunk in parts[1:]]

    def _extract_listing_items(self, html_content):
        results = []
        seen = set()
        for block in self._split_items(html_content):
            title_match = re.search(
                r'<h3[^>]*>\s*<a href="(https://hentaidude\.xxx/watch/[^"]+/?)"[^>]*>(.*?)</a>',
                block,
                re.I | re.S,
            )
            if not title_match:
                continue

            series_url = title_match.group(1)
            series_title = re.sub(r"<[^>]+>", "", title_match.group(2)).strip()
            if not series_title:
                continue

            thumb_match = re.search(r'(?:data-src|src)="(https://[^"]+)"', block, re.I)
            thumb = thumb_match.group(1) if thumb_match else self.icon

            episode_links = re.findall(
                r'href="(https://hentaidude\.xxx/watch/[^"]+/(?:episode|bonus|collection)[^"]*)"',
                block,
                re.I,
            )
            ordered_episode_links = []
            for link in episode_links:
                clean = html.unescape(link)
                if clean not in ordered_episode_links:
                    ordered_episode_links.append(clean)

            if ordered_episode_links:
                for episode_url in ordered_episode_links:
                    slug = episode_url.rstrip("/").split("/")[-1]
                    label = slug.replace("-", " ").title()
                    if episode_url not in seen:
                        seen.add(episode_url)
                        results.append(
                            {
                                "title": f"{series_title} - {label}",
                                "url": episode_url,
                                "thumb": thumb,
                            }
                        )
            elif series_url not in seen:
                seen.add(series_url)
                results.append({"title": series_title, "url": series_url, "thumb": thumb})

        if results:
            return results

        fallback_patterns = [
            (
                r'<div class="c-tabs-item__content[\s\S]+?'
                r'<a href="(https://hentaidude\.xxx/watch/[^"]+/?)"[^>]*>\s*'
                r'<img src="(https://[^"]+)"[^>]*>[\s\S]+?'
                r'<h3[^>]*>\s*<a href="https://hentaidude\.xxx/watch/[^"]+/?"[^>]*>(.*?)</a>[\s\S]+?'
                r'Latest chapter[\s\S]+?<a href="(https://hentaidude\.xxx/watch/[^"]+/(?:episode|bonus|collection)[^"]*)"[^>]*>(.*?)</a>',
                True,
            ),
            (
                r'<div class="page-item-detail video[\s\S]+?'
                r'<a href="(https://hentaidude\.xxx/watch/[^"]+/?)"[^>]*>\s*'
                r'<img src="(https://[^"]+)"[^>]*>[\s\S]+?'
                r'<h3[^>]*>\s*<a href="https://hentaidude\.xxx/watch/[^"]+/?"[^>]*>(.*?)</a>[\s\S]+?'
                r'<div class="list-chapter">[\s\S]+?<a href="(https://hentaidude\.xxx/watch/[^"]+/(?:episode|bonus|collection)[^"]*)"[^>]*>\s*(.*?)\s*</a>',
                True,
            ),
        ]

        for pattern, has_episode in fallback_patterns:
            for match in re.finditer(pattern, html_content, re.I | re.S):
                series_url, thumb, series_title = match.group(1), match.group(2), re.sub(r"<[^>]+>", "", match.group(3)).strip()
                if not series_title:
                    continue

                if has_episode:
                    episode_url = html.unescape(match.group(4))
                    episode_label = re.sub(r"<[^>]+>", "", match.group(5)).strip()
                    title = f"{series_title} - {episode_label}"
                    if episode_url in seen:
                        continue
                    seen.add(episode_url)
                    results.append({"title": title, "url": episode_url, "thumb": thumb})
                elif series_url not in seen:
                    seen.add(series_url)
                    results.append({"title": series_title, "url": series_url, "thumb": thumb})

        return results

    def _extract_next_page(self, html_content):
        for match in re.finditer(r'<a\s+([^>]+)>', html_content, re.I):
            attrs = match.group(1)
            if re.search(r'class="[^"]*(?:nextpostslink|next page-numbers|next)[^"]*"|rel="next"|aria-label="Next"', attrs, re.I):
                href_match = re.search(r'href=["\']([^"\']+)["\']', attrs, re.I)
                if href_match:
                    return html.unescape(href_match.group(1))
        return None

    def process_content(self, url):
        if not url or url == "BOOTSTRAP":
            url = self.base_url

        html_content = self._fetch(url)

        self.add_dir("[COLOR blue]Search[/COLOR]", "", 5, self.icons["search"])
        self.add_dir("[COLOR blue]Categories[/COLOR]", "CATEGORIES", 8, self.icons["categories"])
        self.add_dir("[COLOR blue]Releases[/COLOR]", "RELEASES", 8, self.icons["default"])

        items = self._extract_listing_items(html_content)
        for item in items:
            self.add_link(
                item["title"],
                item["url"],
                4,
                item["thumb"],
                self.fanart,
                info_labels={"title": item["title"]},
            )

        next_page = self._extract_next_page(html_content)
        if not next_page and url == self.base_url:
            next_page = urllib.parse.urljoin(self.base_url, "page/2/")
            
        if next_page:
            self.add_dir("[COLOR blue]Next Page >>>>[/COLOR]", next_page, 2, self.icons["default"], self.fanart)

        self.end_directory()

    def process_categories(self, url):
        html_content = self._fetch(self.base_url)
        links = []
        seen = set()
        if url == "RELEASES":
            matches = re.findall(r'href="(https://hentaidude\.xxx/release/\d{4}/)"', html_content, re.I)
            for release_url in matches:
                if release_url in seen:
                    continue
                seen.add(release_url)
                year = release_url.rstrip("/").split("/")[-1]
                links.append((year, release_url))
        else:
            matches = re.findall(r'href="(https://hentaidude\.xxx/genre/[^"]+/)"[^>]*>([^<]+)</a>', html_content, re.I)
            for genre_url, label in matches:
                genre_url = html.unescape(genre_url)
                label = html.unescape(label).strip()
                if genre_url in seen or not label:
                    continue
                seen.add(genre_url)
                links.append((label, genre_url))

        for label, target in links:
            self.add_dir(label, target, 2, self.icons["default"], self.fanart)
        self.end_directory()

    def _decode_secure_token(self, secure_token):
        decoded = secure_token.replace("sha512-", "")
        for _ in range(3):
            decoded = codecs.decode(decoded, "rot_13")
            decoded += "=" * (-len(decoded) % 4)
            decoded = base64.b64decode(decoded).decode("utf-8")
        return json.loads(decoded)

    def _resolve_playback_url(self, episode_url):
        episode_html = self._fetch(episode_url)
        iframe_match = re.search(
            r'(https://hentaidude\.xxx/wp-content/plugins/player-logic/player\.php\?data=[^"\']+)',
            episode_html,
            re.I,
        )
        if not iframe_match:
            return None

        iframe_url = html.unescape(iframe_match.group(1))
        iframe_html = self._fetch(iframe_url, referer=episode_url)

        token_match = re.search(r'<meta name="x-secure-token" content="([^"]+)"', iframe_html, re.I)
        if not token_match:
            return None

        token_data = self._decode_secure_token(token_match.group(1))
        api_root = token_data.get("uri", "")
        if api_root.startswith("//"):
            api_root = "https:" + api_root
        api_url = urllib.parse.urljoin(api_root, "api.php")

        api_response = self.session.post(
            api_url,
            data={
                "action": "zarat_get_data_player_ajax",
                "a": token_data.get("en", ""),
                "b": token_data.get("iv", ""),
            },
            headers={"Referer": episode_url},
            timeout=30,
        )
        api_response.raise_for_status()
        payload = api_response.json()

        sources = (((payload or {}).get("data") or {}).get("sources")) or []
        if not sources:
            return None
        return sources[0].get("src")

    def play_video(self, url):
        if re.search(r"/watch/[^/]+/?$", url):
            page_html = self._fetch(url)
            episode_match = re.search(
                r'href="(https://hentaidude\.xxx/watch/[^"]+/(?:episode|bonus|collection)[^"]*)"',
                page_html,
                re.I,
            )
            if episode_match:
                url = html.unescape(episode_match.group(1))

        stream_url = self._resolve_playback_url(url)
        if not stream_url:
            self.notify_error("Video source not found")
            return

        subs = []
        if stream_url and ".m3u8" in stream_url:
            try:
                m3u8_content = self._fetch(stream_url, referer=url)
                base_url = stream_url.rsplit("/", 1)[0] + "/"
                for match in re.finditer(r'#EXT-X-MEDIA:(?:.*?)URI="([^"]+\.vtt)"(?:.*?)TYPE=SUBTITLES', m3u8_content, re.I):
                    vtt_uri = match.group(1)
                    vtt_url = urllib.parse.urljoin(base_url, vtt_uri)
                    # Kodi VFS can take headers appended with |
                    vtt_url_with_headers = vtt_url + f"|Referer={urllib.parse.quote('https://hentaidude.xxx/')}"
                    subs.append(vtt_url_with_headers)
            except Exception:
                pass

        list_item = xbmcgui.ListItem(path=stream_url)
        list_item.setProperty("IsPlayable", "true")
        
        if ".m3u8" in stream_url:
            list_item.setProperty("inputstream", "inputstream.adaptive")
            list_item.setProperty("inputstream.adaptive.manifest_type", "hls")
            list_item.setMimeType("application/vnd.apple.mpegurl")
            
        if subs:
            list_item.setSubtitles(subs)
            
        xbmcplugin.setResolvedUrl(self.addon_handle, True, list_item)

    def search(self, query):
        if query:
            self.process_content(self.search_url.format(urllib.parse.quote_plus(query)))
