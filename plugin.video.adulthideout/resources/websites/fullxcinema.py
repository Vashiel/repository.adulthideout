#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os
import re
import urllib.parse
import html
import json
import base64
import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
import xbmcvfs

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
from resources.lib.resolvers import resolver

class FullXCinema(BaseWebsite):
    COOKIE_PROP = "plugin.video.adulthideout.fullxcinema.cookies"

    def __init__(self, addon_handle):
        super().__init__(
            name="fullxcinema",
            base_url="https://www.fullxcinema.com",
            search_url="https://fullxcinema.com/?s={}",
            addon_handle=addon_handle
        )
        self.label = 'FullXCinema'
        self.eporner_base = "https://www.eporner.com/"
        self.scraper = None
        
        self.ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36'

        self.sort_options = ["Latest", "Most Viewed", "Longest", "Popular", "Random"]
        self.sort_paths = {
            "Latest": "/?filter=latest",
            "Most Viewed": "/?filter=most-viewed",
            "Longest": "/?filter=longest",
            "Popular": "/?filter=popular",
            "Random": "/?filter=random"
        }

    def _save_cookies(self):
        if self.scraper:
            try:
                cookies = self.scraper.cookies.get_dict()
                if cookies:
                    xbmcgui.Window(10000).setProperty(self.COOKIE_PROP, json.dumps(cookies))
            except Exception:
                pass

    def _load_cookies(self):
        try:
            cookie_str = xbmcgui.Window(10000).getProperty(self.COOKIE_PROP)
            if cookie_str:
                return json.loads(cookie_str)
        except Exception:
            pass
        return None

    def get_session(self):
        if self.scraper:
            return self.scraper

        self.logger.info(f"[{self.name}] Initializing Cloudscraper session...")
        
        if not _HAS_CF:
            self.notify_error("Cloudscraper library missing.")
            return None

        try:
            scraper = cloudscraper.create_scraper(
                browser={'custom': self.ua}, 
                delay=10
            )
            
            cached_cookies = self._load_cookies()
            if cached_cookies:
                scraper.cookies.update(cached_cookies)
                self.logger.info(f"[{self.name}] Restored session cookies from cache.")
            
            self.scraper = scraper 
            return self.scraper
            
        except Exception as e:
            self.logger.error(f"[{self.name}] Failed to create scraper session: {e}")
            return None

    def make_request(self, url, referer=None, headers=None):
        scraper = self.get_session()
        if not scraper:
            return None
            
        try:
            if not headers:
                headers = {
                    'User-Agent': self.ua,
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Cache-Control': 'no-cache', 'Pragma': 'no-cache'
                }
            
            if referer: headers['Referer'] = referer

            resp = scraper.get(url, headers=headers, timeout=20)
            self._save_cookies()
            resp.raise_for_status()
            return resp.content.decode('utf-8', 'ignore')
        except Exception as e:
            self.logger.error(f"Failed to load data from {url}: {e}")
            return None

    def get_start_url_and_label(self):
        label = f"{self.name.capitalize()}"
        setting_id = f"{self.name}_sort_by"
        try:
            sort_idx = int(self.addon.getSetting(setting_id))
            if not (0 <= sort_idx < len(self.sort_options)): sort_idx = 0
        except Exception: sort_idx = 0
        sort_option = self.sort_options[sort_idx]
        sort_path = self.sort_paths.get(sort_option, "/?filter=latest")
        url = urllib.parse.urljoin(self.base_url, sort_path)
        final_label = f"{label} [COLOR yellow]{sort_option}[/COLOR]"
        return url, final_label

    def process_content(self, url):
        self.logger.info(f"Processing content for FullXCinema: {url}")

        content = self.make_request(url)
        if not content:
            self.end_directory(); return

        is_search = "?s=" in url
        is_category_page = "?cat=" in url
        is_main_page_variant = not is_search and not is_category_page

        self.add_dir('[COLOR blue]Search[/COLOR]', '', 5, self.icons['search'], name_param=self.name)

        if is_main_page_variant:
             self.add_dir('Categories', 'show_categories_placeholder', 8, self.icons['categories'])

        articles = re.findall(r'<article\s+data-video-uid=.*?class="loop-video\s+thumb-block.*?</article>', content, re.DOTALL)
        if not articles: self.logger.info(f"No <article> blocks found on {url}")
        else: self.logger.info(f"Found {len(articles)} <article> blocks.")

        for block in articles:
            try:
                match_link = re.search(r'<a\s+href="([^"]+)"\s+title="([^"]+)"', block, re.DOTALL | re.IGNORECASE)
                if not match_link: continue
                video_url_part, title = match_link.groups()

                match_thumb = re.search(r'<img\s+.*?data-src="([^"]+)"', block, re.DOTALL | re.IGNORECASE)
                thumb_url = match_thumb.group(1) if match_thumb else self.icon

                match_duration = re.search(r'<span\s+class="duration">.*?</i>\s*([\d:]+)\s*</span>', block, re.DOTALL | re.IGNORECASE)
                duration_str = match_duration.group(1).strip() if match_duration else ""

                clean_title = html.unescape(title)
                full_video_url = urllib.parse.urljoin(self.base_url, video_url_part)
                label = f"{clean_title}" + (f" [COLOR lime]({duration_str})[/COLOR]" if duration_str else "")
                self.add_link(label, full_video_url, 4, thumb_url, self.fanart)
            except Exception:
                continue

        next_page_match = re.search(r'<li><a href="([^"]+)">Next</a></li>', content, re.IGNORECASE)
        if next_page_match:
            next_url_relative = html.unescape(next_page_match.group(1))
            next_url_absolute = urllib.parse.urljoin(url, next_url_relative)
            self.add_dir('[COLOR blue]Next Page >>>>[/COLOR]', next_url_absolute, 2, self.icons['default'])

        self.end_directory()

    def process_categories(self, dummy_url):
        self.logger.info("Processing category list")

        content = self.make_request(self.base_url)
        if not content:
            self.end_directory(); return

        select_match = re.search(r'<select\s+name=["\']cat["\'].*?id=["\']cat["\'].*?>(.*?)</select>', content, re.DOTALL | re.IGNORECASE)
        if select_match:
            options_html = select_match.group(1)
            options = re.findall(r'<option.*?value=["\'](\d+)["\'].*?>(.*?)</option>', options_html, re.DOTALL | re.IGNORECASE)

            for cat_value, cat_name in options:
                if int(cat_value) > 0:
                    cat_name_clean = html.unescape(cat_name).strip()
                    cat_url = f"{self.base_url}/?cat={cat_value}"
                    self.add_dir(cat_name_clean, cat_url, 2, self.icons['categories'])
        else:
            self.notify_error("Could not parse categories.")

        self.end_directory()

    def unpack_js(self, packed_js):
        try:
            import js2py
            context = js2py.EvalJs()
            unpacked = packed_js.strip()
            if unpacked.startswith('eval'):
                unpacked = 'var x' + unpacked[4:]
                context.execute(unpacked)
                return context.x
            return packed_js
        except Exception:
            return packed_js

    def decode_hclips_url(self, encoded_str):
        replacements = {
            '\u0410': 'A', '\u0412': 'B', '\u0421': 'C', '\u0415': 'E', '\u041d': 'H',
            '\u041a': 'K', '\u041c': 'M', '\u041e': 'O', '\u0420': 'P', '\u0422': 'T',
            '\u0425': 'X', '\u0430': 'a', '\u0441': 'c', '\u0435': 'e', '\u043e': 'o',
            '\u0440': 'p', '\u0445': 'x', '\u0443': 'y'
        }
        clean_str = encoded_str
        for cyr, lat in replacements.items():
            clean_str = clean_str.replace(cyr, lat)
        clean_str = clean_str.rstrip('~')
        
        try:
            pad = len(clean_str) % 4
            if pad: clean_str += "=" * (4 - pad)
            decoded_bytes = base64.b64decode(clean_str)
            return decoded_bytes.decode('utf-8')
        except Exception:
            return None

    def resolve_hclips(self, embed_url):
        self.logger.info(f"[FullXCinema] Scraping Hclips embed page: {embed_url}")
        html_content = self.make_request(embed_url, referer=self.base_url)
        if not html_content: return None

        stream_url = None
        
        try:
            vid_match = re.search(r'[\'"]video_id[\'"]\s*:\s*[\'"](\d+)[\'"]', html_content)
            lifetime_match = re.search(r'[\'"]lifetime[\'"]\s*:\s*[\'"](\d+)[\'"]', html_content)
            
            if vid_match and lifetime_match:
                video_id = vid_match.group(1)
                lifetime = lifetime_match.group(1)
                
                api_url = f"https://hclips.com/api/videofile.php?video_id={video_id}&lifetime={lifetime}"
                api_content = self.make_request(api_url, referer="https://hclips.com/")
                
                if api_content:
                    file_match = re.search(r'[\'"]file[\'"]\s*:\s*[\'"](https?://[^"\']+)[\'"]', api_content)
                    if file_match:
                        stream_url = file_match.group(1).replace('\\/', '/')
                    elif api_content.strip().startswith('http'):
                        stream_url = api_content.strip()
                    else:
                        try:
                            data = json.loads(api_content)
                            raw = None
                            if isinstance(data, list) and data: 
                                raw = data[0].get('video_url') or data[0].get('file')
                            elif isinstance(data, dict): 
                                raw = data.get('video_url') or data.get('file')
                            
                            if raw:
                                if raw.startswith('http'): 
                                    stream_url = raw
                                else:
                                    decoded = self.decode_hclips_url(raw)
                                    if decoded: 
                                        stream_url = decoded if decoded.startswith('http') else urllib.parse.urljoin("https://hclips.com", decoded)
                        except Exception: 
                            pass
        except Exception:
            pass

        if not stream_url:
            if "eval(function(p,a,c,k,e,d)" in html_content:
                packed_match = re.search(r'(eval\(function\(p,a,c,k,e,d\).*?\.split\(\'\|\'\).*?\)\))', html_content, re.DOTALL)
                if packed_match:
                    unpacked = self.unpack_js(packed_match.group(1))
                    if unpacked: html_content += "\n" + str(unpacked)

            patterns = [
                r'fetch\s*\(\s*["\'](https?://[^"\']*hclips\.ahcdn\.com[^"\']*)["\']',
                r'["\'](https?://[^"\']*hclips\.ahcdn\.com[^"\']*)["\']',
                r'file\s*:\s*["\']([^"\']+\.m3u8[^"\']*)["\']',
                r'src\s*:\s*["\']([^"\']+\.m3u8[^"\']*)["\']',
            ]
            for p in patterns:
                match = re.search(p, html_content)
                if match:
                    stream_url = match.group(1).replace('\\/', '/')
                    break

        if stream_url:
            return stream_url
        
        return None

    def calc_eporner_hash(self, hash_str):
        parts = []
        for i in range(0, len(hash_str), 8):
            try:
                num = int(hash_str[i:i+8], 16)
                table = '0123456789abcdefghijklmnopqrstuvwxyz'
                s = ''
                if num == 0: s = table[0]
                while num: s = table[num % 36] + s; num //= 36
                parts.append(s)
            except Exception: pass
        return ''.join(parts)

    def resolve_eporner(self, embed_url):
        self.logger.info(f"[FullXCinema] Resolving Eporner via API: {embed_url}")
        
        content = self.make_request(embed_url, referer=self.base_url)
        if not content: return None
        
        embed_match = re.search(r"vid\s*=\s*'(.+?)'.*?hash\s*=\s*'(.+?)'", content, re.DOTALL)
        if not embed_match: return None
            
        vid, hash_str = embed_match.groups()
        hash_val = self.calc_eporner_hash(hash_str)
        
        api_url = f'{self.eporner_base}xhr/video/{vid}?hash={hash_val}&domain=www.eporner.com&fallback=false&embed=true&supportedFormats=dash,mp4'
        
        headers = {
            'User-Agent': self.ua,
            'Accept': '*/*',
            'Referer': embed_url,
            'Origin': 'https://www.eporner.com',
            'X-Requested-With': 'XMLHttpRequest'
        }
        
        json_content = self.make_request(api_url, headers=headers)
        if not json_content: return None

        try:
            data = json.loads(json_content)
            stream_url = None
            
            sources = data.get('sources', {}).get('mp4', {})
            if isinstance(sources, dict):
                mp4_urls = [v.get('src', '') for v in sources.values() if isinstance(v, dict) and v.get('src')]
                if mp4_urls:
                    stream_url = max(mp4_urls, key=lambda u: int(re.search(r'(\d+)p', u).group(1) if re.search(r'(\d+)p', u) else 0), default=None)
            
            if not stream_url:
                stream_url = data.get('sources', {}).get('hls', {}).get('auto', {}).get('src')
                
            if stream_url:
                return stream_url
                
        except Exception:
            pass

        return None

    def _play_stream(self, stream_url, referer_url=None, mime_type='video/mp4'):
        # WICHTIG: Referer nur für Hclips/Eporner anhängen. 
        # Für direkte MP4 Links KEINE Header erzwingen, da dies das Seeking/Probing in Kodi verlangsamt (6-10s Delay).
        if referer_url:
            headers = {'User-Agent': self.ua, 'Referer': referer_url}
            url_final = stream_url + '|' + urllib.parse.urlencode(headers)
        else:
            url_final = stream_url

        list_item = xbmcgui.ListItem(path=url_final)
        list_item.setMimeType(mime_type)
        list_item.setProperty('IsPlayable', 'true')
        list_item.setContentLookup(False)

        if mime_type == 'application/vnd.apple.mpegurl':
            list_item.setProperty('inputstream', 'inputstream.adaptive')
            list_item.setProperty('inputstream.adaptive.manifest_type', 'hls')
            
        xbmcplugin.setResolvedUrl(self.addon_handle, True, list_item)

    def play_video(self, url):
        self.logger.info(f"Attempting to play video from: {url}")
        content = self.make_request(url)
        if not content: 
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem(path=url))
            return

        # Direct Links (KEIN Referer, damit Kodi nativ probed)
        mp4_match = re.search(r'["\'](https?://[^"\']+\.mp4(?:\?[^"\']*)?)["\']', content, re.IGNORECASE)
        if mp4_match:
            self._play_stream(html.unescape(mp4_match.group(1)))
            return

        m3u8_match = re.search(r'["\'](https?://[^"\']+\.m3u8(?:\?[^"\']*)?)["\']', content, re.IGNORECASE)
        if m3u8_match:
            self._play_stream(html.unescape(m3u8_match.group(1)), mime_type='application/vnd.apple.mpegurl')
            return

        self.logger.info("No direct video links found. Searching for embeds/iframes...")
        iframe_tags = re.findall(r'<iframe(.*?)>', content, re.IGNORECASE | re.DOTALL)
        ad_keywords = ['magsrv', 'ads', 'banner', 'juicyads', 'trafficjunky', 'ero-advertising', 'pop']

        for iframe_content in iframe_tags:
            srcs = re.findall(r'(?:src|data-src)=["\']([^"\']+)["\']', iframe_content, re.IGNORECASE)
            
            for iframe_src in srcs:
                iframe_src = html.unescape(iframe_src)
                if iframe_src.strip() == "about:blank": continue
                if any(k in iframe_src.lower() for k in ad_keywords): continue

                if iframe_src.startswith('//'): iframe_src = 'https:' + iframe_src
                elif iframe_src.startswith('/'): iframe_src = urllib.parse.urljoin(self.base_url, iframe_src)

                self.logger.info(f"Found potential video iframe: {iframe_src}")

                if 'videohclips.com' in iframe_src or 'hclips.com' in iframe_src:
                    stream_url = self.resolve_hclips(iframe_src)
                    if stream_url:
                        mime = 'application/vnd.apple.mpegurl' if '.m3u8' in stream_url else 'video/mp4'
                        self._play_stream(stream_url, referer_url="https://hclips.com/", mime_type=mime)
                        return

                if 'eporner.com' in iframe_src:
                    stream_url = self.resolve_eporner(iframe_src)
                    if stream_url:
                        self._play_stream(stream_url, referer_url="https://www.eporner.com/")
                        return

                self.logger.info(f"Attempting to resolve iframe with generic resolver: {iframe_src}")
                try:
                    result = resolver.resolve(iframe_src)
                    stream_url = None
                    if isinstance(result, tuple): stream_url = result[0] 
                    elif isinstance(result, str): stream_url = result

                    if stream_url and stream_url.startswith('http') and not 'videohclips.com/embed' in stream_url and not 'eporner.com/embed' in stream_url:
                        self.logger.info(f"Resolver returned: {stream_url}")
                        self._play_stream(stream_url)
                        return
                except Exception: pass

        self.logger.error(f"Could not find playable stream on page {url}")
        self.notify_error("No playable stream found.")
        xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem(path=url))

    def search(self, query):
        if not query: return
        search_url = f"{self.base_url}/?s={urllib.parse.quote_plus(query)}"
        self.process_content(search_url)