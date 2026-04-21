import re
import os
import base64
import json
import sys
import time
import urllib.parse
import urllib.request
import xbmc
import xbmcgui
import xbmcplugin
from resources.lib.base_website import BaseWebsite
from resources.lib.resilient_http import fetch_text

try:
    import xbmcaddon
    addon_path = xbmcaddon.Addon().getAddonInfo('path')
    vendor_path = os.path.join(addon_path, 'resources', 'lib', 'vendor')
    if vendor_path not in sys.path:
        sys.path.insert(0, vendor_path)
except Exception:
    pass

try:
    import cloudscraper
    HAS_CLOUDSCRAPER = True
except ImportError:
    HAS_CLOUDSCRAPER = False


class LetmejerkWebsite(BaseWebsite):
    BASE_URL = "https://www.letmejerk.com"

    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="letmejerk",
            base_url=self.BASE_URL,
            search_url="https://www.letmejerk.com/search.php?q={}",
            addon_handle=addon_handle,
            addon=addon
        )
        self.sort_options = ["Popular", "Latest", "Top Rated"]
        self.sort_paths = {
            0: "/?sort=pop",
            1: "/?sort=latest",
            2: "/?sort=top"
        }
        self.icon = os.path.join(self.addon.getAddonInfo('path'), 'resources', 'logos', 'letmejerk.png')

        self.ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        if HAS_CLOUDSCRAPER:
            self.session = cloudscraper.create_scraper(
                browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True}
            )
        else:
            self.session = None

    def get_start_url_and_label(self):
        sort_id = f"{self.name}_sort_by"
        sort_index = int(self.addon.getSetting(sort_id) or '0')
        path = self.sort_paths.get(sort_index, "/?sort=pop")
        label = f"LetMeJerk - {self.sort_options[sort_index]}"
        return f"{self.BASE_URL}{path}", label

    def make_request(self, url, method='GET', data=None, headers=None):
        try:
            req_headers = {
                'User-Agent': self.ua,
                'Referer': self.BASE_URL
            }
            if headers:
                req_headers.update(headers)

            if method != 'POST':
                html = fetch_text(
                    url,
                    headers=req_headers,
                    scraper=self.session,
                    logger=None,
                    timeout=20,
                )
                if html:
                    return html
            elif self.session:
                self.session.headers.update(req_headers)
                try:
                    r = self.session.post(url, data=data, timeout=20)
                    if r.status_code == 200:
                        return r.text
                except Exception as post_exc:
                    xbmc.log(f"[letmejerk] session POST failed, falling back to urllib: {post_exc}", xbmc.LOGWARNING)

                if data:
                    data_bytes = urllib.parse.urlencode(data).encode('utf-8')
                    req = urllib.request.Request(url, data=data_bytes, headers=req_headers)
                else:
                    req = urllib.request.Request(url, headers=req_headers)
                
                with urllib.request.urlopen(req, timeout=20) as resp:
                    return resp.read().decode('utf-8')
        except Exception as e:
            xbmc.log(f"[letmejerk] make_request error: {e}", xbmc.LOGWARNING)
        return None

    def process_content(self, url):
        self.add_basic_dirs(url)
        self.process_video_list(url)

    def add_basic_dirs(self, current_url):
        self.add_dir('[COLOR blue]Search[/COLOR]', '', 5, self.icons.get('search'))
        self.add_dir('Categories', f'{self.BASE_URL}/cats', 8, self.icons.get('categories'))
        self.add_dir('Pornstars', f'{self.BASE_URL}/az-pornstars', 8, self.icons.get('default'))

    # ─── THUMBNAIL HELPERS ────────────────────────────────────────────────────

    def _decode_preview_data(self, content):
        """
        LetMeJerk embeds a base64 blob in the listing page JS that maps
        img IDs to real thumbnail URLs.
        """
        thumb_map = {}
        # The longest base64 string (>500 chars) usually contains the data
        b64_matches = re.findall(r"'([A-Za-z0-9+/]{100,}={0,2})'", content)
        for b64 in b64_matches:
            try:
                decoded = base64.b64decode(b64 + '==').decode('utf-8', errors='ignore')
                if ';xv;' in decoded or ';ph;' in decoded:
                    for item in decoded.split('|'):
                        parts = item.split(';')
                        if len(parts) >= 3:
                            img_id = parts[0].strip()
                            thumb   = parts[2].strip()
                            if thumb.startswith('http'):
                                thumb_map[img_id] = thumb
                    if thumb_map:
                        break
            except Exception:
                pass
        return thumb_map

    # ─── VIDEO LIST ───────────────────────────────────────────────────────────

    def process_video_list(self, url):
        content = self.make_request(url)
        if not content:
            self.notify_error("Failed to load LetMeJerk page")
            self.end_directory()
            return

        thumb_map = self._decode_preview_data(content)
        
        # Search thumbnails fallback map
        search_thumb_map = {
            m[0]: m[1] for m in re.findall(r'<img id="search_(\d+)"[^>]*src="([^"]+)"', content)
        }
        
        # Parse video cards: <a href...> <img id="...">
        card_pattern = re.compile(
            r'<a href="(/[A-Za-z0-9]+/[^"]+)"[^>]*class="th-image"[^>]*title="([^"]+)"[^>]*>\s*'
            r'<img id="(?:search_)?(\d+)"',
            re.DOTALL
        )
        matches = card_pattern.findall(content)

        if not matches:
             simple = re.compile(
                r'<a href="(/[A-Za-z0-9]+/[^"]+)"[^>]*class="th-image"[^>]*title="([^"]+)"'
             )
             matches = [(path, title, '') for path, title in simple.findall(content)]

        if not matches:
            modern = re.compile(
                r'<div\s+class="thumb">\s*'
                r'<a\s+href="(/[A-Za-z0-9]+/[^"]+)"[^>]*>.*?'
                r'<img[^>]+(?:data-src|src)="([^"]+)"[^>]+alt="([^"]+)"',
                re.DOTALL | re.IGNORECASE
            )
            matches = [(path, title, '') for path, _thumb, title in modern.findall(content)]
            search_thumb_map.update({
                path: thumb for path, thumb, title in modern.findall(content)
            })

        seen = set()
        count = 0
        
        for path, title, img_id in matches:
            title = title.replace('&#039;', "'").replace('&amp;', '&')
            video_url = f"{self.BASE_URL}{path}" if not path.startswith('http') else path
            
            if video_url in seen:
                continue
            seen.add(video_url)

            thumb = thumb_map.get(img_id) or search_thumb_map.get(img_id) or search_thumb_map.get(path) or self.icons.get('default', '')
            
            self.add_link(title, video_url, 4, thumb, self.fanart)
            count += 1

        if count > 0:
            self._add_next_page(url, count)
        else:
            self.notify_error("No videos found on LetMeJerk")

        self.end_directory()

    def _add_next_page(self, url, count):
        p_match = re.search(r'[?&]p=(\d+)', url)
        if p_match:
            current_p = int(p_match.group(1))
            next_p = current_p + 1
            next_url = re.sub(r'p=\d+', f'p={next_p}', url)
        else:
            next_url = url + ('&p=2' if '?' in url else '?p=2')
            next_p = 2
        self.add_dir(f'[COLOR blue]Next Page ({next_p}) >>[/COLOR]', next_url, 2, self.icons.get('default'))

    # ─── CATEGORIES ──────────────────────────────────────────────────────────

    def process_categories(self, url):
        if '/az-pornstars' in url or url.rstrip('/').endswith('/pornstars'):
            self._list_pornstars(url)
            return
        if url.rstrip('/').endswith('/cats') or '/cats' in url:
            self._list_categories()
            return
        self.process_video_list(url)

    def _list_categories(self):
        content = self.make_request(f"{self.BASE_URL}/cats")
        if not content:
            self.end_directory()
            return
        
        seen = set()
        # <a href="/category/voyeur/" title="Voyeur Porn">Voyeur</a>
        cat_pattern = re.compile(
            r'href="(/category/[^/\"]+/)"[^>]*(?:title="([^"]*)")?[^>]*>([^<]+)</a>',
            re.DOTALL
        )
        for path, title_attr, title_text in cat_pattern.findall(content):
            cat_url = f"{self.BASE_URL}{path}"
            if cat_url in seen: continue
            seen.add(cat_url)
            title = (title_text or title_attr).strip().replace(' Porn', '')
            if title:
                self.add_dir(title, cat_url, 2, self.icons.get('categories', self.icon))
        self.end_directory()

    def _list_pornstars(self, url):
        content = self.make_request(url)
        if not content:
            self.end_directory()
            return
        
        seen = set()
        az_links = re.findall(r'<a href="(/az-pornstars/[a-z0-9])">([^<]+)</a>', content)
        if az_links and url.rstrip('/').endswith('/az-pornstars'):
            for path, name in az_links:
                ps_url = f"{self.BASE_URL}{path}"
                if ps_url not in seen:
                    seen.add(ps_url)
                    self.add_dir(name.strip(), ps_url, 8, self.icon)
        else:
            # Models on LetMeJerk are formatted as <li><a href="/category/model-name/">Model Name</a></li>
            for path, name in re.findall(r'<li>\s*<a href="(/category/[^"]+/)">([^<]+)</a>\s*</li>', content):
                ps_url = f"{self.BASE_URL}{path}"
                if ps_url not in seen:
                    seen.add(ps_url)
                    self.add_dir(name.strip(), ps_url, 2, self.icons.get('categories', self.icon))
        self.end_directory()

    # ─── PLAYBACK ─────────────────────────────────────────────────────────────

    def _normalize_stream_url(self, stream_url):
        return (stream_url or "").strip().replace(r"\/", "/").replace("&amp;", "&")

    def _extract_cached_hls(self, content):
        cached_match = re.search(r'var\s+cached\s*=\s*["\']([^"\']*)["\']', content)
        if not cached_match:
            return None
        stream_url = self._normalize_stream_url(cached_match.group(1))
        if stream_url.startswith("http") and ".m3u8" in stream_url:
            return stream_url
        return None

    def _extract_video_id(self, content, url):
        vid_match = re.search(r'var\s+vid\s*=\s*["\']([^"\']+)["\']', content)
        if vid_match:
            return vid_match.group(1).strip()

        path_parts = urllib.parse.urlparse(url).path.strip("/").split("/")
        if path_parts and re.match(r"^[A-Za-z0-9]+$", path_parts[0]):
            return path_parts[0]
        return None

    def _is_expired_hls(self, stream_url, margin_seconds=90):
        expiry_match = re.search(r",(\d{10})/", stream_url or "")
        if not expiry_match:
            return False
        try:
            return int(expiry_match.group(1)) <= int(time.time()) + margin_seconds
        except ValueError:
            return False

    def _refresh_hls(self, video_id, referer):
        if not video_id:
            return None

        api_url = "{}{}{}".format(
            self.BASE_URL,
            "/api/refresh-hls?id=",
            urllib.parse.quote(video_id, safe=""),
        )
        response = self.make_request(
            api_url,
            headers={
                "Accept": "application/json",
                "X-Requested-With": "XMLHttpRequest",
                "Referer": referer,
            },
        )
        if not response:
            return None

        try:
            payload = json.loads(response)
        except Exception as exc:
            xbmc.log(f"[letmejerk] refresh-hls JSON error for {video_id}: {exc}", xbmc.LOGWARNING)
            return None

        if payload.get("removed"):
            xbmc.log(f"[letmejerk] refresh-hls reports removed video: {video_id}", xbmc.LOGWARNING)
            return None

        stream_url = self._normalize_stream_url(payload.get("url"))
        if stream_url.startswith("http") and ".m3u8" in stream_url:
            return stream_url

        xbmc.log(f"[letmejerk] refresh-hls did not return a playable URL for {video_id}: {payload}", xbmc.LOGWARNING)
        return None

    def _play_stream(self, final_url, referer, is_hls=True):
        headers = {
            "User-Agent": self.ua,
            "Referer": referer or (self.BASE_URL + "/"),
        }
        header_string = "&".join(
            "{}={}".format(
                urllib.parse.quote(str(key), safe=""),
                urllib.parse.quote(str(value), safe=""),
            )
            for key, value in headers.items()
        )
        play_url = final_url + "|" + header_string

        li = xbmcgui.ListItem(path=play_url)
        if is_hls or ".m3u8" in final_url:
            li.setMimeType("application/x-mpegURL")
            li.setProperty("inputstream", "inputstream.adaptive")
            li.setProperty("inputstream.adaptive.manifest_type", "hls")
        else:
            li.setMimeType("video/mp4")
        li.setProperty("IsPlayable", "true")
        xbmcplugin.setResolvedUrl(self.addon_handle, True, li)

    def play_video(self, url):
        # 1. Fetch video page to get ID
        content = self.make_request(url)
        if not content:
            self.notify_error("Failed to load video page")
            return

        video_id = self._extract_video_id(content, url)
        final_url = self._extract_cached_hls(content)
        if (not final_url or self._is_expired_hls(final_url)) and video_id:
            refreshed_url = self._refresh_hls(video_id, url)
            if refreshed_url:
                final_url = refreshed_url

        if final_url and not self._is_expired_hls(final_url):
            self._play_stream(final_url, url, True)
            return

        # Find img ID or loadLetMeJerkVideoPlayer call
        msg_id = None
        path_id = None
        
        # New LetMeJerk obfuscation stores parameters in a pipe-delimited string array
        # Format usually looks like: loadLetMeJerkVideoPlayer|120539|...|120539|eHZAIWh0...
        match = re.search(r'loadLetMeJerkVideoPlayer.*?\|(\d{5,8})\|.*?\|(eH[A-Za-z0-9+/=]{50,})\|', content)
        if match:
            msg_id = match.group(1)
            path_id = match.group(2)
        else:
            # Fallback direct search for the base64 path (eHZA... = xv@...)
            b64_match = re.search(r'[|\'"](eH[A-Za-z0-9+/=]{60,})[|\'"]', content)
            id_match = re.search(r'loadLetMeJerkVideoPlayer[^\d]+(\d{5,8})', content)
            if id_match and b64_match:
                msg_id = id_match.group(1)
                path_id = b64_match.group(1)
            else:
                # Old plain-text fallback
                lmj_call = re.search(r'loadLetMeJerkVideoPlayer\s*\(\s*(\d+)\s*,\s*["\']?([^"\',\s)]+)["\']?\s*\)', content)
                if lmj_call:
                    msg_id = lmj_call.group(1)
                    path_id = lmj_call.group(2)
                else:
                    xbmc.log("[letmejerk] Could not find video ID or path ID", xbmc.LOGERROR)
                    self.notify_error("Video ID not found")
                    return

        # 2. Call API: POST /load/video3/{path_id}/ data={id: msg_id}
        api_url = f"{self.BASE_URL}/load/video3/{path_id}/"
        api_headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'X-Requested-With': 'XMLHttpRequest'
        }
        api_response = self.make_request(api_url, method='POST', data={'id': msg_id}, headers=api_headers)

        if not api_response:
            self.notify_error("API request failed")
            return

        # 3. Extract video source
        final_url = None
        is_hls = False

        cached_url = self._extract_cached_hls(content)
        if cached_url and not self._is_expired_hls(cached_url):
            final_url = cached_url
            is_hls = True

        vurl_match = re.search(r'const\s+videoUrl\s*=\s*["\']([^"\']+)["\']', api_response) if api_response else None
        if not final_url and vurl_match:
            final_url = self._normalize_stream_url(vurl_match.group(1))
            is_hls = final_url.lower().endswith('.m3u8') or '.m3u8?' in final_url.lower()
        
        # Fallback: direct src in video tag
        if not final_url and api_response:
            src_match = re.search(r'<video[^>]+src="([^"]+)"', api_response)
            if src_match:
                final_url = src_match.group(1)

        # Fallback: source tag
        if not final_url and api_response:
             src_match = re.search(r'<source[^>]+src="([^"]+)"', api_response)
             if src_match:
                 final_url = src_match.group(1)

        if not final_url:
            self.notify_error("No video URL found in API response")
            return

        xbmc.log(f"[letmejerk] Playing: {final_url}", xbmc.LOGDEBUG)

        self._play_stream(final_url, url, is_hls)
