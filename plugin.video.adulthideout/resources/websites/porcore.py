
import re
import sys
import urllib.parse
import urllib.request
import xbmcgui
import xbmcplugin
import xbmc
from resources.lib.base_website import BaseWebsite

class PorcoreWebsite(BaseWebsite):
    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="porcore",
            base_url="https://porcore.com",
            search_url="https://porcore.com/show/{}?ajax",
            addon_handle=addon_handle,
            addon=addon
        )
        self.sort_options = ["Newest", "Most Viewed", "Top Rated"]

    def get_start_url_and_label(self):
        setting_id = f"{self.name}_sort_by"
        sort_index = int(self.addon.getSetting(setting_id) or '0')
        
        if sort_index == 1:
            return f"{self.base_url}/videos/most-viewed/", f"Porcore - Most Viewed"
        elif sort_index == 2:
            return f"{self.base_url}/videos/top-rated/", f"Porcore - Top Rated"
        return self.base_url, f"Porcore - Newest"

    def make_request(self, url):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"})
            with urllib.request.urlopen(req, timeout=15) as response:
                return response.read().decode('utf-8')
        except Exception:
            return None

    def search(self, query):
        if not query: return
        encoded_query = urllib.parse.quote(query)
        search_url = f"{self.base_url}/show/{encoded_query}?ajax"
        self.process_content(search_url)

    def process_content(self, url):
        self.add_basic_dirs(url)
        content = self.make_request(url)
        if content:
            self.parse_video_list(content, url)
            self.add_next_button(content, url)
        self.end_directory()

    def add_basic_dirs(self, current_url):
        self.add_dir('[COLOR blue]Search[/COLOR]', '', 5, self.icons['search'])
        self.add_dir('Categories', f'{self.base_url}', 8, self.icons['categories'])

    def parse_video_list(self, content, current_url):
        link_pattern = r'<a[^>]+href="(/video/[^"]+)"([^>]*)>(.*?)</a>'
        matches = list(re.finditer(link_pattern, content, re.DOTALL))
        
        seen_urls = set()
        
        for i, match in enumerate(matches):
            video_part = match.group(1)
            attrs = match.group(2)
            text = match.group(3)
            
            full_url = urllib.parse.urljoin(self.base_url, video_part)
            if full_url in seen_urls: continue

            title = "Unknown"
            t_match = re.search(r'title="([^"]+)"', attrs)
            if t_match:
                title = t_match.group(1)
            elif text.strip():
                clean_text = re.sub(r'<[^>]+>', '', text).strip()
                title = clean_text.split('\n')[0].strip()
                if not title: title = clean_text.strip()
            
            if not title or title == "Unknown":
                pass

            thumb = self.fanart
            img_in_link = re.search(r'<img[^>]+(?:data-original|src)="([^"]+)"', text)
            if img_in_link:
                t_url = img_in_link.group(1)
                thumb = self._clean_thumb(t_url)
            else:
                start_search = match.end()
                if i < len(matches) - 1:
                    end_search = matches[i+1].start()
                    if end_search - start_search > 2000:
                         end_search = start_search + 2000
                else:
                    end_search = start_search + 2000
                
                forward_block = content[start_search:end_search]
                img_forward = re.search(r'<img[^>]+(?:data-original|src)="([^"]+)"', forward_block)
                if img_forward:
                     t_url = img_forward.group(1)
                     thumb = self._clean_thumb(t_url)

            self.add_link(title.strip(), full_url, 4, thumb, self.fanart)
            seen_urls.add(full_url)

    def _clean_thumb(self, t_url):
        if not t_url.startswith('data:image') and 'loading' not in t_url and 'blank' not in t_url:
            if t_url.startswith('//'):
                return 'https:' + t_url
            elif not t_url.startswith('http'):
                return urllib.parse.urljoin(self.base_url, t_url)
            return t_url
        return self.fanart

    def add_next_button(self, content, current_url):
        current_page = 1
        
        if 'p=' in current_url:
            m = re.search(r'[?&]p=(\d+)', current_url)
            if m: current_page = int(m.group(1))
        else:
            base_temp = current_url.split('?')[0].rstrip('/')
            m = re.search(r'/(\d+)$', base_temp)
            if m:
                current_page = int(m.group(1))
        
        next_page = current_page + 1
        
        base_url = re.sub(r'[?&]ajax&p=\d+', '', current_url)
        sep = '&' if '?' in base_url else '?'
        next_url = f"{base_url}{sep}ajax&p={next_page}"
        
        self.add_dir(f'[COLOR blue]Next Page ({next_page}) >>>>[/COLOR]', next_url, 2, self.icons['default'], self.fanart)

    def play_video(self, url):
        content = self.make_request(url)
        if content:
            video_url = None
            
            match = re.search(r'<source[^>]+src="([^"]+)"', content)
            if match:
                video_url = match.group(1)
            
            if not video_url:
                match_js = re.search(r'file\s*:\s*"([^"]+)"', content)
                if match_js:
                    video_url = match_js.group(1)
            
            if video_url:
                li = xbmcgui.ListItem(path=video_url)
                
                if '.m3u8' in video_url:
                    li.setProperty('inputstream', 'inputstream.adaptive')
                    li.setProperty('inputstream.adaptive.manifest_type', 'hls')
                    li.setMimeType('application/vnd.apple.mpegurl')
                    
                xbmcplugin.setResolvedUrl(self.addon_handle, True, li)
                return

        self.notify_error("No video found")

    def process_categories(self, url):
        content = self.make_request(url)
        if content:
            pattern = r'<a[^>]+href="(/show/[^"]+)"[^>]*>([^<]+)</a>'
            matches = re.findall(pattern, content)
            
            seen = set()
            for cat_url, param in matches:
                if cat_url in seen: continue
                full_url = urllib.parse.urljoin(self.base_url, cat_url)
                self.add_dir(param.strip(), full_url, 2, self.icons['default'], self.fanart)
                seen.add(cat_url)

        self.end_directory()
