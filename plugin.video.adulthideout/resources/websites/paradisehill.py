#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
import sys
import urllib.parse
import urllib.request
import html
import http.cookiejar
import xbmcgui
import xbmcplugin
import xbmc
from resources.lib.base_website import BaseWebsite

class ParadisehillWebsite(BaseWebsite):
    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="paradisehill",
            base_url="https://en.paradisehill.cc",
            search_url="https://en.paradisehill.cc/search/?pattern={}",
            addon_handle=addon_handle,
            addon=addon
        )
        
        cookie_jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookie_jar))
        self.opener.addheaders = [
            ('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36'),
            ('Accept', 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8'),
            ('Accept-Language', 'de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7'),
            ('Upgrade-Insecure-Requests', '1'),
            ('Referer', self.base_url) 
        ]

    def get_start_url_and_label(self):
        return "https://en.paradisehill.cc/all/?sort=created_at", f"{self.name.capitalize()}"

    def make_request(self, url):
        try:
            with self.opener.open(self.base_url, timeout=15) as initial_response:
                pass 
            
            with self.opener.open(url, timeout=15) as response:
                return response.read().decode('utf-8')
        except Exception as e:
            xbmc.log(f"PARADISEHILL ERROR: Request failed for {url} - {e}", level=xbmc.LOGERROR)
            self.notify_error(f"Failed to load page: {e}")
            return None

    def process_content(self, url):
        self.add_basic_dirs(url)
        content = self.make_request(url)
        if content:
            self.parse_video_list(content, url)
            self.add_next_button(content, url)
        self.end_directory()

    def add_basic_dirs(self, current_url):
        self.add_dir('[COLOR blue]Search[/COLOR]', '', 5, self.icons['search'])
        self.add_dir('Categories', f'{self.base_url}/categories/', 8, self.icons['categories'])

    def parse_video_list(self, content, current_url):
        pattern = r'<div class="item list-film-item".*?<a href="([^"]+)".*?<img.*?src="([^"]+)".*?alt="([^"]+)".*?<span itemprop="name">([^<]+)</span>'
        matches = re.findall(pattern, content, re.DOTALL)

        if not matches:
            self.notify_info("No videos found.")
            return

        for video_url, thumbnail, alt_title, title in matches:
            full_url = urllib.parse.urljoin(self.base_url, video_url)
            full_thumb_url = urllib.parse.urljoin(self.base_url, thumbnail)
            display_name = html.unescape(title.strip()) if title.strip() else html.unescape(alt_title.strip())
            
            self.add_link(display_name, full_url, 4, full_thumb_url, self.fanart)

    def add_next_button(self, content, current_url):
        match = re.search(r'<li class="next"><a href="([^"]+)"', content)
        if match:
            next_url_path = html.unescape(match.group(1))
            next_url = urllib.parse.urljoin(self.base_url, next_url_path)
            self.add_dir('[COLOR blue]Next Page >>>>[/COLOR]', next_url, 2, self.icons['default'], self.fanart)

    def play_video(self, url):
        params = dict(urllib.parse.parse_qsl(sys.argv[2][1:]))
        name = params.get('name', 'Video')

        content = self.make_request(url)
        if not content:
            self.notify_error("Failed to load video page")
            return

        match = re.search(r'var videoList = (\[.*?\]);', content)
        
        if match:
            video_list_json = match.group(1)
            mp4_urls = re.findall(r'"src":"(.*?)"', video_list_json)
            
            if mp4_urls:
                playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)

                first_part_url = mp4_urls[0].replace('\\/', '/').strip()
                li = xbmcgui.ListItem(path=first_part_url)
                li.setInfo('video', {'title': f"{name} - Part 1"})
                li.setProperty("IsPlayable", "true")
                li.setMimeType("video/mp4")

                for i, part_url in enumerate(mp4_urls[1:]):
                    cleaned_url = part_url.replace('\\/', '/').strip()
                    part_title = f"{name} - Part {i+2}"
                    
                    li_rest = xbmcgui.ListItem(part_title)
                    li_rest.setInfo('video', {'title': part_title})
                    li_rest.setProperty("IsPlayable", "true")
                    li_rest.setMimeType("video/mp4")
                    
                    playlist.add(url=cleaned_url, listitem=li_rest)

                xbmcplugin.setResolvedUrl(self.addon_handle, True, li)
                return

        self.notify_error("No playable MP4 stream found in videoList.")

    def process_categories(self, url):
        content = self.make_request(url)
        if content:
            pattern = r'<div class="item".*?<a href="([^"]+)".*?src="([^"]+)".*?alt="([^"]+)">'
            matches = re.findall(pattern, content, re.DOTALL)
            for cat_url, thumb, name in matches:
                full_url = urllib.parse.urljoin(self.base_url, cat_url)
                full_thumb_url = urllib.parse.urljoin(self.base_url, thumb)
                self.add_dir(html.unescape(name.strip()), full_url, 2, full_thumb_url, self.fanart)
        self.end_directory()