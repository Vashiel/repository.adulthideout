#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os
import xbmcaddon
import xbmc

try:
    addon_path = xbmcaddon.Addon().getAddonInfo('path')
    
    vendor_path = os.path.join(addon_path, 'resources', 'lib', 'vendor')
    
    if vendor_path not in sys.path:
        sys.path.insert(0, vendor_path)
            
except Exception as e:
    xbmc.log(f"[AdultHideout-Hack] CRITICAL: Path Hack failed in pornzog.py: {e}", xbmc.LOGERROR)

import re
import urllib.parse
import html
import json
import base64
import xbmcgui
import xbmcplugin
import logging

try:
    import cloudscraper
    _HAS_CF = True
except ImportError as e:
    xbmc.log(f"Pornzog: Import cloudscraper FAILED: {e}", xbmc.LOGERROR)
    _HAS_CF = False
except Exception as e:
    xbmc.log(f"Pornzog: Error importing cloudscraper (missing dependency?): {e}", xbmc.LOGERROR)
    _HAS_CF = False

from resources.lib.base_website import BaseWebsite

class TxxxDecoder:
    def _clean_b64_string(self, b64_string):
        if not b64_string or len(b64_string) == 0: return None
        replacements = {
            '\u0410': 'A', '\u0412': 'B', '\u0421': 'C', '\u0415': 'E', '\u041d': 'H', '\u041a': 'K',
            '\u041c': 'M', '\u041e': 'O', '\u0420': 'P', '\u0422': 'T', '\u0425': 'X',
            '\u0430': 'a', '\u0441': 'c', '\u0435': 'e', '\u043a': 'k', '\u043e': 'o',
            '\u0440': 'p', '\u0445': 'x', '\u0443': 'y', '~': '=',
            '\u0416': 'W', '\u0417': '3', '\u0418': 'B', '\u041b': 'JI', '\u0423': 'Y', '\u0424': '4',
            '\u0427': 'X', '\u042f': '9', '\u0431': '6', '\u0432': 'B', '\u0433': 'r', '\u0434': 'A',
            '\u0436': 'q', '\u0437': '7', '\u0438': 'u', '\u043b': 'JI', '\u0442': 'b', '\u0444': 'O',
            '\u0447': 'x', '\u044f': 'q'
        }
        for original, replacement in replacements.items():
            b64_string = b64_string.replace(original, replacement)
        b64_string = b64_string.replace('\n', '').replace('\r', '').replace('\t', '')
        return b64_string

    def decode_stream_url(self, encoded_path_raw, base_iframe_url, video_page_url, logger):
        try:
            encoded_path_replaced = self._clean_b64_string(encoded_path_raw)
            path_b64, params_b64 = "", ""
            if ',' in encoded_path_replaced:
                path_b64, params_b64 = encoded_path_replaced.split(',', 1)
            else: path_b64 = encoded_path_replaced
            valid_b64_chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/='
            path_b64_cleaned = ''.join(c for c in path_b64 if c in valid_b64_chars)
            missing_padding = len(path_b64_cleaned) % 4
            if missing_padding: path_b64_cleaned += '=' * (4 - missing_padding)
            decoded_path = base64.b64decode(path_b64_cleaned).decode('utf-8', 'ignore').strip()
            iframe_base = urllib.parse.urlunparse(urllib.parse.urlparse(base_iframe_url)[:2] + ('', '', '', ''))
            full_stream_url = urllib.parse.urljoin(iframe_base, decoded_path)
            if params_b64:
                params_b64_cleaned = ''.join(c for c in params_b64 if c in valid_b64_chars)
                missing_padding = len(params_b64_cleaned) % 4
                if missing_padding: params_b64_cleaned += '=' * (4 - missing_padding)
                decoded_params = base64.b64decode(params_b64_cleaned).decode('utf-8', 'ignore').strip()
                full_stream_url += '?' + decoded_params
            return full_stream_url
        except Exception as e:
            if logger: logger.error(f"TXXX Decoder failed inside Pornzog: {e} | Raw: {encoded_path_raw[:50]}")
            return None

class Pornzog(BaseWebsite):

    def __init__(self, addon_handle):
        super().__init__( name="pornzog", base_url="https://pornzog.com", search_url="https://pornzog.com/search/?s={}&o=recent", addon_handle=addon_handle)
        self.label = 'PornZOG'
        self.logger.setLevel(logging.WARNING)
        
        if not _HAS_CF:
            self.logger.error("Cloudscraper module is missing. This site may not work.")
            self.notify_error("Cloudscraper module is missing.")
            
        self.scraper = None 
            
        self.sort_options = ["Popular", "Newest", "Top Rated", "Most Viewed", "Longest"]
        self.sort_paths = {"Popular": "/", "Newest": "/search/?o=recent", "Top Rated": "/search/?o=rated", "Most Viewed": "/search/?o=viewed", "Longest": "/search/?o=longest"}
        self.icons = {'default': self.icon, 'search': self.icon, 'categories': self.icon, 'pornstars': self.icon, 'settings': self.icon}
        self.txxx_decoder = TxxxDecoder()
        
        self.txxx_like_domains = [
            'txxx.com', 'videotxxx.com', 'vxxx.com', 
            'privatehomeclips.com', 'desi-porn.tube', 'vid-xm.com', 
            'xmilf.com', 'vid-ip.com', 'inporn.com'
        ]
        
        self.id_in_url_domains = [
            'ooxxx.com', 'manysex.com', 'hclips.com', 'upornia.com', 'hdzog.com', 
            'hotmovs.com', 'voyeurhit.com', 'tubepornclassic.com', 'vjav.com', 
            'tporn.tube', 'thegay.com', 'shemalez.com',
            'videovoyeurhit.com'
        ]
        
        self.sponsor_domains = ['fupxy.com', 'kepxy.com', 'vid-bx.com', 'vid-01t.com']
        
        self.all_txxx_network_domains = self.txxx_like_domains + self.id_in_url_domains
        self.all_video_domains_regex = '|'.join(re.escape(d.replace('www.', '')) for d in self.sponsor_domains + self.all_txxx_network_domains)

    def get_session(self):
        if self.scraper:
            return self.scraper

        self.logger.info(f"[{self.name}] Initializing new Cloudscraper session...")
        
        if not _HAS_CF:
            self.logger.error(f"[{self.name}] Cloudscraper library is not available.")
            self.notify_error("Cloudscraper library missing.")
            return None

        try:
            scraper = cloudscraper.create_scraper(
                browser={'custom': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36'}, 
                delay=5
            )
            self.scraper = scraper 
            return self.scraper
            
        except Exception as e:
            self.logger.error(f"[{self.name}] Failed to create scraper session: {e}")
            self.notify_error(f"Failed to start session: {e}")
            return None

    def make_request(self, url, referer=None, is_api=False):
        scraper = self.get_session()
        if not scraper:
            self.notify_error("Cloudscraper session is not valid. Request failed.")
            return None
            
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
                'Accept-Language': 'en-US,en;q=0.9'
            }
            if is_api:
                 headers['Accept'] = 'application/json, text/plain, */*'
                 headers['X-Requested-With'] = 'XMLHttpRequest'
            else:
                 headers['Accept'] = 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8'
            if referer: headers['Referer'] = referer
            
            resp = scraper.get(url, headers=headers, timeout=20, allow_redirects=True) 
            
            if resp.status_code == 404:
                self.logger.error(f"Request failed for {url}: 404 Not Found (Link ist tot)")
                self.notify_error("This link appears to be broken (404).")
                return None
            
            resp.raise_for_status()

            content = resp.content.decode('utf-8', 'ignore')
            if not is_api and ("Just a moment..." in content or "cf-browser-verification" in content):
                 self.logger.error("Cloudflare block detected.")
                 self.notify_error("Cloudflare block detected.")
                 return None
            return content
        except Exception as e:
            if "404 Client Error" in str(e):
                self.logger.error(f"Request failed (404): {url} -> {e}")
                self.notify_error("This link appears to be broken (404).")
                return None
            
            self.logger.error(f"Request failed for {url}: {e}")
            return None

    def get_start_url_and_label(self):
        label = f"{self.name.capitalize()}"; setting_id = f"{self.name}_sort_by"; sort_idx = 0
        try:
            saved_setting = self.addon.getSetting(setting_id)
            try: sort_idx = int(saved_setting)
            except ValueError:
                 try: sort_idx = self.sort_options.index(saved_setting)
                 except ValueError: sort_idx = 0
            if not (0 <= sort_idx < len(self.sort_options)): sort_idx = 0
        except Exception: sort_idx = 0
        sort_option = self.sort_options[sort_idx]; sort_path = self.sort_paths.get(sort_option, "/")
        url = urllib.parse.urljoin(self.base_url, sort_path)
        final_label = f"{label} [COLOR yellow]{sort_option}[/COLOR]"
        return url, final_label

    def process_content(self, url):
        content = self.make_request(url)
        if not content: return self.end_directory()

        is_search = "/search/" in url
        is_main_or_sort_page = (url.strip('/') == self.base_url.strip('/') or
                                (is_search and "?o=" in url and "&p=" not in url and "/page/" not in url))

        if is_main_or_sort_page:
            self.add_dir('[COLOR blue]Search[/COLOR]', '', 5, self.icons['search'], name_param=self.name)
            self.add_dir('Categories', f"{self.base_url}/categories/", 8, self.icons['categories'])
            self.add_dir('Pornstars', f"{self.base_url}/pornstars/", 9, self.icons['pornstars'])

        list_html, container_type = None, "unknown"
        patterns = [
            (r'<ul[^>]+class=["\'][^"\']*thumbs-list[^"\']*["\'][^>]*>(.*?)</ul>', "thumbs-list"),
            (r'<div[^>]+class=["\'][^"\']*videos-list[^"\']*["\'][^>]*>(.*?)</div>', "videos-list"),
        ]
        for pattern, type_name in patterns:
            match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
            if match:
                container_type, list_html = type_name, match.group(1)
                break
        if not list_html:
             potential_containers = re.findall(r'<div[^>]*>(.*?)</div>|<ul[^>]*>(.*?)</ul>', content, re.DOTALL | re.IGNORECASE)
             best_match_html, max_video_links = "", 0
             for group1, group2 in potential_containers:
                 html_block = group1 or group2
                 video_links = re.findall(r'<a[^>]+href=["\'](/video/|https?://(?:' + self.all_video_domains_regex + r')\.(?:com|tube)/)[^"\']+\S+["\']', html_block, re.IGNORECASE)
                 if len(video_links) > 10 and len(video_links) > max_video_links and 'nav' not in html_block[:100].lower() and 'footer' not in html_block[:100].lower():
                     max_video_links, best_match_html, container_type = len(video_links), html_block, "generic-video-block"
             if best_match_html:
                 list_html = best_match_html
             else:
                 self.logger.error(f"CRITICAL - No suitable video container found on {url}.")
                 return self.end_directory()

        videos_added = 0
        added_urls = set()
        item_iterator = None
        items_found_count = 0
        use_fallback_iterator = False
        
        if container_type == "thumbs-list":
             item_iterator = re.finditer(r'<div[^>]+class=["\'][^"\']*thumb-video[^"\']*["\']>(.*?)</div>', list_html, re.DOTALL | re.IGNORECASE)
        elif container_type == "videos-list":
             item_iterator = re.finditer(r'<div[^>]+class=["\'][^"\']*(?:thumb|video)[^"\']*["\'][^>]*>(.*?)</div>', list_html, re.DOTALL | re.IGNORECASE)

        if item_iterator:
            item_matches = list(item_iterator)
            items_contain_video = any(re.search(r'<a[^>]+href=["\'](/video/|https?://(?:' + self.all_video_domains_regex + r')\.(?:com|tube)/)', m.group(1), re.IGNORECASE) for m in item_matches)
            if items_contain_video:
                item_iterator = iter(item_matches)
                items_found_count = len(item_matches)
            else:
                use_fallback_iterator = True
        else:
             use_fallback_iterator = True

        if use_fallback_iterator:
            item_iterator = re.finditer(r'<(li|div)[^>]*>(.*?<a[^>]+href=["\'](/video/[^"\']+[^"\'>]*|https?://(?:' + self.all_video_domains_regex + r')\.(?:com|tube)/[^"\']+)["\'][^>]*>.*?)</\1>', list_html, re.DOTALL | re.IGNORECASE)

        for match_num, match in enumerate(item_iterator, 1):
            item_html = match.group(1) if items_found_count > 0 else match.group(2)
            if any(ad in item_html.lower() for ad in [' ad ', 'sponsor', 'promo', 'banner', 'track_ad']): continue
            
            href_match = re.search(r'<a[^>]+class=["\'][^"\']*thumb-video-link[^"\']*["\'][^>]+href=["\']([^"\']+)["\']|<a[^>]+href=["\'](/video/[^"\']+[^"\'>]*|https?://(?:' + self.all_video_domains_regex + r')\.(?:com|tube)/[^"\']+)["\']', item_html, re.IGNORECASE)
            if not href_match:
                 continue
            video_url_part = (href_match.group(1) or href_match.group(2)).strip()
            if '/feedback/' in video_url_part: continue
            full_video_url = urllib.parse.urljoin(self.base_url, video_url_part)
            if full_video_url in added_urls: continue

            title, clean_title = None, "Unknown Title"
            title_match = re.search(r'<a[^>]+title=["\']([^"\']+)["\']', item_html, re.IGNORECASE)
            if title_match: title = title_match.group(1)
            else:
                 alt_match = re.search(r'<img[^>]+alt=["\']([^"\']+)["\']', item_html, re.IGNORECASE)
                 if alt_match: title = alt_match.group(1)
                 else:
                     text_match = re.search(r'<a[^>]+class=["\'][^"\']*thumb-video-link[^"\']*["\'].*?>\s*<span[^>]*>(.*?)</span>\s*</a>', item_html, re.DOTALL | re.IGNORECASE) or \
                                  re.search(r'<a[^>]+href=["\']/video/.*?>(.*?)</a>', item_html, re.DOTALL | re.IGNORECASE)
                     if text_match:
                          link_text = re.sub(r'<[^>]+>', '', text_match.group(1)).strip()
                          if link_text: title = link_text
            if not title: continue
            clean_title = html.unescape(title.strip()); clean_title = re.sub(r'\s*(\d{1,2}:\d{2})\s*(hd)?\s*$', '', clean_title, flags=re.IGNORECASE).strip()
            if not clean_title: clean_title = "Untitled Video"
            
            duration_str = "N/A"
            seconds = 0
            duration_patterns = [r'<div[^>]+class=["\']duration["\'][^>]*>([^<]+)</div>', r'<span[^>]+class=["\']duration["\'][^>]*>([^<]+)</span>', r'duration["\']>\s*([\d:]+)\s*<', r'([\d:]{3,8})</span>', r'>\s*([\d:]{3,8})\s*<']
            for pat in duration_patterns:
                m = re.search(pat, item_html, re.IGNORECASE)
                if m:
                    duration_text = m.group(1).strip()
                    if re.match(r'^(\d{1,2}:)?\d{1,2}:\d{2}$', duration_text):
                        try:
                            parts = duration_text.split(':')
                            if len(parts) == 3: # HH:MM:SS
                                seconds = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
                                duration_str = f"{int(parts[0]):02}:{int(parts[1]):02}:{int(parts[2]):02}"
                            elif len(parts) == 2: # MM:SS
                                seconds = int(parts[0]) * 60 + int(parts[1])
                                duration_str = f"{int(parts[0]):02}:{int(parts[1]):02}"
                        except ValueError:
                            seconds = 0
                            duration_str = "N/A"
                        break
            
            thumb_url = self.icon
            thumb_patterns = [r'data-original=["\']([^"\']+)["\']', r'data-src=["\']([^"\']+)["\']', r'<img[^>]+class=["\'][^"\']*thumb[^"\']*["\'][^>]+src=["\']([^"\']+)["\']']
            for pat in thumb_patterns:
                 m = re.search(pat, item_html, re.IGNORECASE)
                 if m:
                     potential_thumb = m.group(1).strip()
                     if not potential_thumb.startswith(('data:', 'http://:', 'javascript:')) and len(potential_thumb) > 10 :
                           thumb_url = potential_thumb
                           break
            thumb_url_abs = urllib.parse.urljoin(self.base_url, thumb_url)
            source_name = "PornZOG"; source_match = re.search(r'<p[^>]+class=["\']source["\'][^>]*>\s*<a[^>]*>([^<]+)</a>', item_html, re.IGNORECASE)
            if source_match: source_name = source_match.group(1).strip()
            
            label = f"{clean_title} [COLOR lime]({duration_str})[/COLOR] [COLOR yellow]({source_name})[/COLOR]"
            info_labels = {'title': clean_title, 'duration': seconds, 'studio': source_name}
            
            self.add_link(label, full_video_url, 4, thumb_url_abs, self.fanart, info_labels=info_labels); added_urls.add(full_video_url); videos_added += 1
            if videos_added >= 60: break
        
        pag_match = re.search(r'<ul[^>]+class=["\']pagination["\'][^>]*>(.*?)</ul>', content, re.DOTALL | re.IGNORECASE)
        if pag_match:
            pag_html = pag_match.group(1); next_link_patterns = [r'class=["\'][^"\']*(?:next|arrow_pag)[^"\']*["\'][^>]*href=["\']([^"\']+)["\']', r'href=["\']([^"\']+)["\'][^>]*>\s*&gt;']; next_rel = None
            for pat in next_link_patterns:
                 next_match = re.search(pat, pag_html, re.IGNORECASE | re.DOTALL)
                 if next_match:
                      potential_rel = next_match.group(1) or (next_match.group(2) if len(next_match.groups()) > 1 else None)
                      if potential_rel: next_rel = html.unescape(potential_rel.strip()); break
            if next_rel and next_rel != '#':
                 next_abs = urllib.parse.urljoin(url, next_rel)
                 self.add_dir('[COLOR blue]Next Page >>>>[/COLOR]', next_abs, 2, self.icons['default'])
        
        self.end_directory()

    def process_categories(self, url):
         content = self.make_request(url)
         if not content: return self.end_directory()
         
         cat_container_match = re.search(r'<ul[^>]+class=["\'][^"\']*thumbs-list[^"\']*["\']>(.*?)</ul>', content, re.DOTALL | re.IGNORECASE)
         if not cat_container_match:
             self.logger.error(f"Categories: Konnte 'thumbs-list' Container nicht finden.")
             html_to_search = content
             cat_matches = re.findall(r'<a[^>]+href=["\'](/categories/[^/"]+/|/[^/"]+/)[^"\']*["\'][^>]*>\s*([^<]+?)\s*<', html_to_search, re.DOTALL | re.IGNORECASE)
             categories_added, added_urls = 0, set()
             for cat_url_part, cat_title in cat_matches:
                 cat_title_clean = html.unescape(cat_title.strip())
                 if cat_title_clean.lower() in ['home', 'new videos', 'pornstars', 'categories', 'videos', 'popular', 'top rated']: continue
                 full_cat_url = urllib.parse.urljoin(self.base_url, cat_url_part)
                 if cat_url_part.endswith('/') and full_cat_url.count('/') <= 4:
                      full_cat_url = urllib.parse.urljoin(full_cat_url, 'recent/')
                 if full_cat_url not in added_urls:
                     self.add_dir(cat_title_clean, full_cat_url, 2, self.icons['categories'])
                     added_urls.add(full_cat_url); categories_added += 1
         
         else:
             html_to_search = cat_container_match.group(1)
             cat_blocks = re.findall(r'<li>(.*?<a[^>]+class=["\']thumb-category["\'][^>]*>.*?)</li>', html_to_search, re.DOTALL | re.IGNORECASE)
             
             categories_added, added_urls = 0, set()
             
             for item_html in cat_blocks:
                 url_match = re.search(r'<a[^>]+class=["\']thumb-category["\'][^>]*href=["\']([^"\']+)["\']', item_html, re.IGNORECASE)
                 title_match = re.search(r'<div[^>]+class=["\']title["\'][^>]*>\s*<span>([^<]+)</span>', item_html, re.IGNORECASE)
                 thumb_match = re.search(r'data-original=["\']([^"\']+)["\']', item_html, re.IGNORECASE)
                 count_match = re.search(r'class=["\']jsCatVideosCount["\']\s*>([\d,]+)<', item_html, re.IGNORECASE)

                 if not (url_match and title_match and thumb_match):
                     continue
                     
                 cat_url_part = url_match.group(1)
                 cat_title = html.unescape(title_match.group(1).strip())
                 thumb_url = html.unescape(thumb_match.group(1).strip())
                 thumb_url_abs = urllib.parse.urljoin(self.base_url, thumb_url)
                 video_count = count_match.group(1).strip() if count_match else '?'

                 full_cat_url = urllib.parse.urljoin(self.base_url, cat_url_part)
                 if not full_cat_url.endswith('/'): full_cat_url += '/'
                 full_cat_url += 'recent/'

                 if full_cat_url not in added_urls:
                     label = f"{cat_title} ({video_count} videos)"
                     self.add_dir(label, full_cat_url, 2, thumb_url_abs)
                     added_urls.add(full_cat_url); categories_added += 1
             
         pag_match = re.search(r'<div[^>]+class=["\']paginator["\'][^>]*data-page=["\'](\d+)["\'][^>]*data-url=["\']([^"\']+)["\'][^>]*data-max=["\'](\d+)["\']', content, re.DOTALL | re.IGNORECASE)
         if pag_match:
             try:
                 current_page = int(pag_match.group(1))
                 url_template = pag_match.group(2)
                 max_page = int(pag_match.group(3))
                 
                 if current_page < max_page:
                     next_page_num = current_page + 1
                     next_url_part = url_template.replace('%p%', str(next_page_num))
                     next_abs = urllib.parse.urljoin(self.base_url, next_url_part)
                     self.add_dir('[COLOR blue]Next Page >>>>[/COLOR]', next_abs, 8, self.icons['default']) 
             except Exception as e:
                 self.logger.error(f"Error parsing paginator: {e}")
         else:
             old_pag_match = re.search(r'<ul[^>]+class=["\']pagination["\'][^>]*>(.*?)</ul>', content, re.DOTALL | re.IGNORECASE)
             if old_pag_match:
                 pag_html = old_pag_match.group(1)
                 next_match = re.search(r'class=["\'][^"\']*(?:next|arrow_pag)[^"\']*["\'][^>]*href=["\']([^"\']+)["\']|href=["\']([^"\']+)["\'][^>]*>\s*&gt;', pag_html, re.IGNORECASE | re.DOTALL)
                 if next_match:
                     next_rel = html.unescape((next_match.group(1) or next_match.group(2)).strip())
                     if next_rel and next_rel != '#':
                          self.add_dir('[COLOR blue]Next Page >>>>[/COLOR]', urllib.parse.urljoin(url, next_rel), 8, self.icons['default'])

         self.end_directory()

    def process_actresses_list(self, url):
         content = self.make_request(url)
         if not content: return self.end_directory()
         
         star_container_match = re.search(r'<ul[^>]+class=["\'][^"\']*thumbs-list--models[^"\']*["\'][^>]*>(.*?)</ul>', content, re.DOTALL | re.IGNORECASE)
         html_to_search = star_container_match.group(1) if star_container_match else content
         
         star_blocks = re.findall(r'<(li|div)[^>]*>(.*?<a[^>]+class=["\']thumb-model["\'][^>]*href=["\'](/pornstar/[^/"]+/)[^"\']*["\'][^>]*>.*?</\1)>', html_to_search, re.DOTALL | re.IGNORECASE)
         
         stars_added, added_urls = 0, set()
         
         for _, item_html, star_url_part in star_blocks:
             star_name = None
             name_match = re.search(r'<div[^>]+class=["\']title["\'][^>]*>\s*<span>([^<]+)</span>', item_html, re.IGNORECASE)
             if name_match: star_name = name_match.group(1).strip()
             if not star_name:
                 alt_match = re.search(r'<img[^>]+alt=["\']([^"\']+)["\']', item_html, re.IGNORECASE)
                 if alt_match: star_name = alt_match.group(1).strip()
             if not star_name: continue
             
             video_count = '?'
             count_match = re.search(r'<span[^>]+class=["\']videos-amount["\'][^>]*>.*?(\d+)\s*</span>', item_html, re.DOTALL | re.IGNORECASE)
             if count_match:
                 video_count = count_match.group(1)
             
             thumb_url = self.icons['pornstars'] 
             thumb_patterns = [
                 r'data-original=["\']([^"\']+)["\']', 
                 r'data-src=["\']([^"\']+)["\']', 
                 r'<img[^>]+src=["\']([^"\']+)["\']'
             ]
             for pat in thumb_patterns:
                  m = re.search(pat, item_html, re.IGNORECASE)
                  if m:
                      potential_thumb = m.group(1).strip()
                      if not potential_thumb.startswith(('data:', 'http://:', 'javascript:')) and len(potential_thumb) > 10 :
                            thumb_url = potential_thumb
                            break
             thumb_url_abs = urllib.parse.urljoin(self.base_url, thumb_url)

             full_star_url = urllib.parse.urljoin(self.base_url, star_url_part)
             if full_star_url not in added_urls:
                 label = f"{html.unescape(star_name)} ({video_count} videos)"
                 self.add_dir(label, full_star_url, 2, thumb_url_abs) 
                 added_urls.add(full_star_url); stars_added += 1
                 
         pag_match = re.search(r'<div[^>]+class=["\']paginator["\'][^>]*data-page=["\'](\d+)["\'][^>]*data-url=["\']([^"\']+)["\'][^>]*data-max=["\'](\d+)["\']', content, re.DOTALL | re.IGNORECASE)
         if pag_match:
             try:
                 current_page = int(pag_match.group(1))
                 url_template = pag_match.group(2)
                 max_page = int(pag_match.group(3))
                 
                 if current_page < max_page:
                     next_page_num = current_page + 1
                     next_url_part = url_template.replace('%p%', str(next_page_num))
                     next_abs = urllib.parse.urljoin(self.base_url, next_url_part)
                     self.add_dir('[COLOR blue]Next Page >>>>[/COLOR]', next_abs, 9, self.icons['default'])
             except Exception as e:
                 self.logger.error(f"Error parsing paginator: {e}")

         self.end_directory()

    def play_video(self, url):
        original_pornzog_url = url

        if any(domain in url for domain in self.sponsor_domains):
             self.logger.warning(f"External sponsor link: {url}")
             sponsor_content = self.make_request(url, referer=self.base_url)
             stream_url = None
             if sponsor_content:
                  m3u8 = re.search(r'["\'](https?://[^"\']+\.m3u8[^"\']*)["\']', sponsor_content, re.IGNORECASE)
                  mp4 = re.search(r'["\'](https?://[^"\']+\.mp4[^"\']*)["\']', sponsor_content, re.IGNORECASE)
                  stream_url = m3u8.group(1) if m3u8 else mp4.group(1) if mp4 else None
                  if stream_url:
                      return self.resolve_stream(stream_url, url)
             
             if not sponsor_content:
                 return self.resolve_stream(None, original_pornzog_url, "Sponsor link is broken (404).")
             
             self.logger.warning(f"No stream found in sponsor page, trying direct play (will likely fail).")
             list_item = xbmcgui.ListItem(path=url); list_item.setProperty('IsPlayable', 'true')
             return xbmcplugin.setResolvedUrl(self.addon_handle, True, list_item)

        content = self.make_request(url, referer=self.base_url)
        if not content: 
            return self.resolve_stream(None, original_pornzog_url, "Failed to load main video page.")

        iframe_match = re.search(r'<iframe[^>]+src=["\']([^"\']+)["\']', content, re.IGNORECASE)
        iframe_script_match = re.search(r'document\.write\(.*?<iframe.*?src=["\']([^"\']+)["\']', content, re.IGNORECASE | re.DOTALL) if not iframe_match else None
        
        if not iframe_match and not iframe_script_match:
            stream_url = None
            m3u8 = re.search(r'["\'](https?://[^"\']+\.m3u8[^"\']*)["\']', content)
            mp4 = re.search(r'["\'](https?://[^"\']+\.mp4[^"\']*)["\']', content)
            if m3u8: stream_url = html.unescape(m3u8.group(1).replace('\\/', '/'))
            elif mp4: stream_url = html.unescape(mp4.group(1).replace('\\/', '/'))
            if stream_url:
                return self.resolve_stream(stream_url, original_pornzog_url)
            else:
                return self.resolve_stream(None, original_pornzog_url, "No iframe or direct stream found.")

        iframe_url = (iframe_match or iframe_script_match).group(1).strip()
        if iframe_url.startswith('//'): iframe_url = 'https:' + iframe_url
        elif not iframe_url.startswith('http'): iframe_url = urllib.parse.urljoin(url, iframe_url)
        iframe_url = iframe_url.replace('///', '//').replace('tube//', 'tube/')

        iframe_html = self.make_request(iframe_url, referer=url)
        if not iframe_html: return self.resolve_stream(None, original_pornzog_url, f"Failed to load iframe content from {urllib.parse.urlparse(iframe_url).netloc}")

        stream_url = None
        iframe_domain = urllib.parse.urlparse(iframe_url).netloc.replace('www.', '')
        video_id = None

        is_txxx_like = any(domain in iframe_domain for domain in self.txxx_like_domains)
        is_id_in_url = any(domain in iframe_domain for domain in self.id_in_url_domains)

        if is_txxx_like or is_id_in_url:
            constants_match = re.search(r'window\.constants\s*=\s*\{.*?["\']?video_id["\']?\s*:\s*["\']?(\d+)["\']?.*?};', iframe_html, re.DOTALL)
            if constants_match:
                 video_id = constants_match.group(1)
            
            if not video_id:
                 constants_match = re.search(r'["\']video_id["\']\s*:\s*["\'](\d+)["\']', iframe_html)
                 if constants_match:
                     video_id = constants_match.group(1)
            
            if not video_id:
                id_match = re.search(r'/(?:embed|embed-)(\d+)', iframe_url, re.IGNORECASE)
                if id_match:
                    video_id = id_match.group(1)

            if video_id:
                 iframe_base = urllib.parse.urlunparse(urllib.parse.urlparse(iframe_url)[:2] + ('', '', '', ''))
                 api_path = "/api/videofile.php" 
                 api_url = urllib.parse.urljoin(iframe_base, f"{api_path}?video_id={video_id}&lifetime=8640000")

                 api_response_str = self.make_request(api_url, referer=iframe_url, is_api=True)
                 if api_response_str:
                     try:
                         stream_info = json.loads(api_response_str)
                         if stream_info and isinstance(stream_info, list) and len(stream_info) > 0 and 'video_url' in stream_info[0]:
                             encoded_path = stream_info[0]['video_url']
                             stream_url = self.txxx_decoder.decode_stream_url(encoded_path, iframe_url, original_pornzog_url, self.logger)
                             if not stream_url: self.logger.error("TXXX-Like: Decoding failed.")
                         else: self.logger.warning("TXXX-Like: 'video_url' not found in API response.")
                     except Exception as e: self.logger.error(f"TXXX-Like: Failed to parse API JSON: {e}")
                 else: self.logger.error("TXXX-Like: API request failed.")
            else: self.logger.error(f"TXXX-Like: video_id not found in iframe for {iframe_domain}.")
        
        if not stream_url:
            m3u8 = re.search(r'["\'](https?://[^"\']+\.m3u8[^"\']*)["\']', iframe_html)
            mp4 = re.search(r'["\'](https?://[^"\']+\.mp4[^"\']*)["\']', iframe_html)
            if m3u8: stream_url = html.unescape(m3u8.group(1).replace('\\/', '/'))
            elif mp4: stream_url = html.unescape(mp4.group(1).replace('\\/', '/'))

            if not stream_url:
                 jw_setup = re.search(r'jwplayer\([^)]+\)\.setup\(\s*(\{.*?})\s*\);', iframe_html, re.DOTALL)
                 if jw_setup:
                     setup_str = jw_setup.group(1)
                     m3u8_jw = re.search(r'["\']?file["\']?\s*:\s*["\']([^"\']+\.m3u8[^"\']*)["\']', setup_str)
                     mp4_jw = re.search(r'["\']?file["\']?\s*:\s*["\']([^"\']+\.mp4[^"\']*)["\']', setup_str)
                     if m3u8_jw: stream_url = html.unescape(m3u8_jw.group(1).replace('\\/', '/'))
                     elif mp4_jw: stream_url = html.unescape(mp4_jw.group(1).replace('\\/', '/'))

            if not stream_url:
                 scripts = re.findall(r'<script[^>]*>(.*?)</script>', iframe_html, re.DOTALL)
                 for script in scripts:
                     m3u8_script = re.search(r'["\'](https?://[^"\']+\.m3u8[^"\']*)["\']', script)
                     mp4_script = re.search(r'["\'](https?://[^"\']+\.mp4[^"\']*)["\']', script)
                     if m3u8_script: stream_url = html.unescape(m3u8_script.group(1).replace('\\/', '/')); break
                     elif mp4_script: stream_url = html.unescape(mp4_script.group(1).replace('\\/', '/')); break

        if stream_url:
            self.resolve_stream(stream_url, iframe_url)
        else:
            msg = f"No stream found. Player ({iframe_domain}) may not be supported."
            self.resolve_stream(None, original_pornzog_url, msg)


    def resolve_stream(self, stream_url, referer_url, error_msg="Could not find playable stream URL."):
        if stream_url:
            list_item = xbmcgui.ListItem(path=stream_url)
            list_item.setProperty('IsPlayable', 'true')
            scraper = self.get_session()
            user_agent = scraper.headers.get('User-Agent', 'Mozilla/5.0') if scraper else 'Mozilla/5.0'
            
            headers = f"Referer={urllib.parse.quote(referer_url)}&User-Agent={urllib.parse.quote(user_agent)}"
            if '.m3u8' in stream_url:
                list_item.setMimeType('application/vnd.apple.mpegurl')
                list_item.setProperty('inputstream', 'inputstream.adaptive')
                list_item.setProperty('inputstream.adaptive.manifest_type', 'hls')
                list_item.setProperty('inputstream.adaptive.stream_headers', headers)
            elif '.mp4' in stream_url:
                list_item.setMimeType('video/mp4')
                list_item.setProperty('Referer', referer_url)
                list_item.setProperty('User-Agent', user_agent)
            xbmcplugin.setResolvedUrl(self.addon_handle, True, list_item)
        else:
            self.logger.error(f"{error_msg} (Referer/Original: {referer_url})")
            self.notify_error(error_msg)
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem(path=''))


    def search(self, query):
        if not query: return
        try:
            safe_query = urllib.parse.quote_plus(str(query))
            search_url = self.search_url.format(safe_query)
            self.process_content(search_url)
        except Exception as e:
            self.logger.error(f"Error during search for '{query}': {e}")
            self.notify_error(f"Search failed: {e}")
            self.end_directory()