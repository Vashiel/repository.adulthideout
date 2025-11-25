#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Changelog:
# - Final release version
# - Switched to Webmaster API for reliable video listing
# - Fixed playback using flashvars extraction
# - Optimized sorting and period selection
# - Cleaned up code

import re
import sys
import json
import html
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar

import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin

from resources.lib.base_website import BaseWebsite

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
        from http.cookiejar import Cookie
        age_cookie = Cookie(
            version=0, name='age_verified', value='1', port=None, port_specified=False,
            domain='.pornhub.com', domain_specified=True, domain_initial_dot=True,
            path='/', path_specified=True, secure=False, expires=None, discard=True,
            comment=None, comment_url=None, rest={}
        )
        self.cookie_jar.set_cookie(age_cookie)

    def get_headers(self, referer=None):
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7',
        }
        if referer: headers['Referer'] = referer
        return headers

    def make_request(self, url, referer=None, is_api=False):
        try:
            headers = self.get_headers(referer)
            if is_api:
                headers['Accept'] = 'application/json, text/plain, */*'
                headers['X-Requested-With'] = 'XMLHttpRequest'
            
            req = urllib.request.Request(url, headers=headers)
            with self.opener.open(req, timeout=15) as resp:
                return resp.read().decode('utf-8', errors='ignore')
        except Exception as e:
            if hasattr(self, 'notify_error'): self.notify_error("Failed to load data.")
            return None
    
    def process_content(self, url):
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
                label = f"{title} [COLOR lime]({duration})[/COLOR]"
                self.add_link(label, f"{self.base_url}/view_video.php?viewkey={vid_id}", 4, thumb, self.fanart, context_menu)

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
        content = self.make_request(url, referer=url)
        if not content: return

        match = re.search(r'var\s+flashvars_\d+\s*=\s*({.*?});', content, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(1))
                streams = [s for s in data.get('mediaDefinitions', []) if s.get('format') == 'hls' and s.get('videoUrl')]
                if streams:
                    best_stream = max(streams, key=lambda x: int(x.get('quality', '0')))
                    stream_url = html.unescape(best_stream['videoUrl']).replace('\\/', '/')
                    li = xbmcgui.ListItem(path=stream_url)
                    li.setProperty('IsPlayable', 'true')
                    li.setProperty('inputstream', 'inputstream.adaptive')
                    li.setProperty('inputstream.adaptive.manifest_type', 'hls')
                    li.setMimeType('application/vnd.apple.mpegurl')
                    xbmcplugin.setResolvedUrl(self.addon_handle, True, li)
                    return
            except Exception:
                pass
        
        if hasattr(self, 'notify_error'): self.notify_error("No playable stream found.")

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