#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
import sys
import urllib.parse
import urllib.request
import html
import io
import gzip
import xbmc
import xbmcgui
import xbmcplugin
from http.cookiejar import CookieJar
from resources.lib.base_website import BaseWebsite

class Rule34video(BaseWebsite):
    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name='rule34video',
            base_url='https://rule34video.com',
            search_url='https://rule34video.com/search/{}',
            addon_handle=addon_handle,
            addon=addon
        )
        self.display_name = 'Rule34video'
        self.sort_options = ['Newest', 'Most Viewed', 'Top Rated', 'Longest', 'Random']
        self.content_options = ['All', 'Straight', 'Gay', 'Futa']
        self.setting_id_sort = "rule34video_sort_order"
        self.setting_id_content = "rule34video_content_type"
        self.content_params = {
            'All': None, 'Straight': '2109', 'Gay': '192', 'Futa': '15'
        }
        self.cookie_jar = CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cookie_jar))
        self.timeout = 15
        self.make_request(self.base_url)

    def get_headers(self, referer=None):
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Encoding": "gzip, deflate",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": referer or self.base_url,
            "Connection": "keep-alive", 
            "Cache-Control": "no-cache"
        }

    def make_request(self, url, headers=None):
        headers = headers or self.get_headers(url)
        try:
            req = urllib.request.Request(url, headers=headers)
            with self.opener.open(req, timeout=self.timeout) as response:
                final_url = response.geturl()
                if final_url != url and 'boomio-cdn.com' in final_url:
                    return final_url
                if response.info().get('Content-Encoding') == 'gzip':
                    buf = response.read()
                    return gzip.GzipFile(fileobj=io.BytesIO(buf)).read().decode('utf-8', errors='ignore')
                return response.read().decode('utf-8', errors='ignore')
        except Exception as e:
            xbmc.log(f"Request failed for {url}: {str(e)}", xbmc.LOGERROR)
            return None

    def get_current_content_key(self):
        try:
            content_index = int(self.addon.getSetting(self.setting_id_content))
        except (ValueError, TypeError):
            content_index = 0
        return self.content_options[content_index] if 0 <= content_index < len(self.content_options) else self.content_options[0]

    def get_current_sort_key(self):
        try:
            sort_index = int(self.addon.getSetting(self.setting_id_sort))
        except (ValueError, TypeError):
            sort_index = 0
        return self.sort_options[sort_index] if 0 <= sort_index < len(self.sort_options) else self.sort_options[0]

    def _get_start_url(self):
        sort_key = self.get_current_sort_key()
        content_key = self.get_current_content_key()
        content_param_value = self.content_params.get(content_key)
        path_map = {
            'Newest': '/latest-updates/', 'Most Viewed': '/most-popular/', 'Top Rated': '/top-rated/',
            'Longest': '/search/?sort_by=duration', 'Random': '/search/?sort_by=pseudo_rand'
        }
        url = urllib.parse.urljoin(self.base_url, path_map.get(sort_key, '/latest-updates/'))
        if content_param_value:
            url += '&flag1=' if '?' in url else '?'
            url += f"flag1={content_param_value}"
        return url

    def get_start_url_and_label(self):
        label_suffix = f"{self.get_current_content_key()} - {self.get_current_sort_key()}"
        return self._get_start_url(), f"{self.display_name} [COLOR yellow]({label_suffix})[/COLOR]"

    def select_content_type(self, original_url=None):
        try:
            current_setting_idx = int(self.addon.getSetting(self.setting_id_content))
            if not (0 <= current_setting_idx < len(self.content_options)):
                current_setting_idx = 0
        except (ValueError, TypeError):
            current_setting_idx = 0
        dialog = xbmcgui.Dialog()
        idx = dialog.select("Select Content...", self.content_options, preselect=current_setting_idx)
        if idx == -1:
            return
        self.addon.setSetting(self.setting_id_content, str(idx))
        new_url, _ = self.get_start_url_and_label()
        xbmc.executebuiltin(f"Container.Update({sys.argv[0]}?mode=2&url={urllib.parse.quote_plus(new_url)}&website={self.name},replace)")

    def select_sort_order(self, original_url=None):
        try:
            current_setting_idx = int(self.addon.getSetting(self.setting_id_sort))
            if not (0 <= current_setting_idx < len(self.sort_options)):
                current_setting_idx = 0
        except (ValueError, TypeError):
            current_setting_idx = 0
        dialog = xbmcgui.Dialog()
        idx = dialog.select("Sort by...", self.sort_options, preselect=current_setting_idx)
        if idx == -1:
            return
        self.addon.setSetting(self.setting_id_sort, str(idx))
        new_url, _ = self.get_start_url_and_label()
        xbmc.executebuiltin(f"Container.Update({sys.argv[0]}?mode=2&url={urllib.parse.quote_plus(new_url)}&website={self.name},replace)")

    def process_content(self, url):
        if not url:
            url = self._get_start_url()
        self.add_dir('[COLOR blue]Search[/COLOR]', '', 5)
        html_content = self.make_request(url)
        if not html_content:
            return self.end_directory()
        video_pattern = re.compile(
            r'<div class="item\s+thumb\s+video_\d+.*?<a\s+class="th\s+js-open-popup"\s+href="(?P<url>[^"]+)"\s+title="(?P<title>[^"]+)".*?'
            r'<img.*?data-original="(?P<thumb>[^"]+)".*?'
            r'<div\s+class="time">(?P<duration>[^<]+)</div>',
            re.DOTALL | re.IGNORECASE
        )
        for data in video_pattern.finditer(html_content):
            page_url = urllib.parse.urljoin(self.base_url, data.group('url'))
            title_with_duration = f"{html.unescape(data.group('title'))} [COLOR yellow]({data.group('duration').strip()})[/COLOR]"
            context_menu = [
                ('Select Content...', f'RunPlugin({sys.argv[0]}?mode=7&action=select_content_type&website={self.name})'),
                ('Sort by...', f'RunPlugin({sys.argv[0]}?mode=7&action=select_sort_order&website={self.name})')
            ]
            self.add_link(title_with_duration, page_url, 4, data.group('thumb'), self.fanart, context_menu=context_menu)
        next_page_match = re.search(r'<div class="item pager next">\s*<a href="([^"]+)"', html_content)
        if next_page_match:
            next_url = urllib.parse.urljoin(url, html.unescape(next_page_match.group(1)))
            self.add_dir('[COLOR yellow]Nächste Seite >>[/COLOR]', next_url, 2)
        self.end_directory()

    def play_video(self, url):
        html_content = self.make_request(url)
        if not html_content:
            self.notify_error("Konnte die Videoseite nicht laden.")
            return
        qualities = ['video_alt_url3', 'video_alt_url2', 'video_alt_url', 'video_url']
        intermediate_urls = []
        for quality in qualities:
            match = re.search(rf"{quality}: 'function/0/([^']+)'", html_content)
            if match:
                intermediate_urls.append(match.group(1))
        content_url_match = re.search(r'"contentUrl":\s*"([^"]+)"', html_content)
        if content_url_match:
            cu = content_url_match.group(1).rstrip('/')
            if not intermediate_urls or intermediate_urls[-1] != cu:
                intermediate_urls.append(cu)
        rnd_value = None
        rnd_match = re.search(r"rnd: '(\d+)'", html_content)
        if rnd_match:
            rnd_value = rnd_match.group(1)
        for intermediate_url in intermediate_urls:
            final_intermediate_url = intermediate_url
            if rnd_value:
                if '?' in intermediate_url:
                    final_intermediate_url += f"&rnd={rnd_value}"
                else:
                    final_intermediate_url += f"?rnd={rnd_value}"
            headers = self.get_headers(referer=url)
            final_stream_url = self.make_request(final_intermediate_url, headers=headers)
            if final_stream_url and 'remote_control.php' in final_stream_url:
                cookies = []
                for cookie in self.cookie_jar:
                    if 'rule34video.com' in cookie.domain or 'boomio-cdn.com' in cookie.domain:
                        cookies.append(f"{cookie.name}={cookie.value}")
                cookie_str = '; '.join(cookies)
                headers_dict = {
                    'User-Agent': headers['User-Agent'],
                    'Referer': url,
                    'Accept': '*/*',
                    'Connection': 'keep-alive'
                }
                if cookie_str:
                    headers_dict['Cookie'] = cookie_str
                headers = urllib.parse.urlencode(headers_dict)
                li = xbmcgui.ListItem(path=f"{final_stream_url}|{headers}")
                li.setProperty('IsPlayable', 'true')
                li.setMimeType('video/mp4')
                li.setProperty('inputstream.adaptive.stream_headers', headers)
                li.setProperty('inputstream.adaptive.manifest_type', 'mpd')
                xbmcplugin.setResolvedUrl(self.addon_handle, True, li)
                return
        self.notify_error("Konnte keinen abspielbaren Stream im Quellcode finden.")