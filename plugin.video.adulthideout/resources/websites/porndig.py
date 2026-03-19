
import re
import urllib.parse
import json
import xbmcgui
import xbmcplugin
import xbmcaddon
import xbmc
import xbmcvfs
import sys
import os
import html
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    addon_path = xbmcaddon.Addon().getAddonInfo('path')
    vendor_path = os.path.join(addon_path, 'resources', 'lib', 'vendor')
    if vendor_path not in sys.path:
        sys.path.insert(0, vendor_path)
except Exception:
    pass

import cloudscraper
from resources.lib.base_website import BaseWebsite

class PornDig(BaseWebsite):
    
    API_URL = "https://www.porndig.com/posts/load_more_posts"
    API_ITEMS_PER_PAGE = 36

    
    CONTENT_TYPES = {
        'Straight': 1,
        'Gay': 2,
        'Trans': 3,
    }
    CONTENT_OPTIONS = ['Straight', 'Gay', 'Trans']

    
    SORT_TYPES = {
        'Most Recent': 'date',
        'Most Popular': 'ctr',
        'Longest': 'duration',
    }
    SORT_OPTIONS = ['Most Recent', 'Most Popular', 'Longest']

    
    SECTION_OPTIONS = ['Pro', 'Amateur']

    
    TAGS_PAGES = {
        'Straight': '/tags',
        'Gay': '/gay-tags/',
        'Trans': '/shemale-tags/',
    }

    
    SEARCH_URLS = {
        'Straight': 'https://www.porndig.com/videos/s={}',
        'Gay': 'https://www.porndig.com/gay/videos/?q={}',
        'Trans': 'https://www.porndig.com/transexual/videos/?q={}',
        'Amateur': 'https://www.porndig.com/amateur/?q={}',
    }

    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="porndig",
            base_url="https://www.porndig.com",
            search_url="https://www.porndig.com/videos/s={}",
            addon_handle=addon_handle,
            addon=addon
        )
        
        self.sort_options = self.SORT_OPTIONS

        self.scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True})
        self._session_ready = False  
        
        self.logo = os.path.join(self.addon.getAddonInfo('path'), 'resources', 'logos', 'porndig.png')
        self.icons['default'] = self.logo
        self.icons['search'] = os.path.join(self.addon.getAddonInfo('path'), 'resources', 'logos', 'search.png')
        self.icons['categories'] = os.path.join(self.addon.getAddonInfo('path'), 'resources', 'logos', 'categories.png')

    def _time_to_seconds(self, time_str):
        """Convert HH:MM:SS or MM:SS string to seconds integer."""
        if not time_str:
            return 0
        try:
            parts = list(map(int, time_str.split(':')))
            if len(parts) == 2:
                return parts[0] * 60 + parts[1]
            elif len(parts) == 3:
                return parts[0] * 3600 + parts[1] * 60 + parts[2]
        except:
            pass
        return 0

    

    def _get_content_type(self):
        """Return current content type label (Straight/Gay/Trans)."""
        try:
            idx = int(self.addon.getSetting('porndig_content_type'))
            if 0 <= idx < len(self.CONTENT_OPTIONS):
                return self.CONTENT_OPTIONS[idx]
        except (ValueError, TypeError):
            pass
        return 'Straight'

    def _get_content_category_id(self):
        """Return the main_category_id for the current content+section combo."""
        ct = self._get_content_type()
        section = self._get_section()
        if section == 'Amateur':
            return 4  
        return self.CONTENT_TYPES.get(ct, 1)

    def _get_section(self):
        """Return current section: 'Pro' or 'Amateur'."""
        try:
            idx = int(self.addon.getSetting('porndig_section'))
            if 0 <= idx < len(self.SECTION_OPTIONS):
                return self.SECTION_OPTIONS[idx]
        except (ValueError, TypeError):
            pass
        return 'Pro'

    def _get_sort_type(self):
        """Return the current sort filter_type value."""
        try:
            idx = int(self.addon.getSetting('porndig_sort_by'))
            if 0 <= idx < len(self.SORT_OPTIONS):
                return self.SORT_TYPES[self.SORT_OPTIONS[idx]]
        except (ValueError, TypeError):
            pass
        return 'date'

    def _get_sort_label(self):
        """Return the current sort label for display."""
        try:
            idx = int(self.addon.getSetting('porndig_sort_by'))
            if 0 <= idx < len(self.SORT_OPTIONS):
                return self.SORT_OPTIONS[idx]
        except (ValueError, TypeError):
            pass
        return 'Most Recent'

    

    def _ensure_session(self):
        """Establish cloudscraper session by making a GET request first."""
        if not self._session_ready:
            try:
                self.logger.info(f"Initializing session with GET {self.base_url}/video/")
                self.scraper.get(self.base_url + '/video/', timeout=15)
                self._session_ready = True
                self.logger.info("Session initialized successfully")
            except Exception as e:
                self.logger.error(f"Session init failed: {e}")

    

    def _process_thumb(self, url):
        return url

    def _preload_thumbnails(self, thumb_urls):
        if not thumb_urls:
            return {}
        return {url: url for url in thumb_urls}

    

    def make_request(self, url):
        try:
            self.logger.info(f"Requesting: {url}")
            response = self.scraper.get(url)
            if response.status_code == 200:
                return response.text
            else:
                self.logger.error(f"Request failed: {response.status_code}")
                return None
        except Exception as e:
            self.logger.error(f"Request error: {e}")
            return None

    def _api_request(self, params):
        """Make a POST request to the PornDig API."""
        self._ensure_session()
        headers = {
            'X-Requested-With': 'XMLHttpRequest',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'Referer': self.base_url + '/video/',
        }
        data = urllib.parse.urlencode(params)
        try:
            r = self.scraper.post(self.API_URL, data=data, headers=headers, timeout=15)
            self.logger.info(f"API Request Status: {r.status_code}")
            if r.status_code == 200:
                j = json.loads(r.text)
                d = j.get('data', {})
                if isinstance(d, dict):
                    content = d.get('content', '')
                    self.logger.info(f"API Content Length: {len(content)}")
                    return content
                self.logger.error("API Response 'data' is not a dict")
                return ''
            else:
                self.logger.error(f"API request failed: {r.status_code}")
                return ''
        except Exception as e:
            self.logger.error(f"API request error: {e}")
            return ''

    

    def _build_context_menu(self, current_url=''):
        """Build the right-click context menu with Sort By and Content Type."""
        encoded_url = urllib.parse.quote_plus(current_url)
        menu = [
            ('Sort by...', f'RunPlugin({sys.argv[0]}?mode=7&action=select_sort&website={self.name}&original_url={encoded_url})'),
            ('Change Content...', f'RunPlugin({sys.argv[0]}?mode=7&action=select_content_type&website={self.name})'),
        ]
        return menu

    

    def select_sort(self, original_url=None):
        """Show sort selection dialog and refresh listing."""
        try:
            current_idx = int(self.addon.getSetting('porndig_sort_by'))
            if not (0 <= current_idx < len(self.SORT_OPTIONS)):
                current_idx = 0
        except (ValueError, TypeError):
            current_idx = 0

        dialog = xbmcgui.Dialog()
        idx = dialog.select("Sort by...", self.SORT_OPTIONS, preselect=current_idx)

        if idx == -1 or idx == current_idx:
            return

        self.addon.setSetting('porndig_sort_by', str(idx))

        
        url = f"{sys.argv[0]}?mode=2&website={self.name}&url=BOOTSTRAP"
        xbmc.executebuiltin(f"Container.Update({url},replace)")

    

    def search(self, query):
        """Override search to use API directly, bypassing frontend redirects."""
        if not query:
            return
        
        
        self.save_query(query)
        
        
        
        api_url = f"API:search={urllib.parse.quote_plus(query)}&offset=0"
        
        self.logger.info(f"PornDig API search: query={query}, url={api_url}")
        self.process_content(api_url)

    def select_content_type(self, original_url=None):
        """Show content type selection dialog and refresh listing."""
        try:
            current_idx = int(self.addon.getSetting('porndig_content_type'))
            if not (0 <= current_idx < len(self.CONTENT_OPTIONS)):
                current_idx = 0
        except (ValueError, TypeError):
            current_idx = 0

        dialog = xbmcgui.Dialog()
        idx = dialog.select("Content Type...", self.CONTENT_OPTIONS, preselect=current_idx)

        if idx == -1 or idx == current_idx:
            return

        self.addon.setSetting('porndig_content_type', str(idx))

        
        url = f"{sys.argv[0]}?mode=2&website={self.name}&url=BOOTSTRAP"
        xbmc.executebuiltin(f"Container.Update({url},replace)")

    

    def _parse_videos_from_html(self, html_content):
        """Extract video items from HTML content (used for API responses and page scraping)."""
        videos_raw = []
        thumb_urls = []

        
        
        sections = re.findall(r'<section[^>]*>.*?</section>', html_content, re.DOTALL)
        self.logger.info(f"_parse_videos_from_html: Found {len(sections)} sections")

        if sections:
            seen_ids = set()
            for section in sections:
                
                link_match = re.search(
                    r'href="(/videos/(\d+)/([^"]+)\.html)"',
                    section
                )
                if not link_match:
                    continue
                link, vid_id, slug = link_match.groups()
                title = ''
                if vid_id in seen_ids:
                    continue
                seen_ids.add(vid_id)

                if not title:
                    
                    title_match = re.search(r'<a[^>]+href="/videos/' + vid_id + r'/[^"]+\.html"[^>]*>([^<]+)</a>', section)
                    if title_match:
                        title = title_match.group(1).strip()
                    else:
                        title = slug.replace('-', ' ').title()

                
                thumb_match = re.search(
                    r'(?:data-src|src)="(https://[^"]+)"',
                    section
                )
                thumb = thumb_match.group(1) if thumb_match else ''

                
                dur_match = re.search(r'>(\d{1,2}:\d{2}(?::\d{2})?)<', section)
                duration = dur_match.group(1) if dur_match else ''

                videos_raw.append({
                    "title": html.unescape(title.strip()),
                    "url": self.base_url + link,
                    "thumb": thumb,
                    "duration": duration
                })
                if thumb:
                    thumb_urls.append(thumb)
        else:
            
            video_links = re.findall(
                r'<a[^>]+href="(/videos/(\d+)/([^"]+)\.html)"',
                html_content
            )
            thumbs = re.findall(
                r'(?:data-src|src)="(https://[^"]+)"',
                html_content
            )

            seen_ids = set()
            thumb_idx = 0
            for link, vid_id, slug in video_links:
                if vid_id in seen_ids:
                    continue
                seen_ids.add(vid_id)
                
                title = slug.replace('-', ' ').title()

                thumb = thumbs[thumb_idx] if thumb_idx < len(thumbs) else ''
                thumb_idx += 1

                videos_raw.append({
                    "title": html.unescape(title.strip()),
                    "url": self.base_url + link,
                    "thumb": thumb,
                    "duration": ""
                })
                if thumb:
                    thumb_urls.append(thumb)

            
            durations = re.findall(r'>(\d{1,2}:\d{2}(?::\d{2})?)<', html_content)
            vid_durations = [d for d in durations if ':' in d]
            for i, dur in enumerate(vid_durations):
                if i < len(videos_raw):
                    videos_raw[i]['duration'] = dur

        self.logger.info(f"_parse_videos_from_html: Extracted {len(videos_raw)} videos")
        return videos_raw, thumb_urls

    

    def _get_api_listing(self, offset=0, category_id=None, query=None):
        """Fetch videos via POST API with current sort/content/section settings."""
        cat_id = self._get_content_category_id()
        sort = self._get_sort_type()

        params = {
            'main_category_id': cat_id,
            'type': 'post',
            'name': 'category_videos',
            'filters[filter_type]': sort,
            'filters[filter_period]': '',
            'offset': offset,
        }
        if category_id:
            params['category_id[]'] = category_id
        
        if query:
            params['search'] = query

        content_html = self._api_request(params)
        if not content_html:
            return [], []

        return self._parse_videos_from_html(content_html)

    

    def get_listing(self, url):
        
        if url.startswith('TOGGLE_SECTION:'):
            section_val = url.split(':')[1]
            self.addon.setSetting('porndig_section', str(section_val))
            url = 'BOOTSTRAP'

        
        is_api_listing = (
            url == 'BOOTSTRAP'
            or url == self.base_url
            or url == self.base_url + '/'
            or url.startswith('API:')
        )

        if is_api_listing:
            self.logger.info(f"Calling _get_api_listing_wrapper for URL: {url}")
            return self._get_api_listing_wrapper(url)
        else:
            self.logger.info(f"Calling _get_html_listing for URL: {url}")
            return self._get_html_listing(url)

    def _add_nav_buttons(self, context_menu):
        """Add Search, Pro/Amateur toggle, and Categories buttons."""
        section = self._get_section()

        self.add_dir("Search", "", 5, self.icons['search'], context_menu=context_menu)

        
        if section == 'Pro':
            toggle_label = "[COLOR lime]Switch to Amateur[/COLOR]"
            toggle_url = "TOGGLE_SECTION:1"
        else:
            toggle_label = "[COLOR lime]Switch to Pro[/COLOR]"
            toggle_url = "TOGGLE_SECTION:0"
        self.add_dir(toggle_label, toggle_url, 2, self.icons['default'], context_menu=context_menu)

        self.add_dir("Categories", "categories", 2, self.icons['categories'], context_menu=context_menu)

    def _get_api_listing_wrapper(self, url):
        """Handle API-based root listing with pagination."""
        
        offset = 0
        category_id = None
        query = None
        
        if url.startswith('API:'):
            params = urllib.parse.parse_qs(url[4:])
            offset = int(params.get('offset', ['0'])[0])
            category_id = params.get('category_id', [None])[0]
            query = params.get('search', [None])[0]

        videos_raw, thumb_urls = self._get_api_listing(offset, category_id, query)

        
        context_menu = self._build_context_menu()

        
        self._add_nav_buttons(context_menu)

        
        thumb_map = self._preload_thumbnails(thumb_urls)

        videos = []
        for v in videos_raw:
            processed_thumb = thumb_map.get(v['thumb'], v['thumb'])
            videos.append({
                "title": v['title'],
                "url": v['url'],
                "thumb": processed_thumb,
                "duration": v.get('duration', '')
            })

        
        if len(videos_raw) >= self.API_ITEMS_PER_PAGE:
            next_offset = offset + self.API_ITEMS_PER_PAGE
            next_api_url = f"API:offset={next_offset}"
            if category_id:
                next_api_url += f"&category_id={category_id}"
            if query:
                next_api_url += f"&search={urllib.parse.quote_plus(query)}"
            
            page_num = (next_offset // self.API_ITEMS_PER_PAGE) + 1
            videos.append({
                "title": f"Next Page ({page_num})",
                "url": next_api_url,
                "type": "next_page"
            })

        return videos

    def _get_html_listing(self, url):
        """Handle HTML-based listing for channels, search, etc."""
        html_content = self.make_request(url)
        if not html_content:
            return []

        context_menu = self._build_context_menu()

        
        self._add_nav_buttons(context_menu)

        videos_raw, thumb_urls = self._parse_videos_from_html(html_content)

        
        thumb_map = self._preload_thumbnails(thumb_urls)

        videos = []
        for v in videos_raw:
            processed_thumb = thumb_map.get(v['thumb'], v['thumb'])
            videos.append({
                "title": v['title'],
                "url": v['url'],
                "thumb": processed_thumb,
                "duration": v.get('duration', '')
            })

        
        current_num = 1
        m_url = re.search(r'/page/(\d+)', url)
        if m_url:
            current_num = int(m_url.group(1))
        else:
            m_html = re.search(r'class="[^"]*pagination_page[^"]*active[^"]*"[^>]*>(\d+)', html_content)
            if not m_html:
                m_html = re.search(r'<span[^>]*class="[^"]*current[^"]*"[^>]*>(\d+)', html_content)
            if m_html:
                current_num = int(m_html.group(1))

        next_num = current_num + 1
        next_link_pat = r'href="([^"<>]*?/page/' + str(next_num) + r'(?:["/?\u0026][^"<>]*)?)\"'
        m_next = re.search(next_link_pat, html_content)

        next_url = None
        if m_next:
            next_url = m_next.group(1)
            if not next_url.startswith('http'):
                next_url = urllib.parse.urljoin(self.base_url, next_url)
        elif videos_raw:
            base_path = re.sub(r'/page/\d+', '', url.rstrip('/'))
            next_url = f"{base_path}/page/{next_num}"

        if next_url:
            videos.append({
                "title": f"Next Page ({next_num})",
                "url": next_url,
                "type": "next_page"
            })

        return videos

    

    

    def process_categories(self, url):
        context_menu = self._build_context_menu()
        self._add_nav_buttons(context_menu)

        categories = self.get_categories()
        if not categories:
            self.end_directory()
            return

        for cat in categories:
            self.add_dir(
                name=cat['title'],
                url=cat['url'],
                mode=2,
                icon=cat.get('thumb'),
                context_menu=context_menu
            )

        self.end_directory()

    def get_categories(self):
        """Get categories based on current content type."""
        ct = self._get_content_type()
        tags_path = self.TAGS_PAGES.get(ct, '/tags')
        url = f"{self.base_url}{tags_path}"
        
        html_content = self.make_request(url)
        if not html_content:
            return []

        cats_raw = []
        channel_links = re.findall(r'href="(/channels/(\d+)/([^"]+))"', html_content)

        seen = set()
        for link, chan_id, slug in channel_links:
            if chan_id in seen:
                continue
            seen.add(chan_id)
            title = slug.replace('-', ' ').title()
            cats_raw.append({
                "title": html.unescape(title.strip()),
                "url": self.base_url + link,
                "thumb": self.icons['default']
            })

        return cats_raw

    

    def resolve(self, url):
        html_content = self.make_request(url)
        if not html_content: return None, None
        
        player_referer = url
        
        iframe_match = re.search(r'(?:src|data-src)="(https://videos\.porndig\.com/player/[^"]+)"', html_content)
        if iframe_match:
            player_url = iframe_match.group(1)
            player_referer = player_url
            self.logger.info(f"Found player iframe: {player_url}")
            
            player_html = self.make_request(player_url)
            if player_html:
                unescaped = player_html.replace('\\/', '/')
                
                sources = re.findall(
                    r'"src"\s*:\s*"(https?://[^"]+)"[^}]*?"label"\s*:\s*"(\d+)p?"',
                    unescaped
                )
                if not sources:
                    sources = re.findall(
                        r'"label"\s*:\s*"(\d+)p?"[^}]*?"src"\s*:\s*"(https?://[^"]+)"',
                        unescaped
                    )
                    sources = [(url, q) for q, url in sources]
                
                if sources:
                    self.logger.info(f"Found {len(sources)} quality options")
                    
                    preferred_order = ['1080', '720', '2160', '540', '480', '360']
                    best_url = None
                    for pref in preferred_order:
                        for src_url, quality in sources:
                            if quality == pref:
                                best_url = src_url
                                break
                        if best_url:
                            break
                    
                    if not best_url:
                        best_url = sources[0][0]
                    
                    best_url = self._resolve_redirects(best_url)
                    self.logger.info(f"Selected quality: {best_url[:80]}...")
                    return best_url, player_referer
                
                mp4_match = re.search(r'(https?://[^\s"\'<>]+\.mp4[^\s"\'<>]*)', unescaped)
                if mp4_match:
                    return self._resolve_redirects(mp4_match.group(1)), player_referer
        
        
        mp4_direct = re.search(r'(https?://video[^\s"\'<>]*\.mp4[^\s"\'<>]*)', html_content)
        mp4_direct = re.search(r'(https?://video[^\s"\'<>]*\.mp4[^\s"\'<>]*)', html_content)
        if mp4_direct:
            return self._resolve_redirects(mp4_direct.group(1)), player_referer
        
        
        download_match = re.search(r'href="(https?://videos\.porndig\.com/download/[^"]+)"', html_content)
        if download_match:
            return self._resolve_redirects(download_match.group(1)), player_referer
                
        return None, None

    def _resolve_redirects(self, url):
        """Follow any redirects to get the final direct URL for Kodi."""
        try:
            r = self.scraper.head(url, allow_redirects=True, timeout=10)
            if r.url != url:
                self.logger.info(f"Resolved redirect: {url[:60]}... -> {r.url[:60]}...")
                return r.url
        except Exception as e:
            self.logger.error(f"Redirect resolution failed: {e}")
            try:
                r = self.scraper.get(url, allow_redirects=True, stream=True, timeout=10)
                r.close()
                if r.url != url:
                    return r.url
            except Exception:
                pass
        return url

    

    def play_video(self, url):
        resolved_url, referer_url = self.resolve(url)
        if resolved_url:
            # Use Proxy to handle headers and potential Cloudflare issues
            try:
                from resources.lib import proxy_utils
                
                # Use specific Referer for CDN links
                final_referer = referer_url if referer_url else url
                ua = self.scraper.headers.get('User-Agent', '')

                self.logger.info(f"Using Proxy for URL: {resolved_url}")
                self.logger.info(f"Proxy Referer: {final_referer}")

                controller = proxy_utils.ProxyController(
                    upstream_url=resolved_url,
                    upstream_headers={'Referer': final_referer, 'User-Agent': ua},
                    cookies=self.scraper.cookies.get_dict(),
                    session=self.scraper
                )
                
                proxy_url = controller.start()
                self.logger.info(f"Proxy started at: {proxy_url}")
                
                # Start PlaybackGuard to keep proxy alive while playing
                guard = proxy_utils.PlaybackGuard(
                    xbmc.Player(), 
                    xbmc.Monitor(), 
                    proxy_url, 
                    controller
                )
                guard.start()
                
                final_url = proxy_url
                
            except ImportError:
                self.logger.error("Could not import proxy_utils. Falling back to direct link.")
                # Fallback implementation (old logic) if proxy missing
                ua = self.scraper.headers['User-Agent']
                cookies = []
                for name, value in self.scraper.cookies.get_dict().items():
                    cookies.append(f"{name}={value}")
                cookie_str = "; ".join(cookies)
                final_referer = referer_url if referer_url else url
                headers = f"|User-Agent={urllib.parse.quote(ua)}&Referer={urllib.parse.quote(final_referer)}"
                if cookie_str:
                    headers += f"&Cookie={urllib.parse.quote(cookie_str)}"
                headers += "&verifypeer=false&Connection=keep-alive"
                final_url = resolved_url + headers
            
            li = xbmcgui.ListItem(path=final_url)
            li.setMimeType('video/mp4')
            li.setProperty('IsPlayable', 'true')
            
            # For proxy, we might need inputstream.ffmpegdirect if simple HTTP fails, 
            # but usually HTTP is fine for simple proxy.
            
            xbmcplugin.setResolvedUrl(self.addon_handle, True, li)
        else:
            self.notify_error("Could not resolve video URL")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())

    

    def process_content(self, url):
        if url == "categories":
            return self.process_categories(url)

        videos = self.get_listing(url)

        context_menu = self._build_context_menu()

        for v in videos:
            if v.get('type') == 'next_page':
                self.add_dir("Next Page", v['url'], 2, self.icons['default'], context_menu=context_menu)
            else:
                self.add_link(
                    name=v['title'],
                    url=v['url'],
                    mode=4,
                    icon=v.get('thumb'),
                    fanart=self.fanart,
                    context_menu=context_menu,
                    info_labels={'duration': self._time_to_seconds(v.get('duration')), 'plot': v.get('title')}
                )

        self.end_directory()
