#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os
import re
import urllib.parse
import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon
from resources.lib.base_website import BaseWebsite

try:
    addon_path = xbmcaddon.Addon().getAddonInfo('path')
    vendor_path = os.path.join(addon_path, 'resources', 'lib', 'vendor')
    if vendor_path not in sys.path:
        sys.path.insert(0, vendor_path)
except:
    pass

try:
    import cloudscraper
    HAS_CLOUDSCRAPER = True
except ImportError:
    HAS_CLOUDSCRAPER = False

import requests

class Tnaflix(BaseWebsite):
    BASE_URL_STR = "https://www.tnaflix.com/"
    
    def __init__(self, addon_handle):
        super().__init__(
            name="tnaflix",
            base_url=self.BASE_URL_STR,
            search_url="https://www.tnaflix.com/search?what={}",
            addon_handle=addon_handle
        )
        
        self.sort_options = ["Featured", "Most Recent", "Top Rated"]
        self.sort_paths = {
            "Featured": "featured",
            "Most Recent": "new",
            "Top Rated": "toprated"
        }
        
        self.session = None
        self.ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        
        if HAS_CLOUDSCRAPER:
            self.session = cloudscraper.create_scraper(
                browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True}
            )
            self.ua = self.session.headers.get('User-Agent', self.ua)
        else:
            self.session = requests.Session()
            self.session.headers.update({'User-Agent': self.ua})

    def make_request(self, url, headers=None):
        if not headers:
            headers = {'Referer': self.base_url}
        try:
            self.session.headers.update(headers)
            response = self.session.get(url, timeout=20)
            if response.status_code == 200:
                return response.text
        except Exception:
            pass
        return None

    def add_basic_dirs(self, current_url):
        self.add_dir('[COLOR blue]Search[/COLOR]', '', 5, self.icons['search'], self.fanart)
        self.add_dir('Categories', urllib.parse.urljoin(self.base_url, 'categories'), 8, self.icons['categories'], self.fanart)
        self.add_dir('Pornstars', urllib.parse.urljoin(self.base_url, 'pornstars'), 9, self.icons['pornstars'], self.fanart)
        self.add_dir('Channels', urllib.parse.urljoin(self.base_url, 'channels'), 10, self.icons['default'], self.fanart)
    
    def process_content(self, url):
        if url.endswith('/categories') or '/categories' in url:
            self.process_categories(url)
            return
        
        if url.endswith('/pornstars') or '/pornstars?' in url:
            self.process_pornstars(url)
            return
        
        if url.endswith('/channels') or '/channels?' in url:
            self.process_channels(url)
            return
        
        self.add_basic_dirs(url)
        
        content = self.make_request(url)
        if not content:
            self.notify_error("Failed to load content")
            self.end_directory()
            return
        
        self.process_video_list(content, url)
        self.end_directory()

    def process_video_list(self, content, current_url):
        video_items = []
        
        vid_blocks = re.findall(r'<div[^>]+data-vid="(\d+)"[^>]*>(.*?)</div>\s*</div>', content, re.DOTALL | re.IGNORECASE)
        
        if not vid_blocks:
            vid_blocks = re.findall(r'<div[^>]+class="[^"]*col[^"]*"[^>]*>(.*?)</div>\s*</div>', content, re.DOTALL | re.IGNORECASE)
        
        for vid_id, block in vid_blocks:
            url_match = re.search(r'href="(https://www\.tnaflix\.com/[^"]+/video\d+)"', block)
            if not url_match:
                url_match = re.search(r'href="(/[^"]+/video\d+)"', block)
            
            if not url_match:
                continue
            
            video_url = url_match.group(1)
            if not video_url.startswith('http'):
                video_url = urllib.parse.urljoin(self.base_url, video_url)
            
            thumb_match = re.search(r'<img[^>]+(?:data-src|src)="(https?://[^"]+(?:img\.tnaflix|cdnl\.tnaflix)[^"]*)"', block)
            if not thumb_match:
                thumb_match = re.search(r'data-src="([^"]+)"', block)
            if not thumb_match:
                thumb_match = re.search(r'<img[^>]+src="([^"]+)"', block)
            
            thumb = thumb_match.group(1) if thumb_match else self.icons['default']
            if thumb and not thumb.startswith('http'):
                if thumb.startswith('//'):
                    thumb = 'https:' + thumb
                elif not thumb.startswith('/assets'):
                    thumb = urllib.parse.urljoin(self.base_url, thumb)
                else:
                    thumb = self.icons['default']
            
            dur_match = re.search(r'video-duration[^>]*>(\d{1,2}:\d{2}(?::\d{2})?)<', block)
            duration = dur_match.group(1) if dur_match else ''
            
            title_match = re.search(r'class="[^"]*video-title[^"]*"[^>]*>([^<]+)<', block)
            if not title_match:
                title_match = re.search(r'alt="([^"]+)"', block)
            title = title_match.group(1).strip() if title_match else f"Video {vid_id}"
            
            video_items.append({
                'url': video_url,
                'thumb': thumb,
                'duration': duration,
                'title': title
            })
        
        if not video_items:
            normalized = re.sub(r'\s+', ' ', content)
            pattern = r'href="(https://www\.tnaflix\.com/[^"]+/video(\d+))"[^>]*>.*?(?:data-src|src)="([^"]+)".*?video-duration[^>]*>(\d{1,2}:\d{2})'
            matches = re.findall(pattern, normalized, re.IGNORECASE)
            
            for url, vid_id, thumb, duration in matches:
                title_pattern = rf'video{vid_id}"[^>]*class="[^"]*video-title[^"]*"[^>]*>([^<]+)<'
                title_match = re.search(title_pattern, normalized, re.IGNORECASE)
                title = title_match.group(1).strip() if title_match else f"Video {vid_id}"
                
                if thumb.startswith('/assets'):
                    thumb = self.icons['default']
                elif not thumb.startswith('http'):
                    thumb = 'https:' + thumb if thumb.startswith('//') else self.icons['default']
                
                video_items.append({
                    'url': url,
                    'thumb': thumb,
                    'duration': duration,
                    'title': title
                })
        
        seen_urls = set()
        for item in video_items:
            if item['url'] not in seen_urls:
                seen_urls.add(item['url'])
                
                display_name = item['title']
                if item['duration']:
                    display_name = f"{item['title']} [COLOR yellow]({item['duration']})[/COLOR]"
                
                info = {'mediatype': 'video'}
                if item['duration']:
                    parts = item['duration'].split(':')
                    try:
                        if len(parts) == 3:
                            dur_sec = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
                        else:
                            dur_sec = int(parts[0]) * 60 + int(parts[1])
                        info['duration'] = dur_sec
                    except:
                        pass
                
                self.add_link(display_name, item['url'], 4, item['thumb'], self.fanart, info_labels=info)
        
        next_page = re.search(r'<link[^>]+rel="next"[^>]+href="([^"]+)"', content, re.IGNORECASE)
        if not next_page:
            next_page = re.search(r'href="([^"]*\?page=(\d+)[^"]*)"', content)
        if next_page:
            next_url = next_page.group(1)
            if not next_url.startswith('http'):
                next_url = urllib.parse.urljoin(self.base_url, next_url)
            self.add_dir('[COLOR blue]Next Page >>>>[/COLOR]', next_url, 2, self.icons['default'], self.fanart)

    def process_categories(self, url):
        content = self.make_request(url)
        if not content:
            self.notify_error("Failed to load categories")
            self.end_directory()
            return
        
        self.add_basic_dirs(url)
        
        pattern = r'<div[^>]+class="[^"]*category-item[^"]*"[^>]*>\s*<a[^>]+href="(https://www\.tnaflix\.com/[^"]+)"[^>]*>\s*([^<]+?)\s*(?:<span[^>]*>[^<]+</span>)?\s*</a>'
        matches = re.findall(pattern, content, re.DOTALL | re.IGNORECASE)
        
        if not matches:
            pattern = r'<a[^>]+href="(https://www\.tnaflix\.com/[^/"]+(?:-porn|-videos|-sex|/)[^"]*)"[^>]*>\s*([^<]+?)\s*(?:<span[^>]*>[^<]+</span>)?\s*</a>'
            all_matches = re.findall(pattern, content, re.IGNORECASE)
            matches = [(m[0], m[1]) for m in all_matches if '/' not in m[0].replace('https://www.tnaflix.com/', '').strip('/')]
        
        seen = set()
        for cat_url, cat_name in matches:
            if '/pornstar' in cat_url or '/channel' in cat_url or '/video' in cat_url:
                continue
            if cat_url not in seen:
                seen.add(cat_url)
                name = cat_name.strip()
                if name and len(name) > 1 and not name.startswith('<'):
                    self.add_dir(name, cat_url, 2, self.icons['categories'], self.fanart)
        
        self.end_directory()

    def process_pornstars(self, url):
        content = self.make_request(url)
        if not content:
            self.notify_error("Failed to load pornstars")
            self.end_directory()
            return
        
        self.add_basic_dirs(url)
        
        pattern = r'<a[^>]+class="[^"]*thumb[^"]*"[^>]+href="(https://www\.tnaflix\.com/profile/[^"]+|/profile/[^"]+)"[^>]*>.*?<img[^>]+src="([^"]+)"[^>]*>.*?<div[^>]+class="[^"]*thumb-title[^"]*"[^>]*>([^<]+)</div>'
        matches = re.findall(pattern, content, re.DOTALL | re.IGNORECASE)
        
        seen = set()
        for star_path, thumb, name in matches:
            if star_path.startswith('/'):
                star_url = urllib.parse.urljoin(self.base_url, star_path)
            else:
                star_url = star_path
            
            if star_url in seen:
                continue
            seen.add(star_url)
            
            if not thumb.startswith('http'):
                thumb = 'https:' + thumb if thumb.startswith('//') else self.icons['pornstars']
            
            star_name = name.strip()
            if star_name:
                self.add_dir(star_name, star_url, 2, thumb, self.fanart)
        
        next_match = re.search(r'<link[^>]+rel="next"[^>]+href="([^"]+)"', content, re.IGNORECASE)
        if not next_match:
            next_match = re.search(r'href="([^"]*\?page=(\d+)[^"]*)"', content)
        if next_match:
            next_url = next_match.group(1)
            if not next_url.startswith('http'):
                next_url = urllib.parse.urljoin(self.base_url, next_url)
            self.add_dir('[COLOR blue]Next Page >>>>[/COLOR]', next_url, 9, self.icons['default'], self.fanart)
        
        self.end_directory()

    def process_channels(self, url):
        content = self.make_request(url)
        if not content:
            self.notify_error("Failed to load channels")
            self.end_directory()
            return
        
        self.add_basic_dirs(url)
        
        pattern = r'<a[^>]+class="[^"]*thumb[^"]*"[^>]+href="(https://www\.tnaflix\.com/channel/[^"]+|/channel/[^"]+)"[^>]*>.*?<img[^>]+src="([^"]+)"[^>]*>.*?<div[^>]+class="[^"]*thumb-title[^"]*"[^>]*>([^<]+)</div>'
        matches = re.findall(pattern, content, re.DOTALL | re.IGNORECASE)
        
        seen = set()
        for chan_path, thumb, name in matches:
            if chan_path.startswith('/'):
                chan_url = urllib.parse.urljoin(self.base_url, chan_path)
            else:
                chan_url = chan_path
            
            if chan_url in seen:
                continue
            seen.add(chan_url)
            
            if not thumb.startswith('http'):
                thumb = 'https:' + thumb if thumb.startswith('//') else self.icons['default']
            
            chan_name = name.strip()
            if chan_name:
                self.add_dir(chan_name, chan_url, 2, thumb, self.fanart)
        
        next_match = re.search(r'<link[^>]+rel="next"[^>]+href="([^"]+)"', content, re.IGNORECASE)
        if not next_match:
            next_match = re.search(r'href="([^"]*\?page=(\d+)[^"]*)"', content)
        if next_match:
            next_url = next_match.group(1)
            if not next_url.startswith('http'):
                next_url = urllib.parse.urljoin(self.base_url, next_url)
            self.add_dir('[COLOR blue]Next Page >>>>[/COLOR]', next_url, 10, self.icons['default'], self.fanart)
        
        self.end_directory()

    def play_video(self, url):
        content = self.make_request(url)
        if not content:
            return self.notify_error("Failed to load video page")
        
        source_pattern = r'<source[^>]+src="([^"]+\.mp4[^"]*)"[^>]*(?:size="(\d+)")?'
        sources = re.findall(source_pattern, content, re.IGNORECASE)
        
        if not sources:
            cdn_pattern = r'(https://sl\d+\.tnaflix\.com/[^"]+\.mp4[^"]*)'
            sources = [(url, '') for url in re.findall(cdn_pattern, content)]
        
        if not sources:
            return self.notify_error("No video source found")
        
        video_url = None
        max_quality = 0
        
        for src, size in sources:
            quality = int(size) if size else 0
            if not quality:
                qual_match = re.search(r'-(\d+)p\.mp4', src)
                if qual_match:
                    quality = int(qual_match.group(1))
            
            if quality > max_quality:
                max_quality = quality
                video_url = src
        
        if not video_url and sources:
            video_url = sources[0][0]
        
        if video_url:
            kodi_headers = {
                'User-Agent': self.ua,
                'Referer': url
            }
            
            if self.session:
                cookies = self.session.cookies.get_dict()
                if cookies:
                    kodi_headers['Cookie'] = "; ".join([f"{k}={v}" for k, v in cookies.items()])
            
            final_url = f"{video_url}|{urllib.parse.urlencode(kodi_headers)}"
            
            li = xbmcgui.ListItem(path=final_url)
            li.setProperty('IsPlayable', 'true')
            li.setMimeType('video/mp4')
            
            xbmcplugin.setResolvedUrl(self.addon_handle, True, li)
        else:
            self.notify_error("No playable video found")

    def notify_error(self, msg):
        xbmcgui.Dialog().notification('AdultHideout', msg, xbmcgui.NOTIFICATION_ERROR)
