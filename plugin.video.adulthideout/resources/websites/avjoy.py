#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
AVJoy website adapter for AdultHideout.

Architektur-Entscheidungen (Stand April 2026):

1. Page-Fetches laufen primär über curl.exe (Windows) oder curl_cffi (Cross-Platform),
   weil AVJoy's Cloudflare requests+urllib beide blockt.

2. Video-Playback läuft über einen lokalen curl.exe-basierten Proxy. Das umgeht
   Kodi's hardcoded 20s Low-Speed-Timeout, weil curl.exe selbst aggressiver
   connected und früh Body-Bytes liefert (innerhalb von ~1.6s statt 22s).

3. Stream-URLs werden 20min gecached (AVJoy-Tokens haben ~30min TTL, wir gehen
   konservativ vor). Cache wird sowohl per Zeit als auch per URL-expires-Param
   invalidiert.

4. Page-Cache nach URL-Typ differenziert:
   - Video-Detail-Seiten: 30min (stabil)
   - Sort-Listings, Search: 5min (ändert sich häufiger)

5. Precache läuft parallel (4 Threads) UND non-blocking — der User sieht die
   Liste sofort, während im Hintergrund die Stream-URLs aufgelöst werden.
"""

import sys
import os
import glob
import shutil
import subprocess
import tempfile
import threading
import concurrent.futures
import xbmcaddon


try:
    addon_path = xbmcaddon.Addon().getAddonInfo('path')
    vendor_path = os.path.join(addon_path, 'resources', 'lib', 'vendor')
    if vendor_path not in sys.path:
        sys.path.insert(0, vendor_path)
except Exception:
    pass

import re
import urllib.parse
import html
import json
import time
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import xbmc
import xbmcgui
import xbmcplugin
import xbmcvfs
import requests
from resources.lib.base_website import BaseWebsite
from resources.lib.resilient_http import fetch_text
from resources.lib.proxy_utils import PlaybackGuard, ProxyController


# =============================================================================
# curl.exe helpers (Windows only)
# =============================================================================

def _curl_exe_path():
    """
    Sucht nach einem verfügbaren curl-Binary.
    
    - Windows: curl.exe aus C:\\Windows\\System32 (mitgeliefert seit Win10 1803)
    - Linux/macOS/Android mit Root: /usr/bin/curl falls vorhanden
    - Android Kodi: meistens None (Subprocess-Spawning oft eingeschränkt)
    
    Gibt None zurück wenn kein curl gefunden wird ODER subprocess nicht nutzbar ist.
    """
    try:
        # Test ob subprocess überhaupt funktioniert (auf Android oft nicht)
        # Wir prüfen das nicht aktiv, sondern verlassen uns auf shutil.which
        path = shutil.which('curl.exe') or shutil.which('curl')
        if not path:
            return None
        return path
    except Exception:
        return None


def _can_use_curl_subprocess():
    """
    Prüft ob curl als Subprocess nutzbar ist. Startet einen trivialen
    --version-Aufruf um Android-Einschränkungen frühzeitig zu erkennen.
    Ergebnis wird gecached.
    """
    if hasattr(_can_use_curl_subprocess, '_cached'):
        return _can_use_curl_subprocess._cached
    
    path = _curl_exe_path()
    if not path:
        _can_use_curl_subprocess._cached = False
        return False
    
    try:
        startupinfo, creationflags = _no_window_startupinfo()
        result = subprocess.run(
            [path, '--version'],
            capture_output=True,
            timeout=5,
            startupinfo=startupinfo,
            creationflags=creationflags,
        )
        _can_use_curl_subprocess._cached = (result.returncode == 0)
    except Exception:
        _can_use_curl_subprocess._cached = False
    
    return _can_use_curl_subprocess._cached


def _no_window_startupinfo():
    if os.name != 'nt':
        return None, 0
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = 0
    return startupinfo, getattr(subprocess, 'CREATE_NO_WINDOW', 0)


def _kill_process_safely(proc, timeout=2):
    """Terminiert einen Subprocess sauber. Stdout/stderr werden geschlossen."""
    if proc is None:
        return
    try:
        if proc.poll() is None:
            try:
                proc.terminate()
                proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                try:
                    proc.kill()
                    proc.wait(timeout=1)
                except Exception:
                    pass
            except Exception:
                pass
    except Exception:
        pass
    for stream in (getattr(proc, 'stdout', None), getattr(proc, 'stderr', None)):
        if stream:
            try:
                stream.close()
            except Exception:
                pass


# =============================================================================
# curl.exe-basierter lokaler Stream-Proxy (nur Windows)
# =============================================================================

class _AvjoyCurlProxyController:
    """
    Lokaler HTTP-Server der Video-Chunks von curl.exe an Kodi weiterreicht.
    Vorteil gegenüber Python-Sockets: curl.exe's TLS-Stack ist viel schneller
    und liefert erstes Byte in ~1.6s statt 23s wie Python-urllib3.
    """

    def __init__(self, upstream_url, upstream_headers=None, cookies=None,
                 logger=None, host='127.0.0.1', port=0):
        self.upstream_url = upstream_url
        self.upstream_headers = upstream_headers or {}
        self.cookies = cookies or {}
        self.logger = logger
        self.host = host
        self.port = port
        self.httpd = None
        self.thread = None
        self.local_url = None
        self.curl_path = _curl_exe_path()

    def _log(self, level, message):
        if self.logger:
            log_fn = getattr(self.logger, level, None)
            if callable(log_fn):
                log_fn(message)

    def _build_command(self, range_header=None, header_path=None):
        if not self.curl_path:
            raise RuntimeError('curl.exe not available')

        headers = dict(self.upstream_headers)
        headers.pop('Connection', None)
        if self.cookies and 'Cookie' not in headers:
            headers['Cookie'] = '; '.join(f'{k}={v}' for k, v in self.cookies.items())
        if range_header:
            headers['Range'] = range_header

        command = [
            self.curl_path,
            '-L',
            '--silent',
            '--http1.1',  # wichtig für Video-Streams
            '--connect-timeout', '10',
            '--user-agent', headers.pop('User-Agent', 'Mozilla/5.0'),
        ]
        if header_path:
            command.extend(['-D', header_path])
        for k, v in headers.items():
            if v:
                command.extend(['-H', f'{k}: {v}'])
        command.append(self.upstream_url)
        return command

    def _parse_header_file(self, header_path):
        status = None
        headers = {}
        try:
            with open(header_path, 'rb') as fh:
                raw = fh.read().decode('iso-8859-1', errors='replace')
        except Exception:
            return status, headers

        blocks = [b for b in re.split(r'\r?\n\r?\n', raw.strip()) if b.strip()]
        if not blocks:
            return status, headers

        block = blocks[-1]
        lines = block.splitlines()
        if lines:
            m = re.match(r'HTTP/\S+\s+(\d+)', lines[0])
            if m:
                status = int(m.group(1))

        for line in lines[1:]:
            if ':' not in line:
                continue
            k, v = line.split(':', 1)
            headers[k.strip().lower()] = v.strip()
        return status, headers

    def start(self):
        controller = self

        class _Handler(BaseHTTPRequestHandler):
            server_version = 'AHAvjoyCurlProxy/1.0'

            def log_message(self, fmt, *args):
                return

            def _write_chunked(self, data):
                if not data:
                    return
                self.wfile.write(f'{len(data):X}\r\n'.encode('ascii'))
                self.wfile.write(data)
                self.wfile.write(b'\r\n')
                self.wfile.flush()

            def _write_terminator(self):
                try:
                    self.wfile.write(b'0\r\n\r\n')
                    self.wfile.flush()
                except Exception:
                    pass

            def _content_range(self, range_header):
                m = re.match(r'bytes=(\d+)-(\d*)', range_header or '')
                if not m:
                    return None
                start = int(m.group(1))
                end = int(m.group(2)) if m.group(2) else start + (10 * 1024 * 1024) - 1
                return f'bytes {start}-{end}/*'

            def do_GET(self):
                range_header = self.headers.get('Range')
                proc = None
                header_path = None
                started = time.time()
                try:
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.headers') as hf:
                        header_path = hf.name

                    command = controller._build_command(
                        range_header=range_header, header_path=header_path
                    )
                    startupinfo, creationflags = _no_window_startupinfo()
                    proc = subprocess.Popen(
                        command,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        startupinfo=startupinfo,
                        creationflags=creationflags,
                    )
                    first = proc.stdout.read(8192)
                    if not first:
                        stderr_data = b''
                        try:
                            stderr_data = proc.stderr.read(1024)
                        except Exception:
                            pass
                        controller._log(
                            'warning',
                            f'AVJoy curl proxy produced no data: '
                            f'{stderr_data.decode("utf-8", "ignore")[:200]}'
                        )
                        try:
                            self.send_error(502, 'AVJoy upstream produced no data')
                        except Exception:
                            pass
                        return

                    upstream_status, upstream_headers = controller._parse_header_file(header_path)
                    status = upstream_status or (206 if range_header else 200)
                    content_type = upstream_headers.get('content-type') or 'video/mp4'
                    content_length = upstream_headers.get('content-length')
                    content_range = upstream_headers.get('content-range')

                    self.send_response(status)
                    self.send_header('Content-Type', content_type)
                    self.send_header('Accept-Ranges', 'bytes')
                    if content_length:
                        self.send_header('Content-Length', content_length)
                    else:
                        self.send_header('Transfer-Encoding', 'chunked')
                    self.send_header('Cache-Control', 'no-store')
                    self.send_header('Connection', 'close')
                    content_range = content_range or self._content_range(range_header)
                    if content_range:
                        self.send_header('Content-Range', content_range)
                    self.end_headers()

                    use_chunked = not bool(content_length)
                    controller._log(
                        'info',
                        f'AVJoy curl proxy first bytes in {time.time() - started:.2f}s '
                        f'({len(first)} bytes, status={status}, '
                        f'length={content_length or "chunked"})'
                    )
                    if use_chunked:
                        self._write_chunked(first)
                    else:
                        self.wfile.write(first)
                        self.wfile.flush()

                    while True:
                        chunk = proc.stdout.read(512 * 1024)
                        if not chunk:
                            break
                        if use_chunked:
                            self._write_chunked(chunk)
                        else:
                            self.wfile.write(chunk)
                            self.wfile.flush()
                    if use_chunked:
                        self._write_terminator()
                except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError) as exc:
                    controller._log('debug', f'AVJoy curl proxy client disconnected: {exc}')
                except Exception as exc:
                    controller._log('error', f'AVJoy curl proxy failed: {exc}')
                    try:
                        self.send_error(502, f'AVJoy curl proxy failed: {exc}')
                    except Exception:
                        pass
                finally:
                    _kill_process_safely(proc)
                    if header_path and os.path.exists(header_path):
                        try:
                            os.remove(header_path)
                        except Exception:
                            pass

        self.httpd = ThreadingHTTPServer((self.host, self.port), _Handler)
        if self.port == 0:
            self.port = self.httpd.server_port
        self.thread = threading.Thread(
            target=self.httpd.serve_forever,
            name='AHAvjoyCurlProxyThread',
            daemon=True
        )
        self.thread.start()
        self.local_url = f'http://{self.host}:{self.port}/stream'
        self._log('info', f'AVJoy curl proxy started: {self.local_url}')
        return self.local_url

    def stop(self, timeout=1.0):
        try:
            if self.httpd:
                self.httpd.shutdown()
                self.httpd.server_close()
                self._log('info', 'AVJoy curl proxy stopped')
        except Exception as exc:
            self._log('debug', f'AVJoy curl proxy stop failed: {exc}')
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=timeout)


# =============================================================================
# curl_cffi / cloudscraper imports with fallback discovery
# =============================================================================

try:
    from curl_cffi import requests as curl_requests
    _HAS_CURL_CFFI = True
except Exception:
    curl_requests = None
    _HAS_CURL_CFFI = False

if not _HAS_CURL_CFFI:
    try:
        local_app_data = os.environ.get("LOCALAPPDATA", "")
        pattern = os.path.join(local_app_data, "Programs", "Python", "Python*",
                               "Lib", "site-packages")
        for site_packages in sorted(glob.glob(pattern), reverse=True):
            if os.path.isdir(site_packages) and site_packages not in sys.path:
                sys.path.append(site_packages)
        from curl_cffi import requests as curl_requests
        _HAS_CURL_CFFI = True
    except Exception:
        curl_requests = None
        _HAS_CURL_CFFI = False


try:
    import cloudscraper
    _HAS_CF = True
except ImportError:
    _HAS_CF = False


# =============================================================================
# AVJoy Website Adapter
# =============================================================================

class AvjoyWebsite(BaseWebsite):
    def __init__(self, addon_handle):
        super().__init__(
            name="avjoy",
            base_url="https://en.avjoy.me",
            search_url="https://en.avjoy.me/search/videos/{}",
            addon_handle=addon_handle
        )
        self.display_name = "Avjoy"
        self.sort_options = ["Most Recent", "Most Viewed", "Top Rated",
                             "Top Favorites", "Longest"]
        self.sort_paths = {
            "Most Recent": "/videos?o=mr",
            "Most Viewed": "/videos?o=mv",
            "Top Rated": "/videos?o=tr",
            "Top Favorites": "/videos?o=tf",
            "Longest": "/videos?o=lg"
        }
        self.setting_id_sort = "avjoy_sort_by"
        self.timeout = 20
        self.user_agent = (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/123.0.0.0 Safari/537.36'
        )
        self.session = self._init_session()
        self.raw_session = self._init_session(prefer_curl=True)
        self.raw_session.headers.update({
            'User-Agent': self.user_agent,
            'Accept-Language': 'en-US,en;q=0.9',
            'Connection': 'keep-alive',
        })

        # Cache-TTLs (Sekunden)
        self.cache_ttl_video = 30 * 60   # Video-Detail-Seiten: 30min
        self.cache_ttl_listing = 5 * 60  # Sort-Listings, Search: 5min
        self.cookie_ttl = 6 * 60 * 60
        self.stream_ttl = 20 * 60

        # Precache-Konfiguration
        self.pre_resolve_count = 4
        self.precache_workers = 4

        # Cache-Pfade
        self.cache_dir = self._get_cache_dir()
        self.cookie_cache_path = os.path.join(self.cache_dir, 'avjoy_cookies.json')
        self.stream_cache_path = os.path.join(self.cache_dir, 'avjoy_streams.json')

        # State
        self._last_page_cache_hit = False
        self._stream_cache_lock = threading.Lock()
        self._cookie_cache_lock = threading.Lock()
        self._precache_thread = None

        self._restore_cookies()
        if _can_use_curl_subprocess():
            self.logger.info(f"AVJoy using curl HTTP backend: {_curl_exe_path()}")
        else:
            self.logger.info("AVJoy using curl_cffi HTTP backend (no curl subprocess available)")

    # -------------------------------------------------------------------------
    # Cache paths
    # -------------------------------------------------------------------------

    def _get_cache_dir(self):
        try:
            profile = xbmcvfs.translatePath(self.addon.getAddonInfo('profile'))
        except Exception:
            profile = ''
        if not profile:
            profile = os.path.join(os.path.expanduser('~'), '.adulthideout')
        cache_dir = os.path.join(profile, 'avjoy_cache')
        try:
            os.makedirs(cache_dir, exist_ok=True)
        except Exception:
            pass
        return cache_dir

    # -------------------------------------------------------------------------
    # Session setup
    # -------------------------------------------------------------------------

    def _init_session(self, prefer_curl=False):
        """Initialisiert eine Session. curl_cffi > cloudscraper > requests."""
        if prefer_curl and _HAS_CURL_CFFI:
            try:
                session = curl_requests.Session(impersonate="chrome123", verify=False)
                session.headers.update({'User-Agent': self.user_agent})
                self.logger.info("AVJoy using curl_cffi HTTP backend")
                return session
            except Exception as exc:
                self.logger.warning(f"Could not initialize AVJoy curl_cffi session: {exc}")

        if _HAS_CF:
            return cloudscraper.create_scraper(browser={'custom': self.user_agent})
        else:
            s = requests.Session()
            s.headers.update({'User-Agent': self.user_agent})
            return s

    def _get_cookie_dict(self, session):
        try:
            cookies = getattr(session, 'cookies', None)
            if not cookies:
                return {}
            if hasattr(cookies, 'get_dict'):
                return cookies.get_dict()
            if hasattr(cookies, 'items'):
                return dict(cookies.items())
        except Exception:
            pass
        return {}

    # -------------------------------------------------------------------------
    # curl.exe fetch (primary backend on Windows)
    # -------------------------------------------------------------------------

    def _fetch_with_curl_exe(self, url, headers=None, timeout=30):
        if not _can_use_curl_subprocess():
            return None
        curl_path = _curl_exe_path()
        if not curl_path:
            return None

        request_headers = dict(headers or {})
        cookies = self._get_cookie_dict(self.raw_session)
        if not cookies:
            cookies = self._get_cookie_dict(self.session)
        if cookies and 'Cookie' not in request_headers:
            request_headers['Cookie'] = '; '.join(f'{k}={v}' for k, v in cookies.items())

        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.html') as tmp_file:
                tmp_path = tmp_file.name

            # HTTP/2 wurde aus dem Command entfernt weil Windows' mitgelieferte
            # curl.exe (libcurl 7.55+) es nicht unterstützt. HTTP/1.1 ist hier
            # völlig ausreichend — der Flaschenhals ist AVJoy's CDN, nicht das
            # Protokoll.
            command = [
                curl_path,
                '-L',
                '--silent',
                '--show-error',
                '--http1.1',
                '--compressed',    # gzip/br akzeptieren — AVJoy komprimiert
                '--connect-timeout', '10',
                '--max-time', str(timeout),
                '--user-agent', request_headers.pop('User-Agent', self.user_agent),
                '-o', tmp_path,
            ]
            for k, v in request_headers.items():
                if k.lower() in ('connection', 'host') or not v:
                    continue
                command.extend(['-H', f'{k}: {v}'])
            command.append(url)

            startupinfo, creationflags = _no_window_startupinfo()
            completed = subprocess.run(
                command,
                capture_output=True,
                timeout=timeout + 10,
                check=False,
                startupinfo=startupinfo,
                creationflags=creationflags,
            )

            if completed.returncode == 0 and tmp_path and os.path.exists(tmp_path):
                with open(tmp_path, 'rb') as fh:
                    data = fh.read()
                if data:
                    return data.decode('utf-8', errors='ignore')

            stderr = completed.stderr.decode('utf-8', errors='ignore').strip()
            if stderr:
                self.logger.warning(
                    f"AVJoy curl.exe fetch failed rc={completed.returncode}: "
                    f"{stderr[:200]}"
                )
        except Exception as exc:
            self.logger.warning(f"AVJoy curl.exe fetch failed: {exc}")
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass
        return None

    # -------------------------------------------------------------------------
    # JSON cache helpers
    # -------------------------------------------------------------------------

    def _read_json(self, path):
        try:
            with open(path, 'r', encoding='utf-8') as fh:
                return json.load(fh)
        except Exception:
            return {}

    def _write_json_atomic(self, path, data):
        """Atomic write — schreibt in .tmp und rename. Thread-safe."""
        try:
            tmp_path = path + '.tmp'
            with open(tmp_path, 'w', encoding='utf-8') as fh:
                json.dump(data, fh)
            os.replace(tmp_path, path)
        except Exception as exc:
            self.logger.warning(f"Could not write AVJoy cache file {path}: {exc}")

    # -------------------------------------------------------------------------
    # Cookie persistence
    # -------------------------------------------------------------------------

    def _restore_cookies(self):
        data = self._read_json(self.cookie_cache_path)
        cookies = data.get('cookies') if isinstance(data, dict) else {}
        ts = float(data.get('ts', 0) or 0) if isinstance(data, dict) else 0
        if not cookies or time.time() - ts > self.cookie_ttl:
            return
        try:
            self.raw_session.cookies.update(cookies)
            if hasattr(self.session, 'cookies'):
                self.session.cookies.update(cookies)
            self.logger.info("Restored AVJoy session cookies from cache")
        except Exception as exc:
            self.logger.warning(f"Could not restore AVJoy cookies: {exc}")

    def _save_cookies(self):
        cookies = {}
        try:
            cookies.update(self._get_cookie_dict(self.session))
        except Exception:
            pass
        try:
            cookies.update(self._get_cookie_dict(self.raw_session))
        except Exception:
            pass
        if cookies:
            with self._cookie_cache_lock:
                self._write_json_atomic(
                    self.cookie_cache_path,
                    {'ts': time.time(), 'cookies': cookies}
                )

    # -------------------------------------------------------------------------
    # Page cache (URL-type aware TTL)
    # -------------------------------------------------------------------------

    def _get_page_ttl(self, url):
        """Video-Detail-Seiten sind stabil, Listings ändern sich häufig."""
        parsed = urllib.parse.urlparse(url)
        if '/video/' in parsed.path:
            return self.cache_ttl_video
        return self.cache_ttl_listing

    def _is_cacheable_page(self, url):
        # Alle Seiten außer dem Root sind cachebar
        parsed = urllib.parse.urlparse(url)
        return bool(parsed.path and parsed.path != '/')

    def _page_cache_path(self, url):
        digest = hashlib.md5(url.encode('utf-8')).hexdigest()
        return os.path.join(self.cache_dir, f'avjoy_page_{digest}.html')

    def _load_page_cache(self, url):
        if not self._is_cacheable_page(url):
            return None
        path = self._page_cache_path(url)
        try:
            if not os.path.exists(path):
                return None
            age = time.time() - os.path.getmtime(path)
            ttl = self._get_page_ttl(url)
            if age > ttl:
                return None
            with open(path, 'r', encoding='utf-8', errors='ignore') as fh:
                content = fh.read()
            if content:
                self._last_page_cache_hit = True
                self.logger.info(
                    f"AVJoy page cache hit ({int(age)}s/{ttl}s TTL): {url}"
                )
                return content
        except Exception as exc:
            self.logger.warning(f"Could not read AVJoy page cache: {exc}")
        return None

    def _save_page_cache(self, url, content):
        if not content or not self._is_cacheable_page(url):
            return
        try:
            tmp_path = self._page_cache_path(url) + '.tmp'
            with open(tmp_path, 'w', encoding='utf-8') as fh:
                fh.write(content)
            os.replace(tmp_path, self._page_cache_path(url))
        except Exception as exc:
            self.logger.warning(f"Could not write AVJoy page cache: {exc}")

    # -------------------------------------------------------------------------
    # HTTP request with cascading fallback
    # -------------------------------------------------------------------------

    def make_request(self, url, referer=None):
        self._last_page_cache_hit = False
        cached = self._load_page_cache(url)
        if cached:
            return cached

        self.logger.info(f"Fetching: {url}")
        headers = {
            'User-Agent': self.user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': referer or (self.base_url + '/'),
        }
        started = time.time()

        # Primär: curl.exe (Windows)
        content = self._fetch_with_curl_exe(url, headers=headers, timeout=max(self.timeout, 30))
        if content:
            self.logger.info(f"Fetched {url} via curl.exe in {time.time() - started:.2f}s")
            self._save_page_cache(url, content)
            return content

        # Fallback 1: curl_cffi-Session
        try:
            response = self.raw_session.get(
                url, headers=headers, timeout=max(self.timeout, 30)
            )
            if response.status_code == 200 and response.text:
                self.logger.info(f"Fetched {url} via curl_cffi in {time.time() - started:.2f}s")
                self._save_cookies()
                self._save_page_cache(url, response.text)
                return response.text
            self.logger.warning(
                f"curl_cffi request returned HTTP {response.status_code} for {url}"
            )
        except Exception as exc:
            self.logger.warning(f"curl_cffi request failed: {exc}")

        # Fallback 2: resilient_http Kaskade
        content = fetch_text(
            url,
            headers=headers,
            scraper=self.session,
            logger=self.logger,
            timeout=max(self.timeout, 30),
            use_windows_curl_fallback=True,
        )
        if content:
            self.logger.info(f"Fetched {url} via fallback in {time.time() - started:.2f}s")
            self._save_cookies()
            self._save_page_cache(url, content)
        return content

    # -------------------------------------------------------------------------
    # Stream URL cache with expires= validation
    # -------------------------------------------------------------------------

    def _load_stream_cache(self):
        data = self._read_json(self.stream_cache_path)
        return data if isinstance(data, dict) else {}

    def _save_stream_cache(self, data):
        with self._stream_cache_lock:
            self._write_json_atomic(self.stream_cache_path, data)

    def _stream_url_expired(self, stream_url):
        """Prüft ob die URL selbst einen expires= Parameter hat der abgelaufen ist."""
        if not stream_url:
            return True
        for param in ('expires', 'expire', 'e'):
            m = re.search(rf'[?&]{param}=(\d+)', stream_url, re.IGNORECASE)
            if m:
                try:
                    expires_ts = int(m.group(1))
                    # 60s Sicherheitspuffer
                    if time.time() + 60 > expires_ts:
                        return True
                except Exception:
                    pass
        return False

    def _get_cached_stream(self, video_url):
        data = self._load_stream_cache()
        item = data.get(video_url) if isinstance(data, dict) else None
        if not isinstance(item, dict):
            return None
        # TTL 1: unser Cache-TTL
        if time.time() - float(item.get('ts', 0) or 0) > self.stream_ttl:
            return None
        stream_url = item.get('stream_url')
        if not stream_url or '.mp4' not in stream_url:
            return None
        # TTL 2: URL selbst prüfen
        if self._stream_url_expired(stream_url):
            return None
        return stream_url

    def _set_cached_stream(self, video_url, stream_url):
        if not video_url or not stream_url:
            return
        with self._stream_cache_lock:
            data = self._load_stream_cache()
            data[video_url] = {'ts': time.time(), 'stream_url': stream_url}
            # Cache klein halten — tote/abgelaufene Einträge rauswerfen
            cutoff = time.time() - self.stream_ttl
            for key in list(data.keys()):
                try:
                    if float(data[key].get('ts', 0) or 0) < cutoff:
                        del data[key]
                except Exception:
                    del data[key]
            self._write_json_atomic(self.stream_cache_path, data)

    # -------------------------------------------------------------------------
    # Stream URL extraction and resolution
    # -------------------------------------------------------------------------

    def _extract_stream_url(self, content):
        sources = []
        for source_match in re.finditer(r'<source\b[^>]+>', content or '', re.IGNORECASE):
            tag = source_match.group(0)
            src_match = re.search(r'src=[\'"]([^\'"]+)[\'"]', tag, re.IGNORECASE)
            if not src_match:
                continue
            src = html.unescape(src_match.group(1).strip())
            if '.mp4' not in src:
                continue

            res_match = re.search(r'(?:res|label)=[\'"]([^\'"]+)[\'"]', tag, re.IGNORECASE)
            quality = res_match.group(1) if res_match else ''
            quality_match = re.search(r'(\d+)', quality)
            quality_num = int(quality_match.group(1)) if quality_match else 0
            sources.append((quality_num, urllib.parse.urljoin(self.base_url, src)))

        if not sources:
            return None
        # Höchste Qualität zuerst
        sources.sort(key=lambda item: item[0], reverse=True)
        return sources[0][1]

    def _resolve_stream_url(self, video_url):
        cached = self._get_cached_stream(video_url)
        if cached:
            return cached
        content = self.make_request(video_url, referer=self.base_url + '/')
        stream_url = self._extract_stream_url(content)
        if stream_url:
            self._set_cached_stream(video_url, stream_url)
        return stream_url

    # -------------------------------------------------------------------------
    # Parallel + non-blocking precache
    # -------------------------------------------------------------------------

    def _precache_streams_parallel(self, video_urls):
        """Löst bis zu N Stream-URLs parallel auf. Läuft im Hintergrund."""
        if self._last_page_cache_hit:
            return

        to_warm = [u for u in video_urls[:self.pre_resolve_count]
                   if not self._get_cached_stream(u)]
        if not to_warm:
            return

        started = time.time()

        def _warm_one(video_url):
            try:
                return bool(self._resolve_stream_url(video_url))
            except Exception as exc:
                self.logger.warning(f"AVJoy stream pre-cache failed for {video_url}: {exc}")
                return False

        try:
            with concurrent.futures.ThreadPoolExecutor(
                max_workers=min(self.precache_workers, len(to_warm))
            ) as executor:
                results = list(executor.map(_warm_one, to_warm))
            warmed = sum(results)
        except Exception as exc:
            self.logger.warning(f"AVJoy precache pool failed: {exc}")
            warmed = 0

        if warmed:
            self.logger.info(
                f"Pre-cached {warmed}/{len(to_warm)} AVJoy streams "
                f"in {time.time() - started:.2f}s (parallel)"
            )

    def _start_precache_background(self, video_urls):
        """Startet Precaching im Hintergrund-Thread. Non-blocking."""
        # Alten Thread abwarten falls noch einer läuft
        if self._precache_thread and self._precache_thread.is_alive():
            return

        self._precache_thread = threading.Thread(
            target=self._precache_streams_parallel,
            args=(list(video_urls),),
            daemon=True,
            name='AVJoyPrecacheThread'
        )
        self._precache_thread.start()

    # -------------------------------------------------------------------------
    # URL / label
    # -------------------------------------------------------------------------

    def get_start_url_and_label(self):
        try:
            idx = int(self.addon.getSetting(self.setting_id_sort) or 0)
        except ValueError:
            idx = 0

        if idx < 0 or idx >= len(self.sort_options):
            idx = 0

        sort_key = self.sort_options[idx]
        path = self.sort_paths.get(sort_key, "/videos?o=mr")

        full_url = urllib.parse.urljoin(self.base_url, path)
        return full_url, f"{self.display_name} [COLOR yellow]({sort_key})[/COLOR]"

    # -------------------------------------------------------------------------
    # Main listing
    # -------------------------------------------------------------------------

    def process_content(self, url):
        if not url or url == "BOOTSTRAP":
            url, _ = self.get_start_url_and_label()

        content = self.make_request(url, referer=self.base_url + '/')
        if not content:
            self.notify_error("Failed to load content")
            self.end_directory()
            return

        encoded_url = urllib.parse.quote_plus(url)
        dir_context_menu = [(
            'Sort by...',
            f'RunPlugin({sys.argv[0]}?mode=7&action=select_sort&'
            f'website={self.name}&original_url={encoded_url})'
        )]

        self.add_dir(
            '[COLOR blue]Search[/COLOR]', '', 5,
            self.icons.get('search', ''), context_menu=dir_context_menu
        )
        self.add_dir(
            '[COLOR blue]Categories[/COLOR]',
            f'{self.base_url}/categories', 8,
            self.icons.get('categories', ''), context_menu=dir_context_menu
        )

        listing_urls = self.parse_video_list(content, url)
        self.add_next_button(content, url)
        self.end_directory()

        # Precache NACH end_directory — User sieht Liste sofort
        if listing_urls:
            self._start_precache_background(listing_urls)

    def parse_video_list(self, content, current_url):
        """Parst Video-Listing, fügt sie zur Directory hinzu, gibt URL-Liste zurück."""
        if 'class="well-filters"' in content:
            parts = content.split('class="well-filters"')
            content = parts[-1]
        elif 'Most Recent' in content:
            parts = content.split('Most Recent')
            content = parts[-1]

        pattern = (
            r'<div class="[^"]*col-[^"]*">.*?<a href="([^"]+)">.*?'
            r'<div class="thumb-overlay".*?>.*?<img src="([^"]+)" title="([^"]+)"'
        )
        matches = re.findall(pattern, content, re.DOTALL | re.IGNORECASE)

        count = 0
        seen_urls = set()
        listing_urls = []

        for video_path, thumb, title in matches:
            if '/video/' not in video_path or '/videos/' in video_path:
                continue
            if video_path in seen_urls:
                continue
            seen_urls.add(video_path)

            full_url = urllib.parse.urljoin(self.base_url, video_path)
            thumb_url = urllib.parse.urljoin(self.base_url, thumb)
            clean_title = html.unescape(title.strip())

            self.add_link(
                clean_title, full_url, 4, thumb_url, self.fanart,
                info_labels={'title': clean_title}
            )
            listing_urls.append(full_url)
            count += 1

        self.logger.info(f"Found {count} videos")
        return listing_urls

    def add_next_button(self, content, current_url):
        next_url = None
        m = re.search(r'<a [^>]*href="([^"]+)"[^>]*class="[^"]*prevnext"[^>]*>', content)
        if not m:
            m = re.search(
                r'<li class="page-item">\s*<a class="page-link" '
                r'href="([^"]+)"[^>]*aria-label="Next"',
                content
            )
        if m:
            next_url = m.group(1)

        if next_url:
            full_next_url = urllib.parse.urljoin(self.base_url, html.unescape(next_url))
            self.add_dir(
                '[COLOR blue]Next Page >>[/COLOR]',
                full_next_url, 2,
                self.icons.get('default', ''),
                self.fanart
            )

    # -------------------------------------------------------------------------
    # Playback
    # -------------------------------------------------------------------------

    def play_video(self, url):
        self.logger.info(f"Resolving video: {url}")
        resolve_start = time.time()
        video_url = self._resolve_stream_url(url)
        resolve_time = time.time() - resolve_start

        if not video_url:
            self.logger.error("No playable stream found")
            self.notify_error("No playable stream found")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return

        self.logger.info(f"AVJoy stream resolved in {resolve_time:.2f}s: {video_url[:100]}")

        headers = {
            'User-Agent': self.user_agent,
            'Referer': url,
            'Origin': self.base_url,
            'Accept': '*/*',
            'Accept-Encoding': 'identity',
            'Accept-Language': 'en-US,en;q=0.9',
            'Connection': 'keep-alive',
        }
        cookies = self._get_cookie_dict(self.raw_session)
        if not cookies:
            cookies = self._get_cookie_dict(self.session)

        try:
            proxy_start = time.time()
            if _can_use_curl_subprocess():
                # Schneller curl-basierter Proxy (Windows, oder Linux mit curl-Binary)
                proxy = _AvjoyCurlProxyController(
                    upstream_url=video_url,
                    upstream_headers=headers,
                    cookies=cookies,
                    logger=self.logger,
                )
            else:
                # Python-basierter Fallback (Android, eingeschränkte Umgebungen)
                proxy_session = self._init_session(prefer_curl=True)
                proxy_session.headers.update(headers)
                if cookies:
                    proxy_session.cookies.update(cookies)

                proxy = ProxyController(
                    upstream_url=video_url,
                    upstream_headers=headers,
                    cookies=cookies,
                    session=proxy_session,
                    skip_resolve=True,
                )
            local_url = proxy.start()
            proxy_time = time.time() - proxy_start
            self.logger.info(
                f"AVJoy playback stats: resolve={resolve_time:.2f}s, "
                f"proxy_start={proxy_time:.2f}s, url={local_url}"
            )

            li = xbmcgui.ListItem(path=local_url)
            li.setProperty("IsPlayable", "true")
            li.setMimeType("video/mp4")
            li.setContentLookup(False)
            xbmcplugin.setResolvedUrl(self.addon_handle, True, li)
            PlaybackGuard(xbmc.Player(), xbmc.Monitor(), local_url, proxy).start()
            return
        except Exception as exc:
            self.logger.warning(f"AVJoy proxy playback failed, trying direct stream: {exc}")
            if cookies:
                headers['Cookie'] = '; '.join(f'{k}={v}' for k, v in cookies.items())

            li = xbmcgui.ListItem(path=video_url + '|' + urllib.parse.urlencode(headers))
            li.setProperty("IsPlayable", "true")
            li.setMimeType("video/mp4")
            li.setContentLookup(False)
            xbmcplugin.setResolvedUrl(self.addon_handle, True, li)
            return

    # -------------------------------------------------------------------------
    # Categories
    # -------------------------------------------------------------------------

    def process_categories(self, url):
        content = self.make_request(url, referer=self.base_url + '/')
        if not content:
            self.end_directory()
            return

        pattern = (
            r'<a href="(/videos/[^"]+)">\s*<div class="thumb-overlay">\s*'
            r'<img src="([^"]+)" title="([^"]+)"'
        )
        matches = re.findall(pattern, content, re.DOTALL | re.IGNORECASE)

        encoded_url = urllib.parse.quote_plus(url)
        context_menu = [(
            'Sort by...',
            f'RunPlugin({sys.argv[0]}?mode=7&action=select_sort&'
            f'website={self.name}&original_url={encoded_url})'
        )]

        for cat_path, thumb, name in matches:
            full_cat_url = urllib.parse.urljoin(self.base_url, cat_path)
            full_thumb = urllib.parse.urljoin(self.base_url, thumb)
            self.add_dir(
                html.unescape(name.strip()), full_cat_url, 2,
                full_thumb, self.fanart, context_menu=context_menu
            )

        self.end_directory()

    # -------------------------------------------------------------------------
    # Sort selection
    # -------------------------------------------------------------------------

    def select_sort(self, original_url=None):
        try:
            current_idx = int(self.addon.getSetting(self.setting_id_sort) or 0)
        except Exception:
            current_idx = 0

        dialog = xbmcgui.Dialog()
        idx = dialog.select("Sort by...", self.sort_options, preselect=current_idx)

        if idx > -1:
            self.addon.setSetting(self.setting_id_sort, str(idx))
            new_url, _ = self.get_start_url_and_label()
            xbmc.executebuiltin(
                f"Container.Update({sys.argv[0]}?mode=2&"
                f"url={urllib.parse.quote_plus(new_url)}&"
                f"website={self.name},replace)"
            )
