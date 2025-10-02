#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
import urllib.parse as urllib_parse
import urllib.request as urllib_request
from http.cookiejar import CookieJar
import xbmc
import xbmcgui
import xbmcplugin
import sys
from resources.lib.base_website import BaseWebsite
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import time
from html.parser import HTMLParser

# Helper class to parse HTML and find video blocks
class MissAVParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_video_grid = False
        self.in_thumbnail_div = False
        self.in_title_link = False
        self.videos = []
        self.current_video = {}

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        # Find the main grid of videos
        if tag == 'div' and 'grid' in attrs.get('class', ''):
            self.in_video_grid = True

        if self.in_video_grid:
            # Check for the start of a new video item
            if tag == 'div' and 'thumbnail group' in attrs.get('class', ''):
                self.in_thumbnail_div = True
                self.current_video = {}

            if self.in_thumbnail_div:
                if tag == 'a' and 'href' in attrs:
                    if not 'url' in self.current_video:
                        self.current_video['url'] = attrs['href']
                
                if tag == 'img' and 'data-src' in attrs:
                    self.current_video['thumb'] = attrs.get('data-src')
                    self.current_video['title'] = attrs.get('alt', '')

                if tag == 'span' and 'absolute bottom-1' in attrs.get('class', ''):
                    self.in_title_link = True # A simple flag to grab the next data chunk

    def handle_data(self, data):
        if self.in_title_link:
            duration = data.strip()
            if re.match(r'[\d:]+', duration):
                self.current_video['duration'] = duration
            self.in_title_link = False

    def handle_endtag(self, tag):
        if tag == 'div' and self.in_thumbnail_div:
            # End of a video item, check if we have enough data
            if all(k in self.current_video for k in ['url', 'thumb', 'title']):
                self.videos.append(self.current_video)
            self.in_thumbnail_div = False
            self.current_video = {}
        
        # This is a simplification; we assume the grid ends when parsing is done
        # A more robust solution would track div nesting.

class HlsProxy(HTTPServer):
    def __init__(self, server_address, RequestHandlerClass, state):
        super().__init__(server_address, RequestHandlerClass)
        self.state = state

class ProxyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            state = self.server.state
            opener = state.get('opener')
            if not opener: return self.send_error(500, 'Proxy opener not configured')
            playlist_url = state.get('real_playlist_url')
            if not playlist_url: return self.send_error(404, 'Proxy not configured')
            base_stream_url = playlist_url.rsplit('/', 1)[0]
            headers = state.get('headers')
            request_file = self.path.rsplit('/', 1)[-1]
            if request_file.endswith('.m3u8'):
                req = urllib_request.Request(playlist_url, headers=headers)
                with opener.open(req, timeout=15) as response:
                    content = response.read().decode('utf-8', errors='ignore')
                modified_lines, segment_map, segment_index = [], {}, 0
                for line in content.splitlines():
                    line = line.strip()
                    if line and not line.startswith('#'):
                        proxy_segment_name = f"{segment_index}.ts"
                        segment_map[proxy_segment_name] = f"{base_stream_url}/{line}"
                        modified_lines.append(proxy_segment_name)
                        segment_index += 1
                    else: modified_lines.append(line)
                state['segment_map'] = segment_map
                self.send_response(200)
                self.send_header('Content-type', 'application/vnd.apple.mpegurl')
                self.end_headers()
                self.wfile.write('\n'.join(modified_lines).encode('utf-8'))
            elif request_file.endswith('.ts'):
                segment_map = state.get('segment_map', {})
                real_segment_url = segment_map.get(request_file)
                if not real_segment_url: return self.send_error(404, 'Segment not found')
                req = urllib_request.Request(real_segment_url, headers=headers)
                with opener.open(req, timeout=15) as response:
                    segment_data = response.read()
                    content_type = response.getheader('Content-Type', 'video/mp2t')
                self.send_response(200)
                self.send_header('Content-type', content_type)
                self.end_headers()
                self.wfile.write(segment_data)
            else:
                self.send_error(404, 'File Not Found')
        except Exception as e:
            xbmc.log(f"Proxy Error: {e}", level=xbmc.LOGERROR)
            self.send_error(500, str(e))
    def log_message(self, format, *args): pass

class MissavWebsite(BaseWebsite):
    def __init__(self, addon_handle):
        super().__init__(name='missav', base_url='https://missav123.com/', search_url='https://missav123.com/en/search/{}', addon_handle=addon_handle)
        self.cookie_jar = CookieJar()
        self.opener = urllib_request.build_opener(urllib_request.HTTPCookieProcessor(self.cookie_jar))
        self.establish_session()
        self.sort_options = ['New Releases', 'Recent Update', 'Most Viewed Today', 'Most Viewed by Week', 'Most Viewed by Month']
        self.sort_paths = {'New Releases': 'dm588/en/release', 'Recent Update': 'dm514/en/new', 'Most Viewed Today': 'dm291/en/today-hot', 'Most Viewed by Week': 'dm169/en/weekly-hot', 'Most Viewed by Month': 'dm257/en/monthly-hot'}
        self.actress_sort_options = ['Videos', 'Debut']
        self.actress_sort_paths = {'Videos': 'en/actresses?sort=videos', 'Debut': 'en/actresses?sort=debut'}
        self.actress_filters = {'height': {'label': 'Height', 'setting': f'{self.name}_actress_filter_height', 'options': [('All', ''), ('131-135cm', '131-135'), ('136-140cm', '136-140'), ('141-145cm', '141-145'), ('146-150cm', '146-150'), ('151-155cm', '151-155'), ('156-160cm', '156-160'), ('161-165cm', '161-165'), ('166-170cm', '166-170'), ('171-175cm', '171-175'), ('176-180cm', '176-180'), ('181-185cm', '181-185'), ('186-190cm', '186-190')]}, 'cup': {'label': 'Cup Size', 'setting': f'{self.name}_actress_filter_cup', 'options': [('All', ''), ('A cup', 'A'), ('B cup', 'B'), ('C cup', 'C'), ('D cup', 'D'), ('E cup', 'E'), ('F cup', 'F'), ('G cup', 'G'), ('H cup', 'H'), ('I cup', 'I'), ('J cup', 'J'), ('K cup', 'K'), ('L cup', 'L'), ('M cup', 'M'), ('N cup', 'N'), ('O cup', 'O'), ('P cup', 'P'), ('Q cup', 'Q')]}, 'age': {'label': 'Age', 'setting': f'{self.name}_actress_filter_age', 'options': [('All', ''), ('< 20', '0-20'), ('20 - 30', '20-30'), ('30 - 40', '30-40'), ('40 - 50', '40-50'), ('50 - 60', '50-60'), ('> 60', '60-99')]}, 'debut': {'label': 'Debut Year', 'setting': f'{self.name}_actress_filter_debut', 'options': [('All', ''), ('Before 2025', '2025'), ('Before 2024', '2024'), ('Before 2023', '2023'), ('Before 2022', '2022'), ('Before 2021', '2021'), ('Before 2020', '2020'), ('Before 2019', '2019'), ('Before 2018', '2018'), ('Before 2017', '2017'), ('Before 2016', '2016'), ('Before 2015', '2015'), ('Before 2014', '2014'), ('Before 2013', '2013'), ('Before 2012', '2012'), ('Before 2011', '2011'), ('Before 2010', '2010')]}}

    def get_headers(self, url):
        return {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36', 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8', 'Accept-Language': 'de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7', 'Referer': url, 'Connection': 'keep-alive', 'Upgrade-Insecure-Requests': '1', 'Sec-Fetch-Dest': 'document', 'Sec-Fetch-Mode': 'navigate', 'Sec-Fetch-Site': 'same-origin', 'Sec-Fetch-User': '?1'}

    def establish_session(self):
        self.logger.info("Establishing session to get initial cookies...")
        try:
            headers = self.get_headers(self.base_url)
            request = urllib_request.Request(self.base_url, headers=headers)
            with self.opener.open(request, timeout=20) as response:
                self.logger.info(f"Session established with status: {response.getcode()}")
        except Exception as e:
            self.logger.error(f"Failed to establish session: {e}")
            self.notify_error("Could not establish session with website.")

    def make_request(self, url, data=None, max_retries=3, retry_wait=3000):
        headers = self.get_headers(url)
        for attempt in range(max_retries):
            try:
                request = urllib_request.Request(url, data=data, headers=headers)
                with self.opener.open(request, timeout=20) as response:
                    return response.read().decode('utf-8', errors='ignore')
            except urllib_request.HTTPError as e:
                self.logger.error(f"HTTP error fetching {url} (attempt {attempt + 1}/{max_retries}): {e.code} {e.reason}")
                if e.code == 403:
                    self.logger.warning("Got 403 Forbidden, trying to re-establish session...")
                    self.establish_session() 
            except Exception as e:
                self.logger.error(f"Request error fetching {url} (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                self.logger.info(f"Retrying in {retry_wait / 1000} seconds...")
                xbmc.sleep(retry_wait)
        self.notify_error(f"Failed to fetch URL after {max_retries} attempts: {url}")
        return ""

    def process_content(self, url):
        self.logger.info(f"Processing URL: {url}")
        if not url or url == self.base_url:
            url, _ = self.get_video_url_and_label()

        content = self.make_request(url)
        if not content:
            return

        self.add_basic_dirs(url)
        sort_command = f'RunPlugin({sys.argv[0]}?mode=7&action=select_video_sort&website={self.name})'
        video_context_menu = [('Sort Videos by...', sort_command)]
        
        parser = MissAVParser()
        parser.feed(content)
        videos = parser.videos

        if not videos:
            self.logger.error("No videos found using HTMLParser. The page layout may have changed.")
            self.end_directory()
            return

        for video in videos:
            video_url = video.get('url')
            thumbnail = video.get('thumb')
            name = video.get('title', '').strip()
            duration = video.get('duration', '').strip()

            if not all([video_url, thumbnail, name]):
                continue
            
            display_title = f"{name} ({duration})" if duration else name
            
            li = xbmcgui.ListItem(label=display_title)
            li.setArt({'thumb': thumbnail, 'icon': thumbnail, 'fanart': self.fanart})
            li.setProperty('IsPlayable', 'true')
            li.addContextMenuItems(video_context_menu)
            
            try:
                if duration:
                    parts = duration.split(':')
                    seconds = (int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])) if len(parts) == 3 else (int(parts[0]) * 60 + int(parts[1]))
                    li.setInfo('video', {'title': name, 'duration': seconds})
                else:
                    li.setInfo('video', {'title': name})
            except:
                li.setInfo('video', {'title': name})
                
            full_video_url = urllib_parse.urljoin(self.base_url, video_url)
            plugin_url = f"plugin://plugin.video.adulthideout/?url={urllib_parse.quote_plus(full_video_url)}&mode=4&website={self.name}"
            xbmcplugin.addDirectoryItem(self.addon_handle, plugin_url, li, isFolder=False)
            
        next_page_match = re.search(r'<a href="([^"]+)" rel="next"', content)
        if next_page_match:
            next_url = urllib_parse.urljoin(self.base_url, next_page_match.group(1))
            page_num_match = re.search(r'page=(\d+)', next_url)
            page_label = f"Next Page ({page_num_match.group(1)})" if page_num_match else "Next Page"
            self.add_dir(page_label, next_url, 2, self.icons['default'], '')
            
        self.end_directory()

    def get_video_url_and_label(self):
        setting_id = f"{self.name}_video_sort_by"; sort_idx = 0
        try: sort_idx = int(self.addon.getSetting(setting_id))
        except (ValueError, TypeError): pass
        if not (0 <= sort_idx < len(self.sort_options)): sort_idx = 0
        sort_option = self.sort_options[sort_idx]
        sort_path = self.sort_paths.get(sort_option)
        url = urllib_parse.urljoin(self.base_url, sort_path)
        return url, f"[COLOR yellow]Current: {sort_option}[/COLOR]"

    def select_video_sort(self, original_url=None):
        setting_id = f"{self.name}_video_sort_by"; current_idx = 0
        try: current_idx = int(self.addon.getSetting(setting_id))
        except (ValueError, TypeError): pass
        dialog = xbmcgui.Dialog(); idx = dialog.select("Sort Videos by...", self.sort_options, preselect=current_idx)
        if idx != -1: self.addon.setSetting(setting_id, str(idx)); new_base_url, _ = self.get_video_url_and_label(); xbmc.executebuiltin(f"Container.Update({sys.argv[0]}?mode=2&url={urllib_parse.quote_plus(new_base_url)}&website={self.name},replace)")

    def _build_actress_url(self, original_url=None, new_filter_key=None, new_filter_value=None):
        # Fallback for first entry, builds URL from saved settings
        if not original_url:
            base_url, _ = self.get_actress_url_and_label()
            params = {}
            for key, data in self.actress_filters.items():
                value = self.addon.getSetting(data['setting'])
                if value:
                    params[key] = value
            if not params:
                return base_url
            query_string = urllib_parse.urlencode(params)
            return f"{base_url}&{query_string}" if '?' in base_url else f"{base_url}?{query_string}"

        # Main logic: Use the provided URL as the source of truth for existing filters
        parsed_url = urllib_parse.urlparse(original_url)
        base_path = parsed_url.scheme + "://" + parsed_url.netloc + parsed_url.path
        
        params = dict(urllib_parse.parse_qsl(parsed_url.query))
        
        # Update or add the new filter value
        if new_filter_key:
            if new_filter_value: # If a specific value is chosen
                params[new_filter_key] = new_filter_value
            elif new_filter_key in params: # If "All" is chosen (empty value), remove the filter
                del params[new_filter_key]

        if not params:
            return base_path

        query_string = urllib_parse.urlencode(params)
        return f"{base_path}?{query_string}"

    def select_actress_filter(self, original_url=None):
        params = dict(urllib_parse.parse_qsl(sys.argv[2].lstrip('?')))
        filter_key = params.get('filter_key')
        filter_data = self.actress_filters.get(filter_key)
        if not filter_data: return
        
        setting_id = filter_data['setting']
        options = filter_data['options']
        labels = [label for label, value in options]
        current_value = self.addon.getSetting(setting_id)
        preselect = next((i for i, (label, value) in enumerate(options) if value == current_value), 0)
        
        dialog = xbmcgui.Dialog()
        idx = dialog.select(f"Filter by {filter_data['label']}", labels, preselect=preselect)
        
        if idx != -1:
            new_value = options[idx][1]
            # Save setting for persistence across sessions
            self.addon.setSetting(setting_id, new_value)
            
            # Build the new URL by combining existing filters from original_url with the new one
            new_url = self._build_actress_url(
                original_url=original_url, 
                new_filter_key=filter_key, 
                new_filter_value=new_value
            )
            
            xbmc.executebuiltin(f"Container.Update({sys.argv[0]}?mode=9&url={urllib_parse.quote_plus(new_url)}&website={self.name},replace)")

    def reset_actress_filters(self, original_url=None):
        # Clear all filter settings
        for key, data in self.actress_filters.items():
            self.addon.setSetting(data['setting'], "")
        
        # Build the base URL which only contains the sorting parameter, no filters
        new_url, _ = self.get_actress_url_and_label()
        
        self.notify_info("All filters have been reset.")
        xbmc.executebuiltin(f"Container.Update({sys.argv[0]}?mode=9&url={urllib_parse.quote_plus(new_url)}&website={self.name},replace)")

    def get_actress_url_and_label(self):
        setting_id = f"{self.name}_actress_sort_by"; sort_idx = 0
        try: sort_idx = int(self.addon.getSetting(setting_id))
        except (ValueError, TypeError): pass
        sort_option = self.actress_sort_options[sort_idx] if 0 <= sort_idx < len(self.actress_sort_options) else self.actress_sort_options[0]
        sort_path = self.actress_sort_paths.get(sort_option)
        url = urllib_parse.urljoin(self.base_url, sort_path)
        return url, f"Actresses [COLOR yellow]{sort_option}[/COLOR]"

    def select_actress_sort(self, original_url=None):
        setting_id = f"{self.name}_actress_sort_by"
        current_idx = 0
        try: current_idx = int(self.addon.getSetting(setting_id))
        except (ValueError, TypeError): pass
        
        dialog = xbmcgui.Dialog()
        idx = dialog.select("Sort Actresses by...", self.actress_sort_options, preselect=current_idx)
        
        if idx != -1:
            self.addon.setSetting(setting_id, str(idx))
            # Get the new base path for sorting
            new_sort_url, _ = self.get_actress_url_and_label()
            parsed_new = urllib_parse.urlparse(new_sort_url)
            
            # Keep existing filters from the original URL
            parsed_original = urllib_parse.urlparse(original_url)
            params = dict(urllib_parse.parse_qsl(parsed_original.query))
            
            # Update the sort parameter
            params['sort'] = dict(urllib_parse.parse_qsl(parsed_new.query)).get('sort', 'videos')
            
            query_string = urllib_parse.urlencode(params)
            new_url = f"{parsed_new.scheme}://{parsed_new.netloc}{parsed_new.path}?{query_string}"
            
            xbmc.executebuiltin(f"Container.Update({sys.argv[0]}?mode=9&url={urllib_parse.quote_plus(new_url)}&website={self.name},replace)")

    def add_basic_dirs(self, current_url):
        actress_url, actress_label = self.get_actress_url_and_label()
        actress_context_menu = [('Sort by...', f'RunPlugin({sys.argv[0]}?mode=7&action=select_actress_sort&website={self.name})')]
        dirs_data = [{'name': 'Search MissAV', 'url': self.name, 'mode': 5, 'icon': self.icons['search'], 'name_param': self.name}, {'name': 'Categories', 'url': self.name, 'mode': 8, 'icon': self.icons['categories'], 'name_param': self.name}, {'name': actress_label, 'url': actress_url, 'mode': 9, 'icon': self.icons.get('pornstars', self.icons['categories']), 'context_menu': actress_context_menu, 'name_param': actress_label}]
        for item in dirs_data: self.add_dir(name=item['name'], url=item['url'], mode=item['mode'], icon=item['icon'], fanart=self.fanart, context_menu=item.get('context_menu'), name_param=item.get('name_param'))

    def process_categories(self, url):
        self.logger.info(f"Processing Categories, URL: {url}"); main_cat_match = re.search(r'main_cat=([^&]+)', url)
        if main_cat_match: self._process_sub_categories(urllib_parse.unquote_plus(main_cat_match.group(1)))
        else: self._process_main_categories()

    def _process_main_categories(self):
        self.logger.info("Processing main categories from homepage"); content = self.make_request(self.base_url + "en")
        if not content: return self.notify_error("Failed to load main page for categories")
        nav_match = re.search(r'<nav class="hidden xl:flex.*?>(.*?)</nav>', content, re.DOTALL)
        if not nav_match: return self.notify_error("Could not find the main navigation container.")
        nav_content = nav_match.group(1); main_menus = re.findall(r'<span>(Watch JAV|Amateur|Uncensored|Asia AV)</span>', nav_content, re.DOTALL); seen_titles = set()
        for menu_title in main_menus: menu_title = menu_title.strip(); self.add_dir(menu_title, f"main_cat={urllib_parse.quote_plus(menu_title)}", 8, self.icons['categories'], self.fanart); seen_titles.add(menu_title)
        if not seen_titles: self.notify_error("Could not extract main categories from the navigation block.")
        self.end_directory()

    def _process_sub_categories(self, category_title):
        self.logger.info(f"Processing sub-categories for '{category_title}'"); content = self.make_request(self.base_url + "en")
        if not content: return self.notify_error("Failed to load main page for sub-categories")
        nav_match = re.search(r'<nav class="hidden xl:flex.*?>(.*?)</nav>', content, re.DOTALL)
        if not nav_match: return self.notify_error("Could not find the main navigation container.")
        nav_content = nav_match.group(1); category_blocks = re.split(r'<div class="relative">', nav_content); target_block_html = None
        for block_html in category_blocks:
            if f'<span>{category_title}</span>' in block_html: target_block_html = block_html; break
        if not target_block_html: return self.notify_error(f"Could not find category block for '{category_title}'.")
        menu_content_match = re.search(r'<div class="py-1">(.*?)</div>', target_block_html, re.DOTALL)
        if not menu_content_match: return self.notify_error(f"Could not find sub-menu content for '{category_title}'.")
        menu_content = menu_content_match.group(1); sub_links = re.findall(r'<a\s+href="([^"]+)"[^>]*>\s*(.*?)\s*</a>', menu_content, re.DOTALL); found_links = False
        excluded_keywords = ["recent update", "new releases", "most viewed today", "most viewed by week", "most viewed by month"]
        for sub_url, sub_name_html in sub_links:
            sub_name = re.sub(r'<[^>]+>', '', sub_name_html).strip(); sub_name_lower = sub_name.lower()
            if sub_name and 'actress' not in sub_name_lower and sub_name_lower not in excluded_keywords: self.add_dir(sub_name, sub_url, 2, self.icons['default'], self.fanart); found_links = True
        if not found_links: self.notify_error(f"No valid sub-categories found for '{category_title}'.")
        self.end_directory()

    def process_actresses_list(self, url):
        self.logger.info(f"Processing Actresses List from URL: {url}")
        
        if not url or url == self.name:
            current_url = self._build_actress_url()
        else:
            current_url = url
            
        content = self.make_request(current_url)
        if not content: 
            return self.notify_error("Failed to load actresses page")
            
        self.add_basic_dirs(current_url)
        
        # Parse the current URL to get active filters for the UI
        parsed_url = urllib_parse.urlparse(current_url)
        active_filters = dict(urllib_parse.parse_qsl(parsed_url.query))
        
        context_menu = [('Sort by...', f'RunPlugin({sys.argv[0]}?mode=7&action=select_actress_sort&website={self.name}&original_url={urllib_parse.quote_plus(current_url)})')]
        
        # Build filter menu items based on the active URL
        for key, data in self.actress_filters.items():
            current_value_from_url = active_filters.get(key, '')
            current_label = next((label for label, value in data['options'] if value == current_value_from_url), "All")
            label = f"Filter by {data['label']} ([COLOR yellow]{current_label}[/COLOR])"
            action = f"RunPlugin({sys.argv[0]}?mode=7&action=select_actress_filter&website={self.name}&filter_key={key}&original_url={urllib_parse.quote_plus(current_url)})"
            context_menu.append((label, action))
        
        # Add "Reset All Filters" button if any filter is active
        if any(key in active_filters for key in self.actress_filters.keys()):
            context_menu.append(('[COLOR red]Reset All Filters[/COLOR]', f'RunPlugin({sys.argv[0]}?mode=7&action=reset_actress_filters&website={self.name}&original_url={urllib_parse.quote_plus(current_url)})'))
            
        list_container_match = re.search(r'<ul class="mx-auto grid.*?">(.*?)</ul>', content, re.DOTALL)
        matches = []
        if list_container_match: 
            list_html = list_container_match.group(1)
            actress_pattern = re.compile(r'<li>.*?<a href="([^"]+)".*?<img src="([^"]+)".*?<h4[^>]*>([^<]+)</h4>.*?<p[^>]*>([\d,]+\s*videos)</p>.*?</li>', re.DOTALL)
            matches = actress_pattern.findall(list_html)
            
        if not matches:
            self.notify_error("No actresses found. The current filter combination might be too restrictive.")
            li = xbmcgui.ListItem('[I]No results found - Right-click to change filters[/I]')
            li.addContextMenuItems(context_menu)
            li.setProperty('IsPlayable', 'false')
            xbmcplugin.addDirectoryItem(handle=self.addon_handle, url='', listitem=li, isFolder=False)
            self.end_directory()
            return
            
        for page_url, thumb_url, name, video_count in matches:
            display_title = f"{name.strip()} ({video_count.strip()})"
            info = {'title': name.strip(), 'plot': f"{video_count.strip()} available."}
            self.add_dir(name=display_title, url=page_url, mode=2, icon=thumb_url, fanart=self.fanart, info_labels=info, context_menu=context_menu)
            
        next_page_match = re.search(r'<a href="([^"]+)" rel="next"', content)
        if next_page_match:
            next_url = urllib_parse.urljoin(self.base_url, next_page_match.group(1))
            page_num_match = re.search(r'page=(\d+)', next_url)
            if page_num_match:
                page_num = page_num_match.group(1)
                self.add_dir(f"Next Page ({page_num})", next_url, 9, self.icons['default'], '')
                
        self.end_directory()

    def play_video(self, url):
        self.logger.info(f"Starting to play video from URL: {url}"); decoded_url = urllib_parse.unquote_plus(url); content = self.make_request(decoded_url)
        if not content: return
        eval_pattern = r"eval\(function\(p,a,c,k,e,d\)\{.*?\}\('(.*?)',(\d+),(\d+),'(.*?)'\.split\('\|'\).*\)"; eval_match = re.search(eval_pattern, content, re.DOTALL); stream_url = None
        if eval_match:
            self.logger.info("Found packed JavaScript block. Attempting to de-obfuscate."); p, a_str, c_str, k_str = eval_match.groups(); a, c = int(a_str), int(c_str); k = k_str.split('|')
            def int_to_base(n, base): return "0123456789abcdefghijklmnopqrstuvwxyz"[n] if n < base else int_to_base(n // base, base) + "0123456789abcdefghijklmnopqrstuvwxyz"[n % base]
            d = {};
            for i in range(c - 1, -1, -1): key = int_to_base(i, a); d[key] = k[i] if k[i] else key
            result = re.sub(r'\b\w+\b', lambda m: d.get(m.group(0), m.group(0)), p); self.logger.info("Successfully de-obfuscated script. Searching for stream URL.")
            quality_patterns = [r"source1280=\\'([^']+)\\'", r"source842=\\'([^']+)\\'", r"source=\\'([^']+)\\'"]
            for pattern in quality_patterns:
                match = re.search(pattern, result)
                if match: stream_url = match.group(1); self.logger.info(f"Found real stream playlist: {stream_url}"); break
        if not stream_url: self.logger.error("Could not find M3U8 stream URL."); return self.notify_error("Could not find M3U8 stream playlist.")
        httpd = None
        try:
            win = xbmcgui.Window(10000)
            try: last_port = int(win.getProperty('missav_proxy.last_port'))
            except: last_port = 48998
            port = last_port + 1
            if port > 49151: port = 48999
            win.setProperty('missav_proxy.last_port', str(port)); server_address = ('127.0.0.1', port)
            current_video_state = {'real_playlist_url': stream_url, 'base_url': stream_url.rsplit('/', 1)[0], 'headers': self.get_headers(decoded_url), 'opener': self.opener}
            httpd = HlsProxy(server_address, ProxyHandler, current_video_state)
            server_thread = threading.Thread(target=httpd.serve_forever); server_thread.daemon = True; server_thread.start(); self.logger.info(f"Proxy server started on http://127.0.0.1:{port}")
            unique_token = str(time.time()); local_playlist_url = f"http://127.0.0.1:{port}/{unique_token}/playlist.m3u8"
            li = xbmcgui.ListItem(path=local_playlist_url); li.setProperty('IsPlayable', 'true'); li.setMimeType('application/vnd.apple.mpegurl'); li.setProperty('inputstream', 'inputstream.adaptive'); li.setProperty('inputstream.adaptive.manifest_type', 'hls'); xbmcplugin.setResolvedUrl(self.addon_handle, True, li)
            monitor = xbmc.Monitor(); playback_started = False
            for _ in range(15):
                if xbmc.Player().isPlaying(): playback_started = True; self.logger.info("Playback has started."); break
                if monitor.waitForAbort(1): break
            if playback_started:
                while xbmc.Player().isPlaying():
                    if monitor.waitForAbort(1): break
        except Exception as e:
            self.logger.error(f"Failed to start or run proxy server: {e}"); self.notify_error(f"Proxy-Error: {e}")
        finally:
            if httpd: self.logger.info(f"Playback finished or aborted. Shutting down proxy server on port {port}."); httpd.shutdown(); httpd.server_close()