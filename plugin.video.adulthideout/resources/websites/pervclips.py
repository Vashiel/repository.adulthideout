import re
import sys
import urllib.parse
import urllib.request
import xbmc
import xbmcgui
import xbmcplugin
import xbmcvfs
import xbmcaddon
import os
import hashlib
import time
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from resources.lib.base_website import BaseWebsite

class PervClipsWebsite(BaseWebsite):
    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="pervclips",
            base_url="https://www.pervclips.com",
            search_url="https://www.pervclips.com/tube/search/?q={}",
            addon_handle=addon_handle,
            addon=addon
        )
        self.sort_options = ["Newest", "Most Viewed", "Top Rated"]
        self.content_types = ["Straight", "Gay", "Trans"]
        
        self._thumb_cache_dir = self._initialize_thumb_cache()
        self.icon = os.path.join(self.addon.getAddonInfo('path'), 'resources', 'logos', 'pervclips.png')

    def _initialize_thumb_cache(self):
        addon_profile = xbmcvfs.translatePath(xbmcaddon.Addon().getAddonInfo('profile'))
        thumb_dir = os.path.join(addon_profile, 'thumbs', self.name)
        if not xbmcvfs.exists(thumb_dir):
            xbmcvfs.mkdirs(thumb_dir)
        self._maybe_cleanup_cache(thumb_dir)
        return thumb_dir

    def _maybe_cleanup_cache(self, cache_dir):
        marker_file = os.path.join(cache_dir, '.last_cleanup')
        try:
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
                if filename.startswith('.'):
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
            pass

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
            
        except Exception:
            return None

    def _download_and_validate_thumb(self, url):
        if not url: return None
        
        if 'mjedge.net' in url:
           url = url.replace('.mjedge.net', '.pervclips.com').replace('c831ab7da5', 'cdn')
           url = re.sub(r'https?://[a-z0-9]+\.mjedge\.net/', 'https://cdn.pervclips.com/', url)

        url = url.split('#')[0]

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

            req = urllib.request.Request(url, headers={'User-Agent': "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=6) as response:
                 content = response.read()

            if len(content) < 2048: 
                return None
            
            if content.startswith(b'RIFF') and b'WEBP' in content[:12]:
                sanitized = self._sanitize_webp(content)
                if sanitized:
                    content = sanitized

            file_ext = None
            for signature, ext in valid_signatures.items():
                if content.startswith(signature):
                    file_ext = ext
                    break
            
            if not file_ext: return None
            
            local_path = os.path.join(self._thumb_cache_dir, hashed_url + file_ext)
            with xbmcvfs.File(local_path, 'wb') as f:
                f.write(content)
            return local_path

        except Exception:
            return None

    def select_content_type(self, *args):
        setting_id = f"{self.name}_content_type"
        current = int(self.addon.getSetting(setting_id) or '0')
        
        selected = xbmcgui.Dialog().select("Select Content Type", self.content_types, preselect=current)
        if selected != -1:
            self.addon.setSetting(setting_id, str(selected))
            xbmc.executebuiltin("Container.Refresh")

    def get_start_url_and_label(self):
        sort_id = f"{self.name}_sort_by"
        sort_index = int(self.addon.getSetting(sort_id) or '0')
        
        content_id = f"{self.name}_content_type"
        content_index = int(self.addon.getSetting(content_id) or '0')
        
        mapping = {
            0: {
                0: ("/tube/", "PervClips - Straight"),
                1: ("/tube/top-rated/", "PervClips - Top Rated"),
                2: ("/tube/most-popular/", "PervClips - Most Popular")
            },
            1: {
                0: ("/tube/gay/", "PervClips - Gay"),
                1: ("/tube/gay/top-rated/", "PervClips - Gay Top Rated"),
                2: ("/tube/gay/most-popular/", "PervClips - Gay Most Popular")
            },
            2: {
                0: ("/tube/shemale/", "PervClips - Trans"),
                1: ("/tube/shemale/top-rated/", "PervClips - Trans Top Rated"),
                2: ("/tube/shemale/most-popular/", "PervClips - Trans Most Popular")
            }
        }
        
        path, label = mapping.get(content_index, mapping[0]).get(sort_index, mapping[0][0])
        return f"{self.base_url}{path}", label

    def make_request(self, url):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"})
            with urllib.request.urlopen(req, timeout=15) as response:
                return response.read().decode('utf-8')
        except Exception:
            return None

    def process_content(self, url):
        self.add_basic_dirs(url)
        content = self.make_request(url)
        if content:
            videos = self.extract_videos(content)
            
            if not videos:
                self.notify_info('No videos found.')
                self.end_directory()
                return

            def download_thumb_task(video):
                thumb_path = None
                for cand in video['candidates']:
                    if not cand: continue
                    if cand.startswith('//'): cand = 'https:' + cand
                    elif not cand.startswith('http'): cand = urllib.parse.urljoin(self.base_url, cand)
                    
                    found = self._download_and_validate_thumb(cand)
                    if found:
                        thumb_path = found
                        break
                return (video, thumb_path)

            results = []
            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = [executor.submit(download_thumb_task, v) for v in videos]
                for future in as_completed(futures):
                    try:
                        results.append(future.result())
                    except:
                        pass
            
            results_map = {v['url']: path for v, path in results}
            
            for video in videos:
                video_url = video['url']
                local_thumb = results_map.get(video_url) or self.fanart
                
                self.add_link(video['title'], video_url, 4, local_thumb, self.fanart)

            self.add_next_button(content, url)
        self.end_directory()

    def add_basic_dirs(self, current_url):
        self.add_dir('[COLOR blue]Search[/COLOR]', '', 5, self.icons['search'])
        
        content_id = f"{self.name}_content_type"
        content_index = int(self.addon.getSetting(content_id) or '0')
        
        if content_index == 0:
            self.add_dir('Categories', f'{self.base_url}/tube/categories/', 8, self.icons['categories'])
        elif content_index == 1:
            self.add_dir('Gay Categories', f'{self.base_url}/tube/gay/categories/', 8, self.icons['categories'])
        else:
            self.add_dir('Trans Categories', f'{self.base_url}/tube/shemale/categories/', 8, self.icons['categories'])

    def extract_videos(self, content):
        videos = []
        pattern = r'(<a[^>]+class="[^"]*img[^"]*link[^"]*"[^>]*>)(.*?)</a>'
        matches = re.finditer(pattern, content, re.DOTALL)
        
        seen = set()
        for match in matches:
            opening_tag = match.group(1)
            inner_html = match.group(2)
            
            href_match = re.search(r'href="([^"]+)"', opening_tag)
            if not href_match: continue
            video_url = href_match.group(1)
            
            if '/tube/videos/' not in video_url: continue
            if video_url in seen: continue
            seen.add(video_url)
            
            video_url = urllib.parse.urljoin(self.base_url, video_url)
            
            title = "Video"
            title_match = re.search(r'<p[^>]*class="[^"]*title[^"]*"[^>]*>(.*?)</p>', inner_html, re.DOTALL)
            if title_match:
                title = re.sub(r'<[^>]+>', '', title_match.group(1)).strip()
            else:
                alt_match = re.search(r'alt="([^"]+)"', inner_html)
                if alt_match: title = alt_match.group(1).strip()
            
            if not title or title == "Video":
                slug = video_url.rstrip('/').split('/')[-1]
                title = slug.replace('-', ' ').title()

            candidates = []
            
            poster_match = re.search(r'data-poster="([^"]+)"', opening_tag)
            if poster_match: candidates.append(poster_match.group(1))
            
            orig_match = re.search(r'data-original="([^"]+)"', inner_html)
            if orig_match: candidates.append(orig_match.group(1))
            
            src_match = re.search(r'src="([^"]+)"', inner_html)
            if src_match:
                src = src_match.group(1)
                if 'placeholder' not in src:
                    candidates.append(src)
            
            videos.append({
                'title': title,
                'url': video_url,
                'candidates': candidates
            })
        return videos

    def add_next_button(self, content, current_url):
        next_match = re.search(r'<a[^>]+class="[^"]*link next[^"]*"[^>]+href="([^"]+)"', content, re.IGNORECASE)
        
        if next_match:
            next_url = next_match.group(1)
            if not next_url.startswith('http'):
                next_url = urllib.parse.urljoin(self.base_url, next_url)
            
            page_num = "Next"
            p_match = re.search(r'/(\d+)/?$', next_url)
            if p_match:
                page_num = p_match.group(1)
                
            self.add_dir(f'[COLOR blue]Next Page ({page_num}) >>>>[/COLOR]', next_url, 2, self.icons['default'], self.fanart)

    def search(self, query):
        if not query: return
        
        content_id = f"{self.name}_content_type"
        content_index = int(self.addon.getSetting(content_id) or '0')
        
        if content_index == 0:
            search_url = f"{self.base_url}/tube/search/?q={urllib.parse.quote_plus(query)}"
        elif content_index == 1:
            search_url = f"{self.base_url}/tube/gay/search/?q={urllib.parse.quote_plus(query)}"
        else:
            search_url = f"{self.base_url}/tube/shemale/search/?q={urllib.parse.quote_plus(query)}"
            
        self.process_content(search_url)

    def add_dir(self, name, url, mode, icon=None, fanart=None, context_menu=None, **kwargs):
        if context_menu is None: context_menu = []
        
        cm_item = ('Change Content...', f'RunPlugin({sys.argv[0]}?mode=7&action=select_content_type&website={self.name})')
        if not any(cm_item[0] in str(item) for item in context_menu):
            context_menu.append(cm_item)
            
        super().add_dir(name, url, mode, icon, fanart, context_menu, **kwargs)

    def add_link(self, name, url, mode, icon, fanart, context_menu=None, info_labels=None):
        if context_menu is None: context_menu = []
        
        cm_item = ('Change Content...', f'RunPlugin({sys.argv[0]}?mode=7&action=select_content_type&website={self.name})')
        if not any(cm_item[0] in str(item) for item in context_menu):
            context_menu.append(cm_item)
            
        super().add_link(name, url, mode, icon, fanart, context_menu, info_labels)

    def play_video(self, url):
        content = self.make_request(url)
        if not content:
            self.notify_error("Failed to load video page")
            return

        video_url = None
        vu_match = re.search(r"video_url\s*:\s*'([^']+)'", content)
        if vu_match:
            video_url = vu_match.group(1)
            if video_url.startswith('function/0/'):
                video_url = video_url.replace('function/0/', '')
        
        if not video_url:
            vu_match = re.search(r'<source[^>]+src="([^"]+)"', content)
            if vu_match:
                video_url = vu_match.group(1)
        
        if video_url:
            if not video_url.startswith('http'):
                video_url = urllib.parse.urljoin(self.base_url, video_url)
            
            separator = '&' if '?' in video_url else '?'
            video_url += f'{separator}rnd={int(time.time() * 1000)}'
                
            ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            referer = self.base_url + "/"
            
            if '.m3u8' in video_url:
                li = xbmcgui.ListItem(path=video_url)
                li.setMimeType('application/vnd.apple.mpegurl')
                li.setProperty('inputstream', 'inputstream.adaptive')
                li.setProperty('inputstream.adaptive.manifest_type', 'hls')
                li.setProperty('inputstream.adaptive.stream_headers', 'User-Agent={}'.format(urllib.parse.quote(ua)))
                xbmcplugin.setResolvedUrl(self.addon_handle, True, li)
                return
            else:
                try:
                    from resources.lib.proxy_utils import ProxyController, PlaybackGuard
                    
                    headers = {
                        "User-Agent": ua,
                        "Referer": referer
                    }
                    
                    controller = ProxyController(video_url, upstream_headers=headers)
                    local_url = controller.start()
                    
                    monitor = xbmc.Monitor()
                    player = xbmc.Player()
                    guard = PlaybackGuard(player, monitor, local_url, controller)
                    guard.start()
                    
                    li = xbmcgui.ListItem(path=local_url)
                    li.setMimeType('video/mp4')
                    li.setProperty('IsPlayable', 'true')
                    li.setContentLookup(False) 
                    
                    xbmcplugin.setResolvedUrl(self.addon_handle, True, li)
                    
                    guard.join()
                    return
                    
                except ImportError:
                    self.notify_error("Proxy Utils missing")
                except Exception as e:
                    xbmc.log(f"[PervClips] Proxy failed: {e}", xbmc.LOGERROR)
                    headers_str = 'User-Agent={}&Referer={}'.format(
                        urllib.parse.quote(ua),
                        urllib.parse.quote(referer)
                    )
                    li = xbmcgui.ListItem(path=video_url + '|' + headers_str)
                    li.setMimeType('video/mp4')
                    li.setProperty('IsPlayable', 'true')
                    xbmcplugin.setResolvedUrl(self.addon_handle, True, li)
                    return

        self.notify_error("No video found")

    def process_categories(self, url):
        content = self.make_request(url)
        
        if content:
            categories = []
            
            pattern = r'(<a[^>]+class="[^"]*link-thumb[^"]*"[^>]*>)(.*?)</a>'
            matches = list(re.finditer(pattern, content, re.DOTALL))
            
            if not matches:
                 pattern = r'(<a[^>]+href="[^"]*/categories/[^"]*"[^>]*>)(.*?)</a>'
                 matches = list(re.finditer(pattern, content, re.DOTALL))
            
            seen = set()
            for match in matches:
                opening_tag = match.group(1)
                inner_html = match.group(2)
                
                href_match = re.search(r'href="([^"]+)"', opening_tag)
                if not href_match: continue
                c_url = href_match.group(1)
                
                if c_url in seen: continue
                seen.add(c_url)
                
                title_match = re.search(r'<p[^>]*>([^<]+)</p>', inner_html)
                title = title_match.group(1).strip() if title_match else c_url.split('/')[-2].replace('-', ' ').title()
                
                candidates = []
                img_match = re.search(r'<img[^>]+src="([^"]+)"', inner_html)
                if img_match:
                    candidates.append(img_match.group(1))
                
                if not c_url.startswith('http'):
                    c_url = urllib.parse.urljoin(self.base_url, c_url)
                    
                categories.append({
                    'title': title,
                    'url': c_url,
                    'candidates': candidates
                })

            if not categories:
                self.notify_error('No categories found')
                self.end_directory()
                return

            def download_thumb_task(cat):
                thumb_path = None
                for cand in cat['candidates']:
                    if not cand: continue
                    if cand.startswith('//'): cand = 'https:' + cand
                    elif not cand.startswith('http'): cand = urllib.parse.urljoin(self.base_url, cand)
                    
                    found = self._download_and_validate_thumb(cand)
                    if found:
                        thumb_path = found
                        break
                return (cat, thumb_path)

            results = []
            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = [executor.submit(download_thumb_task, c) for c in categories]
                for future in as_completed(futures):
                    try:
                         results.append(future.result())
                    except:
                         pass
            
            results_map = {c['url']: path for c, path in results}
            
            for cat in categories:
                local_thumb = results_map.get(cat['url']) or self.fanart
                self.add_dir(cat['title'], cat['url'], 2, local_thumb, self.fanart)

        self.end_directory()
