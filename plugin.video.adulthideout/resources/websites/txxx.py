#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import json
import urllib.parse
from urllib import request, error
import xbmc
import xbmcgui
import xbmcplugin
from resources.lib.base_website import BaseWebsite
from resources.lib.decoders.txxx_decoder import TxxxDecoder

class TxxxWebsite(BaseWebsite):
    def __init__(self, addon_handle):
        """Initializes the TxxxWebsite class."""
        super().__init__('txxx', '', '', addon_handle)
        
        self.content_type_options = ['Straight', 'Gay', 'Trans']
        self.content_type_data = {
            'Straight': {'domain': 'txxx.com', 'api_filter': 'str'},
            'Gay':      {'domain': 'gaytxxx.com', 'api_filter': 'gay'},
            'Trans':    {'domain': 'transtxxx.com', 'api_filter': 'she'} 
        }
        
        self.sort_options = ['Most Popular', 'Latest Updates', 'Top Rated', 'Most Viewed', 'Longest']
        self.sort_paths = {
            'Most Popular': 'most-popular',
            'Latest Updates': 'latest-updates',
            'Top Rated': 'top-rated',
            'Most Viewed': 'most-viewed',
            'Longest': 'longest'
        }
        
        self.headers = {
            'Accept': 'application/json, text/plain, */*',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36',
            'X-Requested-With': 'XMLHttpRequest',
        }

        self.api_filter = 'str'
        self._set_dynamic_urls()

    def _set_dynamic_urls(self):
        """Reads the content type setting and sets the correct domain and API filter."""
        try:
            content_idx = int(self.addon.getSetting('txxx_content_type'))
            if not (0 <= content_idx < len(self.content_type_options)):
                content_idx = 0
        except (ValueError, TypeError):
            content_idx = 0
        
        selected_content = self.content_type_options[content_idx]
        data = self.content_type_data[selected_content]
        
        domain = data['domain']
        self.api_filter = data['api_filter']
        
        self.base_url = f"https://{domain}/"
        self.search_url = f"https://{domain}/search/{{}}"
        self.logger.info(f"Txxx content type set to '{selected_content}', using domain: {self.base_url} and api_filter: {self.api_filter}")

    def get_start_url_and_label(self):
        """Overrides the base method to show the content type in the label."""
        url, label = super().get_start_url_and_label()
        try:
            content_idx = int(self.addon.getSetting('txxx_content_type'))
            content_name = self.content_type_options[content_idx]
        except (ValueError, TypeError, IndexError):
            content_name = self.content_type_options[0]

        sort_label_part = ""
        if '[COLOR yellow]' in label:
            sort_label_part = label.split('[COLOR yellow]')[1].split('[/COLOR]')[0]
        
        final_label = f"Txxx ({content_name}) [COLOR yellow]{sort_label_part}[/COLOR]"
        return url, final_label

    def select_content_type(self, original_url=None):
        """Opens a dialog to select the content type and updates the view."""
        try:
            current_setting_idx = int(self.addon.getSetting('txxx_content_type'))
        except (ValueError, TypeError):
            current_setting_idx = 0

        dialog = xbmcgui.Dialog()
        idx = dialog.select("Change Content...", self.content_type_options, preselect=current_setting_idx)

        if idx == -1 or idx == current_setting_idx: return

        self.addon.setSetting('txxx_content_type', str(idx))
        self._set_dynamic_urls()
        new_url, _ = self.get_start_url_and_label()
        update_url = f"{sys.argv[0]}?mode=2&url={urllib.parse.quote_plus(new_url)}&website={self.name}"
        xbmc.executebuiltin(f"Container.Update({update_url},replace)")

    def select_sort(self, original_url=None):
        setting_id = f"{self.name}_sort_by"
        try:
            current_idx = int(self.addon.getSetting(setting_id))
        except (ValueError, TypeError):
            current_idx = 0
        
        if not (0 <= current_idx < len(self.sort_options)):
            current_idx = 0

        dialog = xbmcgui.Dialog()
        selected_idx = dialog.select("Sort by...", self.sort_options, preselect=current_idx)

        if selected_idx == -1 or selected_idx == current_idx:
            return

        self.addon.setSetting(setting_id, str(selected_idx))
        
        new_start_url, _ = self.get_start_url_and_label()
        
        update_command = f"Container.Update({sys.argv[0]}?mode=2&website={self.name}&url={urllib.parse.quote_plus(new_start_url)},replace)"
        xbmc.executebuiltin(update_command)

    def _get_context_menu(self, current_url):
        return [
            ('Sort by...', f'RunPlugin({sys.argv[0]}?mode=7&website={self.name}&action=select_sort&original_url={urllib.parse.quote_plus(current_url)})'),
            ('Change Content...', f'RunPlugin({sys.argv[0]}?mode=7&website={self.name}&action=select_content_type&original_url={urllib.parse.quote_plus(current_url)})')
        ]

    def _get_json(self, url, headers=None):
        try:
            req_headers = headers if headers is not None else self.headers
            req = request.Request(url, headers=req_headers)
            with request.urlopen(req, timeout=20) as response:
                if response.getcode() == 200:
                    return json.loads(response.read().decode('utf-8'))
                self.logger.error(f"HTTP Error {response.getcode()} for {url}")
                return None
        except Exception as e:
            self.logger.error(f"Error in _get_json for {url}: {e}")
            return None

    def _add_static_dirs(self, current_url):
        context_menu = self._get_context_menu(current_url)
        self.add_dir('[COLOR blue]Search Txxx[/COLOR]', '', 5, icon=self.icons['search'], context_menu=context_menu)
        self.add_dir('[COLOR blue]Categories[/COLOR]', f"{self.base_url}categories/", 8, icon=self.icons['categories'], context_menu=context_menu)

    def process_content(self, url):
        parsed_url = urllib.parse.urlparse(url)
        path = parsed_url.path.strip('/').lstrip('/')
        
        is_category = path.startswith('categories/')
        is_search = path.startswith('search/')
        is_main_page = not is_category and not is_search

        if is_main_page:
            self._add_static_dirs(url)

        path_parts = path.split('/')
        page = "1"
        if path_parts and path_parts[-1].isdigit():
            page = path_parts.pop()
        
        sort_order = 'most-popular'
        if is_main_page and path_parts:
             sort_order = path_parts[0]
        elif not is_main_page:
            setting_id = f"{self.name}_sort_by"
            saved_sort_setting = self.addon.getSetting(setting_id)
            try:
                sort_idx = int(saved_sort_setting)
                if 0 <= sort_idx < len(self.sort_options):
                    sort_key = self.sort_options[sort_idx]
                    sort_order = self.sort_paths.get(sort_key, 'most-popular')
            except (ValueError, TypeError):
                sort_order = 'most-popular'

        path_for_paging = '/'.join(path_parts) if not is_main_page else sort_order
        filter_string = f"..{page}.all..day"
        
        timeframe = "14400"
        if is_category:
            if len(path_parts) > 1:
                category_name = path_parts[1]
                filter_string = f"categories.{category_name}.{page}.all..day"
        elif is_search:
            timeframe = "259200"
            query_part = path_parts[1] if len(path_parts) > 1 else ''
            api_url = f"{self.base_url}api/videos2.php?params={timeframe}/{self.api_filter}/relevance/60/search..{page}.all..&s={urllib.parse.quote_plus(query_part)}"
        
        if 'api_url' not in locals():
            api_url = f"{self.base_url}api/json/videos2/{timeframe}/{self.api_filter}/{sort_order}/60/{filter_string}.json"
        
        self.logger.info(f"API Call: {api_url}")
        
        data = self._get_json(api_url)
        if not data or 'videos' not in data:
            if not is_main_page: 
                self.notify_error("Could not load video list.")
            return self.end_directory()

        context_menu = self._get_context_menu(url)

        for video in data['videos']:
            title = video.get('title', 'Unknown Title')
            thumbnail = video.get('scr')
            video_dir = video.get('dir')
            video_id = video.get('video_id')
            
            try:
                parts = video.get('duration', '0:0').split(':')
                seconds = int(parts[0]) * 60 + int(parts[1]) if len(parts) == 2 else int(parts[0])
            except (ValueError, IndexError): seconds = 0

            play_data = json.dumps({'video_id': video_id, 'dir': video_dir, 'title': title, 'thumbnail': thumbnail, 'base_url': self.base_url})
            info_labels = {'title': title, 'duration': seconds, 'cast': [model.strip() for model in video.get('models', '').split(',')], 'plot': video.get('description', ''), 'premiered': video.get('post_date', '1970-01-01').split(' ')[0], 'studio': video.get('content_source_name', self.name)}
            
            self.add_link(name=title, url=play_data, mode=4, icon=thumbnail, fanart=self.fanart, context_menu=context_menu, info_labels=info_labels)

        current_page = int(data.get('params', {}).get('page', 1))
        total_pages = int(data.get('pages', 1))
        if current_page < total_pages:
            next_page_path = f"{path_for_paging}/{current_page + 1}"
            next_page_url = urllib.parse.urljoin(self.base_url, next_page_path)
            
            self.add_dir(name='[COLOR cyan]>> Next Page[/COLOR]', url=next_page_url, mode=2, context_menu=context_menu)
            
        self.end_directory()

    def play_video(self, url):
        try:
            video_data = json.loads(url)
            video_id, video_dir, title, thumbnail, base_url = [video_data.get(k) for k in ['video_id', 'dir', 'title', 'thumbnail', 'base_url']]
        except (json.JSONDecodeError, TypeError): 
            return self.notify_error("Invalid video data.")

        if not all([video_id, video_dir, base_url]): 
            return self.notify_error("Missing video information.")

        api_url = f"{base_url}api/videofile.php?video_id={video_id}&lifetime=8640000"
        
        req_headers = self.headers.copy()
        video_page_url = f"{base_url}videos/{video_id}/{video_dir}/"
        req_headers['Referer'] = video_page_url

        stream_info = self._get_json(api_url, headers=req_headers)

        if stream_info and isinstance(stream_info, list) and len(stream_info) > 0 and 'video_url' in stream_info[0]:
            encoded_path_raw = stream_info[0]['video_url']
            
            decoder = TxxxDecoder()
            final_url = decoder.decode_stream_url(encoded_path_raw, base_url, video_page_url, self.logger)

            if final_url:
                list_item = xbmcgui.ListItem(title, path=final_url)
                list_item.setArt({'thumb': thumbnail, 'icon': 'DefaultVideo.png'})
                list_item.setProperty('IsPlayable', 'true')
                xbmcplugin.setResolvedUrl(self.addon_handle, True, listitem=list_item)
                self.logger.info(f"Successfully constructed final URL for video {video_id}")
            else:
                self.notify_error("Error decoding video link.")
        else: 
            self.logger.warning(f"No stream_info for video {video_id}")
            self.notify_error("No playable streams found.")

    def search(self, query):
        if not query: return
        super().search(query)

    def process_categories(self, url):
        api_url = f"{self.base_url}api/json/categories/14400/{self.api_filter}.all.en.json"
        self.logger.info(f"Category API Call: {api_url}")
        data = self._get_json(api_url)
        if not data or 'categories' not in data: 
            return self.notify_error("Could not load categories.")
            
        context_menu = self._get_context_menu(url)
        for category in sorted(data.get('categories', []), key=lambda x: x.get('title', '')):
            if (cat_title := category.get('title')) and (cat_dir := category.get('dir')):
                cat_url = f"{self.base_url}categories/{cat_dir}/"
                self.add_dir(name=cat_title, url=cat_url, mode=2, icon=self.icons['categories'], context_menu=context_menu)
        
        self.end_directory()