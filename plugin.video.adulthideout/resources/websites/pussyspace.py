
import sys
import os
import re
import urllib.parse
import codecs
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
except Exception:
    pass

try:
    import cloudscraper
    _HAS_CF = True
except ImportError:
    _HAS_CF = False

class PussySpace(BaseWebsite):
    NAME = "PussySpace"
    BASE_URL = "https://www.pussyspace.com/"
    SEARCH_URL = BASE_URL + "search?q={}"
    CATEGORIES_URL = BASE_URL + "channels/"
    
    sort_options = ['Recently Posted', 'Top Rated', 'Most Popular', 'Random Porn', 'Movies']
    sort_paths = {
        'Recently Posted': '',
        'Top Rated': 'best/day/',
        'Most Popular': 'mostpopular/',
        'Random Porn': 'video/random/',
        'Movies': 'video/movies/'
    }

    def __init__(self, addon_handle, addon=None):
        xbmc.log("PussySpace: Instantiating class...", xbmc.LOGINFO)
        super(PussySpace, self).__init__(self.NAME, self.BASE_URL, self.SEARCH_URL, addon_handle, addon=addon)

    def get_headers(self):
        return {
            'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            'Referer': self.BASE_URL
        }
    
    def make_request(self, url, method='GET', data=None, headers=None):
        xbmc.log(f"PussySpace: make_request url={url}", xbmc.LOGINFO)
        if not headers:
            headers = self.get_headers()
            
        try:
            if _HAS_CF:
                scraper = cloudscraper.create_scraper(browser={'custom': headers['User-Agent']})
                if method == 'GET':
                    r = scraper.get(url, headers=headers, timeout=20)
                else:
                    r = scraper.post(url, data=data, headers=headers, timeout=20)
                return r
            else:
                xbmc.log("PussySpace: Cloudscraper missing", xbmc.LOGERROR)
                return None
        except Exception as e:
            xbmc.log(f"PussySpace Request Error: {e}", xbmc.LOGERROR)
            return None

    def _unpack_dean_edwards(self, p, a, c, k):
        def baseN(num, b):
            chars = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
            return ((num == 0) and "0") or (baseN(num // b, b).lstrip("0") + chars[num % b])

        try:
            d = {}
            for i in range(c):
                key = baseN(i, a)
                d[key] = k[i] if i < len(k) and k[i] else key

            unpacked = re.sub(r'\b\w+\b', lambda m: d.get(m.group(), m.group()), p)
            return unpacked
        except Exception as e:
            xbmc.log(f"PussySpace Unpack error: {e}", xbmc.LOGERROR)
            return None

    def _decode_rot13(self, text):
        if not text: return ""
        try:
            return codecs.decode(text, 'rot_13')
        except:
            return text

    def resolve(self, url):
        xbmc.log(f"PussySpace: Resolving {url}", xbmc.LOGINFO)
        headers = self.get_headers()
        
        r = self.make_request(url)
        if not r or r.status_code != 200:
            return None
        html = r.text
        
        u64hash = None
        pattern = r"\}\s*\(\s*'((?:[^'\\]|\\.)*)'\s*,\s*['\"]?(\d+)['\"]?\s*,\s*['\"]?(\d+)['\"]?\s*,\s*'((?:[^'\\]|\\.)*)'\.split\('\|'\)"
        packed_matches = re.finditer(pattern, html)
        
        for match in packed_matches:
            try:
                p, a, c, k_str = match.groups()
                unpacked = self._unpack_dean_edwards(p, int(a), int(c), k_str.split('|'))
                if unpacked:
                    msp_match = re.search(r"multiShowPlayer\s*\(\s*\\?['\"]([^'\\]+)\\?['\"]", unpacked)
                    if msp_match:
                        u64hash = msp_match.group(1)
                        break
            except Exception: pass
            
        if not u64hash:
            msp_match = re.search(r"multiShowPlayer\s*\(\s*\\?['\"]([^'\\]+)\\?['\"]", html)
            if msp_match:
                u64hash = msp_match.group(1)
        
        if not u64hash:
            xbmc.log("PussySpace: Could not find player KEY", xbmc.LOGERROR)
            return None

        hs_url = "https://www.pussyspace.com/get/player/xv/"
        hs_data = {"id": u64hash}
        hs_headers = headers.copy()
        hs_headers['X-Requested-With'] = 'XMLHttpRequest'
        hs_headers['Content-Type'] = 'application/x-www-form-urlencoded; charset=UTF-8'
        
        r_hs = self.make_request(hs_url, method='POST', data=hs_data, headers=hs_headers)
        if not r_hs or r_hs.status_code != 200:
            return None
            
        stream_url = None
        rb_match = re.search(r'reversebuffer\?u64hash=([^"&\s]+)', r_hs.text)
        if rb_match:
            stream_url = f"https://www.pussyspace.com/reversebuffer?u64hash={rb_match.group(1)}&hls.m3u8"
        
        if not stream_url:
            file_match = re.search(r'file:"([^"]+hls\.m3u8[^"]*)"', r_hs.text)
            if file_match:
                stream_url = file_match.group(1)

        if stream_url:
            try:
                scraper = cloudscraper.create_scraper(browser={'custom': headers['User-Agent']})
                r_rb = scraper.head(stream_url, headers=headers, allow_redirects=True, timeout=10)
                final_url = r_rb.url
                xbmc.log(f"PussySpace: Final CDN URL: {final_url}", xbmc.LOGINFO)
                
                cookie_str = "; ".join([f"{k}={v}" for k, v in scraper.cookies.items()])
                
                play_url = f"{final_url}|User-Agent={urllib.parse.quote(headers['User-Agent'])}&Referer={urllib.parse.quote(self.BASE_URL)}"
                if cookie_str:
                     play_url += f"&Cookie={urllib.parse.quote(cookie_str)}"
                return play_url
                
            except Exception as e:
                xbmc.log(f"PussySpace Redirect Error: {e}", xbmc.LOGERROR)
        
        return None

    def play_video(self, url):
        video_url = self.resolve(url)
        if video_url:
            li = xbmcgui.ListItem(path=video_url)
            li.setProperty('IsPlayable', 'true')
            xbmcplugin.setResolvedUrl(self.addon_handle, True, li)
        else:
            self.notify_error("Video resolution failed")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())

    def get_listing(self, url):
        return self.process_content(url)

    def process_content(self, url):
        if url == "SEARCH":
             self.show_search_menu()
             return

        self.add_dir("Search", "SEARCH", 5, self.icons['search'])
        self.add_dir("Categories", self.CATEGORIES_URL, 2, self.icons['categories'])

        if 'channels' in url or '/categories' in url:
            self.process_categories(url)
            return
             
        r = self.make_request(url)
        if not r: return
        html = r.text
        
        thumb_map = {}
        va_match = re.search(r'var vid_array = "([^"]+)"', html)
        if va_match:
            decoded_va = self._decode_rot13(va_match.group(1))
            for entry in decoded_va.split('|'):
                parts = entry.split(';')
                if len(parts) >= 4:
                     thumb_map[parts[0]] = parts[3]

        item_pattern = r'<div id="vid_(\d+)" class="video_div">.*?<a[^>]*href="([^"]+)"[^>]*>.*?<img[^>]*src="([^"]+)"[^>]*>.*?<div class="ts3"><a[^>]*>(.*?)</a>'
        matches = re.finditer(item_pattern, html, re.DOTALL)
        
        for match in matches:
            v_id, v_url, v_src, v_title = match.groups()
            
            duration = ""
            dur_match = re.search(r'<span class="video_duration">([^<]+)</span>', html[match.start():match.start()+1000])
            if dur_match:
                duration = dur_match.group(1).strip()
            
            v_title = re.sub(r'<[^>]+>', '', v_title).strip()
            if len(v_title) < 2:
                 t_match = re.search(r'title="([^"]+)"', html[match.start():match.end()])
                 if t_match: v_title = t_match.group(1)

            final_thumb = thumb_map.get(v_id, v_src)
            if not final_thumb.startswith('http'):
                 final_thumb = urllib.parse.urljoin(self.BASE_URL, final_thumb)
            
            if not v_url.startswith('http'):
                 v_url = urllib.parse.urljoin(self.BASE_URL, v_url)

            disp_title = f"[COLOR blue]{duration}[/COLOR] {v_title}" if duration else v_title
            
            self.add_link(disp_title, v_url, 4, final_thumb, self.fanart)

        page_match = re.search(r'/(\d+)/?$', url)
        current_page = int(page_match.group(1)) if page_match else 1
        next_page = current_page + 1
        
        if re.search(item_pattern, html):
             if page_match:
                 next_url = re.sub(r'/\d+/?$', f'/{next_page}/', url)
             else:
                 next_url = url.rstrip('/') + f'/{next_page}/'
             self.add_dir("[COLOR green]Next Page >>[/COLOR]", next_url, 2, self.icons['default'])
        
        self.end_directory()

    def process_categories(self, url):
        html = self.make_request(url).text
        if not html: return
        
        pattern = r"<div class='cat_name'><a href=['\"]([^'\"]+)['\"]>([^<]+)</a>"
        matches = re.finditer(pattern, html, re.IGNORECASE)
        
        for match in matches:
            cat_url, name = match.groups()
            
            if not cat_url.startswith('http'):
                cat_url = urllib.parse.urljoin(self.BASE_URL, cat_url)
                
            self.add_dir(name.strip(), cat_url, 2, self.icons['categories'])
            
        self.end_directory()
