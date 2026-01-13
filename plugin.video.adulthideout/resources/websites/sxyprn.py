import os
import re
import sys
import json
import urllib.parse
import urllib.request
import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
from resources.lib.base_website import BaseWebsite

class SxyPrnWebsite(BaseWebsite):
    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="sxyprn",
            base_url="https://sxyprn.com",
            search_url="https://sxyprn.com/{}.html",
            addon_handle=addon_handle,
            addon=addon
        )
        self.sort_options = ["Newest", "Top Rated", "Most Viewed", "Orgasmic"]
        self.content_types = ["All"]  # SxyPrn doesn't have separate content sections
        
        self.sort_paths = {
            0: "/",                     # Newest (default)
            1: "/popular/top-pop.html",  # Top Rated
            2: "/popular/top-viewed.html",  # Most Viewed
            3: "/orgasm"                 # Orgasmic
        }

    def get_start_url_and_label(self):
        sort_id = f"{self.name}_sort_by"
        sort_index = int(self.addon.getSetting(sort_id) or '0')
        
        path = self.sort_paths.get(sort_index, "/")
        label = f"SxyPrn - {self.sort_options[sort_index]}"
        
        if path == "/":
            return self.base_url, label
        return f"{self.base_url}{path}", label

    def make_request(self, url):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"})
            with urllib.request.urlopen(req, timeout=15) as response:
                return response.read().decode('utf-8')
        except Exception:
            return None

    def process_content(self, url):
        if url == self.base_url or url.endswith('BOOTSTRAP') or 'page=' not in url:
            self.add_basic_dirs(url)
        self.process_video_list(url)

    def add_basic_dirs(self, current_url):
        """Add search and categories navigation"""
        self.add_dir('[COLOR blue]Search[/COLOR]', '', 5, self.icons.get('search'))
        self.add_dir('Categories (Tags)', f'{self.base_url}/searches/0.html', 8, self.icons.get('categories'))

    def process_video_list(self, url, page=1):
        if page > 1:
            if url == self.base_url or url == self.base_url + '/':
                url = f"{self.base_url}/{page}.html"
            elif re.search(r'\d+\.html$', url):
                 url = re.sub(r'(\d+)\.html$', f'{page}.html', url)
            else:
                 url = f"{url.rstrip('/')}/{page}.html"

        content = self.make_request(url)
        if not content:
            self.notify_error(f"Failed to load: {url}")
            self.end_directory()
            return

        blocks = re.split(r"<div class='post_el_small[^>]*'>", content)[1:]
        
        items_added = 0
        for block in blocks:
            link_match = re.search(r"<a class='tdn post_time' href='(/post/[^']+)'[^>]*title='([^']+)'", block)
            if not link_match:
                continue
                
            video_rel = link_match.group(1)
            video_url = urllib.parse.urljoin(self.base_url, video_rel)
            
            title_raw = link_match.group(2)
            title = re.sub(r'\{[^\}]+\}|https?://\S+', '', title_raw).strip()
            title = re.sub(r'\s+', ' ', title).strip()
            
            thumb_match = re.search(r"data-src='([^']+)'", block)
            thumb = ""
            if thumb_match:
                thumb = thumb_match.group(1)
                if thumb.startswith("//"):
                    thumb = "https:" + thumb
                
            dur_match = re.search(r"class='duration_small'[^>]*>([^<]+)", block)
            duration = dur_match.group(1) if dur_match else ""
            
            info = {'duration': duration} if duration else None
            self.add_link(title, video_url, 4, thumb, self.fanart, info_labels=info)
            items_added += 1

        if items_added > 0:
             self.add_next_page(url, page)
        else:
             if page == 1:
                 self.notify_error("No videos found")
                 
        self.end_directory()

    def add_next_page(self, url, page):
        next_page = page + 1
        if url == self.base_url or url == self.base_url + '/':
             next_url = f"{self.base_url}/{next_page}.html"
        elif re.search(r'\d+\.html$', url):
             next_url = re.sub(r'(\d+)\.html$', f'{next_page}.html', url)
        else:
             next_url = f"{url.rstrip('/')}/{next_page}.html"

        self.add_dir(f"[COLOR blue]Next Page ({next_page}) >>[/COLOR]", next_url, 2, self.icons.get('default'))

    def process_categories(self, url):
        """Parse the tags/searches page and list all categories"""
        content = self.make_request(url)
        if not content:
            self.notify_error("Failed to load categories")
            self.end_directory()
            return
        
        categories = []
        
        tag_links = re.findall(r"href='(/([A-Za-z0-9-]+)\.html\?sm=trending[^']*)'", content)
        
        for full_link, tag_name in tag_links:
            if tag_name and len(tag_name) > 1:
                display_name = tag_name.replace('-', ' ').title()
                cat_url = urllib.parse.urljoin(self.base_url, full_link)
                categories.append((display_name, cat_url))
        
        seen = set()
        unique_cats = []
        for name, cat_url in categories:
            key = name.lower()
            if key not in seen:
                seen.add(key)
                unique_cats.append((name, cat_url))
        
        unique_cats.sort(key=lambda x: x[0].lower())
        
        for name, cat_url in unique_cats:
            self.add_dir(name, cat_url, 2, self.icons.get('categories'))
        
        if not unique_cats:
            self.notify_error("No categories found")
            
        self.end_directory()


    def play_video(self, url):
        try:
            addon_path = self.addon.getAddonInfo('path')
            vendor_path = os.path.join(addon_path, 'resources', 'lib', 'vendor')
            if vendor_path not in sys.path:
                sys.path.insert(0, vendor_path)
                
            import requests
        except ImportError:
            self.notify_error("Requests module missing")
            return

        session = requests.Session()
        session.headers.update({
             "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
             "Referer": "https://sxyprn.com/"
        })

        try:
            r = session.get(url, timeout=15)
            response = r.text
        except Exception as e:
            self.notify_error(f"Failed to load page: {e}")
            return

        pid_m = re.search(r"pid:'([^']+)'", response)
        ut_m = re.search(r"ut:'([^']+)'", response)
        cipid_m = re.search(r"cipid:'([^']+)'", response)
        
        if pid_m and ut_m and cipid_m:
            try:
                post_url = f"{self.base_url}/php/cjs.php"
                params = {
                    'pid': pid_m.group(1),
                    'ut': ut_m.group(1),
                    'cipid': cipid_m.group(1)
                }
                headers = {
                    "X-Requested-With": "XMLHttpRequest",
                    "Referer": url,
                    "Origin": self.base_url
                }
                
                session.post(post_url, data=params, headers=headers, timeout=5)
            except Exception as e:
                xbmc.log(f"[SxyPrn] CJS Post failed: {e}", xbmc.LOGWARNING)


        video_url = None
        
        vnfo_match = re.search(r"data-vnfo='([^']+)'", response)
        if vnfo_match:
            try:
                data = json.loads(vnfo_match.group(1))
                raw_path = list(data.values())[0] if data else None
                
                if raw_path:
                    def ssut51(arg):
                        digits = ''.join(c for c in arg if c.isdigit())
                        return sum(int(d) for d in digits) if digits else 0
                    
                    import base64
                    def boo(ss, es):
                        text = f"{ss}-sxyprn.com-{es}"
                        return base64.b64encode(text.encode()).decode()
                    
                    def preda(tmp):
                        tmp[5] = str(int(tmp[5]) - (ssut51(tmp[6]) + ssut51(tmp[7])))
                        return tmp
                    
                    
                    tmp = raw_path.split("/")
                    
                    if len(tmp) >= 8:
                        ss = ssut51(tmp[6])
                        es = ssut51(tmp[7])
                        tmp[1] = tmp[1] + "8/" + boo(ss, es)
                        
                        tmp = preda(tmp)
                        
                        decoded_path = "/".join(tmp)
                        
                        if decoded_path.startswith('/'):
                            video_url = "https://sxyprn.com" + decoded_path
                        else:
                            video_url = decoded_path
                            
                        xbmc.log(f"[SxyPrn] Decoded video URL: {video_url[:100]}...", xbmc.LOGINFO)
                        
            except Exception as e:
                xbmc.log(f"[SxyPrn] URL decode error: {e}", xbmc.LOGWARNING)
                
        if not video_url:
            self.notify_error("No video source found")
            return

        try:
            from resources.lib.proxy_utils import ProxyController, PlaybackGuard
            
            controller = ProxyController(video_url, session=session)
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
            headers_str = 'User-Agent={}&Referer={}'.format(
                urllib.parse.quote(session.headers['User-Agent']),
                urllib.parse.quote(url)
            )
            li = xbmcgui.ListItem(path=video_url + '|' + headers_str)
            li.setMimeType('video/mp4')
            li.setProperty('IsPlayable', 'true')
            xbmcplugin.setResolvedUrl(self.addon_handle, True, li)
