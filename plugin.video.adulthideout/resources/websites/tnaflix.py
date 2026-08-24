#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os
import re
import html
import urllib.parse
import xbmcgui
import xbmcplugin
import xbmcaddon
from resources.lib.base_website import BaseWebsite

try:
    addon_path = xbmcaddon.Addon().getAddonInfo('path')
    vendor_path = os.path.join(addon_path, 'resources', 'lib', 'vendor')
    if vendor_path not in sys.path:
        sys.path.insert(0, vendor_path)
except Exception:
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
        
        self.sort_options = ["Featured", "Most Recent", "Most Viewed", "Top Rated"]
        self.sort_dir_map = {
            0: "featured",
            1: "latest",
            2: "popular",
            3: "toprated"
        }

        self.duration_options = ["All Durations", "Short (1-3 min)", "Medium (3-10 min)", "Long (10-30 min)", "Full Length (30+ min)"]
        self.duration_map = {
            1: "short",
            2: "medium",
            3: "long",
            4: "full"
        }

        self.period_options = ["Anytime", "Today", "This Week", "This Month", "This Year"]
        self.period_map = {
            1: "day",
            2: "week",
            3: "month",
            4: "year"
        }

        self.setting_id_sort = "tnaflix_sort_by"
        self.setting_id_duration = "tnaflix_duration"
        self.setting_id_period = "tnaflix_period"
        
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

    def get_current_sort_idx(self):
        try:
            idx = int(self.addon.getSetting(self.setting_id_sort) or '0')
        except (ValueError, TypeError):
            idx = 0
        if not 0 <= idx < len(self.sort_options):
            idx = 0
        return idx

    def get_current_duration_idx(self):
        try:
            idx = int(self.addon.getSetting(self.setting_id_duration) or '0')
        except (ValueError, TypeError):
            idx = 0
        if not 0 <= idx < len(self.duration_options):
            idx = 0
        return idx

    def get_current_period_idx(self):
        try:
            idx = int(self.addon.getSetting(self.setting_id_period) or '0')
        except (ValueError, TypeError):
            idx = 0
        if not 0 <= idx < len(self.period_options):
            idx = 0
        return idx

    def build_tnaflix_url(self, query="", page=1, raw_url=None):
        if raw_url and raw_url != "BOOTSTRAP":
            parsed = urllib.parse.urlparse(raw_url)
            params = urllib.parse.parse_qs(parsed.query)
        else:
            params = {}

        if query:
            params["what"] = [query]

        sort_idx = self.get_current_sort_idx()
        dur_idx = self.get_current_duration_idx()
        period_idx = self.get_current_period_idx()

        if dur_idx in self.duration_map:
            params["d"] = [self.duration_map[dur_idx]]
        elif "d" in params:
            del params["d"]

        if period_idx in self.period_map:
            params["u"] = [self.period_map[period_idx]]
        elif "u" in params:
            del params["u"]

        if sort_idx in self.sort_dir_map and self.sort_dir_map[sort_idx] != "featured":
            params["dir"] = [self.sort_dir_map[sort_idx]]
        elif "dir" in params:
            del params["dir"]

        if page > 1:
            params["page"] = [str(page)]

        flat_params = {k: v[0] for k, v in params.items() if v}

        if "what" in flat_params or flat_params:
            url = f"{self.base_url.rstrip('/')}/search?{urllib.parse.urlencode(flat_params)}"
        else:
            path_map = {0: "featured", 1: "new", 2: "popular", 3: "toprated"}
            path = path_map.get(sort_idx, "featured")
            url = f"{self.base_url.rstrip('/')}/{path}"
            if page > 1:
                url += f"?page={page}"

        return url

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

    def get_global_context_menu(self, current_url=""):
        encoded_url = urllib.parse.quote_plus(current_url or self.base_url)
        return [
            ('Select Sort...', f'RunPlugin({sys.argv[0]}?mode=7&action=select_sort&website={self.name}&original_url={encoded_url})'),
            ('Select Duration...', f'RunPlugin({sys.argv[0]}?mode=7&action=select_duration&website={self.name}&original_url={encoded_url})'),
            ('Select Upload Period...', f'RunPlugin({sys.argv[0]}?mode=7&action=select_period&website={self.name}&original_url={encoded_url})')
        ]

    def add_basic_dirs(self, current_url):
        context_menu = self.get_global_context_menu(current_url)
        self.add_dir('[COLOR blue]Search[/COLOR]', '', 5, self.icons['search'], self.fanart, context_menu=context_menu)
        self.add_dir('Categories', urllib.parse.urljoin(self.base_url, 'categories'), 8, self.icons['categories'], self.fanart, context_menu=context_menu)
        self.add_dir('Pornstars', urllib.parse.urljoin(self.base_url, 'pornstars'), 9, self.icons['pornstars'], self.fanart, context_menu=context_menu)
        self.add_dir('Channels', urllib.parse.urljoin(self.base_url, 'channels'), 10, self.icons['default'], self.fanart, context_menu=context_menu)

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

        if not url or url == "BOOTSTRAP" or url.rstrip('/') == self.base_url:
            url = self.build_tnaflix_url()

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
        context_menu = self.get_global_context_menu(current_url)

        pattern = re.compile(
            r'<a[^>]+class="[^"]*thumb[^"]*"[^>]+href="([^"]+/video\d+)"[^>]*>.*?<img[^>]+src="([^"]+)".*?(?:video-duration[^>]*>([^<]+)<)?',
            re.DOTALL | re.IGNORECASE
        )
        matches = pattern.findall(content)

        for href, thumb, duration in matches:
            video_url = urllib.parse.urljoin(self.base_url, href)
            vid_id_m = re.search(r'video(\d+)', href)
            vid_id = vid_id_m.group(1) if vid_id_m else ""
            
            title_pattern = rf'video{vid_id}"[^>]*class="[^"]*video-title[^"]*"[^>]*>([^<]+)<' if vid_id else r'video-title[^>]*>([^<]+)<'
            title_match = re.search(title_pattern, content, re.IGNORECASE)
            title = html.unescape(title_match.group(1).strip()) if title_match else "TNAFlix Video"

            if thumb.startswith('/assets'):
                thumb = self.icons['default']
            elif not thumb.startswith('http'):
                thumb = 'https:' + thumb if thumb.startswith('//') else self.icons['default']

            video_items.append({
                'url': video_url,
                'thumb': thumb,
                'duration': duration.strip() if duration else '',
                'title': title
            })

        if not video_items:
            # Fallback legacy parser
            vid_blocks = re.findall(r'<div[^>]+data-vid="(\d+)"[^>]*>(.*?)</div>\s*</div>', content, re.DOTALL | re.IGNORECASE)
            for vid_id, block in vid_blocks:
                url_match = re.search(r'href="(/[^"]+/video\d+|https://www\.tnaflix\.com/[^"]+/video\d+)"', block)
                if not url_match: continue
                v_url = urllib.parse.urljoin(self.base_url, url_match.group(1))
                t_match = re.search(r'alt="([^"]+)"', block)
                v_title = html.unescape(t_match.group(1).strip()) if t_match else f"Video {vid_id}"
                dur_m = re.search(r'video-duration[^>]*>([^<]+)<', block)
                v_dur = dur_m.group(1).strip() if dur_m else ""
                thumb_m = re.search(r'src="([^"]+)"', block)
                v_thumb = thumb_m.group(1) if thumb_m else self.icons['default']

                video_items.append({
                    'url': v_url,
                    'thumb': v_thumb,
                    'duration': v_dur,
                    'title': v_title
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
                    except Exception:
                        pass
                
                self.add_link(display_name, item['url'], 4, item['thumb'], self.fanart, info_labels=info, context_menu=context_menu)

        self.logger.info(f"[TNAFlix] Rendered {len(seen_urls)} videos")
        
        # Next page
        next_page = re.search(r'<link[^>]+rel="next"[^>]+href="([^"]+)"', content, re.IGNORECASE)
        if not next_page:
            next_page = re.search(r'href="([^"]*\?page=(\d+)[^"]*)"[^>]*>\s*Next', content, re.I)
        if next_page:
            next_url = urllib.parse.urljoin(self.base_url, html.unescape(next_page.group(1)))
            self.add_dir('[COLOR blue]Next Page >>>>[/COLOR]', next_url, 2, self.icons['default'], self.fanart, context_menu=context_menu)

    def select_sort(self, original_url=None):
        dialog = xbmcgui.Dialog()
        idx = dialog.select("Select Sort...", self.sort_options, preselect=self.get_current_sort_idx())
        if idx != -1:
            self.addon.setSetting(self.setting_id_sort, str(idx))
            xbmc.executebuiltin(f'Container.Update({sys.argv[0]}?mode=2&url=BOOTSTRAP&website={self.name},replace)')

    def select_duration(self, original_url=None):
        dialog = xbmcgui.Dialog()
        idx = dialog.select("Select Duration...", self.duration_options, preselect=self.get_current_duration_idx())
        if idx != -1:
            self.addon.setSetting(self.setting_id_duration, str(idx))
            xbmc.executebuiltin(f'Container.Update({sys.argv[0]}?mode=2&url=BOOTSTRAP&website={self.name},replace)')

    def select_period(self, original_url=None):
        dialog = xbmcgui.Dialog()
        idx = dialog.select("Select Upload Period...", self.period_options, preselect=self.get_current_period_idx())
        if idx != -1:
            self.addon.setSetting(self.setting_id_period, str(idx))
            xbmc.executebuiltin(f'Container.Update({sys.argv[0]}?mode=2&url=BOOTSTRAP&website={self.name},replace)')

    def process_categories(self, url):
        content = self.make_request(url)
        if not content:
            self.notify_error("Failed to load categories")
            self.end_directory()
            return
        
        pattern = r'<a[^>]+href=["\'](https?://www\.tnaflix\.com/[a-z0-9-]+|/[a-z0-9-]+)["\'][^>]*>(.*?)</a>'
        matches = re.findall(pattern, content, re.DOTALL | re.IGNORECASE)
        context_menu = self.get_global_context_menu(url)

        skip_slugs = {'login', 'signup', 'categories', 'galleries', 'channels', 'pornstars', 'tags', 'dmca', 'cookies', 'text2257', 'content-protection', 'parental-control'}
        seen = set()

        for href, title in matches:
            clean_title = re.sub(r'<[^>]+>', ' ', title).strip()
            slug = href.split('/')[-1]
            if slug not in skip_slugs and clean_title and href not in seen:
                seen.add(href)
                cat_url = urllib.parse.urljoin(self.base_url, href)
                self.add_dir(html.unescape(clean_title), cat_url, 2, self.icons['categories'], self.fanart, context_menu=context_menu)
        
        self.end_directory()

    def process_pornstars(self, url):
        content = self.make_request(url)
        if not content:
            self.notify_error("Failed to load pornstars")
            self.end_directory()
            return
        
        pattern = r'<a[^>]+href=["\'](https?://www\.tnaflix\.com/[a-z0-9-]+|/[a-z0-9-]+)["\'][^>]*>(.*?)</a>'
        matches = re.findall(pattern, content, re.DOTALL | re.IGNORECASE)
        context_menu = self.get_global_context_menu(url)

        skip_slugs = {'login', 'signup', 'categories', 'galleries', 'channels', 'pornstars', 'tags', 'dmca', 'cookies', 'text2257', 'content-protection', 'parental-control'}
        seen = set()

        for href, title in matches:
            clean_title = re.sub(r'<[^>]+>', ' ', title).strip()
            slug = href.split('/')[-1]
            if slug not in skip_slugs and clean_title and href not in seen:
                seen.add(href)
                star_url = urllib.parse.urljoin(self.base_url, href)
                self.add_dir(html.unescape(clean_title), star_url, 2, self.icons['pornstars'], self.fanart, context_menu=context_menu)
        
        self.end_directory()

    def process_channels(self, url):
        content = self.make_request(url)
        if not content:
            self.notify_error("Failed to load channels")
            self.end_directory()
            return
        
        pattern = r'<a[^>]+href=["\'](https?://www\.tnaflix\.com/[a-z0-9-]+|/[a-z0-9-]+)["\'][^>]*>(.*?)</a>'
        matches = re.findall(pattern, content, re.DOTALL | re.IGNORECASE)
        context_menu = self.get_global_context_menu(url)

        skip_slugs = {'login', 'signup', 'categories', 'galleries', 'channels', 'pornstars', 'tags', 'dmca', 'cookies', 'text2257', 'content-protection', 'parental-control'}
        seen = set()

        for href, title in matches:
            clean_title = re.sub(r'<[^>]+>', ' ', title).strip()
            slug = href.split('/')[-1]
            if slug not in skip_slugs and clean_title and href not in seen:
                seen.add(href)
                ch_url = urllib.parse.urljoin(self.base_url, href)
                self.add_dir(html.unescape(clean_title), ch_url, 2, self.icons['default'], self.fanart, context_menu=context_menu)
        
        self.end_directory()

    def play_video(self, url):
        headers = {'Referer': self.base_url}
        content = self.make_request(url, headers=headers)
        if not content:
            return self.notify_error("Failed to load video page")

        video_file = None

        # 1. Check legacy flashvars / XML config
        config_match = re.search(r'flashvars\.config\s*=\s*["\']([^"\']+)["\']', content)
        if not config_match:
            config_match = re.search(r'config:\s*["\']([^"\']+)["\']', content)

        if config_match:
            cfg_url = config_match.group(1)
            cfg_url = html.unescape(cfg_url)
            if not cfg_url.startswith('http'):
                cfg_url = urllib.parse.urljoin(url, cfg_url)
            cfg_content = self.make_request(cfg_url, headers=headers)
            if cfg_content:
                file_match = re.search(r'<videoLink>([^<]+)</videoLink>', cfg_content)
                if file_match:
                    video_file = file_match.group(1)

        # 2. Check HTML5 <source> tag
        if not video_file:
            video_match = re.search(r'<source[^>]+src="([^"]+\.mp4[^"]*)"', content)
            if video_match:
                video_file = video_match.group(1)

        # 3. Check direct MP4 stream links embedded in JS / JSON (excluding preview trailers)
        if not video_file:
            mp4_candidates = re.findall(r'https?://[^\s"\'<>]+\.mp4[^\s"\'<>]*', content)
            valid_candidates = [html.unescape(u) for u in mp4_candidates if 'trailer.mp4' not in u.lower()]
            if valid_candidates:
                def qual_score(u):
                    if '1080p' in u: return 5
                    if '720p' in u: return 4
                    if '480p' in u: return 3
                    if '360p' in u: return 2
                    if '240p' in u: return 1
                    return 0
                valid_candidates.sort(key=qual_score, reverse=True)
                video_file = valid_candidates[0]

        if video_file:
            video_file = html.unescape(video_file)
            if "|" not in video_file:
                video_file += "|User-Agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64)&Referer=https://www.tnaflix.com/"
            item = xbmcgui.ListItem(path=video_file)
            item.setProperty('IsPlayable', 'true')
            item.setMimeType('video/mp4')
            xbmcplugin.setResolvedUrl(self.addon_handle, True, item)
        else:
            self.notify_error("Stream URL not found")

    def search(self, query):
        if query:
            search_url = self.build_tnaflix_url(query=query)
            self.process_content(search_url)
        else:
            self.end_directory()
