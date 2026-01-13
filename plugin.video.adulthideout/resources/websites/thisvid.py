
import re
import sys
import urllib.parse
import urllib.request
import xbmc
import xbmcgui
import xbmcplugin
from resources.lib.base_website import BaseWebsite

class ThisVidWebsite(BaseWebsite):
    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="thisvid",
            base_url="https://thisvid.com",
            search_url="https://thisvid.com/search/?q={}",
            addon_handle=addon_handle,
            addon=addon
        )
        self.sort_options = ["Newest", "Most Viewed", "Top Rated"]
        self.content_types = ["Straight", "Gay", "All"]

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
                0: ("/newest/", "ThisVid - Straight Newest"),
                1: ("/popular/", "ThisVid - Straight Most Viewed"),
                2: ("/winners/", "ThisVid - Straight Top Rated")
            },
            1: {
                0: ("/gay-newest/", "ThisVid - Gay Newest"),
                1: ("/gay-popular/", "ThisVid - Gay Most Viewed"),
                2: ("/gay-winners/", "ThisVid - Gay Top Rated")
            },
            2: {
                0: ("/latest-updates/", "ThisVid - All Newest"),
                1: ("/most-popular/", "ThisVid - All Most Viewed"),
                2: ("/top-rated/", "ThisVid - All Top Rated")
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
            self.parse_video_list(content, url)
            self.add_next_button(content, url)
        self.end_directory()

    def add_basic_dirs(self, current_url):
        self.add_dir('[COLOR blue]Search[/COLOR]', '', 5, self.icons['search'])
        
        content_id = f"{self.name}_content_type"
        content_index = int(self.addon.getSetting(content_id) or '0')
        
        if content_index == 0:
            self.add_dir('Straight Categories', f'{self.base_url}/categories/?tab=straight', 8, self.icons['categories'])
        elif content_index == 1:
            self.add_dir('Gay Categories', f'{self.base_url}/categories/?tab=gay', 8, self.icons['categories'])
        else:
            self.add_dir('Straight Categories', f'{self.base_url}/categories/?tab=straight', 8, self.icons['categories'])
            self.add_dir('Gay Categories', f'{self.base_url}/categories/?tab=gay', 8, self.icons['categories'])

    def parse_video_list(self, content, current_url):
        item_pattern = r'<a[^>]+href="(https://thisvid\.com/videos/[^"]+/)"[^>]*title="([^"]+)"[^>]*class="tumbpu"[^>]*>(.*?)</a>'
        matches = re.finditer(item_pattern, content, re.DOTALL)
        
        for match in matches:
            video_url = match.group(1)
            title = match.group(2)
            inner_html = match.group(3)
            
            thumb = self.fanart
            img_match = re.search(r'data-original="([^"]+)"', inner_html)
            if img_match:
                t_url = img_match.group(1)
                if t_url.startswith('//'):
                    thumb = 'https:' + t_url
                elif t_url.startswith('http'):
                    thumb = t_url
                else:
                    thumb = urllib.parse.urljoin(self.base_url, t_url)
            
            self.add_link(title, video_url, 4, thumb, self.fanart)

    def add_next_button(self, content, current_url):
        next_match = re.search(r'<li[^>]+class="[^"]*pagination-next[^"]*"[^>]*>\s*<a[^>]+href="([^"]+)"', content, re.IGNORECASE)
        
        if next_match:
            next_url = next_match.group(1)
            if not next_url.startswith('http'):
                next_url = urllib.parse.urljoin(self.base_url, next_url)
            
            page_num = "Next"
            p_match = re.search(r'/(\d+)/?$', next_url)
            if p_match:
                page_num = p_match.group(1)
                
            self.add_dir(f'[COLOR blue]Next Page ({page_num}) >>>>[/COLOR]', next_url, 2, self.icons['default'], self.fanart)

    def decode_kvs_url(self, video_url):
        mapping = [6, 21, 16, 2, 27, 0, 20, 18, 14, 10, 3, 5, 15, 9, 30, 25, 22, 1, 31, 13, 7, 23, 8, 11, 26, 28, 29, 19, 17, 24, 12, 4]
        
        if video_url.startswith('function/0/'):
            video_url = video_url.replace('function/0/', '')
            
        match = re.search(r'/get_file/(\d+)/([a-f0-9]+)/', video_url)
        if not match:
            return video_url
            
        original_hash = match.group(2)
        if len(original_hash) < 32:
            return video_url
            
        hash_list = list(original_hash)
        new_hash_list = [''] * len(original_hash)
        
        for i in range(32):
            new_hash_list[i] = hash_list[mapping[i]]
            
        for i in range(32, len(original_hash)):
            new_hash_list[i] = hash_list[i]
            
        new_hash = "".join(new_hash_list)
        return video_url.replace(original_hash, new_hash)

    def search(self, query):
        if not query: return
        
        content_id = f"{self.name}_content_type"
        content_index = int(self.addon.getSetting(content_id) or '0')
        
        if content_index == 0:
            search_url = f"{self.base_url}/female/?q={urllib.parse.quote_plus(query)}"
        elif content_index == 1:
            search_url = f"{self.base_url}/male/?q={urllib.parse.quote_plus(query)}"
        else:
            search_url = f"{self.base_url}/search/?q={urllib.parse.quote_plus(query)}"
            
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

        embed_match = re.search(r'src="(https://thisvid\.com/embed/[^"]+/)"', content)
        if embed_match:
            embed_url = embed_match.group(1)
            embed_content = self.make_request(embed_url)
            
            if embed_content:
                video_url = None
                
                vu_match = re.search(r"video_url\s*:\s*'([^']+)'", embed_content)
                if vu_match:
                    video_url = self.decode_kvs_url(vu_match.group(1))
                
                if not video_url:
                    er2_match = re.search(r"event_reporting2\s*:\s*'([^']+)'", embed_content)
                    if er2_match:
                        video_url = er2_match.group(1)
                
                if video_url:
                    li = xbmcgui.ListItem(path=video_url)
                    xbmcplugin.setResolvedUrl(self.addon_handle, True, li)
                    return

        self.notify_error("No video found")

    def process_categories(self, url):
        is_gay = 'tab=gay' in url
        
        base_cat_url = f'{self.base_url}/categories/'
        content = self.make_request(base_cat_url)
        
        if content:
            tab_id = 'tab2' if is_gay else 'tab1'
            
            tab_pattern = rf'<div[^>]+id="{tab_id}"[^>]*>(.*?)</div>\s*<div[^>]+id="tab'
            tab_match = re.search(tab_pattern, content, re.DOTALL)
            
            if not tab_match:
                tab_pattern = rf'<div[^>]+id="{tab_id}"[^>]*class="[^"]*tab[^"]*"[^>]*>(.*?)</div>\s*(?:<div[^>]+id="tab|<script|</section)'
                tab_match = re.search(tab_pattern, content, re.DOTALL)
            
            section_content = tab_match.group(1) if tab_match else content
            
            cat_pattern = r'href="(https://thisvid\.com/categories/([^"]+)/)"[^>]*>\s*<img[^>]+src="([^"]+)"'
            matches = re.finditer(cat_pattern, section_content)
            
            seen = set()
            for match in matches:
                c_url = match.group(1)
                slug = match.group(2)
                thumb = match.group(3)
                
                if c_url in seen: continue
                
                title = slug.replace('-', ' ').title()
                
                if thumb.startswith('//'): thumb = 'https:' + thumb
                
                self.add_dir(title, c_url, 2, thumb, self.fanart)
                seen.add(c_url)

        self.end_directory()
