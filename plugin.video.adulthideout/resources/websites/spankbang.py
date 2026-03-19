#!/usr/bin/env python

import re
import sys
import urllib.parse
import urllib.request
import http.cookiejar
import xbmc
import xbmcgui
import xbmcplugin
import html
from resources.lib.base_website import BaseWebsite

class Spankbang(BaseWebsite):
    def __init__(self, addon_handle):
        super().__init__(
            name='spankbang',
            base_url='https://spankbang.com/',
            search_url='https://spankbang.com/s/{}/',
            addon_handle=addon_handle
        )
        self.sort_options = ["Recommended", "Trending", "Upcoming", "New", "Popular"]
        self.sort_paths = {
            "Recommended": "/", "Trending": "trending_videos/", "Upcoming": "upcoming/",
            "New": "new_videos/", "Popular": "most_popular/"
        }
        
        self.quality_options = ["All", "720p", "1080p", "4k"]
        self.quality_params = {"All": "", "720p": "hd", "1080p": "fhd", "4k": "uhd"}

        self.duration_options = ["All", "10+ min", "20+ min", "40+ min"]
        self.duration_params = {"All": "", "10+ min": "10", "20+ min": "20", "40+ min": "40"}
        
        self.orientation_options = ["Straight", "Gay", "Transsexual"]
        self.orientation_paths = {"Straight": "straight", "Gay": "gay", "Transsexual": "transexual"}
        
        self.model_sort_options = ["Trending", "Alphabetical"]
        self.model_sort_paths = {"Trending": "pornstars", "Alphabetical": "pornstars_alphabet"}
        
        self.cookie_jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cookie_jar))
        self.opener.addheaders = [
            ('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36'),
            ('Accept', 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8'),
            ('Accept-Language', 'en-US,en;q=0.9')
        ]
        
        self._set_orientation_cookie()

    def _get_html(self, url):
        try:
            with self.opener.open(url, timeout=15) as response:
                return response.read().decode('utf-8', errors='ignore')
        except Exception as e:
            self.logger.error(f"Fehler beim Abrufen der URL {url}: {e}")
            return ""

    def _set_orientation_cookie(self):
        try:
            orientation_idx = int(self.addon.getSetting('spankbang_orientation') or '0')
            if not (0 <= orientation_idx < len(self.orientation_options)):
                orientation_idx = 0
            
            orientation_key = self.orientation_options[orientation_idx]
            orientation_path = self.orientation_paths[orientation_key]
            
            cookie_url = urllib.parse.urljoin(self.base_url, f'sex_version/{orientation_path}')
            self._get_html(cookie_url)
        except Exception as e:
            self.logger.error(f"Failed to set orientation cookie: {e}")

    def _build_url(self, base_path="/"):
        params = {}
        
        quality_setting = self.addon.getSetting('spankbang_quality') or '0'
        try:
            quality_idx = int(quality_setting)
        except ValueError:
            try: quality_idx = self.quality_options.index(quality_setting)
            except (ValueError, IndexError): quality_idx = 0
        
        if 0 <= quality_idx < len(self.quality_options):
            quality_key = self.quality_options[quality_idx]
            if self.quality_params.get(quality_key):
                params['q'] = self.quality_params[quality_key]

        duration_setting = self.addon.getSetting('spankbang_duration') or '0'
        try:
            duration_idx = int(duration_setting)
        except ValueError:
            try: duration_idx = self.duration_options.index(duration_setting)
            except (ValueError, IndexError): duration_idx = 0
        
        if 0 <= duration_idx < len(self.duration_options):
            duration_key = self.duration_options[duration_idx]
            if self.duration_params.get(duration_key):
                params['d'] = self.duration_params[duration_key]
        
        url_parts = urllib.parse.urlparse(base_path)
        original_params = urllib.parse.parse_qs(url_parts.query)
        original_params.update(params)
        
        final_query = urllib.parse.urlencode(original_params, doseq=True)
        full_url = urllib.parse.urljoin(self.base_url, url_parts.path)
        
        return f"{full_url}?{final_query}" if final_query else full_url
        
    def get_start_url_and_label(self):
        sort_idx_str = self.addon.getSetting(f"{self.name}_sort_by") or '0'
        try:
            sort_idx = int(sort_idx_str)
        except ValueError:
            try: sort_idx = self.sort_options.index(sort_idx_str)
            except (ValueError, IndexError): sort_idx = 0
        
        sort_option = self.sort_options[sort_idx] if 0 <= sort_idx < len(self.sort_options) else self.sort_options[0]
        sort_path = self.sort_paths.get(sort_option, "/")
        
        url = self._build_url(sort_path)

        filter_labels = [sort_option]
        
        orientation_idx = int(self.addon.getSetting('spankbang_orientation') or '0')
        if orientation_idx > 0 and orientation_idx < len(self.orientation_options):
            filter_labels.append(self.orientation_options[orientation_idx])
            
        quality_idx_str = self.addon.getSetting('spankbang_quality') or '0'
        try: quality_idx = int(quality_idx_str)
        except: quality_idx = 0
        if quality_idx > 0 and quality_idx < len(self.quality_options):
            filter_labels.append(self.quality_options[quality_idx])
        
        duration_idx_str = self.addon.getSetting('spankbang_duration') or '0'
        try: duration_idx = int(duration_idx_str)
        except: duration_idx = 0
        if duration_idx > 0 and duration_idx < len(self.duration_options):
            filter_labels.append(self.duration_options[duration_idx])

        label = f"{self.name.capitalize()} [COLOR yellow]({' / '.join(filter_labels)})[/COLOR]"
        return url, label

    def _refresh_container_with_new_filters(self, original_url):
        new_url = self._build_url(original_url)
        xbmc.executebuiltin(f"Container.Update({sys.argv[0]}?mode=2&url={urllib.parse.quote_plus(new_url)}&website={self.name},replace)")
    
    def select_orientation(self, original_url=None):
        dialog = xbmcgui.Dialog()
        current_idx = int(self.addon.getSetting('spankbang_orientation') or '0')
        idx = dialog.select("Select Orientation", self.orientation_options, preselect=current_idx)
        if idx != -1:
            self.addon.setSetting('spankbang_orientation', str(idx))
            self.notify_info("Orientation set. Reloading...")
            xbmc.executebuiltin('Container.Refresh')

    def select_quality(self, original_url=None):
        dialog = xbmcgui.Dialog()
        current_idx = int(self.addon.getSetting('spankbang_quality') or '0')
        idx = dialog.select("Select Quality", self.quality_options, preselect=current_idx)
        if idx != -1:
            self.addon.setSetting('spankbang_quality', str(idx))
            self._refresh_container_with_new_filters(original_url)

    def select_duration(self, original_url=None):
        dialog = xbmcgui.Dialog()
        current_idx = int(self.addon.getSetting('spankbang_duration') or '0')
        idx = dialog.select("Select Duration", self.duration_options, preselect=current_idx)
        if idx != -1:
            self.addon.setSetting('spankbang_duration', str(idx))
            self._refresh_container_with_new_filters(original_url)

    def reset_filters(self, original_url=None):
        try:
            new_sort_idx = self.sort_options.index("New")
        except ValueError:
            new_sort_idx = 3

        self.addon.setSetting('spankbang_sort_by', str(new_sort_idx))
        self.addon.setSetting('spankbang_quality', '0')
        self.addon.setSetting('spankbang_duration', '0')
        self.addon.setSetting('spankbang_orientation', '0')
        
        self.notify_info("Filters have been reset.")
        
        new_sort_path = self.sort_paths.get("New", "/")
        new_url = urllib.parse.urljoin(self.base_url, new_sort_path)
        xbmc.executebuiltin(f"Container.Update({sys.argv[0]}?mode=2&url={urllib.parse.quote_plus(new_url)}&website={self.name},replace)")

    def process_content(self, url):
        self.list_videos(url)

    def list_videos(self, url):
        context_menu_items = [
            ('Sort by...', f'RunPlugin({sys.argv[0]}?mode=7&action=select_sort&website={self.name}&original_url={urllib.parse.quote_plus(url)})'),
            ('Select Orientation...', f'RunPlugin({sys.argv[0]}?mode=7&action=select_orientation&website={self.name}&original_url={urllib.parse.quote_plus(url)})'),
            ('Select Quality...', f'RunPlugin({sys.argv[0]}?mode=7&action=select_quality&website={self.name}&original_url={urllib.parse.quote_plus(url)})'),
            ('Select Duration...', f'RunPlugin({sys.argv[0]}?mode=7&action=select_duration&website={self.name}&original_url={urllib.parse.quote_plus(url)})')
        ]
        
        quality_idx_str = self.addon.getSetting('spankbang_quality') or '0'
        try: quality_idx = int(quality_idx_str)
        except: quality_idx = 0
        
        duration_idx_str = self.addon.getSetting('spankbang_duration') or '0'
        try: duration_idx = int(duration_idx_str)
        except: duration_idx = 0

        orientation_idx = int(self.addon.getSetting('spankbang_orientation') or '0')
        
        if quality_idx > 0 or duration_idx > 0 or orientation_idx > 0:
            context_menu_items.append(
                ('[COLOR yellow]Reset Filters[/COLOR]', f'RunPlugin({sys.argv[0]}?mode=7&action=reset_filters&website={self.name}&original_url={urllib.parse.quote_plus(url)})')
            )
        
        self.add_dir('[COLOR blue]Search[/COLOR]', '', 5, self.icons.get('search'), context_menu=context_menu_items)
        self.add_dir('[COLOR yellow]Tags[/COLOR]', urllib.parse.urljoin(self.base_url, 'tags'), 8, self.icons.get('categories'), context_menu=context_menu_items)
        model_sort_idx = int(self.addon.getSetting('spankbang_model_sort') or '0')
        if not (0 <= model_sort_idx < len(self.model_sort_options)):
            model_sort_idx = 0
        model_sort_key = self.model_sort_options[model_sort_idx]
        model_sort_path = self.model_sort_paths.get(model_sort_key, 'pornstars')
        
        models_context = [
            ('[COLOR yellow]Sort Models[/COLOR]', f'RunPlugin({sys.argv[0]}?mode=7&action=select_model_sort&website={self.name})')
        ]
        self.add_dir('[COLOR yellow]Models[/COLOR]', urllib.parse.urljoin(self.base_url, model_sort_path), 9, self.icons.get('pornstars'), context_menu=models_context)

        final_url = self._build_url(url)
        html_content = self._get_html(final_url)
        
        if not html_content:
            self.notify_error("Could not load page content.")
            self.end_directory()
            return

        main_content_match = re.search(r'<main[^>]+data-testid="main"[^>]*>(.*)', html_content, re.DOTALL)
        if main_content_match:
            html_content = main_content_match.group(1)
            self.logger.info("Spankbang: Extracted main content area for video parsing")

        video_chunks = re.split(r'<div[^>]+class="[^"]*video-item[^"]*"[^>]*>', html_content)
        
        if len(video_chunks) < 2:
            video_chunks = html_content.split('data-testid="video-item"')
        
        if len(video_chunks) < 2:
            video_chunks = re.split(r'<a[^>]+class="[^"]*thumb[^"]*"[^>]+href="[^"]+/video/', html_content)
        
        if len(video_chunks) < 2:
            self.notify_info("No videos found on this page.")
            self.end_directory()
            return

        for chunk in video_chunks[1:]:
            try:
                href_match = re.search(r'href="([^"]+/video/[^"]+)"', chunk) or \
                             re.search(r'href="(/[^"]+)"[^>]*class="[^"]*thumb', chunk)
                if not href_match: continue
                video_url = urllib.parse.urljoin(self.base_url, href_match.group(1))
                
                title_match = re.search(r'alt="([^"]+)"', chunk) or \
                              re.search(r'title="([^"]+)"', chunk) or \
                              re.search(r'<h\d[^>]*>([^<]+)</h\d>', chunk)
                title = html.unescape(title_match.group(1).strip()) if title_match else 'Untitled Video'
                
                img_match = re.search(r'<img[^>]+src="(https?://tbi\.sb-cd\.com[^"]+)"', chunk) or \
                            re.search(r'<img[^>]+src="(https?://[^"]+\.(?:jpg|webp|png))"', chunk) or \
                            re.search(r'data-src="(https?://tbi\.sb-cd\.com[^"]+)"', chunk) or \
                            re.search(r'data-src="([^"]+\.(?:jpg|webp|png))"', chunk)
                
                if img_match:
                    img = img_match.group(1)
                    if img.startswith('//'):
                        img = 'https:' + img
                else:
                    img = self.icon

                duration_match = re.search(r'data-testid="video-item-length"[^>]*>\s*([^<]+)\s*<', chunk) or \
                                 re.search(r'class="[^"]*length[^"]*"[^>]*>\s*([^<]+)\s*<', chunk) or \
                                 re.search(r'<span[^>]*>\s*(\d+:\d+)\s*</span>', chunk)
                duration_str = duration_match.group(1).strip() if duration_match else ''
                
                info_labels = {'title': title, 'mediatype': 'video'}
                if duration_str:
                    info_labels['duration'] = duration_str.replace('m', '') + ':00'

                self.add_link(title, video_url, 4, img, self.fanart, info_labels=info_labels, context_menu=context_menu_items)
            except Exception as e:
                self.logger.warning(f"Error parsing a video item: {e}")

        next_page_match = re.search(r'class="next"><a href="([^"]+)"', html_content)
        if next_page_match:
            next_url_path = next_page_match.group(1)
            next_url_base = urllib.parse.urljoin(final_url, next_url_path)
            next_url = self._build_url(next_url_base)
            self.add_dir('[COLOR blue]Next Page >>[/COLOR]', next_url, 2)

        self.end_directory()
        
    def process_categories(self, url):
        html_content = self._get_html(url)
        if not html_content:
            self.notify_error("Could not load tags page.")
            self.end_directory()
            return
        
        top_tags_block_match = re.search(r'<h1[^>]*>.*?Top Tags.*?</h1>.*?<ul class="top_tags_list">(.*?)</ul>', html_content, re.DOTALL)
        if top_tags_block_match:
            tag_matches = re.findall(r'<li><a href="([^"]+)" class="keyword">([^<]+)</a></li>', top_tags_block_match.group(1))
            for tag_url, tag_name in sorted(tag_matches, key=lambda x: x[1]):
                self.add_dir(html.unescape(tag_name.strip().title()), urllib.parse.urljoin(self.base_url, tag_url), 2, self.icons.get('categories'))
        else:
            self.notify_info("No 'Top Tags' list could be found.")
        self.end_directory()

    def process_actresses_list(self, url):
        html_content = self._get_html(url)
        if not html_content:
            self.notify_error("Could not load models page.")
            self.end_directory()
            return
        
        main_content_match = re.search(r'<main[^>]+data-testid="main"[^>]*>(.*)', html_content, re.DOTALL)
        if main_content_match:
            html_content = main_content_match.group(1)
        
        sort_context = [
            ('[COLOR yellow]Sort Models[/COLOR]', f'RunPlugin({sys.argv[0]}?mode=7&action=select_model_sort&website={self.name})')
        ]
        
        model_list = []
        seen_urls = set()
        is_alphabetical = 'pornstars_alphabet' in url
        
        if is_alphabetical:
            letter_matches = re.findall(r'href="(/pornstars_alphabet/[a-z])"[^>]+data-testid="alphabet-letter"', html_content)
            if letter_matches and '/pornstars_alphabet/' in url and len(url.split('/pornstars_alphabet/')) > 1:
                pass
            elif letter_matches:
                for letter_url in letter_matches:
                    letter = letter_url.split('/')[-1].upper()
                    self.add_dir(f'[COLOR cyan]Letter {letter}[/COLOR]', urllib.parse.urljoin(self.base_url, letter_url), 9, self.icons.get('categories'), context_menu=sort_context)
            
            text_pattern = r'data-testid="pornstar-link-item"[^>]*>.*?href="(/[a-z0-9]+/pornstar/[^"]+/)"[^>]*>([^<]+)'
            for match in re.finditer(text_pattern, html_content, re.DOTALL):
                href, name_text = match.groups()
                name = name_text.strip()
                if href not in seen_urls and name:
                    seen_urls.add(href)
                    model_list.append((href, self.icon, name))
        else:
            card_pattern = r'<div[^>]+data-testid="(?:trending|hottest)-models"[^>]*>.*?href="([^"]+/pornstar/[^"]+)".*?data-src="([^"]+)"[^>]+alt="([^"]+)"'
            
            for match in re.finditer(card_pattern, html_content, re.DOTALL):
                href, thumb, name = match.groups()
                if href not in seen_urls:
                    seen_urls.add(href)
                    model_list.append((href, thumb, name))
            
            if not model_list:
                ps_pattern = r'<a[^>]+class="ps[^"]*"[^>]+href="(/[^"]+/pornstar/[^"]+/)"[^>]*>.*?data-src="([^"]+)"[^>]+alt="([^"]+)"'
                for match in re.finditer(ps_pattern, html_content, re.DOTALL):
                    href, thumb, name = match.groups()
                    if href not in seen_urls:
                        seen_urls.add(href)
                        model_list.append((href, thumb, name))
        
        if not model_list and not is_alphabetical:
            self.notify_info("No models found on this page.")
            self.end_directory()
            return
        
        self.logger.info(f"Spankbang Models: Found {len(model_list)} models (alphabetical={is_alphabetical})")

        if is_alphabetical:
            for model_url, thumb_url, model_name in model_list:
                thumb = 'https:' + thumb_url if thumb_url.startswith('//') else thumb_url
                self.add_dir(html.unescape(model_name.strip()), urllib.parse.urljoin(self.base_url, model_url), 2, thumb, context_menu=sort_context)
        else:
            for model_url, thumb_url, model_name in model_list:
                thumb = 'https:' + thumb_url if thumb_url.startswith('//') else thumb_url
                self.add_dir(html.unescape(model_name.strip()), urllib.parse.urljoin(self.base_url, model_url), 2, thumb, context_menu=sort_context)
            
        next_page_match = re.search(r'class="next">\s*<a\s*href="([^"]+)"', html_content)
        if next_page_match:
            self.add_dir('[COLOR blue]Next Page >>[/COLOR]', urllib.parse.urljoin(url, next_page_match.group(1)), 9, context_menu=sort_context)
        self.end_directory()

    def play_video(self, url):
        if ' ' in url and '/video/' in url:
            url = url.replace(' ', '+')
        
        self.logger.info(f"Spankbang: Playing video URL: {url}")
        
        html_content = self._get_html(url)
        if not html_content:
            self.notify_error("Failed to load video page.")
            return

        best_url = None
        
        stream_data_match = re.search(r"var\s+stream_data\s*=\s*\{(.{1,5000})\}", html_content, re.DOTALL)
        if stream_data_match:
            stream_data_str = stream_data_match.group(1)
            self.logger.info(f"Spankbang: Found stream_data: {stream_data_str[:300]}")
            
            m3u8_match = re.search(r"'m3u8'\s*:\s*\[\s*'([^']+)'", stream_data_str)
            if m3u8_match:
                best_url = m3u8_match.group(1)
                self.logger.info(f"Spankbang: Found m3u8: {best_url}")
            
            if not best_url:
                qualities = ['1080p', '720p', '480p', '360p', '240p']
                for quality in qualities:
                    quality_match = re.search(rf"'{quality}'\s*:\s*\[\s*'([^']+)'", stream_data_str)
                    if quality_match:
                        best_url = quality_match.group(1)
                        self.logger.info(f"Spankbang: Found {quality}: {best_url}")
                        break
        
        if not best_url:
            hls_url_match = re.search(r"['\"]?(https?://[^'\"\\s]+\.m3u8[^'\"\\s]*)['\"]?", html_content)
            if hls_url_match:
                best_url = hls_url_match.group(1)
                self.logger.info(f"Spankbang: Found direct m3u8: {best_url}")
        
        if not best_url:
            video_src_match = re.search(r'<video[^>]+src="([^"]+)"', html_content)
            if video_src_match:
                best_url = video_src_match.group(1)
                self.logger.info(f"Spankbang: Found video src: {best_url}")
        
        if not best_url:
            mp4s = re.findall(r'"(https?://[^"]+(?:vdownload|cdn|sb-cd)[^"]+\.mp4[^"]*)"', html_content)
            if not mp4s:
                mp4s = re.findall(r'"(https?://[^"]+\d{3,4}p\.mp4[^"]*)"', html_content)
            if mp4s:
                def get_quality(u):
                    match = re.search(r'(\d{3,4})p', u)
                    return int(match.group(1)) if match else 0
                best_url = sorted(list(set(mp4s)), key=get_quality, reverse=True)[0]
                self.logger.info(f"Spankbang: Found mp4: {best_url}")

        if not best_url:
            self.notify_error("No playable video streams found.")
            return
        
        best_url = best_url.replace('\\/', '/').replace('\\u0026', '&')
            
        play_item = xbmcgui.ListItem(path=best_url)
        
        if '.m3u8' in best_url:
            play_item.setProperty('inputstream', 'inputstream.adaptive')
            play_item.setProperty('inputstream.adaptive.manifest_type', 'hls')
        
        xbmcplugin.setResolvedUrl(self.addon_handle, True, listitem=play_item)

    def select_model_sort(self):
        """Show dialog to select model sorting order."""
        current_sort_idx = int(self.addon.getSetting('spankbang_model_sort') or '0')
        
        dialog = xbmcgui.Dialog()
        selected = dialog.select('Sort Models By', self.model_sort_options, preselect=current_sort_idx)
        
        if selected >= 0:
            self.addon.setSetting('spankbang_model_sort', str(selected))
            sort_key = self.model_sort_options[selected]
            sort_path = self.model_sort_paths.get(sort_key, 'pornstars')
            self.notify_info(f"Models sorted by: {sort_key}")
            
            new_url = urllib.parse.urljoin(self.base_url, sort_path)
            xbmc.executebuiltin(f'Container.Update({sys.argv[0]}?mode=9&url={urllib.parse.quote_plus(new_url)}&website={self.name})')