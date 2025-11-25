#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
import sys
import urllib.parse
import warnings
import html
import os
import threading
import json
import http.cookiejar
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import xbmc
import xbmcgui
import xbmcplugin
import xbmcvfs
import xbmcaddon

from resources.lib.base_website import BaseWebsite
from resources.lib.proxy_utils import ProxyController, PlaybackGuard, _DEFAULT_UA

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
except Exception:
    import requests
    _HAS_CF = False

warnings.filterwarnings('ignore')

# === GLOBAL SESSION CACHE ===
_SESSION = None
_LOCK = threading.Lock()
# ============================

class NoodleMagazine(BaseWebsite):
    def __init__(self, addon_handle):
        super().__init__(
            name='noodlemagazine',
            base_url='https://noodlemagazine.com',
            search_url='https://noodlemagazine.com/video/{}/',
            addon_handle=addon_handle
        )

        self.filter_presets = {
            'Now': '/now',
            'Popular Recent': '/popular/recent?sort_by=views&sort_order=desc',
            'Popular Day': '/popular/day?sort_by=views&sort_order=desc',
            'Popular Week': '/popular/week?sort_by=views&sort_order=desc',
            'Popular Month': '/popular/month?sort_by=views&sort_order=desc',
            'Popular Recent (Long)': '/popular/recent?sort_by=views&sort_order=desc&length_min=10',
            'Popular Recent (Short)': '/popular/recent?sort_by=views&sort_order=desc&length_max=5',
            'Popular Recent HD': '/popular/recent?sort_by=views&sort_order=desc&hd=1',
            'Popular Week (Long)': '/popular/week?sort_by=views&sort_order=desc&length_min=10',
            'Popular Week (Short)': '/popular/week?sort_by=views&sort_order=desc&length_max=5',
            'Popular Week HD': '/popular/week?sort_by=views&sort_order=desc&hd=1',
        }
        
        self.sort_options = list(self.filter_presets.keys())
        self.sort_paths = self.filter_presets
        
        self.session = None
        try:
            profile = xbmcvfs.translatePath(self.addon.getAddonInfo('profile'))
        except Exception:
            profile = ""
        self.cookie_file = os.path.join(profile, 'nm_cookies.jar')

    def get_session(self):
        global _SESSION, _LOCK
        with _LOCK:
            if self.session:
                return self.session
            
            if _SESSION:
                self.logger.info("[NM] Reusing cached Cloudscraper session.")
                self.session = _SESSION
                return self.session

            self.logger.info("[NM] Initializing new Cloudscraper session...")
            
            cookie_jar = http.cookiejar.MozillaCookieJar(self.cookie_file)
            if xbmcvfs.exists(self.cookie_file):
                try:
                    cookie_jar.load(ignore_discard=True, ignore_expires=True)
                    self.logger.info(f"[NM] Loaded {len(cookie_jar)} cookies from file.")
                except Exception as e:
                    self.logger.warning(f"[NM] Could not load cookies: {e}")

            if _HAS_CF:
                session = cloudscraper.create_scraper(browser={'custom': _DEFAULT_UA})
            else:
                session = requests.Session()
                session.headers.update({'User-Agent': _DEFAULT_UA})
            
            session.cookies.update(cookie_jar)
            
            self.session = session
            _SESSION = session
            return self.session

    def save_cookies(self):
        session = self.get_session()
        if session and hasattr(session, 'cookies'):
            temp_jar = http.cookiejar.MozillaCookieJar(self.cookie_file)
            for c in session.cookies:
                temp_jar.set_cookie(c)
            
            try:
                temp_jar.save(self.cookie_file, ignore_discard=True, ignore_expires=True)
            except Exception as e:
                self.logger.error(f"[NM] Failed to save cookies: {e}")

    def _get_kodi_thumb_url(self, url):
        if not url:
            return None
        session = self.get_session()
        headers = {'User-Agent': _DEFAULT_UA, 'Referer': self.base_url}
        if session and session.cookies:
            try:
                cookie_list = [f"{c.name}={c.value}" for c in session.cookies]
                headers['Cookie'] = "; ".join(cookie_list)
            except Exception:
                pass
        params = []
        for k, v in headers.items():
            params.append(f"{k}={urllib.parse.quote(str(v))}")
        return f"{url}|{'&'.join(params)}"

    def _resolve_single_thumb(self, url):
        """
        Resolves redirect links (img.pvvstream).
        PRIORITY 1: Extract embedded URL via regex (Avoids network call & blocks).
        PRIORITY 2: Follow redirect via HTTP (Fallback).
        """
        if not url or "img.pvvstream" not in url:
            return url
        
        # Attempt 1: Aggressive Extraction (Fastest & Safest against 403)
        # Structure: .../240/domain.com/path...
        try:
            # Match /240/ or other resolutions, then capture the rest
            match = re.search(r'/(?:240|320|480|720|1080)/(?:https?://)?([a-zA-Z0-9.-]+\.[a-z]{2,}/.+)$', url)
            if match:
                extracted = match.group(1)
                # Ensure protocol
                if not extracted.startswith('http'):
                    extracted = 'https://' + extracted
                
                # Clean potentially double-encoded entities just in case
                extracted = html.unescape(extracted)
                self.logger.info(f"[NM] Extracted embedded thumb: {extracted}")
                return extracted
        except Exception as e:
            self.logger.warning(f"[NM] Extraction error: {e}")

        # Attempt 2: Network Resolve (Fallback)
        try:
            session = self.get_session()
            headers = {
                'User-Agent': _DEFAULT_UA,
                'Referer': self.base_url,
                'Accept': 'image/avif,image/webp,image/png,image/svg+xml,image/*;q=0.8,*/*;q=0.5'
            }
            resp = session.get(url, headers=headers, allow_redirects=True, stream=True, timeout=5)
            if resp.status_code == 200:
                final_url = resp.url
                resp.close()
                if "cdn" in final_url or "preview" in final_url or "secure=" in final_url:
                    return final_url
            resp.close()
        except Exception:
            pass
            
        return url

    def get_page_content(self, url):
        session = self.get_session()
        if not session:
            return None
            
        headers = {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Referer': self.base_url,
        }
        
        html_content = None
        page_num = None
        parsed_url = urllib.parse.urlparse(url)
        query_params = urllib.parse.parse_qs(parsed_url.query)
        base_request_url = urllib.parse.urlunparse((parsed_url.scheme, parsed_url.netloc, parsed_url.path, '', '', ''))
        
        try:
            if 'page' in query_params:
                page_num = query_params['page'][0]
                csrf_token = None
                for cookie in session.cookies:
                    if cookie.name == 'csrftoken':
                        csrf_token = cookie.value
                        break
                if not csrf_token:
                    self.logger.error("No CSRF token found in cookies!")
                    return None
                post_data = {'csrfmiddlewaretoken': csrf_token, 'p': page_num}
                headers.update({
                    'Accept': '*/*', 'X-Requested-With': 'XMLHttpRequest',
                    'Origin': self.base_url, 'Referer': base_request_url
                })
                if 'Upgrade-Insecure-Requests' in headers: del headers['Upgrade-Insecure-Requests']
                self.logger.info(f"Fetching: {base_request_url} (AJAX POST, Page: {page_num})")
                with session.post(base_request_url, headers=headers, data=post_data, timeout=30) as response:
                    response.raise_for_status()
                    html_content = response.text
            elif '/page/' in parsed_url.path:
                page_num_match = re.search(r'/page/(\d+)', parsed_url.path)
                page_num = page_num_match.group(1) if page_num_match else '?'
                headers['Accept'] = '*/*'
                headers['X-Requested-With'] = 'XMLHttpRequest'
                if 'Upgrade-Insecure-Requests' in headers: del headers['Upgrade-Insecure-Requests']
                self.logger.info(f"Fetching: {url} (AJAX GET, Page: {page_num})")
                with session.get(url, headers=headers, timeout=30) as response:
                    response.raise_for_status()
                    html_content = response.text
            else:
                self.logger.info(f"Fetching: {url} (Standard GET)")
                with session.get(url, headers=headers, timeout=30) as response:
                    response.raise_for_status()
                    html_content = response.text
            
            if page_num and (not html_content or html_content.strip() == '[]' or len(html_content) < 500):
                return None
            if len(html_content) > 500:
                return html_content
            return None
        except Exception as e:
            self.logger.error(f"Fetch error: {e}")
            return None
        finally:
            self.save_cookies()

    def process_content(self, url):
        html_content = self.get_page_content(url)
        if not html_content:
            self.end_directory()
            return

        parsed_url = urllib.parse.urlparse(url)
        query_params = urllib.parse.parse_qs(parsed_url.query)
        is_search_page = "/video/" in parsed_url.path
        if not is_search_page:
            self.add_dir('[COLOR blue]Search[/COLOR]', '', 5, self.icons.get('search', self.icon), name_param=self.name)

        items_to_process = []
        
        # --- PARSING PHASE ---
        if html_content.strip().startswith('[') and html_content.strip().endswith(']'):
            try:
                data = json.loads(html_content)
                for item in data:
                    if not isinstance(item, dict): continue
                    video_path = item.get('url')
                    if not video_path: continue
                    
                    title = html.unescape(item.get('title', 'Unknown'))
                    thumb_url = item.get('thumb', '')
                    
                    items_to_process.append({
                        'title': title,
                        'url': urllib.parse.urljoin(self.base_url, video_path),
                        'thumb': thumb_url,
                        'duration': item.get('duration', ''),
                        'views': item.get('views', '')
                    })
            except Exception as e:
                self.logger.error(f"JSON parse error: {e}")

        else:
            item_blocks = re.findall(r'<div class="item">\s*<a href="(/watch/[^"]+)"[^>]*>(.*?)</a>\s*</div>', html_content, re.DOTALL)
            for video_path, item_content in item_blocks:
                try:
                    thumb_url = ""
                    cdn_match = re.search(r'(https?://cdn2?\.pvvstream\.pro/videos/[^"\']+/preview_\d+\.jpg[^"\']*)', item_content)
                    if cdn_match:
                        thumb_url = cdn_match.group(1)
                    else:
                        thumb_match = re.search(r'data-src="([^"]+)"', item_content)
                        if thumb_match:
                            raw = html.unescape(thumb_match.group(1))
                            if not raw.startswith('http'): raw = urllib.parse.urljoin(self.base_url, raw)
                            thumb_url = raw

                    title_match = re.search(r'<div class="title">([^<]+)</div>', item_content)
                    title = html.unescape(title_match.group(1).strip() if title_match else "Unknown")
                    time_match = re.search(r'<div class="m_time">.*?(\d+:\d+(?::\d+)?)', item_content, re.DOTALL)
                    views_match = re.search(r'<div class="m_views">.*?([\d.KM]+)', item_content, re.DOTALL)
                    
                    items_to_process.append({
                        'title': title,
                        'url': urllib.parse.urljoin(self.base_url, video_path),
                        'thumb': thumb_url,
                        'duration': time_match.group(1) if time_match else "",
                        'views': views_match.group(1).strip() if views_match else ""
                    })
                except Exception:
                    continue

        # --- RESOLUTION PHASE ---
        self.logger.info(f"Resolving {len(items_to_process)} thumbs with max_workers=5...")
        
        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_item = {}
            for item in items_to_process:
                t_url = item['thumb']
                # Resolve if it is the proxy domain
                if t_url and "img.pvvstream" in t_url:
                    future = executor.submit(self._resolve_single_thumb, t_url)
                    future_to_item[future] = item
            
            for future in as_completed(future_to_item):
                item = future_to_item[future]
                try:
                    resolved_url = future.result()
                    if resolved_url and resolved_url != item['thumb']:
                        item['thumb'] = resolved_url
                except Exception:
                    pass

        # --- OUTPUT PHASE ---
        for item in items_to_process:
            label = item['title']
            if item['duration']: label += f" [COLOR yellow]{item['duration']}[/COLOR]"
            if item['views']: label += f" [COLOR cyan]{item['views']}[/COLOR]"
            
            thumb = self.icon
            if item['thumb']:
                thumb = self._get_kodi_thumb_url(item['thumb'])
            
            # FIX: Manually adding context menu removed to avoid duplicate "Sort by..."
            # BaseWebsite handles standard sort options automatically.
            
            info_labels = {'title': item['title'], 'plot': f"{item['title']}\n\n{item['duration']} | {item['views']} views"}
            
            self.add_link(label, item['url'], 4, thumb, self.fanart, info_labels=info_labels)

        self.logger.info(f"✓ Output {len(items_to_process)} items")

        # --- PAGINATION ---
        next_page_num_str = None
        next_page_match = re.search(r'class="more"\s+data-page="(\d+)"', html_content)
        if next_page_match:
            next_page_num_str = next_page_match.group(1)
        
        if not next_page_num_str:
             if 'page' in query_params:
                try: next_page_num_str = str(int(query_params['page'][0]) + 1)
                except: pass
             elif '/page/' in parsed_url.path:
                try: next_page_num_str = str(int(re.search(r'/page/(\d+)', parsed_url.path).group(1)) + 1)
                except: pass

        if next_page_num_str:
            base = urllib.parse.urlunparse((parsed_url.scheme, parsed_url.netloc, parsed_url.path, '', '', ''))
            base = re.sub(r'/page/\d+/?', '', base)
            if not base.endswith('/'): base += '/'
            next_url = f"{base.rstrip('/')}?page={next_page_num_str}"
            self.add_dir(f'[COLOR blue]Next (Page {next_page_num_str})[/COLOR]', next_url, 2, self.icons.get('default', self.icon), self.fanart)

        self.end_directory()

    def play_video(self, url):
        session = self.get_session()
        if not session:
            self.notify_error("Session error")
            return
            
        try:
            self.logger.info(f"Loading video: {url}")
            html_content = self.get_page_content(url)
            if not html_content: return

            video_url = self._extract_video_url(html_content, url)
            if not video_url:
                self.notify_error("No video URL found")
                return

            video_url = html.unescape(video_url)
            upstream_headers = {'Referer': url}
            
            proxy_ctrl = ProxyController(upstream_url=video_url, upstream_headers=upstream_headers, session=session)
            local_url = proxy_ctrl.start()

            play_item = xbmcgui.ListItem(path=local_url)
            play_item.setProperty('IsPlayable', 'true')
            play_item.setMimeType('video/mp4')
            play_item.setContentLookup(False)
            xbmcplugin.setResolvedUrl(self.addon_handle, True, listitem=play_item)

            PlaybackGuard(xbmc.Player(), xbmc.Monitor(), local_url, proxy_ctrl).start()

        except Exception as e:
            self.logger.error(f"Playback error: {e}")
            self.notify_error(str(e))

    def _extract_video_url(self, html_content, page_url):
        patterns = [r'https?://cdn(?:-pr)?\.pvvstream\.pro/videos/[^"\'<>\s]+\.mp4\?[^"\'<>\s]*secure=[^"\'<>\s]+']
        for p in patterns:
            matches = re.findall(p, html_content, re.IGNORECASE)
            for match in matches:
                url = match if isinstance(match, str) else match[0]
                if 'preview' not in url.lower() and 'secure=' in url and '.mp4' in url:
                    return url
        return None

    def search(self, query):
        if not query: return
        search_url = self.search_url.format(urllib.parse.quote_plus(query.replace(' ', '+')))
        self.process_content(search_url)
    
    def select_advanced_filter(self, original_url=None):
        dialog = xbmcgui.Dialog()
        time_periods = ['Now', 'Recent', 'Day', 'Week', 'Month']
        time_idx = dialog.select("Select Time Period", time_periods)
        if time_idx == -1: return
        
        selected_period = time_periods[time_idx]
        if selected_period == 'Now':
            new_url = urllib.parse.urljoin(self.base_url, '/now')
            xbmc.executebuiltin(f"Container.Update({sys.argv[0]}?mode=2&url={urllib.parse.quote_plus(new_url)}&website={self.name},replace)")
            return
        
        length_options = ['Any Length', 'Short (≤5 min)', 'Long (≥10 min)']
        length_idx = dialog.select("Select Video Length", length_options)
        if length_idx == -1: return
        
        quality_options = ['All Quality', 'HD Only']
        quality_idx = dialog.select("Select Quality", quality_options)
        if quality_idx == -1: return
        
        sort_options = ['Views (Descending)', 'Views (Ascending)']
        sort_idx = dialog.select("Select Sort Order", sort_options)
        if sort_idx == -1: return
        
        params = ['sort_by=views']
        params.append('sort_order=desc' if sort_idx == 0 else 'sort_order=asc')
        if length_idx == 1: params.append('length_max=5')
        elif length_idx == 2: params.append('length_min=10')
        if quality_idx == 1: params.append('hd=1')
        
        new_url = f"{self.base_url}/popular/{selected_period.lower()}?{'&'.join(params)}"
        filter_name = f"{selected_period}"
        if length_idx == 1: filter_name += " (Short)"
        elif length_idx == 2: filter_name += " (Long)"
        if quality_idx == 1: filter_name += " HD"
        if sort_idx == 1: filter_name += " (Asc)"
        
        self.addon.setSetting(f"{self.name}_last_filter", filter_name)
        xbmc.executebuiltin(f"Container.Update({sys.argv[0]}?mode=2&url={urllib.parse.quote_plus(new_url)}&website={self.name},replace)")