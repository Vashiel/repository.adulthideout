#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
import urllib.parse
import urllib.request
import sys
from http.cookiejar import CookieJar
import html
import json
import xml.etree.ElementTree as ET
import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
import os
from resources.lib.base_website import BaseWebsite

class AshemaletubeWebsite(BaseWebsite):
    config = {
        "name": "ashemaletube",
        "base_url": "https://www.ashemaletube.com",
        "search_url": "https://www.ashemaletube.com/search/?q={}"
    }

    def __init__(self, addon_handle):
        super().__init__(
            name=self.config["name"],
            base_url=self.config["base_url"],
            search_url=self.config["search_url"],
            addon_handle=addon_handle
        )
        self.sort_options = ["Trending", "Date Added", "Most Popular", "Top Rated", "Longest"]
        self.sort_paths = {
            "Trending": "?s=", "Date Added": "?s=&sort=newest",
            "Most Popular": "?s=&sort=most-popular", "Top Rated": "?s=&sort=top-rated",
            "Longest": "?s=&sort=longest"
        }
        self.pornstar_sort_options = ["User Favorites", "Alphabet", "Top Rated", "Date Added", "Most Videos", "Most Galleries", "Most Comments"]
        self.pornstar_sort_paths = {
            "User Favorites": "/pornstars/", "Alphabet": "/pornstars/?sorterMode=2&sort=m_name",
            "Top Rated": "/pornstars/?sorterMode=1&sort=m_rating_for_sort", "Date Added": "/pornstars/?sorterMode=1&sort=m_created",
            "Most Videos": "/pornstars/?sorterMode=1&sort=ms_videos", "Most Galleries": "/pornstars/?sorterMode=1&sort=ms_galleries",
            "Most Comments": "/pornstars/?sorterMode=1&sort=ms_comments"
        }
        
        self.pf_country_options = ['Any', 'Argentina', 'Australia', 'Austria', 'Brazil', 'Canada', 'Chile', 'China', 'Colombia', 'Czechia', 'France', 'Germany', 'Hong Kong', 'Hungary', 'Indonesia', 'Italy', 'Japan', 'Malaysia', 'Mexico', 'Netherlands', 'Peru', 'Philippines', 'Poland', 'Romania', 'Russia', 'Spain', 'Switzerland', 'Thailand', 'United Kingdom', 'United States', 'Venezuela']
        self.pf_country_params = {'Any': '', 'Argentina': '1', 'Australia': '45', 'Austria': '46', 'Brazil': '2', 'Canada': '3', 'Chile': '4', 'China': '5', 'Colombia': '75', 'Czechia': '84', 'France': '9', 'Germany': '10', 'Hong Kong': '13', 'Hungary': '118', 'Indonesia': '14', 'Italy': '15', 'Japan': '17', 'Malaysia': '148', 'Mexico': '18', 'Netherlands': '169', 'Peru': '19', 'Philippines': '20', 'Poland': '188', 'Romania': '191', 'Russia': '23', 'Spain': '26', 'Switzerland': '27', 'Thailand': '28', 'United Kingdom': '29', 'United States': '30', 'Venezuela': '240'}
        
        self.pf_penis_options = ['Any', 'Small', 'Medium', 'Big']
        self.pf_penis_params = {'Any': '', 'Small': '1', 'Medium': '2', 'Big': '3'}
        
        self.pf_breast_options = ['Any', 'Small', 'Medium', 'Big', 'Natural']
        self.pf_breast_params = {'Any': '', 'Small': '1', 'Medium': '2', 'Big': '3', 'Natural': '4'}
        
        self.pf_hair_options = ['Any', 'Black', 'Brown', 'Auburn', 'Red', 'Blonde', 'Varies / Changing', 'Shaved/Bald', 'Mixture / Multi Colored', 'Silver / Grey']
        self.pf_hair_params = {'Any': '', 'Black': '1', 'Brown': '2', 'Auburn': '3', 'Red': '4', 'Blonde': '5', 'Varies / Changing': '6', 'Shaved/Bald': '7', 'Mixture / Multi Colored': '8', 'Silver / Grey': '9'}
        
        self.pf_birthday_options = ['Any', '1960-1969', '1970-1979', '1980-1989', '1990-1999', '2000-2007']
        self.pf_birthday_params = {'Any': '', '1960-1969': '1960', '1970-1979': '1970', '1980-1989': '1980', '1990-1999': '1990', '2000-2007': '2000'}

        self.pf_eyes_options = ['Any', 'Blue', 'Brown', 'Green', 'Grey', 'Hazel']
        self.pf_eyes_params = {'Any': '', 'Blue': '1', 'Brown': '2', 'Green': '3', 'Grey': '4', 'Hazel': '5'}

        self.pf_gender_options = ['Any', 'TS/TG', 'CD/TV', 'Male', 'Female']
        self.pf_gender_params = {'Any': '', 'TS/TG': '1', 'CD/TV': '2', 'Male': '3', 'Female': '4'}
        
        self.pornstar_filter_map = {
            'country': ('Country', 'filterCountry', self.pf_country_options, self.pf_country_params),
            'penis': ('Penis Size', 'filterPenis', self.pf_penis_options, self.pf_penis_params),
            'breast': ('Breast Size', 'filterBreast', self.pf_breast_options, self.pf_breast_params),
            'hair': ('Hair Color', 'filterHair', self.pf_hair_options, self.pf_hair_params),
            'birthday': ('Date of Birth', 'filterBirthday', self.pf_birthday_options, self.pf_birthday_params),
            'eyes': ('Eye Color', 'filterEyes', self.pf_eyes_options, self.pf_eyes_params),
            'gender': ('Gender', 'filterGender', self.pf_gender_options, self.pf_gender_params),
        }

    def get_headers(self, referer=None, is_json=False):
        headers = {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/*,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9', 'Cache-Control': 'no-cache', 'Pragma': 'no-cache',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36'
        }
        if referer: headers['Referer'] = referer
        if is_json: headers.update({'Accept': 'application/json, text/javascript, */*; q=0.01', 'X-Requested-With': 'XMLHttpRequest'})
        return headers

    def make_request(self, url, headers=None, max_retries=3, retry_wait=5000):
        headers = headers or self.get_headers(url)
        for attempt in range(max_retries):
            try:
                cookie_jar = CookieJar()
                opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookie_jar))
                request = urllib.request.Request(url, headers=headers)
                with opener.open(request, timeout=60) as response:
                    return response.read().decode('utf-8', errors='ignore')
            except Exception as e:
                self.logger.error(f"Request failed on attempt {attempt + 1}: {e}")
                if attempt < max_retries - 1: xbmc.sleep(retry_wait)
        self.notify_error(f"Failed to fetch URL: {url}")
        return ""

    def apply_video_sort(self, url):
        saved_sort_idx = int(self.addon.getSetting('ashemaletube_sort_by') or '0')
        sort_option = self.sort_options[saved_sort_idx]
        sort_path = self.sort_paths[sort_option]
        
        parsed_url = urllib.parse.urlparse(url)
        query_params = urllib.parse.parse_qs(parsed_url.query)
        sort_query_params = urllib.parse.parse_qs(urllib.parse.urlparse(sort_path).query)
        
        query_params.pop('s', None)
        query_params.pop('sort', None)
        query_params.update(sort_query_params)
        
        return parsed_url._replace(query=urllib.parse.urlencode(query_params, doseq=True)).geturl()

    def get_pornstar_list_url(self, current_params=None):
        saved_sort_idx = int(self.addon.getSetting('ashemaletube_pornstar_sort_by') or '0')
        sort_option = self.pornstar_sort_options[saved_sort_idx]
        base_sort_path = self.pornstar_sort_paths[sort_option]
        
        parsed_base = urllib.parse.urlparse(base_sort_path)
        all_params = urllib.parse.parse_qs(parsed_base.query)
        
        for filter_type, (label, param_name, options_list, params_dict) in self.pornstar_filter_map.items():
            setting_id = f'ashemaletube_pf_{filter_type}'
            saved_idx = int(self.addon.getSetting(setting_id) or '0')
            if 0 <= saved_idx < len(options_list):
                selected_option_name = options_list[saved_idx]
                param_value = params_dict.get(selected_option_name, '')
                if param_value:
                    all_params[param_name] = param_value
        
        if current_params:
            all_params.update(current_params)
        
        final_query = urllib.parse.urlencode(all_params, doseq=True)
        return urllib.parse.urljoin(self.base_url, f"{parsed_base.path}?{final_query}") if final_query else urllib.parse.urljoin(self.base_url, parsed_base.path)

    def process_content(self, url):
        parsed_path = urllib.parse.urlparse(url).path.rstrip('/')

        if parsed_path == '/pornstars':
            current_params = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
            final_url = self.get_pornstar_list_url(current_params)
            content = self.make_request(final_url)
            if content:
                self.add_basic_dirs(final_url)
                self.process_filtered_pornstars(content, final_url)
            self.end_directory()
            return
        
        if parsed_path.startswith('/pornstars/'):
            self.process_a_pornstars_videos(url)
            return

        sorted_url = self.apply_video_sort(url)
        content = self.make_request(sorted_url)
        if content:
            self.add_basic_dirs(sorted_url)
            self.process_content_matches(content, sorted_url)
        
        self.end_directory()

    def add_basic_dirs(self, current_url):
        video_sort_context = [('Sort by...', f'RunPlugin({sys.argv[0]}?mode=7&website={self.name}&action=select_sort&original_url={urllib.parse.quote_plus(current_url)})')]
        
        pornstar_context = [('Sort by...', f'RunPlugin({sys.argv[0]}?mode=7&website={self.name}&action=select_pornstar_sort)')]
        for filter_type, (label, _, _, _) in self.pornstar_filter_map.items():
            pornstar_context.append(
                (f'Filter by {label}...', f'RunPlugin({sys.argv[0]}?mode=7&website={self.name}&action=select_pornstar_filter&filter_type={filter_type})')
            )
        pornstar_context.append(('[COLOR yellow]Reset Filters[/COLOR]', f'RunPlugin({sys.argv[0]}?mode=7&website={self.name}&action=reset_pornstar_filters)'))

        dirs = [
            {'name': '[COLOR blue]Search[/COLOR]', 'url': '', 'mode': 5, 'icon': self.icons['search'], 'context': video_sort_context},
            {'name': 'Categories', 'url': f"{self.config['base_url']}/tags/", 'mode': 8, 'icon': self.icons['categories'], 'context': video_sort_context},
            {'name': 'Pornstars', 'url': self.get_pornstar_list_url(), 'mode': 2, 'icon': self.icons['pornstars'], 'context': pornstar_context}
        ]
        for d in dirs:
            self.add_dir(d['name'], d['url'], d['mode'], d['icon'], self.fanart, d['context'], name_param=d.get('name_param', d['name']))

    def process_content_matches(self, content, current_url):
        main_list_pattern = r'<div class="pull-left"\s*>\s*<h1>.*?</h1>\s*</div>.*?<ul class="media-listing-grid main-listing-grid-offset"[^>]*>(.*?)</ul>'
        main_list_match = re.search(main_list_pattern, content, re.DOTALL)
        if not main_list_match:
            fallback_pattern = r'<h1>.*?</h1>.*?<ul class="media-listing-grid[^"]*">(.*?)</ul>'
            main_list_match = re.search(fallback_pattern, content, re.DOTALL)
        if not main_list_match:
            self.logger.error("Could not find the main video list on the page.")
            return

        self.parse_video_list(main_list_match.group(1), current_url)
        self.add_next_button(content, current_url)

    def process_a_pornstars_videos(self, url):
        sorted_url = self.apply_video_sort(url)
        content = self.make_request(sorted_url)
        if not content:
            self.end_directory()
            return

        self.add_basic_dirs(sorted_url)
        video_container_pattern = r'<div id="ajax-profile-content"[^>]*>\s*<ul class="media-listing-grid.*?">(.*?)</ul>'
        list_match = re.search(video_container_pattern, content, re.DOTALL)
        
        if not list_match:
            self.logger.error(f"Could not find video list container on pornstar page: {sorted_url}")
            self.end_directory()
            return
            
        self.parse_video_list(list_match.group(1), sorted_url)
        self.add_next_button(content, sorted_url)
        self.end_directory()

    def parse_video_list(self, html_content, current_url):
        item_pattern = r'(<li class="js-pop media-item.*?</li>)'
        video_pattern = r'<a\s+href="(/videos/[^"]+)"[^>]*>\s*<img[^>]+src="([^"]+)"\s+alt="([^"]+)"'
        duration_pattern = r'<span\s+class="media-item__info-item\s+media-item__info-item-length">\s*([\d:]+)\s*</span>'
        item_blocks = re.findall(item_pattern, html_content, re.DOTALL)
        context_menu = [('Sort by...', f'RunPlugin({sys.argv[0]}?mode=7&action=select_sort&website={self.name}&original_url={urllib.parse.quote_plus(current_url)})')]
        base_url = f"{urllib.parse.urlparse(current_url).scheme}://{urllib.parse.urlparse(current_url).netloc}"
        
        for block in item_blocks:
            video_match = re.search(video_pattern, block, re.DOTALL)
            duration_match = re.search(duration_pattern, block, re.DOTALL)
            if video_match:
                video_url, thumb, name = video_match.groups()
                duration = duration_match.group(1).strip() if duration_match else ""
                display_name = f"{html.unescape(name)} [COLOR yellow]({duration})[/COLOR]" if duration else html.unescape(name)
                self.add_link(display_name, urllib.parse.urljoin(base_url, video_url), 4, urllib.parse.urljoin(base_url, thumb), self.fanart, context_menu)

    def process_categories(self, url):
        json_url = f"{self.config['base_url']}/tags/?response_format=json"
        content = self.make_request(json_url)
        base_url = f"{urllib.parse.urlparse(url).scheme}://{urllib.parse.urlparse(url).netloc}"
        if content:
            try:
                data = json.loads(content)
                if isinstance(data, dict) and data.get('status') is True and 'data' in data:
                    for category in data['data']:
                        name, cat_url, videos, thumb = category.get('name'), category.get('link'), category.get('videos', '0'), category.get('image') or self.icons['categories']
                        if name and cat_url:
                            self.add_dir(f"{name} ({videos} Videos)", urllib.parse.urljoin(base_url, cat_url), 2, thumb, self.fanart)
                    self.end_directory()
                    return
            except json.JSONDecodeError as e:
                self.logger.error(f"Error parsing category JSON: {e}")
        self.notify_error("Failed to load categories.")
        self.end_directory()

    def process_filtered_pornstars(self, content, url):
        context_menu = [('Sort by...', f'RunPlugin({sys.argv[0]}?mode=7&website={self.name}&action=select_pornstar_sort)')]
        for filter_type, (label, _, _, _) in self.pornstar_filter_map.items():
            context_menu.append(
                (f'Filter by {label}...', f'RunPlugin({sys.argv[0]}?mode=7&website={self.name}&action=select_pornstar_filter&filter_type={filter_type})')
            )
        context_menu.append(('[COLOR yellow]Reset Filters[/COLOR]', f'RunPlugin({sys.argv[0]}?mode=7&website={self.name}&action=reset_pornstar_filters)'))

        base_url = f"{urllib.parse.urlparse(url).scheme}://{urllib.parse.urlparse(url).netloc}"
        pattern = r'<div class="media-item model-item.*?<a class="media-item__inner" href="([^"]+)" title="([^"]+)".*?<img[^>]+src="([^"]+)".*?</div>'
        matches = re.findall(pattern, content, re.DOTALL)
        if not matches: self.logger.error(f"No pornstars found on page {url}")
        for pornstar_url, name, thumb in matches:
            self.add_dir(html.unescape(name), urllib.parse.urljoin(base_url, pornstar_url), 2, urllib.parse.urljoin(base_url, thumb), self.fanart, context_menu=context_menu)
        self.add_next_button(content, url)

    def add_next_button(self, content, current_url):
        next_url_path = None
        link_match = re.search(r'<link\s+rel="next"\s+href="([^"]+)"', content)
        if link_match:
            next_url_path = html.unescape(link_match.group(1))
        else:
            pagination_match = re.search(r'<a\s+class="[^"]*rightKey[^"]*"\s+href="([^"]+)"[^>]*>Next</a>', content)
            if pagination_match:
                next_url_path = html.unescape(pagination_match.group(1))

        if next_url_path:
            parsed_current = urllib.parse.urlparse(current_url)
            current_params = urllib.parse.parse_qs(parsed_current.query)
            
            parsed_next_href = urllib.parse.urlparse(next_url_path)
            next_href_params = urllib.parse.parse_qs(parsed_next_href.query)

            current_params.update(next_href_params)
            
            final_query_string = urllib.parse.urlencode(current_params, doseq=True)
            final_path = parsed_next_href.path if parsed_next_href.path else parsed_current.path

            final_url = urllib.parse.urlunparse((parsed_current.scheme, parsed_current.netloc, final_path, '', final_query_string, ''))
            self.add_dir('[COLOR blue]Next Page >>>>[/COLOR]', final_url, 2, self.icons['default'], self.fanart)

    def play_video(self, url):
        content = self.make_request(url)
        if not content: return self.notify_error("Failed to load video page")
        match = re.search(r'["\']video_url["\']\s*:\s*["\'](.*?)["\']', content) or re.search(r'<source\s+src="([^"]+)"\s+type=["\']video/mp4["\']', content)
        if not match: return self.notify_error("No video source found")
        media_url = match.group(1).replace('\\/', '/')
        if not media_url.startswith('http'): media_url = urllib.parse.urljoin(url, media_url)
        li = xbmcgui.ListItem(path=media_url)
        li.setProperty('IsPlayable', 'true')
        li.setMimeType('video/mp4')
        xbmcplugin.setResolvedUrl(self.addon_handle, True, li)

    def select_sort(self, original_url=None):
        if not original_url: return self.notify_error("Cannot sort: page context is missing.")
        try:
            current_setting_idx = int(self.addon.getSetting('ashemaletube_sort_by') or '0')
        except:
            current_setting_idx = 0
        
        dialog = xbmcgui.Dialog()
        idx = dialog.select("Sort by...", self.sort_options, preselect=current_setting_idx)
        if idx == -1: return

        self.addon.setSetting('ashemaletube_sort_by', str(idx))
        new_url = self.apply_video_sort(original_url)
        
        xbmc.executebuiltin(f"Container.Update({sys.argv[0]}?mode=2&url={urllib.parse.quote_plus(new_url)}&website={self.name},replace)")
    
    def select_pornstar_sort(self, original_url=None):
        try:
            current_setting_idx = int(self.addon.getSetting('ashemaletube_pornstar_sort_by') or '0')
        except:
            current_setting_idx = 0
        
        dialog = xbmcgui.Dialog()
        idx = dialog.select("Sort by...", self.pornstar_sort_options, preselect=current_setting_idx)
        if idx == -1: return

        self.addon.setSetting('ashemaletube_pornstar_sort_by', str(idx))
        new_url = self.get_pornstar_list_url()
        
        xbmc.executebuiltin(f"Container.Update({sys.argv[0]}?mode=2&url={urllib.parse.quote_plus(new_url)}&website={self.name},replace)")
    
    def select_pornstar_filter(self, filter_type, original_url=None):
        if filter_type not in self.pornstar_filter_map: return
        
        label, _, options_list, _ = self.pornstar_filter_map[filter_type]
        setting_id = f'ashemaletube_pf_{filter_type}'
        
        try:
            current_idx = int(self.addon.getSetting(setting_id) or '0')
        except:
            current_idx = 0
        
        dialog = xbmcgui.Dialog()
        idx = dialog.select(f"Filter by {label}", options_list, preselect=current_idx)
        if idx == -1: return

        self.addon.setSetting(setting_id, str(idx))
        new_url = self.get_pornstar_list_url()
        xbmc.executebuiltin(f"Container.Update({sys.argv[0]}?mode=2&url={urllib.parse.quote_plus(new_url)}&website={self.name},replace)")

    def reset_pornstar_filters(self):
        self.addon.setSetting('ashemaletube_pornstar_sort_by', "0")
        for filter_type in self.pornstar_filter_map:
            setting_id = f'ashemaletube_pf_{filter_type}'
            self.addon.setSetting(setting_id, "0")
        
        self.notify_info("Pornstar filters have been reset.")
        new_url = self.get_pornstar_list_url()
        xbmc.executebuiltin(f"Container.Update({sys.argv[0]}?mode=2&url={urllib.parse.quote_plus(new_url)}&website={self.name},replace)")