# -*- coding: utf-8 -*-
# [CHANGELOG]
# - FIXED: Path injection logic (Up 1 level to 'resources', then into 'lib/vendor') to fix ImportError
# - FIXED: Categories menu item is now added on every page listing
# - RESTORED: Robust parsing and playback logic from original version
# - CLEANUP: Removed comments and dead code

import sys
import os

# 1. Force Path Injection (Corrected relative path)
try:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # Current: resources/websites/
    # Target:  resources/lib/vendor/
    # Move up 1 level: resources/
    vendor_path = os.path.abspath(os.path.join(current_dir, '..', 'lib', 'vendor'))
    
    if os.path.exists(vendor_path) and vendor_path not in sys.path:
        sys.path.insert(0, vendor_path)
except Exception:
    pass

import re
import html
import urllib.parse
import time
import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon

# Safe import after path injection
import requests

try:
    import cloudscraper
    _HAS_CF = True
except ImportError:
    xbmc.log("[freeomovie] cloudscraper not found, fallback to requests", xbmc.LOGWARNING)
    _HAS_CF = False

from resources.lib.base_website import BaseWebsite
from resources.lib.resolvers import resolver

class freeomovie(BaseWebsite):
    def __init__(self, addon_handle):
        addon = xbmcaddon.Addon()
        name = "freeomovie"
        base_url = "https://www.freeomovie.to/"
        search_url = "https://www.freeomovie.to/?s={}"
        super(freeomovie, self).__init__(name, base_url, search_url, addon_handle, addon=addon)

        self._headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": self.base_url,
        }

    def _http_get(self, url, headers=None, timeout=20):
        headers = headers or self._headers
        
        if _HAS_CF:
            try:
                scraper = cloudscraper.create_scraper(
                    browser={"browser": "chrome", "platform": "windows", "mobile": False}
                )
                response = scraper.get(url, headers=headers, timeout=timeout)
                if response.status_code == 200:
                    return response.text
                xbmc.log(f"[freeomovie] Cloudscraper Status: {response.status_code}", xbmc.LOGWARNING)
            except Exception as e:
                xbmc.log(f"[freeomovie] Cloudscraper Failed: {e}", xbmc.LOGWARNING)
        
        try:
            response = requests.get(url, headers=headers, timeout=timeout, verify=False)
            if response.status_code == 200:
                return response.text
            xbmc.log(f"[freeomovie] Requests Status: {response.status_code}", xbmc.LOGWARNING)
        except Exception as e:
             xbmc.log(f"[freeomovie] Requests Failed: {e}", xbmc.LOGWARNING)

        return ""

    def process_content(self, url):
        # Static items on every page
        self.add_dir('[COLOR blue]Search...[/COLOR]', '', 5, self.icons.get('search', ''))
        self.add_dir('[COLOR blue]Categories[/COLOR]', self.base_url, 8, self.icons.get('categories', ''))

        target_url = url if url and url != "BOOTSTRAP" else self.base_url
        
        html_text = self._http_get(target_url)
        
        if not html_text:
            self.notify_error("Seite konnte nicht geladen werden.")
            xbmcplugin.endOfDirectory(self.addon_handle)
            return

        items = self._parse_listing(html_text)
        
        if not items:
            self.notify_info("Keine Videos gefunden.")
        else:
            for item in items:
                title = html.unescape(item.get("title", "Video")).strip()
                thumb = self._normalize_thumb(item.get("thumb", ""))
                link = item.get("url", "")
                
                if not link.startswith("http"):
                     link = urllib.parse.urljoin(self.base_url, link)

                info_labels = {"title": title}
                self.add_link(title, link, 4, thumb, self.fanart, info_labels=info_labels)

        next_url = self._find_next_page(html_text, target_url)
        if next_url:
            self.add_dir("[COLOR skyblue]Next Page >>[/COLOR]", next_url, 2, self.icons.get('default', ''))

        self.end_directory()

    def process_categories(self, url):
        html_text = self._http_get(url)
        if not html_text:
            self.notify_error("Kategorien konnten nicht geladen werden.")
            self.end_directory()
            return

        cat_pattern = re.compile(r'<li[^>]*class="cat-item[^"]*"[^>]*><a[^>]+href="([^"]+)"[^>]*>([^<]+)</a>', re.IGNORECASE)
        matches = cat_pattern.findall(html_text)

        if not matches:
            cat_pattern = re.compile(r'<a[^>]+href="(https?://[^"]+/category/[^"]+)"[^>]*>([^<]+)</a>', re.IGNORECASE)
            matches = cat_pattern.findall(html_text)

        seen = set()
        for link, title in matches:
            if link not in seen:
                seen.add(link)
                self.add_dir(title, link, 2, self.icons.get('categories', ''))

        self.end_directory()

    def _parse_listing(self, html_text):
        items = []
        
        if 'id="main"' in html_text:
            parts = html_text.split('id="main"')
            main_content = parts[-1]
        elif '<article' in html_text:
             main_content = html_text[html_text.find('<article'):]
        else:
             main_content = html_text

        blocks = re.split(r'<li[^>]+id="post-', main_content)
        
        for block in blocks[1:]:
            url_match = re.search(r'<a\s+href="([^"]+)"', block)
            if not url_match: continue
            url = url_match.group(1)
            
            img_match = re.search(r'<img[^>]+data-src="([^"]+)"', block)
            if not img_match:
                img_match = re.search(r'<img[^>]+src="([^"]+)"', block)
            thumb = img_match.group(1) if img_match else ""
            
            title = ""
            title_match = re.search(r'<a[^>]+title="([^"]+)"', block)
            if title_match:
                title = title_match.group(1)
            else:
                alt_match = re.search(r'<img[^>]+alt="([^"]+)"', block)
                if alt_match: title = alt_match.group(1)
            
            if not title:
                h2_match = re.search(r'<h2>(.*?)</h2>', block)
                if h2_match: title = h2_match.group(1)
                
            if title:
                title = re.sub(r'<[^>]+>', '', title)

            if url and "freeomovie" in url and not "login" in url:
                items.append({"title": title, "url": url, "thumb": thumb})
            
        return items

    def play_video(self, url):
        start_time = time.time()
        html_text = self._http_get(url)
        if not html_text:
            self.notify_error("Detailseite konnte nicht geladen werden.")
            return

        iframe_urls = self._extract_iframes(html_text)
        
        if not iframe_urls:
            self.notify_error("Keine Hoster-Links gefunden.")
            return

        def sort_hosters(link):
            link = link.lower()
            if 'voe.sx' in link or 'voe.sa' in link: return 4
            if 'lulustream' in link: return 3 
            if 'bigwarp' in link: return 3
            if 'mixdrop' in link: return 2
            if 'dood' in link: return 1 
            return 0
            
        iframe_urls.sort(key=sort_hosters, reverse=True)

        try:
            autoplay = self.addon.getSetting('freeomovie_autoplay_hoster') == 'true'
        except: autoplay = True 

        stream_url = None
        headers = {}
        resolved_host = ""

        if autoplay:
             xbmcgui.Dialog().notification("Autoplay", f"Prüfe {len(iframe_urls)} Hoster...", xbmcgui.NOTIFICATION_INFO, 2000)
             
             for link in iframe_urls:
                 try:
                     host_name = urllib.parse.urlparse(link).netloc
                     xbmc.log(f"[freeomovie] Testing host: {host_name}", xbmc.LOGINFO)
                     
                     stream_url, headers = resolver.resolve(link, headers=self._headers)
                     
                     if stream_url and stream_url.startswith("http"):
                         if self._check_stream_valid(stream_url, headers):
                             resolved_host = host_name
                             xbmc.log(f"[freeomovie] Success with {host_name}", xbmc.LOGINFO)
                             break
                         else:
                             xbmc.log(f"[freeomovie] Host {host_name} resolved but stream unreachable.", xbmc.LOGWARNING)
                 except Exception as e:
                     xbmc.log(f"[freeomovie] Resolve failed for {link}: {e}", xbmc.LOGWARNING)
                     continue 
        
        else:
            labels = []
            for u in iframe_urls:
                host = urllib.parse.urlparse(u).netloc.replace('www.', '')
                labels.append(host)
            
            idx = xbmcgui.Dialog().select("Wähle Hoster", labels)
            if idx > -1:
                 try:
                     resolved_host = labels[idx]
                     stream_url, headers = resolver.resolve(iframe_urls[idx], headers=self._headers)
                 except Exception as e:
                     self.notify_error(f"Fehler: {e}")
                     return
            else:
                return

        if stream_url:
            duration = round(time.time() - start_time, 2)
            xbmc.log(f"[freeomovie] Resolved {resolved_host} in {duration}s", xbmc.LOGINFO)
            
            li = xbmcgui.ListItem(path=self._append_headers(stream_url, headers))
            li.setProperty('IsPlayable', 'true')
            xbmcplugin.setResolvedUrl(self.addon_handle, True, li)
        else:
            self.notify_error("Kein funktionierender Stream gefunden.")

    def _check_stream_valid(self, url, headers):
        try:
            r = requests.head(url, headers=headers, timeout=3, verify=False)
            return r.status_code in [200, 302, 301, 206]
        except:
            return False

    def _extract_iframes(self, html_text):
        links = []
        links.extend(re.findall(r'<iframe[^>]+src="([^"]+)"', html_text, re.IGNORECASE))
        links.extend(re.findall(r'data-src="([^"]+)"', html_text, re.IGNORECASE))
        links.extend(re.findall(r'class="url-a-btn"[^>]+href="([^"]+)"', html_text, re.IGNORECASE))
        
        clean_links = []
        for l in links:
            if l.startswith("//"): l = "https:" + l
            if "facebook" in l or "twitter" in l: continue
            if any(ext in l.lower() for ext in ['.jpg', '.png', '.gif', 'favicon']): continue
            if l not in clean_links:
                clean_links.append(l)
        return clean_links

    def _normalize_thumb(self, thumb):
        if not thumb: return self.icon
        if thumb.startswith("//"): return "https:" + thumb
        if thumb.startswith("/"): return urllib.parse.urljoin(self.base_url, thumb)
        return thumb

    def _find_next_page(self, html_text, current_url):
        match = re.search(r"<a[^>]+href=['\"]([^'\"]+)['\"][^>]*class=['\"][^'\"]*next", html_text, re.IGNORECASE)
        if match: return match.group(1)
        return None

    def _append_headers(self, url, headers):
        if not headers: return url
        parts = [f"{k}={urllib.parse.quote(v)}" for k, v in headers.items()]
        return url + "|" + "&".join(parts)

    def notify_error(self, msg):
        xbmcgui.Dialog().notification('FreeOMovie', msg, xbmcgui.NOTIFICATION_ERROR)
    
    def notify_info(self, msg):
        xbmcgui.Dialog().notification('FreeOMovie', msg, xbmcgui.NOTIFICATION_INFO)