import sys
import os
import re
import urllib.parse
import urllib.request
import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon

try:
    import json
except ImportError:
    import simplejson as json

from resources.lib.base_website import BaseWebsite
from resources.lib.decoders.kvs_decoder import kvs_decode_url

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

class HeavyFetish(BaseWebsite):
    NAME = 'heavyfetish'
    BASE_URL = "https://heavyfetish.com/"
    SEARCH_URL = "https://heavyfetish.com/search/{}/"
    
    RE_VIDEO = re.compile(r'<a[^>]+href="(https://heavyfetish\.com/videos/\d+/[^"]+)"[^>]+title="([^"]+)"')
    RE_THUMB = re.compile(r'https://heavyfetish\.com/contents/videos_screenshots/\d+/\d+/\d+x\d+/\d+\.jpg')
    RE_DURATION = re.compile(r'<div class="duration">([^<]+)</div>')
    RE_NEXT_PAGE = re.compile(r'<li class="next">\s*<a href="([^"]+)"', re.IGNORECASE)
    RE_CAT = re.compile(r'<a class="item"\s+href="(https://heavyfetish\.com/categories/[^"]+/)"\s+title="([^"]+)"[^>]*>.*?<img[^>]+src="([^"]+)"', re.DOTALL)
    
    def __init__(self, addon_handle, addon=None):
        super().__init__(self.NAME, self.BASE_URL, self.SEARCH_URL, addon_handle, addon=addon)
        print(f"DEBUG: Initialized. Cloudscraper enabled: {_HAS_CF}")

    def get_headers(self):
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Referer": self.BASE_URL,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5"
        }

    def make_request(self, url):
        print(f"DEBUG: make_request url={url}")
        try:
            headers = self.get_headers()
            if _HAS_CF:
                scraper = cloudscraper.create_scraper(browser={'custom': headers['User-Agent']})
                r = scraper.get(url, headers=headers, timeout=20)
                print(f"DEBUG: CS status {r.status_code}")
                return r.text
            else:
                print("DEBUG: Using urllib")
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=15) as response:
                    return response.read().decode('utf-8')
        except Exception as e:
            print(f"DEBUG: Request error for {url}: {e}")
            return None

    def process_content(self, url):
        self.add_dir("Search", "SEARCH", 5, self.icons['search'])
        self.add_dir("Categories", self.BASE_URL + "categories/", 2, self.icons['categories'])
        
        if not url or url == "BOOTSTRAP":
            url = self.BASE_URL
        
        if "/categories/" in url and url.rstrip('/').endswith("/categories"):
            self.list_categories(url)
            return

        html = self.make_request(url)
        if not html:
            self.end_directory()
            return
        
        print(f"DEBUG: process_content HTML len: {len(html)}")
        print(f"DEBUG: Content Sample: {html[:200]}")
        matches = list(self.RE_VIDEO.finditer(html))
        print(f"DEBUG: Found {len(matches)} video matches")

        seen_urls = set()
        for video_match in matches:
            video_url = video_match.group(1)
            title = video_match.group(2).strip()
            
            if video_url in seen_urls:
                continue
            seen_urls.add(video_url)
            
            start = max(0, video_match.start() - 500)
            end = min(len(html), video_match.end() + 500)
            context = html[start:end]
            
            thumb = ""
            thumb_match = self.RE_THUMB.search(context)
            if thumb_match:
                thumb = thumb_match.group(0)
            
            dur_match = self.RE_DURATION.search(context)
            if dur_match:
                duration = dur_match.group(1).strip()
                title = f"[COLOR blue]{duration}[/COLOR] {title}"
            
            final_thumb = thumb if thumb else self.icons['default']
            self.add_link(title, video_url, 4, final_thumb, final_thumb)
        
        next_match = self.RE_NEXT_PAGE.search(html)
        if next_match:
            next_url = next_match.group(1)
            if not next_url.startswith('http'):
                next_url = urllib.parse.urljoin(self.BASE_URL, next_url)
            self.add_dir("[COLOR green]Next Page >>[/COLOR]", next_url, 2, self.icons['default'])
        
        self.end_directory()

    def resolve(self, url):
        html = self.make_request(url)
        if not html:
            return None
        
        video_url_match = re.search(r"video_url\s*:\s*['\\\"]([^'\\\"]+)['\\\"]", html)
        if not video_url_match:
            return None
        
        video_url = video_url_match.group(1)
        
        license_match = re.search(r"license_code\s*:\s*['\\\"]([^'\\\"]+)['\\\"]", html)
        if license_match:
            license_code = license_match.group(1)
            video_url = kvs_decode_url(video_url, license_code)
        elif video_url.startswith("function/0/"):
            video_url = video_url[len("function/0/"):]
        
        return video_url.rstrip('/')

    def play_video(self, url):
        xbmc.log(f"HeavyFetish: Playing video {url}", xbmc.LOGINFO)
        headers = self.get_headers()
        
        try:
            if _HAS_CF:
                scraper = cloudscraper.create_scraper(browser={'custom': headers['User-Agent']})
                r = scraper.get(url, headers=headers, timeout=20)
                html = r.text
            else:
                self.notify_error("Cloudscraper required for HeavyFetish")
                xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
                return
            
            if not html:
                self.notify_error("Failed to load video page")
                xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
                return
            
            video_url = None
            video_url_match = re.search(r'video_url\s*:\s*[\'"]([^\'"]+)[\'"]', html)
            if video_url_match:
                video_url = video_url_match.group(1)
                xbmc.log(f"HeavyFetish: Extracted video URL: {video_url}", xbmc.LOGINFO)
                
                if not video_url.startswith('http'):
                    license_match = re.search(r'license_code\s*:\s*[\'"]([^\'"]+)[\'"]', html)
                    if license_match:
                        video_url = kvs_decode_url(video_url, license_match.group(1))
            
            if not video_url or not video_url.startswith('http'):
                source_match = re.search(r'<source src="([^"]+)" type="video/mp4"', html)
                if source_match:
                    video_url = source_match.group(1)
            
            if not video_url:
                self.notify_error("No video URL found")
                xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
                return
            
            xbmc.log(f"HeavyFetish: Playing direct URL: {video_url}", xbmc.LOGINFO)
            
            play_url = f"{video_url}|User-Agent={urllib.parse.quote(headers['User-Agent'])}&Referer={urllib.parse.quote(url)}"
            
            li = xbmcgui.ListItem(path=play_url)
            li.setProperty('IsPlayable', 'true')
            li.setMimeType('video/mp4')
            li.setContentLookup(False)
            xbmcplugin.setResolvedUrl(self.addon_handle, True, li)
                
        except Exception as e:
            xbmc.log(f"HeavyFetish play_video Error: {e}", xbmc.LOGERROR)
            self.notify_error(f"Playback error: {e}")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())

    def FORMAT_SEARCH_QUERY(self, query):
        return urllib.parse.quote(query.strip().replace(' ', '-'))

    def list_categories(self, url):
        html = self.make_request(url)
        if not html:
            self.end_directory()
            return
        
        print(f"DEBUG: list_categories HTML len: {len(html)}")
        print(f"DEBUG: Content Sample: {html[:200]}")
        matches = list(self.RE_CAT.finditer(html))
        print(f"DEBUG: Found {len(matches)} category matches")

        for m in matches:
            cat_url = m.group(1)
            name = m.group(2).strip()
            thumb = m.group(3)
            if not thumb.startswith('http'):
                thumb = urllib.parse.urljoin(self.BASE_URL, thumb)
            self.add_dir(name, cat_url, 2, thumb)
        
        self.end_directory()

