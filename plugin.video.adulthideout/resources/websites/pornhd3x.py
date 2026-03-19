from resources.lib.base_website import BaseWebsite
import re
import html as html_module
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import os
import urllib.parse
from resources.lib.proxy_utils import ProxyController, PlaybackGuard
import xbmc, xbmcplugin, xbmcgui, xbmcvfs

class PornHD3X(BaseWebsite):
    def __init__(self, addon_handle, addon=None):
        super(PornHD3X, self).__init__('pornhd3x', 'https://www.pornhd3x.tv', 'https://www.pornhd3x.tv/search/{}', addon_handle, addon)
        self.provider = "PornHD3X"
        
        self.sort_options = ['Latest']
        self.sort_paths = {
            'Latest': '/'
        }
        
        # Max parallel thumbnail downloads
        self.THUMB_WORKERS = 10
        self.THUMB_TIMEOUT = 10
        self._thumb_cache_dir = self._init_thumb_cache()

    def _init_thumb_cache(self):
        addon_profile = xbmcvfs.translatePath(self.addon.getAddonInfo('profile'))
        thumb_dir = os.path.join(addon_profile, 'thumbs', self.name)
        os.makedirs(thumb_dir, exist_ok=True)
        return thumb_dir

    def _download_single_thumb(self, url):
        """Download one thumbnail with correct Referer header.
        Returns local file path on success, or URL+Referer header on failure."""
        if not url or not url.startswith('http'):
            return None

        try:
            hashed = hashlib.md5(url.encode('utf-8')).hexdigest()

            # Check cache first (using standard OS path check)
            for ext in ('.jpg', '.png', '.gif', '.webp', '.bmp'):
                cached = os.path.join(self._thumb_cache_dir, hashed + ext)
                if os.path.exists(cached) and os.path.getsize(cached) > 0:
                    return cached

            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Referer': self.base_url + '/',
                'Accept': 'image/avif,image/webp,image/apng,image/*,*/*;q=0.8',
            }
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=self.THUMB_TIMEOUT) as resp:
                data = resp.read()

            if not data:
                return None

            signatures = {
                b'\xFF\xD8\xFF':       '.jpg',
                b'\x89PNG\r\n\x1a\n':  '.png',
                b'GIF89a':             '.gif',
                b'GIF87a':             '.gif',
                b'BM':                 '.bmp',
            }
            ext = None
            for sig, e in signatures.items():
                if data.startswith(sig):
                    ext = e
                    break
            if ext is None and data[:4] == b'RIFF' and data[8:12] == b'WEBP':
                ext = '.webp'

            if ext is None:
                self.logger.warning(f"PornHD3X: Unknown image format for {url} - first bytes: {data[:8].hex()}")
                return None

            local_path = os.path.join(self._thumb_cache_dir, hashed + ext)
            # Use standard Python open() - xbmcvfs.File has unreliable binary write behaviour
            try:
                with open(local_path, 'wb') as f:
                    f.write(data)
                if os.path.exists(local_path) and os.path.getsize(local_path) > 0:
                    self.logger.debug(f"PornHD3X: Cached thumb {ext} -> {local_path}")
                    return local_path
            except Exception as write_err:
                self.logger.warning(f"PornHD3X: Could not write thumb to {local_path}: {write_err}")

            # Fallback: let Kodi load URL directly with Referer header
            return url + '|Referer=' + urllib.parse.quote(self.base_url + '/')

        except Exception as e:
            self.logger.warning(f"PornHD3X: thumb download failed for {url}: {e}")
            return None


    def _batch_download_thumbs(self, urls):
        """Download multiple thumbnails in parallel via ThreadPoolExecutor."""
        results = {}
        unique_urls = list(set(u for u in urls if u and u.startswith('http')))
        if not unique_urls:
            return results

        with ThreadPoolExecutor(max_workers=self.THUMB_WORKERS) as pool:
            future_map = {
                pool.submit(self._download_single_thumb, u): u
                for u in unique_urls
            }
            for future in as_completed(future_map):
                orig_url = future_map[future]
                try:
                    results[orig_url] = future.result()
                except Exception:
                    results[orig_url] = None

        return results

    def _resolve_thumb(self, thumb_map, url):
        """Look up a downloaded thumbnail, fall back to default icon.
        
        thumb_map values can be:
          - A local file path (C:\\...\\hashed.jpg)  -> use os.path.exists()
          - URL + '|Referer=...' string (Kodi fallback) -> use directly
          - None -> use default icon
        """
        path = thumb_map.get(url)
        if not path:
            return self.icons.get('default', self.icon)
        # If it's a local file path (no | separator), verify it exists
        if '|' not in path:
            if os.path.exists(path) and os.path.getsize(path) > 0:
                return path
            return self.icons.get('default', self.icon)
        # URL+header fallback - pass directly to Kodi
        return path

    def make_request(self, url):
        import cloudscraper
        import time
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': self.base_url,
        }
        scraper = cloudscraper.create_scraper()
        for attempt in range(3):
            try:
                response = scraper.get(url, headers=headers, timeout=15)
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

    def _slug_to_thumb(self, slug):
        """
        Derive thumbnail URL from a movie slug.
        The site stores images at /Cms_Data/Contents/admin/Media/images/<slug>.jpg
        Note: These images are often served with corrupted JPEG headers, so Kodi
        may not be able to display them. This is a site-side issue, not a plugin bug.
        """
        if slug:
            slug = slug.strip('/')
            if slug.startswith('movies/'):
                slug = slug[7:]
            return f"{self.base_url}/Cms_Data/Contents/admin/Media/images/{slug}.jpg"
        return ""

    def process_content(self, url, query=None, page=1):
        if not url or url == "BOOTSTRAP":
             url, _ = self.get_start_url_and_label()
        
        current_url = url
        # No longer modifying URL by hardcoding /page/X/ here, we rely on the exact Next Page link 
        # that was scraped and passed in via `url`.


        page_html = self.make_request(current_url)
        if not page_html:
            self.end_directory()
            return

        # Add Search and Categories on every page
        self.add_dir('Search', '', 5, self.icons.get('search'), name_param=self.name)
        self.add_dir('Categories', f"{self.base_url}/category", 2, self.icons.get('categories'), name_param=self.name)

        # === Parsing categories on /category page ===
        if '/category' in current_url and current_url.rstrip('/').endswith('/category'):
            cat_list = re.findall(
                r'<a[^>]+href=["\'](?:https?://[^"\']*)?(/category/[^"\']+)["\'][^>]*>([^<]+)</a>',
                page_html
            )
            found_cats = set()
            for cat_path, cat_name in cat_list:
                cat_url_full = self.base_url + cat_path
                cat_name = html_module.unescape(cat_name).strip()
                if cat_name and cat_url_full not in found_cats and len(cat_name) > 1:
                    self.add_dir(cat_name, cat_url_full, 2, self.icons.get('categories'), name_param=self.name)
                    found_cats.add(cat_url_full)
            self.end_directory()
            return

        # === Video Item Parsing ===
        # The site HTML structure (from live analysis of pornhd3x.tv):
        # <div data-movie-id="..">
        #   <a href="/movies/SHORT-SLUG" class="ml-mask jt" title="TITLE">
        #     <div class="img thumb__img">
        #       <img data-original="/Cms_Data/Contents/admin/Media/images/LONG-SLUG.jpg"
        #            class="lazy thumb mli-thumb" alt="TITLE"/>
        #     </div>
        #   </a>
        # </div>
        # IMPORTANT: The img data-original URL uses a DIFFERENT, longer slug than the <a href>.
        # We capture href, title, AND the img simultaneously from inside each <a>...</a> block.

        item_pattern = re.compile(
            r'<a[^>]+href=["\'](?:https?://[^"\']*)?(/movies/([^"\'#?]+))["\'][^>]*?'
            r'title=["\']([^"\']*)["\'][^>]*>(.*?)</a>',
            re.DOTALL | re.IGNORECASE
        )

        seen_slugs = set()
        unique_videos = []   # list of (v_path, v_slug, v_title, raw_thumb_url)

        for m in item_pattern.finditer(page_html):
            v_path  = m.group(1)        # /movies/short-slug
            v_slug  = m.group(2)        # short-slug
            v_title = m.group(3) or ''  # title attribute
            inner   = m.group(4)        # HTML content inside <a>...</a>

            if not v_title:
                alt_m = re.search(r'alt=["\']([^"\']+)["\']', inner)
                v_title = alt_m.group(1) if alt_m else v_slug

            if v_slug in seen_slugs:
                continue
            seen_slugs.add(v_slug)

            # Extract thumbnail from inside the <a> block
            img_m = re.search(
                r'<img[^>]+(?:data-original|data-src|src)=["\']([^"\']+)["\']',
                inner, re.IGNORECASE
            )
            raw_thumb = ''
            if img_m:
                candidate = img_m.group(1)
                if candidate and 'data:image' not in candidate and candidate.strip():
                    raw_thumb = candidate if candidate.startswith('http') \
                                else urllib.parse.urljoin(self.base_url, candidate)

            unique_videos.append((v_path, v_slug, v_title, raw_thumb))

        # Parallel batch download of all thumbnails
        raw_thumb_urls = [raw_thumb for _, _, _, raw_thumb in unique_videos]
        downloaded_thumbs = self._batch_download_thumbs([t for t in raw_thumb_urls if t])

        found_count = 0
        for v_path, v_slug, v_title, raw_thumb in unique_videos:
            v_url_full = self.base_url + v_path

            v_title = html_module.unescape(v_title).strip()

            # Fallback to slug-derived URL if no img was found in the block
            if not raw_thumb:
                raw_thumb = self._slug_to_thumb(v_slug)
                
            # Resolve to local file path (downloads and caches locally)
            v_thumb = self._resolve_thumb(downloaded_thumbs, raw_thumb)

            info = {
                'title': v_title,
            }
            self.add_link(v_title, v_url_full, 4, v_thumb, self.fanart, info_labels=info)
            found_count += 1

        self.logger.info(f"PornHD3X: Found {found_count} videos on page {page}")

        # === Pagination ===
        has_next = False
        next_page = page + 1
        
        # Scrape precise next page link from HTML
        # The site doesn't have a "Next" button, just page numbers: <a href="/premium-porn-hd/page-2">2</a>
        next_url = None
        
        # Look for the exact page link for page + 1
        str_next_page = str(next_page)
        links = re.findall(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', page_html, re.IGNORECASE)
        for href, text in links:
            text_clean = text.strip()
            # If the link text is exactly the next page number
            if text_clean == str_next_page:
                next_url = urllib.parse.urljoin(self.base_url, href)
                has_next = True
                break
                
        # Fallback if the link contains the word Next
        if not next_url:
            match = re.search(r'<a[^>]*href=["\']([^"\']+)["\'][^>]*>[^<]*Next', page_html, re.IGNORECASE)
            if match:
                 next_url = urllib.parse.urljoin(self.base_url, match.group(1))
                 has_next = True

        if has_next and next_url and found_count > 0:
            self.add_dir('Next Page >>', next_url, 2, self.icons.get('default'), name_param=self.name, page=next_page)

        self.end_directory()

    def play_video(self, url):
        page_html = self.make_request(url)
        if not page_html:
            self.logger.error("Failed to load video page.")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem(path=url))
            return

        self.logger.info("Extracting stream for PornHD3X...")
        
        # 1. Parse episode_id for native player
        episode_id_match = re.search(r'episode-id=["\']([^"\']+)["\']', page_html)
        if episode_id_match:
            episode_id = episode_id_match.group(1).strip()
            self.logger.info(f"Found episode-id: {episode_id}")
            
            from resources.lib.decoders.pornhd3x_decoder import get_stream_url
            import cloudscraper
            
            session = cloudscraper.create_scraper()
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Referer': self.base_url
            })
            
            if session:
                data = get_stream_url(episode_id, session, self.base_url)
                if data and 'playlist' in data and len(data['playlist']) > 0:
                    sources = data['playlist'][0].get('sources', [])
                    stream_url = ""
                    for s in sources:
                        if s.get('file', '').startswith('http'):
                            stream_url = s['file']
                            break
                            
                    if stream_url:
                        self.logger.info(f"Successfully retrieved stream URL: {stream_url}")
                        mime = 'application/vnd.apple.mpegurl' if '.m3u8' in stream_url else 'video/mp4'
                        
                        ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                        
                        final_stream_url = stream_url + f"|User-Agent={urllib.parse.quote(ua)}&Referer={urllib.parse.quote(self.base_url)}"
                        li = xbmcgui.ListItem(path=final_stream_url)
                        li.setProperty('IsPlayable', 'true')
                        li.setMimeType(mime)

                        if '.m3u8' in stream_url:
                            li.setProperty('inputstream', 'inputstream.adaptive')
                            li.setProperty('inputstream.adaptive.manifest_type', 'hls')
                            li.setProperty('inputstream.adaptive.stream_headers', f"User-Agent={urllib.parse.quote(ua)}&Referer={urllib.parse.quote(self.base_url)}")

                        xbmcplugin.setResolvedUrl(self.addon_handle, True, listitem=li)
                        return
                
        # 2. Check for standard iframes (doodstream, lulustream, etc.) as fallback
        iframes = re.findall(r'<iframe[^>]+src=["\']([^"\']+)["\']', page_html)
        embed_url = None
        for iframe in iframes:
             if any(domain in iframe for domain in ['dood', 'lulu', 'voe', 'strmup', 'vidnest']):
                  embed_url = iframe
                  break
        
        if embed_url:
            self.logger.info(f"Found fallback embed URL: {embed_url}")
            try:
                upstream_headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Referer': self.base_url
                }
                
                ctrl = ProxyController(
                    upstream_url=embed_url,
                    upstream_headers=upstream_headers,
                    use_urllib=True,
                    skip_resolve=False,
                )
                local_url = ctrl.start()
                self.logger.info(f"PornHD3X Proxy started at {local_url}")
                
                li = xbmcgui.ListItem(path=local_url)
                li.setProperty("IsPlayable", "true")
                xbmcplugin.setResolvedUrl(int(self.addon_handle), True, listitem=li)
                
                player = xbmc.Player()
                monitor = xbmc.Monitor()
                guard = PlaybackGuard(player, monitor, local_url, ctrl, idle_timeout=60 * 60)
                guard.start()
                return
            except Exception as e:
                self.logger.error(f"PornHD3X proxy failed: {e}")
                
        self.logger.error("No valid embed URL found.")
        self.notify_error("Could not extract stream URL.")
        xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem(path=url))
