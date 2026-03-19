from resources.lib.base_website import BaseWebsite
import re
import json
import sys
import os

try:
    import xbmcaddon
    addon_path = xbmcaddon.Addon().getAddonInfo('path')
    vendor_path = os.path.join(addon_path, 'resources', 'lib', 'vendor')
    if vendor_path not in sys.path:
        sys.path.insert(0, vendor_path)
except Exception:
    pass

import cloudscraper

class PornDoe(BaseWebsite):
    def __init__(self, addon_handle, addon=None):
        super(PornDoe, self).__init__('porndoe', 'https://porndoe.com', 'https://porndoe.com/search?q=%s', addon_handle, addon)
        self.provider = "PornDoe"
        self.scraper = cloudscraper.create_scraper()  # persistent session for cookies
        self._cookie_path = os.path.join(os.path.expanduser('~'), '.porndoe_cookies.json')
        self._load_cookies()
        
        # Site Sorting Options
        self.sort_options = ['Newest', 'Most Viewed', 'Longest', 'Most Liked']
        self.sort_paths = {
            'Newest': '/videos',
            'Most Viewed': '/videos?sort=views',
            'Longest': '/videos?sort=length',
            'Most Liked': '/videos?sort=likes'
        }

        # Content Type Options
        self.content_options = ['Straight', 'Gay', 'Trans']
        self.content_paths = {
            'Straight': '',
            'Gay': '/gay',
            'Trans': '/m2f'
        }

    def _load_cookies(self):
        """Load saved cookies into the scraper session."""
        try:
            if os.path.exists(self._cookie_path):
                with open(self._cookie_path, 'r') as f:
                    cookies = json.load(f)
                for name, value in cookies.items():
                    self.scraper.cookies.set(name, value, domain='porndoe.com')
        except Exception:
            pass

    def _save_cookies(self):
        """Save scraper session cookies to disk for reuse across Kodi invocations."""
        try:
            cookies = {c.name: c.value for c in self.scraper.cookies if 'porndoe' in c.domain}
            with open(self._cookie_path, 'w') as f:
                json.dump(cookies, f)
        except Exception:
            pass

    def _ensure_utm_session(self, hdr):
        """Ensure the UTM bypass cookie _aVrU is set. Only makes HTTP requests if missing."""
        if self.scraper.cookies.get('_aVrU', domain='porndoe.com'):
            return  # Already have the bypass cookie
        try:
            utm_url = f"{self.base_url}/?utm_campaign=theporndude&utm_medium=trafficbuy&utm_source=theporndude"
            self.scraper.get(utm_url, headers={**hdr, 'Referer': 'https://theporndude.com/'}, timeout=8)
            self._save_cookies()
        except Exception as e:
            self.logger.error(f"PornDoe: UTM preflight failed: {e}")

    def make_request(self, url, headers=None, return_headers=False):
        scraper = self.scraper  # reuse persistent session so cookies persist between calls
        default_headers = {'User-Agent': 'Mozilla/5.0'}
        if headers:
            default_headers.update(headers)
        
        try:
            response = scraper.get(url, headers=default_headers, timeout=15)
            if response.status_code == 200:
                if return_headers:
                    return response.text, response.headers
                return response.text
            self.logger.error(f"PornDoe make_request failed with status: {response.status_code} for URL: {url}")
            return None, None if return_headers else None
        except Exception as e:
            self.logger.error(f"PornDoe make_request error: {e} for URL: {url}")
            return None, None if return_headers else None

    def get_start_url_and_label(self):
        """Returns the starting URL, respecting the saved content type and sort settings."""
        # 1. Get Content Type
        try:
            saved_content = self.addon.getSetting(f"{self.name}_content_type")
            content_idx = int(saved_content) if saved_content else 0
        except ValueError:
            content_idx = 0
            
        if not (0 <= content_idx < len(self.content_options)):
            content_idx = 0
            
        content_label = self.content_options[content_idx]
        content_path = self.content_paths.get(content_label, '')

        # 2. Get Sort Setting
        try:
            saved_sort = self.addon.getSetting(f"{self.name}_sort_by")
            sort_idx = int(saved_sort) if saved_sort else 0
        except ValueError:
            sort_idx = 0

        sort_label = "Videos"
        sort_path = "/videos"
        
        if 0 <= sort_idx < len(self.sort_options):
            sort_option = self.sort_options[sort_idx]
            sort_path = self.sort_paths.get(sort_option, "/videos")
            sort_label = sort_option

        # Join paths: e.g. /gay + /videos?sort=views
        url = f"{self.base_url}{content_path}{sort_path}"
        
        # Build Label: PornDoe (Gay - Most Viewed)
        label = f"{self.provider} [COLOR yellow]({content_label} - {sort_label})[/COLOR]"
        return url, label
        
    def select_content_type(self, original_url=None):
        import xbmcgui, urllib.parse
        try:
            saved_content = self.addon.getSetting(f"{self.name}_content_type")
            preselect_idx = int(saved_content) if saved_content else 0
        except ValueError:
            preselect_idx = 0
            
        dialog = xbmcgui.Dialog()
        idx = dialog.select("Content Type...", self.content_options, preselect=preselect_idx)

        if idx != -1:
            self.addon.setSetting(f"{self.name}_content_type", str(idx))
            new_url, _ = self.get_start_url_and_label()
            
            # Trigger refresh
            update_command = f"Container.Update({sys.argv[0]}?mode=2&website={self.name}&url={urllib.parse.quote_plus(new_url)})"
            import xbmc
            xbmc.executebuiltin(update_command)

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
        
    def get_search_url(self, query):
        from urllib.parse import quote_plus
        # Prepend content path if not Straight
        try:
            saved_content = self.addon.getSetting(f"{self.name}_content_type")
            content_idx = int(saved_content) if saved_content else 0
            content_label = self.content_options[content_idx]
            content_path = self.content_paths.get(content_label, '')
        except Exception:
            content_path = ''
            
        return f"{self.base_url}{content_path}/search?q={quote_plus(query)}"

    def process_content(self, url, query=None, page=1):
        if not url or url == "BOOTSTRAP" or url.strip('/') == self.base_url.strip('/'):
             url, _ = self.get_start_url_and_label()
             
        if not url.startswith('http'):
            url = f"{self.base_url}{url}"

        # Dispatch to categories parser if needed
        if '/categories' in url and '/category/' not in url:
            return self.process_categories(url)

        # Extract page from URL if present (e.g. ?page=2)
        base_url = url
        page_match = re.search(r'[?&]page=(\d+)', url)
        if page_match:
            page = int(page_match.group(1))
            # Strip page param from url to get clean base
            base_url = re.sub(r'[?&]page=\d+', '', url).rstrip('?').rstrip('&')
            
        # Determine context: are we on a listing where we want Search/Categories buttons?
        # Only hide them if we are browsing the /categories list or a specific /category/ listing
        is_category_context = ('/category/' in url or '/categories' in url)
        
        # UI Elements: Search and Categories only if not in category context
        if not is_category_context:
            self.add_dir('[COLOR blue]Search[/COLOR]', '', 5, self.icons.get('search', ''), name_param=self.name)
            
            # Categories URL should be content-aware too
            try:
                saved_content = self.addon.getSetting(f"{self.name}_content_type")
                content_idx = int(saved_content) if saved_content else 0
                content_label = self.content_options[content_idx]
                content_path = self.content_paths.get(content_label, '')
            except Exception:
                content_path = ''
            
            self.add_dir('[COLOR yellow]Categories[/COLOR]', f"{self.base_url}{content_path}/categories", 8, self.icons.get('categories', ''), name_param=self.name)

        # Build current URL with page
        if page > 1:
            separator = '&' if '?' in base_url else '?'
            current_url = f"{base_url}{separator}page={page}"
        else:
            current_url = base_url

        html, headers = self.make_request(current_url, return_headers=True)
        if not html:
            self.end_directory()
            return

        # Replace BeautifulSoup with regex for compatibility across all Kodi setups
        blocks = re.split(r'<div[^>]*class=["\'][^"\']*video-item(?!-)[^"\']*["\']', html)[1:]
        
        # Prepare Context Menu
        context_menu = [
            ('Change Content...', f'RunPlugin({sys.argv[0]}?mode=7&action=select_content_type&website={self.name})'),
            ('Sort by...', f'RunPlugin({sys.argv[0]}?mode=7&action=select_sort_order&website={self.name})')
        ]

        for block in blocks:
            url_match = re.search(r'href=["\']([^"\']+)["\']', block)
            if not url_match:
                continue
            
            video_url = url_match.group(1)
            if not video_url.startswith('http'):
                video_url = f"{self.base_url}{video_url}"

            title = "Unknown Title"
            title_match = re.search(r'aria-label=["\']([^"\']+)["\']', block)
            if title_match:
                title = title_match.group(1).replace('Watch ', '').replace(' Watch', '').strip()
            else:
                title_match2 = re.search(r'class=["\'][^"\']*video-item-title[^"\']*["\'][^>]*>\s*(.*?)\s*<', block, re.DOTALL)
                if title_match2:
                    title = title_match2.group(1).strip()
                    
            thumb_url = ''
            # PornDoe uses SVG with data-src for lazy loading (not img tags)
            # Pattern: data-src="https://p.cdnc.porndoe.com/image/..."
            thumb_match = re.search(r'data-src=["\']([^"\']+(?:porndoe|cdnc)[^"\']+)["\']', block)
            if thumb_match:
                thumb_url = thumb_match.group(1)
            else:
                img_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', block)
                if img_match:
                    thumb_url = img_match.group(1)
                    
            duration = ''
            dur_match = re.search(r'class=["\'][^"\']*video-item-duration[^"\']*["\'][^>]*>\s*([^<]+)\s*<', block)
            if dur_match:
                duration = dur_match.group(1).strip()
            else:
                # Some items store duration in data-duration if the block parent is preserved, 
                # but since we split, check if we accidentally find it inside inner elements
                dur_match2 = re.search(r'data-duration=["\']([^"\']+)["\']', block)
                if dur_match2:
                    duration = dur_match2.group(1).strip()

            if title and video_url:
                self.add_link(
                    name=title,
                    url=video_url,
                    mode=4,
                    icon=thumb_url,
                    fanart=self.fanart,
                    info_labels={'title': title, 'duration': duration},
                    context_menu=context_menu
                )

        # Pagination logic
        next_page = False
        active_match = re.search(r'<li class="active">.*?</li>\s*<li><a href="([^"]+)("\s*rel="next"|>)', html, re.DOTALL)
        
        if active_match:
            next_page = True
        elif 'rel="next"' in html:
            next_page = True
        elif len(blocks) >= 20:
             next_page = True

        if next_page:
            next_page_num = page + 1
            separator = '&' if '?' in base_url else '?'
            next_url = f"{base_url}{separator}page={next_page_num}"
            self.add_dir(
                name=">> Next Page",
                url=next_url,
                mode=2,
                thumb="DefaultFolder.png",
            )

        self.end_directory()

    def process_categories(self, url):
        """Parse categories list page using .-ctlc-item cards."""
        html = self.make_request(url)
        if not html:
            self.end_directory()
            return

        # Categories are in .-ctlc-item blocks
        # Pattern: <a class="-ctlc-item" href="/category/32/hd-videos" title="HD Videos">
        # The title attribute is the most reliable source for the name
        pattern = r'<a[^>]+class=["\'][^"\']*-ctlc-item[^"\']*["\'][^>]+href=["\']([^"\']+)["\'][^>]+title=["\']([^"\']+)["\']'
        matches = re.findall(pattern, html)
        
        for cat_url, title in matches:
            if not cat_url.startswith('http'):
                cat_url = f"{self.base_url}{cat_url}"
            
            # Simple list of categories, no icons parsed for now to keep it fast
            self.add_dir(
                name=title,
                url=cat_url,
                mode=2
            )

        self.end_directory()

    def play_video(self, url):
        # Extract alphanumeric hash directly from URL
        # e.g., https://porndoe.com/watch/pd4u5g7x4x9o -> pd4u5g7x4x9o
        video_id = url.strip('/').split('/')[-1]

        if not video_id:
            import xbmcgui, xbmcplugin
            self.notify_error("PornDoe: Invalid Video URL.")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem(path=url))
            return

        hdr = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
        }

        # Step 1: Ensure UTM session cookie is set (runs once, then reuses cached cookie)
        self._ensure_utm_session(hdr)

        # Step 2: Warm up the video page with the session
        self.make_request(url, headers={**hdr, 'Referer': self.base_url + '/'})

        # Step 3: Call the JSON player API
        api_url = f"{self.base_url}/service/index.json?device=desktop&height=800&width=1280&page=channel&id={video_id}"
        api_resp = self.make_request(api_url, headers={
            **hdr,
            'Referer': url,
            'Accept': 'application/json',
            'X-Requested-With': 'XMLHttpRequest',
        })

        import xbmcgui, xbmcplugin, urllib.parse

        if not api_resp:
            self.notify_error("PornDoe: API Request Failed.")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem(path=url))
            return

        play_url = None
        is_hls = False
        try:
            data = json.loads(api_resp)
            payload = data.get('payload', {})
            player = payload.get('player', {})
            sources = player.get('sources', {})

            if isinstance(sources, dict):
                def get_best_link(arr):
                    """Get best quality entry with type='video' (not premium 'link' type)."""
                    free = [x for x in arr if x.get('type') == 'video' and x.get('link', '').startswith('http')]
                    if not free:
                        return None
                    best = sorted(free, key=lambda x: x.get('height', 0), reverse=True)
                    return best[0].get('link')

                # Prefer HLS (best free quality)
                hls_link = get_best_link(sources.get('hls', []))
                if hls_link:
                    play_url = hls_link
                    is_hls = True

                # Fallback: mp4 array
                if not play_url:
                    mp4_link = get_best_link(sources.get('mp4', []))
                    if mp4_link:
                        play_url = mp4_link

                # Fallback: deo array
                if not play_url:
                    deo_link = get_best_link(sources.get('deo', []))
                    if deo_link:
                        play_url = deo_link

            if not play_url and 'age_gate' in payload:
                self.notify_error("PornDoe: Age Gate still active. Please try again.")
                self.logger.error("PornDoe: Age Gate triggered by IP.")
                xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem(path=url))
                return

        except Exception as e:
            self.logger.error(f"PornDoe API JSON Error: {e}")

        if play_url:
            dl_ua = hdr['User-Agent']
            encoded_headers = f"|User-Agent={urllib.parse.quote(dl_ua)}&Referer={urllib.parse.quote(self.base_url)}/"
            final_play_url = play_url + encoded_headers

            li = xbmcgui.ListItem(path=final_play_url)
            li.setProperty("IsPlayable", "true")

            if is_hls:
                li.setMimeType("application/vnd.apple.mpegurl")
                try:
                    li.setProperty("inputstream", "inputstream.adaptive")
                    li.setProperty("inputstream.adaptive.manifest_type", "hls")
                    li.setProperty("inputstream.adaptive.stream_headers",
                                   f"User-Agent={urllib.parse.quote(dl_ua)}&Referer={urllib.parse.quote(self.base_url)}/")
                except Exception:
                    pass
            else:
                li.setMimeType("video/mp4")

            li.setContentLookup(False)
            self.logger.error(f"PornDoe Resolved URL: {play_url}")
            xbmcplugin.setResolvedUrl(self.addon_handle, True, li)
        else:
            self.logger.error(f"PornDoe: No Stream URL Found for {url}.")
            self.notify_error("PornDoe: No Stream URL Found.")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem(path=url))



