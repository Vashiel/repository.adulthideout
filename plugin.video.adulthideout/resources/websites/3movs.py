from resources.lib.base_website import BaseWebsite
import re
import sys
import urllib.parse
import html as html_module

class ThreeMovs(BaseWebsite):
    def __init__(self, addon_handle, addon=None):
        super(ThreeMovs, self).__init__('3movs', 'https://www.3movs.com', 'https://www.3movs.com/search_videos/?q={}', addon_handle, addon)
        self.provider = "3Movs"
        
        # Site Sorting Options
        self.sort_options = ['Latest', 'Most Viewed', 'Top Rated', 'Longest']
        self.sort_paths = {
            'Latest': '/videos/',
            'Most Viewed': '/most-viewed/all-time/',
            'Top Rated': '/top-rated/all-time/',
            'Longest': '/longest/'
        }

    def make_request(self, url):
        import requests
        import time
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': self.base_url,
            'Connection': 'keep-alive',
        }
        for attempt in range(3):
            try:
                response = requests.get(url, headers=headers, timeout=15)
                if response.status_code == 200:
                    return response.text
                elif response.status_code == 404:
                    self.logger.warning(f"404 Error: {url}")
                    return None
                else:
                    self.logger.warning(f"Attempt {attempt + 1}: Error {response.status_code} fetching {url}")
            except Exception as e:
                self.logger.warning(f"Attempt {attempt + 1}: Exception fetching {url}: {e}")
            time.sleep(1)
        return None

    def process_content(self, url, query=None, page=1):
        if not url or url == "BOOTSTRAP":
             url, _ = self.get_start_url_and_label()
        
        current_url = url
        if page > 1:
            # Explicit pagination URL construction
            if '/search_videos/' in url:
                # https://www.3movs.com/search_videos/2/?q=teen
                if '?' in url:
                    base, query_str = url.split('?', 1)
                    current_url = f"{base.rstrip('/')}/{page}/?{query_str}"
                else:
                    current_url = f"{url.rstrip('/')}/{page}/"
            elif '/categories/' in url:
                # https://www.3movs.com/categories/cat-name/2/
                current_url = f"{url.rstrip('/')}/{page}/"
            elif '/videos/' in url:
                # https://www.3movs.com/videos/2/
                current_url = f"{url.rstrip('/')}/{page}/"
            else:
                # Generic fallback
                if '?' in url:
                    base, query_str = url.split('?', 1)
                    current_url = f"{base.rstrip('/')}/{page}/?{query_str}"
                else:
                    current_url = f"{url.rstrip('/')}/{page}/"

        page_html = self.make_request(current_url)
        if not page_html:
            self.end_directory()
            return

        is_category_context = ('/categories/' in current_url and not current_url.endswith('/categories/'))
        is_search_context = ('/search_videos/' in current_url)
        
        # Always add Search and Categories for easy navigation
        self.add_dir('Search', '', 5, self.icons.get('search'), name_param=self.name)
        self.add_dir('Categories', f"{self.base_url}/categories/", 8, self.icons.get('categories'), name_param=self.name)

        # Video Item Parsing
        # <div class="item thumb  ">...<a class="wrap_image" href="URL" title="TITLE">
        # <img ... data-src="THUMB" ...>
        # <div class="time">DURATION</div>
        
        # Log for debugging
        self.logger.info(f"Processing content for URL: {current_url}")

        # More robust parsing: split by item and parse each
        blocks = re.split(r'<div[^>]+class=["\'][^"\']*item thumb', page_html)[1:]
        
        # Fallback split if class parsing is weird
        if not blocks:
            blocks = re.split(r'<div[^>]+item thumb', page_html)[1:]
            
        found_count = 0
        
        for block in blocks:
            v_url_match = re.search(r'href=["\'](https?://www\.3movs\.com/videos/[^"\']+)["\']', block)
            v_title_match = re.search(r'title=["\']([^"\']+)["\']', block)
            v_thumb_match = re.search(r'data-src=["\']([^"\']+)["\']', block)
            v_duration_match = re.search(r'<div[^>]+time[^>]*>([^<]+)</div>', block)
            
            if v_url_match and v_title_match:
                v_url = v_url_match.group(1)
                v_title = html_module.unescape(v_title_match.group(1))
                v_thumb = v_thumb_match.group(1) if v_thumb_match else self.icons.get('default')
                v_duration = v_duration_match.group(1) if v_duration_match else ""
                
                info = {
                    'title': v_title,
                    'duration': self.convert_duration(v_duration)
                }
                self.add_link(v_title, v_url, 4, v_thumb, self.fanart, info_labels=info)
                found_count += 1

        self.logger.info(f"Found {found_count} videos on page")

        # Pagination: check if "Next" exists
        if 'Next' in page_html or 'icon-arrow-right' in page_html:
            self.add_dir('Next Page >>', url, 2, self.icons.get('default'), name_param=self.name, page=page + 1)

        self.end_directory()

    def process_categories(self, url):
        page_html = self.make_request(url)
        if not page_html:
            self.end_directory()
            return

        # Category Item Parsing
        # <div class="thumb_cat item">...<a class="th_cat" href="URL" title="TITLE">
        # <img ... data-src="THUMB" ...>
        # <div class="title">TITLE <span>COUNT</span></div>
        
        cat_pattern = r'<div[^>]+thumb_cat item[^>]*>.*?<a[^>]+href=["\'](https?://www\.3movs\.com/categories/[^"\']+)["\'][^>]+title=["\']([^"\']+)["\'].*?data-src=["\']([^"\']+)["\'].*?<div[^>]+title[^>]*>(.*?)</div>'
        cats = re.findall(cat_pattern, page_html, re.DOTALL)
        
        for c_url, c_title, c_thumb, c_inner_html in cats:
            count_match = re.search(r'<span>([^<]+)</span>', c_inner_html)
            count = count_match.group(1) if count_match else ""
            display_title = f"{html_module.unescape(c_title)} ({count})"
            self.add_dir(display_title, c_url, 2, c_thumb, name_param=self.name)

        self.end_directory()

    def play_video(self, url):
        import xbmcgui
        import xbmcplugin
        import sys
        
        page_html = self.make_request(url)
        if not page_html:
            return

        # KVS flashvars pattern
        player_config = re.search(r'var\s+flashvars\s*=\s*({.*?});', page_html, re.DOTALL)
        stream_url = None
        
        if player_config:
            config_json = player_config.group(1)
            # Find video_url and video_alt_url
            hq_match = re.search(r'video_url:\s*[\'"](.*?)[\'"]', config_json)
            lq_match = re.search(r'video_alt_url:\s*[\'"](.*?)[\'"]', config_json)
            
            hq_url = hq_match.group(1) if hq_match else None
            lq_url = lq_match.group(1) if lq_match else None
            
            # Always prefer HQ as requested by user, bypass dialog
            stream_url = hq_url or lq_url

        if stream_url:
            try:
                from resources.lib.proxy_utils import ProxyController, PlaybackGuard
                import xbmc, xbmcplugin
                
                # Use same UA as in make_request
                ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                
                upstream_headers = {
                    'User-Agent': ua,
                    'Referer': self.base_url,
                    'Accept-Encoding': 'identity',
                }
                
                ctrl = ProxyController(
                    upstream_url=stream_url,
                    upstream_headers=upstream_headers,
                    cookies=None,
                    use_urllib=True, # Improved seeking performance
                    skip_resolve=True,
                )
                local_url = ctrl.start()
                
                self.logger.info(f"3Movs: Proxy started at {local_url}")
                
                li = xbmcgui.ListItem(path=local_url)
                li.setProperty("IsPlayable", "true")
                li.setMimeType("video/mp4")
                li.setContentLookup(False)
                xbmcplugin.setResolvedUrl(int(self.addon_handle), True, listitem=li)
                
                # Guard to stop proxy after playback
                player = xbmc.Player()
                monitor = xbmc.Monitor()
                guard = PlaybackGuard(player, monitor, local_url, ctrl, idle_timeout=60 * 60)
                guard.start()
                
            except Exception as e:
                self.logger.error(f"3Movs proxy failed: {e}")
                # Fallback to direct resolution
                ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                final_stream_url = stream_url + f"|User-Agent={urllib.parse.quote(ua)}&Referer={urllib.parse.quote(self.base_url)}"
                li = xbmcgui.ListItem(path=final_stream_url)
                xbmcplugin.setResolvedUrl(int(self.addon_handle), True, listitem=li)
        else:
            self.notify_error("Could not extract stream URL.")
