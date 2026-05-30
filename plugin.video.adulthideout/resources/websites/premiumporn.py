#!/usr/bin/env python
# -*- coding: utf-8 -*-

import base64
import html
import json
import re
import sys
import warnings
import urllib.error
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar

import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin

from resources.lib.base_website import BaseWebsite

from resources.lib.vendor import byse_crypto


class PremiumPornWebsite(BaseWebsite):
    def __init__(self, addon_handle):
        addon = xbmcaddon.Addon()
        name = "premiumporn"
        base_url = "https://premiumporn.org/"
        search_url = "https://premiumporn.org/?s={}"
        super(PremiumPornWebsite, self).__init__(
            name, base_url, search_url, addon_handle, addon=addon
        )
        self.label = "PremiumPorn"
        self.sort_options = ["Latest Uploads", "Most Viewed", "Top Rated"]
        self.sort_values = ["date", "views", "liked"]
        
        import ssl
        try:
            ctx = ssl._create_unverified_context()
        except AttributeError:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        https_handler = urllib.request.HTTPSHandler(context=ctx)
        
        self.cookie_jar = CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cookie_jar),
            https_handler
        )
        
        is_android = xbmc.getCondVisibility("System.Platform.Android")
        if is_android:
            user_agent = (
                "Mozilla/5.0 (Linux; Android 10; SM-G973F) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Mobile Safari/537.36"
            )
        else:
            user_agent = (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/126.0.0.0 Safari/537.36"
            )
            
        self.headers = {
            "User-Agent": user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Cookie": "rawx_age_gate_accepted=1",
        }

    def get_start_url_and_label(self):
        sort_value, sort_label = self._current_sort()
        if sort_value == "date":
            return self.base_url, self.label + " - " + sort_label
        return self.base_url + "video/?sort=" + sort_value, self.label + " - " + sort_label

    def _current_sort(self):
        try:
            idx = int(self.addon.getSetting("%s_sort_by" % self.name) or "0")
        except ValueError:
            idx = 0
        if idx < 0 or idx >= len(self.sort_values):
            idx = 0
        return self.sort_values[idx], self.sort_options[idx]

    def process_content(self, url):
        current_url = url if url and url != "BOOTSTRAP" else self.get_start_url_and_label()[0]
        context_menu = [
            (
                "Sort by...",
                "RunPlugin(%s?mode=7&action=select_sort&website=%s&original_url=%s)"
                % (sys.argv[0], self.name, urllib.parse.quote_plus(current_url)),
            )
        ]
        self.add_dir("[COLOR blue]Search[/COLOR]", "", 5, self.icons["search"])
        self.add_dir("[COLOR blue]Categories[/COLOR]", self.base_url + "categories/", 8, self.icons["categories"])

        page = self._http_get(current_url)
        if not page:
            self.notify_error("Failed to load page.")
            self.end_directory()
            return

        items = self._parse_listing(page)
        for item in items:
            self.add_link(
                item["title"],
                item["url"],
                4,
                item.get("thumb") or self.icon,
                self.fanart,
                context_menu,
                info_labels={"title": item["title"]},
            )

        if not items:
            self.notify_info("No videos found.")

        next_url = self._find_next_page(page)
        if next_url:
            self.add_dir("[COLOR blue]Next Page >>>>[/COLOR]", next_url, 2, self.icons["default"], self.fanart, context_menu)

        self.end_directory()

    def process_categories(self, url=None):
        page = self._http_get(url or (self.base_url + "categories/"))
        if not page:
            self.notify_error("Failed to load categories.")
            self.end_directory()
            return

        seen = set()
        for href, label in re.findall(
            r'<a[^>]+href=["\'](https://premiumporn\.org/(?!page/|tag/|actor/|video/|actors/|tags/|favorites/)[^"\']+/)["\'][^>]*>(.*?)</a>',
            page,
            re.IGNORECASE | re.DOTALL,
        ):
            title = self._clean_text(label)
            title = re.sub(r"\s+\d+\s+VIDEOS$", "", title, flags=re.IGNORECASE).strip()
            if not title or href in seen or title.lower() in ("home", "categories", "browse all"):
                continue
            seen.add(href)
            self.add_dir(title, href, 2, self.icons["categories"])

        next_url = self._find_next_page(page)
        if next_url and "/categories/" in next_url:
            self.add_dir("[COLOR blue]Next Page >>>>[/COLOR]", next_url, 8, self.icons["default"])

        self.end_directory()

    def play_video(self, url):
        self._log_playback("Starting playback: %s" % url)

        page = self._http_get(url, referer=self.base_url)
        self._log_playback("Video page length: %s" % len(page))
        iframe_url = self._extract_iframe(page)
        if not iframe_url:
            self._log_playback("No Byse iframe found on video page", xbmc.LOGERROR)
            self.notify_error("No Byse player found.")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem(path=url))
            return
        self._log_playback("Byse iframe: %s" % iframe_url)

        stream_url = self._resolve_byse_hls(iframe_url, url)
        if not stream_url:
            self._log_playback("Resolver returned no stream", xbmc.LOGERROR)
            self.notify_error("No playable stream found.")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem(path=url))
            return

        self._log_playback("Resolved HLS stream: %s" % stream_url[:160])
        li = xbmcgui.ListItem(path=stream_url)
        li.setProperty("IsPlayable", "true")
        li.setMimeType("application/vnd.apple.mpegurl")
        li.setContentLookup(False)
        has_inputstream = xbmc.getCondVisibility("System.HasAddon(inputstream.adaptive)")
        is_android = xbmc.getCondVisibility("System.Platform.Android")

        if has_inputstream:
            li.setProperty("inputstream", "inputstream.adaptive")
            li.setProperty("inputstream.adaptive.manifest_type", "hls")
        elif is_android:
            self._log_playback("InputStream Adaptive is missing or disabled on Android", xbmc.LOGERROR)
            lang = xbmc.getLanguage(0).lower()
            if "german" in lang or "deutsch" in lang:
                title = "[COLOR red]InputStream Adaptive fehlt[/COLOR]"
                msg = (
                    "Für das Abspielen unter Android wird die integrierte Kodi-Komponente 'InputStream Adaptive' benötigt.\n\n"
                    "Bitte aktivieren Sie diese in den Kodi-Einstellungen:\n"
                    "Einstellungen -> Addons -> Benutzer-Addons -> Videoplayer-InputStream -> InputStream Adaptive -> Aktivieren"
                )
            elif "spanish" in lang or "español" in lang or "espanol" in lang:
                title = "[COLOR red]Falta InputStream Adaptive[/COLOR]"
                msg = (
                    "Para la reproducción en Android, se requiere el componente integrado de Kodi 'InputStream Adaptive'.\n\n"
                    "Por favor, actívelo en la configuración de Kodi:\n"
                    "Ajustes -> Add-ons -> Mis add-ons -> InputStream de reproductor de vídeo -> InputStream Adaptive -> Activar"
                )
            elif "french" in lang or "français" in lang or "francais" in lang:
                title = "[COLOR red]InputStream Adaptive manquant[/COLOR]"
                msg = (
                    "Pour la lecture sur Android, le composant Kodi intégré 'InputStream Adaptive' est requis.\n\n"
                    "Veuillez l'activer dans vos paramètres Kodi:\n"
                    "Paramètres -> Extensions -> Mes extensions -> Lecteur vidéo InputStream -> InputStream Adaptive -> Activer"
                )
            else:
                title = "[COLOR red]InputStream Adaptive Missing[/COLOR]"
                msg = (
                    "For playback on Android, the built-in Kodi component 'InputStream Adaptive' is required.\n\n"
                    "Please enable it in your Kodi settings:\n"
                    "Settings -> Add-ons -> My add-ons -> VideoPlayer InputStream -> InputStream Adaptive -> Enable"
                )
            xbmcgui.Dialog().ok(title, msg)
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem(path=url))
            return

        xbmcplugin.setResolvedUrl(self.addon_handle, True, li)

    def search(self, query):
        if query:
            self.process_content(self.search_url.format(urllib.parse.quote_plus(query)))

    def select_sort(self, original_url=None):
        current_idx = 0
        try:
            current_idx = int(self.addon.getSetting("%s_sort_by" % self.name) or "0")
        except ValueError:
            current_idx = 0
        idx = xbmcgui.Dialog().select("Sort by...", self.sort_options, preselect=current_idx)
        if idx == -1:
            return
        self.addon.setSetting("%s_sort_by" % self.name, str(idx))
        sort_value = self.sort_values[idx]
        target = self.base_url if sort_value == "date" else self.base_url + "video/?sort=" + sort_value
        xbmc.executebuiltin(
            "Container.Update(%s?mode=2&url=%s&website=%s,replace)"
            % (sys.argv[0], urllib.parse.quote_plus(target), self.name)
        )

    def _http_get(self, url, referer=None, timeout=25):
        target = urllib.parse.urljoin(self.base_url, url or self.base_url)
        headers = self.headers.copy()
        headers["Referer"] = referer or self.base_url
        try:
            request = urllib.request.Request(target, headers=headers)
            with self.opener.open(request, timeout=timeout) as response:
                return response.read().decode("utf-8", errors="ignore")
        except urllib.error.HTTPError as exc:
            self.logger.warning("HTTP %s while loading %s", exc.code, target)
        except Exception as exc:
            self.logger.warning("Request failed for %s: %s", target, exc)
        return ""

    def _parse_listing(self, page):
        items = []
        seen = set()
        for block in re.findall(r"<article\b[^>]*class=[\"'][^\"']*v-card[^\"']*[\"'][^>]*>.*?</article>", page, re.IGNORECASE | re.DOTALL):
            link = self._match_first(block, r'<a[^>]+href=["\']([^"\']+)["\'][^>]*class=["\'][^"\']*vc-thumb-wrap')
            if not link:
                link = self._match_first(block, r'<a[^>]+href=["\']([^"\']+)["\']')
            href = urllib.parse.urljoin(self.base_url, html.unescape(link))
            if href in seen or not href.startswith(self.base_url):
                continue
            seen.add(href)
            title = self._match_first(block, r'<a[^>]+class=["\'][^"\']*vc-title[^"\']*["\'][^>]*>(.*?)</a>')
            if not title:
                title = self._match_first(block, r'<img[^>]+alt=["\']([^"\']+)')
            duration = self._match_first(block, r'<div[^>]+class=["\'][^"\']*vc-dur[^"\']*["\'][^>]*>(.*?)</div>')
            thumb = self._match_first(block, r'<img[^>]+(?:data-src|src)=["\']([^"\']+)')
            clean_title = self._clean_text(title)
            if duration:
                clean_title += " [COLOR lime](%s)[/COLOR]" % self._clean_text(duration)
            if clean_title:
                items.append({
                    "title": clean_title,
                    "url": href,
                    "thumb": urllib.parse.urljoin(self.base_url, html.unescape(thumb or "")),
                })
        return items

    def _find_next_page(self, page):
        patterns = (
            r'<a[^>]+class=["\'][^"\']*next[^"\']*["\'][^>]+href=["\']([^"\']+)["\']',
            r'<link[^>]+rel=["\']next["\'][^>]+href=["\']([^"\']+)["\']',
        )
        for pattern in patterns:
            match = re.search(pattern, page, re.IGNORECASE)
            if match:
                return urllib.parse.urljoin(self.base_url, html.unescape(match.group(1)))
        return None

    def _extract_iframe(self, page):
        match = re.search(r'<iframe[^>]+src=["\']([^"\']+)["\']', page or "", re.IGNORECASE)
        if match:
            return html.unescape(match.group(1))
        match = re.search(r'"embedUrl"\s*:\s*"([^"]+)"', page or "", re.IGNORECASE)
        return html.unescape(match.group(1).replace("\\/", "/")) if match else ""

    def _resolve_byse_hls(self, iframe_url, page_url):
        parsed = urllib.parse.urlparse(iframe_url)
        code_match = re.search(r"/e/([^/]+)", parsed.path)
        if not code_match:
            self._log_playback("Could not extract Byse code from iframe", xbmc.LOGERROR)
            return ""
        code = code_match.group(1)
        self._log_playback("Byse code: %s" % code)
        details = self._byse_json(urllib.parse.urlunparse(parsed._replace(path="/api/videos/%s/embed/details" % code, query="")), page_url)
        frame_url = details.get("embed_frame_url") or iframe_url
        self._log_playback("Byse frame URL: %s" % frame_url)
        frame = urllib.parse.urlparse(frame_url)
        api_base = "%s://%s" % (frame.scheme, frame.netloc)
        frame_referer = frame_url

        fp = self._byse_fingerprint(api_base, frame_referer)
        if not fp:
            self._log_playback("Fingerprint challenge failed", xbmc.LOGERROR)
            return ""
        self._log_playback("Fingerprint token received")
        headers = {
            "User-Agent": self.headers["User-Agent"],
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Referer": frame_referer,
            "X-Embed-Origin": "premiumporn.org",
            "X-Embed-Referer": self.base_url,
            "X-Embed-Parent": iframe_url,
        }
        playback = self._json_request(
            api_base + "/api/videos/%s/embed/playback" % code,
            headers,
            json.dumps({"fingerprint": fp}).encode("utf-8"),
        )
        if not playback:
            self._log_playback("Playback API returned no JSON", xbmc.LOGERROR)
            return ""
        payload = self._decrypt_byse_payload(playback.get("playback") or {})
        sources = payload.get("sources") or []
        self._log_playback("Playback sources: %s" % len(sources))
        sources = sorted(sources, key=lambda item: item.get("height") or 0, reverse=True)
        for source in sources:
            stream_url = source.get("url") or ""
            if stream_url:
                return stream_url
        return ""

    def _byse_fingerprint(self, api_base, referer):
        challenge = self._json_request(
            api_base + "/api/videos/access/challenge",
            {"User-Agent": self.headers["User-Agent"], "Referer": referer, "Accept": "application/json"},
            b"",
        )
        nonce = challenge.get("nonce") or ""
        challenge_id = challenge.get("challenge_id") or ""
        if not nonce or not challenge_id:
            return {}

        private_key, public_key_point = byse_crypto.generate_keypair()
        pub_x = public_key_point[0].to_bytes(32, "big")
        pub_y = public_key_point[1].to_bytes(32, "big")

        r, s = byse_crypto.sign_challenge(nonce.encode("utf-8"), private_key)
        signature_bytes = r.to_bytes(32, "big") + s.to_bytes(32, "big")

        is_android = xbmc.getCondVisibility("System.Platform.Android")
        if is_android:
            client_data = {
                "user_agent": self.headers["User-Agent"],
                "architecture": "arm64",
                "bitness": "64",
                "platform": "Android",
                "platform_version": "10",
                "model": "SM-G973F",
                "ua_full_version": "124.0.0.0",
                "brand_full_versions": [],
                "pixel_ratio": 3,
                "screen_width": 1080,
                "screen_height": 2280,
                "color_depth": 24,
                "languages": ["en-US", "en"],
                "timezone": "Europe/Berlin",
                "hardware_concurrency": 8,
                "device_memory": 8,
                "max_touch_points": 5,
                "webdriver": False,
            }
        else:
            client_data = {
                "user_agent": self.headers["User-Agent"],
                "architecture": "x86",
                "bitness": "64",
                "platform": "Windows",
                "platform_version": "15.0.0",
                "model": "",
                "ua_full_version": "126.0.0.0",
                "brand_full_versions": [],
                "pixel_ratio": 1,
                "screen_width": 1280,
                "screen_height": 720,
                "color_depth": 24,
                "languages": ["en"],
                "timezone": "Europe/Berlin",
                "hardware_concurrency": 8,
                "device_memory": 8,
                "max_touch_points": 0,
                "webdriver": False,
            }

        body = {
            "viewer_id": "",
            "device_id": "",
            "challenge_id": challenge_id,
            "nonce": nonce,
            "signature": self._b64u(signature_bytes),
            "public_key": {
                "crv": "P-256",
                "ext": True,
                "key_ops": ["verify"],
                "kty": "EC",
                "x": self._b64u(pub_x),
                "y": self._b64u(pub_y),
            },
            "client": client_data,
        }
        attest = self._json_request(
            api_base + "/api/videos/access/attest",
            {"User-Agent": self.headers["User-Agent"], "Referer": referer, "Accept": "application/json", "Content-Type": "application/json"},
            json.dumps(body).encode("utf-8"),
        )
        if not attest.get("token"):
            return {}
        return {
            "token": attest.get("token"),
            "viewer_id": attest.get("viewer_id"),
            "device_id": attest.get("device_id"),
            "confidence": attest.get("confidence"),
        }

    def _byse_json(self, url, referer):
        return self._json_request(
            url,
            {
                "User-Agent": self.headers["User-Agent"],
                "Accept": "application/json",
                "Referer": referer,
                "X-Embed-Origin": "premiumporn.org",
                "X-Embed-Referer": self.base_url,
            },
        )

    def _json_request(self, url, headers, data=None):
        try:
            request = urllib.request.Request(url, headers=headers, data=data)
            if data is not None:
                request.get_method = lambda: "POST"
            with self.opener.open(request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8", errors="ignore"))
        except urllib.error.HTTPError as exc:
            try:
                body = exc.read().decode("utf-8", errors="ignore")
            except Exception:
                body = ""
            self._log_playback("JSON HTTP %s for %s: %s" % (exc.code, url, body[:300]), xbmc.LOGERROR)
        except Exception as exc:
            self._log_playback("JSON request failed for %s: %s" % (url, exc), xbmc.LOGERROR)
        return {}

    def _decrypt_byse_payload(self, encrypted):
        key_parts = encrypted.get("key_parts") or []
        version = str(encrypted.get("version") or "")
        selected = []
        if version.isdigit():
            number = int(version)
            for index in (number, 31 - number):
                if 1 <= index <= len(key_parts):
                    selected.append(key_parts[index - 1])
        if not selected:
            selected = key_parts
        key = b"".join(self._b64d(part) for part in selected)
        iv = self._b64d(encrypted.get("iv") or "")
        payload = self._b64d(encrypted.get("payload") or "")

        ciphertext = payload[:-16]
        tag = payload[-16:]
        decoded = byse_crypto.gcm_decrypt(key, iv, ciphertext, tag, b"")
        return json.loads(decoded.decode("utf-8"))

    def _b64u(self, value):
        return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")

    def _b64d(self, value):
        value = value or ""
        return base64.urlsafe_b64decode(value + "=" * ((4 - len(value) % 4) % 4))

    def _match_first(self, text, pattern):
        match = re.search(pattern, text or "", re.IGNORECASE | re.DOTALL)
        return html.unescape(match.group(1)) if match else ""

    def _clean_text(self, value):
        value = html.unescape(value or "")
        value = re.sub(r"<[^>]+>", " ", value)
        value = re.sub(r"\s+", " ", value)
        return value.strip()

    def _log_playback(self, message, level=xbmc.LOGINFO):
        xbmc.log("[AdultHideout][PremiumPorn] %s" % message, level)
