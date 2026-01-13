#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
import os
import urllib.parse
import urllib.request
import http.cookiejar
import time
import xbmc
import xbmcgui
import xbmcplugin
from resources.lib.base_website import BaseWebsite


class SunpornoWebsite(BaseWebsite):
    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="sunporno",
            base_url="https://www.sunporno.com",
            search_url="https://www.sunporno.com/s/{}/",
            addon_handle=addon_handle,
            addon=addon
        )
        self.sort_options = ["Trending", "Recent", "Top Rated"]
        self.content_types = ["All"]
        self.sort_paths = {
            0: "/trending/",
            1: "/recent/",
            2: "/top-rated/"
        }
        self.icon = os.path.join(self.addon.getAddonInfo('path'), 'resources', 'logos', 'sunporno.png')
        
        self.cookie_jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cookie_jar))
        
        self.opener.addheaders = [
            ('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'),
            ('Accept', 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8'),
            ('Accept-Language', 'en-US,en;q=0.9'),
            ('Accept-Encoding', 'identity'),
            ('Connection', 'keep-alive'),
            ('Upgrade-Insecure-Requests', '1'),
            ('Sec-Fetch-Dest', 'document'),
            ('Sec-Fetch-Mode', 'navigate'),
            ('Sec-Fetch-Site', 'none'),
            ('Sec-Fetch-User', '?1'),
            ('Cache-Control', 'max-age=0'),
        ]

    def get_start_url_and_label(self):
        sort_id = f"{self.name}_sort_by"
        sort_index = int(self.addon.getSetting(sort_id) or '0')
        path = self.sort_paths.get(sort_index, "/")
        label = f"Sunporno - {self.sort_options[sort_index]}"
        return f"{self.base_url}{path}", label

    def make_request(self, url, extra_headers=None):
        try:
            custom_opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cookie_jar))
            
            request_headers = [
                ('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'),
                ('Accept', 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8'),
                ('Accept-Language', 'en-US,en;q=0.9'),
                ('Accept-Encoding', 'identity'),
                ('Connection', 'keep-alive'),
                ('Upgrade-Insecure-Requests', '1'),
                ('Sec-Fetch-Dest', 'document'),
                ('Sec-Fetch-Mode', 'navigate'),
                ('Sec-Fetch-Site', 'none'),
                ('Cache-Control', 'max-age=0'),
            ]
            
            if extra_headers:
                for key, value in extra_headers.items():
                    request_headers.append((key, value))
            
            custom_opener.addheaders = request_headers
            
            xbmc.log(f"[Sunporno] Making request to: {url}", xbmc.LOGINFO)
            
            with custom_opener.open(url, timeout=20) as response:
                return response.read().decode('utf-8')
        except Exception as e:
            xbmc.log(f"[Sunporno] Request failed: {e}", xbmc.LOGERROR)
            return None

    def process_content(self, url):
        self.add_basic_dirs(url)
        self.process_video_list(url)

    def add_basic_dirs(self, current_url):
        self.add_dir('[COLOR blue]Search[/COLOR]', '', 5, self.icons.get('search'))
        self.add_dir('Categories', f'{self.base_url}/tags/', 8, self.icons.get('categories'))

    def process_video_list(self, url):
        content = self.make_request(url)
        if not content:
            self.notify_error("Failed to load page")
            self.end_directory()
            return

        video_pattern = r'href="(https://www\.sunporno\.com/v/(\d+)/([^"]+)/)"'
        video_matches = re.findall(video_pattern, content)
        
        thumb_lookup = {}
        thumb_pattern1 = r'src="(https://[^"]*sunporno[^"]+/(\d+)/[^"]+\.jpg)"'
        thumb_pattern2 = r'data-src="(https://[^"]*sunporno[^"]+/(\d+)/[^"]+\.jpg)"'
        
        for pattern in [thumb_pattern1, thumb_pattern2]:
            for thumb_url, vid_id in re.findall(pattern, content):
                if vid_id not in thumb_lookup:
                    thumb_lookup[vid_id] = thumb_url
        
        seen = set()
        unique_videos = []
        for full_url, video_id, title_slug in video_matches:
            if full_url not in seen:
                seen.add(full_url)
                unique_videos.append((full_url, video_id, title_slug))

        items_added = 0
        for video_url, video_id, title_slug in unique_videos:
            title = title_slug.replace('-', ' ').title()
            thumb = thumb_lookup.get(video_id, "")
            if not thumb:
                prefix = str(int(video_id) // 1000 * 1000)
                thumb = f"https://acdn.sunporno.com/contents/videos_screenshots/{prefix}/{video_id}/320x180/2.jpg"
            
            self.add_link(title, video_url, 4, thumb, self.fanart)
            items_added += 1

        if items_added > 0:
            page_match = re.search(r'/(\d+)/$', url)
            current_page = int(page_match.group(1)) if page_match else 1
            next_page = current_page + 1
            
            if page_match:
                next_url = re.sub(r'/\d+/$', f'/{next_page}/', url)
            else:
                base = url.rstrip('/')
                next_url = f"{base}/{next_page}/"
            
            self.add_dir(f"[COLOR blue]Next Page ({next_page}) >>[/COLOR]", next_url, 2, self.icons.get('default'))
        else:
            self.notify_error("No videos found")
                
        self.end_directory()

    def process_categories(self, url):
        content = self.make_request(url)
        if not content:
            self.notify_error("Failed to load categories")
            self.end_directory()
            return
        
        cat_pattern = r'href="(https://www\.sunporno\.com/tags/([^"]+)/)"'
        categories = re.findall(cat_pattern, content)
        
        seen = set()
        for cat_url, slug in categories:
            if slug not in seen and slug.isalpha():
                seen.add(slug)
                title = slug.replace('-', ' ').title()
                self.add_dir(title, cat_url, 2, self.icons.get('categories'))
            
        self.end_directory()

    def play_video(self, url):
        xbmc.log(f"[Sunporno] play_video called with URL: {url}", xbmc.LOGINFO)
        
        content = self.make_request(url)
        if not content:
            self.notify_error("Failed to load video page")
            return

        embed_url = self._extract_embed_url(content)
        if not embed_url:
            xbmc.log("[Sunporno] No embed URL found, trying main page extraction", xbmc.LOGWARNING)
            video_info = self._extract_video_from_main_page(content)
            if video_info:
                video_url = video_info.get('video_url')
                rnd_value = video_info.get('rnd', str(int(time.time() * 1000)))
            else:
                self.notify_error("No video source found")
                return
        else:
            xbmc.log(f"[Sunporno] Found Embed URL: {embed_url}", xbmc.LOGINFO)
            
            video_info = self._extract_video_from_embed(embed_url)
            if not video_info:
                self.notify_error("Failed to extract video configuration")
                return

            video_url = video_info.get('video_url')
            rnd_value = video_info.get('rnd')
        
        if not video_url:
            self.notify_error("Video URL not found")
            return

        xbmc.log(f"[Sunporno] Video URL: {video_url[:100]}...", xbmc.LOGINFO)
        xbmc.log(f"[Sunporno] RND value: {rnd_value}", xbmc.LOGINFO)

        cookies_dict = {}
        for cookie in self.cookie_jar:
            cookies_dict[cookie.name] = cookie.value
            xbmc.log(f"[Sunporno] Cookie: {cookie.name}={cookie.value[:20]}...", xbmc.LOGDEBUG)
            
        xbmc.log(f"[Sunporno] Cookies for video: {list(cookies_dict.keys())}", xbmc.LOGINFO)

        video_url = video_url.strip().rstrip('/')
        
        params = []
        if rnd_value and 'rnd=' not in video_url:
            params.append(f"rnd={rnd_value}")
        
        if 'embed=true' not in video_url:
            params.append("embed=true")
            
        if params:
            joiner = '&' if '?' in video_url else '?'
            video_url = f"{video_url}{joiner}{'&'.join(params)}"
        
        xbmc.log(f"[Sunporno] Final video URL: {video_url[:150]}...", xbmc.LOGINFO)

        try:
            from resources.lib.proxy_utils import ProxyController, PlaybackGuard
            
            upstream_headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "video/webm,video/ogg,video/*;q=0.9,application/ogg;q=0.7,audio/*;q=0.6,*/*;q=0.5",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "identity",
                "Connection": "keep-alive",
                "Referer": embed_url if embed_url else url,
                "Origin": "https://www.sunporno.com",
            }
            
            controller = ProxyController(
                video_url, 
                upstream_headers=upstream_headers,
                cookies=cookies_dict
            )
            local_url = controller.start()
            
            monitor = xbmc.Monitor()
            player = xbmc.Player()
            guard = PlaybackGuard(player, monitor, local_url, controller)
            guard.start()
            
            li = xbmcgui.ListItem(path=local_url)
            li.setMimeType('video/mp4')
            li.setProperty('IsPlayable', 'true')
            li.setContentLookup(False)
            
            xbmcplugin.setResolvedUrl(self.addon_handle, True, li)
            guard.join()
            
        except ImportError:
            xbmc.log("[Sunporno] ProxyController not available, using direct playback", xbmc.LOGWARNING)
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Referer': embed_url if embed_url else url,
                'Origin': 'https://www.sunporno.com',
                'Accept': 'video/webm,video/ogg,video/*;q=0.9,application/ogg;q=0.7,audio/*;q=0.6,*/*;q=0.5',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'identity',
                'Connection': 'keep-alive',
            }
            
            headers_str = '&'.join([f'{k}={urllib.parse.quote(str(v))}' for k, v in headers.items()])
            
            if cookies_dict:
                cookie_str = "; ".join([f"{k}={v}" for k, v in cookies_dict.items()])
                headers_str += f"&Cookie={urllib.parse.quote(cookie_str)}"
            
            final_url = f"{video_url}|{headers_str}"
            
            xbmc.log(f"[Sunporno] Direct playback URL: {final_url[:200]}...", xbmc.LOGINFO)
            
            li = xbmcgui.ListItem(path=final_url)
            li.setMimeType('video/mp4')
            li.setProperty('IsPlayable', 'true')
            li.setContentLookup(False)
            
            xbmcplugin.setResolvedUrl(self.addon_handle, True, li)

    def _extract_embed_url(self, content):
        meta_embed = re.search(r'<meta[^>]+property=["\']og:video:secure_url["\'][^>]+content=["\']([^"\']+)["\']', content)
        if meta_embed:
            return meta_embed.group(1)
        
        meta_embed2 = re.search(r'<meta[^>]+property=["\']og:video["\'][^>]+content=["\']([^"\']+)["\']', content)
        if meta_embed2:
            return meta_embed2.group(1)
        
        iframe_match = re.search(r'<iframe[^>]+src=["\']([^"\']*embed[^"\']*)["\']', content)
        if iframe_match:
            src = iframe_match.group(1)
            if not src.startswith('http'):
                src = urllib.parse.urljoin(self.base_url, src)
            return src
        
        embed_link = re.search(r'href=["\']([^"\']*/embed/\d+[^"\']*)["\']', content)
        if embed_link:
            src = embed_link.group(1)
            if not src.startswith('http'):
                src = urllib.parse.urljoin(self.base_url, src)
            return src
        
        js_embed = re.search(r'embedUrl\s*[:=]\s*["\']([^"\']+)["\']', content)
        if js_embed:
            return js_embed.group(1)
        
        return None

    def _extract_video_from_embed(self, embed_url):
        content = self.make_request(embed_url)
        if not content:
            return None
        
        try:
            from resources.lib.decoders.sunporno_decoder import SunpornoDecoder
            decoder = SunpornoDecoder()
            video_info = decoder.decode_embed(content)
            
            if video_info:
                xbmc.log(f"[Sunporno] Decoder extracted video_url: {video_info.get('video_url', 'N/A')[:100]}...", xbmc.LOGINFO)
                xbmc.log(f"[Sunporno] Decoder extracted rnd: {video_info.get('rnd', 'N/A')}", xbmc.LOGINFO)
                return video_info
                
        except Exception as e:
            xbmc.log(f"[Sunporno] Decoder error: {e}", xbmc.LOGERROR)
        
        xbmc.log("[Sunporno] Using fallback extraction", xbmc.LOGINFO)
        return self._fallback_extract(content)

    def _extract_video_from_main_page(self, content):
        result = {'video_url': None, 'rnd': None}
        
        try:
            from resources.lib.decoders.sunporno_decoder import SunpornoDecoder
            decoder = SunpornoDecoder()
            result = decoder.decode(content) or {'video_url': None, 'rnd': None}
            if result.get('video_url'):
                xbmc.log(f"[Sunporno] Main page decoder extracted: {result['video_url'][:100]}...", xbmc.LOGINFO)
                return result
        except Exception as e:
            xbmc.log(f"[Sunporno] Main page decoder error: {e}", xbmc.LOGERROR)
        
        patterns = [
            r'video_url\s*:\s*["\']([^"\']+)["\']',
            r'"video_url"\s*:\s*"([^"]+)"',
            r"video_url\s*:\s*'([^']+)'",
            r'<source[^>]+src=["\']([^"\']+\.mp4[^"\']*)["\']',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, content)
            if match:
                video_url = match.group(1).replace('\\/', '/')
                if video_url.startswith('/'):
                    video_url = self.base_url + video_url
                result['video_url'] = video_url
                break
        
        if not result['rnd']:
            result['rnd'] = str(int(time.time() * 1000))
        
        return result if result['video_url'] else None

    def _fallback_extract(self, content):
        result = {'video_url': None, 'rnd': None}
        
        patterns = [
            r'video_url\s*:\s*["\']([^"\']+)["\']',
            r'"video_url"\s*:\s*"([^"]+)"',
            r"video_url\s*:\s*'([^']+)'",
            r'<source[^>]+src=["\']([^"\']+\.mp4[^"\']*)["\']',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, content)
            if match:
                video_url = match.group(1).replace('\\/', '/')
                if video_url.startswith('/'):
                    video_url = self.base_url + video_url
                result['video_url'] = video_url
                break
        
        rnd_patterns = [
            r'rnd["\']?\s*:\s*["\']?(\d+)',
            r'\?rnd=(\d+)',
            r'&rnd=(\d+)',
            r'"rnd"\s*:\s*(\d+)',
            r"rnd\s*=\s*(\d+)",
        ]
        
        for pattern in rnd_patterns:
            match = re.search(pattern, content)
            if match:
                result['rnd'] = match.group(1)
                break
        
        if not result['rnd']:
            result['rnd'] = str(int(time.time() * 1000))
            xbmc.log(f"[Sunporno] Generated rnd: {result['rnd']}", xbmc.LOGINFO)
        
        return result if result['video_url'] else None
