#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
import urllib.parse
import html
import os
import sys

# Import cloudscraper from vendored libs
vendor_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'lib', 'vendor')
if vendor_path not in sys.path:
    sys.path.insert(0, vendor_path)

import cloudscraper

import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon
from resources.lib.base_website import BaseWebsite


class XMoviesForYou(BaseWebsite):

    def __init__(self, addon_handle=None, addon=None):
        super().__init__(
            name="xmoviesforyou",
            base_url="https://xmoviesforyou.com",
            search_url="https://xmoviesforyou.com/search?q={}",
            addon_handle=addon_handle,
            addon=addon
        )
        self.icons['search'] = os.path.join(
            self.addon.getAddonInfo('path'), 'resources', 'logos', 'search.png')
        self.icons['categories'] = os.path.join(
            self.addon.getAddonInfo('path'), 'resources', 'logos', 'categories.png')
        self.icons['pornstars'] = os.path.join(
            self.addon.getAddonInfo('path'), 'resources', 'logos', 'pornstars.png')

        self.sort_options = ["Newest", "Most Viewed", "Top Rated"]
        self.sort_paths = {
            "Newest":      "/",
            "Most Viewed": "/most-viewed",
            "Top Rated":   "/top-rated",
        }

        self._scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'windows',
                'desktop': True
            }
        )

    # ------------------------------------------------------------------ #
    #  HTTP helper                                                         #
    # ------------------------------------------------------------------ #
    def make_request(self, url):
        try:
            self.logger.info(f"[XMoviesForYou] GET {url}")
            response = self._scraper.get(url, timeout=20)
            if response.status_code == 200:
                return response.text
            self.logger.error(f"[XMoviesForYou] HTTP {response.status_code} for {url}")
            return None
        except Exception as e:
            self.logger.error(f"[XMoviesForYou] Request error: {e}")
            return None

    # ------------------------------------------------------------------ #
    #  Content dispatcher                                                  #
    # ------------------------------------------------------------------ #
    def process_content(self, url):
        # Persistent nav items
        self.add_dir("Search", "", 5, self.icons['search'])
        self.add_dir("Categories", urllib.parse.urljoin(self.base_url, "/categories"), 8,
                     self.icons['categories'])
        self.add_dir("Pornstars", urllib.parse.urljoin(self.base_url, "/pornstars"), 9,
                     self.icons['pornstars'])

        if url == "BOOTSTRAP":
            start_url, _ = self.get_start_url_and_label()
            url = start_url

        self._get_listing(url)

    # ------------------------------------------------------------------ #
    #  Video listing (using real HTML parsing, restores thumbnails)       #
    # ------------------------------------------------------------------ #
    def _get_listing(self, url):
        page_html = self.make_request(url)
        if not page_html:
            return self.end_directory()

        # Current layout renders real videos as Tailwind cards, while <article>
        # blocks are mostly ads. Keep the old parser as fallback below.
        card_pattern = re.compile(
            r'<a\s+href="([^"]+)"\s+class="[^"]*\bgroup\b[^"]*">\s*'
            r'<div[^>]*>.*?'
            r'<img\s+src="([^"]+)"\s+alt="([^"]+)"',
            re.DOTALL | re.IGNORECASE,
        )

        items_added = 0
        seen = set()
        for video_path, thumb, title in card_pattern.findall(page_html):
            if video_path.startswith('http'):
                video_url = video_path
            else:
                video_url = urllib.parse.urljoin(self.base_url, video_path)

            if video_url in seen:
                continue
            seen.add(video_url)

            if not thumb.startswith('http'):
                thumb = urllib.parse.urljoin(self.base_url, thumb)

            title = html.unescape(re.sub(r'\s+', ' ', title).strip())
            if not title:
                continue

            self.add_link(title, video_url, 4, thumb, self.fanart,
                          info_labels={'title': title, 'plot': title})
            items_added += 1

        articles = re.findall(r'<article.*?</article>', page_html, re.DOTALL | re.IGNORECASE)
        self.logger.info(f"[XMoviesForYou] Total <article> tags found: {len(articles)}")
        for i, block in enumerate(articles):
            # Title
            title = ""
            title_match = re.search(r'<h3[^>]*>\s*<a[^>]*>(.*?)</a>', block, re.DOTALL | re.IGNORECASE)
            if title_match:
                # Remove any tags inside title
                title = re.sub(r'<[^>]+>', '', title_match.group(1)).strip()
            
            if not title:
                title_match = re.search(r'alt="([^"]+)"', block, re.IGNORECASE)
                if title_match:
                    title = title_match.group(1).strip()
            
            if not title:
                # If it's an ad or some other block, skip silently if it has no title
                # self.logger.debug(f"[XMoviesForYou] Block {i} skipped: no title found")
                continue

            title = html.unescape(title)

            # URL
            link_match = re.search(r'<a\s+href="(https?://[^"]+|/[^"]+)"', block, re.IGNORECASE)
            if not link_match:
                self.logger.debug(f"[XMoviesForYou] Block {i} skipped: no link found")
                continue
            video_url = link_match.group(1)
            if not video_url.startswith('http'):
                video_url = urllib.parse.urljoin(self.base_url, video_url)
            if video_url in seen:
                continue
            seen.add(video_url)

            # Thumbnail
            img_match = re.search(r'<img[^>]+src="(https?://[^"]+\.(jpg|jpeg|png|webp|gif)[^"]*)"', block, re.IGNORECASE)
            if not img_match:
                img_match = re.search(r'<img[^>]+data-src="(https?://[^"]+\.(jpg|jpeg|png|webp|gif)[^"]*)"', block, re.IGNORECASE)
            thumb = img_match.group(1) if img_match else self.icon

            self.add_link(title, video_url, 4, thumb, self.fanart,
                          info_labels={'title': title, 'plot': title})
            items_added += 1

        self.logger.info(f"[XMoviesForYou] Successfully added {items_added} items to directory")

        # Pagination
        next_url = self._find_next_page(url, page_html, items_added)
        if next_url:
            self.add_dir("Next Page >>", next_url, 2, self.icons['default'])

        self.end_directory()

    def _find_next_page(self, current_url, page_html, item_count):
        """Find next page via next link or URL increment."""
        if item_count < 8:
            return None

        # Actual pagination link on the site
        pag_match = re.search(r'<a\s+href="([^"]+)"[^>]*>Next\s*<', page_html, re.IGNORECASE)
        if not pag_match:
            pag_match = re.search(r'href="(/page/\d+)"[^>]*class="[^"]*primary-btn[^"]*"', page_html, re.IGNORECASE)

        if pag_match:
            href = pag_match.group(1)
            if not href.startswith('http'):
                href = urllib.parse.urljoin(current_url, href)
            return href

        # URL-based increment fallback
        m = re.search(r'([?&]page=)(\d+)', current_url)
        if m:
            next_num = int(m.group(2)) + 1
            return re.sub(r'([?&]page=)\d+', rf'\g<1>{next_num}', current_url)
            
        m2 = re.search(r'/page/(\d+)', current_url)
        if m2:
            next_num = int(m2.group(1)) + 1
            return re.sub(r'/page/\d+', f'/page/{next_num}', current_url)

        if '?' in current_url:
            return f"{current_url}&page=2"
        return f"{current_url}?page=2"

    # ------------------------------------------------------------------ #
    #  Categories                                                          #
    # ------------------------------------------------------------------ #
    def process_categories(self, url):
        if not url.startswith('http'):
            url = urllib.parse.urljoin(self.base_url, url)

        page_html = self.make_request(url)
        if not page_html:
            return self.end_directory()

        # The categories are actually inside <a href="/category/..."> and often contain just text or span
        cats = re.findall(
            r'<a[^>]+href="(?:https?://xmoviesforyou\.com)?/category/([^"]+)"[^>]*>.*?<h3[^>]*>([^<]+)</h3>',
            page_html, re.IGNORECASE | re.DOTALL
        )
        
        seen = set()
        items_added = 0
        for slug, name in cats:
            name = html.unescape(name.strip())
            if len(name) < 2 or len(name) > 60:
                continue
            cat_url = urllib.parse.urljoin(self.base_url, '/category/' + slug)
            if cat_url in seen:
                continue
            seen.add(cat_url)
            self.add_dir(name, cat_url, 2, self.icons['categories'])
            items_added += 1

        next_url = self._find_next_page(url, page_html, items_added)
        if next_url:
            self.add_dir("Next Page >>", next_url, 8, self.icons['default'])

        self.end_directory()

    # ------------------------------------------------------------------ #
    #  Pornstars                                                           #
    # ------------------------------------------------------------------ #
    def process_pornstars(self, url):
        if not url.startswith('http'):
            url = urllib.parse.urljoin(self.base_url, url)
        page_html = self.make_request(url)
        if not page_html:
            return self.end_directory()

        ps = re.findall(
            r'<a[^>]+href="(?:https?://xmoviesforyou\.com)?/pornstar/([^"]+)"[^>]*>.*?<h3[^>]*>([^<]+)</h3>',
            page_html, re.IGNORECASE | re.DOTALL
        )
        
        seen = set()
        items_added = 0
        for slug, name in ps:
            name = html.unescape(name.strip())
            if len(name) < 2:
                continue
            ps_url = urllib.parse.urljoin(self.base_url, '/pornstar/' + slug)
            if ps_url in seen:
                continue
            seen.add(ps_url)
            self.add_dir(name, ps_url, 2, self.icons['pornstars'])
            items_added += 1

        next_url = self._find_next_page(url, page_html, items_added)
        if next_url:
            self.add_dir("Next Page >>", next_url, 9, self.icons['default'])

        self.end_directory()

    # ------------------------------------------------------------------ #
    #  Playback                                                            #
    # ------------------------------------------------------------------ #
    def play_video(self, url):
        page_html = self.make_request(url)
        if not page_html:
            self._fail_playback()
            return

        stream_url = None
        play_headers = {}

        # Collect hosters from page
        from resources.lib.resolvers import resolver
        
        # We look for any absolute links that might be hosters
        all_links = re.findall(r'href="(https?://[^"]+)"', page_html, re.IGNORECASE)
        
        # These are the hosters we know xmoviesforyou uses
        hoster_keywords = ['streamtape', 'mixdrop', 'm1xdrop', 'myvidplay', 'doodstream', 
                           'dsvplay', 'dood.', 'lulustream', 'voe.sx', 'voe-unblock', 
                           'filemoon', 'upstream']

        hoster_links = []
        for link in all_links:
            link_decoded = html.unescape(link)
            if any(h in link_decoded.lower() for h in hoster_keywords):
                hoster_links.append(link_decoded)

        # Prioritize DoodStream links
        dood_keywords = ['dood', 'dsvplay', 'myvidplay']
        hoster_links.sort(key=lambda x: not any(k in x.lower() for k in dood_keywords))

        self.logger.info(f"[XMoviesForYou] Found {len(hoster_links)} potential hoster links (DoodStream prioritized)")

        # Try resolving each one until one works
        for hoster_url in hoster_links:
            self.logger.info(f"[XMoviesForYou] Trying to resolve: {hoster_url}")
            try:
                result = resolver.resolve(hoster_url, referer=url)
                
                # Unpack result
                res_url = None
                res_headers = {}
                if isinstance(result, tuple):
                    res_url = result[0]
                    res_headers = result[1] if len(result) > 1 else {}
                elif isinstance(result, str):
                    res_url = result
                
                if res_url and res_url.startswith('http'):
                    # The resolver.py returns the original URL if no specific resolver is found.
                    # We check if it actually did anything (by comparing clean URLs)
                    clean_res = res_url.split('|')[0]
                    clean_orig = hoster_url.split('|')[0]
                    
                    if clean_res != clean_orig:
                        stream_url = res_url
                        play_headers = res_headers
                        self.logger.info(f"[XMoviesForYou] Successfully resolved: {stream_url[:80]}")
                        break
            except Exception as e:
                self.logger.error(f"[XMoviesForYou] Error resolving {hoster_url}: {e}")

        # Final Fallback: Direct sources in page (legacy)
        if not stream_url:
            src_match = re.search(r'<source[^>]+src=["\']([^"\']+\.(?:m3u8|mp4)[^"\']*)["\']', page_html, re.IGNORECASE)
            if src_match:
                stream_url = src_match.group(1)
        
        if not stream_url:
            js_match = re.search(r'["\']?(?:file|src)["\']?\s*:\s*["\']([^"\']+\.(?:m3u8|mp4)[^"\']*)["\']', page_html, re.IGNORECASE)
            if js_match:
                stream_url = js_match.group(1)

        # Play the video
        if stream_url:
            if stream_url.startswith('//'):
                stream_url = 'https:' + stream_url

            # Build final URL with headers
            ua = self._scraper.headers.get('User-Agent', 'Mozilla/5.0')
            header_parts = []
            if play_headers.get('User-Agent'):
                header_parts.append(f'User-Agent={urllib.parse.quote(play_headers["User-Agent"])}')
            else:
                header_parts.append(f'User-Agent={urllib.parse.quote(ua)}')
            if play_headers.get('Referer'):
                header_parts.append(f'Referer={urllib.parse.quote(play_headers["Referer"])}')
            else:
                header_parts.append(f'Referer={urllib.parse.quote(url)}')

            # Only append pipe-headers if no existing pipe
            if '|' not in stream_url:
                final_url = stream_url + '|' + '&'.join(header_parts)
            else:
                final_url = stream_url

            li = xbmcgui.ListItem(path=final_url)
            if '.m3u8' in stream_url:
                li.setProperty('inputstream', 'inputstream.adaptive')
                li.setProperty('inputstream.adaptive.manifest_type', 'hls')
                li.setMimeType('application/vnd.apple.mpegurl')
            else:
                li.setMimeType('video/mp4')
            li.setProperty('IsPlayable', 'true')
            xbmcplugin.setResolvedUrl(self.addon_handle, True, li)
        else:
            self.logger.error(f"[XMoviesForYou] No stream found in: {url}")
            self._fail_playback()

    def _fail_playback(self):
        self.notify_error("Could not resolve video stream.")
        xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
