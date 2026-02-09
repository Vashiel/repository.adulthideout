#!/usr/bin/env python

import re
import json
import urllib.parse as urllib_parse
import urllib.request as urllib_request
import urllib.error
from http.cookiejar import CookieJar
import gzip
from io import BytesIO
import xbmc
import xbmcgui
import xbmcplugin
import xbmcvfs
import os
from resources.lib.base_website import BaseWebsite

class RedtubeWebsite(BaseWebsite):
    config = {
        "name": "redtube",
        "base_url": "https://www.redtube.com/",
        "search_url": "https://api.redtube.com/?data=redtube.Videos.searchVideos&output=json&search={}"
    }

    sort_options = [
        "Newest",
        "Most Viewed",
        "Trending",
        "Top Rated",
        "Longest",
        "Most Favorited"
    ]

    sort_paths = {
        "Newest": "?ordering=newest&period=alltime",
        "Most Viewed": "?ordering=mostviewed&period=alltime",
        "Trending": "?ordering=newest&period=alltime",
        "Top Rated": "?ordering=rating&period=alltime",
        "Longest": "?ordering=newest&period=alltime",
        "Most Favorited": "?ordering=mostfavoured&period=alltime"
    }
    
    web_sort_paths = {
        "Newest": "/newest",
        "Most Viewed": "/mostviewed",
        "Trending": "/hot",
        "Top Rated": "/top",
        "Longest": "/longest",
        "Most Favorited": "/mostfavored"
    }
    
    pornstar_sort_options = [
        "Trending",
        "Top Rated",
        "Most Subscribed",
        "Video Count",
        "Recently Updated",
        "Alphabetical"
    ]
    
    pornstar_sort_paths = {
        "Trending": "/pornstar/",
        "Top Rated": "/pornstar/topranked/",
        "Most Subscribed": "/pornstar/subscribers/",
        "Video Count": "/pornstar/videocount/",
        "Recently Updated": "/pornstar/recentlyupdate/",
        "Alphabetical": "/pornstar/alphabetical/"
    }
    
    pornstar_filters = {
        "gender": {
            "label": "Gender",
            "options": ["All", "Female", "Male", "Transgender"],
            "url_values": {"All": "", "Female": "female", "Male": "male", "Transgender": "transgender"},
            "type": "path"  # Goes in URL path
        },
        "ethnicity": {
            "label": "Ethnicity", 
            "options": ["All", "Asian", "Black", "Indian", "Latin", "Middle Eastern", "White"],
            "url_values": {"All": "", "Asian": "asian", "Black": "black", "Indian": "indian", "Latin": "latin", "Middle Eastern": "middle+eastern", "White": "white"},
            "type": "query"  # Goes in query string
        },
        "cup": {
            "label": "Cup Size",
            "options": ["All", "A", "B", "C", "D", "E", "F", "G+"],
            "url_values": {"All": "", "A": "a", "B": "b", "C": "c", "D": "d", "E": "e", "F": "f", "G+": "g+"},
            "type": "query"
        },
        "hair": {
            "label": "Hair Color",
            "options": ["All", "Blonde", "Black", "Brunette", "Bald", "Red", "Gray"],
            "url_values": {"All": "", "Blonde": "blonde", "Black": "black", "Brunette": "brunette", "Bald": "bald", "Red": "red", "Gray": "gray"},
            "type": "query"
        },
        "breastType": {
            "label": "Breast Type",
            "options": ["All", "Natural", "Fake"],
            "url_values": {"All": "", "Natural": "natural", "Fake": "fake"},
            "type": "query"
        },
        "tattoos": {
            "label": "Tattoos",
            "options": ["All", "Yes", "No"],
            "url_values": {"All": "", "Yes": "yes", "No": "no"},
            "type": "query"
        },
        "piercings": {
            "label": "Piercings",
            "options": ["All", "Yes", "No"],
            "url_values": {"All": "", "Yes": "yes", "No": "no"},
            "type": "query"
        }
    }

    def __init__(self, addon_handle):
        super().__init__(
            name=self.config["name"],
            base_url=self.config["base_url"],
            search_url=self.config["search_url"],
            addon_handle=addon_handle
        )
        self.api_base = "https://api.redtube.com/"
        self.web_base = "https://www.redtube.com/"

    def get_headers(self, referer=None, is_json=False):
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,de;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Origin": "https://www.redtube.com",
            "Referer": referer or "https://www.redtube.com/",
            "sec-ch-ua": '"Google Chrome";v="125", "Chromium";v="125", "Not.A/Brand";v="24"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "document",
            "sec-fetch-mode": "navigate",
            "sec-fetch-site": "same-origin",
            "sec-fetch-user": "?1",
            "DNT": "1",
            "Upgrade-Insecure-Requests": "1",
            "Connection": "keep-alive",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache"
        }
        if is_json:
            headers["Accept"] = "application/json, text/javascript, */*; q=0.01"
            headers["X-Requested-With"] = "XMLHttpRequest"
            headers["sec-fetch-dest"] = "empty"
            headers["sec-fetch-mode"] = "cors"
            headers["sec-fetch-site"] = "same-origin"
        return headers

    def make_request(self, url, headers=None, max_retries=3, retry_wait=5000):
        is_json = 'json' in url.lower()
        headers = headers or self.get_headers(url, is_json=is_json)
        cookie_jar = CookieJar()
        handler = urllib_request.HTTPCookieProcessor(cookie_jar)
        opener = urllib_request.build_opener(handler)
        for attempt in range(max_retries):
            try:
                request = urllib_request.Request(url, headers=headers)
                with opener.open(request, timeout=15) as response:
                    content = response.read()
                    content_encoding = response.info().get('Content-Encoding')
                    if content_encoding == 'gzip':
                        try:
                            content = gzip.GzipFile(fileobj=BytesIO(content)).read()
                        except Exception as e:
                            self.notify_error(f"Gzip decompression failed: {e}")
                            return None, cookie_jar
                    content_str = content.decode('utf-8', errors='ignore')
                    return content_str, cookie_jar
            except urllib.error.HTTPError:
                if attempt < max_retries - 1:
                    xbmc.sleep(retry_wait)
            except Exception:
                if attempt < max_retries - 1:
                    xbmc.sleep(retry_wait)
        self.notify_error(f"Failed to fetch URL: {url}")
        return None, cookie_jar

    def fetch_mp4_json(self, mp4_url, headers, cookie_jar):
        try:
            headers["Accept"] = "application/json, text/javascript, */*; q=0.01"
            headers["X-Requested-With"] = "XMLHttpRequest"
            content, _ = self.make_request(mp4_url, headers=headers)
            if not content:
                return None
            json_data = json.loads(content)
            return json_data
        except (json.JSONDecodeError, Exception):
            return None

    def extract_stream_from_html(self, html_content):
        try:
            media_def_match = re.search(r'mediaDefinition\s*:\s*(\[[\s\S]*?\])\s*,', html_content)
            if media_def_match:
                media_def_str = media_def_match.group(1)
                try:
                    media_list = json.loads(media_def_str)
                    for media in media_list:
                        if media.get("format") == "mp4" and media.get("videoUrl"):
                            mp4_url = media["videoUrl"]
                            if mp4_url.startswith("http"):
                                return mp4_url, "mp4"
                            elif mp4_url.startswith("/"):
                                return f"https://www.redtube.com{mp4_url}", "mp4"
                            else:
                                 return f"https://www.redtube.com/{mp4_url}", "mp4"
                    for media in media_list:
                        if media.get("format") == "hls" and media.get("videoUrl"):
                            hls_url = media["videoUrl"]
                            if hls_url.startswith("http"):
                                return hls_url, "hls"
                            elif hls_url.startswith("/"):
                                return f"https://www.redtube.com{hls_url}", "hls"
                            else:
                                return f"https://www.redtube.com/{hls_url}", "hls"
                except json.JSONDecodeError:
                    pass
            
            mp4_url_match = re.search(r'https:\/\/www\.redtube\.com\/media\/mp4\?s=[^"\']+', html_content)
            if mp4_url_match:
                return mp4_url_match.group(0), "mp4"

            hls_url_match = re.search(r'https:\/\/www\.redtube\.com\/media\/hls\?s=[^"\']+', html_content)
            if hls_url_match:
                return hls_url_match.group(0), "hls"
                
            return None, None
        except Exception:
            return None, None

    def scrape_main_page(self, sort_path):
        """Scrape videos from the main page with sorting (HTML scraping)."""
        url = f"{self.web_base.rstrip('/')}{sort_path}"
        self.logger.info(f"Redtube Debug: Scraping main page: {url}")
        
        html_content, cookie_jar = self.make_request(url)
        if not html_content:
            return []
        
        videos = []
        seen_ids = set()
        
        video_block_pattern = re.compile(
            r'data-video-id="(\d+)".*?'  # Video ID
            r'data-src="([^"]+)".*?'  # Thumbnail
            r'tm_video_duration["\s>]+(\d+:\d+).*?'  # Duration
            r'title="([^"]+)"',  # Title
            re.DOTALL
        )
        
        for match in video_block_pattern.finditer(html_content):
            video_id = match.group(1)
            if video_id in seen_ids:
                continue
            seen_ids.add(video_id)
            
            thumb = match.group(2)
            duration = match.group(3)
            title = match.group(4).strip()
            
            videos.append({
                "video_id": video_id,
                "url": f"{self.web_base}{video_id}",
                "title": title,
                "duration": duration,
                "thumb": thumb
            })
            
            if len(videos) >= 40:
                break
        
        if not videos:
            self.logger.info("Redtube Debug: Primary pattern failed, trying fallback")
            id_matches = re.findall(r'data-video-id="(\d+)"', html_content)
            title_matches = re.findall(r'class="[^"]*video-title[^"]*"[^>]*title="([^"]+)"', html_content)
            duration_matches = re.findall(r'tm_video_duration["\s>]+(\d+:\d+)', html_content)
            thumb_matches = re.findall(r'data-src="(https://[^"]+\.jpg[^"]*)"', html_content)
            
            for i, vid_id in enumerate(id_matches):
                if vid_id in seen_ids:
                    continue
                seen_ids.add(vid_id)
                
                title = title_matches[i] if i < len(title_matches) else f"Video {vid_id}"
                duration = duration_matches[i] if i < len(duration_matches) else "0:00"
                thumb = thumb_matches[i] if i < len(thumb_matches) else ""
                
                videos.append({
                    "video_id": vid_id,
                    "url": f"{self.web_base}{vid_id}",
                    "title": title,
                    "duration": duration,
                    "thumb": thumb
                })
                
                if len(videos) >= 40:
                    break
        
        self.logger.info(f"Redtube Debug: Scraped {len(videos)} videos (with details: {len([v for v in videos if v['thumb']])})")
        return videos

    def scrape_categories(self):
        """Scrape categories with thumbnails from the website."""
        url = f"{self.web_base}categories"
        self.logger.info(f"Redtube Debug: Scraping categories from: {url}")
        
        html_content, _ = self.make_request(url)
        if not html_content:
            return []
        
        categories = []
        cat_pattern = re.compile(
            r'category_item.*?href="([^"]+)".*?data-src="(https://[^"]+)".*?tm_cat_name[^>]*>\s*([^<]+?)\s*<',
            re.DOTALL
        )
        
        for match in cat_pattern.finditer(html_content):
            cat_url = match.group(1)
            thumb = match.group(2)
            name = match.group(3).strip()
            
            cat_name = cat_url.split('/')[-1] if '/' in cat_url else cat_url
            api_url = f"{self.api_base}?data=redtube.Videos.searchVideos&output=json&category={urllib_parse.quote(name)}&page=1"
            
            categories.append({
                "name": name,
                "url": api_url,
                "thumb": thumb
            })
        
        self.logger.info(f"Redtube Debug: Scraped {len(categories)} categories")
        return categories

    def scrape_pornstars(self, sort_path="/pornstar/"):
        """Scrape pornstars with thumbnails from the website."""
        url = f"{self.web_base.rstrip('/')}{sort_path}"
        self.logger.info(f"Redtube Debug: Scraping pornstars from: {url}")
        
        html_content, _ = self.make_request(url)
        if not html_content:
            return []
        
        pornstars = []
        seen_names = set()
        
        ps_pattern = re.compile(
            r'tm_pornstar_link[^>]*href="([^"]+)".*?data-src="(https://[^"]+)".*?tm_pornstar_name[^>]*>\s*([^<]+?)\s*<',
            re.DOTALL
        )
        
        for match in ps_pattern.finditer(html_content):
            ps_url = match.group(1)
            thumb = match.group(2)
            name = match.group(3).strip()
            
            if name in seen_names:
                continue
            seen_names.add(name)
            
            full_url = ps_url if ps_url.startswith("http") else f"{self.web_base.rstrip('/')}{ps_url}"
            
            pornstars.append({
                "name": name,
                "url": full_url,
                "thumb": thumb
            })
            
            if len(pornstars) >= 48:
                break
        
        self.logger.info(f"Redtube Debug: Scraped {len(pornstars)} pornstars")
        return pornstars

    def api_request(self, method, params=None):
        if params is None:
            params = {}
        params.update({"data": method, "output": "json"})
        url = f"{self.api_base}?{urllib_parse.urlencode(params, doseq=True)}"
        content, cookie_jar = self.make_request(url)
        if not content:
            return None, cookie_jar
        try:
            json_data = json.loads(content)
            return json_data, cookie_jar
        except json.JSONDecodeError:
            return None, cookie_jar

    def process_content(self, url):
        self.logger.info(f"Redtube process_content url: {url}")
        try:
            parsed_url = urllib_parse.urlparse(url)
            base_path = parsed_url.path.strip('/')
            netloc = parsed_url.netloc
            query = parsed_url.query
            
            self.logger.info(f"Redtube Debug: base_path='{base_path}', netloc='{netloc}', query='{query}'")

            is_main_page = (url == self.base_url or url == self.web_base or 
                           not netloc or 
                           (not base_path and netloc == "www.redtube.com"))
            
            if is_main_page:
                self.logger.info("Redtube Debug: Main page - using HTML scraping for sorting")
                
                try:
                    sort_idx = int(self.addon.getSetting(f"{self.name}_sort_by") or "0")
                    if 0 <= sort_idx < len(self.sort_options):
                        sort_option = self.sort_options[sort_idx]
                    else:
                        sort_option = self.sort_options[0]
                except (ValueError, TypeError):
                    sort_option = self.sort_options[0]
                
                sort_path = self.web_sort_paths.get(sort_option, "/newest")
                self.logger.info(f"Redtube Debug: Sort option={sort_option}, path={sort_path}")
                
                videos = self.scrape_main_page(sort_path)
                
                if not videos:
                    self.notify_error("No videos found")
                    self.add_basic_dirs(url)
                    self.end_directory()
                    return

                self.add_basic_dirs(url)
                for video in videos:
                    display_title = f"{video['title']} [{video.get('duration', '0:00')}]"
                    self.add_link(display_title, video["url"], 4, video.get("thumb", ""), self.fanart)

                self.end_directory()
                return

            page = urllib_parse.parse_qs(query).get("page", ["1"])[0]

            if base_path == "categories":
                categories = self.scrape_categories()
                if not categories:
                    self.notify_error("Failed to load categories")
                else:
                    self.add_basic_dirs(url)
                    for cat in sorted(categories, key=lambda x: x["name"]):
                        self.add_dir(cat["name"], cat["url"], 2, cat["thumb"], self.fanart)
                self.end_directory()
                return

            if base_path == "pornstar" or base_path.startswith("pornstar/"):
                path_parts = parsed_url.path.strip('/').split('/')
                
                SORT_PATH_NAMES = {'topranked', 'subscribers', 'videocount', 'recentlyupdate', 'alphabetical'}
                GENDER_PATH_NAMES = {'female', 'male', 'transgender'}
                ALL_KNOWN_PATHS = SORT_PATH_NAMES | GENDER_PATH_NAMES
                
                is_list_page = len(path_parts) == 1  # Just /pornstar/
                if len(path_parts) == 2 and path_parts[1] in ALL_KNOWN_PATHS:
                    is_list_page = True
                if len(path_parts) == 3 and path_parts[1] in GENDER_PATH_NAMES and path_parts[2] in SORT_PATH_NAMES:
                    is_list_page = True
                
                if is_list_page:  # Show pornstar list
                    if query and 'reset_filters=1' in query:
                        for filter_name in self.pornstar_filters:
                            self._set_pornstar_filter(filter_name, "All")
                        self.addon.setSetting(f"{self.name}_pornstar_sort", "0")
                        self.logger.info("Redtube Debug: Filters reset via URL parameter")
                    
                    page = 1
                    if query:
                        page_match = re.search(r'page=(\d+)', query)
                        if page_match:
                            page = int(page_match.group(1))
                    
                    filter_url = self._build_pornstar_filter_url()
                    self.logger.info(f"Redtube Debug: Filter URL = {filter_url}")
                    
                    filter_parsed = urllib_parse.urlparse(filter_url)
                    scrape_path = filter_parsed.path
                    filter_query = filter_parsed.query
                    
                    if page > 1:
                        if filter_query:
                            scrape_url = f"{scrape_path}?{filter_query}&page={page}"
                        else:
                            scrape_url = f"{scrape_path}?page={page}"
                    else:
                        if filter_query:
                            scrape_url = f"{scrape_path}?{filter_query}"
                        else:
                            scrape_url = scrape_path
                    
                    pornstars = self.scrape_pornstars(scrape_url)
                    if not pornstars:
                        import sys
                        active_filters = self._get_active_filters_count()
                        if active_filters > 0:
                            xbmcgui.Dialog().notification('Redtube', 'No pornstars found. Please reset filters.', xbmcgui.NOTIFICATION_WARNING, 3000)
                            self.add_basic_dirs(url)
                            reset_url = f"{self.web_base}pornstar/?reset_filters=1"
                            self.add_dir("[COLOR red]Reset Filters[/COLOR]", reset_url, 2, self.icons['default'], self.fanart)
                        else:
                            self.notify_error("Failed to load pornstars")
                    else:
                        self.add_basic_dirs(url)
                        import sys
                        ps_context = [
                            ('Sort Pornstars...', f'RunPlugin({sys.argv[0]}?mode=7&action=select_pornstar_sort&website=redtube)'),
                            ('Filter: Gender...', f'RunPlugin({sys.argv[0]}?mode=7&action=select_pornstar_filter&filter_type=gender&website=redtube)'),
                            ('Filter: Ethnicity...', f'RunPlugin({sys.argv[0]}?mode=7&action=select_pornstar_filter&filter_type=ethnicity&website=redtube)'),
                            ('Filter: Cup Size...', f'RunPlugin({sys.argv[0]}?mode=7&action=select_pornstar_filter&filter_type=cup&website=redtube)'),
                            ('Filter: Hair Color...', f'RunPlugin({sys.argv[0]}?mode=7&action=select_pornstar_filter&filter_type=hair&website=redtube)'),
                            ('Filter: Breast Type...', f'RunPlugin({sys.argv[0]}?mode=7&action=select_pornstar_filter&filter_type=breastType&website=redtube)'),
                            ('Filter: Tattoos...', f'RunPlugin({sys.argv[0]}?mode=7&action=select_pornstar_filter&filter_type=tattoos&website=redtube)'),
                            ('Filter: Piercings...', f'RunPlugin({sys.argv[0]}?mode=7&action=select_pornstar_filter&filter_type=piercings&website=redtube)'),
                            ('[COLOR red]Reset All Filters[/COLOR]', f'RunPlugin({sys.argv[0]}?mode=7&action=reset_pornstar_filters&website=redtube)')
                        ]
                        for ps in pornstars:
                            self.add_dir(ps["name"], ps["url"], 2, ps["thumb"], self.fanart, ps_context)
                        
                        next_page = page + 1
                        next_url = filter_url + ("&" if "?" in filter_url else "?") + f"page={next_page}"
                        self.add_dir(f">> Next Page ({next_page}) >>", next_url, 2, self.icons['default'], self.fanart)
                    self.end_directory()
                    return
                else:  # /pornstar/name - show pornstar's videos
                    self.logger.info(f"Redtube Debug: Scraping videos for pornstar: {path_parts[1]}")
                    videos = self.scrape_main_page(parsed_url.path)
                    
                    if not videos:
                        self.notify_error("No videos found for this pornstar")
                        self.add_basic_dirs(url)
                        self.end_directory()
                        return
                    
                    self.add_basic_dirs(url)
                    for video in videos:
                        display_title = f"{video['title']} [{video.get('duration', '0:00')}]"
                        self.add_link(display_title, video["url"], 4, video.get("thumb", ""), self.fanart)
                    self.end_directory()
                    return

            params = urllib_parse.parse_qs(query)
            params["page"] = page
            
            if "search" in params or "tags[]" in params or "category" in params:
                try:
                    sort_idx = int(self.addon.getSetting(f"{self.name}_sort_by") or "0")
                    if 0 <= sort_idx < len(self.sort_options):
                        sort_option = self.sort_options[sort_idx]
                        sort_path = self.sort_paths.get(sort_option, "")
                        sort_params = urllib_parse.parse_qs(sort_path.lstrip("?"))
                        if "ordering" in sort_params:
                            params["ordering"] = sort_params["ordering"][0]
                        if "period" in sort_params:
                            params["period"] = sort_params["period"][0]
                        self.logger.info(f"Redtube Debug: Applied sort for search - {sort_option}")
                except (ValueError, TypeError):
                    pass
            
            data, _ = self.api_request("redtube.Videos.searchVideos", params)
            if not data or "videos" not in data or not data["videos"]:
                self.notify_error("No videos found")
                self.end_directory()
                return

            self.add_basic_dirs(url)
            for video in data["videos"]:
                video_data = video["video"]
                display_title = f"{video_data['title']} [{video_data.get('duration', '0:00')}]"
                self.add_link(display_title, video_data["url"], 4, video_data.get("thumb", ""), self.fanart)

            next_page = int(page) + 1
            total_videos = data.get("count", 0)
            if next_page <= (total_videos + 19) // 20:
                params["page"] = str(next_page)
                next_url = f"{self.api_base}?{urllib_parse.urlencode(params, doseq=True)}"
                self.add_dir("Next Page", next_url, 2, self.icons['default'], self.fanart)

            self.end_directory()
        except Exception as e:
            self.notify_error(f"Content processing failed: {e}")
            self.end_directory()

    def add_basic_dirs(self, current_url):
        import sys
        self.add_dir('Search RedTube', '', 5, self.icons['search'], self.fanart, [], name_param=self.config['name'])
        self.add_dir('Categories', f"{self.web_base}categories", 2, self.icons['categories'], self.fanart, [], name_param='Categories')
        
        pornstar_url = f"{self.web_base}pornstar/"
        context_items = [
            ('Sort Pornstars...', f'RunPlugin({sys.argv[0]}?mode=7&action=select_pornstar_sort&website=redtube)')
        ]
        self.add_dir('Pornstars', pornstar_url, 2, self.icons['default'], self.fanart, context_items, name_param='Pornstars')

    def play_video(self, url):
        try:
            decoded_url = urllib_parse.unquote_plus(url)
            video_id_match = re.search(r'/(\d+)', decoded_url)
            if not video_id_match:
                self.notify_error("Invalid video URL")
                return xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())

            video_id = video_id_match.group(1)
            params = {"video_id": video_id, "thumbsize": "medium"}
            data, _ = self.api_request("redtube.Videos.getVideoById", params)

            if not data or "video" not in data:
                self.notify_error("Could not get video data")
                return xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())

            video_data = data["video"]
            headers = self.get_headers(referer=decoded_url)
            html_content, cookie_jar = self.make_request(decoded_url, headers=headers)

            stream_url, stream_format = None, None
            if html_content:
                stream_url, stream_format = self.extract_stream_from_html(html_content)
            
            if not stream_url and video_data.get("embed_url"):
                html_content, _ = self.make_request(video_data["embed_url"], headers=headers)
                if html_content:
                    stream_url, stream_format = self.extract_stream_from_html(html_content)

            if stream_url and stream_format == "mp4":
                mp4_json = self.fetch_mp4_json(stream_url, headers, cookie_jar)
                if isinstance(mp4_json, list):
                    sorted_sources = sorted(mp4_json, key=lambda x: int(x.get("quality", "0")), reverse=True)
                    stream_url = next((s["videoUrl"] for q in ["1080", "720", "480", "240"] for s in sorted_sources if s.get("quality") == q and s.get("videoUrl")),
                                      sorted_sources[0].get("videoUrl") if sorted_sources and sorted_sources[0].get("videoUrl") else stream_url)

            if not stream_url:
                self.notify_error("No playable stream found")
                return xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())

            if stream_format == "mp4" or (stream_url and ".mp4" in stream_url.lower()):
                from resources.lib.proxy_utils import ProxyController, PlaybackGuard
                
                proxy = ProxyController(
                    upstream_url=stream_url,
                    upstream_headers=headers,
                    cookies={cookie.name: cookie.value for cookie in cookie_jar}
                )
                local_url = proxy.start()
                
                self.logger.info(f"Redtube Debug: Playing via Proxy: {local_url}")
                
                list_item = xbmcgui.ListItem(path=local_url)
                list_item.setProperty('IsPlayable', 'true')
                list_item.setInfo('video', {'title': video_data.get('title', 'Unknown Title')})
                list_item.setMimeType("video/mp4")
                list_item.setContentLookup(False)
                
                xbmcplugin.setResolvedUrl(self.addon_handle, True, list_item)
                
                guard = PlaybackGuard(
                    xbmc.Player(),
                    xbmc.Monitor(),
                    local_url,
                    proxy
                )
                guard.start()
            else:
                header_string = f"|User-Agent={urllib_parse.quote(headers['User-Agent'])}&Referer={urllib_parse.quote(headers['Referer'])}"
                final_url = stream_url + header_string
                self.logger.info(f"Redtube Debug: Playing HLS URL: {final_url}")
                
                list_item = xbmcgui.ListItem(path=final_url)
                list_item.setProperty('IsPlayable', 'true')
                list_item.setInfo('video', {'title': video_data.get('title', 'Unknown Title')})
                list_item.setProperty("inputstream", "inputstream.adaptive")
                list_item.setProperty("inputstream.adaptive.manifest_type", "hls")
                list_item.setMimeType("application/vnd.apple.mpegurl")
                list_item.setContentLookup(False)
                
                xbmcplugin.setResolvedUrl(self.addon_handle, True, list_item)
        except Exception as e:
            self.notify_error(f"Playback failed: {e}")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())

    def select_pornstar_sort(self, *args):
        """Show a dialog to select pornstar sorting."""
        import sys
        import xbmcgui
        self.logger.info("Redtube Debug: select_pornstar_sort called")
        dialog = xbmcgui.Dialog()
        selection = dialog.select("Sort Pornstars by...", self.pornstar_sort_options)
        self.logger.info(f"Redtube Debug: selection = {selection}")
        if selection >= 0:
            self.addon.setSetting(f"{self.name}_pornstar_sort", str(selection))
            self.logger.info(f"Redtube Debug: Set pornstar_sort to {selection}")
            self._navigate_to_pornstars()

    def _get_pornstar_filter(self, filter_name):
        """Get current value of a pornstar filter from settings."""
        return self.addon.getSetting(f"redtube_ps_{filter_name}") or "All"
    
    def _set_pornstar_filter(self, filter_name, value):
        """Set a pornstar filter value in settings."""
        self.addon.setSetting(f"redtube_ps_{filter_name}", value)
    
    def _get_active_filters_count(self):
        """Count how many filters are active (not 'All')."""
        count = 0
        for filter_name in self.pornstar_filters:
            if self._get_pornstar_filter(filter_name) != "All":
                count += 1
        return count
    
    def _build_pornstar_filter_url(self):
        """Build the URL with all active filters."""
        try:
            ps_sort_idx = int(self.addon.getSetting(f"{self.name}_pornstar_sort") or "0")
            sort_option = self.pornstar_sort_options[ps_sort_idx] if 0 <= ps_sort_idx < len(self.pornstar_sort_options) else "Trending"
        except (ValueError, TypeError):
            sort_option = "Trending"
        
        base_sort_path = self.pornstar_sort_paths.get(sort_option, "/pornstar/")
        
        gender_value = self._get_pornstar_filter("gender")
        gender_url = self.pornstar_filters["gender"]["url_values"].get(gender_value, "")
        
        if gender_url:
            path_parts = base_sort_path.strip('/').split('/')
            if len(path_parts) == 1:  # Just /pornstar/
                path = f"/pornstar/{gender_url}/"
            else:  # /pornstar/alphabetical/ -> /pornstar/female/alphabetical/
                path = f"/pornstar/{gender_url}/{path_parts[1]}/"
        else:
            path = base_sort_path
        
        query_params = []
        for filter_name, filter_def in self.pornstar_filters.items():
            if filter_def["type"] == "query":
                value = self._get_pornstar_filter(filter_name)
                url_value = filter_def["url_values"].get(value, "")
                if url_value:
                    query_params.append(f"{filter_name}={url_value}")
        
        url = f"{self.web_base.rstrip('/')}{path}"
        if query_params:
            url += "?" + "&".join(query_params)
        
        return url
    
    def _navigate_to_pornstars(self):
        """Navigate to pornstars page with current filters."""
        import sys
        url = self._build_pornstar_filter_url()
        plugin_url = f"{sys.argv[0]}?mode=2&url={urllib_parse.quote_plus(url)}&website=redtube"
        xbmc.executebuiltin(f'Container.Update({plugin_url})')
    
    def select_pornstar_filter(self, filter_name, *args):
        """Generic filter selection dialog."""
        import xbmcgui
        if filter_name not in self.pornstar_filters:
            return
        
        filter_def = self.pornstar_filters[filter_name]
        current_value = self._get_pornstar_filter(filter_name)
        
        options = []
        preselect = 0
        for i, opt in enumerate(filter_def["options"]):
            if opt == current_value:
                options.append(f"[B]{opt}[/B] ✓")
                preselect = i
            else:
                options.append(opt)
        
        dialog = xbmcgui.Dialog()
        selection = dialog.select(f"Filter by {filter_def['label']}...", options, preselect=preselect)
        
        if selection >= 0:
            new_value = filter_def["options"][selection]
            self._set_pornstar_filter(filter_name, new_value)
            self._navigate_to_pornstars()
    
    def reset_pornstar_filters(self, *args):
        """Reset all pornstar filters to default."""
        for filter_name in self.pornstar_filters:
            self._set_pornstar_filter(filter_name, "All")
        self.addon.setSetting(f"{self.name}_pornstar_sort", "0")
        self._navigate_to_pornstars()