#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
import sys
import urllib.parse
import urllib.request
import html
import xbmc
import xbmcgui
import xbmcplugin
from resources.lib.base_website import BaseWebsite

class MotherlessWebsite(BaseWebsite):
    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="motherless",
            base_url="https://motherless.com",
            search_url="https://motherless.com/term/videos/{}",
            addon_handle=addon_handle,
            addon=addon
        )
        self.sort_options = ["Newest", "Being Watched Now", "Favorites", "Most Viewed", "Most Commented", "Popular", "Archived", "Random Video"]
        self.sort_paths = {
            "Newest": "/videos/recent", "Being Watched Now": "/live/videos",
            "Favorites": "/videos/favorited", "Most Viewed": "/videos/viewed",
            "Most Commented": "/videos/commented", "Popular": "/videos/popular",
            "Archived": "/videos/archives", "Random Video": "/random/video"
        }
        self.setting_id_sort = "motherless_sort_order"

    def _make_request(self, url):
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36'}
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=20) as response:
                final_url = response.geturl()
                if self.sort_paths["Random Video"] in url and "motherless.com" in final_url:
                    self.play_video(final_url)
                    return None
                return response.read().decode('utf-8', errors='ignore')
        except Exception as e:
            self.notify_error(f"Failed to load page: {e}")
        return ""

    def get_current_sort_key(self):
        try:
            sort_index = int(self.addon.getSetting(self.setting_id_sort))
        except (ValueError, TypeError):
            sort_index = 0
        if not 0 <= sort_index < len(self.sort_options):
            sort_index = 0
        return self.sort_options[sort_index]

    def process_content(self, url):
        if not url:
            sort_key = self.get_current_sort_key()
            url = urllib.parse.urljoin(self.base_url, self.sort_paths.get(sort_key, "/videos/recent"))

        self.add_basic_dirs(url)
        content = self._make_request(url)
        if not content:
            self.end_directory(); return

        path = urllib.parse.urlparse(url).path

        if path.startswith('/groups'):
            self.process_groups(content, url)
        elif path.startswith('/galleries'):
            self.process_galleries(content, url)
        elif path.startswith(('/shouts', '/orientation/')):
            self.process_categories(content, url)
        else:
            self.process_video_list(content, url)
            
        self.end_directory()

    def add_basic_dirs(self, current_url):
        self.add_dir('[COLOR blue]Search[/COLOR]', '', 5, self.icons['search'])
        self.add_dir('Categories', f'{self.base_url}/orientation/straight', 2, self.icons['categories'])
        self.add_dir('Groups', f'{self.base_url}/groups', 2, self.icons['groups'])
        self.add_dir('Galleries', f'{self.base_url}/galleries/updated', 2, self.icons['galleries'])

    def process_video_list(self, content, current_url):
        pattern = re.compile(r'<a href="([^\"]+)" class="img-container"[^>]*>.+?<span class="size">([:\d]+)</span>.+?<img class="static" src="([^\"]+)"[^>]*alt="([^\"]+)"', re.DOTALL)
        matches = re.findall(pattern, content)
        if not matches:
            self.notify_info("No videos found on this page.")
            return

        context_menu = [('Sort by...', f'RunPlugin({sys.argv[0]}?mode=7&action=select_sort&website={self.name})')]
        for href, duration, thumb, name in matches:
            self.add_link(f"{html.unescape(name)} [COLOR yellow]({duration})[/COLOR]", urllib.parse.urljoin(self.base_url, href), 4, thumb, self.fanart, context_menu)
        self.add_next_button(content, current_url)

    def process_groups(self, content, current_url):
        pattern = re.compile(r'<h1 class="group-bio-name">.+?<a href="/g/([^\"]*)">\s*(.+?)\s*</a>.+?src="https://([^\"]*)"', re.DOTALL)
        matches = re.findall(pattern, content)
        if not matches:
            self.notify_info("No groups found.")
            return
        
        for part, name, thumb_host in matches:
            video_list_url = f"{self.base_url}/g/{part}/videos"
            thumb_url = f"https://{thumb_host}"
            self.add_dir(html.unescape(name.strip()), video_list_url, 2, thumb_url, self.fanart)
        self.add_next_button(content, current_url)

    def process_galleries(self, content, current_url):
        pattern = r'<img class="static" src="(https://[^\"]*)".*?<a href="/G([^\"]*)"[^>]*title="([^\"]*)".*?<span>\s*(\d+)\s*Videos'
        matches = re.findall(pattern, content, re.DOTALL)
        if not matches:
            self.notify_info("No video galleries found.")
            return

        for thumb, gid, name, count in matches:
            if int(count) > 0:
                self.add_dir(f"{html.unescape(name)} ({count} Videos)", f"{self.base_url}/GV{gid}", 2, thumb, self.fanart)
        self.add_next_button(content, current_url)

    def process_categories(self, content, current_url):
        orientations = {'Straight': 'straight', 'Gay': 'gay', 'Transsexual': 'transsexual', 'Extreme': 'extreme', 'Funny & Misc.': 'funny'}
        
        current_orientation_path = None
        if '/orientation/' in current_url:
            current_orientation_path = current_url.split('/orientation/')[-1].strip('/')

        if current_orientation_path and current_orientation_path in orientations.values():
            pattern = r'<a href="(/porn/[^/"]+/videos)" class="pop plain">([^<]+)</a>'
            all_cats = list(set(re.findall(pattern, content, re.DOTALL)))
            if not all_cats:
                self.notify_info("No categories found for this orientation.")
                return
            
            known_prefixes = {p + '-' for p in orientations.values() if p != 'straight'}
            for path, name in sorted(all_cats, key=lambda x: x[1].strip()):
                clean_path = path.split('/')[2]
                is_straight = not any(clean_path.startswith(p) for p in known_prefixes)
                if (current_orientation_path == 'straight' and is_straight) or \
                   (current_orientation_path != 'straight' and clean_path.startswith(current_orientation_path + '-')):
                    cat_url = urllib.parse.urljoin(self.base_url, path)
                    self.add_dir(html.unescape(name.strip()), cat_url, 2, self.icons['categories'])
        else:
            for name, path_part in orientations.items():
                self.add_dir(f"[COLOR yellow]{name}[/COLOR]", f'{self.base_url}/orientation/{path_part}', 2, self.icons['categories'])

    def add_next_button(self, content, current_url):
        match = re.search(r'<link rel="next" href="(.+?)"', content)
        if match:
            self.add_dir('[COLOR blue]Next Page >>>>[/COLOR]', html.unescape(match.group(1)), 2, self.icons['default'])

    def play_video(self, url):
        content = self._make_request(url)
        if content:
            m = re.search(r"__fileurl = '(.+?)';", content)
            if m:
                path = m.group(1)
                li = xbmcgui.ListItem(path=path)
                li.setProperty('IsPlayable', 'true')
                li.setMimeType('video/mp4')
                xbmcplugin.setResolvedUrl(self.addon_handle, True, li)
                return
        self.notify_error("Failed to find media URL")

    def select_sort(self, original_url=None):
        current_key = self.get_current_sort_key()
        try:
            preselect_idx = self.sort_options.index(current_key)
        except ValueError:
            preselect_idx = 0
        
        dialog = xbmcgui.Dialog()
        idx = dialog.select("Sort by...", self.sort_options, preselect=preselect_idx)

        if idx != -1:
            self.addon.setSetting(self.setting_id_sort, str(idx))
            new_sort_key = self.sort_options[idx]
            
            if new_sort_key == "Random Video":
                self._make_request(urllib.parse.urljoin(self.base_url, self.sort_paths[new_sort_key]))
                return
                
            new_sort_path = self.sort_paths[new_sort_key]
            new_url = urllib.parse.urljoin(self.base_url, new_sort_path)
            
            update_command = f"Container.Update({sys.argv[0]}?mode=2&website={self.name}&url={urllib.parse.quote_plus(new_url)})"
            xbmc.sleep(250)
            xbmc.executebuiltin(update_command)