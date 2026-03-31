
import re
import sys
import json
import html
import base64
import urllib.parse
import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon
import xbmcvfs
import hashlib
import os
import sys
import threading
import http.cookiejar
import socket
import socketserver
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from resources.lib.base_website import BaseWebsite

try:
    import cloudscraper
    _HAS_CF = True
except ImportError:
    _HAS_CF = False
_PROXY_INSTANCE = None
_PROXY_LOCK = threading.Lock()

class ThumbProxyHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args): return

    def do_GET(self):
        query = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(query)
        url = params.get('url', [None])[0]
        encoded = params.get('b64', [None])[0]

        if not url and encoded:
            padded = encoded + ('=' * (-len(encoded) % 4))
            try:
                url = base64.urlsafe_b64decode(padded.encode('ascii')).decode('utf-8')
            except Exception:
                url = None
        
        if not url:
            self.send_error(400, "Missing URL parameter")
            return

        try:
            # Use persistent session from server to avoid connection overhead
            xbmc.log(f"[Tube8Proxy] Requesting: {url}", xbmc.LOGINFO)
            resp = self.server.session.get(url, timeout=10, stream=True)
            if resp.status_code == 200:
                self.send_response(200)
                for k, v in resp.headers.items():
                    if k.lower() in ['content-type', 'content-length', 'cache-control', 'expires']:
                        self.send_header(k, v)
                self.end_headers()
                for chunk in resp.iter_content(chunk_size=8192):
                    self.wfile.write(chunk)
                xbmc.log(f"[Tube8Proxy] Completed: {url}", xbmc.LOGINFO)
            else:
                self.send_error(resp.status_code, f"Upstream error: {resp.status_code}")
                xbmc.log(f"[Tube8Proxy] Upstream Error {resp.status_code} for {url}", xbmc.LOGERROR)
        except Exception as e:
            self.send_error(500, str(e))
            xbmc.log(f"[Tube8Proxy] Exception for {url}: {e}", xbmc.LOGERROR)

class ThumbProxyServer(ThreadingHTTPServer):
    def __init__(self, server_address, RequestHandlerClass, scraper):
        self.scraper = scraper
        import requests
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://www.tube8.com/'
        })
        # Set mount pool size to handle seek bar concurrency (usually 10-20 images)
        adapter = requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=20)
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)
        super().__init__(server_address, RequestHandlerClass)

def start_thumb_proxy(scraper):
    global _PROXY_INSTANCE, _PROXY_LOCK
    with _PROXY_LOCK:
        if _PROXY_INSTANCE:
            return _PROXY_INSTANCE
        
        # Find a free port
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('127.0.0.1', 0))
            port = s.getsockname()[1]
        
        server = ThumbProxyServer(('127.0.0.1', port), ThumbProxyHandler, scraper)
        t = threading.Thread(target=server.serve_forever, name="Tube8ThumbProxy", daemon=True)
        t.start()
        _PROXY_INSTANCE = port
        xbmc.log(f"[Tube8] Thumbnail Proxy started on port {port}", xbmc.LOGINFO)
        return port

class Tube8(BaseWebsite):
    NAME = 'tube8'
    BASE_URL = 'https://www.tube8.com'
    SEARCH_URL = 'https://www.tube8.com/searches.html?q=%s&page=%d'
    
    sort_options = ['Newest', 'Most Viewed', 'Top Rated', 'Longest']
    sort_paths = {
        'Newest': '/newest.html/',
        'Most Viewed': '/mostviewed.html/',
        'Top Rated': '/top.html/',
        'Longest': '/longest.html/'
    }
    
    search_sort_map = {
        'Newest': 'newest',
        'Most Viewed': 'views',
        'Top Rated': 'rating',
        'Longest': 'longest'
    }

    def __init__(self, addon_handle, addon=None):
        super(Tube8, self).__init__(self.NAME, self.BASE_URL, self.SEARCH_URL, addon_handle, addon=addon)
        self.scraper = None
        self._initialize_scraper()
        self.proxy_port = start_thumb_proxy(self.scraper)
        self._set_age_cookie()

    def _get_proxied_thumb(self, url):
        if not url: return self.icon
        url = html.unescape(url)
        if not url.startswith('http'):
            if any(url.startswith(p) for p in ['special://', 'C:', '/', 'special/']):
                return url
            url = urllib.parse.urljoin(self.BASE_URL, url)
        encoded = base64.urlsafe_b64encode(url.encode('utf-8')).decode('ascii').rstrip('=')
        return f"http://127.0.0.1:{self.proxy_port}/thumb.jpg?b64={encoded}"

    def _initialize_scraper(self):
        if _HAS_CF:
            self.scraper = cloudscraper.create_scraper()
        else:
            import requests
            self.scraper = requests.Session()
        
        self.scraper.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': self.BASE_URL
        })
        try:
            self.scraper.get(self.BASE_URL, timeout=10)
        except:
            pass

    def add_dir(self, name, url, mode, icon=None, fanart=None, context_menu=None, name_param=None, info_labels=None, **kwargs):
        icon = self._get_proxied_thumb(icon) if icon and icon != self.icon else (icon or self.icon)
        super(Tube8, self).add_dir(name, url, mode, icon, fanart, context_menu, name_param, info_labels, **kwargs)

    def add_link(self, name, url, mode, icon, fanart, context_menu=None, info_labels=None):
        icon = self._get_proxied_thumb(icon) if icon and icon != self.icon else (icon or self.icon)
        super(Tube8, self).add_link(name, url, mode, icon, fanart, context_menu, info_labels)

    def _set_age_cookie(self):
        try:
            from http.cookiejar import Cookie
            age_cookie = Cookie(
                version=0, name='access', value='1', port=None, port_specified=False,
                domain='.tube8.com', domain_specified=True, domain_initial_dot=True,
                path='/', path_specified=True, secure=False, expires=None, discard=True,
                comment=None, comment_url=None, rest={}
            )
            # We don't have a persistent session/opener in BaseWebsite usually, 
            # but cloudscraper/requests handles cookies. 
            # If used with cloudscraper, we might need a session.
            pass
        except: pass

    def get_headers(self, referer=None):
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            "Referer": referer or self.BASE_URL + "/",
            "Cookie": "access=1"
        }

    def make_request(self, url, method='GET', data=None, headers=None):
        if not headers:
            headers = self.get_headers(referer=url)
        try:
            if _HAS_CF:
                if not self.scraper:
                    self.scraper = cloudscraper.create_scraper(browser={'custom': headers['User-Agent']})
                if method == 'GET':
                    r = self.scraper.get(url, headers=headers, timeout=20)
                else:
                    r = self.scraper.post(url, data=data, headers=headers, timeout=20)
                return r
            else:
                import requests
                if not self.scraper:
                    self.scraper = requests.Session()
                if method == 'GET':
                    return self.scraper.get(url, headers=headers, timeout=20)
                else:
                    return self.scraper.post(url, data=data, headers=headers, timeout=20)
        except Exception as e:
            xbmc.log(f"Tube8 Request Error for {url}: {e}", xbmc.LOGERROR)
            return None

    def get_listing(self, url):
        return self.process_content(url)

    def process_content(self, url):
        if url == "SEARCH":
            self.show_search_menu()
            return

        if "/categories.html" in url:
            self.list_categories(url)
            return

        if not any(x in url for x in ['SEARCH', 'categories.html']):
            self.add_dir("Search", "SEARCH", 5, self.icons['search'])
            self.add_dir("Categories", self.BASE_URL + "/categories.html", 8, self.icons['categories'])

        r = self.make_request(url)
        if not r: 
            xbmc.log(f"Tube8: Request failed (status {r.status_code if r else 'None'}) for {url}", xbmc.LOGERROR)
            self.end_directory()
            return

        html_content = r.text

        article_pattern = r'(<article class="video-box[^"]*.*?</article>)'
        snippets = re.findall(article_pattern, html_content, re.DOTALL | re.IGNORECASE)
        for item in snippets:
            try:
                m_url = re.search(
                    r'<a href="([^"]+)"[^>]*class="[^"]*(?:tm_video_link|video-title-text)[^"]*"',
                    item,
                    re.DOTALL | re.IGNORECASE,
                )
                if not m_url:
                    continue
                video_url = urllib.parse.urljoin(self.BASE_URL, html.unescape(m_url.group(1)))

                title = ""
                m_title = re.search(
                    r'class="[^"]*video-title-text[^"]*"[^>]*>\s*(?:<span>)?(.*?)(?:</span>)?\s*</a>',
                    item,
                    re.DOTALL | re.IGNORECASE,
                )
                if m_title:
                    title = re.sub(r'<[^>]+>', '', m_title.group(1)).strip()

                if not title:
                    m_alt = re.search(r'alt="([^"]+)"', item, re.IGNORECASE)
                    if m_alt:
                        title = m_alt.group(1).strip()

                if not title:
                    title = "Unknown Video"
                title = html.unescape(re.sub(r'\s+', ' ', title))

                thumb = ""
                for thumb_pattern in (
                    r'data-poster="([^"]+)"',
                    r'data-src="([^"]+)"',
                    r'poster="([^"]+)"',
                    r'src="([^"]+)"',
                ):
                    m_thumb = re.search(thumb_pattern, item, re.IGNORECASE)
                    if not m_thumb:
                        continue
                    candidate = html.unescape(m_thumb.group(1))
                    if candidate.startswith('data:image'):
                        continue
                    thumb = candidate
                    break

                if thumb and not thumb.startswith('http'):
                    thumb = urllib.parse.urljoin(self.BASE_URL, thumb)

                duration = ""
                m_dur = re.search(r'class="[^"]*tm_video_duration[^"]*"[^>]*>\s*<span>(.*?)</span>', item, re.DOTALL | re.IGNORECASE)
                if m_dur:
                    duration = re.sub(r'<[^>]+>', '', m_dur.group(1)).strip()
                    duration = re.sub(r'\s+', ' ', duration)

                label = f"[{duration}] {title}" if duration else title
                self.add_link(label, video_url, 4, thumb, self.fanart)
            except Exception:
                pass

        next_url = None
        m_next = re.search(r'<link rel="next" href="([^"]+)"', html_content, re.IGNORECASE)
        if not m_next:
            m_next = re.search(r'href="([^"]+)"[^>]*class="[^"]*next[^"]*"', html_content, re.IGNORECASE)
        if not m_next:
            m_next = re.search(r'<a[^>]+href="([^"]+)"[^>]*>\s*Next\s*</a>', html_content, re.IGNORECASE)
        if m_next:
            next_url = urllib.parse.urljoin(self.BASE_URL, html.unescape(m_next.group(1)))

        if next_url:
            self.add_dir("[COLOR green]Next Page >>[/COLOR]", next_url, 2, self.icons['default'])

        self.end_directory()

    def process_categories(self, url):
        self.list_categories(url)

    def list_categories(self, url):
        r = self.make_request(url)
        if not r: return
        html_content = r.text
        
        # Highly targeted category extraction
        items = re.findall(r'class="categoryBox[^"]*".*?href="([^"]+)".*?alt="([^"]+)"', html_content, re.DOTALL)
        if not items:
            items = re.findall(r'href="(/cat/[^"]+)".*?tm_category_title[^>]*>([^<]+)', html_content, re.DOTALL)
            
        seen = set()
        for cat_url, title in items:
            if cat_url in seen: continue
            seen.add(cat_url)
            self.add_dir(title.strip(), urllib.parse.urljoin(self.BASE_URL, cat_url), 2, self.icons['categories'])
        self.end_directory()

    def resolve(self, url):
        r = self.make_request(url)
        if not r: return None
        html_content = r.text
        
        # MindGeek mediaDefinition extraction
        m = re.search(r'mediaDefinition\s*:\s*(\[.*?\]),', html_content, re.DOTALL)
        if m:
            try:
                defs = json.loads(m.group(1))
                
                # Check for HLS first (Better for seeking/buffering)
                hls_stream = next((d for d in defs if d.get('format') == 'hls' and d.get('videoUrl')), None)
                if hls_stream:
                    stream_url = hls_stream['videoUrl'].replace('\\/', '/')
                    if '/media/' in stream_url:
                        rj = self.make_request(stream_url)
                        if rj:
                            try:
                                defs_inner = rj.json()
                                hls_inner = next((d for d in defs_inner if d.get('format') == 'hls' and d.get('videoUrl')), None)
                                if hls_inner:
                                    stream_url = hls_inner['videoUrl'].replace('\\/', '/')
                            except: pass
                    
                    return stream_url + "|User-Agent=" + urllib.parse.quote(self.get_headers()['User-Agent']) + "&Referer=" + urllib.parse.quote(self.BASE_URL)

                mp4_streams = [d for d in defs if (d.get('format') == 'mp4' or 'mp4' in d.get('videoUrl', '')) and d.get('videoUrl')]
                if mp4_streams:
                    def get_q(d):
                        q = str(d.get('quality', '0'))
                        q = re.sub(r'\D', '', q)
                        return int(q) if q else 0
                    
                    best = max(mp4_streams, key=get_q)
                    stream_url = best['videoUrl'].replace('\\/', '/')
                    
                    # If this is a MindGeek API URL (returning JSON), follow it
                    if '/media/' in stream_url:
                        rj = self.make_request(stream_url)
                        if rj:
                            try:
                                defs_inner = rj.json()
                                mp4_inner = [d for d in defs_inner if (d.get('format') == 'mp4' or 'mp4' in d.get('videoUrl', '')) and d.get('videoUrl')]
                                if mp4_inner:
                                    best_inner = max(mp4_inner, key=get_q)
                                    stream_url = best_inner['videoUrl'].replace('\\/', '/')
                            except: pass

                    return stream_url + "|User-Agent=" + urllib.parse.quote(self.get_headers()['User-Agent']) + "&Referer=" + urllib.parse.quote(self.BASE_URL)
            except: pass
            
        m_fv = re.search(r'var\s+flashvars_\d+\s*=\s*({.*?});', html_content, re.DOTALL)
        if m_fv:
            try:
                data = json.loads(m_fv.group(1))
                defs = data.get('mediaDefinitions', [])
                
                # Check for HLS first
                hls_stream = next((d for d in defs if d.get('format') == 'hls' and d.get('videoUrl')), None)
                if hls_stream:
                    stream_url = hls_stream['videoUrl'].replace('\\/', '/')
                    if '/media/' in stream_url:
                        rj = self.make_request(stream_url)
                        if rj:
                            try:
                                defs_inner = rj.json()
                                hls_inner = next((d for d in defs_inner if d.get('format') == 'hls' and d.get('videoUrl')), None)
                                if hls_inner:
                                    stream_url = hls_inner['videoUrl'].replace('\\/', '/')
                            except: pass
                    return stream_url + "|User-Agent=" + urllib.parse.quote(self.get_headers()['User-Agent']) + "&Referer=" + urllib.parse.quote(self.BASE_URL)

                mp4_streams = [d for d in defs if (d.get('format') == 'mp4' or 'mp4' in d.get('videoUrl', '')) and d.get('videoUrl')]
                if mp4_streams:
                    def get_q(d):
                        q = str(d.get('quality', '0'))
                        q = re.sub(r'\D', '', q)
                        return int(q) if q else 0
                    best = max(mp4_streams, key=get_q)
                    stream_url = best['videoUrl'].replace('\\/', '/')
                    return stream_url + "|User-Agent=" + urllib.parse.quote(self.get_headers()['User-Agent']) + "&Referer=" + urllib.parse.quote(self.BASE_URL)
            except: pass

        return None

    def play_video(self, url):
        stream_url = self.resolve(url)
        if stream_url:
            li = xbmcgui.ListItem(path=stream_url)
            li.setProperty('IsPlayable', 'true')
            
            # Extract current thumbnail from the list item that triggered this
            # We can't easily get the *source* list item here without passing it, 
            # but we can try to re-extract it or use a generic one.
            # Ideally, we should set the Art to the proxied thumb to avoid Kodi trying to fetch the original
            pass

            xbmcplugin.setResolvedUrl(self.addon_handle, True, li)
        else:
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())

    def search(self, query):
        if not query: return
        
        sel_idx = self.addon.getSetting(f"{self.name}_sort_by")
        try:
            sel_idx = int(sel_idx)
            sort_label = self.sort_options[sel_idx]
        except:
            sort_label = 'Newest'
            
        sort_val = self.search_sort_map.get(sort_label, 'newest')
        
        url = self.SEARCH_URL % (urllib.parse.quote_plus(query), 1) + f"&orderby={sort_val}"
        self.process_content(url)
