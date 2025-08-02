#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
import json
import urllib.parse as urllib_parse
import urllib.request as urllib_request
from http.cookiejar import CookieJar
import xbmc
import xbmcgui
import xbmcplugin
import xbmcvfs
import sys
from resources.lib.base_website import BaseWebsite
from resources.lib.decoders.porntn_decoder import kvs_decode

class PorntnWebsite(BaseWebsite):
    config = {
        "name": "porntn",
        "base_url": "https://porntn.com",
        "search_url": "https://porntn.com/search/{}"
    }

    def __init__(self, addon_handle):
        super().__init__(
            name=self.config["name"],
            base_url=self.config["base_url"].rstrip('/'),
            search_url=self.config["search_url"],
            addon_handle=addon_handle
        )
        self.sort_options = ["Latest", "Most Viewed", "Top Rated", "Longest", "Most Commented", "Most Favorited"]
        self.sort_map = {
            "Latest": "post_date",
            "Most Viewed": "video_viewed",
            "Top Rated": "rating",
            "Longest": "duration",
            "Most Commented": "most_commented",
            "Most Favorited": "most_favourited"
        }
        self.cookie_jar = CookieJar()
        self.sort_index_file = xbmcvfs.translatePath('special://profile/addon_data/plugin.video.adulthideout/porntn_sort.json')
        self.current_sort_index = self.load_sort_index()

    def get_start_url_and_label(self):
        label = f"{self.name.capitalize()}"
        sort_option = self.sort_options[self.current_sort_index]
        final_label = f"{label} [COLOR yellow]{sort_option}[/COLOR]"
        url = self.apply_video_sort(self.base_url, sort_index=self.current_sort_index)
        return url, final_label

    def load_sort_index(self):
        try:
            with xbmcvfs.File(self.sort_index_file, 'r') as f:
                data = json.load(f)
                index = int(data.get('sort_index', 0))
                if 0 <= index < len(self.sort_options):
                    self.addon.setSetting("porntn_sort_by", str(index))
                    return index
        except (FileNotFoundError, json.JSONDecodeError, ValueError):
            self.addon.setSetting("porntn_sort_by", "0")
            return 0
        return 0

    def save_sort_index(self, index):
        try:
            with xbmcvfs.File(self.sort_index_file, 'w') as f:
                json.dump({'sort_index': index}, f)
            self.addon.setSetting("porntn_sort_by", str(index))
        except Exception as e:
            pass

    def get_headers(self, referer=None):
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'de-DE,de;q=0.9',
            'Accept-Encoding': 'identity',
            'Referer': referer or self.base_url,
            'Connection': 'keep-alive'
        }
        return headers

    def make_request(self, url, headers=None, data=None, max_retries=3, retry_wait=5000):
        headers = headers or self.get_headers(url)
        handler = urllib_request.HTTPCookieProcessor(self.cookie_jar)
        opener = urllib_request.build_opener(handler)
        if data:
            data = urllib_parse.urlencode(data).encode('utf-8')
        for attempt in range(max_retries):
            try:
                request = urllib_request.Request(url, data=data, headers=headers)
                with opener.open(request, timeout=60) as response:
                    content = response.read().decode('utf-8', errors='ignore')
                    return content
            except urllib_request.HTTPError as e:
                if e.code == 404:
                    return None
                if attempt < max_retries - 1:
                    xbmc.sleep(retry_wait)
            except urllib_request.URLError:
                if attempt < max_retries - 1:
                    xbmc.sleep(retry_wait)
        self.notify_error(f"Failed to fetch URL: {url}")
        return None

    def check_url(self, url):
        try:
            request = urllib_request.Request(url, method='HEAD', headers=self.get_headers(url))
            with urllib_request.urlopen(request, timeout=5) as response:
                return response.getcode() == 200
        except (urllib_request.HTTPError, urllib_request.URLError):
            return False

    def apply_video_sort(self, url, sort_index=None):
        if sort_index is None:
            sort_index = self.current_sort_index
        self.current_sort_index = sort_index
        sort_display = self.sort_options[sort_index]
        sort_param = self.sort_map.get(sort_display, "post_date")
        parsed_url = urllib_parse.urlparse(url)
        query_params = urllib_parse.parse_qs(parsed_url.query)
        query_params.pop("sort_by", None)
        query_params["sort_by"] = sort_param
        base_path = parsed_url.path.strip('/')
        if parsed_url.path.startswith('/search/') or parsed_url.path.startswith('/video/'):
            search_term = parsed_url.path.split('/')[-1].strip('/')
            base_url = f"{self.base_url}/video/{urllib_parse.quote(search_term)}"
            query_params['q'] = search_term
            query_params['from_videos'] = query_params.get('from_videos', ['1'])[0]
            query_params.pop('from', None)
        elif parsed_url.path.startswith('/new/') and base_path != 'new':
            base_url = f"{self.base_url}/{base_path}"
            query_params['from'] = query_params.get('from', ['1'])[0]
            query_params.pop('from_videos', None)
        else:
            base_url = f"{self.base_url}/new/all-new-hd-porn-videos"
            query_params['from'] = query_params.get('from', ['1'])[0]
            query_params.pop('from_videos', None)
        final_query = urllib_parse.urlencode(query_params, doseq=True)
        final_url = f"{base_url}?{final_query}"
        final_url = final_url.replace('//', '/').replace('https:/', 'https://')
        return final_url

    def process_content(self, url):
        sorted_url = self.apply_video_sort(url, sort_index=self.current_sort_index)
        content = self.make_request(sorted_url)
        if not content:
            self.notify_error("No more pages available")
            return
        parsed_url = urllib_parse.urlparse(url)
        base_path = parsed_url.path.strip('/')
        if 'filter_options' in base_path:
            self.addon.openSettings()
            new_url = f"{self.base_url}/new/all-new-hd-porn-videos"
            xbmc.executebuiltin(f"Container.Update({sys.argv[0]}?mode=2&url={urllib_parse.quote_plus(new_url)},replace)")
            return
        if base_path == 'new':
            self.process_categories(url)
            return
        self.add_basic_dirs(url)
        sort_display = self.sort_options[self.current_sort_index]
        context_menu = [(f'Sort by ({sort_display})...', f'RunPlugin({sys.argv[0]}?mode=7&action=select_sort&website={self.name}&original_url={urllib_parse.quote_plus(url)})')]
        video_pattern = r'<div class="item[^"]*">\s*<a href="([^"]+)"\s*title="([^"]+)"[^>]*>.*?<img[^>]+data-original="([^"]+)".*?<div class="duration">([^<]+)</div>'
        alt_video_pattern = r'<div class="item[^"]*">\s*<a href="([^"]+)"\s*title="([^"]+)"[^>]*>.*?<img[^>]+src="([^"]+)".*?<div class="duration">([^<]+)</div>'
        matches = re.findall(video_pattern, content, re.DOTALL)
        if not matches:
            matches = re.findall(alt_video_pattern, content, re.DOTALL)
        for video_url, title, thumbnail, duration in matches:
            if not thumbnail.startswith("http"):
                thumbnail = "https:" + thumbnail
            display_title = f'{title} [{duration.strip()}]'
            self.add_link(display_title, video_url, 4, thumbnail, '', context_menu=context_menu)
        query_params = urllib_parse.parse_qs(parsed_url.query)
        if parsed_url.path.startswith('/search/') or parsed_url.path.startswith('/video/'):
            current_page = int(query_params.get('from_videos', ['1'])[0])
            next_page_num = current_page + 1
            search_term = parsed_url.path.split('/')[-1].strip('/')
            sort_param = self.sort_map.get(self.sort_options[self.current_sort_index], "post_date")
            ajax_params = {'q': search_term, 'sort_by': sort_param, 'from_videos': str(next_page_num)}
            next_page_url = f"{self.base_url}/video/{urllib_parse.quote(search_term)}?{urllib_parse.urlencode(ajax_params, doseq=True)}"
            next_page_url = next_page_url.replace('//', '/').replace('https:/', 'https://')
            if matches:
                self.add_dir(f"[COLOR blue]Next Page ({next_page_num}) >>>>[/COLOR]", next_page_url, 2, self.icons['default'], '', context_menu=context_menu)
        else:
            current_page = int(query_params.get('from', ['1'])[0])
            next_page_num = current_page + 1
            query_params['from'] = str(next_page_num)
            query_params.pop('from_videos', None)
            final_query = urllib_parse.urlencode(query_params, doseq=True)
            base_url = f"{self.base_url}/{base_path}" if base_path else f"{self.base_url}/new/all-new-hd-porn-videos"
            next_page_url = f"{base_url}?{final_query}"
            next_page_url = next_page_url.replace('//', '/').replace('https:/', 'https://')
            if matches:
                self.add_dir(f"[COLOR blue]Next Page ({next_page_num}) >>>>[/COLOR]", next_page_url, 2, self.icons['default'], '', context_menu=context_menu)
        self.end_directory()

    def add_basic_dirs(self, current_url):
        sort_display = self.sort_options[self.current_sort_index]
        context_menu = [(f'Sort by ({sort_display})...', f'RunPlugin({sys.argv[0]}?mode=7&action=select_sort&website={self.name}&original_url={urllib_parse.quote_plus(current_url)})')]
        dirs = [
            (f'[COLOR blue]Search[/COLOR]', '', 5, self.icons['search'], None, self.config['name']),
            ('Categories', f'{self.base_url}/new', 2, self.icons['categories'], context_menu, 'Categories')
        ]
        for name, url, mode, icon, ctx, *extra in dirs:
            self.add_dir(name, url, mode, icon, self.fanart, ctx, name_param=extra[0] if extra else name)

    def process_categories(self, url):
        content = self.make_request(f"{self.base_url}/new/", headers=self.get_headers(url))
        if not content:
            self.notify_error("Failed to load categories")
            return
        category_pattern = r'<a class="item" href="(https://porntn\.com/new/[^"]+)"\s*title="([^"]+)".*?<img[^>]+src="([^"]+)"[^>]*>.*?<div class="videos">([^<]+)</div>'
        matches = re.findall(category_pattern, content, re.DOTALL)
        for cat_url, name, thumbnail, count in matches:
            if not thumbnail.startswith("http"):
                thumbnail = "https:" + thumbnail
            if not self.check_url(thumbnail):
                thumbnail = self.icons['categories']
            display_title = f"{name.strip()} ({count.strip()})"
            sorted_cat_url = self.apply_video_sort(cat_url, sort_index=self.current_sort_index)
            self.add_dir(display_title, sorted_cat_url, 2, thumbnail, '')
        self.end_directory()

    def select_sort(self, original_url=None):
        if not original_url:
            self.notify_error("Cannot sort: page context is missing.")
            return
        current_setting_idx = self.current_sort_index
        dialog = xbmcgui.Dialog()
        idx = dialog.select(f"PornTN {self.sort_options[current_setting_idx]}", self.sort_options, preselect=current_setting_idx)
        if idx == -1: return
        self.current_sort_index = idx
        self.save_sort_index(idx)
        new_url = self.apply_video_sort(original_url, sort_index=idx)
        xbmc.executebuiltin(f"Container.Update({sys.argv[0]}?mode=2&url={urllib_parse.quote_plus(new_url)}&website={self.name},replace)")

    def play_video(self, url):
        content = self.make_request(url, headers=self.get_headers(url))
        if not content:
            self.notify_error("Server not responding")
            return

        page_content_to_parse = content
        current_domain = self.base_url
        referer = url

        redirect_match = re.search(r'<a class="btn-play" href="(https?://porndd\.com/video/[^"]+)"', content)
        if redirect_match:
            redirect_url = redirect_match.group(1)
            page_content_to_parse = self.make_request(redirect_url, headers=self.get_headers(referer=url))
            current_domain = "https://porndd.com"
            referer = redirect_url
            if not page_content_to_parse:
                self.notify_error("Failed to load redirected page.")
                return

        license_match = re.search(r"license_code[\"']?\s*:\s*[\"']([a-zA-Z0-9$]+)[\"']", page_content_to_parse)
        encoded_urls = re.findall(r"[\"'](function/[^\"']+)[\"']", page_content_to_parse)
        if license_match and encoded_urls:
            license_code = license_match.group(1)
            for encoded_url in reversed(encoded_urls):
                decoded_stream_url = kvs_decode(encoded_url, license_code)
                if decoded_stream_url:
                    if not decoded_stream_url.startswith("http"):
                        decoded_stream_url = urllib_parse.urljoin(current_domain, decoded_stream_url)
                    if self.check_url(decoded_stream_url):
                        li = xbmcgui.ListItem(path=decoded_stream_url)
                        li.setMimeType('video/mp4')
                        li.setProperty('Referer', referer)
                        xbmcplugin.setResolvedUrl(self.addon_handle, True, li)
                        return

        stream_match = re.search(r"[\"'](https?://[^\"']+\.mp4[^\"']*)[\"']", page_content_to_parse)
        if stream_match:
            stream_url = stream_match.group(1).replace('&amp;', '&')
            if self.check_url(stream_url):
                 li = xbmcgui.ListItem(path=stream_url)
                 li.setMimeType('video/mp4')
                 li.setProperty('Referer', referer)
                 xbmcplugin.setResolvedUrl(self.addon_handle, True, li)
                 return

        self.notify_error("Could not find a playable video stream with any known method.")