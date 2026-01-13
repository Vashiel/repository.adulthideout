#!/usr/bin/env python
# -*- coding: utf-8 -*-


import re
import sys
import os
import hashlib
import json
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
import xbmc
import xbmcgui
import xbmcplugin
import xbmcvfs
import xbmcaddon
from resources.lib.base_website import BaseWebsite

try:
    addon_path = xbmcaddon.Addon().getAddonInfo('path')
    vendor_path = os.path.join(addon_path, 'resources', 'lib', 'vendor')
    if vendor_path not in sys.path:
        sys.path.insert(0, vendor_path)
    import cloudscraper
    HAS_CLOUDSCRAPER = True
except Exception:
    HAS_CLOUDSCRAPER = False
    import requests

try:
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except:
    pass

class XHamster(BaseWebsite):
    def __init__(self, addon_handle):
        super().__init__(
            name='xhamster',
            base_url='https://xhamster.com',
            search_url='https://xhamster.com/search/{}',
            addon_handle=addon_handle
        )
        self.categories_url = 'https://xhamster.com/categories'
        
        if HAS_CLOUDSCRAPER:
            self.session = cloudscraper.create_scraper(browser={'custom': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'})
        else:
            self.session = requests.Session()
            self.session.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
            
        self.session.headers.update({
            'Referer': self.base_url + '/',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8'
        })

        self._thumb_cache_dir = self._initialize_thumb_cache()
        
        self.content_options = ['Straight', 'Gay', 'Shemale']
        self.content_paths = {'Straight': '', 'Gay': 'gay/', 'Shemale': 'shemale/'}
        
        self.sort_options = ['Trending', 'Newest', 'Top Rated', 'Most Popular (Weekly)', 'Most Popular (Monthly)']
        self.sort_paths = {
            'Trending': '',
            'Newest': 'newest/',
            'Top Rated': 'best/',
            'Most Popular (Weekly)': 'best/weekly/',
            'Most Popular (Monthly)': 'best/monthly/'
        }
        
        self.duration_options = ['All', '0-2 min', '2-5 min', '5-10 min', '10-30 min', '30+ min', 'Full Video']
        self.duration_data = {
            'All': ('', ''),
            '0-2 min': ('', 'max-duration=2'),
            '2-5 min': ('', 'min-duration=2&max-duration=5'),
            '5-10 min': ('', 'min-duration=5&max-duration=10'),
            '10-30 min': ('', 'min-duration=10&max-duration=30'),
            '30+ min': ('', 'min-duration=30'),
            'Full Video': ('full-length/', '')
        }
        
        self.quality_options = ['All', '720p+', '1080p+', '4K']
        self.quality_data = {
            'All': ('', ''),
            '720p+': ('hd/', ''),
            '1080p+': ('hd/', 'quality=1080p'),
            '4K': ('4k/', '')
        }

    def _initialize_thumb_cache(self):
        addon_profile = xbmcvfs.translatePath(xbmcaddon.Addon().getAddonInfo('profile'))
        thumb_dir = os.path.join(addon_profile, 'thumbs', self.name)
        if not xbmcvfs.exists(thumb_dir):
            xbmcvfs.mkdirs(thumb_dir)
        self._cleanup_cache(thumb_dir, max_age_days=3, max_size_mb=10)
        return thumb_dir

    def _maybe_cleanup_cache(self, cache_dir):
        """Only run cleanup if last cleanup was more than 1 hour ago."""
        marker_file = os.path.join(cache_dir, '.last_cleanup')
        try:
            if xbmcvfs.exists(marker_file):
                stat = os.stat(marker_file)
                if time.time() - stat.st_mtime < 3600:  # Less than 1 hour
                    return  # Skip cleanup
            
            self._cleanup_cache(cache_dir, max_age_days=3, max_size_mb=10)
            
            with xbmcvfs.File(marker_file, 'w') as f:
                f.write(str(time.time()))
        except:
            pass

    def _cleanup_cache(self, cache_dir, max_age_days=3, max_size_mb=10):
        """Clean cache: delete files older than max_age_days and limit total size."""
        try:
            files = []
            now = time.time()
            max_age_seconds = max_age_days * 86400
            
            dirs, filenames = xbmcvfs.listdir(cache_dir)
            for filename in filenames:
                if filename.startswith('.'):  # Skip marker files
                    continue
                filepath = os.path.join(cache_dir, filename)
                try:
                    stat = os.stat(filepath)
                    age = now - stat.st_mtime
                    
                    if age > max_age_seconds:
                        xbmcvfs.delete(filepath)
                    else:
                        files.append((filepath, stat.st_mtime, stat.st_size))
                except:
                    pass
            
            total_size = sum(f[2] for f in files)
            max_size_bytes = max_size_mb * 1024 * 1024
            
            if total_size > max_size_bytes:
                files.sort(key=lambda x: x[1])
                
                while total_size > max_size_bytes and files:
                    oldest = files.pop(0)
                    xbmcvfs.delete(oldest[0])
                    total_size -= oldest[2]
        except:
            pass  # Silent fail for cleanup

    def _sanitize_webp(self, data):
        """
        Convert Extended WebP to Simple WebP by stripping VP8X and all metadata.
        Returns None if data is not a valid WebP or conversion fails.
        """
        try:
            if len(data) < 12 or data[:4] != b'RIFF' or data[8:12] != b'WEBP':
                return None

            pos = 12
            image_chunk = None
            
            while pos < len(data):
                chunk_id = data[pos:pos+4]
                if len(chunk_id) < 4: break
                
                try:
                    chunk_size = int.from_bytes(data[pos+4:pos+8], 'little')
                except:
                    break
                    
                chunk_total_size = chunk_size + 8
                if chunk_size % 2 == 1:
                    chunk_total_size += 1
                
                if chunk_id in (b'VP8 ', b'VP8L'):
                    image_chunk = data[pos:pos+chunk_total_size]
                    break 
                
                pos += chunk_total_size
                
            if not image_chunk:
                return None

            file_size = len(image_chunk) + 4 # 'WEBP' is 4 bytes
            header = b'RIFF' + file_size.to_bytes(4, 'little') + b'WEBP'
            return header + image_chunk
            
        except Exception as e:
            self.logger.error(f"WebP Sanitizer failed: {e}")
            return None

    def _format_thumb_url(self, url):
        if not url:
            return None
        
        url = str(url).strip()
        if not url.startswith('http'):
            if url.startswith('//'):
                url = 'https:' + url
            else:
                return None
        
        if any(ext in url.lower() for ext in ['.m3u8', '.mp4', '.ts']):
            return None

        if ',webp' in url:
            if url.lower().endswith(('.jpg', '.jpeg')):
                 base = url[:-4] if url.lower().endswith('.jpg') else url[:-5]
                 url = base + '.webp'
            elif '.jpg.' in url:
                 url = url.replace('.jpg.', '.webp.', 1)
        
        return url

    def _download_and_validate_thumb(self, url, referer=None):
        if not url:
            return None

        try:
            hashed_url = hashlib.md5(url.encode('utf-8')).hexdigest()
            
            valid_signatures = {
                b'\xFF\xD8\xFF': '.jpg',
                b'\x89PNG\r\n\x1a\n': '.png',
                b'GIF89a': '.gif',
                b'GIF87a': '.gif',
                b'BM': '.bmp',
                b'RIFF': '.webp'
            }

            for ext in set(valid_signatures.values()):
                local_path = os.path.join(self._thumb_cache_dir, hashed_url + ext)
                if xbmcvfs.exists(local_path):
                    return local_path

            response = self.session.get(url, timeout=8)
            
            if response.status_code in (401, 403) and referer:
                response = self.session.get(url, headers={'Referer': referer}, timeout=6)

            if response.status_code != 200:
                return None

            content = response.content
            
            if len(content) < 2048: 
                return None
            
            if content.startswith(b'RIFF') and b'WEBP' in content[:12]:
                sanitized = self._sanitize_webp(content)
                if sanitized:
                    content = sanitized
                else:
                    return None

            file_ext = None
            for signature, ext in valid_signatures.items():
                if content.startswith(signature):
                    file_ext = ext
                    break
            
            if not file_ext:
                return None
            
            local_path = os.path.join(self._thumb_cache_dir, hashed_url + file_ext)
            with xbmcvfs.File(local_path, 'wb') as f:
                f.write(content)
            return local_path

        except Exception as e:
            self.logger.error(f"Failed to process thumb {url}: {e}")
            return None

    def make_request(self, url):
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            return response.text
        except Exception as e:
            self.logger.error(f"Request failed: {e}")
            return ""

    def _select_generic(self, setting_id, options_list, title):
        current_setting = self.addon.getSetting(setting_id)
        try:
            preselect_idx = options_list.index(current_setting)
        except ValueError:
            preselect_idx = 0
        dialog = xbmcgui.Dialog()
        idx = dialog.select(title, options_list, preselect=preselect_idx)
        if idx != -1:
            self.addon.setSetting(setting_id, options_list[idx])
            xbmc.executebuiltin('Container.Refresh')

    def select_content_type(self, original_url=None):
        self._select_generic("xhamster_category", self.content_options, "Select Content Type...")

    def select_sort(self, original_url=None):
        self._select_generic("xhamster_sort_by", self.sort_options, "Sort by...")

    def select_duration(self, original_url=None):
        self._select_generic("xhamster_min_duration", self.duration_options, "Filter by Duration...")

    def select_quality(self, original_url=None):
        self._select_generic("xhamster_resolution", self.quality_options, "Filter by Quality...")

    def _build_filtered_url(self, page=1):
        content = self.addon.getSetting("xhamster_category") or self.content_options[0]
        sort = self.addon.getSetting("xhamster_sort_by") or self.sort_options[0]
        duration = self.addon.getSetting("xhamster_min_duration") or self.duration_options[0]
        quality = self.addon.getSetting("xhamster_resolution") or self.quality_options[0]
        
        content_path = self.content_paths.get(content, '')
        sort_path = self.sort_paths.get(sort, '')
        duration_path, duration_query = self.duration_data.get(duration, ('', ''))
        quality_path, quality_query = self.quality_data.get(quality, ('', ''))
        
        path_parts = [self.base_url, content_path, quality_path, duration_path, sort_path]
        if int(page) > 1:
            path_parts.append(str(page))
        
        final_url = "/".join(p.strip('/') for p in path_parts if p)
        if not urllib.parse.urlparse(final_url).path:
            final_url += '/'
        
        query_parts = [q for q in [quality_query, duration_query] if q]
        if query_parts:
            final_url += "?" + "&".join(query_parts)
        
        return final_url

    def process_content(self, url):
        parsed_url = urllib.parse.urlparse(url)
        path = parsed_url.path.strip('/')

        if path == 'categories':
            self.process_categories(url)
            return

        self.add_basic_dirs(url)
        
        if 'search' in path or ('categories' in path and path != 'categories'):
            request_url = url
        else:
            page = 1
            path_parts = path.split('/')
            if path_parts and path_parts[-1].isdigit():
                page = int(path_parts[-1])
            request_url = self._build_filtered_url(page=page)

        content = self.make_request(request_url)
        if not content:
            self.notify_error('Failed to fetch content')
            self.end_directory()
            return
        
        videos = []
        json_match = re.search(r'window\.initials\s*=\s*({.*?});</script>', content, re.DOTALL)
        if json_match:
            try:
                jdata = json.loads(json_match.group(1))
                video_paths = [
                    jdata.get('pagesCategoryComponent', {}).get('trendingVideoListProps', {}).get('videoThumbProps', []),
                    jdata.get('videoListProps', {}).get('videoThumbProps', []),
                    jdata.get('searchResult', {}).get('videoThumbProps', []),
                    jdata.get('layoutPage', {}).get('videoListProps', {}).get('videoThumbProps', []),
                    jdata.get('layoutPage', {}).get('trendingVideoListProps', {}).get('videoThumbProps', []),
                    jdata.get('layoutPage', {}).get('store', {}).get('videos', [])
                ]
                for vpath in video_paths:
                    if isinstance(vpath, list) and vpath:
                        videos.extend(vpath)
                        break
            except json.JSONDecodeError:
                pass

        if not videos:
            self.notify_info('No videos found.')
            self.end_directory()
            return

        video_data = []
        for video in videos:
            if video.get('isBlockedByGeo'):
                continue
            
            title = video.get('title', 'No Title')
            page_url = video.get('pageURL', '')
            if not page_url.startswith('http'):
                page_url = urllib.parse.urljoin(self.base_url, page_url)

            candidates = []
            
            imageURL = video.get('imageURL', '')
            thumbURL = video.get('thumbURL', '')
            
            if '/v2/' in str(imageURL): candidates.append(imageURL)
            if '/v2/' in str(thumbURL): candidates.append(thumbURL)
            if imageURL: candidates.append(imageURL)
            if thumbURL: candidates.append(thumbURL)
            
            thumbs = video.get('thumbs')
            if isinstance(thumbs, dict):
                 if thumbs.get('big'): candidates.append(thumbs.get('big'))
                 if thumbs.get('medium'): candidates.append(thumbs.get('medium'))
                 if thumbs.get('url'): candidates.append(thumbs.get('url'))
            elif isinstance(thumbs, str):
                candidates.append(thumbs)
                
            if video.get('staticThumb'): candidates.append(video.get('staticThumb'))
            if video.get('thumb'): candidates.append(video.get('thumb'))
            
            if video.get('previewThumbURL'): candidates.append(video.get('previewThumbURL'))
            if video.get('spriteURL'): candidates.append(video.get('spriteURL'))
            if video.get('landing', {}).get('logo'): candidates.append(video.get('landing', {}).get('logo'))
            if video.get('previewURL'): candidates.append(video.get('previewURL'))
            if video.get('preview'): candidates.append(video.get('preview'))

            seen = set()
            unique_candidates = []
            for c in candidates:
                if c and isinstance(c, str) and c not in seen:
                    seen.add(c)
                    unique_candidates.append(c)

            duration = video.get('duration', 0)
            try:
                duration = int(duration)
                duration_str = f'[COLOR yellow][{duration // 60}:{duration % 60:02d}][/COLOR]' if duration > 0 else ''
            except (TypeError, ValueError):
                duration_str = ''

            video_data.append({
                'title': title,
                'page_url': page_url,
                'candidates': unique_candidates,
                'duration_str': duration_str
            })

        def download_thumb_for_video(vdata):
            thumbnail = None
            for raw_thumb in vdata['candidates']:
                clean_thumb_url = self._format_thumb_url(raw_thumb)
                if clean_thumb_url and clean_thumb_url.startswith('http'):
                    potential_thumb = self._download_and_validate_thumb(clean_thumb_url, referer=vdata['page_url'])
                    if potential_thumb:
                        thumbnail = potential_thumb
                        break
            return (vdata, thumbnail)

        results = []
        with ThreadPoolExecutor(max_workers=15) as executor:
            futures = [executor.submit(download_thumb_for_video, vdata) for vdata in video_data]
            for future in as_completed(futures):
                try:
                    results.append(future.result())
                except:
                    pass

        results_dict = {r[0]['page_url']: r for r in results}
        for vdata in video_data:
            result = results_dict.get(vdata['page_url'])
            if result:
                thumbnail = result[1] if result[1] else self.icons['default']
            else:
                thumbnail = self.icons['default']

            context_menu = [
                ('Content Type...', f'RunPlugin({sys.argv[0]}?mode=7&action=select_content_type&website={self.name})'),
                ('Sort by...', f'RunPlugin({sys.argv[0]}?mode=7&action=select_sort&website={self.name})'),
                ('Filter by Duration...', f'RunPlugin({sys.argv[0]}?mode=7&action=select_duration&website={self.name})'),
                ('Filter by Quality...', f'RunPlugin({sys.argv[0]}?mode=7&action=select_quality&website={self.name})')
            ]

            display_title = f"{vdata['title']} {vdata['duration_str']}".strip()
            self.add_link(display_title, vdata['page_url'], 4, thumbnail, self.fanart, context_menu=context_menu)
        
        current_page_num = 1
        parsed_req_url = urllib.parse.urlparse(request_url)
        path_parts = parsed_req_url.path.strip('/').split('/')
        base_path_for_next = parsed_req_url.path
        
        if path_parts and path_parts[-1].isdigit():
            current_page_num = int(path_parts[-1])
            base_path_for_next = '/' + '/'.join(path_parts[:-1])
        
        next_page_num = current_page_num + 1
        next_page_path = base_path_for_next.strip('/') + '/' + str(next_page_num)
        next_page_url = urllib.parse.urljoin(self.base_url, next_page_path)
        
        if parsed_req_url.query:
            next_page_url += f"?{parsed_req_url.query}"
            
        self.add_dir('[COLOR blue]Next Page >>>>[/COLOR]', next_page_url, 2, self.icons['default'], self.fanart)
        self.end_directory()

    def add_basic_dirs(self, current_url):
        self.add_dir('[COLOR blue]Search[/COLOR]', '', 5, self.icons['search'], self.fanart)
        self.add_dir('Categories', self.categories_url, 2, self.icons['categories'], self.fanart)

    def process_categories(self, url):
        content = self.make_request(url)
        if not content:
            self.notify_error('Failed to load categories')
            self.end_directory()
            return
            
        categories_dict = {}
        json_match = re.search(r'window\.initials\s*=\s*({.*?});</script>', content, re.DOTALL)
        if json_match:
            try:
                jdata = json.loads(json_match.group(1))
                category_groups = [
                    jdata.get('layoutPage', {}).get('store', {}).get('popular', {}).get('trending', {}).get('items', []),
                ]
                assignable_groups = jdata.get('layoutPage', {}).get('store', {}).get('popular', {}).get('assignable', [])
                for group in assignable_groups:
                    if isinstance(group, dict) and 'items' in group:
                        category_groups.append(group.get('items', []))
                
                for group in category_groups:
                    for item in group:
                        if isinstance(item, dict) and 'url' in item and 'name' in item:
                            cat_url = item['url']
                            if 'categories' in cat_url:
                                raw_thumb = item.get('thumb', '') or item.get('thumbnail', '')
                                clean_url = self._format_thumb_url(raw_thumb)
                                
                                thumb = None
                                if clean_url and clean_url.startswith('http'):
                                    thumb = self._download_and_validate_thumb(clean_url)
                                
                                final_thumb = thumb if thumb else self.icons['categories']
                                categories_dict[cat_url] = (item['name'], final_thumb)
            except json.JSONDecodeError:
                pass
        
        if not categories_dict:
            self.notify_error('No categories found')
            self.end_directory()
            return
            
        for cat_url, (name, thumbnail) in sorted(categories_dict.items()):
            self.add_dir(name, cat_url, 2, thumbnail, self.fanart)
            
        self.end_directory()

    def play_video(self, url):
        content = self.make_request(urllib.parse.unquote_plus(url))
        if not content:
            self.notify_error('Failed to load video page')
            return

        stream_url = None
        
        preload_match = re.search(r'<link rel="preload" href="([^"]+\.m3u8)"', content)
        if preload_match:
            stream_url = preload_match.group(1)

        if not stream_url:
            noscript_match = re.search(r'<noscript>.*?<video[^>]+src="([^"]+\.mp4)"', content, re.DOTALL)
            if noscript_match:
                stream_url = noscript_match.group(1)

        if not stream_url:
            self.notify_error('No playable stream found')
            return

        if not stream_url.startswith('http'):
            stream_url = urllib.parse.urljoin(self.base_url, stream_url)
        
        li = xbmcgui.ListItem(path=stream_url)
        
        if '.m3u8' in stream_url:
            li.setProperty('inputstream', 'inputstream.adaptive')
            li.setProperty('inputstream.adaptive.manifest_type', 'hls')
            li.setMimeType('application/vnd.apple.mpegurl')
        else:
            li.setMimeType('video/mp4')
            
        li.setContentLookup(False)
        xbmcplugin.setResolvedUrl(self.addon_handle, True, li)