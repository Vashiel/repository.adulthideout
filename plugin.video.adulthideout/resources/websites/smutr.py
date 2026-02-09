
import sys
import os
import re
import urllib.parse
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

class Smutr(BaseWebsite):
    NAME = 'Smutr'
    BASE_URL = 'https://smutr.com'
    SEARCH_URL = 'https://smutr.com/videos/?q=%s'
    
    sort_options = ['Date', 'Views', 'Likes']
    sort_paths = {
        'Date': '',
        'Views': '?sortby=post_views_count',
        'Likes': '?sortby=votes_count'
    }

    def __init__(self, addon_handle, addon=None):
        xbmc.log("Smutr: Instantiating class...", xbmc.LOGINFO)
        super(Smutr, self).__init__(self.NAME, self.BASE_URL, self.SEARCH_URL, addon_handle, addon=addon)

    def get_headers(self):
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://smutr.com/",
        }
    
    def make_request(self, url, method='GET', data=None, headers=None):
        xbmc.log(f"Smutr: make_request url={url}", xbmc.LOGINFO)
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
                xbmc.log("Smutr: Cloudscraper missing", xbmc.LOGERROR)
                return None
        except Exception as e:
            xbmc.log(f"Smutr Request Error: {e}", xbmc.LOGERROR)
            return None

    def get_listing(self, url):
        return self.process_content(url)

    def process_content(self, url):
        if url == "SEARCH":
             self.show_search_menu()
             return
             
        if "/categories" in url:
             self.list_categories(url)
             return

        self.add_dir("Search", "SEARCH", 5, self.icons['search'])
        self.add_dir("Categories", self.BASE_URL + "/categories/", 2, self.icons['categories'])
             
        r = self.make_request(url)
        if not r: return
        
        # 1. Extract pagination info from the FULL HTML first
        m_next_btn = re.search(r'data-count-page="(\d+)"', r.text)
        
        # 2. Truncate HTML to avoid 'Trending Categories' at the bottom
        html = r.text
        if "Trending Categories" in html:
            html = html.split("Trending Categories")[0]
        
        snippets = re.split(r'class="thumb-item', html)[1:]
        xbmc.log(f"Smutr: Analyzing {len(snippets)} snippets with Deep Filter...", xbmc.LOGINFO)
        
        processed_items = []
        for item in snippets:
                try:
                    if "/v/" not in item: continue
                    
                    m_url = re.search(r'href="([^"]+)"', item)
                    if not m_url: continue
                    video_url = m_url.group(1)
                    if not video_url.startswith('http'):
                        video_url = urllib.parse.urljoin(self.BASE_URL, video_url)
                    
                    m_title = re.search(r'class="title"><a[^>]+title="([^"]+)"', item)
                    title = m_title.group(1) if m_title else "Unknown"
                    
                    m_thumb = re.search(r'<img[^>]+data-src="([^"]+)"', item)
                    thumb = m_thumb.group(1) if m_thumb else ""
                    if thumb and not thumb.startswith('http'):
                         thumb = urllib.parse.urljoin(self.BASE_URL, thumb)
                    
                    m_dur = re.search(r'<div class="duration">\s*([^<]+)\s*</div>', item)
                    duration = m_dur.group(1).strip() if m_dur else ""

                    processed_items.append({
                        'title': title,
                        'url': video_url,
                        'thumb': thumb,
                        'duration': duration,
                        'snippet': item
                    })
                except: pass

        # --- DEEP FILTER (Parallel Subpage Check) ---
        import concurrent.futures
        
        def is_paid_content(item_data):
            try:
                # First, quick check on snippet/title/url
                t_low = item_data['title'].lower()
                u_low = item_data['url'].lower()
                s_low = item_data['snippet'].lower()
                
                # Immediate filter for obvious ones
                if any(x in u_low for x in ['clips4sale', 'c4s', 'market', 'store']): return True
                if any(x in t_low for x in ['promo', 'trailer', 'preview', 'full video at']): return True
                
                # If duration < 35s, it's very likely an ad
                if item_data['duration']:
                    parts = item_data['duration'].split(':')
                    if len(parts) == 2 and (int(parts[0]) * 60 + int(parts[1])) < 35:
                        return True

                # Deep check subpage
                r_sub = self.make_request(item_data['url'])
                if r_sub:
                    sub_text = r_sub.text.lower()
                    if "clips4sale" in sub_text or "visit store" in sub_text or "buy now" in sub_text:
                        return True
                    # Also check for lack of direct video sources (common for redirect ads)
                    if not any(x in sub_text for x in ['video_url', 'url_hd', 'get_file', '.mp4']):
                        return True
                        
                return False
            except: return False

        # Execute Deep Filter with max 20 threads
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            # Map items to ad-check results
            results = list(executor.map(is_paid_content, processed_items))
            
            for i, is_ad in enumerate(results):
                if not is_ad:
                    item = processed_items[i]
                    self.add_link(f"[COLOR blue]{item['duration']}[/COLOR] {item['title']}", item['url'], 4, item['thumb'], self.fanart)

        # Pagination (Infinite Scroll Logic)
        if m_next_btn:
            current_offset = 0
            if "from=" in url:
                m_off = re.search(r'from=(\d+)', url)
                if m_off: current_offset = int(m_off.group(1))
            
            next_offset = current_offset + 60
            parsed = urllib.parse.urlparse(url)
            qs = urllib.parse.parse_qs(parsed.query)
            qs['from'] = [next_offset]
            new_query = urllib.parse.urlencode(qs, doseq=True)
            next_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}?{new_query}"
            self.add_dir(f"[COLOR green]Next Page >>[/COLOR]", next_url, 2, self.icons['default'])
        
        self.end_directory()

    def list_categories(self, url):
        r = self.make_request(url)
        if not r: return
        html = r.text

        cats = re.findall(r'<a href="(https://smutr.com/videos/[^"]+/)"[^>]*title="([^"]+)"', html)
        
        self.add_dir("Search", "SEARCH", 5, self.icons['search'])
        
        for cat_url, title in cats:
            title = title.replace(' Porn', '').strip()
            self.add_dir(title, cat_url, 2, self.icons['categories'], self.fanart)
        
        self.end_directory()

    def resolve(self, url):
        xbmc.log(f"Smutr: Resolving {url}", xbmc.LOGINFO)
        r = self.make_request(url)
        if not r: return None
        html = r.text
        
        sources = []
        
        m_sd = re.search(r"video_url:\s*'([^']+)'", html)
        if m_sd:
            link = m_sd.group(1)
            sources.append({'url': link, 'quality': 'SD', 'order': 1})

        m_hd = re.search(r"video_alt_url:\s*'([^']+)'", html)
        if m_hd:
            link = m_hd.group(1)
            sources.append({'url': link, 'quality': 'HD', 'order': 2})

        if not sources and "clips4sale.com" in html:
            self.notify_error("Premium external content (Clips4Sale)")
            return None

        sources.sort(key=lambda x: x['order'], reverse=True)
        
        if sources:
            stream_url = sources[0]['url']
            headers = self.get_headers()
            stream_url_auth = f"{stream_url}|User-Agent={urllib.parse.quote(headers['User-Agent'])}&Referer={urllib.parse.quote(self.BASE_URL)}"
            return stream_url_auth
        
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

    def search(self, query):
        if not query:
             return
        url = self.SEARCH_URL % urllib.parse.quote(query)
        self.process_content(url)
