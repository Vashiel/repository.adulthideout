#!/usr/bin/env python

import re
import sys
import json
import html
import time
import urllib.parse
import urllib.request
import urllib.error
from http.cookiejar import CookieJar

import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin

from resources.lib.base_website import BaseWebsite
from resources.lib.lookup_info import choose_and_open, extract_html_items

class PornhubWebsite(BaseWebsite):
    config = {
        "name": "pornhub",
        "base_url": "https://www.pornhub.com",
        "api_base": "https://www.pornhub.com/webmasters",
    }

    def __init__(self, addon_handle):
        super().__init__(
            name=self.config["name"],
            base_url=self.config["base_url"],
            search_url="",
            addon_handle=addon_handle
        )
        
        self.label = 'Pornhub'
        self.cookie_jar = CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cookie_jar)
        )
        urllib.request.install_opener(self.opener)
        self._set_age_cookie()

        self.sorting_options = ["Newest", "Most Viewed", "Top Rated"]
        self.sorting_paths = {
            "Newest": "newest",
            "Most Viewed": "mostviewed",
            "Top Rated": "rating"
        }
        
        self.period_options = ["All Time", "This Month", "This Week"]
        self.period_paths = {"All Time": "alltime", "This Month": "monthly", "This Week": "weekly"}
        
        self.pornstar_sort_options = ["Most Popular", "Most Viewed", "Top Trending", "Most Subscribed", "Alphabetical", "No. Of Videos", "Random"]
        self.pornstar_sort_paths = {
            "Most Popular": "", "Most Viewed": "mv", "Top Trending": "t", 
            "Most Subscribed": "ms", "Alphabetical": "a", "No. Of Videos": "nv", "Random": "r"
        }

    def get_start_url_and_label(self):
        addon = xbmcaddon.Addon()
        selected_sort_name = addon.getSetting('pornhub_sort_by') or "Newest"
        sort_param = self.sorting_paths.get(selected_sort_name, 'newest')
        start_url = f"{self.base_url}/video?o={sort_param}"
        label = f"{self.label} [COLOR yellow]{selected_sort_name}[/COLOR]"
        return start_url, label

    def _set_age_cookie(self):
        for name, value in (
            ('age_verified', '1'),
            ('accessAgeDisclaimerPH', '1'),
            ('accessAgeDisclaimerUK', '1'),
            ('accessPH', '1'),
            ('platform', 'pc'),
        ):
            self.cookie_jar.set_cookie(self._create_cookie(name, value, '.pornhub.com'))

    def _extract_flashvars(self, content):
        """Extract Pornhub's flashvars object with brace balancing."""
        for marker in (r'var\s+flashvars_\d+\s*=', r'var\s+flashvars\s*=', r'flashvars\s*='):
            for match in re.finditer(marker, content, re.DOTALL):
                start = content.find('{', match.end())
                if start == -1:
                    continue

                depth = 0
                quote = None
                escape = False
                for idx in range(start, len(content)):
                    ch = content[idx]
                    if escape:
                        escape = False
                        continue
                    if ch == '\\':
                        escape = True
                        continue
                    if quote:
                        if ch == quote:
                            quote = None
                        continue
                    if ch in ('"', "'"):
                        quote = ch
                        continue
                    if ch == '{':
                        depth += 1
                    elif ch == '}':
                        depth -= 1
                        if depth == 0:
                            raw = content[start:idx + 1]
                            try:
                                data = json.loads(raw)
                                if data and data.get('mediaDefinitions'):
                                    self.logger.info(f"Pornhub: Successfully extracted flashvars with marker: {marker}")
                                    return data
                            except Exception as exc:
                                self.logger.warning(f"Pornhub: flashvars JSON parse failed: {exc}")
                            break
        return None

    def _warmup_session(self, referer=None):
        try:
            self._set_age_cookie()
            req = urllib.request.Request(
                self.base_url,
                headers=self.get_headers(referer or self.base_url)
            )
            with self.opener.open(req, timeout=8) as resp:
                resp.read(2048)
            return True
        except Exception as exc:
            self.logger.warning(f"Pornhub: session warmup failed: {exc}")
            return False

    def _prime_stream_url(self, stream_url, referer, headers, attempts=3):
        """Prime DNS/CDN access before handing the HLS URL to Kodi."""
        clean_url = stream_url.split("|", 1)[0]
        request_headers = {
            "User-Agent": headers.get("User-Agent", self.get_headers().get("User-Agent")),
            "Referer": headers.get("Referer", referer),
            "Origin": headers.get("Origin", self.base_url.rstrip("/")),
        }
        cookie = headers.get("Cookie")
        if cookie:
            request_headers["Cookie"] = cookie

        for attempt in range(attempts):
            try:
                req = urllib.request.Request(clean_url, headers=request_headers)
                with self.opener.open(req, timeout=8) as resp:
                    sample = resp.read(512)
                if sample:
                    return True
            except Exception as exc:
                self.logger.warning(
                    f"Pornhub: stream preflight failed on attempt {attempt + 1}: {exc}"
                )
                time.sleep(0.5 * (attempt + 1))
        return False

    def _create_cookie(self, name, value, domain):
        from http.cookiejar import Cookie
        return Cookie(
            version=0, name=name, value=value, port=None, port_specified=False,
            domain=domain, domain_specified=True, domain_initial_dot=domain.startswith('.'),
            path='/', path_specified=True, secure=False, expires=None, discard=True,
            comment=None, comment_url=None, rest={'HttpOnly': None}, rfc2109=False
        )

    def get_headers(self, referer=None):
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7',
        }
        if referer: headers['Referer'] = referer
        return headers

    def make_request(self, url, referer=None, is_api=False):
        last_error = None
        for attempt in range(3):
            try:
                if attempt:
                    time.sleep(0.8 * attempt)
                    self._set_age_cookie()

                headers = self.get_headers(referer)
                if is_api:
                    headers['Accept'] = 'application/json, text/plain, */*'
                    headers['X-Requested-With'] = 'XMLHttpRequest'
                
                req = urllib.request.Request(url, headers=headers)
                with self.opener.open(req, timeout=15) as resp:
                    return resp.read().decode('utf-8', errors='ignore')
            except urllib.error.HTTPError as e:
                last_error = e
                self.logger.warning(f"Pornhub request failed for {url} on attempt {attempt + 1}: HTTP {e.code}")
                if e.code not in (403, 429, 503):
                    break
            except Exception as e:
                last_error = e
                self.logger.warning(f"Pornhub request failed for {url} on attempt {attempt + 1}: {e}")
                break

        if last_error:
            self.logger.warning(f"Pornhub request exhausted for {url}: {last_error}")
        if hasattr(self, 'notify_error'):
            self.notify_error("Failed to load data.")
        return None
    
    def process_content(self, url):
        params = {}
        if len(sys.argv) > 2 and sys.argv[2]:
            params = dict(urllib.parse.parse_qsl(sys.argv[2][1:]))
        action = params.get('action')
        if action == "show_related":
            self.process_related_videos(url)
            return

        if not url or url == "BOOTSTRAP": url = self.base_url

        parsed_url = urllib.parse.urlparse(url)
        path = parsed_url.path

        if '/pornstar/' in path or '/model/' in path:
            self.process_video_list(url)
        elif '/pornstars' in path:
            self.process_pornstars(url)
        elif '/categories' in path:
            self.process_categories()
        else:
            if hasattr(self, 'add_dir'):
                self.add_dir('[COLOR blue]Search[/COLOR]', '', 5, self.icons['search'], name_param=self.name)
                self.add_dir('Categories', f"{self.base_url}/categories", 2, self.icons['categories'])
                
                pornstars_url = f"{self.base_url}/pornstars"
                self.add_dir(
                    'Pornstars', 
                    pornstars_url, 
                    2, 
                    self.icons['pornstars'], 
                    context_menu=[
                        ('Sort by', f'RunPlugin({sys.argv[0]}?mode=7&action=select_pornstar_sort&website={self.name}&original_url={urllib.parse.quote_plus(pornstars_url)})')
                    ]
                )
            
            self.process_video_list(url)

        if hasattr(self, 'end_directory'):
            self.end_directory()

    def process_video_list(self, current_url):
        parsed = urllib.parse.urlparse(current_url)
        params = urllib.parse.parse_qs(parsed.query)
        api_params = {'page': params.get('page', ['1'])[0]}
        
        if '/pornstar/' in parsed.path:
            pornstar_name = parsed.path.split('/pornstar/')[-1].split('/')[0]
            api_params['search'] = pornstar_name.replace('-', ' ')
        elif '/model/' in parsed.path:
            model_name = parsed.path.split('/model/')[-1].split('/')[0]
            api_params['search'] = model_name.replace('-', ' ')
        elif 'search' in params:
            api_params['search'] = params['search'][0]
        elif 'category' in params:
            api_params['category'] = params['category'][0]
        elif 'category_slug' in params:
            api_params['category'] = params['category_slug'][0]
        
        api_params['ordering'] = params.get('o', [self.sorting_paths['Newest']])[0]
        
        if api_params['ordering'] in ['mostviewed', 'rating']:
            api_params['period'] = params.get('p', ['alltime'])[0]
        
        api_url = f"{self.config['api_base']}/search?{urllib.parse.urlencode(api_params, doseq=True)}"
        content = self.make_request(api_url, referer=current_url, is_api=True)
        if not content: return

        try: data = json.loads(content)
        except json.JSONDecodeError: return

        videos = data.get('videos', [])
        
        context_menu = [
            ('Sort by', f'RunPlugin({sys.argv[0]}?mode=7&action=select_sort&website={self.name}&original_url={urllib.parse.quote_plus(current_url)})'),
            ('Select Period', f'RunPlugin({sys.argv[0]}?mode=7&action=select_period&website={self.name}&original_url={urllib.parse.quote_plus(current_url)})')
        ]
        
        for vid in videos:
            title = html.unescape(vid.get('title', ''))
            vid_id, thumb, duration = vid.get('video_id'), vid.get('default_thumb'), vid.get('duration')
            if all((title, vid_id, thumb, duration)) and hasattr(self, 'add_link'):
                if thumb:
                    thumb = thumb.replace("&amp;", "&")
                    if "|" not in thumb:
                        thumb += "|User-Agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0.0.0&Referer=https://www.pornhub.com/"
                
                video_url = f"{self.base_url}/view_video.php?viewkey={vid_id}"
                video_context_menu = [
                    ('Explore similar', f'RunPlugin({sys.argv[0]}?mode=7&action=explore_similar&website={self.name}&original_url={urllib.parse.quote_plus(video_url)})')
                ] + context_menu

                label = f"{title} [COLOR lime]({duration})[/COLOR]"
                self.add_link(label, video_url, 4, thumb, self.fanart, video_context_menu)

        if len(videos) > 0 and hasattr(self, 'add_dir'):
            next_params = params.copy()
            current_page = int(api_params.get('page', '1'))
            next_params['page'] = [str(current_page + 1)]
            next_url = parsed._replace(query=urllib.parse.urlencode(next_params, doseq=True)).geturl()
            self.add_dir('[COLOR blue]Next Page >>>>[/COLOR]', next_url, 2, self.icons['default'])

    def process_categories(self):
        api_url = f"{self.config['api_base']}/categories"
        content = self.make_request(api_url, referer=self.config['base_url'], is_api=True)
        if not content: return
        
        try:
            data = json.loads(content)
            for cat in data.get('categories', []):
                name = cat.get('category')
                if name and hasattr(self, 'add_dir'):
                    slug = name.lower().replace(' ', '-')
                    kodi_url = f"{self.base_url}/video?category_slug={slug}"
                    self.add_dir(name, kodi_url, 2, self.icons['categories'])
        except json.JSONDecodeError:
            pass

    def process_pornstars(self, current_url):
        content = self.make_request(current_url, referer=self.base_url, is_api=False)
        if not content: return

        pornstar_context_menu = [
            ('Sort by', f'RunPlugin({sys.argv[0]}?mode=7&action=select_pornstar_sort&website={self.name}&original_url={urllib.parse.quote_plus(current_url)})')
        ]

        try:
            items = content.split('<li class="')
            for item in items[1:]:
                if 'performerCard' not in item: continue
                try:
                    url_part = item.split('<a href="')[1].split('"')[0]
                    full_url = urllib.parse.urljoin(self.base_url, html.unescape(url_part))
                    img_block = item.split('<img')[1]
                    thumb = html.unescape(img_block.split('data-thumb_url="')[1].split('"')[0])
                    if thumb:
                        thumb = thumb.replace("&amp;", "&")
                        if "|" not in thumb:
                            thumb += "|User-Agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0.0.0&Referer=https://www.pornhub.com/"
                            
                    name = html.unescape(img_block.split('alt="')[1].split('"')[0])
                    if hasattr(self, 'add_dir'):
                        self.add_dir(name, full_url, 2, thumb, self.fanart, context_menu=pornstar_context_menu)
                except IndexError:
                    continue
            
            if '<li class="page_next">' in content and hasattr(self, 'add_dir'):
                next_page_url_part = content.split('<li class="page_next">')[1].split('href="')[1].split('"')[0]
                next_page_url = urllib.parse.urljoin(self.base_url, html.unescape(next_page_url_part))
                self.add_dir('[COLOR blue]Next Page >>>>[/COLOR]', next_page_url, 2, self.icons['default'])
        except Exception as e:
            if hasattr(self, 'notify_error'): self.notify_error("An error occurred while parsing the page.")

    def play_video(self, url):
        self.logger.info(f"Pornhub: play_video for {url}")
        
        # Ensure age disclaimer cookies are present
        data = None
        self._set_age_cookie()
        # Direct fetch without initial homepage warmup to avoid geo-block/consent cookies (returns 403)

        for attempt in range(2):
            content = self.make_request(url, referer=self.base_url if attempt == 0 else url)
            if content:
                data = self._extract_flashvars(content)
                if data:
                    break
            if attempt == 0:
                self.logger.warning("Pornhub: first video-page request had no playable flashvars; retrying after warmup.")
                self._warmup_session(referer=url)
        
        if data:
            media = data.get('mediaDefinitions', [])
            # Try HLS first
            streams = [s for s in media if s.get('format') == 'hls' and s.get('videoUrl')]
            
            # Fallback to MP4 if no HLS found
            if not streams:
                self.logger.info("Pornhub: No HLS found, checking for mp4 streams")
                streams = [s for s in media if s.get('format') == 'mp4' and s.get('videoUrl')]
            
            if streams:
                # Find best stream by quality
                try:
                    best_stream = max(streams, key=lambda x: int(str(x.get('quality', '0'))) if str(x.get('quality', '0')).isdigit() else 0)
                except:
                    best_stream = streams[0]
                
                if best_stream:
                    stream_url = html.unescape(best_stream['videoUrl']).replace('\\/', '/')
                    ua = self.get_headers()['User-Agent']
                    
                    # Prepare headers for segments and manifest
                    headers = {
                        'User-Agent': ua,
                        'Referer': url,
                        'Origin': self.base_url.rstrip('/'),
                        'Cookie': "; ".join([f"{c.name}={c.value}" for c in self.cookie_jar])
                    }
                    
                    header_str = urllib.parse.urlencode(headers)

                    if not self._prime_stream_url(stream_url, url, headers):
                        self.logger.warning("Pornhub: stream preflight did not succeed; Kodi playback may retry.")
                    
                    # Construct Kodi player URL
                    kodi_url = stream_url
                    if "|" not in kodi_url:
                        kodi_url += "|" + header_str
                        
                    self.logger.info(f"Pornhub: Playback resolved to: {kodi_url[:120]}...")
                    
                    li = xbmcgui.ListItem(path=kodi_url)
                    li.setProperty('IsPlayable', 'true')
                    
                    if best_stream.get('format') == 'hls':
                        li.setProperty('inputstream', 'inputstream.adaptive')
                        li.setProperty('inputstream.adaptive.manifest_type', 'hls')
                        # CRITICAL: Pass headers EXPLICITLY to segments
                        li.setProperty('inputstream.adaptive.stream_headers', header_str)
                        li.setProperty('inputstream.adaptive.manifest_headers', header_str)
                        li.setMimeType('application/vnd.apple.mpegurl')
                    else:
                        li.setMimeType('video/mp4')
                        
                    xbmcplugin.setResolvedUrl(self.addon_handle, True, li)
                    return
        
        self.logger.error(f"Pornhub: No playable streams found in flashvars for {url}")
        if hasattr(self, 'notify_error'): self.notify_error("No playable stream found.")
        xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem(path=url))

    def search(self, query):
        if not query: return
        url = f"{self.base_url}/video/search?search={urllib.parse.quote_plus(query)}&o=newest"
        self.process_content(url)

    def select_sort(self, original_url):
        dialog = xbmcgui.Dialog()
        idx = dialog.select("Sort by", self.sorting_options)
        if idx == -1: return

        sort_key = self.sorting_options[idx]
        sort_val = self.sorting_paths[sort_key]
        
        addon = xbmcaddon.Addon()
        addon.setSetting('pornhub_sort_by', sort_key)
        
        parsed_url = urllib.parse.urlparse(original_url)
        params = urllib.parse.parse_qs(parsed_url.query)
        params['o'] = [sort_val]
        params.pop('page', None)
        
        new_query = urllib.parse.urlencode(params, doseq=True)
        new_url = parsed_url._replace(query=new_query).geturl()
        
        xbmc.executebuiltin(f"Container.Update({sys.argv[0]}?mode=2&website={self.name}&url={urllib.parse.quote_plus(new_url)})")

    def select_period(self, original_url):
        dialog = xbmcgui.Dialog()
        idx = dialog.select("Select Period", self.period_options)
        if idx == -1: return

        period_key = self.period_options[idx]
        period_val = self.period_paths[period_key]
        parsed_url = urllib.parse.urlparse(original_url)
        params = urllib.parse.parse_qs(parsed_url.query)
        params['p'] = [period_val]
        params.pop('page', None)
        new_query = urllib.parse.urlencode(params, doseq=True)
        new_url = parsed_url._replace(query=new_query).geturl()
        xbmc.executebuiltin(f"Container.Update({sys.argv[0]}?mode=2&website={self.name}&url={urllib.parse.quote_plus(new_url)})")

    def select_pornstar_sort(self, original_url):
        dialog = xbmcgui.Dialog()
        idx = dialog.select("Sort Pornstars by", self.pornstar_sort_options)
        if idx == -1: return

        base_pornstar_url = f"{self.base_url}/pornstars"
        parsed_url = urllib.parse.urlparse(base_pornstar_url)
        params = {}
        sort_key = self.pornstar_sort_options[idx]
        sort_val = self.pornstar_sort_paths.get(sort_key)
        if sort_val: params['o'] = [sort_val]
        new_query = urllib.parse.urlencode(params, doseq=True)
        new_url = parsed_url._replace(query=new_query).geturl()
        xbmc.executebuiltin(f"Container.Update({sys.argv[0]}?mode=2&website={self.name}&url={urllib.parse.quote_plus(new_url)})")

    def process_related_videos(self, url):
        if hasattr(self, 'add_dir'):
            self.add_dir('[COLOR blue]Search[/COLOR]', '', 5, self.icons['search'], name_param=self.name)
        
        content = self.make_request(url, referer=self.base_url)
        if not content:
            self.logger.warning("Pornhub: failed to fetch related video page.")
            if hasattr(self, 'end_directory'): self.end_directory()
            return

        context_menu = [
            ('Sort by', f'RunPlugin({sys.argv[0]}?mode=7&action=select_sort&website={self.name}&original_url={urllib.parse.quote_plus(url)})'),
            ('Select Period', f'RunPlugin({sys.argv[0]}?mode=7&action=select_period&website={self.name}&original_url={urllib.parse.quote_plus(url)})')
        ]

        # Try parsing the relatedVideos JavaScript array for 100% true related videos
        js_match = re.search(r'relatedVideos\s*=\s*(\[.*?\])\s*;', content, re.DOTALL)
        if not js_match:
            js_match = re.search(r'var\s+relatedVideos\s*=\s*(\[.*?\])', content, re.DOTALL)

        if js_match:
            try:
                data = json.loads(js_match.group(1))
                # Extract all global URLs to map high-quality CDN thumbnails dynamically
                all_urls = re.findall(r'(https?://[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/[^"\s\'>]+)', content)
                url_map = {}
                for u in all_urls:
                    if "phncdn" in u or "phncdn.com" in u or "/videos/" in u:
                        m_path = re.search(r'/\d{6}/\d{2}/\d+/', u)
                        if m_path:
                            path_key = m_path.group(0)
                            # Prioritize images (.jpg, .jpeg, .png, .webp, or /plain/) over preview video webm/mp4
                            is_image = any(ext in u.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp', '/plain/']) and '.webm' not in u.lower()
                            if is_image or path_key not in url_map:
                                url_map[path_key] = u

                found_any = False
                for item in data:
                    fields = item.get("fields")
                    if not fields:
                        continue
                    vkey = fields.get("vkey")
                    if not vkey:
                        continue
                    
                    title = html.unescape(fields.get("title", "Related Video"))
                    title = re.sub(r'<[^>]+>', '', title).strip()
                    duration_sec = fields.get("duration", 0)
                    media_path = fields.get("media_path", "")

                    # Map thumbnail from our global URL map
                    thumb = ""
                    if media_path:
                        thumb = url_map.get(media_path, "")
                        if not thumb:
                            # Generic lookup by ID
                            video_id_str = media_path.strip("/").split("/")[-1]
                            # Try to find an image first
                            for u in all_urls:
                                if video_id_str in u and any(ext in u.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp', '/plain/']) and '.webm' not in u.lower():
                                    thumb = u
                                    break
                            if not thumb:
                                for u in all_urls:
                                    if video_id_str in u:
                                        thumb = u
                                        break
                    if not thumb:
                        thumb = self.fanart

                    if thumb and "|" not in thumb:
                        thumb = thumb.replace("&amp;", "&")
                        thumb += "|User-Agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0.0.0&Referer=https://www.pornhub.com/"

                    duration_str = ""
                    if duration_sec > 0:
                        mins = duration_sec // 60
                        secs = duration_sec % 60
                        duration_str = f"{mins}:{secs:02d}"

                    video_url = f"{self.base_url}/view_video.php?viewkey={vkey}"
                    video_context_menu = [
                        ('Explore similar', f'RunPlugin({sys.argv[0]}?mode=7&action=explore_similar&website={self.name}&original_url={urllib.parse.quote_plus(video_url)})'),
                    ] + context_menu

                    label = title
                    if duration_str:
                        label += f" [COLOR lime]({duration_str})[/COLOR]"

                    self.add_link(label, video_url, 4, thumb, self.fanart, video_context_menu)
                    found_any = True

                if found_any:
                    if hasattr(self, 'end_directory'): self.end_directory()
                    return
            except Exception as e:
                self.logger.warning(f"Pornhub: failed to parse JS relatedVideos: {e}")

        # Fallback to HTML matching if JavaScript parsing is unavailable
        related_matches = re.findall(r'<li\b[^>]*class="[^"]*(?:videoBox|ph-thumbnail)[^"]*"[^>]*>(.*?)</li>', content, re.DOTALL)
        if not related_matches:
            related_matches = re.findall(r'<div\b[^>]*class="[^"]*(?:videoBox|ph-thumbnail)[^"]*"[^>]*>(.*?)</div>', content, re.DOTALL)

        found_any = False
        for chunk in related_matches:
            v_match = re.search(r'href="[^"]*viewkey=([^"&]+)"', chunk)
            if not v_match:
                continue
            viewkey = v_match.group(1)
            
            t_match = re.search(r'title="([^"]+)"', chunk) or re.search(r'<span class="title">[^<]*<a[^>]*>([^<]+)</a>', chunk, re.DOTALL)
            img_match = re.search(r'<img[^>]+src="([^"]+)"', chunk) or re.search(r'data-src="([^"]+)"', chunk)
            dur_match = re.search(r'<var class="duration">([^<]+)</var>', chunk)

            title = html.unescape(t_match.group(1).strip()) if t_match else 'Untitled Video'
            title = re.sub(r'<[^>]+>', '', title).strip()
            img = img_match.group(1) if img_match else ''
            duration = dur_match.group(1).strip() if dur_match else ''

            if img:
                img = img.replace("&amp;", "&")
                if "|" not in img:
                    img += "|User-Agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0.0.0&Referer=https://www.pornhub.com/"

            video_url = f"{self.base_url}/view_video.php?viewkey={viewkey}"
            
            video_context_menu = [
                ('Explore similar', f'RunPlugin({sys.argv[0]}?mode=7&action=explore_similar&website={self.name}&original_url={urllib.parse.quote_plus(video_url)})'),
            ] + context_menu

            label = title
            if duration:
                label += f" [COLOR lime]({duration})[/COLOR]"
                
            self.add_link(label, video_url, 4, img, self.fanart, video_context_menu)
            found_any = True

        if not found_any:
            self.logger.warning("Pornhub: no related videos found on video page.")
            
        if hasattr(self, 'end_directory'):
            self.end_directory()

    def explore_similar(self, original_url=None):
        if not original_url:
            self.notify_info("No video URL available")
            return

        html_content = self.make_request(original_url)
        if not html_content:
            self.notify_error("Could not load video info")
            return

        pornstars_chunk = ""
        categories_chunk = ""
        tags_chunk = ""

        # Extract pornstars wrapper
        pornstars_match = re.search(r'<div[^>]+class="[^"]*pornstarsWrapper[^"]*"[^>]*>(.*?)</div>', html_content, re.DOTALL)
        if pornstars_match:
            pornstars_chunk = pornstars_match.group(1)

        # Extract categories wrapper
        categories_match = re.search(r'<div[^>]+class="[^"]*categoriesWrapper[^"]*"[^>]*>(.*?)</div>', html_content, re.DOTALL)
        if categories_match:
            categories_chunk = categories_match.group(1)

        # Extract tags wrapper
        tags_match = re.search(r'<div[^>]+class="[^"]*tagsWrapper[^"]*"[^>]*>(.*?)</div>', html_content, re.DOTALL)
        if tags_match:
            tags_chunk = tags_match.group(1)

        pornstar_items = []
        if pornstars_chunk:
            patterns = [
                ("Pornstar", r'href="(/pornstar/[^"]+)"[^>]*>([^<]+)', 2),
                ("Model", r'href="(/model/[^"]+)"[^>]*>([^<]+)', 2),
            ]
            pornstar_items = extract_html_items(pornstars_chunk, self.base_url, patterns)

        category_items = []
        if categories_chunk:
            patterns = [
                ("Category", r'href="(/categories/[^"]+)"[^>]*>([^<]+)', 2),
            ]
            category_items = extract_html_items(categories_chunk, self.base_url, patterns)
            for item in category_items:
                parsed = urllib.parse.urlparse(item["url"])
                slug = parsed.path.rstrip("/").split("/")[-1]
                item["url"] = f"{self.base_url}/video?category_slug={slug}"

        tag_items = []
        if tags_chunk:
            patterns = [
                ("Tag", r'href="(/video/search\?search=[^"]+)"[^>]*>([^<]+)', 2),
                ("Tag", r'href="(/search\?search=[^"]+)"[^>]*>([^<]+)', 2),
            ]
            tag_items = extract_html_items(tags_chunk, self.base_url, patterns)

        items = pornstar_items + category_items + tag_items

        if not items:
            # Fallback to global matching if wrapper blocks are not found or are empty
            patterns = [
                ("Pornstar", r'href="(/pornstar/[^"]+)"[^>]*>([^<]+)', 2),
                ("Model", r'href="(/model/[^"]+)"[^>]*>([^<]+)', 2),
                ("Category", r'href="(/categories/[^"]+)"[^>]*>([^<]+)', 2),
                ("Tag", r'href="(/video/search\?search=[^"]+)"[^>]*>([^<]+)', 2),
                ("Tag", r'href="(/search\?search=[^"]+)"[^>]*>([^<]+)', 2),
            ]
            items = extract_html_items(html_content, self.base_url, patterns)
            for item in items:
                if item["group"] == "Category":
                    parsed = urllib.parse.urlparse(item["url"])
                    slug = parsed.path.rstrip("/").split("/")[-1]
                    item["url"] = f"{self.base_url}/video?category_slug={slug}"
        
        if items:
            lang = xbmc.getLanguage(0).lower()
            if "german" in lang or "deutsch" in lang:
                group = "Wiedergabe"
                label = "[COLOR lime]>>> Ähnliche Videos anzeigen <<<[/COLOR]"
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
                "url": original_url,
                "mode": 2,
                "action": "show_related"
            })
            
        if not choose_and_open(items, self.config["name"], "Explore similar"):
            self.logger.info("[pornhub] No lookup target selected for {}".format(original_url))
