# -*- coding: utf-8 -*-
import html
import re
import sys
import urllib.parse

import requests
import xbmc
import xbmcgui
import xbmcplugin

from resources.lib.base_website import BaseWebsite
from resources.lib.resilient_http import fetch_text


class Pornslash(BaseWebsite):
    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="pornslash",
            base_url="https://www.pornslash.com",
            search_url="https://www.pornslash.com/search/{}",
            addon_handle=addon_handle,
            addon=addon,
        )
        self.ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/126.0.0.0 Safari/537.36"
        )
        self.session = requests.Session()
        self.content_options = ["Straight", "Gay", "Shemale"]
        self.sort_options = ["Trending", "New"]

    def make_request(self, url, referer=None):
        headers = {
            "User-Agent": self.ua,
            "Referer": referer or (self.base_url + "/"),
        }
        return fetch_text(
            url,
            headers=headers,
            scraper=self.session,
            logger=self.logger,
            timeout=20,
        )

    def _get_content_key(self):
        try:
            idx = int(self.addon.getSetting("pornslash_content_type") or "0")
        except Exception:
            idx = 0
        if not 0 <= idx < len(self.content_options):
            idx = 0
        return self.content_options[idx]

    def _get_sort_key(self):
        try:
            idx = int(self.addon.getSetting("pornslash_sort_by") or "0")
        except Exception:
            idx = 0
        if not 0 <= idx < len(self.sort_options):
            idx = 0
        return self.sort_options[idx]

    def _get_listing_base(self):
        content_key = self._get_content_key()
        sort_key = self._get_sort_key()
        content_paths = {
            "Straight": "",
            "Gay": "/gay",
            "Shemale": "/shemale",
        }
        sort_suffix = {
            "Trending": "",
            "New": "/videos/new",
        }
        base = content_paths.get(content_key, "")
        suffix = sort_suffix.get(sort_key, "")
        if suffix:
            return urllib.parse.urljoin(self.base_url, base + suffix)
        return urllib.parse.urljoin(self.base_url, base or "/")

    def _get_categories_url(self):
        content_key = self._get_content_key()
        path_map = {
            "Straight": "/categories",
            "Gay": "/categories/gay",
            "Shemale": "/categories/shemale",
        }
        return urllib.parse.urljoin(self.base_url, path_map.get(content_key, "/categories"))

    def _get_pornstars_url(self):
        content_key = self._get_content_key()
        path_map = {
            "Straight": "/pornstars",
            "Gay": "/pornstars/gay",
            "Shemale": "/pornstars/shemale",
        }
        return urllib.parse.urljoin(self.base_url, path_map.get(content_key, "/pornstars"))

    def get_start_url_and_label(self):
        content_key = self._get_content_key()
        sort_key = self._get_sort_key()
        return self._get_listing_base(), f"PornSlash [COLOR yellow]({content_key} - {sort_key})[/COLOR]"

    def _get_standard_context_menu(self):
        return [
            (
                "Select Content",
                f"RunPlugin({sys.argv[0]}?mode=7&action=select_content_type&website={self.name})",
            ),
            (
                "Sort by...",
                f"RunPlugin({sys.argv[0]}?mode=7&action=select_sort_order&website={self.name})",
            ),
        ]

    def _get_pornstar_filters(self, url=None):
        target_url = url or self._get_pornstars_url()
        content = self.make_request(target_url)
        if not content:
            return {}

        pattern = re.compile(
            r'<div class="select-menu" data-name=([a-z_]+)>.*?'
            r'<div class="selected-item">([^<]+)</div>.*?'
            r'<div class="select-items">(.*?)</div>',
            re.IGNORECASE | re.DOTALL,
        )

        filters = {}
        for filter_name, selected_label, options_html in pattern.findall(content):
            options = re.findall(
                r"class='select-item(?: active)?' href='([^']+)' data-value='([^']*)'>([^<]+)</a>",
                options_html,
                re.IGNORECASE,
            )
            if not options:
                continue
            filters[filter_name] = {
                "label": selected_label.split(":", 1)[0].strip(),
                "options": [
                    (
                        urllib.parse.urljoin(self.base_url, href.strip()),
                        value,
                        html.unescape(title.strip()),
                    )
                    for href, value, title in options
                ],
            }
        return filters

    def _get_pornstar_context_menu(self, original_url=None):
        base_url = original_url or self._get_pornstars_url()
        items = [
            (
                "Select Content",
                f"RunPlugin({sys.argv[0]}?mode=7&action=select_content_type&website={self.name})",
            )
        ]
        for filter_name, data in self._get_pornstar_filters(base_url).items():
            items.append(
                (
                    f"Filter by {data['label']}...",
                    "RunPlugin({}?mode=7&action=select_pornstar_filter&website={}&filter_type={}&original_url={})".format(
                        sys.argv[0],
                        self.name,
                        urllib.parse.quote_plus(filter_name),
                        urllib.parse.quote_plus(base_url),
                    ),
                )
            )
        if len(items) > 1:
            items.append(
                (
                    "[COLOR yellow]Reset Filters[/COLOR]",
                    "RunPlugin({}?mode=7&action=reset_pornstar_filters&website={}&original_url={})".format(
                        sys.argv[0],
                        self.name,
                        urllib.parse.quote_plus(base_url),
                    ),
                )
            )
        return items

    def _add_main_dirs(self, standard_context=None, pornstar_context=None, in_pornstars=False):
        self.add_dir("Search", "", 5, self.icons.get("search", self.icon), context_menu=standard_context)
        self.add_dir(
            "Categories",
            self._get_categories_url(),
            8,
            self.icons.get("categories", self.icon),
            context_menu=standard_context,
        )
        self.add_dir(
            "Pornstars",
            self._get_pornstars_url(),
            2,
            self.icons.get("pornstars", self.icon),
            context_menu=pornstar_context if in_pornstars else None,
        )

    def select_content_type(self, original_url=None):
        try:
            preselect_idx = self.content_options.index(self._get_content_key())
        except ValueError:
            preselect_idx = 0

        dialog = xbmcgui.Dialog()
        idx = dialog.select("Content Type...", self.content_options, preselect=preselect_idx)
        if idx == -1:
            return

        self.addon.setSetting("pornslash_content_type", str(idx))
        new_url, _ = self.get_start_url_and_label()
        xbmc.executebuiltin(
            f"Container.Update({sys.argv[0]}?mode=2&website={self.name}&url={urllib.parse.quote_plus(new_url)})"
        )

    def select_sort_order(self, original_url=None):
        try:
            preselect_idx = self.sort_options.index(self._get_sort_key())
        except ValueError:
            preselect_idx = 0

        dialog = xbmcgui.Dialog()
        idx = dialog.select("Sort by...", self.sort_options, preselect=preselect_idx)
        if idx == -1:
            return

        self.addon.setSetting("pornslash_sort_by", str(idx))
        new_url, _ = self.get_start_url_and_label()
        xbmc.executebuiltin(
            f"Container.Update({sys.argv[0]}?mode=2&website={self.name}&url={urllib.parse.quote_plus(new_url)})"
        )

    def _get_search_url(self, query):
        content_key = self._get_content_key()
        q = urllib.parse.quote_plus(query)
        if content_key == "Gay":
            return f"{self.base_url}/gay/search/{q}"
        if content_key == "Shemale":
            return f"{self.base_url}/shemale/search/{q}"
        return self.search_url.format(q)

    def search(self, query):
        if not query:
            return
        self.process_content(self._get_search_url(query))

    def process_content(self, url):
        if url == "BOOTSTRAP":
            url, _ = self.get_start_url_and_label()

        parsed = urllib.parse.urlparse(url)
        path = parsed.path.rstrip("/")
        standard_context = self._get_standard_context_menu()
        in_pornstars = path.startswith("/pornstars") or path.startswith("/pornstar/")
        pornstar_context = self._get_pornstar_context_menu(url) if in_pornstars else None

        if path.startswith("/pornstars"):
            self._add_main_dirs(
                standard_context=standard_context,
                pornstar_context=pornstar_context,
                in_pornstars=True,
            )
            return self.process_pornstars(url)

        if path.startswith("/pornstar/"):
            self._add_main_dirs(
                standard_context=standard_context,
                pornstar_context=pornstar_context,
                in_pornstars=True,
            )
            return self._list_videos(url, context_menu=standard_context)

        self._add_main_dirs(standard_context=standard_context, pornstar_context=pornstar_context, in_pornstars=False)
        self._list_videos(url, context_menu=standard_context)

    def _extract_watch_ids(self, content):
        ids = []
        for watch_id in re.findall(r'/watch/([A-Za-z0-9]+)', content, re.IGNORECASE):
            if watch_id not in ids:
                ids.append(watch_id)
        return ids

    def _extract_pornstar_ids(self, content):
        ids = []
        for slug in re.findall(r'/pornstar/([a-z0-9-]+)', content, re.IGNORECASE):
            if slug not in ids:
                ids.append(slug)
        return ids

    def _get_page_num(self, url):
        parsed = urllib.parse.urlparse(url)
        query = urllib.parse.parse_qs(parsed.query)
        try:
            return int((query.get("p") or ["1"])[0])
        except Exception:
            return 1

    def _set_page_num(self, url, page_num):
        parsed = urllib.parse.urlparse(url)
        query = urllib.parse.parse_qs(parsed.query)
        query["p"] = [str(page_num)]
        new_query = urllib.parse.urlencode(query, doseq=True)
        return urllib.parse.urlunparse(
            (parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment)
        )

    def _has_next_page(self, current_url, current_ids):
        if not current_ids:
            return None

        page_size = 25 if ("/search/" in current_url or "/cat/" in current_url) else 50
        if len(current_ids) < page_size:
            return None

        next_url = self._set_page_num(current_url, self._get_page_num(current_url) + 1)
        next_content = self.make_request(next_url, referer=current_url)
        if not next_content:
            return None

        next_ids = self._extract_watch_ids(next_content)
        if not next_ids:
            return None

        if next_ids[:5] == current_ids[:5]:
            return None
        return next_url

    def _has_next_pornstar_page(self, current_url, current_ids):
        if not current_ids or len(current_ids) < 30:
            return None

        next_url = self._set_page_num(current_url, self._get_page_num(current_url) + 1)
        next_content = self.make_request(next_url, referer=current_url)
        if not next_content:
            return None

        next_ids = self._extract_pornstar_ids(next_content)
        if not next_ids or next_ids[:5] == current_ids[:5]:
            return None
        return next_url

    def _list_videos(self, url, context_menu=None):
        content = self.make_request(url)
        if not content:
            return self.end_directory("videos")

        blocks = re.split(r'<div class="video-item">', content)[1:]
        seen = set()
        current_ids = []

        for block in blocks:
            link_match = re.search(r'<a href="(/watch/[A-Za-z0-9]+)"', block, re.IGNORECASE)
            title_match = re.search(r'data-title="([^"]+)"', block, re.IGNORECASE)
            if not title_match:
                title_match = re.search(
                    r'<h2 class="video-title">\s*<a [^>]*title="([^"]+)"',
                    block,
                    re.IGNORECASE | re.DOTALL,
                )
            if not title_match:
                title_match = re.search(r'<img [^>]*alt="([^"]+)"', block, re.IGNORECASE)
            if not (link_match and title_match):
                continue

            video_url = urllib.parse.urljoin(self.base_url, link_match.group(1))
            if video_url in seen:
                continue
            seen.add(video_url)

            watch_id = link_match.group(1).rsplit("/", 1)[-1]
            current_ids.append(watch_id)

            thumb_match = re.search(r'<img [^>]*src="([^"]+)"', block, re.IGNORECASE)
            duration_match = re.search(r'<div class="duration">\s*([^<]+)\s*</div>', block, re.IGNORECASE)

            title = html.unescape(title_match.group(1).strip())
            thumb = thumb_match.group(1).strip() if thumb_match else ""
            if thumb.startswith("//"):
                thumb = "https:" + thumb
            elif thumb.startswith("/"):
                thumb = urllib.parse.urljoin(self.base_url, thumb)

            info = {"title": title, "plot": title}
            duration = duration_match.group(1).strip() if duration_match else ""
            duration_seconds = self.convert_duration(duration)
            if duration_seconds:
                info["duration"] = duration_seconds

            self.add_link(
                title,
                video_url,
                4,
                thumb or self.icon,
                self.fanart,
                info_labels=info,
                context_menu=context_menu,
            )

        next_url = self._has_next_page(url, current_ids)
        if next_url:
            self.add_dir("Next Page", next_url, 2, self.icons.get("default", self.icon), context_menu=context_menu)

        self.end_directory("videos")

    def process_categories(self, url):
        categories_url = self._get_categories_url()
        if url != categories_url:
            return self._list_videos(url)

        content = self.make_request(categories_url)
        if not content:
            return self.end_directory("videos")

        seen = set()
        cat_pattern = re.compile(
            r'<a class="cat-item" href="(/cat/[^"]+)".*?'
            r'<img class="cat-poster-img" src="([^"]+)".*?'
            r'<div class="cat-name">\s*([^<]+)\s*</div>',
            re.IGNORECASE | re.DOTALL,
        )

        for path, thumb, title in cat_pattern.findall(content):
            full_url = urllib.parse.urljoin(self.base_url, path)
            if full_url in seen:
                continue
            seen.add(full_url)

            if thumb.startswith("//"):
                thumb = "https:" + thumb
            elif thumb.startswith("/"):
                thumb = urllib.parse.urljoin(self.base_url, thumb)

            self.add_dir(html.unescape(title.strip()), full_url, 2, thumb or self.icons.get("categories", self.icon))

        self.end_directory("videos")

    def process_pornstars(self, url):
        content = self.make_request(url, referer=self._get_pornstars_url())
        if not content:
            return self.end_directory("videos")

        blocks = re.split(r'<div class="model-item">', content)[1:]
        seen = set()
        current_ids = []
        context_menu = self._get_pornstar_context_menu(url)

        for block in blocks:
            url_match = re.search(r'<a class="poster-wrapper" href="(/pornstar/[a-z0-9-]+)"', block, re.IGNORECASE)
            title_match = re.search(r'<div class="model-name">\s*<a [^>]*>([^<]+)</a>', block, re.IGNORECASE | re.DOTALL)
            if not title_match:
                title_match = re.search(r'<img class="poster-img" [^>]*alt="([^"]+)"', block, re.IGNORECASE)
            thumb_match = re.search(r'<img class="poster-img" src="([^"]+)"', block, re.IGNORECASE)
            if not (url_match and title_match):
                continue

            full_url = urllib.parse.urljoin(self.base_url, url_match.group(1))
            if full_url in seen:
                continue
            seen.add(full_url)
            current_ids.append(url_match.group(1).rsplit("/", 1)[-1])

            thumb = thumb_match.group(1).strip() if thumb_match else ""
            if thumb.startswith("//"):
                thumb = "https:" + thumb
            elif thumb.startswith("/"):
                thumb = urllib.parse.urljoin(self.base_url, thumb)

            title = html.unescape(title_match.group(1).strip())
            self.add_dir(title, full_url, 2, thumb or self.icons.get("pornstars", self.icon), context_menu=context_menu)

        next_url = self._has_next_pornstar_page(url, current_ids)
        if next_url:
            self.add_dir("Next Page", next_url, 2, self.icons.get("default", self.icon), context_menu=context_menu)

        self.end_directory("videos")

    def select_pornstar_filter(self, filter_name, original_url=None):
        # mode=7 dispatch in default.py passes filter_type specially; recover
        # gracefully if an older cached context menu still uses filter_name.
        filter_name = urllib.parse.unquote_plus(filter_name or "")
        if filter_name.startswith("http://") or filter_name.startswith("https://"):
            original_url = filter_name
            filter_name = ""
        if not filter_name and len(sys.argv) > 2:
            try:
                query_params = urllib.parse.parse_qs(sys.argv[2].lstrip("?"))
                filter_name = urllib.parse.unquote_plus(
                    (query_params.get("filter_type") or query_params.get("filter_name") or [""])[0]
                )
            except Exception:
                filter_name = ""

        current_url = urllib.parse.unquote_plus(original_url or self._get_pornstars_url())
        filters = self._get_pornstar_filters(current_url)
        if filter_name not in filters:
            return

        data = filters[filter_name]
        options = [label for _, _, label in data["options"]]

        parsed = urllib.parse.urlparse(current_url)
        current_query = urllib.parse.parse_qs(parsed.query)
        current_value = (current_query.get(filter_name) or [""])[0]
        preselect_idx = 0
        for idx, (_, value, _) in enumerate(data["options"]):
            if value == current_value:
                preselect_idx = idx
                break

        idx = xbmcgui.Dialog().select(f"{data['label']}...", options, preselect=preselect_idx)
        if idx == -1:
            return

        new_url = data["options"][idx][0]
        xbmc.executebuiltin(
            f"Container.Update({sys.argv[0]}?mode=2&website={self.name}&url={urllib.parse.quote_plus(new_url)})"
        )

    def reset_pornstar_filters(self, original_url=None):
        parsed = urllib.parse.urlparse(urllib.parse.unquote_plus(original_url or self._get_pornstars_url()))
        new_url = urllib.parse.urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, "", parsed.fragment))
        xbmc.executebuiltin(
            f"Container.Update({sys.argv[0]}?mode=2&website={self.name}&url={urllib.parse.quote_plus(new_url)})"
        )

    def _select_variant_playlist(self, master_url, referer, preferred_quality=None):
        manifest = self.make_request(master_url, referer=referer)
        if not manifest:
            return master_url

        variants = []
        lines = [line.strip() for line in manifest.splitlines() if line.strip()]
        for idx, line in enumerate(lines):
            if not line.startswith("#EXT-X-STREAM-INF:"):
                continue

            quality = 0
            q_match = re.search(r'NAME="(\d+)p"', line, re.IGNORECASE)
            if q_match:
                quality = int(q_match.group(1))
            else:
                res_match = re.search(r'RESOLUTION=\d+x(\d+)', line, re.IGNORECASE)
                if res_match:
                    quality = int(res_match.group(1))

            if idx + 1 < len(lines) and not lines[idx + 1].startswith("#"):
                playlist_url = urllib.parse.urljoin(master_url, lines[idx + 1])
                variants.append((quality, playlist_url))

        if not variants:
            return master_url

        variants.sort(key=lambda item: item[0])
        if preferred_quality:
            for quality, playlist_url in reversed(variants):
                if quality <= preferred_quality:
                    return playlist_url
        return variants[-1][1]

    def play_video(self, url):
        content = self.make_request(url, referer=self.base_url + "/")
        if not content:
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return

        hls_match = re.search(r'loadSource\("([^"]+)"\)', content, re.IGNORECASE)
        if not hls_match:
            embed_match = re.search(r'property="og:video:url" content="([^"]+)"', content, re.IGNORECASE)
            if embed_match:
                embed_url = html.unescape(embed_match.group(1))
                embed_content = self.make_request(embed_url, referer=url)
                if embed_content:
                    hls_match = re.search(r'loadSource\("([^"]+)"\)', embed_content, re.IGNORECASE)

        if not hls_match:
            self.logger.error("[PornSlash] No HLS source found")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return

        preferred_quality = 0
        quality_match = re.search(r'data-quality="(\d+)"', content, re.IGNORECASE)
        if quality_match:
            preferred_quality = int(quality_match.group(1))

        hls_url = html.unescape(hls_match.group(1).strip())
        hls_url = self._select_variant_playlist(hls_url, referer=url, preferred_quality=preferred_quality)
        headers = urllib.parse.urlencode({"User-Agent": self.ua, "Referer": url})
        list_item = xbmcgui.ListItem(path=f"{hls_url}|{headers}")
        list_item.setProperty("IsPlayable", "true")
        list_item.setMimeType("application/vnd.apple.mpegurl")
        list_item.setContentLookup(False)
        xbmcplugin.setResolvedUrl(self.addon_handle, True, list_item)
