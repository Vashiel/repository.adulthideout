"""
Hanime.red website module for Adult Hideout.

Current playback flow:
  1. Load the Hanime episode page.
  2. Open the nhplayer iframe URL.
  3. Extract the current data-id/player.php URL.
  4. Decode the base64 vid/u payload into the signed CDN URL.
  5. Prefer proxy mode when Python can reach the CDN, otherwise use Kodi's
     native libcurl with pipe headers as fallback.
"""

import base64
import glob
import html
import json
import hashlib
import os
import re
import ssl
import sys
import urllib.parse
import urllib.request
import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
import requests

try:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    vendor_path = os.path.abspath(os.path.join(current_dir, "..", "lib", "vendor"))
    if os.path.exists(vendor_path) and vendor_path not in sys.path:
        sys.path.insert(0, vendor_path)
except Exception:
    pass

try:
    import cloudscraper

    _HAS_CF = True
except ImportError:
    cloudscraper = None
    _HAS_CF = False

try:
    from curl_cffi import requests as curl_requests

    _HAS_CURL_CFFI = True
except ImportError:
    curl_requests = None
    _HAS_CURL_CFFI = False

if not _HAS_CURL_CFFI:
    try:
        local_app_data = os.environ.get("LOCALAPPDATA", "")
        pattern = os.path.join(local_app_data, "Programs", "Python", "Python*", "Lib", "site-packages")
        for site_packages in sorted(glob.glob(pattern), reverse=True):
            if os.path.isdir(site_packages) and site_packages not in sys.path:
                sys.path.append(site_packages)
        from curl_cffi import requests as curl_requests

        _HAS_CURL_CFFI = True
    except Exception:
        curl_requests = None
        _HAS_CURL_CFFI = False

from resources.lib.base_website import BaseWebsite
from resources.lib.proxy_utils import PlaybackGuard, ProxyController

_LOG = "Hanime"
_SCRAPER = None
_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/145.0.0.0 Safari/537.36"
)


class Hanime(BaseWebsite):
    def __init__(self, addon_handle):
        addon = xbmcaddon.Addon()
        super(Hanime, self).__init__(
            name="hanime",
            base_url="https://hanime.red/",
            search_url="https://hanime.red/?s={}",
            addon_handle=addon_handle,
            addon=addon,
        )

        self.sort_options = [
            "Recent Upload",
            "Old Upload",
            "Most Views",
            "Least Views",
            "Most Likes",
            "Least Likes",
            "Alphabetical (A-Z)",
            "Alphabetical (Z-A)",
        ]
        self.sort_paths = {
            "Recent Upload": "recent-hentai/",
            "Old Upload": "old-videos/",
            "Most Views": "most-views/",
            "Least Views": "least-views/",
            "Most Likes": "most-likes/",
            "Least Likes": "least-likes/",
            "Alphabetical (A-Z)": "alphabetical-a-z/",
            "Alphabetical (Z-A)": "alphabetical-z-a/",
        }

        global _SCRAPER
        if _HAS_CF and _SCRAPER is None:
            try:
                _SCRAPER = cloudscraper.create_scraper(
                    browser={"browser": "chrome", "platform": "windows", "mobile": False}
                )
            except Exception as exc:
                xbmc.log(f"{_LOG}: cloudscraper init failed: {exc}", xbmc.LOGINFO)

    def get_start_url_and_label(self):
        setting_id = f"{self.name}_sort_by"
        saved_sort_setting = self.addon.getSetting(setting_id)
        sort_option = self.sort_options[0]

        try:
            sort_idx = int(saved_sort_setting)
        except ValueError:
            sort_idx = 0

        if 0 <= sort_idx < len(self.sort_options):
            sort_option = self.sort_options[sort_idx]

        sort_path = self.sort_paths.get(sort_option, "")
        url = urllib.parse.urljoin(self.base_url, sort_path)
        label = f"{self.name.capitalize()} [COLOR yellow]{sort_option}[/COLOR]"
        return url, label

    def _get_html(self, url, referer=None):
        global _SCRAPER
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/145.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        }
        if referer:
            headers["Referer"] = referer

        if _SCRAPER:
            try:
                response = _SCRAPER.get(url, headers=headers, timeout=15)
                if response.status_code == 200:
                    return response.text
            except Exception as exc:
                xbmc.log(f"{_LOG}: cloudscraper fetch failed for {url[:80]}: {exc}", xbmc.LOGWARNING)

        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as response:
                if 200 <= response.status < 300:
                    return response.read().decode("utf-8", errors="ignore")
        except Exception as exc:
            xbmc.log(f"{_LOG}: urllib fetch failed for {url[:80]}: {exc}", xbmc.LOGWARNING)

        return None

    def _extract_video_items(self, html_content, is_tag_page=False):
        video_items = []

        if is_tag_page:
            pattern = (
                r'<a href="([^"]+)".*?<h2[^>]+>([^<]+)</h2>.*?'
                r'<img[^>]+src="([^"]+)"[^>]+class="[^"]*wp-post-image'
            )
            matches = re.findall(pattern, html_content, re.DOTALL)
            for video_url, title, thumb_url in matches:
                if not thumb_url.lower().endswith(".svg"):
                    video_items.append(
                        {"url": video_url, "title": html.unescape(title.strip()), "thumb": thumb_url}
                    )
            return video_items

        patterns = [
            r'<a href="([^"]+)".*?<figure class="main-figure">.*?<img[^>]+src="([^"]+)"[^>]*>.*?</figure>.*?<h2[^>]+>([^<]+)</h2>',
            r'<article[^>]+class="[^"]*post[^"]*"[^>]*>.*?<a href="([^"]+)"[^>]*>.*?<img[^>]+src="([^"]+)"[^>]*>.*?<h2[^>]*>([^<]+)</h2>',
            r'<div[^>]+class="video-thumb">.*?<a href="([^"]+)".*?title="([^"]+)".*?src="([^"]+)"',
        ]

        for index, pattern in enumerate(patterns):
            matches = re.findall(pattern, html_content, re.DOTALL)
            for match in matches:
                if index < 2:
                    video_url, thumb_url, title = match
                else:
                    video_url, title, thumb_url = match
                if not thumb_url.lower().endswith(".svg"):
                    video_items.append(
                        {"url": video_url, "title": html.unescape(title.strip()), "thumb": thumb_url}
                    )
            if video_items:
                break

        return video_items

    def process_content(self, url):
        if not url or url == "BOOTSTRAP":
            url = self.base_url

        parsed_url = urllib.parse.urlparse(url)
        path = parsed_url.path.strip("/")
        is_main_menu = not path or any(sort_path.strip("/") == path for sort_path in self.sort_paths.values())
        is_tag_page = path.startswith("tag/")

        context_menu = [("Sort by...", f"RunPlugin({sys.argv[0]}?mode=7&website={self.name}&action=select_sort)")]

        if is_main_menu and not parsed_url.query and "/page/" not in path:
            self.add_dir("[COLOR yellow]Search[/COLOR]", "", 5, self.icons.get("search", ""), context_menu=context_menu)
            self.add_dir(
                "[COLOR yellow]Tags[/COLOR]",
                urllib.parse.urljoin(self.base_url, "tags-page/"),
                8,
                self.icons.get("categories", ""),
                context_menu=context_menu,
            )

        html_content = self._get_html(url)
        if not html_content:
            self.notify_error("Seite konnte nicht geladen werden.")
            self.end_directory()
            return

        video_items = self._extract_video_items(html_content, is_tag_page=is_tag_page)
        if not video_items:
            self.notify_info("Keine Videos gefunden.")
        else:
            for item in video_items:
                video_url = item["url"]
                if not video_url.startswith("http"):
                    video_url = urllib.parse.urljoin(self.base_url, video_url)

                thumb_url = item["thumb"]
                try:
                    parsed_thumb = urllib.parse.urlparse(thumb_url)
                    safe_path = urllib.parse.quote(parsed_thumb.path)
                    thumb_url = parsed_thumb._replace(path=safe_path).geturl()
                except Exception:
                    pass

                self.add_link(
                    item["title"],
                    video_url,
                    4,
                    thumb_url,
                    self.fanart,
                    info_labels={"title": item["title"]},
                )

        next_page_match = re.search(r'<a[^>]+href="([^"]+)"\s*>Next</a>', html_content, re.IGNORECASE)
        if not next_page_match:
            next_page_match = re.search(r'<a[^>]+class="next page-numbers"[^>]+href="([^"]+)"', html_content)

        if next_page_match:
            next_page_url = html.unescape(next_page_match.group(1))
            self.add_dir(
                "[COLOR skyblue]Next Page >>[/COLOR]",
                next_page_url,
                2,
                self.icons.get("default", ""),
                context_menu=context_menu,
            )

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
                    icon_url = (
                        icon_match.group(1)
                        if icon_match and not icon_match.group(1).endswith(".svg")
                        else self.icons.get("categories", "")
                    )
                    self.add_dir(title.capitalize(), tag_url, 2, icon_url, self.fanart)

        self.end_directory()

    def _decode_stream_param(self, encoded_value):
        if not encoded_value:
            return None
        try:
            encoded_value += "=" * (-len(encoded_value) % 4)
            return base64.urlsafe_b64decode(encoded_value).decode("utf-8")
        except Exception as exc:
            xbmc.log(f"{_LOG}: base64 decode failed: {exc}", xbmc.LOGERROR)
            return None

    def _new_http_session(self):
        session = requests.Session()
        session.headers.update(
            {
                "User-Agent": _BROWSER_UA,
                "Accept-Language": "en-US,en;q=0.9",
            }
        )
        return session

    def _fetch_with_session(self, session, url, headers=None, params=None, timeout=20):
        response = session.get(url, headers=headers, params=params, timeout=timeout)
        response.raise_for_status()
        return response

    def _build_fingerprint(self):
        payload = {
            "t": 3200,
            "mm": [[120, 100, 101], [190, 160, 208], [260, 190, 450]],
            "tm": [],
            "cl": [[310, 250, 650]],
            "kp": [],
            "sc": [],
            "i": 1,
            "mc": 3,
            "tc": 0,
            "cc": 1,
            "kc": 0,
            "b": {
                "sw": 1920,
                "sh": 1080,
                "aw": 1920,
                "ah": 1040,
                "cd": 24,
                "pd": 24,
                "tz": -60,
                "hc": 8,
                "dm": 8,
                "pl": "Win32",
                "lang": "en-US",
                "langs": "en-US,en",
                "dpr": 1,
                "ww": 1280,
                "wh": 720,
                "touch": False,
                "pdf": True,
                "fonts": 0,
            },
        }
        return base64.b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8")).decode("ascii")

    def _solve_pow(self, challenge):
        nonce = 0
        while nonce < 10000000:
            digest = hashlib.sha256((challenge + format(nonce, "x")).encode("utf-8")).digest()
            if digest[0] == 0 and digest[1] == 0:
                return format(nonce, "x")
            nonce += 1
        raise ValueError("PoW solver exhausted")

    def _resolve_nhplayer_stream(self, video_page_url, iframe_url):
        session = self._new_http_session()

        iframe_headers = {
            "Referer": video_page_url,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Sec-Fetch-Site": "cross-site",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Dest": "iframe",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
        }
        iframe_html = self._fetch_with_session(session, iframe_url, headers=iframe_headers).text

        player_match = re.search(r'data-id="([^"]*player\.php\?(?:u|vid)=[^"]+)"', iframe_html, re.IGNORECASE)
        if not player_match:
            player_match = re.search(r'[\'"]([^\'"]*player\.php\?(?:u|vid)=[^\'"]+)[\'"]', iframe_html, re.IGNORECASE)
        if not player_match:
            return None, None

        player_url = html.unescape(player_match.group(1))
        if not player_url.startswith("http"):
            player_url = urllib.parse.urljoin("https://nhplayer.com/", player_url)

        player_headers = {
            "Referer": iframe_url,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Dest": "iframe",
            "Upgrade-Insecure-Requests": "1",
            "sec-ch-ua": '"Google Chrome";v="145", "Chromium";v="145", "Not.A/Brand";v="24"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
        }
        player_html = self._fetch_with_session(session, player_url, headers=player_headers).text

        core_match = re.search(r'<script src="([^"]*player-core-v2\.php[^"]+)"', player_html, re.IGNORECASE)
        if not core_match:
            return None, None
        core_url = urllib.parse.urljoin("https://nhplayer.com/", html.unescape(core_match.group(1)).replace("&amp;", "&"))

        core_headers = {
            "Referer": player_url,
            "Accept": "*/*",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-Mode": "no-cors",
            "Sec-Fetch-Dest": "script",
        }
        core_js = self._fetch_with_session(session, core_url, headers=core_headers).text

        pv = {key: value for key, value in re.findall(r'(vid|ct|pid|st):"([^"]*)"', player_html)}
        selector_ids = [value for _, value in re.findall(r"var\s+(_\w+)=function\(\)\{return d\.getElementById\('([^']+)'\);\};", core_js)]
        attrs_match = re.search(
            r"p1=e1\.getAttribute\('([^']+)'\)\|\|'',\s*"
            r"p2=e2\.value\|\|'',\s*"
            r"p3=e3\.getAttribute\('([^']+)'\)\|\|'',\s*"
            r"p4=e4\.content\?e4\.content\.textContent\.trim\(\):'',\s*"
            r"ts=e5\.getAttribute\('([^']+)'\)\|\|'';",
            core_js,
            re.DOTALL,
        )
        token_matches = re.findall(r"var\s+(_\w+)='([^']+)';", core_js)
        if len(selector_ids) < 5 or not attrs_match or len(token_matches) < 2:
            return None, None

        attr1, attr3, attr_ts = attrs_match.groups()
        server_challenge = token_matches[0][1]
        request_id = token_matches[1][1]

        try:
            p1 = re.search(rf'id="{re.escape(selector_ids[0])}"[^>]*{re.escape(attr1)}="([^"]+)"', player_html).group(1)
            p2 = re.search(rf'id="{re.escape(selector_ids[1])}"[^>]*value="([^"]+)"', player_html).group(1)
            p3 = re.search(rf'id="{re.escape(selector_ids[2])}"[^>]*{re.escape(attr3)}="([^"]+)"', player_html).group(1)
            p4 = re.search(rf'<template id="{re.escape(selector_ids[3])}"><p>([^<]+)</p></template>', player_html).group(1)
            ts = re.search(rf'id="{re.escape(selector_ids[4])}"[^>]*{re.escape(attr_ts)}="([^"]+)"', player_html).group(1)
        except Exception:
            return None, None

        params = {
            "vid": pv.get("vid", ""),
            "c": pv.get("ct", ""),
            "p1": p1,
            "p2": p2,
            "p3": p3,
            "p4": p4,
            "t": ts,
            "sc": server_challenge,
            "rid": request_id,
            "fp": self._build_fingerprint(),
            "df": "",
            "pow": self._solve_pow(p1 + p2 + p3 + p4 + ts),
            "pid": pv.get("pid", ""),
            "st": pv.get("st", ""),
        }

        api_headers = {
            "Referer": player_url,
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "X-Requested-With": "XMLHttpRequest",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Dest": "empty",
        }
        api_response = self._fetch_with_session(
            session,
            "https://nhplayer.com/get-video-url-v2.php",
            headers=api_headers,
            params=params,
            timeout=30,
        )
        data = api_response.json()
        return data.get("url"), player_url

    def _resolve_stream_url(self, video_page_url, main_page_html):
        iframe_match = re.search(r'src="(https://nhplayer\.com/v/[^"]+)"', main_page_html)
        if iframe_match:
            iframe_url = html.unescape(iframe_match.group(1))
            try:
                stream_url, player_url = self._resolve_nhplayer_stream(video_page_url, iframe_url)
                if stream_url:
                    xbmc.log(f"{_LOG}: stream resolved via player API: {stream_url[:120]}", xbmc.LOGINFO)
                    return stream_url, player_url
            except Exception as exc:
                xbmc.log(f"{_LOG}: player API resolve failed: {exc}", xbmc.LOGWARNING)

            iframe_html = self._get_html(iframe_url, referer=video_page_url)
            if iframe_html:
                player_match = re.search(r'data-id="([^"]*player\.php\?(?:u|vid)=[^"]+)"', iframe_html, re.IGNORECASE)
                if not player_match:
                    player_match = re.search(r'[\'"]([^\'"]*player\.php\?(?:u|vid)=[^\'"]+)[\'"]', iframe_html, re.IGNORECASE)

                if player_match:
                    player_url = html.unescape(player_match.group(1))
                    if not player_url.startswith("http"):
                        player_url = urllib.parse.urljoin("https://nhplayer.com/", player_url)
                    params = urllib.parse.parse_qs(urllib.parse.urlparse(player_url).query)
                    for key in ("vid", "u"):
                        decoded = self._decode_stream_param(params.get(key, [""])[0])
                        if decoded:
                            xbmc.log(f"{_LOG}: stream resolved via legacy {key}: {decoded[:120]}", xbmc.LOGINFO)
                            return decoded, player_url

        source_match = re.search(r'<source[^>]+src="([^"]+)"', main_page_html)
        if source_match:
            return source_match.group(1), video_page_url

        return None, None

    def _probe_cdn(self, stream_url, headers):
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        for method in ["HEAD", "GET"]:
            try:
                probe_headers = dict(headers)
                if method == "GET":
                    probe_headers["Range"] = "bytes=0-1"

                req = urllib.request.Request(stream_url, headers=probe_headers)
                if method == "HEAD":
                    req.get_method = lambda: "HEAD"

                response = urllib.request.urlopen(req, timeout=5, context=ctx)
                status = response.status
                response.close()
                if status in (200, 206):
                    xbmc.log(f"{_LOG}: CDN probe OK ({method} -> {status})", xbmc.LOGINFO)
                    return True
            except urllib.error.HTTPError as exc:
                xbmc.log(f"{_LOG}: CDN probe {method} -> {exc.code}", xbmc.LOGWARNING)
                if exc.code == 403 and method == "GET":
                    return False
            except Exception as exc:
                xbmc.log(f"{_LOG}: CDN probe {method} error: {exc}", xbmc.LOGWARNING)

        return False

    def _probe_cloudscraper(self, stream_url, headers):
        global _SCRAPER
        if not _HAS_CF or not _SCRAPER:
            return False

        try:
            probe_headers = dict(headers)
            probe_headers["Range"] = "bytes=0-1"
            response = _SCRAPER.get(stream_url, headers=probe_headers, timeout=5)
            if response.status_code in (200, 206):
                xbmc.log(f"{_LOG}: Cloudscraper probe OK -> {response.status_code}", xbmc.LOGINFO)
                return True
            xbmc.log(f"{_LOG}: Cloudscraper probe -> {response.status_code}", xbmc.LOGWARNING)
        except Exception as exc:
            xbmc.log(f"{_LOG}: Cloudscraper probe error: {exc}", xbmc.LOGWARNING)

        return False

    def _probe_curl_cffi(self, stream_url, headers):
        if not _HAS_CURL_CFFI:
            return False

        try:
            session = curl_requests.Session(impersonate="chrome123", verify=False)
            session.headers.update(headers)
            response = session.get(stream_url, headers={"Range": "bytes=0-1"}, stream=True, timeout=10)
            ok = response.status_code in (200, 206)
            xbmc.log(f"{_LOG}: curl_cffi probe -> {response.status_code}", xbmc.LOGINFO if ok else xbmc.LOGWARNING)
            response.close()
            return ok
        except Exception as exc:
            xbmc.log(f"{_LOG}: curl_cffi probe error: {exc}", xbmc.LOGWARNING)
            return False

    def _play_via_proxy(self, stream_url, proxy_headers):
        xbmc.log(f"{_LOG}: Using PROXY mode (urllib)", xbmc.LOGINFO)
        controller = ProxyController(
            upstream_url=stream_url,
            upstream_headers=proxy_headers,
            cookies=None,
            use_urllib=True,
        )
        local_url = controller.start()

        list_item = xbmcgui.ListItem(path=local_url)
        list_item.setProperty("IsPlayable", "true")
        list_item.setMimeType("video/mp4")
        list_item.setContentLookup(False)
        xbmcplugin.setResolvedUrl(self.addon_handle, True, list_item)

        player = xbmc.Player()
        monitor = xbmc.Monitor()
        PlaybackGuard(player, monitor, local_url, controller).start()

    def _play_direct_kodi(self, stream_url, proxy_headers):
        xbmc.log(f"{_LOG}: Using DIRECT mode (Kodi libcurl)", xbmc.LOGINFO)
        pipe_headers = dict(proxy_headers)
        pipe_headers.pop("Accept-Encoding", None)
        pipe_headers.pop("Connection", None)
        header_str = "&".join(f"{key}={urllib.parse.quote(value)}" for key, value in pipe_headers.items())
        safe_stream_url = stream_url.replace("|", "%7C")
        play_url = f"{safe_stream_url}|{header_str}"

        list_item = xbmcgui.ListItem(path=play_url)
        list_item.setProperty("IsPlayable", "true")
        list_item.setMimeType("video/mp4")
        list_item.setContentLookup(False)
        xbmcplugin.setResolvedUrl(self.addon_handle, True, list_item)

    def _play_via_curl_cffi_proxy(self, stream_url, proxy_headers):
        if not _HAS_CURL_CFFI:
            return False

        xbmc.log(f"{_LOG}: Using PROXY mode (curl_cffi)", xbmc.LOGINFO)
        try:
            session = curl_requests.Session(impersonate="chrome123", verify=False)
            controller = ProxyController(
                upstream_url=stream_url,
                upstream_headers=proxy_headers,
                cookies=None,
                session=session,
                skip_resolve=True,
                use_urllib=False,
            )
            local_url = controller.start()
            list_item = xbmcgui.ListItem(path=local_url)
            list_item.setProperty("IsPlayable", "true")
            list_item.setMimeType("video/mp4")
            list_item.setContentLookup(False)
            xbmcplugin.setResolvedUrl(self.addon_handle, True, list_item)

            player = xbmc.Player()
            monitor = xbmc.Monitor()
            PlaybackGuard(player, monitor, local_url, controller).start()
            return True
        except Exception as exc:
            xbmc.log(f"{_LOG}: curl_cffi proxy failed: {exc}", xbmc.LOGERROR)
            return False

    def _play_via_cloudscraper_proxy(self, stream_url, proxy_headers):
        global _SCRAPER
        if not _HAS_CF or not _SCRAPER:
            return False

        xbmc.log(f"{_LOG}: Using PROXY mode (cloudscraper)", xbmc.LOGINFO)
        try:
            controller = ProxyController(
                upstream_url=stream_url,
                upstream_headers=proxy_headers,
                cookies=None,
                session=_SCRAPER,
                use_urllib=False,
            )
            local_url = controller.start()
            list_item = xbmcgui.ListItem(path=local_url)
            list_item.setProperty("IsPlayable", "true")
            list_item.setMimeType("video/mp4")
            list_item.setContentLookup(False)
            xbmcplugin.setResolvedUrl(self.addon_handle, True, list_item)

            player = xbmc.Player()
            monitor = xbmc.Monitor()
            PlaybackGuard(player, monitor, local_url, controller).start()
            return True
        except Exception as exc:
            xbmc.log(f"{_LOG}: Cloudscraper proxy failed: {exc}", xbmc.LOGERROR)
            return False

    def play_video(self, url):
        main_page_html = self._get_html(url)
        if not main_page_html:
            self.notify_error("Video-Seite konnte nicht geladen werden.")
            return

        stream_url, player_url = self._resolve_stream_url(url, main_page_html)
        if not stream_url:
            self.notify_error("Kein Stream gefunden.")
            return

        xbmc.log(f"{_LOG}: Stream URL resolved: {stream_url[:150]}", xbmc.LOGINFO)

        proxy_headers = {
            "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/145.0.0.0 Safari/537.36"
            ),
            "Accept": "*/*",
            "Referer": "https://nhplayer.com/",
            "Origin": "https://nhplayer.com",
            "Sec-Fetch-Site": "cross-site",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Dest": "video",
            "Accept-Encoding": "identity",
            "Accept-Language": "en-US,en;q=0.9",
            "Connection": "keep-alive",
        }

        try:
            if self._probe_curl_cffi(stream_url, proxy_headers):
                if self._play_via_curl_cffi_proxy(stream_url, proxy_headers):
                    return

            if self._probe_cdn(stream_url, proxy_headers):
                self._play_via_proxy(stream_url, proxy_headers)
                return

            xbmc.log(f"{_LOG}: urllib probe blocked, trying cloudscraper proxy before Kodi direct playback", xbmc.LOGINFO)
            if self._probe_cloudscraper(stream_url, proxy_headers):
                if self._play_via_cloudscraper_proxy(stream_url, proxy_headers):
                    return

            if self._play_via_cloudscraper_proxy(stream_url, proxy_headers):
                return

            xbmc.log(f"{_LOG}: cloudscraper proxy unavailable, trying Kodi direct playback", xbmc.LOGINFO)
            self._play_direct_kodi(stream_url, proxy_headers)
        except Exception as exc:
            xbmc.log(f"{_LOG}: primary playback strategy failed: {exc}", xbmc.LOGERROR)
            if not self._play_via_cloudscraper_proxy(stream_url, proxy_headers):
                self.notify_error(f"Wiedergabe fehlgeschlagen: {exc}")

    def select_sort(self, original_url=None):
        try:
            current_idx = int(self.addon.getSetting(f"{self.name.lower()}_sort_by") or "0")
        except Exception:
            current_idx = 0

        if not (0 <= current_idx < len(self.sort_options)):
            current_idx = 0

        dialog = xbmcgui.Dialog()
        idx = dialog.select("Sort by...", self.sort_options, preselect=current_idx)
        if idx != -1:
            self.addon.setSetting(f"{self.name.lower()}_sort_by", str(idx))
            xbmc.executebuiltin("Container.Refresh")

    def notify_error(self, msg):
        xbmcgui.Dialog().notification("Hanime", msg, xbmcgui.NOTIFICATION_ERROR, 3000)

    def notify_info(self, msg):
        xbmcgui.Dialog().notification("Hanime", msg, xbmcgui.NOTIFICATION_INFO, 3000)
