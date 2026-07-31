import re
import sys
import os
import html
import urllib.parse
from resources.lib.base_website import BaseWebsite

import xbmcaddon

try:
    addon_path = xbmcaddon.Addon().getAddonInfo('path')
    vendor_path = os.path.join(addon_path, 'resources', 'lib', 'vendor')
    if vendor_path not in sys.path:
        sys.path.insert(0, vendor_path)
except Exception:
    pass

import cloudscraper
from resources.lib.resilient_http import fetch_text


class Fuqer(BaseWebsite):
    NAME = "fuqer"
    BASE_URL = "https://www.fuqer.com/"
    SEARCH_URL = "https://www.fuqer.com/search/videos/{}/page1.html"
    UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

    def __init__(self, addon_handle, name=None, base_url=None, search_url=None, addon=None):
        BaseWebsite.__init__(self, name or self.NAME, base_url or self.BASE_URL, search_url or self.SEARCH_URL, addon_handle, addon)
        self.scraper = cloudscraper.create_scraper(browser={'custom': self.UA})

    def get_headers(self, url):
        return {
            "User-Agent": self.UA,
            "Referer": "https://www.fuqer.com/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }

    def get_html(self, url):
        headers = self.get_headers(url)
        try:
            html_text = fetch_text(
                url,
                headers=headers,
                scraper=self.scraper,
                logger=None,
                timeout=30,
            )
            if html_text:
                return html_text
        except Exception as e:
            import xbmc
            xbmc.log(f"[Fuqer] Error fetching {url}: {e}", xbmc.LOGERROR)
        return None

    def process_content(self, url):
        import xbmc
        xbmc.log(f"[Fuqer][ProcessContent] URL: {url}", xbmc.LOGINFO)
        
        is_category_index = "/channels" in url and not re.search(r'/channels/\d+/', url)
        
        if is_category_index:
            self.list_categories(url)
            return
        
        self.add_dir("[COLOR yellow]Search[/COLOR]", "search", 5, self.icons.get('search', self.icon), self.fanart)
        self.add_dir("[COLOR yellow]Categories[/COLOR]", "https://www.fuqer.com/channels/", 2, self.icons.get('categories', self.icon), self.fanart)
        
        items, next_url = self._get_listing_with_pagination(url)
        
        for title, video_url, thumbnail in items:
            self.add_link(title, video_url, 4, thumbnail, self.fanart)
        
        if next_url:
            self.add_dir("[COLOR blue]Next Page >>[/COLOR]", next_url, 2, self.icons.get('next', self.icon), self.fanart)
        
        self.end_directory()

    def list_categories(self, url):
        import xbmc
        xbmc.log(f"[Fuqer][Categories] Fetching: {url}", xbmc.LOGINFO)
        
        html_text = self.get_html(url)
        if not html_text:
            self.end_directory()
            return
        
        count = 0
        blocks = html_text.split('class="item"')
        for block in blocks[1:]:
            link_match = re.search(
                r'href="((?:https://www\.fuqer\.com)?/channels/[^"]+)"[^>]*>',
                block,
            )
            if not link_match:
                continue
            
            cat_url = urllib.parse.urljoin(self.BASE_URL, link_match.group(1))
            
            title_match = re.search(r'<p class="title">([^<]+)</p>', block)
            if not title_match:
                title_match = re.search(r'title="([^"]+)"', block)
            
            title = title_match.group(1).strip() if title_match else cat_url.split('/')[-2].replace('-', ' ').title()
            
            thumb_match = re.search(r'data-src="([^"]+)"', block)
            thumbnail = thumb_match.group(1) if thumb_match else ""
            
            if thumbnail and '|' not in thumbnail:
                thumbnail += f"|User-Agent={urllib.parse.quote(self.UA)}&Referer={urllib.parse.quote(self.BASE_URL)}"

            self.add_dir(title, cat_url, 2, thumbnail)
            count += 1
        
        xbmc.log(f"[Fuqer][Categories] Added {count} categories", xbmc.LOGINFO)
        self.end_directory()

    def _get_listing_with_pagination(self, url):
        import xbmc
        xbmc.log(f"[Fuqer][Listing] Fetching listing for: {url}", xbmc.LOGINFO)
        html_text = self.get_html(url)
        if not html_text:
            xbmc.log(f"[Fuqer][Listing] Failed to get HTML for: {url}", xbmc.LOGERROR)
            return [], None

        items = []
        next_url = None
        seen = set()

        matches = re.findall(
            r'<a\s+[^>]*href=["\'](https://www\.fuqer\.com/videos/[^"\']+)["\'][^>]*>([\s\S]*?)</a>',
            html_text
        )
        for href, inner in matches:
            if href in seen:
                continue
            seen.add(href)
            title_m = re.search(r'title=["\']([^"\']+)["\']', inner) or re.search(r'alt=["\']([^"\']+)["\']', inner)
            thumb_m = re.search(r'data-src=["\']([^"\']+)["\']', inner) or re.search(r'src=["\']([^"\']+)["\']', inner)
            if not title_m or not thumb_m:
                continue
            title = html.unescape(title_m.group(1).strip())
            thumbnail = thumb_m.group(1).strip()
            if thumbnail.startswith('//'):
                thumbnail = 'https:' + thumbnail
            if thumbnail and '|' not in thumbnail:
                thumbnail += f"|User-Agent={urllib.parse.quote(self.UA)}&Referer={urllib.parse.quote(self.BASE_URL)}"
            items.append((title, href, thumbnail))

        xbmc.log(f"[Fuqer][Listing] Parsed {len(items)} items", xbmc.LOGINFO)

        next_match = re.search(r'<a[^>]+href=["\']([^"\'#]+)["\'][^>]*>\s*Next', html_text, re.IGNORECASE)
        if next_match:
            n_url = next_match.group(1)
            next_url = urllib.parse.urljoin(url, n_url)
            xbmc.log(f"[Fuqer][Pagination] Raw: {n_url}, Resolved: {next_url}", xbmc.LOGINFO)

        return items, next_url

    def get_listing(self, url):
        items, _ = self._get_listing_with_pagination(url)
        return items

    def search(self, query):
        search_url = f"https://www.fuqer.com/search/videos/{urllib.parse.quote_plus(query)}/page1.html"
        self.process_content(search_url)

    def resolve(self, url):
        import xbmc
        from resources.lib.proxy_utils import ProxyController, PlaybackGuard
        
        xbmc.log(f"[Fuqer][Resolve] Starting resolution for: {url}", xbmc.LOGINFO)
        
        try:
            html_text = self.get_html(url)
            if not html_text:
                xbmc.log("[Fuqer][Resolve] Failed to get video page HTML", xbmc.LOGERROR)
                return None
            
            match = re.search(r'var defaultRaw\s*=\s*"([^"]+)"', html_text)
            if not match:
                xbmc.log("[Fuqer][Resolve] defaultRaw not found in HTML", xbmc.LOGERROR)
                return None
                
            video_url = match.group(1).replace(r'\/', '/')
            xbmc.log(f"[Fuqer][Resolve] Found defaultRaw: {video_url}", xbmc.LOGINFO)
            
            try:
                r = self.scraper.request("GET", "https://www.fuqer.com/secure_link.php", 
                                   params={"mode": "redirect", "path": video_url},
                                   headers=self.get_headers(url), 
                                   allow_redirects=False, timeout=10)
            except Exception:
                xbmc.log("[Fuqer][Resolve] Fast path failed, falling back to scraper", xbmc.LOGWARNING)
                r = self.scraper.get("https://www.fuqer.com/secure_link.php", 
                                   params={"mode": "redirect", "path": video_url},
                                   headers=self.get_headers(url), 
                                   allow_redirects=False, timeout=60)
            
            if r.status_code in [301, 302] and 'Location' in r.headers:
                stream_url = r.headers['Location']
                xbmc.log(f"[Fuqer][Resolve] Signed URL: {stream_url}", xbmc.LOGINFO)
                
                monitor = xbmc.Monitor() 
                player = xbmc.Player()
                
                ctrl = ProxyController(
                    stream_url,
                    upstream_headers=self.get_headers(url),
                    session=self.scraper
                )
                
                proxy_url = ctrl.start()
                if not proxy_url:
                    raise Exception("Proxy failed to start")
                    
                guard = PlaybackGuard(player, monitor, proxy_url, ctrl)
                guard.start()
                
                return proxy_url
                
            else:
                xbmc.log(f"[Fuqer][Resolve] Signing failed. Status: {r.status_code}", xbmc.LOGERROR)
                return f"{video_url}|User-Agent={urllib.parse.quote(self.UA)}&Referer={urllib.parse.quote(url)}"

        except Exception as e:
            xbmc.log(f"[Fuqer][Resolve] Error: {e}", xbmc.LOGERROR)
            return None

    def parse_duration(self, duration_str):
        try:
            parts = list(map(int, duration_str.split(':')))
            if len(parts) == 2:
                return parts[0] * 60 + parts[1]
            elif len(parts) == 3:
                return parts[0] * 3600 + parts[1] * 60 + parts[2]
        except:
            return 0
        return 0

    def play_video(self, url):
        import xbmc
        import xbmcgui
        import xbmcplugin
        
        xbmc.log(f"[Fuqer] Playing video: {url}", xbmc.LOGINFO)
        video_url = self.resolve(url)
        
        if video_url:
            xbmc.log(f"[Fuqer] Resolved to: {video_url}", xbmc.LOGINFO)
            li = xbmcgui.ListItem(path=video_url)
            li.setProperty('IsPlayable', 'true')
            li.setMimeType('video/mp4')
            li.setContentLookup(False)
            xbmcplugin.setResolvedUrl(self.addon_handle, True, li)
        else:
            xbmc.log("[Fuqer] Resolution failed", xbmc.LOGERROR)
            self.notify_error("Could not resolve video")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
