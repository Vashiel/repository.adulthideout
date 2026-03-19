#!/usr/bin/env python

import re
import os
import sys
import json
import html
import urllib.parse
import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin

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

from resources.lib.base_website import BaseWebsite

class PornHits(BaseWebsite):
    def __init__(self, addon_handle):
        super().__init__(
            name="pornhits",
            base_url="https://www.pornhits.com",
            search_url="https://www.pornhits.com/videos.php",
            addon_handle=addon_handle
        )
        self.label = 'PornHits'
        self.categories_url = "https://www.pornhits.com/categories.php"
        self.stars_url = "https://www.pornhits.com/pornstars.php?p=1&s=avp&mg=f"
        self.scraper = None
        self.ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'

        self.sort_options = ['Most Recent', 'Most Viewed', 'Top Rated']
        self.sort_paths = {
            'Most Recent': 'videos.php?s=l',
            'Most Viewed': 'videos.php?s=pm',
            'Top Rated': 'videos.php?s=bm'
        }

        # Pornstar-specific sort
        self.pornstar_sort_options = ['Most Popular', 'Date Added']
        self.pornstar_sort_params = {
            'Most Popular': 's=avp',
            'Date Added': 's=l'
        }

    def get_session(self):
        if self.scraper:
            return self.scraper

        if not _HAS_CF:
            self.logger.error("Cloudscraper library missing.")
            return None

        try:
            self.scraper = cloudscraper.create_scraper(
                browser={'custom': self.ua},
                delay=10
            )
            return self.scraper
        except Exception as e:
            self.logger.error(f"Failed to create scraper session: {e}")
            return None

    def make_request(self, url, method='GET', data=None, referer=None):
        scraper = self.get_session()
        if not scraper:
            return None
            
        headers = {'User-Agent': self.ua}
        if referer:
            headers['Referer'] = referer

        try:
            if method == 'POST':
                resp = scraper.post(url, data=data, headers=headers, timeout=20)
            else:
                resp = scraper.get(url, headers=headers, timeout=20)
            
            resp.raise_for_status()
            return resp.text
        except Exception as e:
            self.logger.error(f"Request failed for {url}: {e}")
            return None



    def process_content(self, url):
        self.logger.info(f"Processing PornHits: {url}")
        
        if "/categories.php" in url:
            self.list_categories()
            return
            
        if "/pornstars.php" in url:
            self.list_pornstars(url)
            return

        # Extract page and query from URL params
        parsed = urllib.parse.urlparse(url)
        params = urllib.parse.parse_qs(parsed.query)
        page = int(params.get('p', ['1'])[0])
        query = params.get('q', [None])[0]

        # Determine if this is the "Root" view (Latest videos or Sorted videos on base url)
        is_root = (url == self.base_url or url == self.base_url + "/" or "videos.php" in url) and not query and "ct=" not in url and "ps=" not in url

        # Ensure page param is in the URL for the request
        if 'p' not in params:
            params['p'] = [str(page)]
        
        # Build request URL
        new_query = urllib.parse.urlencode(params, doseq=True)
        request_url = urllib.parse.urljoin(self.base_url, parsed.path)
        if new_query:
            request_url += "?" + new_query
            
        self.logger.info(f"Requesting: {request_url} (page={page}, query={query})")
        content = self.make_request(request_url)
        
        if not content:
            self.end_directory()
            return

        # Add Navigation Links at the top
        self.add_dir('[COLOR blue]Search[/COLOR]', '', 5, self.icons['search'], name_param=self.name)
        if is_root:
            self.add_dir('[COLOR pink]Categories[/COLOR]', self.categories_url, 2, self.icons['categories'])
            self.add_dir('[COLOR cyan]Pornstars[/COLOR]', self.stars_url, 2, self.icons['pornstars'])

        # Parse video items
        blocks = re.findall(r'<article\s+class="item">(.*?)</article>', content, re.DOTALL | re.IGNORECASE)
        
        for block in blocks:
            v_match = re.search(r'<a\s+href="([^"]+)"\s+title="([^"]+)"', block)
            if not v_match: continue
            
            v_url, title = v_match.groups()
            
            # Find thumb - prefer data-original
            img_match = re.search(r'<img[^>]+(?:data-original|src)="([^"]+)"', block)
            thumb = img_match.group(1) if img_match else ""
            
            # If thumb is a placeholder, try specifically for data-original
            if thumb and ('data:image' in thumb or thumb.endswith('.gif')):
                orig_match = re.search(r'data-original="([^"]+)"', block)
                if orig_match:
                    thumb = orig_match.group(1)
            
            # Find duration
            dur_match = re.search(r'<span\s+class="duration">([^<]+)</span>', block)
            duration = dur_match.group(1).strip() if dur_match else "00:00"
            
            full_v_url = urllib.parse.urljoin(self.base_url, v_url)
            clean_title = html.unescape(title)
            display_label = f"{clean_title} [COLOR yellow]({duration})[/COLOR]"
            
            info = {
                'title': clean_title,
                'duration': self._duration_to_seconds(duration),
                'plot': clean_title
            }
            
            self.add_link(display_label, full_v_url, 4, thumb, self.fanart, info_labels=info)

        # Pagination: build next page URL by incrementing the p param
        if len(blocks) >= 20:
            next_params = dict(params)
            next_params['p'] = [str(page + 1)]
            next_query = urllib.parse.urlencode(next_params, doseq=True)
            next_url = urllib.parse.urljoin(self.base_url, parsed.path)
            if next_query:
                next_url += "?" + next_query
                
            self.add_dir('[COLOR blue]Next Page >>>>[/COLOR]', next_url, 2, self.icons['default'])

        self.end_directory()


    def extract_json(self, content, start_marker):
        match = re.search(start_marker, content, re.S)
        if not match: return None
        
        start_idx = match.end()
        brace_count = 0
        json_str = ""
        
        for i in range(start_idx, len(content)):
            char = content[i]
            if char == '{': brace_count += 1
            elif char == '}': brace_count -= 1
            
            json_str += char
            if brace_count == 0:
                break
        
        try:
            return json.loads(json_str)
        except Exception as e:
            self.logger.error(f"JSON extraction failed: {e}")
            return None

    def list_categories(self):
        self.logger.info(f"Listing categories from {self.categories_url}")
        content = self.make_request(self.categories_url)
        if not content:
            self.logger.error("No content received for categories")
            self.end_directory()
            return
            
        # Try to parse the JSON if present
        data = self.extract_json(content, r'let\s+categories\s*=\s*')
        if data and data.get('categories'):
            self.logger.info(f"Adding {len(data['categories'])} categories from JSON")
            for cat in data['categories']:
                title = cat.get('title')
                dir_name = cat.get('dir')
                if title and dir_name:
                    full_url = f"{self.base_url}/videos.php?p=1&s=l&ct={dir_name}"
                    self.add_dir(title, full_url, 2, self.icons['default'])
            self.end_directory()
            return

        # Fallback to HTML parsing if JSON fails or is missing categories
        self.logger.info("Falling back to HTML parsing for categories")
        items = re.findall(r'<a[^>]+href="([^"]+(?:ct=|/categories/)[^"]+)"[^>]*>(.*?)</a>', content, re.S)
        
        count = 0
        added_urls = set()
        for href, text in items:
            full_url = urllib.parse.urljoin(self.base_url, href)
            if full_url in added_urls: continue
            
            clean_title = re.sub(r'<[^>]*>', '', text).strip()
            if len(clean_title) < 2 or clean_title.lower() in ['latest', 'top rated', 'most viewed', 'free porn categories']: continue
            
            added_urls.add(full_url)
            self.add_dir(clean_title, full_url, 2, self.icons['default'])
            count += 1
            
        self.logger.info(f"Added {count} category folders from HTML")
        self.end_directory()

    def list_pornstars(self, url=None):
        if not url:
            url = self.stars_url
        
        # Parse pagination from URL
        parsed = urllib.parse.urlparse(url)
        params = urllib.parse.parse_qs(parsed.query)
        page = int(params.get('p', ['1'])[0])
        
        # Ensure default sort params if not present
        if 's' not in params:
            params['s'] = ['avp']
        if 'mg' not in params:
            params['mg'] = ['f']
        if 'p' not in params:
            params['p'] = [str(page)]
        
        # Build request URL
        req_query = urllib.parse.urlencode(params, doseq=True)
        request_url = urllib.parse.urljoin(self.base_url, parsed.path)
        if req_query:
            request_url += "?" + req_query
        
        self.logger.info(f"Listing pornstars from {request_url} (page={page})")
        content = self.make_request(request_url)
        if not content:
            self.logger.error("No content received for pornstars")
            self.end_directory()
            return

        # Build context menu for pornstar sort (right-click → Sort)
        ps_sort_ctx = [
            ('Sort Pornstars by...', f'RunPlugin({sys.argv[0]}?mode=7&action=select_pornstar_sort&website={self.name})')
        ]

        count = 0
        added_titles = set()

        # Pattern 1: <li> entries with <a href title> + <img> + <h2>
        items = re.findall(
            r'<li[^>]*>\s*<a[^>]+href="([^"]+)"[^>]+title="([^"]+)"[^>]*>'
            r'.*?<img[^>]+(?:src|data-original)="([^"]+)"'
            r'.*?</a>\s*</li>',
            content, re.S
        )

        if items:
            self.logger.info(f"Found {len(items)} pornstar entries via <li> pattern")
            for href, title, thumb in items:
                if 'data:image' in thumb or thumb.endswith('.gif'):
                    thumb = self.icons['default']
                full_url = urllib.parse.urljoin(self.base_url, href)
                clean_title = html.unescape(title).strip()
                if not clean_title or clean_title.lower() in added_titles:
                    continue
                added_titles.add(clean_title.lower())
                self.add_dir(clean_title, full_url, 2, thumb, context_menu=ps_sort_ctx)
                count += 1
        else:
            # Fallback: any <a> with ps= param and a title attribute
            self.logger.info("Trying fallback pornstar regex")
            fallback_items = re.findall(
                r'<a[^>]+href="([^"]*ps=[^"]+)"[^>]*title="([^"]+)"',
                content, re.S
            )
            if not fallback_items:
                raw_links = re.findall(
                    r'<a[^>]+href="([^"]*ps=[^"]+)"[^>]*>(.*?)</a>',
                    content, re.S
                )
                for href, text in raw_links:
                    clean_title = re.sub(r'<[^>]*>', '', text).strip()
                    if clean_title and len(clean_title) > 2 and clean_title.lower() not in ['pornstars', 'upload']:
                        fallback_items.append((href, clean_title))

            for href, title in fallback_items:
                full_url = urllib.parse.urljoin(self.base_url, href)
                clean_title = html.unescape(title).strip()
                if not clean_title or clean_title.lower() in added_titles:
                    continue
                added_titles.add(clean_title.lower())
                self.add_dir(clean_title, full_url, 2, self.icons['default'], context_menu=ps_sort_ctx)
                count += 1

        self.logger.info(f"Added {count} pornstar folders")

        # Pagination: Next Page if enough items
        if count >= 20:
            next_params = dict(params)
            next_params['p'] = [str(page + 1)]
            next_query = urllib.parse.urlencode(next_params, doseq=True)
            next_url = urllib.parse.urljoin(self.base_url, parsed.path)
            if next_query:
                next_url += "?" + next_query
            self.add_dir('[COLOR blue]Next Page >>>>[/COLOR]', next_url, 2, self.icons['default'])

        self.end_directory()

    def select_pornstar_sort(self, original_url=None):
        """Sort dialog specifically for pornstars listing."""
        try:
            current_idx = int(self.addon.getSetting('pornhits_pornstar_sort_by') or '0')
            if not (0 <= current_idx < len(self.pornstar_sort_options)):
                current_idx = 0
        except (ValueError, TypeError):
            current_idx = 0

        dialog = xbmcgui.Dialog()
        idx = dialog.select("Sort Pornstars by...", self.pornstar_sort_options, preselect=current_idx)
        if idx == -1:
            return

        self.addon.setSetting('pornhits_pornstar_sort_by', str(idx))
        sort_option = self.pornstar_sort_options[idx]
        sort_param = self.pornstar_sort_params[sort_option]
        new_url = f"{self.base_url}/pornstars.php?p=1&{sort_param}&mg=f"
        xbmc.executebuiltin(f"Container.Update({sys.argv[0]}?mode=2&url={urllib.parse.quote_plus(new_url)}&website={self.name},replace)")



    def _duration_to_seconds(self, duration_str):
        try:
            parts = list(map(int, duration_str.split(':')))
            if len(parts) == 2:
                return parts[0] * 60 + parts[1]
            elif len(parts) == 3:
                return parts[0] * 3600 + parts[1] * 60 + parts[2]
        except:
            pass
        return 0

    def base164_decode(self, encoded):
        alphabet = "АВСDЕFGHIJKLМNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.,~"
        # Filter out anything not in alphabet (e.g. whitespace, quotes)
        encoded = "".join([c for c in encoded if c in alphabet])
        n = ""
        r = 0
        while r < len(encoded):
            chunk = encoded[r:r+4]
            r += 4
            indices = []
            for i in range(4):
                if i < len(chunk):
                    indices.append(alphabet.find(chunk[i]))
                else:
                    indices.append(64)
            i, o, a, s = indices
            
            c1 = (i << 2 | o >> 4) & 0xFF
            n += chr(c1)
            
            if o != 64:
                c2 = ((o & 15) << 4 | a >> 2) & 0xFF
                n += chr(c2)
                
            if a != 64 and s != 64:
                c3 = ((a & 3) << 6 | s) & 0xFF
                n += chr(c3)
        try:
            return n.encode('latin1').decode('utf-8', errors='ignore').split("\0")[0]
        except:
            return n.split("\0")[0]

    def play_video(self, url):
        self.logger.info(f"Resolving PornHits: {url}")
        
        scraper = self.get_session()
        if not scraper:
            self.notify_error("Cloudscraper failed")
            return

        headers = {'User-Agent': self.ua}
        
        # Step 1: Get the video page
        try:
            resp = scraper.get(url, headers=headers, timeout=20)
            resp.raise_for_status()
            content = resp.text
        except Exception as e:
            self.logger.error(f"Failed to load video page: {e}")
            self.notify_error("Failed to load video page")
            return

        # Step 2: Extract video payload - look for the long base164 string in initPlayer
        payload_match = re.search(r'initPlayer\s*\(.*?,?\s*[\'"]([A-Za-z0-9АВСDЕFGHIJKLМNOPQRSTUVWXYZ.,~]{100,})[\'"]', content, re.DOTALL)
        
        if not payload_match:
            # Check for embed if it's an older/different page layout
            embed_match = re.search(r'<iframe\s+[^>]*src="([^"]*embed\.php[^"]+)"', content, re.IGNORECASE)
            if embed_match:
                embed_url = urllib.parse.urljoin(self.base_url, embed_match.group(1))
                self.logger.info(f"Checking embed: {embed_url}")
                try:
                    resp = scraper.get(embed_url, headers={'Referer': url, 'User-Agent': self.ua}, timeout=20)
                    content = resp.text
                    payload_match = re.search(r'initPlayer\s*\(.*?,?\s*[\'"]([A-Za-z0-9АВСDЕFGHIJKLМNOPQRSTUVWXYZ.,~]{100,})[\'"]', content, re.DOTALL)
                except: pass

        if not payload_match:
            self.logger.error("Could not find video payload")
            self.notify_error("Video resolution failed")
            return

        try:
            payload = payload_match.group(1)
            decoded_payload = self.base164_decode(payload)
            data = json.loads(decoded_payload)
            
            # Format could be list of streams or single stream object
            streams = data if isinstance(data, list) else [data]
            
            # Prioritize higher quality
            streams.sort(key=lambda x: "_hq" in x.get('format', '').lower() or "1080" in x.get('format', ''), reverse=True)
            
            for q in streams:
                v_url_encoded = q.get('video_url')
                if v_url_encoded:
                    v_url_path = self.base164_decode(v_url_encoded)
                    self.logger.info(f"Found path candidate: {v_url_path}")
                    
                    # Construct URL - research shows the path is already correct relative to base_url
                    # We'll try without /v2 first, as /v2 was causing 404s in tests.
                    final_stream_url = urllib.parse.urljoin(self.base_url, v_url_path)
                    
                    # Follow redirects to verify the link and get the final CDN node
                    headers['Referer'] = url
                    try:
                        resp = scraper.get(final_stream_url, headers=headers, allow_redirects=True, stream=True)
                        final_active_url = resp.url
                        status = resp.status_code
                        resp.close()
                        
                        self.logger.info(f"Final resolution status ({status}) -> {final_active_url}")
                        
                        if status == 200 and ('ahcdn.com' in final_active_url or 'mp4' in final_active_url.lower()):
                            li = xbmcgui.ListItem(path=final_active_url)
                            li.setProperty('IsPlayable', 'true')
                            li.setMimeType('video/mp4')
                            
                            # Append headers for Kodi's player
                            final_active_url += f"|User-Agent={self.ua}&Referer={self.base_url}/"
                            li.setPath(final_active_url)
                            
                            xbmcplugin.setResolvedUrl(self.addon_handle, True, li)
                            return
                    except Exception as e:
                        self.logger.error(f"Failed to follow stream redirect: {e}")
                        
        except Exception as e:
            self.logger.error(f"Error during video resolution: {e}")
            import traceback
            self.logger.error(traceback.format_exc())

        self.notify_error("No playable stream found")

    def search(self, query):
        if not query: return
        # Pass the query via URL for GET consistency
        url = f"{self.search_url}?q={urllib.parse.quote(query)}"
        self.process_content(url)
