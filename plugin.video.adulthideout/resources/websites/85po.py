#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
import urllib.parse
import html
import os
import xbmc
import xbmcgui
import xbmcplugin
import sys
from resources.lib.base_website import BaseWebsite
from resources.lib.proxy_utils import PlaybackGuard, ProxyController
vendor_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "lib", "vendor")
if os.path.isdir(vendor_path) and vendor_path not in sys.path:
    sys.path.insert(0, vendor_path)
try:
    import cloudscraper
except Exception:
    cloudscraper = None
try:
    import requests
except Exception:
    requests = None
try:
    from resources.lib.decoders.kvs_decoder import kvs_decode_url
except ImportError:
    kvs_decode_url = None

class Po85(BaseWebsite):
    
    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="85po",
            base_url="https://www.85po.com/en",
            search_url="https://www.85po.com/en/search/?q={}",
            addon_handle=addon_handle,
            addon=addon
        )
        self.logo = self.icon
        self.icons['default'] = self.logo
        self.icons['search'] = os.path.join(self.addon.getAddonInfo('path'), 'resources', 'logos', 'search.png')
        self.icons['categories'] = os.path.join(self.addon.getAddonInfo('path'), 'resources', 'logos', 'categories.png')
        self.ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        self.session = self._build_session()

    def _build_session(self):
        if cloudscraper:
            try:
                return cloudscraper.create_scraper(browser={"custom": self.ua})
            except Exception as exc:
                self.logger.warning("[85po] cloudscraper init failed: %s", exc)
        return requests.Session() if requests else None

    def _headers(self, referer=None):
        return {
            "User-Agent": self.ua,
            "Referer": referer or "https://www.85po.com/",
            "Origin": "https://www.85po.com",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "identity",
            "Connection": "keep-alive",
        }

    def make_request(self, url):
        self.logger.info(f"[85po] Requesting: {url}")
        if not self.session:
            self.notify_error("No HTTP session available.")
            return ""
        try:
            response = self.session.get(url, headers=self._headers(), timeout=30)
            response.raise_for_status()
            response.encoding = response.encoding or "utf-8"
            return response.text.replace("\x00", "")
        except Exception as exc:
            self.logger.error("[85po] Request failed for %s: %s", url, exc)
            return ""

    def process_content(self, url, **kwargs):
        params = {}
        if len(sys.argv) > 2 and sys.argv[2]:
            params = dict(urllib.parse.parse_qsl(sys.argv[2][1:]))
        action = params.get('action')
        
        if action == "show_related":
            self.process_related_videos(url)
            return
            
        if action == "explore_similar":
            self.explore_similar(url)
            return

        # Handle bootstrap / homepage
        if url == "BOOTSTRAP" or url == self.base_url or url == f"{self.base_url}/":
            self.add_dir("Search", "", 5, self.icons['search'], name_param=self.name)
            self.add_dir("Tags", f"{self.base_url}/tags/", 2, self.icons['categories'])
            self.get_listing(f"{self.base_url}/")
            return

        if url == f"{self.base_url}/tags/":
            self.process_tags(url)
            return

        self.get_listing(url)

    def get_listing(self, url):
        html_content = self.make_request(url)
        if not html_content:
            return self.end_directory()

        # Split content into video items
        chunks = html_content.split('<div class="thumb thumb_rel item ">')
        for chunk in chunks[1:]:
            # Extract video link, ID and Title
            match = re.search(r'<a href="([^"]+/v/(\d+)/[^"]*)" title="([^"]+)"', chunk)
            if not match:
                continue
            video_url, video_id, title = match.groups()
            title = html.unescape(title.strip())
            
            # Extract thumbnail
            thumb_match = re.search(r'data-original="([^"]+)"', chunk)
            thumb = thumb_match.group(1) if thumb_match else self.icons['default']
            
            # Extract duration
            duration_match = re.search(r'<div class="time">(?:<span[^>]*></span>)?\s*([^<]+)</div>', chunk)
            duration_sec = 0
            if duration_match:
                duration_str = duration_match.group(1).strip()
                duration_sec = self.convert_duration(duration_str)

            # Map Explore Similar context menu
            context_menu = [
                ('Explore similar', f'RunPlugin({sys.argv[0]}?mode=7&action=explore_similar&website={self.name}&original_url={urllib.parse.quote_plus(video_url)})')
            ]
            
            info_labels = {}
            if duration_sec > 0:
                info_labels['duration'] = duration_sec

            self.add_link(title, video_url, 4, thumb, self.fanart, context_menu=context_menu, info_labels=info_labels)

        # Pagination support
        pagination_match = re.search(r'<div class="pagination"[^>]*>(.*?)</div>', html_content, re.DOTALL)
        if pagination_match:
            pag_html = pagination_match.group(1)
            # Find next page index from KVS data parameters
            next_matches = re.findall(r'(?:from_videos\+from_albums|from):(\d+)', pag_html)
            if next_matches:
                pages = sorted(list(set([int(p) for p in next_matches])))
                active_match = re.search(r'<a class="active[^>]*>(\d+)</a>', pag_html)
                current_page = int(active_match.group(1)) if active_match else 1
                next_page = current_page + 1
                
                if next_page in pages or any(p >= next_page for p in pages):
                    if "/search/" in url:
                        # Append from_videos query param
                        parsed = urllib.parse.urlparse(url)
                        query_params = urllib.parse.parse_qs(parsed.query)
                        query_params['from_videos'] = [str(next_page)]
                        next_url = parsed._replace(query=urllib.parse.urlencode(query_params, doseq=True)).geturl()
                    elif "/tags/" in url:
                        # URL format is https://www.85po.com/tags/[TAG]/[PAGE]/
                        parsed = urllib.parse.urlparse(url)
                        path_parts = [p for p in parsed.path.split('/') if p]
                        if path_parts[-1].isdigit():
                            path_parts[-1] = str(next_page)
                        else:
                            path_parts.append(str(next_page))
                        next_url = parsed._replace(path='/' + '/'.join(path_parts) + '/').geturl()
                    else:
                        next_url = f"{self.base_url}/latest-updates/{next_page}/"
                        
                    self.add_dir("Next Page >>>>", next_url, 2, self.icons['default'])

        self.end_directory()

    def process_tags(self, url):
        html_content = self.make_request(url)
        if not html_content:
            return self.end_directory()

        # Find tags wrapped in list structure
        tag_matches = re.findall(r'href="(https://www\.85po\.com/(?:en/)?tags/([^/]+)/)"[^>]*>\s*<span>([^<]+)</span>', html_content)
        for link, slug, name in tag_matches:
            name = html.unescape(name.strip())
            self.add_dir(name, link, 2, self.icons['categories'])

        self.end_directory()

    def play_video(self, url):
        self.logger.info(f"[85po] play_video for {url}")
        resolved = self.resolve_recording_stream(url)
        if not resolved or not resolved.get("url"):
            self.logger.error("[85po] No playable direct stream links found")
            self.notify_error("No playable streams found.")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return

        resolved_url = resolved["url"]
        headers = resolved.get("headers") or {}
        playback_path = resolved_url + "|" + urllib.parse.urlencode(headers)
        playback_controller = None

        try:
            playback_controller = ProxyController(
                upstream_url=resolved_url,
                upstream_headers=headers,
                cookies=self.session.cookies.get_dict() if self.session else None,
                session=self.session,
                probe_size=True,
            )
            playback_path = playback_controller.start()
            self.logger.info("[85po] Using in-process Range proxy for playback")
        except Exception as exc:
            self.logger.warning("[85po] Range proxy failed, falling back direct: %s", exc)

        self.logger.info(f"[85po] Resolved stream URL with headers/proxy: {playback_path[:120]}...")
        liz = xbmcgui.ListItem(path=playback_path)
        liz.setProperty('IsPlayable', 'true')
        liz.setMimeType('video/mp4')
        liz.setContentLookup(False)
        xbmcplugin.setResolvedUrl(self.addon_handle, True, listitem=liz)
        if playback_controller:
            PlaybackGuard(xbmc.Player(), xbmc.Monitor(), playback_path, playback_controller).start()

    def resolve_recording_stream(self, url):
        html_content = self.make_request(url)
        if not html_content:
            return None
            
        # Extract license code
        license_match = re.search(r"license_code:\s*'([^']+)'", html_content, re.IGNORECASE)
        license_code = license_match.group(1).strip() if license_match else ""
        
        # Search for direct mp4 links in KVS player flashvars
        video_url_match = re.search(r"video_url:\s*'([^']+)'", html_content, re.IGNORECASE)
        video_alt_url_match = re.search(r"video_alt_url:\s*'([^']+)'", html_content, re.IGNORECASE)
        
        scrambled_links = []
        if video_url_match:
            scrambled_links.append((html.unescape(video_url_match.group(1).strip()), 360))
        if video_alt_url_match:
            scrambled_links.append((html.unescape(video_alt_url_match.group(1).strip()), 720))
            
        if not scrambled_links:
            # Fallback to direct MP4 links matching get_file
            mp4_links = re.findall(r'https?://[^"\s\'>]+/get_file/[^"\s\'>]+\.mp4[^"\s\'>]*', html_content)
            if mp4_links:
                scrambled_links = [(html.unescape(l), 360) for l in set(mp4_links)]

        resolved_url = ""
        if scrambled_links:
            # Sort by quality descending (prefer 720p over 360p)
            scrambled_links.sort(key=lambda x: x[1], reverse=True)
            best_scrambled = scrambled_links[0][0]
            
            if best_scrambled.startswith("function/0/") and kvs_decode_url is not None and license_code:
                try:
                    resolved_url = kvs_decode_url(best_scrambled, license_code)
                    self.logger.info(f"[85po] Decoded KVS URL successfully")
                except Exception as e:
                    self.logger.error(f"[85po] Failed to decode KVS URL: {e}")
                    # Fallback to stripping function/0/
                    resolved_url = best_scrambled[len("function/0/"):]
            else:
                resolved_url = best_scrambled
                if resolved_url.startswith("function/0/"):
                    resolved_url = resolved_url[len("function/0/"):]
                
        if not resolved_url:
            return None

        headers = {
            "User-Agent": self.ua,
            "Referer": url,
            "Origin": "https://www.85po.com",
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "identity",
        }
        cookies = self.session.cookies.get_dict() if self.session else {}
        if cookies:
            headers["Cookie"] = "; ".join("{}={}".format(key, value) for key, value in cookies.items())
        return {"url": resolved_url, "headers": headers, "extension": "mp4"}

    def explore_similar(self, original_url=None):
        if not original_url:
            self.notify_info("No video URL available")
            return

        html_content = self.make_request(original_url)
        if not html_content:
            self.notify_error("Could not load video info")
            return

        from resources.lib.lookup_info import choose_and_open, extract_html_items

        # Extract tags
        patterns = [
            ("Tag", r'href="(https://www\.85po\.com/(?:en/)?tags/([^/]+)/)"[^>]*>([^<]+)', 3),
        ]
        tag_items = extract_html_items(html_content, self.base_url, patterns)
        
        seen_urls = set()
        items = []
        for item in tag_items:
            if item["url"] not in seen_urls:
                items.append(item)
                seen_urls.add(item["url"])

        # Add the related videos ajax overlay as dynamic Playback item
        video_id_match = re.search(r'/v/(\d+)/', original_url)
        if video_id_match:
            video_id = video_id_match.group(1)
            related_url = f"{self.base_url}/related_videos_html/{video_id}/"
            
            lang = xbmc.getLanguage(0).lower()
            if "german" in lang or "deutsch" in lang:
                group = "Wiedergabe"
                label = "[COLOR lime]>>> Show similar videos <<<[/COLOR]"
            elif "spanish" in lang or "español" in lang or "espanol" in lang:
                group = "Reproducción"
                label = "[COLOR lime]>>> Mostrar videos similares <<<[/COLOR]"
            elif "french" in lang or "français" in lang or "francais" in lang:
                group = "Lecture"
                label = "[COLOR lime]>>> Afficher les vidéos similaires <<<[/COLOR]"
            else:
                group = "Playback"
                label = "[COLOR lime]>>> Show Similar Videos <<<[/COLOR]"
                
            items.insert(0, {
                "group": group,
                "label": label,
                "url": related_url,
                "mode": 2,
                "action": "show_related"
            })

        if not choose_and_open(items, self.name, "Explore similar"):
            self.logger.info("[85po] No lookup target selected for {}".format(original_url))

    def process_related_videos(self, url):
        html_content = self.make_request(url)
        if not html_content:
            return self.end_directory()

        # Parse player related videos overlay
        chunks = html_content.split('<a href="https://www.85po.com/v/')
        for chunk in chunks[1:]:
            match = re.search(r'^(\d+/[^"]*)"[^>]*title="([^"]+)"', chunk)
            if not match:
                continue
            slug, title = match.groups()
            video_url = f"{self.base_url}/v/{slug}"
            title = html.unescape(title.strip())
            
            # Extract thumbnail
            thumb_match = re.search(r"url\('([^']+)'\)", chunk) or re.search(r'src="([^"]+)"', chunk)
            thumb = thumb_match.group(1) if thumb_match else self.icons['default']
            
            # Extract duration
            duration_match = re.search(r'<span class="duration">([^<]+)</span>', chunk)
            duration_sec = 0
            if duration_match:
                duration_str = duration_match.group(1).strip()
                duration_sec = self.convert_duration(duration_str)

            context_menu = [
                ('Explore similar', f'RunPlugin({sys.argv[0]}?mode=7&action=explore_similar&website={self.name}&original_url={urllib.parse.quote_plus(video_url)})')
            ]
            
            info_labels = {}
            if duration_sec > 0:
                info_labels['duration'] = duration_sec

            self.add_link(title, video_url, 4, thumb, self.fanart, context_menu=context_menu, info_labels=info_labels)

        self.end_directory()
