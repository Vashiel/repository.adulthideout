#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
import sys
import json
import urllib.parse as urllib_parse
import urllib.request as urllib_request
from http.cookiejar import CookieJar
import time
import xbmc
import xbmcgui
import xbmcplugin
from resources.lib.base_website import BaseWebsite
from resources.lib.decoders.tubepornclassic_decoder import custom_base64_decode

class TubepornclassicWebsite(BaseWebsite):
    config = {
        "name": "tubepornclassic",
        "base_url": "https://tubepornclassic.com/",
        "search_url": "https://tubepornclassic.com/search/?q={}"
    }

    def __init__(self, addon_handle):
        super().__init__(
            name=self.config["name"],
            base_url=self.config["base_url"],
            search_url=self.config["search_url"],
            addon_handle=addon_handle
        )
        self.sort_options = ["Latest Updates", "Top Rated", "Longest"]
        self.sort_paths = {
            "Latest Updates": "latest-updates/",
            "Top Rated": "top-rated/",
            "Longest": "longest/"
        }
        self.search_sort_options = ["Relevance", "Latest", "Top Rated", "Most Viewed", "Longest"]
        self.search_sort_values = ["relevance", "latest", "top-rated", "most-viewed", "longest"]

    def get_headers(self, referer=None, is_json=False):
        headers = {
            'User-Agent': 'Mozilla/5.0',
            'Accept': 'application/json' if is_json else 'text/html',
            'Cookie': 'kt_lang=de; _agev=1'
        }
        if referer:
            headers['Referer'] = referer
        return headers

    def make_request(self, url, headers=None, data=None):
        headers = headers or self.get_headers(url, 'json' in url.lower())
        cj = CookieJar()
        opener = urllib_request.build_opener(urllib_request.HTTPCookieProcessor(cj))
        if data:
            data = urllib_parse.urlencode(data).encode('utf-8')
        try:
            req = urllib_request.Request(url, data=data, headers=headers)
            with opener.open(req, timeout=60) as res:
                return res.read().decode('utf-8', errors='ignore')
        except Exception as e:
            self.logger.error(f"Request failed: {url} -> {e}")
            self.notify_error("Network error")
            return ""

    def fetch_categories(self):
        api = f"{self.base_url}api/json/categories/14400/str.toptn.en.json"
        content = self.make_request(api, self.get_headers(self.base_url + 'categories/', True))
        try:
            data = json.loads(content)
            return data.get('categories', [])
        except Exception:
            self.notify_error("Invalid categories response")
            return []

    def fetch_videos(self, page=1, sort_by='latest-updates', category=None):
        if category:
            api = f"{self.base_url}api/json/videos2/86400/str/{sort_by}/60/categories.{category}.{page}.all...json"
            ref = f"{self.base_url}categories/{category}/"
        else:
            api = f"{self.base_url}api/json/videos2/86400/str/{sort_by}/60/..{page}.all...json"
            ref = f"{self.base_url}{sort_by}/"
        content = self.make_request(api, self.get_headers(ref, True))
        try:
            data = json.loads(content)
            return data.get('videos', []), data.get('pages', 1)
        except Exception:
            self.notify_error("Invalid videos response")
            return [], 1

    def fetch_search(self, term, page=1, sort_by='relevance'):
        params = {'params': f"86400/str/{sort_by}/60/search..{page}.all..", 's': term}
        api = f"{self.base_url}api/videos2.php?{urllib_parse.urlencode(params)}"
        content = self.make_request(api, self.get_headers(self.base_url + 'search/', True))
        try:
            data = json.loads(content)
            return data.get('videos', []), data.get('pages', 1)
        except Exception:
            self.notify_error("Invalid search response")
            return [], 1

    def apply_sort(self, url):
        idx = int(self.addon.getSetting('tubepornclassic_sort_by') or '0')
        sort_option = self.sort_options[idx]
        sort_path = self.sort_paths.get(sort_option, "latest-updates/").strip('/')
        
        p = urllib_parse.urlparse(url)
        parts = p.path.strip('/').split('/')
        if parts and parts[0] == 'categories':
            parts = ['categories', parts[1], sort_path]
        else:
            parts = [sort_path]
        new_path = '/' + '/'.join(parts) + '/'
        return urllib_parse.urlunparse((p.scheme, p.netloc, new_path, '', '', ''))

    def process_content(self, url):
        p = urllib_parse.urlparse(url)
        path = p.path.strip('/')
        q = urllib_parse.parse_qs(p.query)
        
        idx = int(self.addon.getSetting('tubepornclassic_sort_by') or '0')
        sort_option = self.sort_options[idx]
        sort = self.sort_paths[sort_option].strip('/')
        
        page = 1
        category = None

        if path == 'categories':
            self.add_basic_dirs(url)
            categories = self.fetch_categories()
            for cat in categories:
                title = cat.get('title', 'Unknown').strip()
                dir_name = cat.get('dir', '')
                count = cat.get('total_videos', '0').strip()
                thumb = ''
                top = cat.get('toptn', [])
                if top:
                    thumb = top[0].get('scr', '')
                    if thumb and not thumb.startswith('http'):
                        thumb = urllib_parse.urljoin(self.base_url, thumb)
                disp = f"{title} ({count})"
                url_cat = f"{self.base_url}categories/{dir_name}/"
                self.add_dir(disp, url_cat, 2, thumb, '', [
                    ('Sort by...', f'RunPlugin({sys.argv[0]}?mode=7&website={self.name}&action=select_sort&original_url={urllib_parse.quote_plus(url_cat)})')
                ])
            self.end_directory()
            return

        if 'search' in path:
            term = q.get('q', [''])[0]
            vids, pages = self.fetch_search(
                term,
                page,
                self.search_sort_values[int(self.addon.getSetting('tubepornclassic_search_sort_by') or '0')]
            )
        elif path.startswith('categories/'):
            parts = path.split('/')
            category = parts[1]
            if len(parts) > 2 and parts[2].isdigit():
                page = int(parts[2])
            vids, pages = self.fetch_videos(page, sort, category)
        else:
            parts = path.split('/')
            valid_sort_paths = [v.strip('/') for v in self.sort_paths.values()]
            if parts and parts[0] in valid_sort_paths:
                sort = parts[0]
            if len(parts) > 1 and parts[1].isdigit():
                page = int(parts[1])
            vids, pages = self.fetch_videos(page, sort)

        self.add_basic_dirs(url)
        for v in vids:
            vid = v.get('video_id')
            title = v.get('title', 'No Title')
            dur = v.get('duration', '0:00')
            thumb = v.get('scr', '')
            if thumb and not thumb.startswith('http'):
                thumb = urllib_parse.urljoin(self.base_url, thumb)
            page_url = f"{self.base_url}videos/{vid}/"
            disp = f"{title} [{dur}]"
            self.add_link(disp, page_url, 4, thumb, '', [
                ('Sort by...', f'RunPlugin({sys.argv[0]}?mode=7&website={self.name}&action=select_sort&original_url={urllib_parse.quote_plus(url)})')
            ])

        if page < pages:
            next_url = url.rstrip('/') + f"/{page+1}/"
            self.add_dir(f"Next Page ({page+1})", next_url, 2)

        self.end_directory()

    def add_basic_dirs(self, current):
        context_menu = [
            ('Sort by...', f'RunPlugin({sys.argv[0]}?mode=7&website={self.name}&action=select_sort&original_url={urllib_parse.quote_plus(str(current))}')
        ]
        dirs = [
            ('Search TubePornClassic', '', 5, self.icons['search'], context_menu, self.config['name']),
            ('Categories', f'{self.config["base_url"]}categories', 2, self.icons['categories'], context_menu)
        ]
        for name, url, mode, icon, ctx, *extra in dirs:
            self.add_dir(name, url, mode, icon, '', ctx, name_param=extra[0] if extra else name)

    def select_sort(self, original_url=None):
        if not original_url:
            return self.notify_error("No context")
        dialog = xbmcgui.Dialog()
        idx = dialog.select("Sort by...", self.sort_options, preselect=int(self.addon.getSetting('tubepornclassic_sort_by') or '0'))
        if idx == -1:
            return
        self.addon.setSetting('tubepornclassic_sort_by', str(idx))
        new_url = self.apply_sort(original_url)
        xbmc.executebuiltin(f"Container.Update({sys.argv[0]}?mode=2&url={urllib_parse.quote_plus(new_url)}&website={self.name},replace)")

    def play_video(self, url):
        m = re.search(r'/videos/(\d+)/', urllib_parse.unquote_plus(url))
        if not m:
            return self.notify_error("Invalid URL")
        vid = m.group(1)
        api = f"{self.base_url}api/videofile.php?video_id={vid}&lifetime=8640000&ti={int(time.time())}"
        content = self.make_request(api, self.get_headers(url, True))
        try:
            data = json.loads(content)
            enc = data[0].get('video_url', '') if isinstance(data, list) else ''
            dec = custom_base64_decode(enc)
            stream = dec if dec.startswith('http') else urllib_parse.urljoin(self.base_url, dec.lstrip('/'))
        except Exception:
            return self.notify_error("Playback error")

        li = xbmcgui.ListItem(path=stream)
        li.setMimeType('video/mp4')
        xbmcplugin.setResolvedUrl(self.addon_handle, True, li)