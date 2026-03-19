import re
import os
import urllib.parse
import urllib.request
import xbmc
import xbmcgui
import xbmcplugin
from resources.lib.base_website import BaseWebsite

try:
    import cloudscraper
    HAS_CLOUDSCRAPER = True
except ImportError:
    HAS_CLOUDSCRAPER = False


class XcafeWebsite(BaseWebsite):
    BASE_URL = "https://xcafe.com"

    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="xcafe",
            base_url=self.BASE_URL,
            search_url="https://xcafe.com/videos/?q={}",
            addon_handle=addon_handle,
            addon=addon
        )
        self.sort_options = ["Recommended", "Newest", "Most Popular", "Top Rated"]
        # (path, uses_query_pagination)
        # uses_query_pagination=True  → page 2 = base?page=2
        # uses_query_pagination=False → page 2 = base2/
        self.sort_paths = {
            0: ("/videos/", True),
            1: ("/latest-updates/", False),
            2: ("/most-popular/", False),
            3: ("/top-rated/", False),
        }
        self.icon = os.path.join(self.addon.getAddonInfo('path'), 'resources', 'logos', 'xcafe.png')
        self.ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        if HAS_CLOUDSCRAPER:
            self.session = cloudscraper.create_scraper(
                browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True}
            )
        else:
            self.session = None

    # ─── HTTP ────────────────────────────────────────────────────────────────

    def make_request(self, url):
        try:
            if self.session:
                self.session.headers.update({'User-Agent': self.ua, 'Referer': self.BASE_URL})
                r = self.session.get(url, timeout=20)
                if r.status_code == 200:
                    return r.text
            else:
                req = urllib.request.Request(url, headers={
                    'User-Agent': self.ua,
                    'Referer': self.BASE_URL
                })
                with urllib.request.urlopen(req, timeout=20) as resp:
                    return resp.read().decode('utf-8')
        except Exception as e:
            xbmc.log(f"[xcafe] make_request error for {url}: {e}", xbmc.LOGWARNING)
        return None

    # ─── ROUTING ─────────────────────────────────────────────────────────────

    def get_start_url_and_label(self):
        sort_id = f"{self.name}_sort_by"
        sort_index = int(self.addon.getSetting(sort_id) or '0')
        path, _ = self.sort_paths.get(sort_index, ("/videos/", True))
        label = f"xCafe - {self.sort_options[sort_index]}"
        return f"{self.BASE_URL}{path}", label

    def process_content(self, url):
        """Called for mode=2 (video listing pages, including category/model sub-pages)."""
        if url == 'BOOTSTRAP' or not url:
            url, _ = self.get_start_url_and_label()
        self.add_basic_dirs(url)
        self.process_video_list(url)

    def process_categories(self, url):
        """Called for mode=8 (categories listing, models listing, or sub-page videos)."""
        if '/models/' in url and not url.rstrip('/').endswith('/models'):
            # A specific model's video page
            self.process_video_list(url)
        elif url.rstrip('/').endswith('/models'):
            self._list_models()
        elif url.rstrip('/').endswith('/categories'):
            self._list_categories()
        else:
            # A category video page (e.g. /videos/milf/)
            self.process_video_list(url)

    # ─── DIRECTORY HELPERS ───────────────────────────────────────────────────

    def add_basic_dirs(self, current_url):
        self.add_dir('[COLOR blue]Search[/COLOR]', '', 5, self.icons.get('search'))
        self.add_dir('Categories', f'{self.BASE_URL}/categories/', 8, self.icons.get('categories'))
        self.add_dir('Models', f'{self.BASE_URL}/models/', 8, self.icons.get('default'))

    # ─── SHARED LISTING PATTERN ──────────────────────────────────────────────
    # Both categories and models use the same HTML structure as video listings:
    # <a href="https://xcafe.com/videos/milf/" class="popfire">
    #   <img loading="lazy" src="https://i.xcafe.com/..." alt="milf">
    #   <span class="data2"><span class="title">milf</span></span>
    # </a>

    def _parse_popfire_items(self, content, url_pattern):
        """
        Parse items that use the popfire link+thumbnail+title structure.
        url_pattern: regex for the href (e.g. r'https://xcafe\.com/videos/[^/"]+/')
        Returns list of (url, thumb, title) tuples.
        """
        pattern = re.compile(
            r'<a href="(' + url_pattern + r')"[^>]*>\s*'
            r'<img[^>]+src="(https://i\.xcafe\.com/[^"]+)"[^>]*>\s*'
            r'<span class="data2">\s*<span class="title">([^<]+)</span>',
            re.DOTALL
        )
        return pattern.findall(content)

    # ─── CATEGORIES ──────────────────────────────────────────────────────────

    def _list_categories(self):
        content = self.make_request(f"{self.BASE_URL}/categories/")
        if not content:
            self.notify_error("Failed to load xCafe categories")
            self.end_directory()
            return

        items = self._parse_popfire_items(content, r'https://xcafe\.com/videos/[^/"]+/')
        if not items:
            self.notify_error("No categories found")
            self.end_directory()
            return

        seen = set()
        for cat_url, thumb, title in items:
            if cat_url not in seen:
                seen.add(cat_url)
                self.add_dir(title.strip().title(), cat_url, 8, thumb)

        self.end_directory()

    # ─── MODELS ──────────────────────────────────────────────────────────────

    def _list_models(self):
        content = self.make_request(f"{self.BASE_URL}/models/")
        if not content:
            self.notify_error("Failed to load xCafe models")
            self.end_directory()
            return

        items = self._parse_popfire_items(content, r'https://xcafe\.com/models/[^/"]+/')
        if not items:
            self.notify_error("No models found")
            self.end_directory()
            return

        seen = set()
        for model_url, thumb, name in items:
            if model_url not in seen:
                seen.add(model_url)
                self.add_dir(name.strip(), model_url, 8, thumb)

        # Models pagination: /models/2/, /models/3/ etc.
        self._add_next_page(f"{self.BASE_URL}/models/", len(items))
        self.end_directory()

    # ─── VIDEO LISTING ───────────────────────────────────────────────────────

    def process_video_list(self, url):
        content = self.make_request(url)
        if not content:
            self.notify_error("Failed to load xCafe page")
            self.end_directory()
            return

        # Primary pattern: data-video_id + popfire link + img + title
        video_pattern = re.compile(
            r'data-video_id="\d+"[^>]*>\s*'
            r'<a href="(https://xcafe\.com/\d+/)"[^>]*>\s*'
            r'<img[^>]+src="(https://i\.xcafe\.com/[^"]+)"[^>]+alt="([^"]+)"',
            re.DOTALL
        )
        matches = video_pattern.findall(content)

        # Fallback for category/model/search pages (no data-video_id wrapper)
        if not matches:
            fallback = re.compile(
                r'<a href="(https://xcafe\.com/\d+/)"[^>]*>\s*'
                r'<img[^>]+src="(https://i\.xcafe\.com/[^"]+)"[^>]+alt="([^"]+)"',
                re.DOTALL
            )
            matches = fallback.findall(content)

        if not matches:
            self.notify_error("No videos found on xCafe")
            self.end_directory()
            return

        seen = set()
        count = 0
        for video_url, thumb, title in matches:
            if video_url not in seen:
                seen.add(video_url)
                self.add_link(title, video_url, 4, thumb, self.fanart)
                count += 1

        if count > 0:
            self._add_next_page(url, count)

        self.end_directory()

    # ─── PAGINATION ──────────────────────────────────────────────────────────

    def _add_next_page(self, url, count):
        """
        Build the next-page URL.

        URL patterns:
          /videos/          → page 2 = /videos/?page=2   (query param)
          /videos/?page=N   → page N+1 = /videos/?page=N+1
          /videos/?q=...    → page 2 = /videos/?q=...&page=2
          /latest-updates/  → page 2 = /latest-updates/2/
          /latest-updates/N/→ page N+1 = /latest-updates/N+1/
          /videos/milf/     → page 2 = /videos/milf/2/
          /videos/milf/N/   → page N+1 = /videos/milf/N+1/
          /models/          → page 2 = /models/2/
          /models/N/        → page N+1 = /models/N+1/
        """
        # Case 1: already has ?page=N
        page_param_match = re.search(r'[?&]page=(\d+)', url)
        if page_param_match:
            current_page = int(page_param_match.group(1))
            next_page = current_page + 1
            next_url = re.sub(r'page=\d+', f'page={next_page}', url)
            self.add_dir(f'[COLOR blue]Next Page ({next_page}) >>[/COLOR]', next_url, 2, self.icons.get('default'))
            return

        # Case 2: search with ?q= but no page yet
        if '?q=' in url and 'page=' not in url:
            next_url = url + '&page=2'
            self.add_dir('[COLOR blue]Next Page (2) >>[/COLOR]', next_url, 2, self.icons.get('default'))
            return

        # Case 3: /videos/ base (Recommended sort, first page) → use ?page=2
        if re.search(r'/videos/\s*$', url.rstrip('/')):
            next_url = f"{self.BASE_URL}/videos/?page=2"
            self.add_dir('[COLOR blue]Next Page (2) >>[/COLOR]', next_url, 2, self.icons.get('default'))
            return

        # Case 4: path-based pagination — URL already ends with /N/
        path_page_match = re.search(r'/(\d+)/?$', url.rstrip('/'))
        if path_page_match:
            current_page = int(path_page_match.group(1))
            next_page = current_page + 1
            next_url = re.sub(r'/\d+/?$', f'/{next_page}/', url.rstrip('/')) + '/'
            self.add_dir(f'[COLOR blue]Next Page ({next_page}) >>[/COLOR]', next_url, 2, self.icons.get('default'))
            return

        # Case 5: first page of any path-based URL → append /2/
        base = url.rstrip('/')
        next_url = f"{base}/2/"
        self.add_dir('[COLOR blue]Next Page (2) >>[/COLOR]', next_url, 2, self.icons.get('default'))

    # ─── SEARCH ──────────────────────────────────────────────────────────────

    def search(self, query):
        url = f"{self.BASE_URL}/videos/?q={urllib.parse.quote_plus(query)}"
        self.process_video_list(url)

    # ─── PLAYBACK ────────────────────────────────────────────────────────────

    def play_video(self, url):
        content = self.make_request(url)
        if not content:
            self.notify_error("Failed to load xCafe video page")
            return

        video_url = None

        # Pattern 1: "sources":[{"file":"https://...mp4"}]
        sources_match = re.search(
            r'"sources"\s*:\s*\[.*?"file"\s*:\s*"([^"]+\.mp4[^"]*)"',
            content, re.DOTALL
        )
        if sources_match:
            video_url = sources_match.group(1)

        # Pattern 2: file: "https://...mp4"
        if not video_url:
            file_match = re.search(
                r'["\']?file["\']?\s*:\s*["\']([^"\']+\.mp4[^"\']*)["\']',
                content
            )
            if file_match:
                video_url = file_match.group(1)

        # Pattern 3: direct mp4 URLs
        if not video_url:
            mp4_matches = re.findall(r'https?://[^\s"\'<>]+\.mp4[^\s"\'<>]*', content)
            if mp4_matches:
                video_url = mp4_matches[0]

        # Pattern 4: m3u8 stream
        if not video_url:
            m3u8_match = re.search(r'https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*', content)
            if m3u8_match:
                video_url = m3u8_match.group(0)

        if not video_url:
            self.notify_error("No video source found on xCafe")
            return

        video_url = video_url.replace('\\/', '/')

        try:
            from resources.lib.proxy_utils import ProxyController, PlaybackGuard
            controller = ProxyController(video_url, upstream_headers={
                "User-Agent": self.ua,
                "Referer": url
            })
            local_url = controller.start()
            monitor = xbmc.Monitor()
            player = xbmc.Player()
            guard = PlaybackGuard(player, monitor, local_url, controller)
            guard.start()
            li = xbmcgui.ListItem(path=local_url)
            li.setMimeType('video/mp4')
            li.setProperty('IsPlayable', 'true')
            li.setContentLookup(False)
            xbmcplugin.setResolvedUrl(self.addon_handle, True, li)
            guard.join()
        except ImportError:
            headers_str = 'User-Agent={}&Referer={}'.format(
                urllib.parse.quote(self.ua),
                urllib.parse.quote(url)
            )
            li = xbmcgui.ListItem(path=video_url + '|' + headers_str)
            li.setMimeType('video/mp4')
            li.setProperty('IsPlayable', 'true')
            xbmcplugin.setResolvedUrl(self.addon_handle, True, li)
