# Changelog:
# - Switched to urllib.request for better compatibility
# - Fixed thumbnail URL encoding (HTTP 400 error)
# - Added fallback video extraction for HTML5 source tags
# - Removed redundant context menu items
# - Fixed title extraction (removed "Permalink to")
# - Cleaned up code and comments

import sys
import os
import xbmcaddon
import xbmcgui
import xbmcplugin
import re
import urllib.parse
import urllib.request
import html
import ssl

try:
    _addon = xbmcaddon.Addon()
    _addon_path = _addon.getAddonInfo('path')
    _vendor_path = os.path.join(_addon_path, 'resources', 'lib', 'vendor')
    if _vendor_path not in sys.path:
        sys.path.insert(0, _vendor_path)
except Exception:
    pass

from resources.lib.base_website import BaseWebsite

class HentaigasmWebsite(BaseWebsite):
    def __init__(self, addon_handle):
        super().__init__(
            name="hentaigasm",
            base_url="https://hentaigasm.com",
            search_url="https://hentaigasm.com/?s={}",
            addon_handle=addon_handle
        )
        self.sort_options = ['Date', 'Views', 'Likes', 'Title', 'Random']
        self.sort_paths = {
            'Date': '/?orderby=date',
            'Views': '/?orderby=views',
            'Likes': '/?orderby=likes',
            'Title': '/?orderby=title',
            'Random': '/?orderby=rand'
        }

    def get_headers(self):
        return {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        }

    def make_request(self, url):
        try:
            headers = self.get_headers()
            req = urllib.request.Request(url, headers=headers)
            
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            
            with urllib.request.urlopen(req, context=ctx, timeout=60) as response:
                return response.read().decode('utf-8', errors='ignore')
        except Exception:
            return None

    def process_content(self, url):
        if not url or url == "BOOTSTRAP":
            url = self.base_url
            
        if 's=' not in url and not urllib.parse.urlparse(url).query:
            saved_sort_idx = int(self.addon.getSetting('hentaigasm_sort_by') or '0')
            if 0 <= saved_sort_idx < len(self.sort_options):
                sort_option = self.sort_options[saved_sort_idx]
                path = self.sort_paths.get(sort_option)
                if path:
                    url = urllib.parse.urljoin(self.base_url, path)

        content = self.make_request(url)
        if not content:
            self.end_directory()
            return

        self.add_dir('[COLOR blue]Search[/COLOR]', '', 5, self.icons['search'])

        item_pattern = r'(<div id="post-[\s\S]+?</div>\s*</div>)'
        video_blocks = re.findall(item_pattern, content)

        for block in video_blocks:
            title_match = re.search(r'<h2 class="title"><a href="([^"]+)"[^>]+title="([^"]+)">([^<]+)</a></h2>', block)
            thumb_match = re.search(r'<img src="([^"]+)"', block)
            views_match = re.search(r'<span class="views"><i class="count">([^<]+)</i>', block)

            if title_match and thumb_match:
                video_url = title_match.group(1)
                title_text = title_match.group(3)
                thumb_raw = thumb_match.group(1)
                
                display_title = html.unescape(title_text.strip())
                
                if "AI JERK OFF" in display_title.upper(): continue
                
                if views_match:
                    views = views_match.group(1).strip()
                    display_title += f" [COLOR yellow]({views} Views)[/COLOR]"

                if thumb_raw.startswith('//'):
                    thumb_raw = 'https:' + thumb_raw
                elif not thumb_raw.startswith('http'):
                    thumb_raw = urllib.parse.urljoin(self.base_url, thumb_raw)
                
                parts = urllib.parse.urlparse(thumb_raw)
                path_encoded = urllib.parse.quote(parts.path, safe='/')
                final_thumb_url = urllib.parse.urlunparse(parts._replace(path=path_encoded))
                
                ua_quoted = urllib.parse.quote(self.get_headers()['User-Agent'])
                final_thumb_url += f"|User-Agent={ua_quoted}"

                self.add_link(display_title, video_url, 4, final_thumb_url, self.fanart)

        self.add_next_button(content, url)
        self.end_directory()

    def add_next_button(self, content, current_url):
        next_match = re.search(r'<a class="nextpostslink" rel="next"[^>]+href="([^"]+)">', content)
        if next_match:
            next_url = html.unescape(next_match.group(1))
            self.add_dir('[COLOR blue]Next Page >>>>[/COLOR]', next_url, 2, self.icons['default'], self.fanart)

    def play_video(self, url):
        content = self.make_request(url)
        if not content: return

        video_url_match = re.search(r'file:\s*"([^"]+)"', content)
        if not video_url_match:
            video_url_match = re.search(r'<source[^>]+src=["\']([^"\']+\.mp4)["\']', content)

        if video_url_match:
            video_url_raw = video_url_match.group(1)
            
            parsed_video = urllib.parse.urlparse(video_url_raw)
            clean_path = parsed_video.path.lstrip('.')
            video_url = urllib.parse.urlunparse(parsed_video._replace(path=urllib.parse.quote(clean_path)))
            
            if video_url.startswith('//'):
                video_url = 'https:' + video_url
            
            ua_quoted = urllib.parse.quote(self.get_headers()['User-Agent'])
            video_url += f"|User-Agent={ua_quoted}"

            li = xbmcgui.ListItem(path=video_url)
            li.setProperty('IsPlayable', 'true')
            xbmcplugin.setResolvedUrl(self.addon_handle, True, li)
        else:
            self.notify_error("Video source not found")

    def search(self, query):
        if query:
            self.process_content(self.search_url.format(urllib.parse.quote_plus(query)))