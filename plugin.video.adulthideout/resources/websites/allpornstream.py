# -*- coding: utf-8 -*-
import html
import json
import re
import sys
import urllib.parse

import requests
import xbmc
import xbmcgui
import xbmcplugin

from resources.lib.base_website import BaseWebsite
from resources.lib.resolvers import resolver


class AllPornStream(BaseWebsite):
    """Experimental APStream catalog scraper.

    AllPornStream is a structured catalog with actor/producer/category pages
    and public mirror embeds. It is intentionally handled as an experiment,
    not as a template for broad aggregator support.
    """

    sort_options = ["Latest", "Popular", "Top Rated"]
    sort_paths = {
        "Latest": "/",
        "Popular": "/?sort=views",
        "Top Rated": "/?sort=rating",
    }

    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="allpornstream",
            base_url="https://allpornstream.com",
            search_url="https://allpornstream.com/search?q={}",
            addon_handle=addon_handle,
            addon=addon,
        )
        self.session = requests.Session()
        self.ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        )
        self.icon = self._logo_path()

    def _logo_path(self):
        import os
        path = os.path.join(self.addon.getAddonInfo("path"), "resources", "logos", "allpornstream.png")
        return path if os.path.exists(path) else self.icon

    def _headers(self, referer=None):
        return {
            "User-Agent": self.ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "identity",
            "Referer": referer or self.base_url + "/",
        }

    def _make_request(self, url, referer=None):
        try:
            response = self.session.get(url, headers=self._headers(referer), timeout=20)
            if response.status_code == 200:
                return response.text
            self.logger.warning("[AllPornStream] HTTP %s for %s", response.status_code, url)
        except Exception as exc:
            self.logger.warning("[AllPornStream] Request failed for %s: %s", url, exc)
        return ""

    def _clean(self, text):
        if not text:
            return ""
        text = html.unescape(str(text))
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def _absolute(self, url):
        return urllib.parse.urljoin(self.base_url + "/", html.unescape(url or "").strip())

    def _proxied_image(self, src):
        if not src:
            return ""
        src = html.unescape(src)
        if src.startswith("/api/images?"):
            return self._append_image_size(src)
        if src.startswith("http"):
            return self._append_image_size(
                "/api/images?src={}&width=750&quality=75".format(urllib.parse.quote(src, safe=""))
            )
        return self._append_image_size(src)

    def _append_image_size(self, src):
        if not src:
            return self.icon
        src = html.unescape(src)
        if src.startswith("/api/images?"):
            if "width=" not in src:
                src += "&width=750&quality=70"
            return self._absolute(src)
        return self._absolute(src)

    def _slugify(self, text):
        text = html.unescape(text or "")
        text = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1-\2", text)
        text = re.sub(r"([a-z0-9])([A-Z])", r"\1-\2", text)
        text = re.sub(r"(?<=\d)(?=[A-Za-z])", "-", text)
        text = text.lower()
        text = re.sub(r"[^a-z0-9]+", "-", text)
        return text.strip("-")

    def _display_directory_name(self, text, section):
        text = html.unescape(text or "").strip()
        if section == "actors":
            return text
        text = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", text)
        text = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", text)
        text = re.sub(r"(?<=\d)(?=[A-Za-z])", " ", text)
        text = text.replace("-", " ").replace("_", " ")
        return " ".join(part.capitalize() for part in text.split())

    def _image_from_anchor(self, anchor_html, fallback=None):
        fallback = fallback or self.icon
        srcset = re.search(r'<img[^>]+srcSet="([^"]+)"', anchor_html, re.IGNORECASE)
        if srcset:
            best_url = ""
            best_width = -1
            fallback_larger_url = ""
            fallback_larger_width = 99999
            for candidate in html.unescape(srcset.group(1)).split(","):
                candidate = candidate.strip()
                if not candidate:
                    continue
                parts = candidate.rsplit(" ", 1)
                image_url = parts[0].strip()
                width = 0
                if len(parts) > 1:
                    width_match = re.search(r"(\d+)w", parts[1])
                    if width_match:
                        width = int(width_match.group(1))
                if 320 <= width <= 750 and width > best_width:
                    best_width = width
                    best_url = image_url
                elif width > 750 and width < fallback_larger_width:
                    fallback_larger_width = width
                    fallback_larger_url = image_url
            if not best_url:
                best_url = fallback_larger_url
            if best_url:
                return self._append_image_size(best_url)

        src = re.search(r'<img[^>]+src="([^"]+)"', anchor_html, re.IGNORECASE)
        if src:
            return self._append_image_size(src.group(1).split(" ")[0])
        return fallback

    def get_start_url_and_label(self):
        idx = 0
        try:
            idx = int(self.addon.getSetting("allpornstream_sort_by") or "0")
        except Exception:
            idx = 0
        if idx < 0 or idx >= len(self.sort_options):
            idx = 0
        sort_name = self.sort_options[idx]
        return self._absolute(self.sort_paths.get(sort_name, "/")), "AllPornStream [COLOR yellow]{}[/COLOR]".format(sort_name)

    def _context_menu(self):
        return [
            (
                "Sort by...",
                "RunPlugin({}?mode=7&action=select_sort&website={})".format(sys.argv[0], self.name),
            )
        ]

    def _extract_videos(self, page_html):
        items = []
        seen = set()
        for match in re.finditer(
            r'<div[^>]+data-thumb-id="([^"]+)"[^>]+data-href="([^"]+)"[^>]+data-slug="([^"]+)"[^>]+data-title="([^"]+)"([\s\S]*?)(?=<div class="group relative flex h-full|\Z)',
            page_html,
            re.IGNORECASE,
        ):
            _, href, slug, title, block = match.groups()
            video_url = self._absolute(slug or href)
            if "/post/" not in video_url or video_url in seen:
                continue
            seen.add(video_url)

            title = self._clean(title)
            if not title:
                continue

            thumb = ""
            img = re.search(r'<img[^>]+(?:src|srcSet)="([^"]+)"', block, re.IGNORECASE)
            if img:
                thumb = img.group(1).split(" ")[0]
            if not thumb:
                images = re.search(r'data-images="([^"]+)"', match.group(0), re.IGNORECASE)
                if images:
                    image_text = html.unescape(images.group(1))
                    first = re.search(r'https?://[^",\]]+', image_text)
                    if first:
                        thumb = first.group(0)
            thumb = self._append_image_size(thumb)

            duration = ""
            dur = re.search(r'<span[^>]*>\s*([0-9]{1,2}:[0-9]{2}(?::[0-9]{2})?)\s*</span>', block)
            if dur:
                duration = dur.group(1)

            label = title
            if duration:
                label += " [COLOR lime]({})[/COLOR]".format(duration)

            items.append(
                {
                    "title": label,
                    "url": video_url,
                    "thumb": thumb,
                    "info": {
                        "title": title,
                        "plot": title,
                        "duration": self.convert_duration(duration),
                    },
                }
            )
        return items

    def _extract_directory_links(self, page_html, prefix, fallback_icon=None):
        links = []
        seen = set()
        fallback_icon = fallback_icon or self.icons.get("default", self.icon)
        prefix = prefix.strip("/")
        pattern = r'<a\b(?=[^>]*href="/' + re.escape(prefix) + r'/[^"]+")[^>]*>[\s\S]*?</a>'
        for match in re.finditer(pattern, page_html, re.IGNORECASE):
            anchor = match.group(0)
            href_match = re.search(r'href="(/' + re.escape(prefix) + r'/[^"]+)"', anchor, re.IGNORECASE)
            if not href_match:
                continue
            href = href_match.group(1)

            label = ""
            title = re.search(r'title="View all videos (?:with|from|in) ([^"]+)"', anchor, re.IGNORECASE)
            if title:
                label = self._clean(title.group(1))
            if not label:
                alt = re.search(r'<img[^>]+alt="([^"]+)"', anchor, re.IGNORECASE)
                if alt:
                    label = self._clean(alt.group(1))
            if not label:
                label = self._clean(anchor)
            if not label or label.lower() in ("actors", "categories", "producers", "studios"):
                continue
            url = self._absolute(href)
            if url in seen:
                continue
            seen.add(url)
            thumb = self._image_from_anchor(anchor, fallback_icon)
            links.append((label, url, thumb))
        links.sort(key=lambda item: item[0].lower())
        return links

    def _extract_serialized_directory_items(self, page_html, section):
        key = {"actors": "actor", "categories": "category", "producers": "producer"}.get(section)
        if not key:
            return []
        text = self._decode_next_strings(page_html)
        pattern = r'\{[^{}]*"' + re.escape(key) + r'"\s*:\s*"[^"]+"[^{}]*\}'
        items = []
        seen = set()
        fallback_icon = self.icons.get(
            "pornstars" if section == "actors" else "groups" if section == "producers" else "categories",
            self.icon,
        )
        for match in re.finditer(pattern, text, re.IGNORECASE):
            try:
                data = json.loads(match.group(0))
            except Exception:
                continue
            raw_name = data.get(key) or ""
            label = self._display_directory_name(raw_name, section)
            slug = self._slugify(raw_name)
            dedupe_key = raw_name
            if not label or not slug or dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            images = data.get("thumbs_urls") or data.get("images") or []
            thumb = self._proxied_image(images[0]) if images else fallback_icon
            count = int(data.get("count") or data.get("videos_count") or 0)
            likes = int(data.get("likes") or 0)
            views = int(data.get("views") or 0)
            url = self._absolute("/{}/{}".format(section, slug))
            items.append(
                {
                    "label": label,
                    "url": url,
                    "thumb": thumb,
                    "count": count,
                    "likes": likes,
                    "views": views,
                }
            )
        return items

    def _directory_section_from_url(self, url, default_section="categories"):
        path = urllib.parse.urlparse(url or "").path.rstrip("/")
        if path.startswith("/actors"):
            return "actors"
        if path.startswith("/producers"):
            return "producers"
        if path.startswith("/categories"):
            return "categories"
        return default_section

    def _directory_mode(self, section):
        return 9 if section == "actors" else 8

    def _directory_url(self, section, params=None):
        params = params or {}
        query = urllib.parse.urlencode({k: v for k, v in params.items() if v not in (None, "")})
        url = self.base_url + "/" + section
        return url + ("?" + query if query else "")

    def _directory_params(self, url):
        parsed = urllib.parse.urlparse(url or "")
        query = urllib.parse.parse_qs(parsed.query)
        params = {}
        for key, default in (("page", "1"), ("sort", "count"), ("dir", "desc"), ("letter", ""), ("q", "")):
            params[key] = (query.get(key) or [default])[0]
        try:
            params["page"] = str(max(1, int(params["page"])))
        except Exception:
            params["page"] = "1"
        if params["sort"] not in ("count", "likes", "views", "alphabetical"):
            params["sort"] = "count"
        if params["dir"] not in ("asc", "desc"):
            params["dir"] = "desc"
        return params

    def _update_directory(self, section, params):
        url = self._directory_url(section, params)
        xbmc.executebuiltin(
            "Container.Update({}?mode={}&url={}&website={},replace)".format(
                sys.argv[0],
                self._directory_mode(section),
                urllib.parse.quote_plus(url),
                self.name,
            )
        )

    def select_directory_options(self, original_url=None):
        section = self._directory_section_from_url(original_url or "", "actors")
        params = self._directory_params(original_url or self._directory_url(section))
        sort_labels = {
            "count": "Video Count",
            "likes": "Like Count",
            "views": "View Count",
            "alphabetical": "Alphabetical",
        }
        choices = [
            "Sort: Video Count",
            "Sort: Like Count",
            "Sort: View Count",
            "Sort: Alphabetical",
            "Direction: {}".format("Ascending" if params["dir"] == "asc" else "Descending"),
            "Letter: {}".format(params["letter"] or "All"),
            "Search: {}".format(params["q"] or "None"),
            "Clear filters",
        ]
        idx = xbmcgui.Dialog().select("AllPornStream", choices)
        if idx == -1:
            return
        if idx in (0, 1, 2, 3):
            params["sort"] = ("count", "likes", "views", "alphabetical")[idx]
            params["page"] = "1"
        elif idx == 4:
            params["dir"] = "asc" if params["dir"] == "desc" else "desc"
            params["page"] = "1"
        elif idx == 5:
            letters = ["All"] + [chr(code) for code in range(ord("A"), ord("Z") + 1)]
            letter_idx = xbmcgui.Dialog().select("Letter", letters)
            if letter_idx == -1:
                return
            params["letter"] = "" if letter_idx == 0 else letters[letter_idx]
            params["page"] = "1"
        elif idx == 6:
            keyb = xbmc.Keyboard(params["q"], "Search {}".format(section.title()))
            keyb.doModal()
            if not keyb.isConfirmed():
                return
            params["q"] = keyb.getText().strip()
            params["page"] = "1"
        elif idx == 7:
            params = {"page": "1", "sort": "count", "dir": "desc", "letter": "", "q": ""}
        self._update_directory(section, params)

    def _filter_directory_items(self, items, section, params):
        letter = (params.get("letter") or "").upper()
        query = (params.get("q") or "").strip().lower()
        if letter:
            items = [item for item in items if item["label"].upper().startswith(letter)]
        if query:
            items = [item for item in items if query in item["label"].lower()]
        reverse = params.get("dir") != "asc"
        sort_key = params.get("sort") or "count"
        if sort_key == "alphabetical":
            items.sort(key=lambda item: item["label"].lower(), reverse=reverse)
        else:
            items.sort(key=lambda item: item.get(sort_key, 0), reverse=reverse)
        return items

    def _render_directory_overview(self, url, section):
        url = url or self._directory_url(section)
        params = self._directory_params(url)
        page_html = self._make_request(self.base_url + "/" + section)
        if not page_html:
            self.notify_error("Could not load {}".format(section))
            self.end_directory("videos")
            return

        items = self._extract_serialized_directory_items(page_html, section)
        if not items:
            fallback_icon = self.icons.get(
                "pornstars" if section == "actors" else "groups" if section == "producers" else "categories",
                self.icon,
            )
            items = [
                {"label": label, "url": target_url, "thumb": thumb, "count": 0, "likes": 0, "views": 0}
                for label, target_url, thumb in self._extract_directory_links(page_html, section, fallback_icon)
            ]

        filtered = self._filter_directory_items(items, section, params)
        per_page = 30
        total_pages = max(1, (len(filtered) + per_page - 1) // per_page)
        try:
            current_page = min(max(1, int(params["page"])), total_pages)
        except Exception:
            current_page = 1
        params["page"] = str(current_page)

        sort_labels = {"count": "Video Count", "likes": "Likes", "views": "Views", "alphabetical": "A-Z"}
        summary = "Options: {} {} / {} / Page {} of {}".format(
            sort_labels.get(params["sort"], "Video Count"),
            "asc" if params["dir"] == "asc" else "desc",
            params["letter"] or params["q"] or "All",
            current_page,
            total_pages,
        )
        self.add_dir(
            "[COLOR yellow]{}[/COLOR]".format(summary),
            self._directory_url(section, params),
            7,
            self.icons.get("settings", self.icon),
            action="select_directory_options",
        )

        if current_page > 1:
            previous_params = dict(params)
            previous_params["page"] = str(current_page - 1)
            self.add_dir(
                "[COLOR blue]<<< Previous Page[/COLOR]",
                self._directory_url(section, previous_params),
                self._directory_mode(section),
                self.icons.get("default", self.icon),
            )

        start = (current_page - 1) * per_page
        for item in filtered[start : start + per_page]:
            label = item["label"]
            if item.get("count"):
                label += " [COLOR gray]({} videos)[/COLOR]".format(item["count"])
            self.add_dir(label, item["url"], 2, item["thumb"])

        if current_page < total_pages:
            next_params = dict(params)
            next_params["page"] = str(current_page + 1)
            self.add_dir(
                "[COLOR blue]Next Page >>>[/COLOR]",
                self._directory_url(section, next_params),
                self._directory_mode(section),
                self.icons.get("default", self.icon),
            )

        if not filtered:
            self.notify_error("No {} found".format(section))
        self.end_directory("videos")

    def _is_directory_overview_url(self, url):
        parsed = urllib.parse.urlparse(url or "")
        return parsed.path.rstrip("/") in ("/actors", "/categories", "/producers")

    def _manual_next_page_url(self, current_url):
        parsed = urllib.parse.urlparse(current_url)
        params = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
        try:
            current_page = int((params.get("page") or ["1"])[0])
        except Exception:
            current_page = 1
        params["page"] = [str(current_page + 1)]
        query = urllib.parse.urlencode(params, doseq=True)
        return urllib.parse.urlunparse(parsed._replace(query=query))

    def _extract_next_page(self, page_html, current_url):
        links = re.findall(r'href="([^"]*(?:\?|&)page=(\d+)[^"]*)"', page_html, re.IGNORECASE)
        if not links:
            return ""
        current_page = 1
        parsed = urllib.parse.urlparse(current_url)
        params = urllib.parse.parse_qs(parsed.query)
        try:
            current_page = int((params.get("page") or ["1"])[0])
        except Exception:
            current_page = 1
        candidates = []
        for href, number in links:
            try:
                page = int(number)
            except Exception:
                continue
            if page > current_page:
                candidates.append((page, self._absolute(href)))
        if candidates:
            candidates.sort(key=lambda item: item[0])
            return candidates[0][1]
        return ""

    def _add_root_entries(self, context_menu):
        self.add_dir("Search", "", 5, self.icons.get("search", self.icon), context_menu=context_menu)
        self.add_dir("Actors", self.base_url + "/actors", 9, self.icons.get("pornstars", self.icon), context_menu=context_menu)
        self.add_dir("Categories", self.base_url + "/categories", 8, self.icons.get("categories", self.icon), context_menu=context_menu)
        self.add_dir("Producers", self.base_url + "/producers", 8, self.icons.get("groups", self.icon), context_menu=context_menu, section="producers")

    def process_content(self, url, page=1):
        if not url or url == "BOOTSTRAP":
            url, _ = self.get_start_url_and_label()

        page_html = self._make_request(url)
        if not page_html:
            self.notify_error("Could not load AllPornStream")
            self.end_directory("videos")
            return

        context_menu = self._context_menu()
        parsed = urllib.parse.urlparse(url)
        if parsed.path in ("", "/") and "page=" not in parsed.query and "q=" not in parsed.query:
            self._add_root_entries(context_menu)

        videos = self._extract_videos(page_html)
        for item in videos:
            self.add_link(
                item["title"],
                item["url"],
                4,
                item["thumb"],
                self.fanart,
                context_menu=context_menu,
                info_labels=item["info"],
            )

        next_url = self._extract_next_page(page_html, url)
        if not next_url and videos and len(videos) >= 50 and not self._is_directory_overview_url(url):
            next_url = self._manual_next_page_url(url)
        if next_url:
            self.add_dir("[COLOR blue]Next Page >>>[/COLOR]", next_url, 2, self.icons.get("default", self.icon), context_menu=context_menu)

        if not videos:
            self.notify_error("No AllPornStream videos found")
        self.end_directory("videos")

    def process_categories(self, url):
        section = self._directory_section_from_url(url or "", "categories")
        if "section=producers" in (sys.argv[2] if len(sys.argv) > 2 else ""):
            section = "producers"
        self._render_directory_overview(url or self._directory_url(section), section)

    def process_pornstars(self, url):
        self._render_directory_overview(url or self._directory_url("actors"), "actors")

    def search(self, query):
        if not query:
            return
        self.process_content(self.search_url.format(urllib.parse.quote_plus(query.strip())))

    def _decode_next_strings(self, page_html):
        chunks = []
        for raw in re.findall(r'self\.__next_f\.push\(\[1,"([\s\S]*?)"\]\)</script>', page_html):
            try:
                chunks.append(bytes(raw, "utf-8").decode("unicode_escape"))
            except Exception:
                chunks.append(raw)
        return "\n".join(chunks) if chunks else page_html

    def _extract_host_links(self, page_html):
        text = self._decode_next_strings(page_html)
        links = []
        seen = set()

        for url in re.findall(r'"embed_url"\s*:\s*"(https?://[^"]+)"', text, re.IGNORECASE):
            url = re.sub(r"\s+", "", html.unescape(url).replace("\\/", "/")).strip()
            if url and re.search(r"/[a-z]/|/embed-|/video/|/e/|/v/|/d/|/f/", url, re.IGNORECASE) and url not in seen:
                seen.add(url)
                links.append(url)

        for url in re.findall(
            r'(https?://(?:streamtape|doodstream|dood\.|dooood|miiixdrop|mixdrop|m1xdrop|voe\.sx|lulustream|lulu|mydaddy\.cc)[^\s"\'<>\\]+)',
            text,
            re.IGNORECASE,
        ):
            url = re.sub(r"\s+", "", html.unescape(url).replace("\\/", "/")).strip()
            if url and re.search(r"/[a-z]/|/embed-|/video/|/e/|/v/|/d/|/f/", url, re.IGNORECASE) and url not in seen:
                seen.add(url)
                links.append(url)

        normalised = []
        normalised_seen = set()
        for link in resolver.sort_urls_by_resolver_preference(links, self.addon):
            link = re.sub(r"(streamtape\.[^/]+)/v/", r"\1/e/", link, flags=re.IGNORECASE)
            link = re.sub(r"(doodstream\.[^/]+)/d/", r"\1/e/", link, flags=re.IGNORECASE)
            link = re.sub(r"(mixdrop\.[^/]+)/f/", r"\1/e/", link, flags=re.IGNORECASE)
            link = re.sub(r"(miiixdrop\.[^/]+)/f/", r"\1/e/", link, flags=re.IGNORECASE)
            if link in normalised_seen:
                continue
            normalised_seen.add(link)
            normalised.append(link)
        return normalised

    def _has_mydaddy_mirror(self, page_html):
        return "mydaddy.cc/video/" in self._decode_next_strings(page_html).lower()

    def resolve_recording_stream(self, url):
        page_html = self._make_request(url)
        if not page_html:
            return None
        for host_url in self._extract_host_links(page_html):
            try:
                result = resolver.resolve(host_url, referer=url, headers={"User-Agent": self.ua, "Referer": url})
                if isinstance(result, tuple):
                    stream_url, headers = result
                else:
                    stream_url, headers = result, {}
                if stream_url and stream_url.startswith("http"):
                    if resolver.resolver_preflight_enabled(self.addon) and not resolver.probe_resolved_stream(stream_url, headers):
                        continue
                    return {"url": stream_url, "headers": headers or {}, "extension": "mp4"}
            except Exception as exc:
                self.logger.warning("[AllPornStream] Resolver failed for %s: %s", host_url[:80], exc)
        if self._has_mydaddy_mirror(page_html):
            self.logger.info("[AllPornStream] MyDaddy mirror found but no playable stream resolved for %s", url)
        return None

    def play_video(self, url):
        resolved = self.resolve_recording_stream(url)
        if not resolved:
            page_html = self._make_request(url)
            if page_html and self._has_mydaddy_mirror(page_html):
                self.notify_error("MyDaddy mirror found, but no playable stream resolved")
            else:
                self.notify_error("Could not resolve any AllPornStream mirror")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return

        stream_url = resolved["url"]
        headers = resolved.get("headers") or {}
        play_url = stream_url
        if "|" not in play_url and headers:
            play_url += "|" + urllib.parse.urlencode(headers)

        list_item = xbmcgui.ListItem(path=play_url)
        list_item.setProperty("IsPlayable", "true")
        if ".m3u8" in stream_url:
            list_item.setMimeType("application/vnd.apple.mpegurl")
            list_item.setContentLookup(False)
        xbmcplugin.setResolvedUrl(self.addon_handle, True, list_item)
