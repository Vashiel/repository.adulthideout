import re
import urllib.parse
import xbmc
import xbmcgui
import xbmcplugin
import json
import os
import sys
import xbmcaddon
from resources.lib.base_website import BaseWebsite

try:
    addon_path = xbmcaddon.Addon().getAddonInfo('path')
    vendor_path = os.path.join(addon_path, 'resources', 'lib', 'vendor')
    if vendor_path not in sys.path:
        sys.path.append(vendor_path)
    import cloudscraper
except ImportError:
    cloudscraper = None

class Drtuber(BaseWebsite):
    def __init__(self, addon_handle):
        self.name = 'drtuber'
        self.base_url = 'https://www.drtuber.com'
        self.search_url = 'https://www.drtuber.com/search/videos/{}'
        super().__init__(self.name, self.base_url, self.search_url, addon_handle)
        
        if cloudscraper:
            self.session = cloudscraper.create_scraper()
        else:
            self.session = None
        
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': self.base_url + '/',
            'Accept-Language': 'en-US,en;q=0.9'
        }
        
        self.content_types = {
            'straight': ('Straight', ''),
            'gay': ('Gay', '/gay'),
            'shemale': ('Transsexual', '/shemale')
        }
        self.sort_options = {
            'newest': ('Newest', ''),
            'longest': ('Longest', '/longest'),
            'hd': ('HD Videos', '/hd'),
            '4k': ('4K Videos', '/4k')
        }
        self.channel_sorts = {
            'top': ('Top', ''),
            'newest': ('Newest', '/newest'),
            'a-z': ('A-Z', '/a-z')
        }
        
        self.video_list_pattern = re.compile(r'<a\s+href="(/video/(\d+)/[^"]+)"[^>]*class="[^"]*th[^"]*"[^>]*>.*?<img[^>]+(?:src|data-original)="([^"]+)"[^>]+alt="([^"]*)".*?<em\s+class="time_thumb"[^>]*>.*?<em>([^<]+)</em>', re.DOTALL)
        self.categories_pattern = re.compile(r'<a\s+href="((?:/(?:gay|shemale))?/categories/[^"]+)"[^>]*>\s*(?:<span>)?([^<]+)(?:</span>)?\s*</a>', re.DOTALL)
        self.pornstars_pattern = re.compile(r'<a\s+href="(/pornstar/[^"]+)"[^>]*>(?:.*?<img\s+(?:src|data-src|data-original)="([^"]+)")?.*?(?:<span[^>]*>)?([^<>]+)(?:</span>)?\s*</a>', re.DOTALL)
        self.channels_pattern = re.compile(r'<a[^>]+href="(/channel/[^"]+)"[^>]*>.*?(?:<span[^>]*>)?([^<]+)(?:</span>)?.*?</a>', re.DOTALL)
        self.next_page_pattern = re.compile(r'<link\s+rel="next"\s+href="([^"]+)"')
        self.pornstars_page_pattern = re.compile(r'<a[^>]+href="(/pornstars/\d+)"[^>]*>')
        self.channels_page_pattern = re.compile(r'<a[^>]+href="(/channels/\d+)"[^>]*>')
        self.next_button_pattern = re.compile(r'<a[^>]+href="([^"]+)"[^>]*>[^<]*Next[^<]*</a>', re.IGNORECASE)
        
        self.current_url = getattr(self, 'url', None) or self.base_url

    def get_filter(self, name, default):
        val = self.addon.getSetting(f'drtuber_{name}')
        return val if val else default

    def set_filter(self, name, value):
        self.addon.setSetting(f'drtuber_{name}', value)
        xbmc.sleep(200)

    def get_content_type(self):
        return self.get_filter('content_type', 'straight')
    
    def set_content_type(self, value):
        self.set_filter('content_type', value)
    
    def get_sort(self):
        return self.get_filter('sort', 'newest')
    
    def set_sort(self, value):
        self.set_filter('sort', value)
    
    def get_channel_sort(self):
        return self.get_filter('channel_sort', 'top')
    
    def set_channel_sort(self, value):
        self.set_filter('channel_sort', value)

    def build_url(self):
        content = self.get_content_type()
        sort = self.get_sort()
        url = self.base_url
        
        if content != 'straight':
            for ct_id, (ct_name, ct_path) in self.content_types.items():
                if ct_id == content and ct_path:
                    url += ct_path
                    break
            return url
        
        for s_id, (s_name, s_path) in self.sort_options.items():
            if s_id == sort and s_path:
                url += s_path
                break
        
        return url
    
    def build_categories_url(self):
        content = self.get_content_type()
        url = self.base_url
        
        for ct_id, (ct_name, ct_path) in self.content_types.items():
            if ct_id == content and ct_path:
                url += ct_path
                break
        
        url += '/categories'
        return url
    
    def build_channels_url(self):
        channel_sort = self.get_channel_sort()
        url = f"{self.base_url}/channels"
        
        for cs_id, (cs_name, cs_path) in self.channel_sorts.items():
            if cs_id == channel_sort and cs_path:
                url += cs_path
                break
        
        return url

    def make_request(self, url):
        try:
            if self.session:
                response = self.session.get(url, headers=self.headers, timeout=30)
                response.raise_for_status()
                return response.text
            else:
                import urllib.request
                req = urllib.request.Request(url, headers=self.headers)
                with urllib.request.urlopen(req, timeout=30) as response:
                    return response.read().decode('utf-8')
        except Exception as e:
            xbmc.log(f"[DrTuber] Request failed: {e}", xbmc.LOGERROR)
            return ""

    def show_sort_dialog(self):
        options = list(self.sort_options.keys())
        labels = [self.sort_options[k][0] for k in options]
        
        dialog = xbmcgui.Dialog()
        idx = dialog.select('Sort By', labels)
        if idx >= 0:
            sort_key = options[idx]
            self.set_sort(sort_key)
            _, sort_path = self.sort_options[sort_key]
            
            params = dict(urllib.parse.parse_qsl(sys.argv[2][1:]))
            base_context = params.get('current_url', self.base_url)
            
            clean_url = base_context
            for s_k, (s_n, s_p) in self.sort_options.items():
                if s_p and clean_url.endswith(s_p):
                    clean_url = clean_url[:-len(s_p)]
            
            if sort_path:
                clean_url = clean_url.rstrip('/') + sort_path
            
            xbmc.executebuiltin(f'Container.Update({sys.argv[0]}?mode=2&website={self.name}&url={urllib.parse.quote(clean_url, safe="")})')
    
    def show_content_type_dialog(self):
        options = list(self.content_types.keys())
        labels = [self.content_types[k][0] for k in options]
        
        dialog = xbmcgui.Dialog()
        idx = dialog.select('Content Type', labels)
        if idx >= 0:
            ct_key = options[idx]
            self.set_content_type(ct_key)
            url = self.build_url()
            xbmc.executebuiltin(f'Container.Update({sys.argv[0]}?mode=2&website={self.name}&url={urllib.parse.quote(url, safe="")})')
    
    def show_channel_sort_dialog(self):
        options = list(self.channel_sorts.keys())
        labels = [self.channel_sorts[k][0] for k in options]
        
        dialog = xbmcgui.Dialog()
        idx = dialog.select('Sort Channels', labels)
        if idx >= 0:
            cs_key = options[idx]
            self.set_channel_sort(cs_key)
            url = self.build_channels_url()
            xbmc.executebuiltin(f'Container.Update({sys.argv[0]}?mode=10&website={self.name}&url={urllib.parse.quote(url, safe="")})')
    
    def add_context_menu(self, li, include_sort_by=True, include_channel_sort=False):
        cm = []
        curr = urllib.parse.quote(self.current_url, safe="")
        
        if include_sort_by:
            cm.append(('Sort By', f'RunPlugin({sys.argv[0]}?mode=7&website={self.name}&action=show_sort_dialog&current_url={curr})'))
        cm.append(('Content Type', f'RunPlugin({sys.argv[0]}?mode=7&website={self.name}&action=show_content_type_dialog)'))
        if include_channel_sort:
            cm.append(('Sort Channels', f'RunPlugin({sys.argv[0]}?mode=7&website={self.name}&action=show_channel_sort_dialog)'))
        li.addContextMenuItems(cm)
        return li

    def search(self, query):
        if not query:
            return
            
        content = self.get_content_type()
        
        if content == 'gay':
            url = f"{self.base_url}/search/gay/{urllib.parse.quote(query)}"
        elif content == 'shemale':
            url = f"{self.base_url}/search/trans/{urllib.parse.quote(query)}"
        else:
            url = f"{self.base_url}/search/videos/{urllib.parse.quote(query)}"
        
        self.process_content(url)

    def process_content(self, url):
        if url == 'BOOTSTRAP':
            url = self.build_url()
        
        self.current_url = url
        
        html = self.make_request(url)
        if not html:
            self.end_directory()
            return
        
        self.add_dir('[COLOR blue]Search[/COLOR]', 'BOOTSTRAP', 5, self.icons.get('search', self.icon), action='show_search_menu')
        self.add_dir('[COLOR blue]Categories[/COLOR]', 'BOOTSTRAP', 8, self.icons.get('categories', self.icon), action='process_categories')
        self.add_dir('[COLOR blue]Pornstars[/COLOR]', 'BOOTSTRAP', 9, self.icons.get('pornstars', self.icon), action='process_pornstars')
        self.add_dir('[COLOR blue]Channels[/COLOR]', 'BOOTSTRAP', 10, self.icons.get('groups', self.icon), action='process_channels')
        
        matches = self.video_list_pattern.findall(html)
        
        is_search = '/search' in url
        content_type = self.get_content_type()
        
        filtered_matches = []
        if is_search and content_type == 'shemale':
            trans_keywords = ['shemale', 'trans', 'ladyboy', 'tranny', 'ts ', ' ts', 't-girl', 'dickgirl', 'futanari', 'tgirl']
            for match in matches:
                title = match[3].lower()
                if any(k in title for k in trans_keywords):
                    filtered_matches.append(match)
            matches = filtered_matches
        
        for path, video_id, thumb, title, duration in matches:
            video_url = f"{self.base_url}{path}" if path.startswith('/') else path
            
            try:
                parts = duration.split(':')
                duration_seconds = int(parts[0]) * 60 + int(parts[1])
            except:
                duration_seconds = 0

            title = title.replace('&quot;', '"').replace('&#039;', "'")
            
            li = xbmcgui.ListItem(label=title)
            li.setArt({'thumb': thumb, 'icon': thumb, 'fanart': self.fanart})
            li.setInfo('video', {'title': title, 'duration': duration_seconds, 'mediatype': 'video'})
            li.setProperty('IsPlayable', 'true')
            can_sort = '/search/' not in url and '/categories/' not in url
            li = self.add_context_menu(li, include_sort_by=can_sort)
            
            url_params = {'mode': '4', 'website': self.name, 'url': video_url, 'video_id': video_id}
            xbmcplugin.addDirectoryItem(handle=self.addon_handle, url=f"{sys.argv[0]}?{urllib.parse.urlencode(url_params)}", listitem=li, isFolder=False)
        
        next_page = self.next_page_pattern.search(html)
        next_url = None
        
        if next_page:
            next_url = next_page.group(1)
        else:
            next_btn = self.next_button_pattern.search(html)
            if next_btn:
               next_url = next_btn.group(1)
        
        if next_url:
            if not next_url.startswith('http'):
                next_url = f"{self.base_url}{next_url}" if next_url.startswith('/') else f"{self.base_url}/{next_url}"
            self.add_dir('[COLOR blue]Next Page >>>>[/COLOR]', next_url, 2, self.icons.get('default', self.icon), action='process_content')
        
        self.end_directory()

    def play_video(self, url):
        video_id = ""
        match_id = re.search(r'/video/(\d+)', url)
        if match_id:
            video_id = match_id.group(1)
        
        if not video_id:
            xbmcgui.Dialog().notification("Error", "Could not extract video ID", xbmcgui.NOTIFICATION_ERROR)
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return
        
        config_url = f"https://www.drtuber.com/player_config_json/?vid={video_id}&aid=0&domain_id=0&embed=0&ref=null&check_speed=0"
        
        headers = {
            'User-Agent': self.headers.get('User-Agent', 'Mozilla/5.0'),
            'Referer': url,
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'X-Requested-With': 'XMLHttpRequest'
        }
        
        video_url_to_play = None
        
        try:
            if cloudscraper:
                scraper = cloudscraper.create_scraper()
                res = scraper.get(config_url, headers=headers)
                if res.status_code == 200:
                    data = json.loads(res.text)
                    if isinstance(data, dict) and 'files' in data:
                        files = data['files']
                        if '4k' in files and files['4k']:
                            video_url_to_play = files['4k']
                        elif 'hq' in files and files['hq']:
                            video_url_to_play = files['hq']
                        elif 'lq' in files and files['lq']:
                            video_url_to_play = files['lq']
        except Exception as e:
            xbmc.log(f"[DrTuber] Config fetch failed: {e}", xbmc.LOGERROR)
        
        if not video_url_to_play:
            html = self.make_request(url)
            server = "g5"
            if html:
                server_match = re.search(r'https://(g\d+)\.drtst\.com/media/videos/tmb', html)
                if server_match:
                    server = server_match.group(1)
            video_url_to_play = f"https://{server}.drtst.com/media/videos/tmb/{video_id}/{video_id}.mp4"
            xbmcgui.Dialog().notification("DrTuber", "Using preview video", xbmcgui.NOTIFICATION_INFO)
        
        if video_url_to_play:
            li = xbmcgui.ListItem(path=video_url_to_play)
            if '.m3u8' in video_url_to_play:
                li.setProperty('inputstream', 'inputstream.adaptive')
                li.setProperty('inputstream.adaptive.manifest_type', 'hls')
                li.setMimeType('application/vnd.apple.mpegurl')
            else:
                li.setMimeType('video/mp4')
            xbmcplugin.setResolvedUrl(self.addon_handle, True, li)
        else:
            xbmcgui.Dialog().notification("Error", "Video source not found", xbmcgui.NOTIFICATION_ERROR)
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())

    def process_categories(self, url):
        if url == 'BOOTSTRAP':
             url = self.build_categories_url()
        
        html = self.make_request(url)
        if not html:
            self.end_directory()
            return
        
        content = self.get_content_type()
        
        if content == 'gay':
            expected_prefix = '/gay/categories/'
        elif content == 'shemale':
            expected_prefix = '/shemale/categories/'
        else:
            expected_prefix = '/categories/'
        
        matches = self.categories_pattern.findall(html)
        seen = set()
        for path, name in matches:
            name = name.strip()
            if not name or name in seen or len(name) < 2:
                continue
            
            if content == 'straight':
                if path.startswith('/gay/') or path.startswith('/shemale/'):
                    continue
            else:
                if not path.startswith(expected_prefix):
                    continue
            
            seen.add(name)
            
            li = xbmcgui.ListItem(label=name)
            li.setArt({'icon': 'DefaultFolder.png'})
            
            full_url = f"{self.base_url}{path}"
                
            url_params = {'mode': '2', 'website': self.name, 'url': full_url}
            xbmcplugin.addDirectoryItem(handle=self.addon_handle, url=f"{sys.argv[0]}?{urllib.parse.urlencode(url_params)}", listitem=li, isFolder=True)
        
        self.end_directory()

    def process_pornstars(self, url):
        if url == 'BOOTSTRAP':
            url = f"{self.base_url}/pornstars"
        
        li = xbmcgui.ListItem(label='[COLOR gold]Top 30 Pornstars[/COLOR]')
        li.setArt({'icon': self.icons.get('pornstars', self.icon)})
        top30_params = {'mode': '7', 'website': self.name, 'action': 'show_top30_pornstars'}
        xbmcplugin.addDirectoryItem(handle=self.addon_handle, url=f"{sys.argv[0]}?{urllib.parse.urlencode(top30_params)}", listitem=li, isFolder=True)
        
        html = self.make_request(url)
        if not html:
            self.end_directory()
            return
        
        matches = self.pornstars_pattern.findall(html)
        seen = set()
        
        for match in matches:
            if len(match) == 3:
                path, thumb, name = match
            else:
                path = match[0]
                thumb = ''
                name = match[1]

            name = name.strip()
            if not name or name in seen or len(name) < 2:
                continue
            if re.match(r'^\d+\.', name):
                continue
            seen.add(name)
            
            full_url = f"{self.base_url}{path}"
            li = xbmcgui.ListItem(label=name)
            if thumb:
                li.setArt({'thumb': thumb, 'icon': thumb})
            else:
                li.setArt({'icon': 'DefaultActor.png'})
            
            url_params = {'mode': '2', 'website': self.name, 'url': full_url}
            xbmcplugin.addDirectoryItem(handle=self.addon_handle, url=f"{sys.argv[0]}?{urllib.parse.urlencode(url_params)}", listitem=li, isFolder=True)
        
        current_page = 1
        page_match = re.search(r'/pornstars/(\d+)', url)
        if page_match:
            current_page = int(page_match.group(1))
        
        page_links = self.pornstars_page_pattern.findall(html)
        next_page_num = current_page + 1
        next_page_path = f"/pornstars/{next_page_num}"
        if next_page_path in page_links or any(f"/pornstars/{next_page_num}" in p for p in page_links):
            self.add_dir('[COLOR blue]Next Page >>>>[/COLOR]', f"{self.base_url}{next_page_path}", 9, self.icons.get('default', self.icon))
        
        self.end_directory()
    
    def show_top30_pornstars(self):
        li = xbmcgui.ListItem(label='[COLOR blue]<< All Pornstars[/COLOR]')
        li.setArt({'icon': self.icons.get('pornstars', self.icon)})
        all_params = {'mode': '9', 'website': self.name, 'url': 'BOOTSTRAP', 'action': 'process_pornstars'}
        xbmcplugin.addDirectoryItem(handle=self.addon_handle, url=f"{sys.argv[0]}?{urllib.parse.urlencode(all_params)}", listitem=li, isFolder=True)
        
        top30 = [
            ('Lisa Ann', '/pornstar/lisa-ann'),
            ('Tori Black', '/pornstar/tori-black'),
            ('Sasha Grey', '/pornstar/sasha-grey'),
            ('Alexis Texas', '/pornstar/alexis-texas'),
            ('Eva Angelina', '/pornstar/eva-angelina'),
            ('Aletta Ocean', '/pornstar/aletta-ocean'),
            ('Shyla Stylez', '/pornstar/shyla-stylez'),
            ('Gianna Michaels', '/pornstar/gianna-michaels'),
            ('Asa Akira', '/pornstar/asa-akira'),
            ('Audrey Bitoni', '/pornstar/audrey-bitoni'),
            ('Phoenix Marie', '/pornstar/phoenix-marie'),
            ('Sophie Dee', '/pornstar/sophie-dee'),
            ('Jenna Haze', '/pornstar/jenna-haze'),
            ('Julia Ann', '/pornstar/julia-ann'),
            ('Jayden Jaymes', '/pornstar/jayden-jaymes'),
            ('Ashlynn Brooke', '/pornstar/ashlynn-brooke'),
            ('Maria Ozawa', '/pornstar/maria-ozawa'),
            ('Faye Reagan', '/pornstar/faye-reagan'),
            ('Carmella Bing', '/pornstar/carmella-bing'),
            ('Lexi Belle', '/pornstar/lexi-belle'),
            ('Rachel Roxxx', '/pornstar/rachel-roxxx'),
            ('Tory Lane', '/pornstar/tory-lane'),
            ('Jenna Presley', '/pornstar/jenna-presley'),
            ('Rachel Starr', '/pornstar/rachel-starr'),
            ('Peter North', '/pornstar/peter-north'),
            ('Rebeca Linares', '/pornstar/rebeca-linares'),
            ('Bree Olson', '/pornstar/bree-olson'),
            ('Lela Star', '/pornstar/lela-star'),
            ('Ava Devine', '/pornstar/ava-devine'),
            ('Angel Dark', '/pornstar/angel-dark'),
        ]
        
        for i, (name, path) in enumerate(top30, 1):
            li = xbmcgui.ListItem(label=f'{i}. {name}')
            li.setArt({'icon': 'DefaultActor.png'})
            
            url_params = {'mode': '2', 'website': self.name, 'url': f"{self.base_url}{path}"}
            xbmcplugin.addDirectoryItem(handle=self.addon_handle, url=f"{sys.argv[0]}?{urllib.parse.urlencode(url_params)}", listitem=li, isFolder=True)
        
        self.end_directory()

    def process_channels(self, url):
        if url == 'BOOTSTRAP':
            url = f"{self.base_url}/channels"
        
        content = self.get_content_type()
        cattype_map = {
            'straight': 'straight',
            'gay': 'gay', 
            'shemale': 'trans'
        }
        cattype = cattype_map.get(content, 'straight')
        
        if self.session:
            self.session.cookies.set('cattype', cattype, domain='www.drtuber.com')
        
        html = self.make_request(url)
        if not html:
            self.end_directory()
            return
        
        channel_pattern = re.compile(r'<a[^>]+href="(/channel/[^"]+)"[^>]+class="[^"]*thumb[^"]*"[^>]*>.*?<img[^>]+(?:src|data-src|data-original)="([^"]+)".*?<span>([^<]+)</span>', re.DOTALL)
        matches = channel_pattern.findall(html)
        seen = set()
        
        for path, thumb, name in matches:
            name = name.strip()
            if not name or name in seen or len(name) < 2:
                continue
            seen.add(name)
            
            li = xbmcgui.ListItem(label=name)
            if thumb:
                li.setArt({'thumb': thumb, 'icon': thumb})
            else:
                li.setArt({'icon': 'DefaultFolder.png'})
            li = self.add_context_menu(li, include_channel_sort=True)
            
            url_params = {'mode': '2', 'website': self.name, 'url': f"{self.base_url}{path}"}
            xbmcplugin.addDirectoryItem(handle=self.addon_handle, url=f"{sys.argv[0]}?{urllib.parse.urlencode(url_params)}", listitem=li, isFolder=True)
        
        current_page = 1
        page_match = re.search(r'/channels/(\d+)', url)
        if page_match:
            current_page = int(page_match.group(1))
        
        page_links = self.channels_page_pattern.findall(html)
        next_page_num = current_page + 1
        next_page_path = f"/channels/{next_page_num}"
        if next_page_path in page_links or any(f"/channels/{next_page_num}" in p for p in page_links):
            self.add_dir('[COLOR blue]Next Page >>>>[/COLOR]', f"{self.base_url}{next_page_path}", 10, self.icons.get('default', self.icon))
        
        self.end_directory()
