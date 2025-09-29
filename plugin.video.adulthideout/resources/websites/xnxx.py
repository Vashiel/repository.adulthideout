#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
import sys
import urllib.parse
import urllib.request
import traceback
import html
import io
import xbmc
import xbmcgui
import xbmcplugin
from resources.lib.base_website import BaseWebsite

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
        
        # Options
        self.sort_options = ['Best', "Today's selection", 'Hits']
        self.content_options = ['Straight', 'Gay', 'Trans']
        
        # Settings IDs
        self.setting_id_sort = "xnxx_sort_order"
        self.setting_id_content = "xnxx_content_type"

        # Correct URL paths for each combination of content and sort order
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
        
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept-Encoding': 'gzip, deflate'
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

        # Get the specific path from the nested dictionary
        try:
            path = self.sort_paths[content_key][sort_key]
        except KeyError:
            # Fallback to the default 'Best' for the selected category
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

    def make_request(self, url):
        try:
            req = urllib.request.Request(url, headers=self.headers)
            with urllib.request.urlopen(req, timeout=20) as response:
                if response.getcode() != 200:
                    self.notify_error(f"HTTP Error: {response.getcode()}")
                    return None
                encoding = response.info().get('Content-Encoding')
                if encoding == 'gzip':
                    import gzip
                    buf = response.read()
                    html_content_bytes = gzip.GzipFile(fileobj=io.BytesIO(buf)).read()
                else:
                    html_content_bytes = response.read()
                return html_content_bytes.decode('utf-8', errors='ignore')
        except Exception as e:
            self.notify_error(f"Download fehlgeschlagen: {e}")
            self.logger.error(traceback.format_exc())
            return None

    def process_content(self, url):
        if not url:
            url = self._get_start_url()

        self.add_dir('[COLOR blue]Search[/COLOR]', url='', mode=5)

        html_content = self.make_request(url)
        if not html_content:
            return self.end_directory()

        # Flexible pattern to find videos on all page types
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
            self.notify_info("Keine Videos gefunden.")
            return self.end_directory()
        
        context_menu = [
            ('Content Type...', f'RunPlugin({sys.argv[0]}?mode=7&action=select_content_type&website={self.name})'),
            ('Sort by...', f'RunPlugin({sys.argv[0]}?mode=7&action=select_sort_order&website={self.name})')
        ]

        for data in video_list:
            page_url = urllib.parse.urljoin(self.base_url, data['url'])
            duration = (data.get('duration') or 'N/A').strip()
            display_title = f"{html.unescape(data['title'])} [COLOR yellow]({duration})[/COLOR]"
            thumbnail = data.get('thumb', '')
            large_thumb = thumbnail.replace('/thumbs169xnxxll/', '/thumbslll/').replace('/thumbs169lll/', '/thumbslll/')
            
            self.add_link(name=display_title, url=page_url, mode=4, icon=large_thumb, fanart=self.fanart, context_menu=context_menu)

        next_page_match = re.search(r'<a[^>]+href="([^"]+)"[^>]*class="[^"]*(?:next|pagination-button)[^"]*"', html_content)
        if next_page_match:
            next_url = urllib.parse.urljoin(url, html.unescape(next_page_match.group(1)))
            self.add_dir('[COLOR yellow]Nächste Seite >>[/COLOR]', url=next_url, mode=2)

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
            self.notify_error("Konnte keinen abspielbaren Stream finden.")