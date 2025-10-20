# -*- coding: utf-8 -*-
import re
import html
import urllib.parse
import urllib.request
import gzip
import io
import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon
import sys
import os
import time

from resources.lib.base_website import BaseWebsite
from resources.lib.resolvers import resolver

sys.path.append(
    os.path.join(
        xbmcaddon.Addon().getAddonInfo("path"),
        "resources", "lib", "vendor", "cloudscraper"
    )
)
try:
    import cloudscraper
    _HAS_CF = True
except Exception:
    _HAS_CF = False

try:
    from bs4 import BeautifulSoup
    _HAS_BS4 = True
except Exception:
    _HAS_BS4 = False


class freeomovie(BaseWebsite):
    def __init__(self, addon_handle):
        addon = xbmcaddon.Addon()
        name = "freeomovie"
        base_url = "https://www.freeomovie.to/"
        search_url = "https://www.freeomovie.to/?s={}"
        super(freeomovie, self).__init__(name, base_url, search_url, addon_handle, addon=addon)

        self._headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/126.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,de;q=0.8",
            "Referer": self.base_url,
        }

    def _http_get(self, url, headers=None, retries=2, timeout=15):
        headers = headers or self._headers
        if _HAS_CF:
            try:
                scraper = cloudscraper.create_scraper(
                    browser={"browser": "chrome", "platform": "windows", "mobile": False}
                )
                response = scraper.get(url, headers=headers, timeout=timeout)
                if response.status_code == 200:
                    return response.text
            except Exception as e:
                xbmc.log("[freeomovie] cloudscraper failed: {}".format(e), xbmc.LOGWARNING)
        
        req = urllib.request.Request(url, headers=headers)
        attempt = 0
        while attempt <= retries:
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    data = resp.read()
                    if resp.info().get('Content-Encoding') == 'gzip':
                        buf = io.BytesIO(data)
                        with gzip.GzipFile(fileobj=buf) as f:
                            data = f.read()
                    return data.decode('utf-8', errors='replace')
            except Exception as e:
                xbmc.log("[freeomovie] urllib failed ({}/{}): {}".format(attempt+1, retries, e), xbmc.LOGWARNING)
                attempt += 1
        return ""

    def process_content(self, url):
        self.add_dir('[COLOR blue]Search…[/COLOR]', '', 5, self.icons['search'])

        html_text = self._http_get(url or self.base_url)
        if not html_text:
            self.notify_error("Seite konnte nicht geladen werden.")
            xbmcplugin.endOfDirectory(self.addon_handle)
            return

        items = self._parse_listing(html_text)
        if not items:
            self.notify_info("Keine Videos gefunden.")
        else:
            for item in items:
                title = html.unescape(item.get("title", "Video")).strip()
                thumb = self._normalize_thumb(item.get("thumb", ""))
                detail_url = urllib.parse.urljoin(self.base_url, item.get("url", ""))

                info_labels = {"title": title}
                self.add_link(title, detail_url, 4, thumb, self.fanart, info_labels=info_labels)

        next_url = self._find_next_page(html_text, url or self.base_url)
        if next_url:
            self.add_dir("[COLOR skyblue]Next Page »[/COLOR]", next_url, 2, self.icon)

        self.end_directory()

    def play_video(self, url):
        start_time = time.time()
        html_text = self._http_get(url)
        if not html_text:
            self.notify_error("Detailseite konnte nicht geladen werden.")
            return

        iframe_urls = self._extract_iframes(html_text, base=url)

        xbmcgui.Dialog().notification("DEBUG", "Hoster gefunden: {}".format(len(iframe_urls)), xbmcgui.NOTIFICATION_INFO, 3000)
        
        if not iframe_urls:
            self.notify_error("Keine Hoster-Links gefunden.")
            return

        try:
            autoplay_enabled = self.addon.getSettingBool('freeomovie_autoplay_hoster')
        except AttributeError:
             autoplay_enabled = self.addon.getSetting('freeomovie_autoplay_hoster') == 'true'

        stream_url = ""
        headers = {}
        resolved_host_display = ""
        if autoplay_enabled:
            xbmcgui.Dialog().notification("Autoplay", "Versuche {} Hoster...".format(len(iframe_urls)), xbmcgui.NOTIFICATION_INFO, 2500)
            
            for embed_url in iframe_urls:
                try:
                    host = urllib.parse.urlparse(embed_url).netloc
                    host_display = host.replace("www.", "")
                    xbmc.log("[AdultHideout][freeomovie] Autoplay versucht: {}".format(host_display), xbmc.LOGINFO)

                    temp_url, temp_headers = resolver.resolve(embed_url, referer=url, headers=self._headers)

                    if temp_url:
                        xbmc.log("[AdultHideout][freeomovie] Autoplay Erfolg bei: {}".format(host_display), xbmc.LOGINFO)
                        stream_url = temp_url
                        headers = temp_headers
                        resolved_host_display = host_display
                        break 
                
                except Exception as e:
                    xbmc.log("[AdultHideout][freeomovie] Autoplay Hoster fehlgeschlagen: {} ({})".format(host_display, e), xbmc.LOGWARNING)

            if not stream_url:
                self.notify_error("Autoplay: Keiner der {} Hoster konnte aufgelöst werden.".format(len(iframe_urls)))
                return

        else:
            embed_url = ""

            if len(iframe_urls) == 1:
                embed_url = iframe_urls[0]
            else:
                host_names = []
                for u in iframe_urls:
                    try:
                        host = urllib.parse.urlparse(u).netloc.replace("www.", "")
                        host_names.append("[COLOR skyblue]{}[/COLOR]".format(host))
                    except:
                        host_names.append(u)

                dialog = xbmcgui.Dialog()
                selection = dialog.select("Hoster auswählen", host_names) 

                if selection == -1:
                    return
                
                embed_url = iframe_urls[selection]

            host = urllib.parse.urlparse(embed_url).netloc
            resolved_host_display = host.replace("www.", "")
            xbmc.log("[AdultHideout][freeomovie] Using resolver for host: {}".format(resolved_host_display), xbmc.LOGINFO)
            xbmcgui.Dialog().notification("Freeomovie", "Versuche Hoster: {}".format(resolved_host_display), xbmcgui.NOTIFICATION_INFO, 3000)

            try:
                 stream_url, headers = resolver.resolve(embed_url, referer=url, headers=self._headers)
            except Exception as e:
                 xbmc.log("[AdultHideout][freeomovie] Manueller Resolve fehlgeschlagen: {}".format(e), xbmc.LOGERROR)
                 self.notify_error("Stream von {} konnte nicht geladen werden.".format(resolved_host_display))
                 return

        if stream_url:
            load_time = round(time.time() - start_time, 2)
            xbmc.log("[AdultHideout][freeomovie] Resolved {} in {}s -> {}".format(resolved_host_display, load_time, stream_url), xbmc.LOGINFO)
            xbmcgui.Dialog().notification("Video geladen", "{} ({}s)".format(resolved_host_display, load_time), xbmcgui.NOTIFICATION_INFO, 4000)

            li = xbmcgui.ListItem(path=self._append_headers(stream_url, headers))
            li.setProperty('IsPlayable', 'true')
            xbmcplugin.setResolvedUrl(self.addon_handle, True, li)
            return

        if not autoplay_enabled:
             self.notify_error("Stream von {} konnte nicht geladen werden.".format(resolved_host_display))

    def _parse_listing(self, html_text):
        items = []
        if _HAS_BS4:
            try:
                soup = BeautifulSoup(html_text, "html.parser")
                for box in soup.select("div.box a[href]"):
                    href = box.get("href")
                    if not href or "/category/" in href:
                        continue
                    title_tag = box.find("h2")
                    img_tag = box.find("img")
                    title = title_tag.get_text(strip=True) if title_tag else box.get("title", "")
                    thumb = ""
                    if img_tag:
                        thumb = img_tag.get("data-src") or img_tag.get("src") or ""
                    if href and title:
                        items.append({"title": title, "url": href, "thumb": thumb})
                if items:
                    return items
            except Exception as e:
                xbmc.log("[freeomovie] parse failed: {}".format(e), xbmc.LOGWARNING)

        pattern = re.compile(
            r'<a href="([^"]+)".*?(?:data-src|src)="([^"]+)".*?<h2[^>]*>([^<]+)</h2>',
            re.DOTALL | re.IGNORECASE
        )
        for m in pattern.finditer(html_text):
            url, thumb, title = m.groups()
            items.append({"title": title.strip(), "url": url, "thumb": thumb})
        return items

    def _extract_iframes(self, html_text, base):
        return re.findall(r'<li><a href="([^"]+)"[^>]+class="url-a-btn"', html_text, re.IGNORECASE)

    def _normalize_thumb(self, thumb):
        if not thumb:
            return self.icon
        if thumb.startswith("//"):
            thumb = "https:" + thumb
        elif thumb.startswith("/"):
            thumb = urllib.parse.urljoin(self.base_url, thumb)
        return thumb

    def _find_next_page(self, html_text, current_url):
        m = re.search(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(?:Next|»|›)</a>', html_text, re.IGNORECASE)
        if m:
            return urllib.parse.urljoin(current_url, m.group(1))

        parsed = urllib.parse.urlparse(current_url)
        qs = urllib.parse.parse_qs(parsed.query)
        if "s" in qs:
            query = qs["s"][0]
            m_page = re.search(r"/page/(\d+)/", parsed.path)
            next_page = (int(m_page.group(1)) + 1) if m_page else 2
            next_url = "{}://{}/page/{}/?s={}".format(
                parsed.scheme, parsed.netloc, next_page, urllib.parse.quote_plus(query)
            )
            return next_url

        if current_url.rstrip("/") == self.base_url.rstrip("/"):
            return urllib.parse.urljoin(self.base_url, "page/2/")
        return None

    def _append_headers(self, url, headers):
        if not headers:
            return url
        parts = ["{}={}".format(k, urllib.parse.quote(v)) for k, v in headers.items()]
        return url + "|" + "&".join(parts)