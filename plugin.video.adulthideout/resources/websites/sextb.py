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
import json
import hashlib
import xbmcvfs
from resources.lib.base_website import BaseWebsite

class Sextb(BaseWebsite):
    
    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="sextb",
            base_url="https://sextb.net",
            search_url="https://sextb.net/search/{}",
            addon_handle=addon_handle,
            addon=addon
        )
        self.sort_options = ["Latest", "Coming Soon", "Most Liked", "Most Viewed", "Popular"]
        self.sort_paths = {
            "Latest": "/jav-censored-u5psppar?genre=all&studio=all&quality=all&year=all&sort=release",
            "Coming Soon": "/new-releases",
            "Most Liked": "/jav-censored-u5psppar?genre=all&studio=all&quality=all&year=all&sort=liked",
            "Most Viewed": "/jav-censored-u5psppar?genre=all&studio=all&quality=all&year=all&sort=viewed",
            "Popular": "/jav-censored-u5psppar?genre=all&studio=all&quality=all&year=all&sort=favorite"
        }
        self.ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        self.icon = os.path.join(self.addon.getAddonInfo('path'), 'resources', 'logos', 'sextb.png')
        self.icons['default'] = self.icon
        
        try:
            addon_root = self.addon.getAddonInfo('path')
            vendor_path = os.path.join(addon_root, "resources", "lib", "vendor")
            if vendor_path not in sys.path:
                sys.path.insert(0, vendor_path)
            import cloudscraper
            self.scraper = cloudscraper.create_scraper(browser={"custom": self.ua})
        except Exception as exc:
            self.logger.error("[sextb] Failed to import/initialize cloudscraper: %s", exc)
            self.scraper = None

        self._last_unplayable_reason = ""
        self._thumb_cache_dir = self._init_thumb_cache()

    def _init_thumb_cache(self):
        addon_profile = xbmcvfs.translatePath(self.addon.getAddonInfo("profile"))
        thumb_dir = os.path.join(addon_profile, "thumbs", "sextb")
        if not xbmcvfs.exists(thumb_dir):
            xbmcvfs.mkdirs(thumb_dir)
        return thumb_dir

    def _download_single_thumb(self, url):
        if not url or not url.startswith("http"):
            return None
        try:
            hashed = hashlib.md5(url.encode("utf-8")).hexdigest()
            for ext in (".jpg", ".png", ".gif", ".webp", ".bmp"):
                cached = os.path.join(self._thumb_cache_dir, hashed + ext)
                if xbmcvfs.exists(cached):
                    return cached
            
            headers = {
                "User-Agent": self.ua,
                "Referer": "https://sextb.net/"
            }
            data = None
            if self.scraper:
                try:
                    resp = self.scraper.get(url, headers=headers, timeout=10)
                    if resp.status_code == 200:
                        data = resp.content
                except Exception as e:
                    self.logger.warning(f"[sextb] cloudscraper thumb download failed: {e}")
            
            if not data:
                try:
                    import urllib.request
                    req = urllib.request.Request(url, headers=headers)
                    with urllib.request.urlopen(req, timeout=10) as resp:
                        data = resp.read()
                except Exception as e:
                    self.logger.warning(f"[sextb] urllib thumb download failed: {e}")
                    
            if not data:
                return None
                
            signatures = {
                b"\xFF\xD8\xFF": ".jpg",
                b"\x89PNG\r\n\x1a\n": ".png",
                b"GIF89a": ".gif",
                b"GIF87a": ".gif",
                b"BM": ".bmp",
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
            self.logger.warning(f"[sextb] Failed to download thumbnail {url}: {e}")
            return None

    def _batch_download_thumbs(self, urls):
        from concurrent.futures import ThreadPoolExecutor, as_completed
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
                    results[orig] = None
        return results

    def xor_decrypt(self, encoded, key):
        import base64
        decoded = base64.b64decode(encoded)
        key_bytes = key.encode('utf-8')
        key_len = len(key_bytes)
        return "".join(chr(decoded[i] ^ key_bytes[i % key_len]) for i in range(len(decoded)))

    def make_request(self, url, method="GET", data=None, headers=None):
        self.logger.info(f"[sextb] Requesting ({method}): {url}")
        req_headers = {
            "User-Agent": self.ua,
            "Referer": self.base_url
        }
        if headers:
            req_headers.update(headers)
        
        if self.scraper:
            try:
                if method == "POST":
                    response = self.scraper.post(url, data=data, headers=req_headers, timeout=20)
                else:
                    response = self.scraper.get(url, headers=req_headers, timeout=20)
                response.raise_for_status()
                return response.text.replace("\x00", "")
            except Exception as exc:
                self.logger.error("[sextb] cloudscraper request failed: %s", exc)
        
        if method == "GET":
            try:
                import urllib.request
                req = urllib.request.Request(url, headers=req_headers)
                with urllib.request.urlopen(req, timeout=20) as response:
                    html_bytes = response.read()
                    return html_bytes.decode('utf-8', errors='ignore').replace("\x00", "")
            except Exception as exc:
                self.logger.error("[sextb] urllib request failed: %s", exc)
        return ""

    def get_page_url(self, base_url, page_num):
        parsed = urllib.parse.urlparse(base_url)
        path = parsed.path
        path = re.sub(r'/pg-\d+/?', '', path)
        path = path.rstrip('/')
        if page_num > 1:
            path += f"/pg-{page_num}"
        return urllib.parse.urlunparse((
            parsed.scheme,
            parsed.netloc,
            path,
            parsed.params,
            parsed.query,
            parsed.fragment
        ))

    def process_content(self, url, page=1):
        self.logger.info(f"[sextb] process_content: {url} | Page: {page}")
        start_url, _ = self.get_start_url_and_label()
        
        self.add_dir("Search", "", 5, self.icons['search'], name_param=self.name)
        self.add_dir("Amateur", "https://sextb.net/jav-amateur-d7r86hnd", 2, self.icons['categories'])
        self.add_dir("Censored", "https://sextb.net/jav-censored-u5psppar", 2, self.icons['categories'])
        self.add_dir("Uncensored", "https://sextb.net/jav-uncensored-wwzd85vc", 2, self.icons['categories'])
        self.add_dir("English Subtitle", "https://sextb.net/jav-subtitle-o9apo8o4", 2, self.icons['categories'])
        self.add_dir("Coming Soon", "https://sextb.net/new-releases", 2, self.icons['categories'])
        self.add_dir("Actresses", "https://sextb.net/list-actress", 9, self.icons['pornstars'])
        self.add_dir("Studios", "https://sextb.net/list-studios", 8, self.icons['categories'])
        self.add_dir("Genres", "https://sextb.net/genres", 11, self.icons['categories'])
        
        target_url = url
        if not target_url or target_url == "BOOTSTRAP":
            target_url = start_url

        if "/search/" in target_url:
            query = urllib.parse.unquote(target_url.split('/search/')[-1].strip('/'))
            self.get_search_listing(query, page)
            return

        self.get_listing(target_url, page)

    def get_search_listing(self, query, page):
        self.logger.info(f"[sextb] Search listing: {query} | Page: {page}")
        ajax_url = "https://sextb.net/ajax/search"
        payload = {
            "q": query,
            "page": page
        }
        headers = {
            "X-Requested-With": "XMLHttpRequest",
            "Referer": self.base_url
        }
        
        resp_text = self.make_request(ajax_url, method="POST", data=payload, headers=headers)
        if not resp_text:
            return self.end_directory()
            
        try:
            data = json.loads(resp_text)
        except Exception as e:
            self.logger.error(f"[sextb] Failed to parse search JSON: {e}")
            return self.end_directory()
            
        hits = data.get("hits", [])
        total_pages = data.get("totalPages", 1)
        
        parsed_items = []
        for hit in hits:
            code = hit.get("code")
            if not code:
                continue
            video_url = f"/{code}"
            title = hit.get("name", "")
            thumb = hit.get("poster", "")
            
            runtime_min = hit.get("runtimes", "")
            if runtime_min:
                title = f"[{runtime_min} min] {title}"
            title = f"{title} ({code.upper()})"
            
            parsed_items.append({
                "title": title,
                "video_url": video_url,
                "thumb_url": thumb
            })
            
        thumb_urls = [item["thumb_url"] for item in parsed_items if item["thumb_url"]]
        thumb_map = self._batch_download_thumbs(thumb_urls)
        
        for item in parsed_items:
            thumb_local = thumb_map.get(item["thumb_url"]) if item["thumb_url"] else None
            thumb_local = thumb_local or self.icons['default']
            self.add_link(item["title"], item["video_url"], 4, thumb_local, self.fanart)
            
        if page < total_pages and len(hits) > 0:
            next_page = page + 1
            search_url = f"https://sextb.net/search/{urllib.parse.quote_plus(query)}"
            self.add_dir(f"[COLOR blue]Next Page ({next_page}) >>[/COLOR]", search_url, 2, self.icons['default'], page=next_page)
            
        self.end_directory()

    def get_listing(self, url, page):
        target_url = url
        if page > 1:
            target_url = self.get_page_url(url, page)
            
        html_content = self.make_request(target_url)
        if not html_content:
            return self.end_directory()
            
        chunks = re.split(r'<div class="tray-item[\s">]', html_content)
        parsed_items = []
        
        for chunk in chunks[1:]:
            block = chunk[:1500]
            
            href_match = re.search(r'href="([^"]+)"', block)
            if not href_match:
                continue
            video_url = href_match.group(1)
            
            if not video_url.startswith('/'):
                continue
                
            alt_match = re.search(r'alt="([^"]+)"', block)
            title = html.unescape(alt_match.group(1).strip()) if alt_match else "Video"
            
            src_match = re.search(r'data-src="([^"]+)"', block)
            if not src_match:
                src_match = re.search(r'src="([^"]+)"', block)
            thumb = src_match.group(1) if src_match else ""
            
            code_match = re.search(r'class="tray-item-code">([^<]+)<', block)
            code = code_match.group(1).strip() if code_match else ""
            
            runtime_match = re.search(r'class="tray-item-runtime">([^<]+)<', block)
            runtime = runtime_match.group(1).strip() if runtime_match else ""
            
            if runtime:
                title = f"[{runtime}] {title}"
            if code:
                title = f"{title} ({code.upper()})"
                
            parsed_items.append({
                "title": title,
                "video_url": video_url,
                "thumb_url": thumb
            })
            
        thumb_urls = [item["thumb_url"] for item in parsed_items if item["thumb_url"]]
        thumb_map = self._batch_download_thumbs(thumb_urls)
        
        items_added = 0
        for item in parsed_items:
            thumb_local = thumb_map.get(item["thumb_url"]) if item["thumb_url"] else None
            thumb_local = thumb_local or self.icons['default']
            self.add_link(item["title"], item["video_url"], 4, thumb_local, self.fanart)
            items_added += 1
            
        if items_added > 0:
            next_page = page + 1
            self.add_dir(f"[COLOR blue]Next Page ({next_page}) >>[/COLOR]", url, 2, self.icons['default'], page=next_page)
                 
        self.end_directory()

    def process_categories(self, url):
        html_content = self.make_request(url)
        if not html_content:
            return self.end_directory()
            
        matches = re.findall(r'<a[^>]+href="(/studio/([^"]+))"[^>]*>(.*?)</a>', html_content)
        seen = set()
        items_added = 0
        for link, slug, name_raw in matches:
            link_full = self.base_url + link
            if link_full not in seen:
                seen.add(link_full)
                name = html.unescape(re.sub(r'<[^>]*>', '', name_raw).strip())
                if name:
                    self.add_dir(name, link_full, 2, self.icons['categories'])
                    items_added += 1
                     

                 
        self.end_directory()

    def process_pornstars(self, url):
        html_content = self.make_request(url)
        if not html_content:
            return self.end_directory()
            
        matches = re.findall(r'<a[^>]+href="(/actress/([^"]+))"[^>]*>(.*?)</a>', html_content)
        seen = set()
        items_added = 0
        for link, slug, name_raw in matches:
            link_full = self.base_url + link
            if link_full not in seen:
                seen.add(link_full)
                name = html.unescape(re.sub(r'<[^>]*>', '', name_raw).strip())
                if name:
                    self.add_dir(name, link_full, 2, self.icons['pornstars'])
                    items_added += 1
                     

                 
        self.end_directory()

    def process_collections(self, url):
        html_content = self.make_request(url)
        if not html_content:
            return self.end_directory()
            
        matches = re.findall(r'<a[^>]+href="(/genre/([^"]+))"[^>]*>(.*?)</a>', html_content)
        seen = set()
        for link, slug, name_raw in matches:
            link_full = self.base_url + link
            if link_full not in seen:
                seen.add(link_full)
                name = html.unescape(re.sub(r'<[^>]*>', '', name_raw).strip())
                if name:
                    self.add_dir(name, link_full, 2, self.icons['categories'])
                     
        self.end_directory()

    def play_video(self, url):
        self.logger.info(f"[sextb] play_video: {url}")
        self._last_unplayable_reason = ""
        resolved = self.resolve_recording_stream(url)
        if not resolved or not resolved.get("url"):
            message = self._last_unplayable_reason or "No playable streams found."
            self.logger.error("[sextb] No playable direct stream links found: %s", message)
            self.notify_error(message)
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return
             
        resolved_url = resolved["url"]
        headers = resolved.get("headers") or {}
        
        self.logger.info(f"[sextb] Playing resolved stream: {resolved_url}")
        liz = xbmcgui.ListItem(path=resolved_url)
        liz.setProperty('IsPlayable', 'true')
        liz.setContentLookup(False)
        
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
        target_url = url
        if not target_url.startswith("http"):
            target_url = urllib.parse.urljoin(self.base_url, target_url)
             
        html_content = self.make_request(target_url)
        if not html_content:
            return None

        if self._is_updating_links_page(html_content):
            self._last_unplayable_reason = "Sextb is still updating links for this video."
            self.logger.warning("[sextb] Video has no public server links yet: %s", target_url)
            return None

        context = self._extract_player_context(html_content)
        if not context:
            self._last_unplayable_reason = "Sextb player data could not be parsed."
            self.logger.warning("[sextb] Failed to parse filmId, pt, or pk from page")
            return None

        film_id, pt, pk, servers = context
        if not servers:
            self._last_unplayable_reason = "Sextb has no public server links for this video."
            self.logger.warning("[sextb] No player server buttons found on video page")
            return None
             
        from resources.lib.resolvers import resolver

        server_resolver_urls = {
            "ST": "https://streamtape.net/",
            "DD": "https://dsvplay.com/",
            "TB": "https://turboplayers.xyz/",
            "SW": "https://hglink.to/",
            "FL": "https://ryderjet.com/",
            "US": "https://player.upn.one/",
            "PP": "https://stb.strp2p.com/",
        }
        priority = ['ST', 'DD', 'TB', 'SW', 'FL', 'US', 'PP']
        enabled_servers = []
        for server in servers:
            resolver_url = server_resolver_urls.get(server[0])
            if resolver_url and not resolver.is_resolver_enabled(resolver_url, self.addon):
                self.logger.info(f"[sextb] Skipping disabled resolver server: {server[0]}")
                continue
            enabled_servers.append(server)

        servers = enabled_servers
        servers.sort(
            key=lambda x: (
                resolver.resolver_sort_key_for_url(server_resolver_urls.get(x[0], ""), self.addon),
                priority.index(x[0]) if x[0] in priority else 99,
            )
        )
         
        ajax_url = "https://sextb.net/ajax/player"
        ajax_headers = {
            "X-Requested-With": "XMLHttpRequest",
            "Referer": target_url
        }
         
        for index, (name, epi_id) in enumerate(servers):
            self.logger.info(f"[sextb] Attempting server: {name} (ID: {epi_id})")
            if index > 0:
                refreshed_html = self.make_request(target_url)
                refreshed_context = self._extract_player_context(refreshed_html) if refreshed_html else None
                if refreshed_context:
                    film_id, pt, pk, refreshed_servers = refreshed_context
                    refreshed_map = dict(refreshed_servers)
                    epi_id = refreshed_map.get(name, epi_id)

            payload = {
                "episode": epi_id,
                "filmId": film_id,
                "pt": pt
            }
             
            resp_text = self.make_request(ajax_url, method="POST", data=payload, headers=ajax_headers)
            if not resp_text:
                continue
                 
            try:
                data = json.loads(resp_text)
            except Exception as je:
                self.logger.warning(f"[sextb] Failed to parse player AJAX JSON response: {je}")
                continue
                 
            if data.get("error"):
                self.logger.warning(f"[sextb] Server error for episode {epi_id}: {data['error']}")
                continue
                 
            player_enc = data.get("player_enc")
            if not player_enc:
                continue
                 
            try:
                decrypted_html = self.xor_decrypt(player_enc, pk)
            except Exception as de:
                self.logger.warning(f"[sextb] Failed to decrypt player payload: {de}")
                continue
                 
            iframe_match = re.search(r'src="([^"]+)"', decrypted_html)
            if not iframe_match:
                self.logger.warning("[sextb] Failed to extract iframe src from decrypted player HTML")
                continue
                 
            iframe_url = iframe_match.group(1)
            if iframe_url.startswith('//'):
                iframe_url = 'https:' + iframe_url
                 
            self.logger.info(f"[sextb] Decrypted iframe URL: {iframe_url}")
             
            try:
                res_url, headers = resolver.resolve(iframe_url, referer=target_url)
                if res_url and not res_url.startswith("http://localhost") and not "ERROR" in res_url:
                    parts = res_url.split('|')
                    direct_url = parts[0]
                    url_headers = headers or {}
                    if len(parts) > 1:
                        extra_headers = dict(urllib.parse.parse_qsl(parts[1]))
                        url_headers.update(extra_headers)
                    ext = "m3u8" if ".m3u8" in direct_url else "mp4"
                    if resolver.resolver_preflight_enabled(self.addon):
                        if not resolver.probe_resolved_stream(direct_url, url_headers):
                            self.logger.warning(
                                f"[sextb] Resolver server {name} failed stream preflight; trying next server"
                            )
                            continue
                    return {"url": direct_url, "headers": url_headers, "extension": ext}
            except Exception as e:
                self.logger.warning(f"[sextb] Failed to resolve iframe URL {iframe_url}: {e}")
                 
        self._last_unplayable_reason = "All available Sextb servers failed."
        return None

    def _extract_player_context(self, html_content):
        film_id_match = re.search(r'var\s+filmId\s*=\s*(\d+);', html_content)
        pt_match = re.search(r'window\.__pt\s*=\s*"([^"]+)";', html_content)
        pk_match = re.search(r'window\.__pk\s*=\s*"([^"]+)";', html_content)
        if not film_id_match or not pt_match or not pk_match:
            return None

        buttons = re.findall(
            r'<button[^>]+class="[^"]*btn-player[^"]*"[^>]*data-id="(\d+)"[^>]*>([\s\S]*?)</button>',
            html_content,
            re.IGNORECASE,
        )
        servers = []
        for epi_id, name_raw in buttons:
            name = re.sub(r'<[^>]*>', '', name_raw).strip()
            if not name or name.upper() == "VIP":
                continue
            servers.append((name, epi_id))

        return film_id_match.group(1), pt_match.group(1), pk_match.group(1), servers

    def _is_updating_links_page(self, html_content):
        lower = (html_content or "").lower()
        return (
            "coming-soon" in lower
            or "we are updating the link for this movie" in lower
            or "please come back later" in lower
        )
