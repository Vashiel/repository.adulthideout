import re
import sys
import urllib.request
import urllib.parse
import urllib.error
import http.cookiejar
import xbmc
import xbmcgui
import xbmcplugin
import xbmcvfs
import os

from resources.lib.base_website import BaseWebsite
from resources.lib.lookup_info import choose_and_open, extract_html_items

class HQPorner(BaseWebsite):
    def __init__(self, addon_handle):
        super(HQPorner, self).__init__(
            name='hqporner',
            base_url='https://hqporner.com',
            search_url='https://hqporner.com/?q={}',
            addon_handle=addon_handle
        )
        self.sort_options = ['Newest', 'Top Rated', 'Most Viewed (Month)', 'Most Viewed (Week)']
        self.sort_paths = {
            'Newest': '/',
            'Top Rated': '/top',
            'Most Viewed (Month)': '/top/month',
            'Most Viewed (Week)': '/top/week',
        }
        self.cookie_jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cookie_jar))
        self.opener.addheaders = [('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')]
        urllib.request.install_opener(self.opener)

    def _get_html(self, url, referer=None, extra_headers=None):
        max_retries = int(self.addon.getSetting('max_retry_attempts') or 3)
        for attempt in range(max_retries):
            try:
                headers = {
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                }
                if referer:
                    headers['Referer'] = referer
                if extra_headers:
                    headers.update(extra_headers)
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=30) as response:
                    if response.getcode() == 200:
                        return response.read().decode('utf-8', errors='ignore')
                    else:
                        self.logger.error(f"HQPorner: HTTP {response.getcode()} for {url}")
                        return None
            except urllib.error.HTTPError as e:
                self.logger.error(f"HQPorner: HTTP Error {e.code} for {url}: {e.reason}")
                if attempt < max_retries - 1:
                    self.logger.info(f"Retrying ({attempt + 1}/{max_retries})...")
                    continue
                return None
            except Exception as e:
                self.logger.error(f"HQPorner: Request failed for {url}: {e}")
                if attempt < max_retries - 1:
                    self.logger.info(f"Retrying ({attempt + 1}/{max_retries})...")
                    continue
                return None
        return None

    def _check_url(self, url, referer):
        try:
            req = urllib.request.Request(url, method='HEAD', headers={'Referer': referer})
            with urllib.request.urlopen(req, timeout=10) as response:
                return response.getcode() == 200
        except:
            return False

    def _save_debug_html(self, content, filename):
        return

    def _parse_duration(self, duration_str):
        seconds = 0
        try:
            parts = duration_str.strip().split()
            for part in parts:
                if 'h' in part: seconds += int(part.replace('h', '')) * 3600
                elif 'm' in part: seconds += int(part.replace('m', '')) * 60
                elif 's' in part: seconds += int(part.replace('s', ''))
        except (ValueError, TypeError): return 0
        return seconds

    def _build_thumbnail_url(self, thumb_url):
        thumb_url = (thumb_url or '').strip()
        if thumb_url.startswith('//'):
            thumb_url = 'https:' + thumb_url
        elif thumb_url.startswith('/'):
            thumb_url = urllib.parse.urljoin(self.base_url, thumb_url)

        headers = {
            'Referer': self.base_url + '/',
            'User-Agent': self.opener.addheaders[0][1],
        }
        return thumb_url + '|' + urllib.parse.urlencode(headers)

    def process_content(self, url):
        params = {}
        if len(sys.argv) > 2 and sys.argv[2]:
            params = dict(urllib.parse.parse_qsl(sys.argv[2][1:]))
        action = params.get('action')
        if action == "show_related":
            self.process_related_videos(url)
            return

        self.add_dir('[COLOR blue]Search...[/COLOR]', self.base_url, 5, icon=self.icons['search'], fanart=self.fanart)
        self.add_dir('[COLOR blue]Categories...[/COLOR]', self.base_url, 8, icon=self.icons['categories'], fanart=self.fanart)

        html_content = self._get_html(url)
        if not html_content:
            self.notify_error("Failed to load page content.")
            self.end_directory()
            return

        try:
            video_pattern = re.compile(
                r'<a href="(/hdporn/[^"]+)".*?<img.*?src="([^"]+)".*?alt="([^"]+)".*?<span class="icon fa-clock-o meta-data">([^<]+)</span>',
                re.DOTALL
            )
            matches = video_pattern.findall(html_content)

            if not matches: self.notify_info("No videos found on this page.")

            for video_path, thumb_url, title, duration_str in matches:
                video_url = urllib.parse.urljoin(self.base_url, video_path)
                thumbnail = self._build_thumbnail_url(thumb_url)
                duration = self._parse_duration(duration_str)
                info_labels = {'title': title, 'duration': duration, 'plot': title}
                
                context_menu = [
                    ('Explore similar', f'RunPlugin({sys.argv[0]}?mode=7&action=explore_similar&website={self.name}&original_url={urllib.parse.quote_plus(video_url)})')
                ]
                self.add_link(name=title, url=video_url, mode=4, icon=thumbnail, fanart=self.fanart, info_labels=info_labels, context_menu=context_menu)

            next_page_match = re.search(r'<li><a href="([^"]+)" class="button[^"]*?pagi-btn">Next</a></li>', html_content)
            if not next_page_match:
                 next_page_match = re.search(r'<a href="([^"]+)" class="button mobile-pagi pagi-btn">Next</a>', html_content)
            
            if next_page_match:
                next_url = next_page_match.group(1).replace('&amp;', '&')
                next_page_url = urllib.parse.urljoin(self.base_url, next_url)
                self.add_dir('[COLOR blue]Next Page >>[/COLOR]', next_page_url, 2)

        except Exception as e:
            self.logger.error(f"HQPorner: Error parsing content: {e}")
            self.notify_error("Failed to parse the webpage.")

        self.end_directory()

    def process_categories(self, url):
        categories_url = url or 'https://hqporner.com/categories'
        html_content = self._get_html(categories_url)
        if not html_content:
            self.notify_error("Failed to load categories page.")
            self.end_directory()
            return

        try:
            category_pattern = re.compile(
                r'<a href="(/category/[^"]+)"[^>]*>([^<]+)</a>',
                re.DOTALL | re.IGNORECASE
            )
            matches = category_pattern.findall(html_content)

            if not matches:
                self.notify_info("No categories found.")
                self.end_directory()
                return

            seen = set()
            for cat_path, cat_title in matches:
                cat_title = cat_title.strip()
                if not cat_title or cat_title.lower() in seen:
                    continue
                seen.add(cat_title.lower())
                cat_url = urllib.parse.urljoin(self.base_url, cat_path)
                self.add_dir(cat_title.capitalize(), cat_url, 2, icon=self.icons['categories'])

        except Exception as e:
            self.logger.error(f"HQPorner: Error parsing categories: {e}")
            self.notify_error("Failed to parse categories.")

        self.end_directory()

    def play_video(self, url):
        self.logger.info(f"HQPorner: Starting play_video for URL: {url}")
        
        self._get_html(self.base_url)
        hqporner_html = self._get_html(url, referer=self.base_url)
        if not hqporner_html:
            self.logger.error(f"HQPorner: Failed to load main video page. URL: {url}")
            self._save_debug_html("HQPorner: No HTML", f"debug_hqporner_{url[-10:]}.html")
            archive_url = url.replace('/hdporn/', '/archive/')
            self.logger.info(f"HQPorner: Trying archive URL: {archive_url}")
            hqporner_html = self._get_html(archive_url, referer=self.base_url)
            if not hqporner_html:
                self.logger.error(f"HQPorner: Failed to load archive video page. URL: {archive_url}")
                self._save_debug_html("HQPorner: No Archive HTML", f"debug_hqporner_archive_{url[-10:]}.html")
                self.notify_error("This video is no longer available (likely removed or archived).")
                xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
                return
            self._save_debug_html(hqporner_html, f"debug_hqporner_archive_{url[-10:]}.html")
        else:
            self._save_debug_html(hqporner_html, f"debug_hqporner_{url[-10:]}.html")

        mydaddy_match = re.search(
            r'(?:nativeplayer|altplayer|player)\.php\?i=(//mydaddy\.cc/video/[a-f0-9]+/?(?:&alt)?)',
            hqporner_html,
            re.IGNORECASE | re.DOTALL,
        )
        if not mydaddy_match:
            self.logger.error("HQPorner: No mydaddy match found in HTML.")
            self.notify_error("Could not find the embedded video URL.")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return
            
        mydaddy_relative_url = mydaddy_match.group(1).strip()
        if not mydaddy_relative_url.startswith('//'):
            mydaddy_relative_url = '//' + mydaddy_relative_url
        mydaddy_url = 'https:' + mydaddy_relative_url
        self.logger.info(f"HQPorner: Extracted mydaddy URL: {mydaddy_url}")

        mydaddy_html = self._get_html(mydaddy_url, referer=url)
        if not mydaddy_html:
            self.logger.error(f"HQPorner: Failed to load embedded video page: {mydaddy_url}")
            self._save_debug_html("HQPorner: No mydaddy HTML", f"debug_mydaddy_{url[-10:]}.html")
            self.notify_error("Failed to load embedded video page.")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return
        self._save_debug_html(mydaddy_html, f"debug_mydaddy_{url[-10:]}.html")

        source_matches = re.findall(
            r'(//(?:s\d+\.)?(?:bigcdn\.cc|othercdn\.com)/pubs/[a-f0-9.]+/(\d+)\.mp4)',
            mydaddy_html,
            re.IGNORECASE | re.DOTALL,
        )
        if not source_matches:
            self.logger.error("HQPorner: No video path match found in mydaddy HTML.")
            self.notify_error("Could not find the video base path.")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return

        sources = {}
        for full_url, qual_num in source_matches:
            normalized = full_url.rstrip("\\")
            if normalized.startswith('//'):
                normalized = 'https:' + normalized
            try:
                sources[int(qual_num)] = normalized
            except Exception:
                continue

        if not sources:
            self.notify_error("No valid video qualities found.")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return

        selected_quality_num = max(sources.keys())
        final_url = sources[selected_quality_num]
        self.logger.info(f"HQPorner: Selected quality: {selected_quality_num}p, URL: {final_url}")

        playback_url = f"{final_url}|Referer={urllib.parse.quote_plus(mydaddy_url)}&User-Agent={urllib.parse.quote_plus(self.opener.addheaders[0][1])}"
        self.logger.info(f"HQPorner: Playback URL: {playback_url}")
        
        list_item = xbmcgui.ListItem(path=playback_url)
        xbmcplugin.setResolvedUrl(self.addon_handle, True, list_item)

    def process_related_videos(self, url):
        self.add_dir('[COLOR blue]Search...[/COLOR]', self.base_url, 5, icon=self.icons['search'], fanart=self.fanart)
        self.add_dir('[COLOR blue]Categories...[/COLOR]', self.base_url, 8, icon=self.icons['categories'], fanart=self.fanart)

        html_content = self._get_html(url)
        if not html_content:
            self.notify_error("Failed to load page content.")
            self.end_directory()
            return

        try:
            video_pattern = re.compile(
                r'<a href="(/hdporn/[^"]+)".*?<img.*?src="([^"]+)".*?alt="([^"]+)".*?<span class="icon fa-clock-o meta-data">([^<]+)</span>',
                re.DOTALL
            )
            matches = video_pattern.findall(html_content)

            if not matches:
                self.logger.warning("HQPorner: no related videos found.")

            for video_path, thumb_url, title, duration_str in matches:
                video_url = urllib.parse.urljoin(self.base_url, video_path)
                thumbnail = self._build_thumbnail_url(thumb_url)
                duration = self._parse_duration(duration_str)
                info_labels = {'title': title, 'duration': duration, 'plot': title}
                
                context_menu = [
                    ('Explore similar', f'RunPlugin({sys.argv[0]}?mode=7&action=explore_similar&website={self.name}&original_url={urllib.parse.quote_plus(video_url)})')
                ]
                self.add_link(name=title, url=video_url, mode=4, icon=thumbnail, fanart=self.fanart, info_labels=info_labels, context_menu=context_menu)

        except Exception as e:
            self.logger.error(f"HQPorner: Error parsing related content: {e}")

        self.end_directory()

    def explore_similar(self, original_url=None):
        if not original_url:
            self.notify_info("No video URL available")
            return

        html_content = self._get_html(original_url)
        if not html_content:
            self.notify_error("Could not load video info")
            return

        patterns = [
            ("Actress", r'href="(/actress/[^"]+)"[^>]*>([^<]+)', 2),
            ("Category", r'href="(/category/[^"]+)"[^>]*>([^<]+)', 2),
        ]
        items = extract_html_items(html_content, self.base_url, patterns)
        
        if items:
            lang = xbmc.getLanguage(0).lower()
            if "german" in lang or "deutsch" in lang:
                group = "Wiedergabe"
                label = "[COLOR lime]>>> Ähnliche Videos anzeigen <<<[/COLOR]"
            elif "spanish" in lang or "español" in lang or "espanol" in lang:
                group = "Reproducción"
                label = "[COLOR lime]>>> Mostrar videos similares <<<[/COLOR]"
            elif "french" in lang or "français" in lang or "francais" in lang:
                group = "Lecture"
                label = "[COLOR lime]>>> Afficher les vidéos similaires <<<[/COLOR]"
            else:
                group = "Playback"
                label = "[COLOR lime]>>> Show Similar Videos <<<[/COLOR]"
            items.insert(0, {
                "group": group,
                "label": label,
                "url": original_url,
                "mode": 2,
                "action": "show_related"
            })
            
        if not choose_and_open(items, self.name, "Explore similar"):
            self.logger.info("[hqporner] No lookup target selected for {}".format(original_url))
