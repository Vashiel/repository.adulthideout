#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
import urllib.parse
import html
import os
import xbmc
import xbmcgui
import xbmcplugin
import sys
from resources.lib.base_website import BaseWebsite

class Javsubbed(BaseWebsite):
    
    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="javsubbed",
            base_url="https://javsubbed.net",
            search_url="https://javsubbed.net/?s={}",
            addon_handle=addon_handle,
            addon=addon
        )
        self.sort_options = ["Latest", "Most Viewed", "Popular"]
        self.sort_paths = {
            "Latest": "/?filter=latest",
            "Most Viewed": "/?filter=most-viewed",
            "Popular": "/?filter=popular"
        }
        self.ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        self.icon = os.path.join(self.addon.getAddonInfo('path'), 'resources', 'logos', 'javsubbed.png')
        self.icons['default'] = self.icon
        
        try:
            import requests
            self.session = requests.Session()
        except ImportError:
            self.session = None

    def make_request(self, url):
        self.logger.info(f"[javsubbed] Requesting: {url}")
        headers = {
            "User-Agent": self.ua,
            "Referer": self.base_url
        }
        
        if self.session:
            try:
                response = self.session.get(url, headers=headers, timeout=20)
                response.raise_for_status()
                response.encoding = response.encoding or "utf-8"
                return response.text.replace("\x00", "")
            except Exception as exc:
                self.logger.error("[javsubbed] requests request failed: %s", exc)
        
        # Fallback to urllib.request
        try:
            import urllib.request
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=20) as response:
                html_bytes = response.read()
                return html_bytes.decode('utf-8', errors='ignore').replace("\x00", "")
        except Exception as exc:
            self.logger.error("[javsubbed] urllib request failed: %s", exc)
        return ""

    def get_page_url(self, base_url, page_num):
        parsed = urllib.parse.urlparse(base_url)
        path = parsed.path
        path = re.sub(r'page/\d+/?', '', path)
        if not path.endswith('/'):
            path += '/'
        path += f"page/{page_num}/"
        return urllib.parse.urlunparse((
            parsed.scheme,
            parsed.netloc,
            path,
            parsed.params,
            parsed.query,
            parsed.fragment
        ))

    def process_content(self, url, page=1):
        # Bootstrap handling
        if url == "BOOTSTRAP" or url == self.base_url or url == f"{self.base_url}/":
            self.add_dir("Search", "", 5, self.icons['search'], name_param=self.name)
            self.add_dir("English Subbed", "https://javsubbed.net/category/english-subbed/", 2, self.icons['categories'])
            self.add_dir("Censored", "https://javsubbed.net/category/censored/", 2, self.icons['categories'])
            self.add_dir("Uncensored", "https://javsubbed.net/category/uncensored/", 2, self.icons['categories'])
            self.add_dir("Actresses", "https://javsubbed.net/actors/", 9, self.icons['pornstars'])
            self.add_dir("Studios", "https://javsubbed.net/studios/", 8, self.icons['categories'])
            self.add_dir("Tags", "https://javsubbed.net/tags/", 11, self.icons['categories'])
            
            # Show homepage updates
            start_url, _ = self.get_start_url_and_label()
            self.get_listing(start_url, page)
            return

        self.get_listing(url, page)

    def get_listing(self, url, page):
        target_url = url
        if page > 1:
            target_url = self.get_page_url(url, page)
            
        html_content = self.make_request(target_url)
        if not html_content:
            return self.end_directory()

        # Parse loop video articles
        articles = re.findall(r'<article[^>]*class="[^"]*post[^"]*"[^>]*>(.*?)</article>', html_content, re.DOTALL)
        
        items_added = 0
        for art in articles:
            href_match = re.search(r'href=["\']([^"\']+)["\']', art)
            title_match = re.search(r'title=["\']([^"\']+)["\']', art)
            
            if not href_match or not title_match:
                continue
                
            video_url = href_match.group(1)
            title = html.unescape(title_match.group(1).strip())
            
            img_match = re.search(r'data-src=["\']([^"\']+)["\']', art)
            if not img_match:
                img_match = re.search(r'src=["\']([^"\']+)["\']', art)
                
            thumb = img_match.group(1) if img_match else self.icons['default']
            if thumb.startswith("data:"):
                img_match_retry = re.search(r'data-src=["\']([^"\']+)["\']', art)
                if img_match_retry:
                    thumb = img_match_retry.group(1)
                else:
                    srcset_match = re.search(r'data-srcset=["\']([^"\s]+)', art)
                    if srcset_match:
                        thumb = srcset_match.group(1)
                    else:
                        thumb = self.icons['default']
            
            # If it is a remote image URL, append headers to bypass hotlink protection (403 Forbidden)
            if thumb.startswith("http"):
                headers_str = 'User-Agent={}&Referer={}'.format(
                    urllib.parse.quote(self.ua),
                    urllib.parse.quote('https://javsubbed.net/')
                )
                thumb = thumb + '|' + headers_str
            
            self.add_link(title, video_url, 4, thumb, self.fanart)
            items_added += 1

        if items_added > 0:
            next_page = page + 1
            # Add dynamic Next Page item
            self.add_dir(f"[COLOR blue]Next Page ({next_page}) >>[/COLOR]", url, 2, self.icons['default'], page=next_page)
            
        self.end_directory()

    def process_categories(self, url):
        # Handle Studios list (mode 8)
        html_content = self.make_request(url)
        if not html_content:
            return self.end_directory()
            
        matches = re.findall(r'<a[^>]+href="(https://javsubbed.net/category/([^/]+)/)"[^>]*>(.*?)</a>', html_content)
        seen = set()
        for link, slug, name_raw in matches:
            if slug in ['english-subbed', 'censored', 'uncensored', 'hardsub']:
                continue
            if link not in seen:
                seen.add(link)
                name = html.unescape(re.sub(r'<[^>]*>', '', name_raw).strip())
                self.add_dir(name, link, 2, self.icons['categories'])
                
        self.end_directory()

    def process_pornstars(self, url):
        # Handle Actresses list (mode 9)
        html_content = self.make_request(url)
        if not html_content:
            return self.end_directory()
            
        matches = re.findall(r'<a[^>]+href="(https://javsubbed.net/actor/([^/]+)/)"[^>]*>(.*?)</a>', html_content)
        seen = set()
        for link, slug, name_raw in matches:
            if link not in seen:
                seen.add(link)
                name = html.unescape(re.sub(r'<[^>]*>', '', name_raw).strip())
                self.add_dir(name, link, 2, self.icons['pornstars'])
                
        self.end_directory()

    def process_collections(self, url):
        # Handle Tags list (mode 11)
        html_content = self.make_request(url)
        if not html_content:
            return self.end_directory()
            
        matches = re.findall(r'<a[^>]+href="(https://javsubbed.net/tag/([^/]+)/)"[^>]*>(.*?)</a>', html_content)
        seen = set()
        for link, slug, name_raw in matches:
            if link not in seen:
                seen.add(link)
                name = html.unescape(re.sub(r'<[^>]*>', '', name_raw).strip())
                self.add_dir(name, link, 2, self.icons['categories'])
                
        self.end_directory()

    def play_video(self, url):
        self.logger.info(f"[javsubbed] play_video: {url}")
        resolved = self.resolve_recording_stream(url)
        if not resolved or not resolved.get("url"):
            self.logger.error("[javsubbed] No playable direct stream links found")
            self.notify_error("No playable streams found.")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return

        resolved_url = resolved["url"]
        headers = resolved.get("headers") or {}
        
        self.logger.info(f"[javsubbed] Playing resolved stream: {resolved_url}")
        liz = xbmcgui.ListItem(path=resolved_url)
        liz.setProperty('IsPlayable', 'true')
        liz.setContentLookup(False)
        
        # Pass headers to Kodi
        if headers:
            header_str = urllib.parse.urlencode(headers)
            liz.setPath(resolved_url + "|" + header_str)
            
        if ".m3u8" in resolved_url:
            liz.setMimeType('application/vnd.apple.mpegurl')
            liz.setProperty('inputstream', 'inputstream.adaptive')
            liz.setProperty('inputstream.adaptive.manifest_type', 'hls')
        else:
            liz.setMimeType('video/mp4')
            
        xbmcplugin.setResolvedUrl(self.addon_handle, True, listitem=liz)

    def resolve_recording_stream(self, url):
        html_content = self.make_request(url)
        if not html_content:
            return None
            
        links_raw = re.findall(r'<a[^>]+class=["\']myLink["\'][^>]*>', html_content)
        server_links = []
        for l in links_raw:
            href_m = re.search(r'href=["\']([^"\']+)["\']', l)
            name_m = re.search(r'name=["\']([^"\']+)["\']', l)
            if href_m:
                href = href_m.group(1)
                name = name_m.group(1) if name_m else "Unknown"
                server_links.append((name, href))
                
        # Sort so we try voe and streamtape first
        priority = ['voe.sx', 'streamtape.com']
        server_links.sort(key=lambda x: 0 if any(p in x[1] or p in x[0].lower() for p in priority) else 1)
        
        from resources.lib.resolvers.resolver import resolve
        for name, href in server_links:
            self.logger.info(f"[javsubbed] Attempting to resolve stream: {name} ({href})")
            try:
                res_url, headers = resolve(href, referer=url)
                if res_url and not res_url.startswith("http://localhost") and not "ERROR" in res_url:
                    parts = res_url.split('|')
                    direct_url = parts[0]
                    url_headers = headers or {}
                    if len(parts) > 1:
                        extra_headers = dict(urllib.parse.parse_qsl(parts[1]))
                        url_headers.update(extra_headers)
                    ext = "m3u8" if ".m3u8" in direct_url else "mp4"
                    return {"url": direct_url, "headers": url_headers, "extension": ext}
            except Exception as e:
                self.logger.warning(f"[javsubbed] Failed to resolve stream {name}: {e}")
        return None
