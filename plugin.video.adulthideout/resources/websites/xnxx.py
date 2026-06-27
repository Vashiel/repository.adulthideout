#!/usr/bin/env python

import re
import sys
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar
from io import BytesIO
import gzip
import traceback
import html
import xbmc
import xbmcgui
import xbmcplugin
from resources.lib.base_website import BaseWebsite
from resources.lib.lookup_info import choose_and_open, extract_html_items

class Xnxx(BaseWebsite):
    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name='xnxx',
            base_url='https://www.xnxx.com',
            search_url='https://www.xnxx.com/search/{}',
            addon_handle=addon_handle,
            addon=addon
        )
        self.display_name = 'XNXX'
        
        self.sort_options = ['Best', "Today's selection", 'Hits']
        self.content_options = ['Straight', 'Gay', 'Trans']
        
        self.setting_id_sort = "xnxx_sort_order"
        self.setting_id_content = "xnxx_content_type"

        self.sort_paths = {
            'Straight': {
                'Best': '/best',
                "Today's selection": '/todays-selection',
                'Hits': '/hits'
            },
            'Gay': {
                'Best': '/best-of-gay',
                "Today's selection": '/gay/todays-selection',
                'Hits': '/gay-hits'
            },
            'Trans': {
                'Best': '/best-of-trans',
                "Today's selection": '/shemale/todays-selection',
                'Hits': '/trans-hits'
            }
        }

    def get_current_content_key(self):
        try:
            content_index = int(self.addon.getSetting(self.setting_id_content))
        except (ValueError, TypeError):
            content_index = 0
        if not 0 <= content_index < len(self.content_options):
            content_index = 0
        return self.content_options[content_index]

    def get_current_sort_key(self):
        try:
            sort_index = int(self.addon.getSetting(self.setting_id_sort))
        except (ValueError, TypeError):
            sort_index = 0
        if not 0 <= sort_index < len(self.sort_options):
            sort_index = 0
        return self.sort_options[sort_index]

    def _get_start_url(self):
        content_key = self.get_current_content_key()
        sort_key = self.get_current_sort_key()

        try:
            path = self.sort_paths[content_key][sort_key]
        except KeyError:
            path = self.sort_paths[content_key]['Best']

        return urllib.parse.urljoin(self.base_url, path)

    def get_start_url_and_label(self):
        content_key = self.get_current_content_key()
        sort_key = self.get_current_sort_key()
        url = self._get_start_url()
        label_suffix = f"{content_key} - {sort_key}"
        label = f"{self.display_name} [COLOR yellow]({label_suffix})[/COLOR]"
        return url, label

    def select_content_type(self, original_url=None):
        current_key = self.get_current_content_key()
        try:
            preselect_idx = self.content_options.index(current_key)
        except ValueError:
            preselect_idx = 0
        
        dialog = xbmcgui.Dialog()
        idx = dialog.select("Content Type...", self.content_options, preselect=preselect_idx)

        if idx != -1:
            self.addon.setSetting(self.setting_id_content, str(idx))
            new_url = self._get_start_url()
            
            update_command = f"Container.Update({sys.argv[0]}?mode=2&website={self.name}&url={urllib.parse.quote_plus(new_url)})"
            xbmc.sleep(250)
            xbmc.executebuiltin(update_command)

    def select_sort_order(self, original_url=None):
        current_key = self.get_current_sort_key()
        try:
            preselect_idx = self.sort_options.index(current_key)
        except ValueError:
            preselect_idx = 0
        
        dialog = xbmcgui.Dialog()
        idx = dialog.select("Sort by...", self.sort_options, preselect=preselect_idx)

        if idx != -1:
            self.addon.setSetting(self.setting_id_sort, str(idx))
            new_url = self._get_start_url()
            
            update_command = f"Container.Update({sys.argv[0]}?mode=2&website={self.name}&url={urllib.parse.quote_plus(new_url)})"
            xbmc.sleep(250)
            xbmc.executebuiltin(update_command)

    def get_headers(self, referer=None):
        headers = {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/*,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
            'Sec-Ch-Ua': '"Google Chrome";v="129", "Not=A?Brand";v="8", "Chromium";v="129"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"Windows"',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36'
        }
        if referer:
            headers['Referer'] = referer
        return headers

    def make_request(self, url, max_retries=3, retry_wait=5000):
        headers = self.get_headers(url)
        cookie_jar = CookieJar()
        handler = urllib.request.HTTPCookieProcessor(cookie_jar)
        opener = urllib.request.build_opener(handler)

        for attempt in range(max_retries):
            try:
                request = urllib.request.Request(url, headers=headers)
                with opener.open(request, timeout=20) as response:
                    encoding = response.info().get('Content-Encoding')
                    raw_data = response.read()
                    if encoding == 'gzip':
                        data = gzip.GzipFile(fileobj=BytesIO(raw_data)).read()
                    else:
                        data = raw_data
                    content = data.decode('utf-8', errors='ignore')
                    return content
            except (urllib.error.HTTPError, urllib.error.URLError) as e:
                self.logger.warning(f"[{self.name}] make_request attempt {attempt+1} failed: {e}")
                if attempt < max_retries - 1:
                    xbmc.sleep(retry_wait)

        self.notify_error(f"Failed to fetch URL: {url}")
        return ""

    def process_content(self, url):
        if not url:
            url = self._get_start_url()

        # Check action for Related Videos view
        params = {}
        if len(sys.argv) > 2 and sys.argv[2]:
            params = dict(urllib.parse.parse_qsl(sys.argv[2][1:]))
        action = params.get('action')
        if action == "show_related":
            self.process_related_videos(url)
            return

        self.add_dir('[COLOR blue]Search[/COLOR]', url='', mode=5)

        html_content = self.make_request(url)
        if not html_content:
            return self.end_directory()

        video_pattern = re.compile(
            r'<div[^>]*class="[^"]*thumb-block[^"]*"[^>]*>.*?'
            r'<img[^>]*data-src="(?P<thumb>https?://[^"]+)".*?'
            r'<a[^>]*href="(?P<url>/video-[^"]+)"[^>]*title="(?P<title>[^"]+)"[^>]*>.*?'
            r'(?:<p[^>]*class="metadata"[^>]*>.*?(?P<duration>\d+min|\d+:\d{2}(?::\d{2})?).*?</p>)?',
            re.DOTALL | re.IGNORECASE
        )
        matches = video_pattern.finditer(html_content)
        
        video_list = [m.groupdict() for m in matches]
        if not video_list and "search" not in url:
            self.notify_info("No videos found.")
            return self.end_directory()

        for data in video_list:
            page_url = urllib.parse.urljoin(self.base_url, data['url'])
            duration = (data.get('duration') or 'N/A').strip()
            display_title = f"{html.unescape(data['title'])} [COLOR yellow]({duration})[/COLOR]"
            thumbnail = data.get('thumb', '')
            large_thumb = thumbnail.replace('/thumbs169xnxxll/', '/thumbslll/').replace('/thumbs169lll/', '/thumbslll/')
            
            context_menu = [
                ('Explore similar', f'RunPlugin({sys.argv[0]}?mode=7&action=explore_similar&website={self.name}&original_url={urllib.parse.quote_plus(page_url)})'),
                ('Content Type...', f'RunPlugin({sys.argv[0]}?mode=7&action=select_content_type&website={self.name})'),
                ('Sort by...', f'RunPlugin({sys.argv[0]}?mode=7&action=select_sort_order&website={self.name})')
            ]
            self.add_link(name=display_title, url=page_url, mode=4, icon=large_thumb, fanart=self.fanart, context_menu=context_menu)

        next_page_match = re.search(r'<a[^>]+href="([^"]+)"[^>]*class="[^"]*(?:next|pagination-button)[^"]*"', html_content)
        if next_page_match:
            next_url = urllib.parse.urljoin(url, html.unescape(next_page_match.group(1)))
            self.add_dir('[COLOR yellow]Next Page >>[/COLOR]', url=next_url, mode=2)

        self.end_directory()

    def play_video(self, url):
        html_content = self.make_request(url)
        if not html_content: return

        stream_url = None
        hls_match = re.search(r"setVideoHLS\('(.*?)'\)", html_content)
        if hls_match:
            stream_url = hls_match.group(1)
        else:
            high_quality_match = re.search(r"setVideoUrlHigh\('(.*?)'\)", html_content)
            if high_quality_match:
                stream_url = high_quality_match.group(1)
            else:
                low_quality_match = re.search(r"setVideoUrlLow\('(.*?)'\)", html_content)
                if low_quality_match:
                    stream_url = low_quality_match.group(1)
        
        if stream_url:
            list_item = xbmcgui.ListItem(path=stream_url)
            if '.m3u8' in stream_url:
                list_item.setProperty('inputstream', 'inputstream.adaptive')
                list_item.setProperty('inputstream.adaptive.manifest_type', 'hls')
                list_item.setMimeType('application/vnd.apple.mpegurl')
            else:
                list_item.setMimeType('video/mp4')
            xbmcplugin.setResolvedUrl(self.addon_handle, True, list_item)
        else:
            self.notify_error("Could not find a playable stream.")

    def process_related_videos(self, url):
        self.add_dir('[COLOR blue]Search[/COLOR]', url='', mode=5)
        content = self.make_request(url)
        if not content:
            self.notify_error("Failed to load video page")
            self.end_directory()
            return
            
        match = re.search(r'var\s+video_related\s*=\s*(\[.*?\])\s*;', content, re.DOTALL)
        if not match:
            self.notify_info("No similar videos found.")
            self.end_directory()
            return
            
        try:
            import json
            data = json.loads(match.group(1))
            base_url = urllib.parse.urlparse(url).scheme + "://" + urllib.parse.urlparse(url).netloc
            for item in data:
                rel_url = item.get("u", "")
                if not rel_url:
                    continue
                video_url = urllib.parse.urljoin(base_url, rel_url)
                title = html.unescape(item.get("tf", item.get("t", "Related Video"))).replace('`', "'")
                duration = item.get("d", "")
                thumb = item.get("i", "")
                large_thumb = thumb.replace('/thumbs169xnxxll/', '/thumbslll/').replace('/thumbs169lll/', '/thumbslll/')
                
                context_menu = [
                    ('Explore similar', f'RunPlugin({sys.argv[0]}?mode=7&action=explore_similar&website={self.name}&original_url={urllib.parse.quote_plus(video_url)})'),
                    ('Content Type...', f'RunPlugin({sys.argv[0]}?mode=7&action=select_content_type&website={self.name})'),
                    ('Sort by...', f'RunPlugin({sys.argv[0]}?mode=7&action=select_sort_order&website={self.name})')
                ]
                display_title = f"{title} [COLOR yellow]({duration})[/COLOR]"
                self.add_link(name=display_title, url=video_url, mode=4, icon=large_thumb, fanart=self.fanart, context_menu=context_menu)
        except Exception as e:
            self.notify_error("Failed to parse related videos")
            
        self.end_directory()

    def explore_similar(self, original_url=None):
        if not original_url:
            self.notify_info("No video URL available")
            return

        html_content = self.make_request(original_url)
        if not html_content:
            self.notify_error("Could not load video info")
            return

        patterns = [
            ("Pornstar", r'href="(/pornstars/[^"]+)"[^>]*>(?:<span[^>]*>)?([^<]+)', 2),
            ("Tag", r'href="(/search/[^"]+)"[^>]*>(?:<span[^>]*>)?([^<]+)', 2),
            ("Tag", r'href="(/tags/[^"]+)"[^>]*>(?:<span[^>]*>)?([^<]+)', 2),
            ("Category", r'href="(/c/[^"]+)"[^>]*>(?:<span[^>]*>)?([^<]+)', 2),
            ("Maker", r'href="(/porn-maker/[^"]+)"[^>]*>(?:<span[^>]*>)?([^<]+)', 2),
            ("Profile", r'href="(/profiles/[^"]+)"[^>]*>(?:<span[^>]*>)?([^<]+)', 2),
            ("Channel", r'href="(/channels/[^"]+)"[^>]*>(?:<span[^>]*>)?([^<]+)', 2),
        ]
        items = extract_html_items(html_content, self.base_url, patterns)
        
        if items:
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
                "url": original_url,
                "mode": 2,
                "action": "show_related"
            })
            
        if not choose_and_open(items, self.name, "Explore similar"):
            self.logger.info("[xnxx] No lookup target selected for {}".format(original_url))
