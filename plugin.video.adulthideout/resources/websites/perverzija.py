import html
import glob
import os
import re
import subprocess
import sys
import urllib.parse

import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin

from resources.lib.base_website import BaseWebsite

try:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    vendor_path = os.path.abspath(os.path.join(current_dir, "..", "lib", "vendor"))
    if os.path.exists(vendor_path) and vendor_path not in sys.path:
        sys.path.insert(0, vendor_path)
except Exception:
    pass

try:
    from curl_cffi import requests as curl_requests
    _HAS_CURL = True
except Exception:
    curl_requests = None
    _HAS_CURL = False

if not _HAS_CURL:
    try:
        import glob

        local_app_data = os.environ.get("LOCALAPPDATA", "")
        pattern = os.path.join(local_app_data, "Programs", "Python", "Python*", "Lib", "site-packages")
        for site_packages in sorted(glob.glob(pattern), reverse=True):
            if os.path.isdir(site_packages) and site_packages not in sys.path:
                sys.path.append(site_packages)
        from curl_cffi import requests as curl_requests

        _HAS_CURL = True
    except Exception:
        curl_requests = None
        _HAS_CURL = False

try:
    import cloudscraper
    _HAS_CF = True
except Exception:
    cloudscraper = None
    _HAS_CF = False


class PerverzijaWebsite(BaseWebsite):
    def __init__(self, addon_handle):
        addon = xbmcaddon.Addon()
        super().__init__(
            name="perverzija",
            base_url="https://tube.perverzija.com/",
            search_url="https://tube.perverzija.com/?s={}",
            addon_handle=addon_handle,
            addon=addon,
        )
        self.user_agent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/123.0.0.0 Safari/537.36"
        )
        self.session = self._build_session()

    def _find_system_python(self):
        local_app_data = os.environ.get("LOCALAPPDATA", "")
        pattern = os.path.join(local_app_data, "Programs", "Python", "Python*", "python.exe")
        for candidate in sorted(glob.glob(pattern), reverse=True):
            if os.path.isfile(candidate):
                return candidate
        return "python"

    def _build_session(self):
        if _HAS_CURL:
            return curl_requests.Session(impersonate="chrome123", verify=False)
        if _HAS_CF:
            return cloudscraper.create_scraper(browser={"browser": "chrome", "platform": "windows", "desktop": True})
        raise RuntimeError("No Cloudflare-capable backend available")

    def _request_via_system_python(self, url, referer=None, accept=None):
        script = r"""
import glob
import os
import sys

url = sys.argv[1]
user_agent = sys.argv[2]
referer = sys.argv[3]
accept = sys.argv[4]
vendor_path = sys.argv[5]
if os.path.isdir(vendor_path) and vendor_path not in sys.path:
    sys.path.insert(0, vendor_path)
local_app_data = os.environ.get("LOCALAPPDATA", "")
pattern = os.path.join(local_app_data, "Programs", "Python", "Python*", "Lib", "site-packages")
for site_packages in sorted(glob.glob(pattern), reverse=True):
    if os.path.isdir(site_packages) and site_packages not in sys.path:
        sys.path.append(site_packages)
try:
    from curl_cffi import requests as curl_requests
except Exception:
    curl_requests = None
try:
    import cloudscraper
except Exception:
    cloudscraper = None
import requests
session = None
if curl_requests is not None:
    try:
        session = curl_requests.Session(impersonate="chrome123", verify=False)
    except Exception:
        session = None
if session is None and cloudscraper is not None:
    try:
        session = cloudscraper.create_scraper(browser={"custom": user_agent})
    except Exception:
        session = None
if session is None:
    session = requests.Session()
headers = {"User-Agent": user_agent, "Accept": accept, "Accept-Language": "en-US,en;q=0.9"}
if referer:
    headers["Referer"] = referer
response = session.get(url, headers=headers, timeout=30)
response.raise_for_status()
body = response.text if isinstance(response.text, str) else response.content.decode("utf-8", "replace")
sys.stdout.write(body)
"""

        command = [
            self._find_system_python(),
            "-c",
            script,
            url,
            self.user_agent,
            referer or "",
            accept or "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "lib", "vendor")),
        ]

        startupinfo = None
        creationflags = 0
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

        completed = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=45,
            startupinfo=startupinfo,
            creationflags=creationflags,
        )
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr.strip() or "system fetch failed")
        return completed.stdout

    def _request(self, url, referer=None):
        headers = {"User-Agent": self.user_agent}
        if referer:
            headers["Referer"] = referer
        try:
            response = self.session.get(url, headers=headers, timeout=30)
            if response.status_code == 200:
                return response.text
            xbmc.log(
                f"[AdultHideout][Pervrezija] Primary fetch HTTP {response.status_code} for {url}. Trying system helper.",
                xbmc.LOGWARNING,
            )
        except Exception as exc:
            xbmc.log(f"[AdultHideout][Pervrezija] Primary fetch failed for {url}: {exc}", xbmc.LOGWARNING)

        return self._request_via_system_python(url, referer=referer)

    def _extract_blocks(self, html_content):
        return re.findall(
            r'(<div id="post-\d+"[^>]*class="[^"]*video-item[^"]*"[\s\S]+?<div class="clearfix"></div>\s*</div>)',
            html_content,
            re.I,
        )

    def _parse_listing(self, html_content):
        items = []
        seen = set()
        for block in self._extract_blocks(html_content):
            title_match = re.search(
                r'<h[23]><a href="(https://tube\.perverzija\.com/[^"]+/)"[^>]*title="([^"]+)"',
                block,
                re.I,
            )
            img_match = re.search(r'<img[^>]+src="([^"]+)"', block, re.I)
            dur_match = re.search(r'<span class="rating-bar[^"]*time_dur">([^<]+)</span>', block, re.I)

            if not title_match:
                continue

            video_url = html.unescape(title_match.group(1))
            if any(skip in video_url for skip in ("/tag/", "/studio/", "/featured-scenes/")):
                continue
            if video_url in seen:
                continue
            seen.add(video_url)

            title = html.unescape(title_match.group(2)).replace("&#8211;", "-").strip()
            thumb = img_match.group(1) if img_match else self.icon
            duration = dur_match.group(1).strip() if dur_match else ""

            items.append({"title": title, "url": video_url, "thumb": thumb, "duration": duration})

        if items:
            return items

        for match in re.finditer(
            r'<div id="post-\d+"[^>]*class="[^"]*video-item[^"]*"[\s\S]+?'
            r'<img[^>]+src="([^"]+)"[\s\S]+?'
            r'<h3><a href="(https://tube\.perverzija\.com/[^"]+/)"[^>]*title="([^"]+)"',
            html_content,
            re.I,
        ):
            thumb = match.group(1)
            video_url = html.unescape(match.group(2))
            if any(skip in video_url for skip in ("/tag/", "/studio/", "/featured-scenes/")):
                continue
            if video_url in seen:
                continue
            seen.add(video_url)
            title = html.unescape(match.group(3)).replace("&#8211;", "-").strip()
            items.append({"title": title, "url": video_url, "thumb": thumb, "duration": ""})

        return items

    def _extract_next_page(self, html_content):
        match = re.search(r'<a[^>]+(?:class="nextpostslink"|rel="next")[^>]+href="([^"]+)"', html_content, re.I)
        return html.unescape(match.group(1)) if match else None

    def process_content(self, url):
        if not url or url == "BOOTSTRAP":
            url = self.base_url

        html_content = self._request(url)
        self.add_dir("[COLOR blue]Search[/COLOR]", "", 5, self.icons["search"])
        self.add_dir("[COLOR blue]Categories[/COLOR]", "TAGS", 8, self.icons["categories"])

        for item in self._parse_listing(html_content):
            info = {"title": item["title"], "mediatype": "video"}
            if item["duration"]:
                info["duration"] = self.convert_duration(item["duration"])
            self.add_link(item["title"], item["url"], 4, item["thumb"], self.fanart, info_labels=info)

        next_page = self._extract_next_page(html_content)
        if next_page:
            self.add_dir("[COLOR blue]Next Page >>>>[/COLOR]", next_page, 2, self.icons["default"], self.fanart)
        self.end_directory()

    def process_categories(self, url):
        html_content = self._request(self.base_url)
        seen = set()
        for target, label in re.findall(r'href="(https://tube\.perverzija\.com/tag/[^"]+/)"[^>]*>([^<]+)</a>', html_content, re.I):
            target = html.unescape(target)
            label = html.unescape(label).strip()
            if not label or target in seen:
                continue
            seen.add(target)
            self.add_dir(label, target, 2, self.icons["default"], self.fanart)
        self.end_directory()

    def _extract_iframe(self, page_html):
        match = re.search(r'<iframe[^>]+src="(https://[^"]*xtremestream[^"]+player/index\.php\?data=[^"]+)"', page_html, re.I)
        return html.unescape(match.group(1)) if match else None

    def _extract_best_variant_url(self, master_url, referer):
        master_text = self._request(master_url, referer=referer)
        best_url = None
        best_score = -1
        lines = [line.strip() for line in master_text.splitlines() if line.strip()]
        for idx, line in enumerate(lines):
            if not line.startswith("#EXT-X-STREAM-INF:"):
                continue
            if idx + 1 >= len(lines):
                continue
            candidate = urllib.parse.urljoin(master_url, lines[idx + 1])
            q_match = re.search(r"[?&]q=(\d+)", candidate)
            score = int(q_match.group(1)) if q_match else 0
            bw_match = re.search(r"BANDWIDTH=(\d+)", line)
            if bw_match:
                score = max(score, int(bw_match.group(1)) // 1000)
            if score > best_score:
                best_score = score
                best_url = candidate
        return best_url or master_url

    def _resolve_stream(self, page_url):
        page_html = self._request(page_url)
        iframe_url = self._extract_iframe(page_html)
        if not iframe_url:
            return None, None

        iframe_html = self._request(iframe_url, referer=page_url)
        loader_match = re.search(r"var m3u8_loader_url = `([^`]+)`;", iframe_html)
        video_match = re.search(r"var video_id = `([^`]+)`;", iframe_html)
        if not loader_match or not video_match:
            return None, None

        master_url = f"{loader_match.group(1)}{video_match.group(1)}"
        variant_url = self._extract_best_variant_url(master_url, iframe_url)
        return variant_url, iframe_url

    def play_video(self, url):
        stream_url, iframe_url = self._resolve_stream(url)
        if not stream_url:
            self.notify_error("Could not resolve video URL")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return

        headers = urllib.parse.urlencode({"User-Agent": self.user_agent, "Referer": iframe_url})
        list_item = xbmcgui.ListItem(path=f"{stream_url}|{headers}")
        list_item.setProperty("IsPlayable", "true")
        list_item.setMimeType("application/vnd.apple.mpegurl")
        list_item.setContentLookup(False)
        xbmcplugin.setResolvedUrl(self.addon_handle, True, list_item)

    def search(self, query):
        if query:
            self.process_content(self.search_url.format(urllib.parse.quote_plus(query)))
