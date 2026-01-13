#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
import sys
import os
import urllib.parse
import html
import xbmc
import xbmcgui
import xbmcplugin
from resources.lib.base_website import BaseWebsite

class EromeWebsite(BaseWebsite):
    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="erome",
            base_url="https://www.erome.com",
            search_url="https://www.erome.com/search?q={}",
            addon_handle=addon_handle,
            addon=addon
        )
        self.sort_options = ["Hot", "New"]
        self.sort_paths = {
            0: "/explore",
            1: "/explore/new"
        }
        self.content_options = ["All", "Straight", "Gay", "Trans", "Hentai"]
        self.content_queries = {
            1: "straight",
            2: "gay",
            3: "trans",
            4: "hentai"
        }
        self.icon = os.path.join(self.addon.getAddonInfo('path'), 'resources', 'logos', 'erome.png')

    def get_headers(self):
        return {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'identity',
            'Referer': self.base_url + '/',
            'Cookie': 'disclaimer=1; collapse=0'
        }

    def get_start_url_and_label(self):
        try:
            sort_idx = int(self.addon.getSetting('erome_sort_by') or '1')
        except ValueError:
            sort_idx = 1
            
        try:
            content_idx = int(self.addon.getSetting('erome_content_type') or '0')
        except ValueError:
            content_idx = 0

        label = f"Erome - {self.content_options[content_idx]} ({self.sort_options[sort_idx]})"
        
        if content_idx > 0 and content_idx in self.content_queries:
            query = self.content_queries[content_idx]
            base = f"{self.base_url}/search?q={query}"
            if sort_idx == 1: 
                base += "&o=new"
            return base, label
        else:
            return f"{self.base_url}{self.sort_paths[sort_idx]}", label

    def make_request(self, url):
        vendor_path = os.path.join(self.addon.getAddonInfo('path'), 'resources', 'lib', 'vendor')
        if vendor_path not in sys.path:
            sys.path.insert(0, vendor_path)
        
        try:
            import requests
            if not hasattr(self, '_session'):
                self._session = requests.Session()
            
            response = self._session.get(url, headers=self.get_headers(), timeout=15)
            self.logger.info(f"[{self.name.title()}] Request status for {url}: {response.status_code}")
            response.raise_for_status()
            return response.text
        except Exception as e:
            self.logger.error(f"[{self.name.title()}] Request failed: {e}")
            return None

    def process_content(self, url):
        if not url or url == "BOOTSTRAP" or url == self.base_url or url == self.base_url + "/":
            url, _ = self.get_start_url_and_label()
            
        self.add_basic_dirs(url)
        content = self.make_request(url)
        if not content:
            self.notify_error("Failed to load page")
            self.end_directory()
            return
            
        self.logger.info(f"[{self.name.title()}] Content length: {len(content)}")
        path = urllib.parse.urlparse(url).path
        
        if len(content) < 15000 and 'id="disclaimer"' in content:
            self.logger.warning(f"[{self.name.title()}] Hit disclaimer page, trying to proceed anyway...")

        if '/a/' in path:
            self.process_album(content, url)
        else:
            self.process_album_list(content, url)
            
        self.end_directory()

    def add_basic_dirs(self, current_url):
        self.add_dir('[COLOR blue]Search[/COLOR]', '', 5, self.icons.get('search', self.icon), self.fanart)

    def get_global_context_menu(self):
        return [
            ('Select Sort...', f'RunPlugin({sys.argv[0]}?mode=7&action=select_sort&website={self.name})'),
            ('Select Content...', f'RunPlugin({sys.argv[0]}?mode=7&action=select_content&website={self.name})')
        ]

    def process_album_list(self, content, current_url):
        items_added = 0
        seen_urls = set()
        blocks = re.split(r'<div[^>]*class="[^"]*album[^"]*"[^>]*>', content)[1:]
        
        for block in blocks:
            url_match = re.search(r'href="(https?://[^"]*erome.com/a/[^"]+)"', block, re.IGNORECASE)
            if not url_match:
                 url_match = re.search(r'href="(/a/[^"]+)"', block, re.IGNORECASE)
            
            if url_match:
                album_url = url_match.group(1)
                if not album_url.startswith('http'):
                    album_url = self.base_url + album_url
                
                if album_url in seen_urls: continue
                seen_urls.add(album_url)
                
                thumb_match = re.search(r'data-src="([^"]+)"', block, re.IGNORECASE)
                if not thumb_match:
                    thumb_match = re.search(r'src="([^"]+)"', block, re.IGNORECASE)
                
                thumb = thumb_match.group(1) if thumb_match else ''
                if thumb.startswith('data:image'):
                    thumb_match = re.search(r'data-src="([^"]+)"', block, re.IGNORECASE)
                    thumb = thumb_match.group(1) if thumb_match else ''
                
                title_match = re.search(r'class="album-title"[^>]*>([^<]+)', block, re.IGNORECASE)
                if not title_match:
                     title_match = re.search(r'alt="([^"]+)"', block, re.IGNORECASE)
                
                title = title_match.group(1) if title_match else album_url.split('/')[-1]
                
                context_menu = [
                    ('Play Album', f'RunPlugin({sys.argv[0]}?mode=7&action=play_album&website={self.name}&original_url={urllib.parse.quote_plus(album_url)})'),
                    ('Play All From Here', f'RunPlugin({sys.argv[0]}?mode=7&action=play_all_from_here&website={self.name}&original_url={urllib.parse.quote_plus(album_url + "|" + current_url)})')
                ]
                context_menu.extend(self.get_global_context_menu())
                
                self.add_dir(html.unescape(title.strip()), album_url, 2, thumb or self.icon, self.fanart, context_menu=context_menu)
                items_added += 1
        
        if items_added == 0:
            links = re.findall(r'href="((?:https?://www\.erome\.com)?/a/([a-zA-Z0-9]+))"', content)
            seen_ids = set()
            for link_url, album_id in links:
                if album_id in seen_ids: continue
                seen_ids.add(album_id)
                url = link_url if link_url.startswith('http') else self.base_url + link_url
                self.add_dir(f"Album {album_id}", url, 2, self.icon, self.fanart)
                items_added += 1
        
        self.logger.info(f"[{self.name.title()}] Found {items_added} albums")
        
        next_match = re.search(r'<a[^>]*href="([^"]+)"[^>]*rel="next"', content)
        if not next_match:
            next_match = re.search(r'<a[^>]*href="([^"]+)"[^>]*>Next</a>', content, re.IGNORECASE)
        if next_match:
            next_url = next_match.group(1)
            next_url = html.unescape(next_url)
            next_url = urllib.parse.urljoin(current_url, next_url)
            
            if '?' in current_url and '?' in next_url and not next_url.split('?')[0].endswith(current_url.split('?')[0]):
                match_href = next_match.group(1)
                if match_href.startswith('?'):
                    base_parts = list(urllib.parse.urlparse(current_url))
                    query = dict(urllib.parse.parse_qsl(base_parts[4]))
                    query.update(dict(urllib.parse.parse_qsl(match_href[1:])))
                    base_parts[4] = urllib.parse.urlencode(query)
                    next_url = urllib.parse.urlunparse(base_parts)

            self.add_dir('[COLOR blue]Next Page >>[/COLOR]', next_url, 2, self.icons.get('default', self.icon), context_menu=self.get_global_context_menu())

    def process_album(self, content, album_url):
        items_added = 0
        self.add_dir('[COLOR green]Play All Videos[/COLOR]', album_url, 7, self.icons['default'], action='play_album', original_url=album_url)
        
        title_match = re.search(r'<meta[^>]*property="og:title"[^>]*content="([^"]+)"', content)
        album_title = title_match.group(1) if title_match else "Album"
        
        video_pattern = re.compile(r'<source[^>]*src="([^"]+)"[^>]*/?>', re.IGNORECASE)
        raw_video_urls = video_pattern.findall(content)
        video_pattern2 = re.compile(r'<video[^>]*src="([^"]+)"', re.IGNORECASE)
        raw_video_urls.extend(video_pattern2.findall(content))
        
        video_urls = []
        for v in raw_video_urls:
            if v not in video_urls:
                video_urls.append(v)
        
        poster_pattern = re.compile(r'<video[^>]*poster="([^"]+)"[^>]*>.*?<source[^>]*src="([^"]+)"', re.DOTALL | re.IGNORECASE)
        poster_matches = poster_pattern.findall(content)
        video_to_poster = {video: poster for poster, video in poster_matches}
        
        for i, video_url in enumerate(video_urls, 1):
            poster = video_to_poster.get(video_url, '')
            title = f"{album_title} - Video {i}" if len(video_urls) > 1 else album_title
            self.add_link(html.unescape(title), video_url, 4, poster or self.icon, self.fanart)
            items_added += 1
        
        self.logger.info(f"[{self.name.title()}] Found {items_added} videos in album")

    def play_video(self, url):
        if url:
            li = xbmcgui.ListItem(path=url)
            li.setProperty('IsPlayable', 'true')
            headers = f'User-Agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36&Referer={self.base_url}/'
            play_url = url + '|' + headers
            li.setPath(play_url)
            li.setProperty('inputstream.adaptive.stream_headers', headers)
            li.setMimeType('video/mp4')
            xbmcplugin.setResolvedUrl(self.addon_handle, True, li)
        else:
            self.notify_error("No video URL provided")

    def play_album(self, url):
        if not url: return
        content = self.make_request(url)
        if not content:
            self.notify_error("Failed to load album")
            return

        video_pattern = re.compile(r'<source[^>]*src="([^"]+)"[^>]*/?>', re.IGNORECASE)
        raw_video_urls = video_pattern.findall(content)
        video_pattern2 = re.compile(r'<video[^>]*src="([^"]+)"', re.IGNORECASE)
        raw_video_urls.extend(video_pattern2.findall(content))
        
        video_urls = []
        for v in raw_video_urls:
            if v not in video_urls:
                video_urls.append(v)
                
        if not video_urls:
            self.notify_error("No videos found in album")
            return

        title_match = re.search(r'<meta[^>]*property="og:title"[^>]*content="([^"]+)"', content)
        album_title = title_match.group(1) if title_match else "Album"

        playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
        playlist.clear()
        headers = f'User-Agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36&Referer={self.base_url}/'

        for i, video_url in enumerate(video_urls, 1):
            title = f"{album_title} - Video {i}" if len(video_urls) > 1 else album_title
            play_url = video_url + '|' + headers
            li = xbmcgui.ListItem(html.unescape(title))
            li.setArt({'thumb': self.icon, 'icon': self.icon})
            li.setProperty('IsPlayable', 'true')
            li.setProperty('inputstream.adaptive.stream_headers', headers)
            li.setMimeType('video/mp4')
            playlist.add(url=play_url, listitem=li)

        xbmc.Player().play(playlist)

    def play_all_from_here(self, packed_url):
        if not packed_url or '|' not in packed_url: return
        start_album_url, page_url = packed_url.split('|', 1)
        content = self.make_request(page_url)
        if not content:
            self.notify_error("Failed to load page")
            return

        links = re.findall(r'href="((?:https?://www\.erome\.com)?/a/[a-zA-Z0-9]+)"', content)
        all_albums = []
        for l in links:
            full_l = l if l.startswith('http') else self.base_url + l
            if full_l not in all_albums:
                all_albums.append(full_l)

        if start_album_url not in all_albums:
            self.notify_error("Could not find starting album on page")
            return

        start_idx = all_albums.index(start_album_url)
        albums_to_play = all_albums[start_idx:]
        playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
        playlist.clear()
        
        progress = xbmcgui.DialogProgress()
        progress.create('Erome', 'Gathering videos from albums...')
        headers = f'User-Agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36&Referer={self.base_url}/'
        total = len(albums_to_play)
        added_count = 0
        
        for i, album_url in enumerate(albums_to_play):
            if progress.iscanceled(): break
            percent = int((i / float(total)) * 100)
            progress.update(percent, f'Processing album {i+1} of {total}...')
            album_content = self.make_request(album_url)
            if not album_content: continue
            
            title_match = re.search(r'<meta[^>]*property="og:title"[^>]*content="([^"]+)"', album_content)
            album_title = title_match.group(1) if title_match else "Album"
            video_pattern = re.compile(r'<source[^>]*src="([^"]+)"[^>]*/?>', re.IGNORECASE)
            raw_vids = video_pattern.findall(album_content)
            video_pattern2 = re.compile(r'<video[^>]*src="([^"]+)"', re.IGNORECASE)
            raw_vids.extend(video_pattern2.findall(album_content))
            
            vids = []
            for v in raw_vids:
                if v not in vids: vids.append(v)
            
            for j, v_url in enumerate(vids, 1):
                title = f"{album_title} - Video {j}" if len(vids) > 1 else album_title
                play_url = v_url + '|' + headers
                li = xbmcgui.ListItem(html.unescape(title))
                li.setArt({'thumb': self.icon, 'icon': self.icon})
                li.setProperty('IsPlayable', 'true')
                li.setProperty('inputstream.adaptive.stream_headers', headers)
                li.setMimeType('video/mp4')
                playlist.add(url=play_url, listitem=li)
                added_count += 1

        progress.close()
        if added_count > 0:
            xbmc.Player().play(playlist)
        else:
            self.notify_error("No videos found to play")

    def select_sort(self, original_url=None):
        dialog = xbmcgui.Dialog()
        idx = dialog.select("Sort by...", self.sort_options)
        if idx != -1:
            self.addon.setSetting('erome_sort_by', str(idx))
            xbmc.executebuiltin(f'Container.Update({sys.argv[0]}?mode=2&url=BOOTSTRAP&website={self.name},replace)')

    def select_content(self, original_url=None):
        dialog = xbmcgui.Dialog()
        idx = dialog.select("Select Content...", self.content_options)
        if idx != -1:
            self.addon.setSetting('erome_content_type', str(idx))
            xbmc.executebuiltin(f'Container.Update({sys.argv[0]}?mode=2&url=BOOTSTRAP&website={self.name},replace)')

    def search(self, query):
        if query:
            search_url = self.search_url.format(urllib.parse.quote_plus(query))
            self.process_content(search_url)
        else:
            self.end_directory()
