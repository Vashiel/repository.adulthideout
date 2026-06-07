#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
import urllib.parse
import urllib.request
import html
import os
import sys
import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed

import xbmc
import xbmcgui
import xbmcplugin
import xbmcvfs

from resources.lib.base_website import BaseWebsite

class Porn4Fans(BaseWebsite):
    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="porn4fans",
            base_url="https://www.porn4fans.com/",
            search_url="https://www.porn4fans.com/search/?q={}",
            addon_handle=addon_handle,
            addon=addon
        )
        self.label = "Porn4Fans"
        self.icon = os.path.join(self.addon.getAddonInfo('path'), 'resources', 'logos', 'porn4fans.png')
        self.icons['default'] = self.icon
        
        self.ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        
        self.sort_options = ["Latest", "Popular", "Top Rated", "Longest"]
        self.sort_paths = {
            "Latest": "/onlyfans-videos/?p=post_date",
            "Popular": "/onlyfans-videos/?p=video_viewed",
            "Top Rated": "/onlyfans-videos/?p=rating",
            "Longest": "/onlyfans-videos/?p=duration"
        }
        self._thumb_cache_dir = self._init_thumb_cache()

    def _init_thumb_cache(self):
        addon_profile = xbmcvfs.translatePath(self.addon.getAddonInfo("profile"))
        thumb_dir = os.path.join(addon_profile, "thumbs", "porn4fans")
        if not xbmcvfs.exists(thumb_dir):
            xbmcvfs.mkdirs(thumb_dir)
        return thumb_dir

    def _download_single_thumb(self, url):
        if not url or not url.startswith("http"):
            return url
        try:
            hashed = hashlib.md5(url.encode("utf-8")).hexdigest()
            for ext in (".webp", ".jpg", ".png", ".gif"):
                cached = os.path.join(self._thumb_cache_dir, hashed + ext)
                if xbmcvfs.exists(cached):
                    return cached
            
            headers = {
                "User-Agent": self.ua,
                "Referer": self.base_url
            }
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = resp.read()
                
            if not data:
                return url
                
            signatures = {
                b"\xFF\xD8\xFF": ".jpg",
                b"\x89PNG\r\n\x1a\n": ".png",
                b"GIF89a": ".gif",
                b"GIF87a": ".gif",
            }
            ext = None
            for sig, e in signatures.items():
                if data.startswith(sig):
                    ext = e
                    break
            if ext is None and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
                ext = ".webp"
            if ext is None:
                ext = ".jpg"
                
            local_path = os.path.join(self._thumb_cache_dir, hashed + ext)
            with xbmcvfs.File(local_path, "wb") as f:
                f.write(data)
            return local_path
        except Exception as e:
            self.logger.warning(f"[porn4fans] Failed to download thumbnail {url}: {e}")
            return url

    def _batch_download_thumbs(self, urls):
        results = {}
        unique = list(set(u for u in urls if u and u.startswith("http")))
        if not unique:
            return results
        with ThreadPoolExecutor(max_workers=10) as pool:
            future_map = {pool.submit(self._download_single_thumb, u): u for u in unique}
            for future in as_completed(future_map):
                orig = future_map[future]
                try:
                    results[orig] = future.result()
                except Exception:
                    results[orig] = orig
        return results

    def make_request(self, url, method="GET", data=None, headers=None):
        self.logger.info(f"[porn4fans] Requesting ({method}): {url}")
        req_headers = {
            "User-Agent": self.ua,
            "Referer": self.base_url
        }
        if headers:
            req_headers.update(headers)
            
        try:
            req = urllib.request.Request(url, headers=req_headers, method=method)
            if data:
                if isinstance(data, dict):
                    data_bytes = urllib.parse.urlencode(data).encode("utf-8")
                else:
                    data_bytes = data
                req.data = data_bytes
            with urllib.request.urlopen(req, timeout=20) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except Exception as e:
            self.logger.error(f"[porn4fans] Request failed: {e}")
            return None

    def _absolute(self, url):
        if not url:
            return ""
        return urllib.parse.urljoin(self.base_url, html.unescape(url).strip())

    def _clean(self, value):
        value = re.sub(r"<[^>]+>", " ", value or "")
        return re.sub(r"\s+", " ", html.unescape(value)).strip()

    def _get_sort_key(self):
        try:
            idx = int(self.addon.getSetting("porn4fans_sort_by") or "0")
        except Exception:
            idx = 0
        if not 0 <= idx < len(self.sort_options):
            idx = 0
        return self.sort_options[idx]

    def get_start_url_and_label(self):
        sort_key = self._get_sort_key()
        return self._absolute(self.sort_paths.get(sort_key, "/onlyfans-videos/?p=post_date")), (
            "{} [COLOR yellow]{}[/COLOR]".format(self.label, sort_key)
        )

    def get_page_url(self, base_url, page_num):
        if page_num <= 1:
            return base_url
            
        parsed = urllib.parse.urlparse(base_url)
        query_params = urllib.parse.parse_qs(parsed.query)
        
        if "/search/" in parsed.path or "q" in query_params:
            query_params["from_videos"] = [str(page_num)]
            new_query = urllib.parse.urlencode(query_params, doseq=True)
            return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))
        
        path = parsed.path
        if not path.endswith('/'):
            path += '/'
            
        match = re.search(r'/(\d+)/$', path)
        if match:
            path = re.sub(r'/(\d+)/$', f'/{page_num}/', path)
        else:
            path += f'{page_num}/'
            
        return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, path, parsed.params, parsed.query, parsed.fragment))

    def _context_menu(self, original_url=None):
        suffix = ""
        if original_url:
            suffix = "&original_url={}".format(urllib.parse.quote_plus(original_url))
        return [
            (
                "Sort by...",
                "RunPlugin({}?mode=7&action=select_sort&website={}{} )".format(
                    sys.argv[0], self.name, suffix
                ).replace(" )", ")"),
            )
        ]

    def _is_top_listing(self, url):
        parsed = urllib.parse.urlparse(url or "")
        path = parsed.path.strip("/")
        return path in ("", "onlyfans-videos")

    def _extract_videos(self, html_content):
        videos = []
        seen = set()
        
        blocks = re.split(r'(?=<div\s+(?:data-video-id="\d+"\s+)?class=["\']item\b)', html_content or "")
        
        for block in blocks:
            if "/video/" not in block:
                continue
                
            href_match = re.search(r'href=["\']([^"\']+/video/\d+/[^"\']*)["\']', block)
            if not href_match:
                continue
            video_url = self._absolute(href_match.group(1))
            if not video_url or video_url in seen:
                continue
            seen.add(video_url)
            
            title_match = re.search(r'title=["\']([^"\']+)["\']', block)
            if not title_match:
                title_match = re.search(r'alt=["\']([^"\']+)["\']', block)
            if not title_match:
                title_match = re.search(r'class=["\']video-text["\'][^>]*>([\s\S]*?)</a>', block)
                
            title = self._clean(title_match.group(1) if title_match else "")
            if not title:
                continue
                
            duration_match = re.search(r'<div class="duration">([^<]+)</div>', block)
            duration = duration_match.group(1).strip() if duration_match else ""
            
            thumb_match = re.search(r'<source[^>]+srcset=["\']([^"\']+)["\']', block)
            if not thumb_match:
                thumb_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', block)
            thumb = self._absolute(thumb_match.group(1) if thumb_match else "")
            
            videos.append({
                "label": title,
                "url": video_url,
                "thumb": thumb or self.icon,
                "duration": duration,
                "info": {"title": title, "plot": title}
            })
            
        return videos

    def _extract_next_page(self, html_content, current_url):
        parsed = urllib.parse.urlparse(current_url)
        query_params = urllib.parse.parse_qs(parsed.query)
        
        current_page = 1
        if "/search/" in parsed.path or "q" in query_params:
            if "from_videos" in query_params:
                try:
                    current_page = int(query_params["from_videos"][0])
                except Exception:
                    pass
        else:
            page_match = re.search(r'/(\d+)/?$', parsed.path)
            if page_match:
                try:
                    current_page = int(page_match.group(1))
                except Exception:
                    pass
                    
        next_page = current_page + 1
        
        has_next = False
        if "/search/" in parsed.path or "q" in query_params:
            if f"from_videos+from_albums:{next_page}" in html_content or f"from_videos:{next_page}" in html_content:
                has_next = True
        else:
            escaped_path = re.escape(parsed.path.rstrip("/"))
            base_path = re.sub(r'/\d+$', '', escaped_path)
            pattern = base_path + r'/' + str(next_page) + r'/?["\']'
            if re.search(pattern, html_content) or f"from:{next_page}" in html_content or "next pager" in html_content:
                has_next = True
                
        if has_next:
            return self.get_page_url(current_url, next_page)
        return None

    def process_content(self, url, page=1):
        if not url or url == "BOOTSTRAP":
            url, _ = self.get_start_url_and_label()
            
        context_menu = self._context_menu(url)
        if self._is_top_listing(url):
            self.add_dir("Search", "", 5, self.icons.get("search", self.icon), context_menu=context_menu)
            self.add_dir("Categories", "https://www.porn4fans.com/categories/", 8, self.icons.get("categories", self.icon), context_menu=context_menu)
            self.add_dir("Models", "https://www.porn4fans.com/models/", 8, self.icons.get("pornstars", self.icon), context_menu=context_menu)
            
        target_url = self.get_page_url(url, page)
        
        html_content = self.make_request(target_url)
        if not html_content:
            self.notify_error("Could not load Porn4Fans listing")
            xbmcplugin.endOfDirectory(self.addon_handle, succeeded=False, updateListing=False, cacheToDisc=False)
            return
            
        videos = self._extract_videos(html_content)
        if not videos:
            self.notify_error("No Porn4Fans videos found")
            return self.end_directory("videos")
            
        thumb_urls = [v["thumb"] for v in videos if v["thumb"]]
        thumb_map = self._batch_download_thumbs(thumb_urls)
        
        for item in videos:
            local_thumb = thumb_map.get(item["thumb"], item["thumb"])
            info_labels = item["info"]
            if item.get("duration"):
                info_labels["duration"] = self.convert_duration(item["duration"])
            self.add_link(
                item["label"],
                item["url"],
                4,
                local_thumb,
                self.fanart,
                context_menu=context_menu,
                info_labels=info_labels
            )
            
        next_url = self._extract_next_page(html_content, target_url)
        if next_url:
            self.add_dir("Next Page", url, 2, self.icons.get("default", self.icon), context_menu=context_menu, page=page + 1)
            
        self.end_directory("videos")

    def process_categories(self, url):
        if "/models/" in url:
            self._process_models(url)
        else:
            self._process_categories(url)

    def _process_categories(self, url):
        html_content = self.make_request(url or "https://www.porn4fans.com/categories/")
        if not html_content:
            self.notify_error("Could not load Porn4Fans categories")
            xbmcplugin.endOfDirectory(self.addon_handle, succeeded=False, updateListing=False, cacheToDisc=False)
            return
            
        seen = set()
        matches = re.findall(r'<a[^>]+class=["\']item["\'][^>]+href=["\'](https://www\.porn4fans\.com/categories/[^"\']+)["\'][^>]*title=["\']([^"\']+)["\']', html_content)
        
        cats = []
        thumb_urls = []
        for href, title in matches:
            cat_url = self._absolute(href)
            if not cat_url or cat_url in seen:
                continue
            seen.add(cat_url)
            
            start_idx = html_content.find(href)
            block = html_content[start_idx:start_idx+1000]
            img_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', block)
            thumb = self._absolute(img_match.group(1) if img_match else "")
            
            cats.append({
                "title": self._clean(title),
                "url": cat_url,
                "thumb": thumb or self.icons.get("categories", self.icon)
            })
            if thumb:
                thumb_urls.append(thumb)
                
        thumb_map = self._batch_download_thumbs(thumb_urls)
        
        for cat in cats:
            local_thumb = thumb_map.get(cat["thumb"], cat["thumb"])
            self.add_dir(cat["title"], cat["url"], 2, local_thumb, self.fanart)
            
        self.end_directory("videos")

    def _process_models(self, url):
        html_content = self.make_request(url or "https://www.porn4fans.com/models/")
        if not html_content:
            self.notify_error("Could not load Porn4Fans models")
            xbmcplugin.endOfDirectory(self.addon_handle, succeeded=False, updateListing=False, cacheToDisc=False)
            return
            
        seen = set()
        matches = re.findall(r'<div class=["\']model-item["\']>.*?<a[^>]+href=["\'](https://www\.porn4fans\.com/models/[^"\']+)["\'][^>]*title=["\']([^"\']+)["\']', html_content, re.DOTALL)
        
        models = []
        thumb_urls = []
        for href, title in matches:
            model_url = self._absolute(href)
            if not model_url or model_url in seen:
                continue
            seen.add(model_url)
            
            start_idx = html_content.find(href)
            block = html_content[start_idx:start_idx+1000]
            img_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', block)
            thumb = self._absolute(img_match.group(1) if img_match else "")
            
            models.append({
                "title": self._clean(title),
                "url": model_url,
                "thumb": thumb or self.icons.get("pornstars", self.icon)
            })
            if thumb:
                thumb_urls.append(thumb)
                
        thumb_map = self._batch_download_thumbs(thumb_urls)
        
        for m in models:
            local_thumb = thumb_map.get(m["thumb"], m["thumb"])
            self.add_dir(m["title"], m["url"], 2, local_thumb, self.fanart)
            
        next_url = self._extract_next_page(html_content, url or "https://www.porn4fans.com/models/")
        if next_url:
            self.add_dir("Next Page", next_url, 8, self.icons.get("default", self.icon))
            
        self.end_directory("videos")

    def search(self, query):
        if query:
            self.process_content(self.search_url.format(urllib.parse.quote_plus(query.strip())))

    def _is_stream_candidate(self, url):
        if not url:
            return False
        lowered = url.lower()
        if "login-required" in lowered:
            return False
        return "/get_file/" in lowered and ".mp4/" in lowered

    def _probe_stream(self, stream_url, referer):
        try:
            headers = {
                "User-Agent": self.ua,
                "Referer": referer,
                "Accept": "*/*",
                "Range": "bytes=0-0",
            }
            req = urllib.request.Request(stream_url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                content_type = resp.headers.get("Content-Type", "")
                return "video" in content_type.lower()
        except Exception as exc:
            self.logger.warning(f"[porn4fans] Stream probe failed for {stream_url}: {exc}")
            return False

    def _extract_stream_url(self, html_content, referer=None):
        download_matches = re.findall(r'href=["\']([^"\']+/get_file/\d+/[^"\']+\.mp4/[^"\']*)["\']', html_content or "", re.IGNORECASE)
        if download_matches:
            for candidate in download_matches:
                stream_url = self._absolute(candidate)
                if self._is_stream_candidate(stream_url) and self._probe_stream(stream_url, referer or self.base_url):
                    return stream_url
            for candidate in reversed(download_matches):
                stream_url = self._absolute(candidate)
                if self._is_stream_candidate(stream_url):
                    return stream_url
            
        matches = re.findall(r'(video_url|video_alt_url\d*|event_reporting2):\s*[\'"]([^\'"]+)["\']', html_content or "")
        urls = {}
        for key, val in matches:
            val = html.unescape(val).replace("\\/", "/")
            if val.startswith("http") and self._is_stream_candidate(val):
                urls[key] = val
                
        keys_in_order = ["video_alt_url4", "video_alt_url3", "video_alt_url2", "video_alt_url", "video_url", "event_reporting2"]
        for key in keys_in_order:
            if key in urls and self._probe_stream(urls[key], referer or self.base_url):
                return urls[key]
        for key in keys_in_order:
            if key in urls:
                return urls[key]
                
        return None

    def resolve_recording_stream(self, url):
        html_content = self.make_request(url)
        stream_url = self._extract_stream_url(html_content, referer=url)
        if not stream_url:
            self.logger.info("[porn4fans] No direct stream on detail page: %s", url)
            return None
        headers = {
            "User-Agent": self.ua,
            "Referer": url,
            "Accept": "*/*"
        }
        return {"url": stream_url, "headers": headers, "extension": "mp4"}

    def play_video(self, url):
        resolved = self.resolve_recording_stream(url)
        if not resolved:
            self.notify_error("Could not resolve stream URL")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return
            
        play_url = resolved["url"]
        headers = resolved.get("headers") or {}
        if headers:
            play_url = "{}|{}".format(play_url, urllib.parse.urlencode(headers))
            
        list_item = xbmcgui.ListItem(path=play_url)
        list_item.setProperty("IsPlayable", "true")
        list_item.setMimeType("video/mp4")
        list_item.setContentLookup(False)
        xbmcplugin.setResolvedUrl(self.addon_handle, True, list_item)
