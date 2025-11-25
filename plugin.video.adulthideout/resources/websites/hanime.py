# -*- coding: utf-8 -*-

"""
Hanime.red Website Module for Adult Hideout
Combines the visual layout of the original version with modern technical improvements
"""
import sys
import os
import re
import urllib.request
import urllib.parse
import urllib.error
import base64
import html
import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon

try:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    vendor_path = os.path.abspath(os.path.join(current_dir, '..', 'lib', 'vendor'))
    
    if os.path.exists(vendor_path) and vendor_path not in sys.path:
        sys.path.insert(0, vendor_path)
except Exception:
    pass

try:
    import cloudscraper
    _HAS_CF = True
except ImportError:
    _HAS_CF = False

from resources.lib.base_website import BaseWebsite

class Hanime(BaseWebsite):
    def __init__(self, addon_handle):
        addon = xbmcaddon.Addon()
        name = 'hanime'
        base_url = 'https://hanime.red/'
        search_url = urllib.parse.urljoin(base_url, '?s={}')

        super(Hanime, self).__init__(
            name=name,
            base_url=base_url,
            search_url=search_url,
            addon_handle=addon_handle,
            addon=addon
        )
        
        self.sort_options = [
            "Recent Upload", "Old Upload", "Most Views", "Least Views",
            "Most Likes", "Least Likes", "Alphabetical (A-Z)", "Alphabetical (Z-A)"
        ]
        self.sort_paths = {
            "Recent Upload": "recent-hentai/",
            "Old Upload": "old-videos/",
            "Most Views": "most-views/",
            "Least Views": "least-views/",
            "Most Likes": "most-likes/",
            "Least Likes": "least-likes/",
            "Alphabetical (A-Z)": "alphabetical-a-z/",
            "Alphabetical (Z-A)": "alphabetical-z-a/"
        }
        
        self.scraper = None
        if _HAS_CF:
            try:
                self.scraper = cloudscraper.create_scraper(
                    browser={"browser": "chrome", "platform": "windows", "mobile": False}
                )
            except:
                pass

    def get_start_url_and_label(self):
        label = f"{self.name.capitalize()}"
        url = self.base_url
        
        setting_id = f"{self.name}_sort_by"
        saved_sort_setting = self.addon.getSetting(setting_id)
        
        sort_option = self.sort_options[0]
        
        try:
            sort_idx = int(saved_sort_setting)
        except ValueError:
            try:
                sort_idx = self.sort_options.index(saved_sort_setting)
            except ValueError:
                sort_idx = 0
        
        if 0 <= sort_idx < len(self.sort_options):
            sort_option = self.sort_options[sort_idx]
        
        sort_path = self.sort_paths.get(sort_option)
        if sort_path:
            url = urllib.parse.urljoin(self.base_url, sort_path)
        
        sort_label_suffix = sort_option
        final_label = f"{label} [COLOR yellow]{sort_label_suffix}[/COLOR]"
        
        return url, final_label

    def _get_html(self, url, referer=None):
        if self.scraper:
            try:
                headers = {
                    'Referer': referer if referer else self.base_url,
                    'Accept-Language': 'en-US,en;q=0.9'
                }
                response = self.scraper.get(url, headers=headers, timeout=15)
                if response.status_code == 200:
                    return response.text
            except Exception:
                pass
        
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36'
            }
            if referer:
                headers['Referer'] = referer
            
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as response:
                if 200 <= response.status < 300:
                    return response.read().decode('utf-8', errors='ignore')
        except Exception:
            pass
        
        return None

    def process_content(self, url):
        if not url or url == "BOOTSTRAP":
            url = self.base_url
        
        parsed_url = urllib.parse.urlparse(url)
        path = parsed_url.path.strip('/')
        
        is_main_menu = (
            not path or 
            path == '' or 
            any(sort_path.strip('/') == path for sort_path in self.sort_paths.values())
        )
        
        is_tag_page = path.startswith('tag/')
        
        context_menu = [('Sort by...', f'RunPlugin({sys.argv[0]}?mode=7&website={self.name}&action=select_sort)')]
        
        if is_main_menu and not parsed_url.query and '/page/' not in path:
            self.add_dir('[COLOR yellow]Search[/COLOR]', '', 5, self.icons.get('search', ''), context_menu=context_menu)
            
            tag_url = urllib.parse.urljoin(self.base_url, 'tags-page/')
            self.add_dir('[COLOR yellow]Tags[/COLOR]', tag_url, 8, self.icons.get('categories', ''), context_menu=context_menu)
        
        html_content = self._get_html(url)
        if not html_content:
            self.notify_error("Seite konnte nicht geladen werden.")
            self.end_directory()
            return
        
        video_items = []
        
        if is_tag_page:
            pattern_tag = r'<a href="([^"]+)".*?<h2[^>]+>([^<]+)</h2>.*?<img[^>]+src="([^"]+)"[^>]+class="[^"]*wp-post-image'
            matches_tag = re.findall(pattern_tag, html_content, re.DOTALL)
            
            for video_url, title, thumb_url in matches_tag:
                if not thumb_url.lower().endswith('.svg'):
                    video_items.append({
                        'url': video_url,
                        'title': html.unescape(title.strip()),
                        'thumb': thumb_url
                    })
        else:
            pattern1 = r'<a href="([^"]+)".*?<figure class="main-figure">.*?<img[^>]+src="([^"]+)"[^>]*>.*?</figure>.*?<h2[^>]+>([^<]+)</h2>'
            matches1 = re.findall(pattern1, html_content, re.DOTALL)
            
            for video_url, thumb_url, title in matches1:
                if not thumb_url.lower().endswith('.svg'):
                    video_items.append({
                        'url': video_url,
                        'title': html.unescape(title.strip()),
                        'thumb': thumb_url
                    })
            
            if not video_items:
                pattern2 = r'<article[^>]+class="[^"]*post[^"]*"[^>]*>.*?<a href="([^"]+)"[^>]*>.*?<img[^>]+src="([^"]+)"[^>]*>.*?<h2[^>]*>([^<]+)</h2>'
                matches2 = re.findall(pattern2, html_content, re.DOTALL)
                
                for video_url, thumb_url, title in matches2:
                    if not thumb_url.lower().endswith('.svg'):
                        video_items.append({
                            'url': video_url,
                            'title': html.unescape(title.strip()),
                            'thumb': thumb_url
                        })
            
            if not video_items:
                pattern3 = r'<div[^>]+class="video-thumb">.*?<a href="([^"]+)".*?title="([^"]+)".*?src="([^"]+)"'
                matches3 = re.findall(pattern3, html_content, re.DOTALL)
                
                for video_url, title, thumb_url in matches3:
                    if not thumb_url.lower().endswith('.svg'):
                        video_items.append({
                            'url': video_url,
                            'title': html.unescape(title.strip()),
                            'thumb': thumb_url
                        })
        
        if not video_items:
            self.notify_info("Keine Videos gefunden.")
        else:
            for item in video_items:
                if not item['url'].startswith('http'):
                    item['url'] = urllib.parse.urljoin(self.base_url, item['url'])
                
                try:
                    parsed_thumb = urllib.parse.urlparse(item['thumb'])
                    safe_path = urllib.parse.quote(parsed_thumb.path)
                    safe_thumb = parsed_thumb._replace(path=safe_path).geturl()
                except:
                    safe_thumb = item['thumb']
                
                info_labels = {"title": item['title']}
                self.add_link(item['title'], item['url'], 4, safe_thumb, self.fanart, info_labels=info_labels)
        
        next_page_match = re.search(r'<a[^>]+href="([^"]+)"\s*>Next</a>', html_content, re.IGNORECASE)
        if not next_page_match:
            next_page_match = re.search(r'<a[^>]+class="next page-numbers"[^>]+href="([^"]+)"', html_content)
        
        if next_page_match:
            next_page_url = html.unescape(next_page_match.group(1))
            self.add_dir('[COLOR skyblue]Next Page >>[/COLOR]', next_page_url, 2, self.icons.get('default', ''), context_menu=context_menu)
        
        self.end_directory()

    def process_categories(self, url):
        html_content = self._get_html(url)
        if not html_content:
            self.end_directory()
            return
        
        tag_blocks = re.findall(r'<a class="bg-tr".*?</a>', html_content, re.DOTALL)
        
        if not tag_blocks:
            self.notify_info("Keine Tags gefunden.")
        else:
            for block in tag_blocks:
                url_match = re.search(r'href="([^"]+)"', block)
                title_match = re.search(r'<h2[^>]+>([^<]+)</h2>', block)
                icon_match = re.search(r'<img[^>]+src="([^"]*)"', block)
                
                if url_match and title_match:
                    tag_url = url_match.group(1)
                    title = html.unescape(title_match.group(1).strip())
                    icon_url = icon_match.group(1) if icon_match and not icon_match.group(1).endswith('.svg') else self.icons.get('categories', '')
                    
                    self.add_dir(title.capitalize(), tag_url, 2, icon_url, self.fanart)
        
        self.end_directory()

    def play_video(self, url):
        main_page_html = self._get_html(url)
        if not main_page_html:
            self.notify_error("Video-Seite konnte nicht geladen werden.")
            return
        
        stream_url = None
        
        iframe_match = re.search(r'src="(https://nhplayer\.com/v/[^"]+)"', main_page_html)
        if iframe_match:
            iframe_url = html.unescape(iframe_match.group(1))
            
            iframe_html = self._get_html(iframe_url, referer=url)
            if iframe_html:
                player_match = re.search(r'[\'"]([^\'"]*player\.php\?u=[^\'"]+)[\'"]', iframe_html)
                if player_match:
                    player_url = html.unescape(player_match.group(1))
                    if not player_url.startswith('http'):
                        player_url = urllib.parse.urljoin('https://nhplayer.com/', player_url)
                    
                    try:
                        parsed_url = urllib.parse.urlparse(player_url)
                        query_params = urllib.parse.parse_qs(parsed_url.query)
                        
                        if 'u' in query_params:
                            base64_string = query_params['u'][0]
                            base64_string += '=' * (-len(base64_string) % 4)
                            decoded_bytes = base64.b64decode(base64_string)
                            stream_url = decoded_bytes.decode('utf-8')
                    except Exception:
                        pass
        
        if not stream_url:
            player_match = re.search(r'player\.php\?u=([^"\'&]+)', main_page_html)
            if player_match:
                try:
                    b64_data = player_match.group(1)
                    b64_data += '=' * (-len(b64_data) % 4)
                    stream_url = base64.b64decode(b64_data).decode('utf-8')
                except:
                    pass
        
        if not stream_url:
            source_match = re.search(r'<source[^>]+src="([^"]+)"', main_page_html)
            if source_match:
                stream_url = source_match.group(1)
        
        if stream_url:
            final_path = f"{stream_url}|Referer=https://nhplayer.com/&User-Agent=Mozilla/5.0"
            
            list_item = xbmcgui.ListItem(path=final_path)
            list_item.setProperty('IsPlayable', 'true')
            xbmcplugin.setResolvedUrl(self.addon_handle, True, list_item)
        else:
            self.notify_error("Kein Stream gefunden.")

    def select_sort(self, original_url=None):
        try:
            current_idx = int(self.addon.getSetting(f"{self.name.lower()}_sort_by") or '0')
        except:
            current_idx = 0
        
        if not (0 <= current_idx < len(self.sort_options)):
            current_idx = 0
        
        dialog = xbmcgui.Dialog()
        idx = dialog.select("Sort by...", self.sort_options, preselect=current_idx)
        
        if idx != -1:
            self.addon.setSetting(f"{self.name.lower()}_sort_by", str(idx))
            xbmc.executebuiltin('Container.Refresh')

    def notify_error(self, msg):
        xbmcgui.Dialog().notification('Hanime', msg, xbmcgui.NOTIFICATION_ERROR, 3000)
    
    def notify_info(self, msg):
        xbmcgui.Dialog().notification('Hanime', msg, xbmcgui.NOTIFICATION_INFO, 3000)