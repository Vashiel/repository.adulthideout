#!/usr/bin/env python
# -*- coding: utf-8 -*-

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
                            if mp4_url.startswith("/media/"):
                                return f"https://www.redtube.com{mp4_url}", "mp4"
                    for media in media_list:
                        if media.get("format") == "hls" and media.get("videoUrl"):
                            hls_url = media["videoUrl"]
                            if hls_url.startswith("/media/"):
                                return f"https://www.redtube.com{hls_url}", "hls"
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
        try:
            parsed_url = urllib_parse.urlparse(url)
            base_path = parsed_url.path.strip('/')
            netloc = parsed_url.netloc
            query = parsed_url.query

            if url == self.base_url or url == self.web_base or not netloc:
                params = {"page": "1", "ordering": "newest", "period": "alltime", "thumbsize": "medium"}
                data, _ = self.api_request("redtube.Videos.searchVideos", params)
                if not data:
                    data, _ = self.api_request("redtube.Videos.searchVideos", {"page": "1"})
                
                if not data or "videos" not in data or not data["videos"]:
                    self.notify_error("No videos found")
                    self.add_basic_dirs(url)
                    self.end_directory()
                    return

                self.add_basic_dirs(url)
                for video in data["videos"]:
                    video_data = video["video"]
                    display_title = f"{video_data['title']} [{video_data.get('duration', '0:00')}]"
                    self.add_link(display_title, video_data["url"], 4, video_data.get("thumb", ""), self.fanart)

                next_page = 2
                total_videos = data.get("count", 0)
                if next_page <= (total_videos + 19) // 20:
                    params["page"] = str(next_page)
                    next_url = f"{self.api_base}?{urllib_parse.urlencode(params, doseq=True)}"
                    self.add_dir("Next Page", next_url, 2, self.icons['default'], self.fanart)

                self.end_directory()
                return

            page = urllib_parse.parse_qs(query).get("page", ["1"])[0]

            if base_path == "categories":
                data, _ = self.api_request("redtube.Categories.getCategoriesList")
                if not data or "categories" not in data:
                    self.notify_error("Failed to load categories")
                else:
                    self.add_basic_dirs(url)
                    for cat in sorted(data["categories"], key=lambda x: x["category"]):
                        cat_url = f"{self.api_base}?data=redtube.Videos.searchVideos&output=json&category={urllib_parse.quote(cat['category'])}&page=1"
                        self.add_dir(cat["category"], cat_url, 2, self.icons['categories'], self.fanart)
                self.end_directory()
                return

            if base_path == "tags":
                data, _ = self.api_request("redtube.Tags.getTagList")
                if not data or "tags" not in data:
                    self.notify_error("Failed to load tags")
                else:
                    self.add_basic_dirs(url)
                    for tag in sorted(data["tags"], key=lambda x: x["tag"]["tag_name"]):
                        tag_name = tag["tag"]["tag_name"]
                        if tag_name:
                            tag_url = f"{self.api_base}?data=redtube.Videos.searchVideos&output=json&tags[]={urllib_parse.quote(tag_name)}&page=1"
                            self.add_dir(tag_name, tag_url, 2, self.icons['default'], self.fanart)
                self.end_directory()
                return

            params = urllib_parse.parse_qs(query)
            params["page"] = page
            
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
        dirs = [
            ('Search RedTube', '', 5, self.icons['search'], self.config['name']),
            ('Categories', f"{self.api_base}categories", 2, self.icons['categories']),
            ('Tags', f"{self.api_base}tags", 2, self.icons['default']),
        ]
        for name, url, mode, icon, *extra in dirs:
            self.add_dir(name, url, mode, icon, self.fanart, [], name_param=extra[0] if extra else name)

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

            list_item = xbmcgui.ListItem(path=stream_url)
            list_item.setProperty('IsPlayable', 'true')
            list_item.setInfo('video', {'title': video_data.get('title', 'Unknown Title')})

            if stream_format == "hls" or ".m3u8" in stream_url:
                list_item.setProperty("inputstream", "inputstream.adaptive")
                list_item.setProperty("inputstream.adaptive.manifest_type", "hls")
                list_item.setMimeType("application/vnd.apple.mpegurl")
            else:
                list_item.setMimeType("video/mp4")

            list_item.setContentLookup(False)
            xbmcplugin.setResolvedUrl(self.addon_handle, True, list_item)
        except Exception as e:
            self.notify_error(f"Playback failed: {e}")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())