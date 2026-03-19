from resources.lib.base_website import BaseWebsite
import re
import sys
import os
import html as html_module

class XXXFiles(BaseWebsite):
    def __init__(self, addon_handle, addon=None):
        super(XXXFiles, self).__init__('xxxfiles', 'https://www.xxxfiles.com', 'https://www.xxxfiles.com/search/{}/', addon_handle, addon)
        self.provider = "XXXFiles"
        
        # Site Sorting Options
        self.sort_options = ['Latest Updates', 'Most Viewed', 'Top Rated']
        self.sort_paths = {
            'Latest Updates': '/latest-updates/',
            'Most Viewed': '/most-popular/',
            'Top Rated': '/top-rated/'
        }

    def make_request(self, url):
        import requests
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': self.base_url
        }
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                return response.text
            else:
                self.logger.warning(f"Error {response.status_code} fetching {url}")
        except Exception as e:
            self.logger.error(f"Exception fetching {url}: {e}")
        return None

    def get_start_url_and_label(self):
        """Returns the starting URL, respecting the saved sort setting."""
        try:
            saved_sort = self.addon.getSetting(f"{self.name}_sort_by")
            sort_idx = int(saved_sort) if saved_sort else 0
        except ValueError:
            sort_idx = 0

        sort_label = "Videos"
        path = "/latest-updates/"
        
        if 0 <= sort_idx < len(self.sort_options):
            sort_option = self.sort_options[sort_idx]
            path = self.sort_paths.get(sort_option, "/latest-updates/")
            sort_label = sort_option

        url = f"{self.base_url}{path}"
        label = f"{self.provider} [COLOR yellow]{sort_label}[/COLOR]"
        return url, label

    def process_content(self, url, query=None, page=1):
        if not url or url == "BOOTSTRAP" or url.strip('/') == self.base_url.strip('/'):
             url, _ = self.get_start_url_and_label()
             
        if not url.startswith('http'):
            url = f"{self.base_url}{url}"

        # Clean base URL for pagination (strip trailing page number)
        base_url = re.sub(r'/\d+/$', '/', url)
        if not base_url.endswith('/'):
            base_url += '/'

        # Build current URL with page number. XXXFiles uses /path/2/
        if page > 1:
            current_url = f"{base_url.rstrip('/')}/{page}/"
        else:
            current_url = url

        page_html = self.make_request(current_url)
        if not page_html:
            self.end_directory()
            return

        is_category_context = ('/categories/' in current_url)
        is_search_context = ('/search/' in current_url)
        
        # UI Elements: Search and Categories only if not in category/search context
        if not is_category_context and not is_search_context:
            self.add_dir('Search', '', 5, self.icons.get('search', ''), name_param=self.name, action='show_search_menu')
            self.add_dir('Categories', f"{self.base_url}/categories/", 8, self.icons.get('categories', ''), name_param=self.name)

        # Video block parsing
        # Structure: <div class="item">...<a href="URL" title="TITLE">...<img data-src="THUMB"...<span class="duration">00:00</span>
        blocks = re.split(r'<div[^>]*class=["\'][^"\']*(?:item|video|thumb|post)[^"\']*["\']\s*>', page_html)[1:]
        
        context_menu = [
            ('Sort by...', f'RunPlugin({sys.argv[0]}?mode=7&action=select_sort_order&website={self.name})')
        ]

        for block in blocks:
            # Only process blocks containing an a-tag with href
            a_match = re.search(r'<a[^>]+href=["\']([^"\']+)["\']', block, re.IGNORECASE)
            if not a_match:
                continue
                
            page_url = a_match.group(1)
            if not page_url.startswith('http'):
                page_url = f"{self.base_url}{page_url}"
                
            # Only accept actual video URLs: /videos/NNNNN/HASH/ or search-result URLs
            # This filters out suggest-model, pagination, category, model links etc.
            is_video_url = bool(re.search(r'/videos/\d+/[a-f0-9]+/', page_url))
            if not is_video_url:
                continue

            # Title - prefer title attribute, fall back to alt attribute on img
            title_match = re.search(r'<img[^>]+alt=["\']([^"\']+)["\']', block, re.IGNORECASE)
            if not title_match:
                title_match = re.search(r'title=["\']([^"\']+)["\']', block, re.IGNORECASE)
            title = html_module.unescape(title_match.group(1)) if title_match else "Unknown"

            # Thumbnail
            thumb_url = self.icons.get('default', '')
            thumb_match = re.search(r'<img[^>]+(?:data-src|data-original|src)=["\']([^"\']+)["\']', block, re.IGNORECASE)
            if thumb_match:
                thumb_url = thumb_match.group(1)
                
            # Duration
            duration = ""
            dur_match = re.search(r'<span[^>]*class=["\'][^"\']*(?:duration|time|length)[^"\']*["\'][^>]*>([\d:]+)</span>', block, re.IGNORECASE)
            if dur_match:
                duration = dur_match.group(1)

            self.add_link(
                name=title,
                url=page_url,
                mode=4,
                icon=thumb_url,
                fanart=self.fanart,
                info_labels={'title': title, 'duration': self.convert_duration(duration)},
                context_menu=context_menu
            )

        # Pagination - look for next page link
        next_page_match = re.search(
            r'href=["\']([^"\']*?/(\d+)/)["\'][^>]*>Next',
            page_html, re.IGNORECASE
        )
        if not next_page_match:
            # Fall back: any pagination present => show next page
            if re.search(r'class=["\'][^"\']*pagination[^"\']*["\']', page_html, re.IGNORECASE):
                next_page = page + 1
                next_url = f"{base_url.rstrip('/')}/{next_page}/"
                self.add_dir(f'Next Page ({next_page})', next_url, 2,
                             self.icons.get('default', ''), name_param=self.name)
        else:
            next_url = next_page_match.group(1)
            if not next_url.startswith('http'):
                next_url = f"{self.base_url}{next_url}"
            next_page_num = next_page_match.group(2)
            self.add_dir(f'Next Page ({next_page_num})', next_url, 2,
                         self.icons.get('default', ''), name_param=self.name)

        self.end_directory()

    def process_categories(self, url):
        page_html = self.make_request(url)
        if not page_html:
            self.end_directory()
            return

        cat_blocks = re.finditer(r'<a[^>]+href=["\']([^"\']+/categories/[^"\']+)["\'][^>]*>(.*?)</a>', page_html, re.IGNORECASE | re.DOTALL)
        added_urls = set()
        
        for match in cat_blocks:
            href = match.group(1)
            inner_html = match.group(2)
            
            if '?' in href or '/latest-updates/' in href or href == 'https://www.xxxfiles.com/categories/':
                continue
                
            if not href.startswith('http'):
                href = f"{self.base_url}{href}"
                
            # Extract title
            title_match = re.search(r'title=["\']([^"\']+)["\']', match.group(0), re.IGNORECASE)
            if title_match:
                title = title_match.group(1)
            else:
                # remove html tags from inner_html
                title = re.sub(r'<[^>]+>', '', inner_html).strip()
                
            if title and href not in added_urls:
                added_urls.add(href)
                
                # Extract image
                thumb_url = self.icons.get('default', '')
                img_match = re.search(r'<img[^>]+(?:data-src|data-original|src)=["\']([^"\']+)["\']', inner_html, re.IGNORECASE)
                if img_match:
                     thumb_url = img_match.group(1)

                self.add_dir(
                    name=html_module.unescape(title.title()),
                    url=href,
                    mode=2,
                    icon=thumb_url,
                    fanart=self.fanart,
                    name_param=self.name
                )
                
        self.end_directory()


    def play_video(self, url):
        import requests, urllib.parse
        from urllib.parse import urlparse
        
        # Browser UA from working curl
        ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36'
        
        # 1. Start a session to capture cookies from xxxfiles.com
        session = requests.Session()
        session.headers.update({'User-Agent': ua, 'Referer': self.base_url})
        
        # Load the video page to get necessary cookies (PHPSESSID, kt_ips)
        page_html = None
        try:
            r_page = session.get(url, timeout=10)
            if r_page.status_code == 200:
                page_html = r_page.text
            self.logger.info(f"XXXFiles: Session cookies after page load: {session.cookies.get_dict()}")
        except Exception as e:
            self.logger.error(f"Error fetching video page {url}: {e}")
            
        if not page_html:
            import xbmcgui, xbmcplugin
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem(path=url))
            return

        # 2. Extract Direct MP4 streams: /get_file/13/....
        # Handle escaped slashes if present in some JS blocks
        clean_html = page_html.replace('\\/', '/')
        stream_matches = list(re.finditer(r'(https?://(?:www\.)?xxxfiles\.com/get_file/[^"\'<>\s]+)', clean_html, re.IGNORECASE))
        
        self.logger.info(f"XXXFiles: Found {len(stream_matches)} stream candidates.")
        
        videos = []
        seen = set()
        for match in stream_matches:
            stream_url = match.group(1)
            # Ensure it has exactly one trailing slash for the xxxfiles redirect logic
            stream_url = stream_url.rstrip('/') + '/'
            
            if stream_url in seen:
                continue
            seen.add(stream_url)
            res_match = re.search(r'_(\d+)m?\.mp4', stream_url)
            resolution = int(res_match.group(1)) if res_match else 0
            self.logger.info(f"XXXFiles: Candidate: {resolution}p -> {stream_url}")
            videos.append((resolution, stream_url))
            
        if not videos:
            self.logger.error("XXXFiles: No video stream extracted from HTML.")
            import xbmcgui, xbmcplugin
            xbmcgui.Dialog().notification(self.provider, "No video stream found.", xbmcgui.NOTIFICATION_ERROR)
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem(path=url))
            return
        
        # Selection logic: Prioritize 480p as it's the one verified in user's curl.
        # Otherwise pick best resolution.
        target_480 = next((v for v in videos if v[0] == 480), None)
        if target_480:
            get_file_url = target_480[1]
        else:
            videos.sort(key=lambda x: x[0], reverse=True)
            get_file_url = videos[0][1]
        
        self.logger.info(f"XXXFiles: Selected stream URL: {get_file_url}")
        
        # Stage 1: Construct critical cookies BEFORE the resolution hop
        url_path = urlparse(url).path
        parts = [p for p in url_path.split('/') if p]
        if len(parts) >= 3 and parts[0] == 'videos':
            v_id = parts[1]
            v_dir = parts[2]
            # Add kt_qparams and kt_tcookie seen in working curl
            kt_qparams = urllib.parse.quote(f"id={v_id}&dir={v_dir}")
            session.cookies.set('kt_qparams', kt_qparams, domain='www.xxxfiles.com')
            session.cookies.set('kt_tcookie', '1', domain='www.xxxfiles.com')
            self.logger.info(f"XXXFiles: Final session cookies before resolution: {session.cookies.get_dict()}")

        # 3. Resolve the full redirect chain manually (xxxfiles -> cdnawm -> ahcdn)
        # Some CDN nodes reject cookies, so we must strip them when leaving xxxfiles.com
        cdn_url = get_file_url
        try:
            current_url = get_file_url
            max_redirects = 5
            redirect_count = 0
            
            # Start with session cookies and video page referer
            current_headers = {
                'User-Agent': ua,
                'Referer': url,
                'Accept': '*/*',
                'Accept-Language': 'de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7'
            }
            
            while redirect_count < max_redirects:
                # Logic: If we are leaving xxxfiles.com, use a fresh request WITHOUT cookies or Referer.
                is_xxxfiles = 'xxxfiles.com' in current_url
                
                if is_xxxfiles:
                    r_cdn = session.get(current_url, allow_redirects=False, stream=True, timeout=10, headers=current_headers)
                else:
                    # CDN nodes often require clean requests (no cookies, no referer)
                    cdn_headers = current_headers.copy()
                    if 'Referer' in cdn_headers: del cdn_headers['Referer']
                    r_cdn = requests.get(current_url, allow_redirects=False, stream=True, timeout=10, headers=cdn_headers)
                
                status = r_cdn.status_code
                self.logger.info(f"XXXFiles: Hop {redirect_count} [{status}]: {current_url}")
                
                if status in (301, 302, 303, 307, 308) and 'Location' in r_cdn.headers:
                    new_url = r_cdn.headers['Location']
                    if new_url.startswith('/'):
                        from urllib.parse import urljoin
                        new_url = urljoin(current_url, new_url)
                    
                    current_url = new_url
                    redirect_count += 1
                    continue
                
                final_status = status
                cdn_url = current_url
                break
            
            self.logger.info(f"XXXFiles: Resolved final CDN URL: {cdn_url}")
        except Exception as e:
            self.logger.error(f"Error resolving CDN chain manually for {get_file_url}: {e}")
            cdn_url = get_file_url
            
        # 4. Integrate Proxy Controller
        try:
            from resources.lib.proxy_utils import ProxyController, PlaybackGuard
            import xbmc, xbmcgui, xbmcplugin
            
            # Stage 2 Referer: The base site URL - critical for cdnawm/ahcdn
            proxy_referer = self.base_url + "/"
            
            # Browser UA from working curl
            browser_ua = ua
            
            upstream_headers = {
                'User-Agent': browser_ua,
                'Referer': proxy_referer,
                'Accept-Encoding': 'identity',
            }
            
            # IMPORTANT: The working curl shows that CDN requests should NOT have cookies.
            # We only needed cookies for the resolution hop in Stage 1.
            self.logger.info("XXXFiles: Initializing proxy with NO cookies (CDN requirement).")
            
            ctrl = ProxyController(
                upstream_url=cdn_url,
                upstream_headers=upstream_headers,
                cookies=None, # NO COOKIES for the CDN nodes
                use_urllib=True, # Critical for AHCDN TLS fingerprinting
                skip_resolve=True, # We already have the final playable URL
            )
            local_url = ctrl.start()
            
            self.logger.info(f"XXXFiles: Proxy started at {local_url}")
            
            li = xbmcgui.ListItem(path=local_url)
            li.setProperty("IsPlayable", "true")
            li.setMimeType("video/mp4")
            li.setContentLookup(False)
            xbmcplugin.setResolvedUrl(self.addon_handle, True, li)
            
            # Guard to stop proxy after playback
            player = xbmc.Player()
            monitor = xbmc.Monitor()
            guard = PlaybackGuard(player, monitor, local_url, ctrl, idle_timeout=60)
            guard.start()
            self.logger.info("XXXFiles: PlaybackGuard started.")
            
        except Exception as e:
            self.logger.error(f"Proxy implementation failed: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            # Fallback to direct resolution if proxy fails
            import xbmcgui, xbmcplugin
            stream_url = cdn_url + f"|User-Agent={urllib.parse.quote(ua)}&Referer={urllib.parse.quote(proxy_referer)}"
            li = xbmcgui.ListItem(path=stream_url)
            li.setProperty("IsPlayable", "true")
            xbmcplugin.setResolvedUrl(self.addon_handle, True, li)

    def select_sort_order(self, original_url=None):
        import xbmcgui, urllib.parse
        try:
            saved_sort = self.addon.getSetting(f"{self.name}_sort_by")
            preselect_idx = int(saved_sort) if saved_sort else 0
        except ValueError:
            preselect_idx = 0
            
        dialog = xbmcgui.Dialog()
        idx = dialog.select("Sort by...", self.sort_options, preselect=preselect_idx)

        if idx != -1:
            self.addon.setSetting(f"{self.name}_sort_by", str(idx))
            new_url, _ = self.get_start_url_and_label()
            
            # Trigger refresh
            update_command = f"Container.Update({sys.argv[0]}?mode=2&website={self.name}&url={urllib.parse.quote_plus(new_url)})"
            import xbmc
            xbmc.executebuiltin(update_command)
