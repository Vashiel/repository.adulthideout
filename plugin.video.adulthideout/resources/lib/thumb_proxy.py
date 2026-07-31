# -*- coding: utf-8 -*-
"""Small local proxy for protected thumbnail requests."""

import os
import queue
import re
import sys
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import xbmc
import xbmcgui
import xbmcvfs


PORT_PROPERTY = "AdultHideout.ThumbProxyPort"
ALLOWED_HOSTS = frozenset((
    "85po.com",
    "www.85po.com",
    "i.pornktube.com",
    "cdn.pornve.com",
    "st.4kporn.xxx",
    "hqpornero.com",
    "pornobae.com",
    "yespornpleasexxx.com",
    "www.yespornpleasexxx.com",
    "euroxxx.net",
    "www.euroxxx.net",
    "images1.hdpornos.xxx",
    "images2.hdpornos.xxx",
    "hentai-moon.com",
    "www.hentai-moon.com",
    "cdn.javmiku.com",
    "t.aki-h.com",
    "watchhentai.net",
    "yourdailypornvideos.ws",
    "tickle.porn",
    "www.tickle.porn",
    "giantess.porn",
    "www.giantess.porn",
))
ALLOWED_PATH_PREFIXES = (
    "/_",
    "/contents/videos_screenshots/",
    "/avatar/",
    "/posts/",
    "/timthumb/",
    "/uploads/",
    "/wp-content/uploads/",
)
SESSION_COUNT = 4

_vendor = os.path.join(os.path.dirname(__file__), "vendor")
if os.path.isdir(_vendor) and _vendor not in sys.path:
    sys.path.insert(0, _vendor)

try:
    import requests
except Exception:
    requests = None
try:
    import cloudscraper
except Exception:
    cloudscraper = None

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)


def _log(message, level=xbmc.LOGINFO):
    xbmc.log("[AdultHideout][ThumbProxy] {}".format(message), level)


# Some artwork CDNs live on a subdomain gated by the domain-wide cf_clearance
# cookie that only gets minted by solving the Cloudflare challenge on the site's
# main origin. A listing fires dozens of thumbnails at once; letting every pooled
# session solve that challenge in parallel bursts the origin and trips CF's rate
# limit, so all of them fail. Instead serialize the warm-up behind a lock, do it
# once per origin, and share the resulting clearance cookies across every session.
_CLEARANCE = {}
_CLEARANCE_LOCK = threading.Lock()
_CLEARANCE_TTL = 240


def _origin(url):
    parsed = urllib.parse.urlsplit(url)
    return "{}://{}".format(parsed.scheme, parsed.netloc)


def _ensure_clearance(session, referer):
    """Give `session` a fresh Cloudflare clearance cookie for `referer`'s origin,
    warming the origin at most once per _CLEARANCE_TTL across all sessions."""
    origin = _origin(referer)
    with _CLEARANCE_LOCK:
        entry = _CLEARANCE.get(origin)
        if not entry or time.time() - entry[1] >= _CLEARANCE_TTL:
            try:
                session.get(origin + "/", headers={"User-Agent": UA}, timeout=(5, 15))
                entry = (session.cookies.get_dict(), time.time())
                _CLEARANCE[origin] = entry
            except Exception as exc:
                _log("clearance warm-up failed: {}".format(exc), xbmc.LOGWARNING)
                entry = None
        if entry:
            for name, value in entry[0].items():
                try:
                    session.cookies.set(name, value)
                except Exception:
                    pass


def _valid_image_url(url):
    try:
        parsed = urllib.parse.urlsplit(url)
        hostname = (parsed.hostname or "").lower()
        valid_path = parsed.path.startswith(ALLOWED_PATH_PREFIXES)
        return (
            parsed.scheme == "https"
            and hostname in ALLOWED_HOSTS
            and parsed.port in (None, 443)
            and valid_path
            and not parsed.username
            and not parsed.password
        )
    except (TypeError, ValueError):
        return False


def _valid_loadvid_segment(url):
    try:
        parsed = urllib.parse.urlsplit(url)
        hostname = (parsed.hostname or "").lower()
        return (
            parsed.scheme == "https"
            and (hostname == "stream-baby1.top" or hostname.endswith(".stream-baby1.top"))
            and parsed.port in (None, 443)
            and parsed.path.startswith("/user/")
            and not parsed.username
            and not parsed.password
        )
    except (TypeError, ValueError):
        return False


def _normalize_image(upstream, content_type):
    """Correct a CDN MIME lie so Kodi selects its WebP decoder."""
    body = upstream.content
    is_mislabeled_webp = (
        content_type == "image/jpeg" and body.startswith(b"RIFF") and b"WEBP" in body[:16]
    )
    return body, "image/webp" if is_mislabeled_webp else content_type


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    session_pool = None

    def log_message(self, fmt, *args):
        pass

    def do_HEAD(self):
        self._dispatch(send_body=False)

    def do_GET(self):
        self._dispatch(send_body=True)

    def _dispatch(self, send_body):
        parsed = urllib.parse.urlsplit(self.path)
        if parsed.path == "/thumb":
            self._serve_thumbnail(send_body)
        elif parsed.path.startswith("/loadvid/"):
            self._serve_loadvid_playlist(parsed.path, send_body)
        elif parsed.path.startswith("/loadvid-segment/") and parsed.path.endswith(".ts"):
            self._serve_loadvid_segment(parsed.path, send_body)
        else:
            self.send_error(404)

    def _serve_thumbnail(self, send_body):
        self.close_connection = True
        parsed = urllib.parse.urlsplit(self.path)
        params = dict(urllib.parse.parse_qsl(parsed.query))
        url = params.get("u")
        if parsed.path != "/thumb" or not _valid_image_url(url):
            self.send_error(400)
            return
        referer = params.get("r") or "https://www.85po.com/"

        try:
            session = self.session_pool.get(timeout=5)
        except queue.Empty:
            self.send_error(503)
            return

        response_started = False
        headers = {
            "User-Agent": UA,
            "Referer": referer,
            "Accept": "image/jpeg,image/png,image/*;q=0.8,*/*;q=0.5",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "identity",
        }
        try:
            upstream = session.get(url, headers=headers, timeout=(5, 15))
            content_type = upstream.headers.get("Content-Type", "").split(";", 1)[0].lower()
            if upstream.status_code != 200 or not content_type.startswith("image/"):
                # CDN gated by the domain-wide cf_clearance cookie: obtain it once
                # (serialized + shared across sessions), then retry the image.
                upstream.close()
                _ensure_clearance(session, referer)
                upstream = session.get(url, headers=headers, timeout=(5, 15))
                content_type = upstream.headers.get("Content-Type", "").split(";", 1)[0].lower()
            with upstream:
                if upstream.status_code != 200 or not content_type.startswith("image/"):
                    _log("upstream rejected thumbnail with status {}".format(upstream.status_code), xbmc.LOGWARNING)
                    self.send_error(502)
                    return

                body, content_type = _normalize_image(upstream, content_type)
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Connection", "close")
                self.end_headers()
                response_started = True

                if send_body:
                    self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as exc:
            _log("thumbnail fetch failed: {}".format(exc), xbmc.LOGWARNING)
            if not response_started:
                try:
                    self.send_error(502)
                except Exception:
                    pass
        finally:
            self.session_pool.put(session)

    def _serve_loadvid_playlist(self, request_path, send_body):
        filename = request_path.rsplit("/", 1)[-1]
        if not re.match(r"^adulthideout_loadvid_[0-9a-f]{16}\.m3u8$", filename):
            self.send_error(400)
            return
        path = os.path.join(xbmcvfs.translatePath("special://temp"), filename)
        try:
            with open(path, "r", encoding="utf-8") as handle:
                source = handle.read()
            lines = []
            segment_index = 0
            playlist_id = filename[len("adulthideout_loadvid_"):-len(".m3u8")]
            for line in source.splitlines():
                value = line.strip()
                if value and not value.startswith("#"):
                    if not _valid_loadvid_segment(value):
                        self.send_error(400)
                        return
                    value = "http://127.0.0.1:{}/loadvid-segment/{}/{}.ts".format(
                        self.server.server_address[1],
                        playlist_id,
                        segment_index,
                    )
                    segment_index += 1
                lines.append(value if value else line)
            body = ("\n".join(lines) + "\n").encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/vnd.apple.mpegurl")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "close")
            self.end_headers()
            if send_body:
                self.wfile.write(body)
        except FileNotFoundError:
            self.send_error(404)
        except Exception as exc:
            _log("Loadvid playlist failed: {}".format(exc), xbmc.LOGWARNING)
            self.send_error(502)

    def _serve_loadvid_segment(self, request_path, send_body):
        match = re.match(r"^/loadvid-segment/([0-9a-f]{16})/(\d+)\.ts$", request_path)
        if not match:
            self.send_error(400)
            return
        filename = "adulthideout_loadvid_{}.m3u8".format(match.group(1))
        path = os.path.join(xbmcvfs.translatePath("special://temp"), filename)
        try:
            with open(path, "r", encoding="utf-8") as handle:
                urls = [line.strip() for line in handle if line.strip() and not line.startswith("#")]
            url = urls[int(match.group(2))]
        except (FileNotFoundError, IndexError, ValueError):
            self.send_error(404)
            return
        if not _valid_loadvid_segment(url):
            self.send_error(400)
            return
        try:
            session = self.session_pool.get(timeout=5)
        except queue.Empty:
            self.send_error(503)
            return
        try:
            with session.get(
                url,
                headers={"User-Agent": UA, "Accept-Encoding": "identity"},
                timeout=(5, 20),
                stream=True,
            ) as upstream:
                if upstream.status_code != 200:
                    self.send_error(502)
                    return
                self.send_response(200)
                self.send_header("Content-Type", "video/mp2t")
                length = upstream.headers.get("Content-Length")
                if length:
                    self.send_header("Content-Length", length)
                self.send_header("Cache-Control", "no-store")
                self.send_header("Connection", "close")
                self.end_headers()
                if send_body:
                    for chunk in upstream.iter_content(64 * 1024):
                        if chunk:
                            self.wfile.write(chunk)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as exc:
            _log("Loadvid segment failed: {}".format(exc), xbmc.LOGWARNING)
        finally:
            self.session_pool.put(session)


def _create_session():
    if cloudscraper:
        try:
            return cloudscraper.create_scraper(browser={"custom": UA})
        except Exception as exc:
            _log("cloudscraper init failed: {}".format(exc), xbmc.LOGWARNING)
    return requests.Session() if requests else None


class ThumbProxy:
    def __init__(self):
        self.server = None
        self.thread = None
        self.sessions = []
        self.session_pool = queue.LifoQueue(maxsize=SESSION_COUNT)

    def start(self):
        window = xbmcgui.Window(10000)
        window.clearProperty(PORT_PROPERTY)

        for _ in range(SESSION_COUNT):
            session = _create_session()
            if session is None:
                break
            self.sessions.append(session)
            self.session_pool.put(session)

        if not self.sessions:
            _log("no HTTP session available; proxy disabled", xbmc.LOGWARNING)
            return False

        try:
            _Handler.session_pool = self.session_pool
            self.server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
            self.server.daemon_threads = True
            self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
            self.thread.start()
            window.setProperty(PORT_PROPERTY, str(self.server.server_address[1]))
            _log("listening on 127.0.0.1:{}".format(self.server.server_address[1]))
            return True
        except Exception as exc:
            _log("start failed: {}".format(exc), xbmc.LOGWARNING)
            self.stop()
            return False

    def stop(self):
        xbmcgui.Window(10000).clearProperty(PORT_PROPERTY)
        if self.server:
            try:
                self.server.shutdown()
                self.server.server_close()
            except Exception:
                pass
        if self.thread:
            self.thread.join(timeout=2)
        for session in self.sessions:
            try:
                session.close()
            except Exception:
                pass
        self.sessions = []
        self.server = None
        self.thread = None


def build_thumb_url(image_url, referer=None):
    """Return a local proxy URL, or the source URL while the service is absent."""
    if not _valid_image_url(image_url):
        return image_url
    port = xbmcgui.Window(10000).getProperty(PORT_PROPERTY)
    if not port or not port.isdigit():
        return image_url
    data = {"u": image_url}
    if referer:
        data["r"] = referer
    query = urllib.parse.urlencode(data)
    return "http://127.0.0.1:{}/thumb?{}".format(port, query)


def build_loadvid_url(filename):
    if not re.match(r"^adulthideout_loadvid_[0-9a-f]{16}\.m3u8$", filename or ""):
        return ""
    port = xbmcgui.Window(10000).getProperty(PORT_PROPERTY)
    if not port or not port.isdigit():
        return ""
    return "http://127.0.0.1:{}/loadvid/{}".format(port, filename)
