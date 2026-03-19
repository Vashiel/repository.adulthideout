# -*- coding: utf-8 -*-
import xbmcplugin
import xbmcgui
import xbmc
from resources.lib.base_website import BaseWebsite
import re
import urllib.parse
from html import unescape

class OKXXX(BaseWebsite):
    def __init__(self, addon_handle, addon=None):
        super(OKXXX, self).__init__(
            'okxxx', 
            'https://ok.xxx', 
            'https://ok.xxx/search/{}/',
            addon_handle, 
            addon)

        self.sort_options = ['Recent', 'Popular', 'Top Rated']
        self.sort_paths = {
            'Recent': '/',
            'Popular': '/popular/',
            'Top Rated': '/top-rated/'
        }

        import os
        import sys
        vendor_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'lib', 'vendor')
        if vendor_path not in sys.path:
            sys.path.insert(0, vendor_path)

        import cloudscraper
        self._scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'windows',
                'desktop': True
            }
        )

    def make_request(self, url):
        try:
            self.logger.info(f"[OK.xxx] GET {url}")
            response = self._scraper.get(url, timeout=20)
            if response.status_code == 200:
                return response.text
            self.logger.error(f"[OK.xxx] HTTP {response.status_code} for {url}")
            return None
        except Exception as e:
            self.logger.error(f"[OK.xxx] Request error: {e}")
            return None

    def process_content(self, url):
        if url == "BOOTSTRAP":
            url, _ = self.get_start_url_and_label()

        self.add_dir('Search', '', 5, self.icons.get('search', self.icon), name_param=self.name)
        self.add_dir('Categories', f"{self.base_url}/channels/", 8, self.icons.get('categories', self.icon), name_param=self.name)

        html = self.make_request(url)
        if not html:
            self.end_directory()
            return

        found = 0
        blocks = re.split(r'<div[^>]+class=["\'][^"\']*thumb-bl-video[^"\']*["\'][^>]*>', html)
        if len(blocks) > 1:
            for block in blocks[1:]:
                video_slug = ""
                thumb = ""
                title = ""
                
                # Link and title
                a_match = re.search(r'<a[^>]+href=["\'](/video/[^"\']+)["\']([^>]*)>', block, re.IGNORECASE)
                if not a_match:
                    continue
                video_slug = a_match.group(1)
                
                title_attr = re.search(r'title=["\']([^"\']+)["\']', a_match.group(2), re.IGNORECASE)
                if title_attr:
                    title = title_attr.group(1).strip()
                
                # Image
                img_match = re.search(r'<img[^>]+(?:data-original|src)=["\']([^"\']+)["\']([^>]*)>', block, re.IGNORECASE)
                if img_match:
                    thumb = img_match.group(1)
                    if not title:
                        alt_attr = re.search(r'alt=["\']([^"\']+)["\']', img_match.group(2), re.IGNORECASE)
                        if alt_attr:
                            title = alt_attr.group(1).strip()
                            
                # Fallback title from h tags
                if not title:
                    h_match = re.search(r'<h[2345][^>]*>(.*?)</h[2345]>', block, re.IGNORECASE)
                    if h_match:
                        title = h_match.group(1).strip()

                title = unescape(title)
                full_url = urllib.parse.urljoin(self.base_url, video_slug)
                
                if not thumb:
                    thumb = self.icon
                elif not thumb.startswith('http'):
                    if thumb.startswith('//'):
                        thumb = 'https:' + thumb
                    else:
                        thumb = urllib.parse.urljoin(self.base_url, thumb)

                # Duration
                duration = 0
                dur_m = re.search(r'<i[^>]+fa-clock-o[^>]*></i>\s*<span>\s*([\d:]+)\s*</span>', block, re.IGNORECASE)
                if dur_m:
                    duration = self.duration_to_seconds(dur_m.group(1))

                info_labels = {'title': title, 'plot': title, 'duration': duration}
                self.add_link(title, full_url, 4, thumb, self.fanart, info_labels=info_labels)
                found += 1
            
        self.logger.info(f"[OK.xxx] Found {found} videos!")

        # Pagination: <div class="pagination">...<ul>...<li><a href="LINK">Next</a></li>
        next_m = re.search(r'<li[^>]+pagination-next[^>]*>\s*<a[^>]+href=["\']([^"\']+)["\']', html, re.IGNORECASE)
        if next_m:
            next_url = urllib.parse.urljoin(self.base_url, next_m.group(1))
            self.add_dir('Next Page >>', next_url, 2 if '/channels/' not in next_url else 8, self.icons.get('default', self.icon), name_param=self.name)
            
        self.end_directory(content_type="movies")


    def process_categories(self, url):
        html = self.make_request(url)
        if not html:
            self.end_directory()
            return

        blocks = re.split(r'<div[^>]+class=["\'][^"\']*thumb-bl["\'][^>]*>', html)
        if len(blocks) > 1:
            for block in blocks[1:]:
                a_match = re.search(r'<a[^>]+href=["\'](/(?:channels|sites|models|tags)/[^"\']+)["\']([^>]*)>', block, re.IGNORECASE)
                if not a_match: continue
                
                cat_url = urllib.parse.urljoin(self.base_url, a_match.group(1))
                
                title = ""
                title_attr = re.search(r'title=["\']([^"\']+)["\']', a_match.group(2), re.IGNORECASE)
                if title_attr: title = title_attr.group(1).strip()
                
                thumb = ""
                img_match = re.search(r'<img[^>]+(?:data-original|src)=["\']([^"\']+)["\']([^>]*)>', block, re.IGNORECASE)
                if img_match:
                    thumb = img_match.group(1)
                    if not title:
                        alt_attr = re.search(r'alt=["\']([^"\']+)["\']', img_match.group(2), re.IGNORECASE)
                        if alt_attr: title = alt_attr.group(1).strip()
                
                if not title:
                    p_match = re.search(r'<p>(.*?)</p>', block, re.IGNORECASE|re.DOTALL)
                    if p_match: title = p_match.group(1).strip()
                    
                title = unescape(title)

                if not thumb.startswith('http'):
                    if thumb.startswith('//'):
                        thumb = 'https:' + thumb
                    else:
                        thumb = urllib.parse.urljoin(self.base_url, thumb)
                        
                self.add_dir(title, cat_url, 2, thumb, name_param=self.name)

        next_m = re.search(r'<li[^>]+pagination-next[^>]*>\s*<a[^>]+href=["\']([^"\']+)["\']', html, re.IGNORECASE)
        if next_m:
            next_url = urllib.parse.urljoin(self.base_url, next_m.group(1))
            self.add_dir('Next Page >>', next_url, 8, self.icons.get('default', self.icon), name_param=self.name)

        self.end_directory(content_type="movies")

    def end_directory(self, content_type="movies"):
        import xbmcplugin
        import xbmc
        xbmcplugin.setContent(self.addon_handle, content_type)
        xbmcplugin.endOfDirectory(self.addon_handle)
        
        try:
            viewtype = int(self.addon.getSetting('viewtype') or '2')
        except:
            viewtype = 2
            
        view_modes = [50, 51, 500, 501, 502]
        if 0 <= viewtype < len(view_modes):
            xbmc.executebuiltin(f'Container.SetViewMode({view_modes[viewtype]})')


    def search(self, query):
        if not query:
            # Fallback to sys.argv for KVAT tests
            for arg in sys.argv:
                if 'query=' in arg:
                    query = urllib.parse.unquote_plus(arg.split('query=')[1].split('&')[0])
                    break
        if not query: return
        search_url = self.search_url.format(urllib.parse.quote_plus(query))
        self.process_content(search_url)

    def play_video(self, url):
        html = self.make_request(url)
        if not html:
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return

        # Priority: mp4 sources inside <source>
        sources = []
        for match in re.finditer(r'<source[^>]+src=["\']([^"\']+)["\'][^>]*label=["\']?.*?(Auto|\d{3,4})', html, re.IGNORECASE):
            src_url = match.group(1)
            quality = match.group(2)
            
            res_val = 0
            if quality != 'Auto':
                 res_val = int(re.sub(r'[^\d]', '', quality) or 0)
            
            sources.append((res_val, src_url))
            
        if sources:
            sources.sort(key=lambda x: x[0], reverse=True)
            stream_url = sources[0][1]
        else:
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return
            
        if not stream_url.startswith('http'):
            stream_url = urllib.parse.urljoin(self.base_url, stream_url)

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': url
        }
        
        final_url = stream_url + '|' + urllib.parse.urlencode(headers)
        
        li = xbmcgui.ListItem(path=final_url)
        li.setMimeType('video/mp4')
        li.setProperty('IsPlayable', 'true')
        
        xbmcplugin.setResolvedUrl(self.addon_handle, True, li)

    def duration_to_seconds(self, duration_str):
        if not duration_str: return 0
        parts = duration_str.split(':')
        try:
            if len(parts) == 2:
                return int(parts[0]) * 60 + int(parts[1])
            elif len(parts) == 3:
                return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        except Exception:
            pass
        return 0
