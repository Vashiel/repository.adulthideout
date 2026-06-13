#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os
import urllib.parse
import urllib.request
import urllib.error
import xbmc
import xbmcaddon
import threading
import socket
import json
import re
import ssl
import time
from http.server import BaseHTTPRequestHandler
try:
    from http.server import ThreadingHTTPServer
except ImportError:
    from http.server import HTTPServer
    import socketserver
    class ThreadingHTTPServer(socketserver.ThreadingMixIn, HTTPServer):
        pass

try:
    addon_path = xbmcaddon.Addon().getAddonInfo('path')
    vendor_path = os.path.join(addon_path, 'resources', 'lib', 'vendor')
    if vendor_path not in sys.path:
        sys.path.insert(0, vendor_path)
except Exception as e:
    xbmc.log(f"[AdultHideout] Vendor path inject failed in proxy_utils.py: {e}", xbmc.LOGERROR)

try:
    import cloudscraper
    _HAS_CF = True
except Exception as e:
    xbmc.log(f"[AHProxy] cloudscraper import failed: {e}", xbmc.LOGERROR)
    _HAS_CF = False

import requests

# Kleinere Chunks (32 KB) damit read() schneller zurückkehrt — kritisch für Seeks!
# 512 KB blockiert zu lange wenn mehrere Streams parallel laufen.
PROXY_CHUNK = 32 * 1024
DEFAULT_CHUNK = 512 * 1024  # Für requests-Backend (bleibt wie gehabt)

# Read-Timeout für laufende urllib-Streams: Kodis curl gibt nach 20s ohne
# Bytes auf ("Timeout was reached(28)"). Wir brechen VORHER ab, damit Kodi
# sauber neu verbindet statt einzufrieren.
STREAM_READ_TIMEOUT = 15

# KVS-CDNs (get_file-Links) erlauben pro Token typischerweise 2 parallele
# Verbindungen — die dritte bekommt zwar Response-Header, aber der Body
# wird serverseitig gestallt (genau das war der "0 bytes"-Hänger beim Seek).
# Kodi selbst nutzt für MP4 legitim 2 Verbindungen (Daten + moov-Probe).
MAX_PARALLEL_UPSTREAMS = 2

_DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)


# =============================================================================
# urllib-basierter Upstream (für CDNs die requests/urllib3 blocken)
# Nutzt Pythons stdlib http.client + ssl direkt → anderer TLS-Fingerprint
# =============================================================================

class _UrllibUpstream:
    """
    Upstream-Fetcher der Pythons stdlib urllib.request nutzt.
    
    Features:
    - Anderer TLS-Fingerprint als requests/urllib3 → umgeht CDN-Blocking
    - Verbindungs-Management: alte Streams werden bei Seek geschlossen
    - HEAD-Request beim Init für Content-Length (nötig für Kodi-Seeking)
    """
    
    def __init__(self, url, headers=None, cookies=None, probe_size=True):
        self.original_url = url
        self.resolved_url = None
        self.headers = {
            'User-Agent': _DEFAULT_UA,
            'Accept-Encoding': 'identity',
            'Accept-Language': 'en-US,en;q=0.9',
            'Connection': 'keep-alive',
        }
        if headers:
            self.headers.update(headers)
        
        self.cookie_str = ""
        if cookies:
            if isinstance(cookies, dict):
                self.cookie_str = "; ".join(f"{k}={v}" for k, v in cookies.items())
            elif isinstance(cookies, str):
                self.cookie_str = cookies
        
        self._ssl_ctx = ssl.create_default_context()
        self._ssl_ctx.check_hostname = False
        self._ssl_ctx.verify_mode = ssl.CERT_NONE
        
        # Registry aller aktiven Upstream-Streams: Liste von
        # (cancel_event, response, raw_socket). Vorher gab es nur EINEN
        # _active_resp-Slot — bei Kodis parallelen Range-Requests haben
        # sich die Handler-Threads den gegenseitig überschrieben.
        self._active_streams = []
        self._active_lock = threading.Lock()
        
        # Gesamtgröße der Datei (per HEAD ermittelt)
        self.total_size = None
        self._head_failed = False

        # DNS pre-resolve: Löse den Hostnamen EINMAL auf und cache die IP.
        # Nach einem Seek macht urllib erneut getaddrinfo() — aber Windows-DNS-
        # Cache kann dabei intermittierend versagen ([Errno 11002]). Mit der
        # gecachten IP bauen wir die URL um (Host-Header bleibt korrekt).
        self._host_ip_map = {}  # hostname -> ip
        self._pre_resolve(url)
        
        xbmc.log(f"[AHProxy-urllib] Upstream URL: {url[:200]}", xbmc.LOGINFO)
        
        # HEAD-Request um Dateigröße zu ermitteln (Kodi braucht das für Seeks)
        if probe_size:
            self._probe_size()
        else:
            xbmc.log("[AHProxy-urllib] Skipping startup size probe", xbmc.LOGINFO)

    def _pre_resolve(self, url):
        """Löst den Hostnamen aus der URL einmalig auf und speichert die IP."""
        try:
            parsed = urllib.parse.urlparse(url)
            host = parsed.hostname
            if host and not re.match(r'^\d+\.\d+\.\d+\.\d+$', host):
                ip = socket.gethostbyname(host)
                self._host_ip_map[host] = ip
                xbmc.log(f"[AHProxy-urllib] Pre-resolved {host} -> {ip}", xbmc.LOGINFO)
        except Exception as e:
            xbmc.log(f"[AHProxy-urllib] Pre-resolve failed: {e}", xbmc.LOGWARNING)

    def _ip_url(self, url):
        """Ersetzt den Hostnamen in der URL durch die gecachte IP.
        
        Gibt (ip_url, original_host) zurück, oder (url, None) falls keine IP
        gecacht ist."""
        try:
            parsed = urllib.parse.urlparse(url)
            host = parsed.hostname
            ip = self._host_ip_map.get(host)
            if ip and ip != host:
                # Ersetze Host durch IP, behalte Port falls vorhanden
                port = parsed.port
                if port:
                    netloc = f"{ip}:{port}"
                else:
                    netloc = ip
                ip_url = parsed._replace(netloc=netloc).geturl()
                return ip_url, host
        except Exception:
            pass
        return url, None

    def _probe_size(self):
        """HEAD-Request um Content-Length zu ermitteln."""
        try:
            req = self._build_request(self.url)
            req.get_method = lambda: 'HEAD'
            resp = urllib.request.urlopen(req, timeout=3, context=self._ssl_ctx)
            cl = resp.headers.get('Content-Length')
            if cl:
                self.total_size = int(cl)
                xbmc.log(f"[AHProxy-urllib] Total file size: {self.total_size} bytes", xbmc.LOGINFO)
            resp.close()
        except Exception as e:
            self._head_failed = True
            xbmc.log(f"[AHProxy-urllib] HEAD probe failed ({e}). Trying GET Range probe...", xbmc.LOGINFO)
            try:
                req = self._build_request(self.url, {'Range': 'bytes=0-1'})
                resp = urllib.request.urlopen(req, timeout=10, context=self._ssl_ctx)
                cr = resp.headers.get('Content-Range')
                if cr and '/' in cr:
                    self.total_size = int(cr.split('/')[-1].strip())
                    xbmc.log(f"[AHProxy-urllib] Total file size (via GET probe): {self.total_size} bytes", xbmc.LOGINFO)
                resp.close()
            except Exception as e2:
                xbmc.log(f"[AHProxy-urllib] GET Range probe failed: {e2}", xbmc.LOGWARNING)

    @property
    def url(self):
        return self.resolved_url or self.original_url
    
    def _build_request(self, url, extra_headers=None):
        h = {
            'User-Agent': self.headers.get('User-Agent', _DEFAULT_UA),
            'Accept': '*/*',
            'Accept-Encoding': 'identity',
            'Accept-Language': 'en-US,en;q=0.9',
            'Connection': 'keep-alive',
            'Sec-Fetch-Dest': 'video',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'cross-site'
        }
        h.update(self.headers)
        if extra_headers:
            h.update(extra_headers)
        if self.cookie_str and 'Cookie' not in h:
            h['Cookie'] = self.cookie_str
        
        # Log headers for debugging (abbreviate Cookie)
        clean_h = {k: (v[:20] + '...' if k == 'Cookie' and len(v) > 20 else v) for k, v in h.items()}
        xbmc.log(f"[AHProxy-urllib] Request Headers: {clean_h}", xbmc.LOGDEBUG)
            
        req = urllib.request.Request(url, headers=h)
        return req
    
    @staticmethod
    def _raw_sock(resp):
        """Holt das echte socket-Objekt aus einer http.client.HTTPResponse.

        Kette: resp.fp (BufferedReader) -> .raw (SocketIO) -> ._sock (socket).
        Wird beim Öffnen gespeichert, nicht erst beim Schließen gefischt.
        """
        try:
            fp = getattr(resp, 'fp', None)
            raw = getattr(fp, 'raw', fp)
            return getattr(raw, '_sock', None)
        except Exception:
            return None

    @staticmethod
    def _kill_stream(entry):
        """Beendet einen Stream ZUVERLÄSSIG.

        Wichtig: socket.shutdown() statt nur close()! close() auf dem
        BufferedReader unterbricht ein blockierendes recv() NICHT (und kann
        sich mit einem laufenden read() eines anderen Threads verklemmen).
        shutdown() reißt das recv() sofort auf — das war der Grund, warum
        der alte Code Verbindungen "geschlossen" hat, die munter weiterliefen.
        """
        cancel, resp, sock = entry
        try:
            cancel.set()
        except Exception:
            pass
        if sock is not None:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
        try:
            resp.close()
        except Exception:
            pass

    def _close_active(self, only_if_cancel=None):
        """Schließt aktive Upstream-Verbindungen (z.B. bei Seek/Stop)."""
        with self._active_lock:
            if only_if_cancel is not None:
                victims = [e for e in self._active_streams if e[0] is only_if_cancel]
                self._active_streams = [e for e in self._active_streams if e[0] is not only_if_cancel]
            else:
                victims = list(self._active_streams)
                self._active_streams = []
        for entry in victims:
            self._kill_stream(entry)

    def _trim_streams(self, keep_slots):
        """Killt die ältesten Streams, bis nur noch keep_slots aktiv sind."""
        with self._active_lock:
            victims = []
            while len(self._active_streams) > keep_slots:
                victims.append(self._active_streams.pop(0))
        for entry in victims:
            xbmc.log("[AHProxy-urllib] Closing oldest upstream stream to free a CDN slot", xbmc.LOGDEBUG)
            self._kill_stream(entry)
    
    def make_head(self, extra=None, timeout=15):
        if self._head_failed:
            xbmc.log("[AHProxy-urllib] Skipping HEAD request due to previous failure. Using GET Range 0-1.", xbmc.LOGINFO)
            return self._make_head_via_get(extra, timeout)
            
        req = self._build_request(self.url, extra)
        req.get_method = lambda: 'HEAD'
        xbmc.log(f"[AHProxy-urllib] HEAD {self.url[:120]}", xbmc.LOGINFO)
        try:
            # We enforce a short timeout (3s) for the HEAD request since a valid CDN should answer instantly
            head_timeout = min(timeout, 3)
            resp = urllib.request.urlopen(req, timeout=head_timeout, context=self._ssl_ctx)
            wrapped = _UrllibResponse(resp, total_size=self.total_size)
            xbmc.log(f"[AHProxy-urllib] HEAD Response: {resp.status}", xbmc.LOGINFO)
            return wrapped
        except Exception as e:
            self._head_failed = True
            xbmc.log(f"[AHProxy-urllib] HEAD failed ({e}). Falling back to GET Range 0-1.", xbmc.LOGWARNING)
            return self._make_head_via_get(extra, timeout)
            
    def _make_head_via_get(self, extra=None, timeout=15):
        try:
            fallback_extra = dict(extra) if extra else {}
            if 'Range' not in fallback_extra:
                fallback_extra['Range'] = 'bytes=0-1'
            req = self._build_request(self.url, fallback_extra)
            resp = urllib.request.urlopen(req, timeout=timeout, context=self._ssl_ctx)
            wrapped = _UrllibResponse(resp, total_size=self.total_size)
            
            # Fakes a classic HEAD response out of the partial GET
            if 'Content-Range' in wrapped.headers and '/' in wrapped.headers['Content-Range']:
                total = wrapped.headers['Content-Range'].split('/')[-1].strip()
                wrapped.headers['Content-Length'] = total
                if not extra or 'Range' not in extra:
                    wrapped.status_code = 200
                    del wrapped.headers['Content-Range']
            
            xbmc.log(f"[AHProxy-urllib] HEAD Fallback GET Response: {wrapped.status_code}", xbmc.LOGINFO)
            return wrapped
        except urllib.error.HTTPError as e2:
            xbmc.log(f"[AHProxy-urllib] HEAD Fallback GET HTTP Error: {e2.code}", xbmc.LOGWARNING)
            return _UrllibResponse(e2, total_size=self.total_size)
        except Exception as e2:
            xbmc.log(f"[AHProxy-urllib] HEAD Fallback GET Error: {e2}", xbmc.LOGWARNING)
            raise
    
    def make_get(self, extra=None, stream=True, timeout=STREAM_READ_TIMEOUT):
        # Nicht mehr ALLE alten Verbindungen killen (Kodi nutzt legitim 2
        # parallel: Daten-Stream + moov-Probe), sondern nur Platz für den
        # neuen Request schaffen, damit das CDN-Limit nicht überschritten
        # wird. Sonst stallt der Server den Body der überzähligen Verbindung
        # → Kodi wartet auf 0 Bytes → Hänger.
        range_hdr = (extra or {}).get('Range', 'none')
        range_start = None
        match = re.match(r'bytes=(\d+)-', range_hdr or '')
        if match:
            try:
                range_start = int(match.group(1))
            except Exception:
                range_start = None

        if range_start and range_start > 0:
            xbmc.log(
                f"[AHProxy-urllib] Seek Range={range_hdr}; closing old upstream streams first",
                xbmc.LOGINFO,
            )
            self._close_active()
        else:
            self._trim_streams(MAX_PARALLEL_UPSTREAMS - 1)
        # Dedicated cancel flag for this request.
        cancel_event = threading.Event()
        
        req = self._build_request(self.url, extra)
        xbmc.log(f"[AHProxy-urllib] GET {self.url[:100]} Range={range_hdr}", xbmc.LOGINFO)
        try:
            # timeout wirkt als Socket-Timeout für connect UND jedes recv():
            # ein Stream, der >15s lang NULL Bytes liefert, bricht ab und
            # Kodi verbindet neu — statt ewig zu blocken.
            resp = urllib.request.urlopen(req, timeout=timeout, context=self._ssl_ctx)
            
            sock = self._raw_sock(resp)
            with self._active_lock:
                self._active_streams.append((cancel_event, resp, sock))
            
            xbmc.log(
                f"[AHProxy-urllib] Response: {resp.status}, "
                f"Content-Length: {resp.headers.get('Content-Length', '?')}, "
                f"Content-Range: {resp.headers.get('Content-Range', 'none')}",
                xbmc.LOGINFO
            )
            return _UrllibResponse(resp, total_size=self.total_size, cancel_event=cancel_event)
        except urllib.error.HTTPError as e:
            xbmc.log(f"[AHProxy-urllib] HTTP Error: {e.code} {e.reason}", xbmc.LOGERROR)
            return _UrllibResponse(e, total_size=self.total_size)
        except Exception as e:
            # DNS-Fallback: Falls getaddrinfo fehlschlägt aber wir eine gecachte IP haben,
            # versuchen wir den Request über die IP mit gesetztem Host-Header neu.
            err_str = str(e).lower()
            if ('getaddrinfo' in err_str or 'nameresolution' in err_str or '11002' in err_str):
                parsed = urllib.parse.urlparse(self.url)
                host = parsed.hostname
                cached_ip = self._host_ip_map.get(host)
                if cached_ip:
                    xbmc.log(f"[AHProxy-urllib] DNS failed, retrying via cached IP {cached_ip}", xbmc.LOGWARNING)
                    try:
                        port = parsed.port or (443 if parsed.scheme == 'https' else 80)
                        path = parsed.path
                        if parsed.query:
                            path += '?' + parsed.query
                        import http.client
                        conn = http.client.HTTPSConnection(cached_ip, port, context=self._ssl_ctx, timeout=timeout)
                        req_headers = dict(req.headers)
                        req_headers['Host'] = host
                        range_val = (extra or {}).get('Range')
                        if range_val:
                            req_headers['Range'] = range_val
                        conn.request('GET', path, headers=req_headers)
                        raw_resp = conn.getresponse()
                        xbmc.log(f"[AHProxy-urllib] DNS-fallback response: {raw_resp.status}", xbmc.LOGINFO)
                        # Wrap in a urllib-compatible object
                        from urllib.response import addinfourl
                        import email.message
                        msg = email.message.Message()
                        for k, v in raw_resp.getheaders():
                            msg[k] = v
                        wrapped_resp = addinfourl(raw_resp, msg, self.url, raw_resp.status)
                        wrapped_resp.msg = raw_resp.reason
                        sock2 = getattr(conn, 'sock', None)
                        with self._active_lock:
                            self._active_streams.append((cancel_event, wrapped_resp, sock2))
                        return _UrllibResponse(wrapped_resp, total_size=self.total_size, cancel_event=cancel_event)
                    except Exception as e2:
                        xbmc.log(f"[AHProxy-urllib] DNS-fallback also failed: {e2}", xbmc.LOGERROR)
            xbmc.log(f"[AHProxy-urllib] Request failed: {e}", xbmc.LOGERROR)
            raise


class _UrllibResponse:
    """Wrapper um urllib-Response der das gleiche Interface wie requests.Response hat."""
    
    def __init__(self, resp, total_size=None, cancel_event=None):
        self._resp = resp
        self.total_size = total_size
        self._cancel = cancel_event
        if isinstance(resp, urllib.error.HTTPError):
            self.status_code = resp.code
            self.headers = dict(resp.headers)
        else:
            self.status_code = resp.status
            self.headers = dict(resp.headers)
    
    def iter_content(self, chunk_size=PROXY_CHUNK):
        """Yield chunks — checks cancel event between reads so seeks don't block."""
        read_fn = getattr(self._resp, "read1", self._resp.read)
        while True:
            if self._cancel and self._cancel.is_set():
                return
            try:
                chunk = read_fn(chunk_size)
            except socket.timeout:
                # Stream hat >STREAM_READ_TIMEOUT s nichts geliefert.
                # Abbrechen → Verbindung zu Kodi schließt → Kodi reconnected.
                xbmc.log("[AHProxy-urllib] Upstream read timeout, aborting stream so Kodi can reconnect", xbmc.LOGWARNING)
                return
            except Exception as e:
                if not (self._cancel and self._cancel.is_set()):
                    xbmc.log(f"[AHProxy-urllib] Upstream read aborted: {e}", xbmc.LOGDEBUG)
                return
            if not chunk:
                return
            yield chunk
    
    def probe_first_chunk(self, probe_timeout=5.0, chunk_size=PROXY_CHUNK):
        """Liest den ersten Body-Chunk mit kurzem Timeout.

        Rückgabe:
          bytes  -> erster Chunk (Stream fließt)
          None   -> Timeout, Body wird vom CDN gestallt (Slot belegt)
          b""    -> EOF/Fehler
        """
        sock = _UrllibUpstream._raw_sock(self._resp)
        old_timeout = None
        if sock is not None:
            try:
                old_timeout = sock.gettimeout()
                sock.settimeout(probe_timeout)
            except Exception:
                sock = None
        try:
            read_fn = getattr(self._resp, "read1", self._resp.read)
            chunk = read_fn(chunk_size)
            return chunk if chunk else b""
        except socket.timeout:
            # SocketIO setzt nach einem Timeout intern _timeout_occurred und
            # verweigert danach JEDES Lesen ("cannot read from timed out
            # object") — obwohl die Verbindung noch lebt. Flag zurücksetzen,
            # damit wir auf derselben Verbindung weiter warten können.
            try:
                raw = getattr(getattr(self._resp, 'fp', None), 'raw', None)
                if raw is not None and getattr(raw, '_timeout_occurred', False):
                    raw._timeout_occurred = False
            except Exception:
                pass
            return None
        except Exception:
            return b""
        finally:
            if sock is not None:
                try:
                    sock.settimeout(old_timeout if old_timeout else STREAM_READ_TIMEOUT)
                except Exception:
                    pass

    def close(self):
        try:
            self._resp.close()
        except Exception:
            pass


# =============================================================================
# requests-basierter Upstream (Original, für andere Websites)
# =============================================================================

class _Upstream:
    def __init__(
        self,
        url,
        headers=None,
        cookies=None,
        session=None,
        skip_resolve=False,
    ):
        self.original_url = url
        self.resolved_url = None
        self.total_size = None
        xbmc.log(f"[AHProxy] Upstream URL: {url[:200]}", xbmc.LOGINFO)

        if session is not None:
            self.session = session
        else:
            if _HAS_CF:
                self.session = cloudscraper.create_scraper(browser={'custom': _DEFAULT_UA})
            else:
                self.session = requests.Session()

        try:
            if hasattr(self.session, "headers") and isinstance(self.session.headers, dict):
                self.session.headers.setdefault("User-Agent", _DEFAULT_UA)
                self.session.headers.setdefault("Connection", "keep-alive")
                self.session.headers.setdefault("Accept-Encoding", "identity")
                self.session.headers.setdefault("Accept-Language", "en-US,en;q=0.9")

            if headers:
                self.session.headers.update(headers)

            if cookies and hasattr(self.session, "cookies"):
                try:
                    self.session.cookies.update(cookies)
                except Exception:
                    pass
            
            # Mask cookies for logging
            clean_cookies = {k: '***' for k in cookies} if cookies else {}
            xbmc.log(f"[AHProxy] Session initialized with cookies: {clean_cookies}", xbmc.LOGDEBUG)
            xbmc.log(f"[AHProxy] Session headers: {self.session.headers}", xbmc.LOGDEBUG)
        except Exception:
            pass

        if not skip_resolve:
            self._resolve_url()
        else:
            xbmc.log("[AHProxy] Skipping URL resolution (skip_resolve=True)", xbmc.LOGINFO)

    def _resolve_url(self):
        try:
            xbmc.log("[AHProxy] Checking if URL needs resolution...", xbmc.LOGINFO)
            try:
                head_resp = self.session.head(self.original_url, timeout=5, allow_redirects=True)
                content_type = head_resp.headers.get('Content-Type', '').lower()
                if 'video/' in content_type or 'octet-stream' in content_type:
                    xbmc.log("[AHProxy] HEAD shows video content, no resolution needed", xbmc.LOGINFO)
                    cl = head_resp.headers.get('Content-Length')
                    if cl:
                        self.total_size = int(cl)
                    return
            except Exception:
                pass
            
            resp = self.session.get(self.original_url, timeout=10, stream=False)
            
            content_type = resp.headers.get('Content-Type', '').lower()
            xbmc.log(f"[AHProxy] Initial response: status={resp.status_code}, content-type={content_type}", xbmc.LOGINFO)
            
            if 'application/json' in content_type:
                xbmc.log("[AHProxy] URL returns JSON, parsing...", xbmc.LOGINFO)
                try:
                    data = resp.json()
                    xbmc.log(f"[AHProxy] JSON type: {type(data)}, length: {len(data) if isinstance(data, (list, dict)) else 'N/A'}", xbmc.LOGINFO)
                    xbmc.log(f"[AHProxy] JSON data: {str(data)[:500]}", xbmc.LOGINFO)
                    
                    video_url = None
                    
                    if isinstance(data, str) and data.startswith('http'):
                        video_url = data
                    elif isinstance(data, list) and len(data) > 0:
                        best = None
                        default_found = False
                        
                        for item in data:
                            if not isinstance(item, dict):
                                continue
                            
                            if item.get('defaultQuality') is True:
                                best = item
                                default_found = True
                                xbmc.log(f"[AHProxy] Found default quality: {item.get('quality')}", xbmc.LOGINFO)
                                break
                            
                            if not default_found:
                                try:
                                    current_q = int(str(item.get('quality', '0')))
                                    best_q = int(str(best.get('quality', '0'))) if best else 0
                                    if current_q > best_q:
                                        best = item
                                except (ValueError, TypeError):
                                    if not best:
                                        best = item
                        
                        if best and 'videoUrl' in best:
                            video_url = best['videoUrl']
                            xbmc.log(f"[AHProxy] Selected quality: {best.get('quality')}", xbmc.LOGINFO)
                    elif isinstance(data, dict) and 'url' in data:
                        video_url = data['url']
                    elif isinstance(data, dict) and 'videoUrl' in data:
                        video_url = data['videoUrl']
                    elif isinstance(data, dict):
                        for key in ['video', 'media', 'file', 'source']:
                            if key in data:
                                val = data[key]
                                if isinstance(val, str) and val.startswith('http'):
                                    video_url = val
                                    break
                                elif isinstance(val, dict) and 'url' in val:
                                    video_url = val['url']
                                    break
                    
                    if video_url:
                        xbmc.log(f"[AHProxy] Resolved video URL: {video_url[:200]}", xbmc.LOGINFO)
                        self.resolved_url = video_url
                        return
                    else:
                        xbmc.log(f"[AHProxy] Could not find video URL in JSON. Data type: {type(data)}", xbmc.LOGWARNING)
                        if isinstance(data, list) and len(data) > 0:
                            xbmc.log(f"[AHProxy] First item keys: {list(data[0].keys()) if isinstance(data[0], dict) else 'not a dict'}", xbmc.LOGWARNING)
                except Exception as e:
                    xbmc.log(f"[AHProxy] JSON parsing error: {e}", xbmc.LOGERROR)
            else:
                xbmc.log("[AHProxy] URL returns video directly", xbmc.LOGINFO)
        except Exception as e:
            xbmc.log(f"[AHProxy] URL resolution error: {e}", xbmc.LOGWARNING)

    @property
    def url(self):
        return self.resolved_url or self.original_url

    def make_head(self, extra=None, timeout=15):
        h = dict(getattr(self.session, "headers", {}) or {})
        if extra:
            h.update(extra)
        resp = self.session.head(self.url, headers=h, allow_redirects=True, timeout=timeout)
        if resp.url != self.url:
            self.resolved_url = resp.url
            xbmc.log(f"[AHProxy] Dynamically resolved redirected URL via HEAD: {self.resolved_url}", xbmc.LOGINFO)
        return resp

    def make_get(self, extra=None, stream=True, timeout=60):
        h = dict(getattr(self.session, "headers", {}) or {})
        if extra:
            h.update(extra)
        xbmc.log(f"[AHProxy] GET request to {self.url[:100]} (stream={stream})", xbmc.LOGINFO)
        last_error = None
        for attempt in range(1, 4):
            try:
                resp = self.session.get(self.url, headers=h, allow_redirects=True, stream=stream, timeout=timeout)
                xbmc.log(f"[AHProxy] Response status: {resp.status_code}, Content-Type: {resp.headers.get('Content-Type')}", xbmc.LOGINFO)
                if resp.url != self.url:
                    self.resolved_url = resp.url
                    xbmc.log(f"[AHProxy] Dynamically resolved redirected URL via GET: {self.resolved_url}", xbmc.LOGINFO)
                return resp
            except Exception as e:
                last_error = e
                xbmc.log(f"[AHProxy] GET request failed attempt {attempt}/3: {e}", xbmc.LOGWARNING if attempt < 3 else xbmc.LOGERROR)
                if attempt < 3:
                    xbmc.sleep(500 * attempt)
        raise last_error


# =============================================================================
# Proxy Handler (unterstützt beide Upstream-Typen)
# =============================================================================

class _ProxyHandler(BaseHTTPRequestHandler):
    server_version = "AHProxy/2.0"
    upstream = None 
    controller = None

    def log_message(self, fmt, *args):
        return 

    def _extract_range(self):
        rng = self.headers.get("Range")
        return rng if rng else None

    def _infer_origin(self):
        if isinstance(self.upstream, _UrllibUpstream):
            ref = self.upstream.headers.get("Referer", "")
        else:
            try:
                ref = getattr(self.upstream.session, "headers", {}).get("Referer")
            except Exception:
                ref = None
        if not ref:
            return None
        try:
            pu = urllib.parse.urlparse(ref)
            if pu.scheme and pu.netloc:
                return f"{pu.scheme}://{pu.netloc}"
        except Exception:
            return None
        return None

    def _extra_browser_headers(self):
        if isinstance(self.upstream, _UrllibUpstream):
            src = self.upstream.headers
        else:
            src = getattr(self.upstream.session, "headers", {}) or {}
        
        extra = {
            "Accept-Encoding": "identity",
            "Sec-Fetch-Site": src.get("Sec-Fetch-Site", "cross-site"),
            "Sec-Fetch-Mode": src.get("Sec-Fetch-Mode", "cors"),
            "Sec-Fetch-Dest": src.get("Sec-Fetch-Dest", "video"),
        }
        origin = self._infer_origin()
        if origin:
            extra["Origin"] = origin
        return extra

    def _write_head_from_upstream(self, rsp, force_accept_ranges=True):
        status = getattr(rsp, "status_code", 502)
        self.send_response(status)
        
        hop_by_hop = {
            "transfer-encoding", "connection", "proxy-authenticate", "proxy-authorization",
            "te", "trailer", "upgrade", "keep-alive",
        }
        
        has_accept_ranges = False
        has_content_length = False
        
        for k, v in getattr(rsp, "headers", {}).items():
            lk = k.lower()
            if lk in hop_by_hop:
                continue
            if lk in ("content-length", "content-type", "accept-ranges", "content-range", "etag", "last-modified"):
                self.send_header(k, v)
                if lk == "accept-ranges":
                    has_accept_ranges = True
                if lk == "content-length":
                    has_content_length = True
        
        # KRITISCH: Accept-Ranges immer setzen damit Kodi weiß dass Seeks möglich sind
        if force_accept_ranges and not has_accept_ranges:
            self.send_header("Accept-Ranges", "bytes")
        
        # Falls Content-Length fehlt aber wir die Gesamtgröße kennen (200er Response)
        total = getattr(rsp, 'total_size', None) or getattr(self.upstream, 'total_size', None)
        if not has_content_length and total and status == 200:
            self.send_header("Content-Length", str(total))
        
        self.send_header("Cache-Control", "no-store")
        self.send_header("Pragma", "no-cache")

    def handle(self):
        # Wenn der Server herunterfährt, lehne jede Anfrage sofort ab
        if getattr(self.server, '_shutting_down', False):
            try:
                self.send_response(503)
                self.end_headers()
            except Exception:
                pass
            return
        super().handle()

    def do_HEAD(self):
        if getattr(self.server, '_shutting_down', False):
            self.send_error(503, "Service shutting down")
            return
        extra = self._extra_browser_headers()
        rng = self._extract_range()
        if rng:
            extra["Range"] = rng
        try:
            rsp = self.upstream.make_head(extra=extra)
            self._write_head_from_upstream(rsp)
            self.end_headers()
        except Exception as e:
            xbmc.log(f"[AHProxy] HEAD error: {e}", xbmc.LOGERROR)
            self.send_error(502, f"Upstream error: {e}")

    def _upstream_get_async(self, extra, result_holder):
        """
        Ruft make_get() in einem Background-Thread auf und legt das Ergebnis
        in result_holder ab. So können wir parallel dazu Keep-Alive-Chunks
        an Kodi schicken während das CDN trödelt.
        """
        try:
            result_holder["response"] = self.upstream.make_get(extra=extra, stream=True)
        except Exception as e:
            result_holder["error"] = e

    def _write_chunked(self, data):
        """Schreibt einen HTTP/1.1 chunked-transfer Chunk."""
        if not data:
            return
        # ACHTUNG: hier müssen ECHTE CRLF-Bytes raus (\r\n) — vorher standen
        # hier doppelt escapte Literale (Backslash-r-Backslash-n), was
        # ungültiges chunked-Framing erzeugt hat.
        self.wfile.write(f"{len(data):X}\r\n".encode("ascii"))
        self.wfile.write(data)
        self.wfile.write(b"\r\n")
        self.wfile.flush()

    def _write_chunked_terminator(self):
        """Schreibt das Ende eines chunked-transfer Streams."""
        try:
            self.wfile.write(b"0\r\n\r\n")
            self.wfile.flush()
        except Exception:
            pass

    def do_GET(self):
        """
        GET-Handler der libcurl's 20-Sekunden Low-Speed-Timeout umgeht.
        """
        if getattr(self.server, '_shutting_down', False):
            self.send_error(503, "Service shutting down")
            return
            
        extra = self._extra_browser_headers()
        rng = self._extract_range()

        if rng:
            extra["Range"] = rng
            xbmc.log(f"[AHProxy] Kodi requested Range: {rng}", xbmc.LOGINFO)

        rsp = None
        first_chunk = b""
        client_disconnected = False
        headers_committed = False
        use_chunked = False

        try:
            # --- Schritt 1: Upstream-GET asynchron starten ---
            result_holder = {}
            upstream_thread = threading.Thread(
                target=self._upstream_get_async,
                args=(extra, result_holder),
                name="AHProxyUpstreamGET",
                daemon=True,
            )
            upstream_thread.start()

            # --- Schritt 2: Kurze Wartezeit für "schnelles" CDN ---
            # Die meisten CDNs antworten in < 5s. Nur wenn das CDN langsamer ist,
            # kommen wir in den Keep-Alive-Modus mit Chunked-Encoding.
            FAST_WAIT = 8.0
            upstream_thread.join(timeout=FAST_WAIT)

            if not upstream_thread.is_alive():
                # CDN hat schnell genug geantwortet — normaler Pfad ohne Chunked
                if "error" in result_holder:
                    raise result_holder["error"]
                rsp = result_holder.get("response")
                if rsp is None:
                    raise RuntimeError("Upstream thread returned no response")

                # First-Byte-Check (nur urllib-Upstream)
                first_chunk = b""
                if (isinstance(self.upstream, _UrllibUpstream)
                        and getattr(rsp, "status_code", 0) in (200, 206)
                        and hasattr(rsp, "probe_first_chunk")):
                    probed = None
                    for probe_timeout in (5.0, 6.0):
                        if getattr(self.server, '_shutting_down', False):
                            return
                        probed = rsp.probe_first_chunk(probe_timeout=probe_timeout)
                        if probed or probed == b"":
                            break
                        xbmc.log(
                            f"[AHProxy] Body still stalled after {probe_timeout:.0f}s "
                            f"(Range={rng}), waiting on same connection",
                            xbmc.LOGWARNING,
                        )
                    if probed is None:
                        xbmc.log(
                            f"[AHProxy] Body stalled (CDN slot race) for Range={rng}, "
                            f"reconnecting upstream once",
                            xbmc.LOGWARNING,
                        )
                        try:
                            cancel_ev = getattr(rsp, "_cancel", None)
                            if cancel_ev is not None:
                                self.upstream._close_active(only_if_cancel=cancel_ev)
                            rsp.close()
                        except Exception:
                            pass
                        if getattr(self.server, '_shutting_down', False):
                            return
                        rsp = self.upstream.make_get(extra=extra, stream=True)
                        if getattr(rsp, "status_code", 0) in (200, 206):
                            probed = rsp.probe_first_chunk(probe_timeout=5.0)
                    if probed:
                        first_chunk = probed

                if getattr(self.server, '_shutting_down', False):
                    return

                self._write_head_from_upstream(rsp)
                self.end_headers()
                headers_committed = True
                use_chunked = False
                xbmc.log(f"[AHProxy] Fast CDN response ({FAST_WAIT}s), normal streaming", xbmc.LOGDEBUG)
            else:
                # CDN ist langsam. Wir committen JETZT zu chunked Headers damit
                # libcurl's Timer nicht 20s leer läuft.
                status = 206 if rng else 200
                self.send_response(status)

                # Standard-Header für Video-Streaming
                self.send_header("Content-Type", "video/mp4")
                self.send_header("Accept-Ranges", "bytes")
                self.send_header("Transfer-Encoding", "chunked")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Connection", "close")
                if status == 206 and rng:
                    total = getattr(self.upstream, 'total_size', None)
                    m = re.match(r'bytes=(\d+)-(\d*)', rng)
                    if m:
                        start = int(m.group(1))
                        end = int(m.group(2)) if m.group(2) else (total - 1 if total else start + 10 * 1024 * 1024)
                        total_str = str(total) if total else "*"
                        self.send_header("Content-Range", f"bytes {start}-{end}/{total_str}")
                self.end_headers()
                headers_committed = True
                use_chunked = True

                xbmc.log(
                    f"[AHProxy] Slow CDN detected (>{FAST_WAIT}s), committed to chunked streaming with status {status}",
                    xbmc.LOGINFO,
                )

                # --- Schritt 3: Keep-Alive-Chunks schicken bis CDN antwortet ---
                PING_INTERVAL = 2.0
                MAX_WAIT = 45.0
                waited = FAST_WAIT
                pings_sent = 0

                range_start = 0
                if rng:
                    m0 = re.match(r'bytes=(\d+)-', rng)
                    if m0:
                        range_start = int(m0.group(1))
                allow_padding = (range_start == 0)
                if not allow_padding:
                    xbmc.log("[AHProxy] Mid-file range, keep-alive padding disabled", xbmc.LOGDEBUG)

                while waited < MAX_WAIT:
                    if getattr(self.server, '_shutting_down', False):
                        return
                    upstream_thread.join(timeout=PING_INTERVAL)
                    if not upstream_thread.is_alive():
                        break
                    waited += PING_INTERVAL
                    if not allow_padding:
                        continue
                    try:
                        self._write_chunked(b"\x00")
                        pings_sent += 1
                        xbmc.log(
                            f"[AHProxy] Keep-alive chunk #{pings_sent} sent (waited {waited:.0f}s for CDN)",
                            xbmc.LOGDEBUG,
                        )
                    except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, socket.error) as e:
                        client_disconnected = True
                        xbmc.log(
                            f"[AHProxy] Kodi disconnected during CDN wait (after {waited:.0f}s, {pings_sent} chunks): {e}",
                            xbmc.LOGDEBUG,
                        )
                        if hasattr(self.upstream, "_close_active"):
                            try:
                                self.upstream._close_active()
                            except Exception:
                                pass
                        return

                if upstream_thread.is_alive():
                    xbmc.log(
                        f"[AHProxy] Upstream timeout after {MAX_WAIT}s",
                        xbmc.LOGERROR,
                    )
                    self._write_chunked_terminator()
                    if hasattr(self.upstream, "_close_active"):
                        try:
                            self.upstream._close_active()
                        except Exception:
                            pass
                    return

                if "error" in result_holder:
                    raise result_holder["error"]
                rsp = result_holder.get("response")
                if rsp is None:
                    raise RuntimeError("Upstream thread returned no response after wait")

                xbmc.log(
                    f"[AHProxy] CDN responded after {waited:.0f}s and {pings_sent} keep-alive chunks",
                    xbmc.LOGINFO,
                )

            status = getattr(rsp, "status_code", 0)

            # Chunk-Size: klein für urllib (Seek-Performance), normal für requests
            if isinstance(self.upstream, _UrllibUpstream):
                chunk_size = PROXY_CHUNK  # 32 KB
            else:
                chunk_size = DEFAULT_CHUNK  # 512 KB

            if status in (200, 206):
                bytes_sent = 0
                chunk_count = 0

                def _all_chunks():
                    if first_chunk:
                        yield first_chunk
                    for c in rsp.iter_content(chunk_size=chunk_size):
                        if getattr(self.server, '_shutting_down', False):
                            break
                        yield c

                try:
                    for chunk in _all_chunks():
                        if not chunk:
                            continue
                        try:
                            if use_chunked:
                                self._write_chunked(chunk)
                            else:
                                self.wfile.write(chunk)
                                if chunk_count <= 4 or chunk_count % 4 == 0:
                                    self.wfile.flush()
                            bytes_sent += len(chunk)
                            chunk_count += 1

                            # Aktivität tracken
                            if self.controller:
                                self.controller.last_activity = time.time()

                            if chunk_count == 1:
                                xbmc.log(
                                    f"[AHProxy] First chunk sent: {bytes_sent} bytes "
                                    f"(Range={rng}, chunked={use_chunked})",
                                    xbmc.LOGINFO,
                                )
                        except (
                            BrokenPipeError,
                            ConnectionResetError,
                            ConnectionAbortedError,
                            socket.error,
                        ) as e:
                            client_disconnected = True
                            xbmc.log(
                                f"[AHProxy] Client disconnected after {bytes_sent} bytes "
                                f"(Range={rng}): {e}. Expected for MP4 seeks.",
                                xbmc.LOGDEBUG,
                            )
                            break
                    if not client_disconnected:
                        if bytes_sent == 0:
                            xbmc.log(
                                f"[AHProxy] Upstream delivered 0 bytes for Range={rng} "
                                f"(CDN slot stalled or connection killed) — closing so Kodi retries",
                                xbmc.LOGERROR,
                            )
                            self.close_connection = True
                        else:
                            xbmc.log(f"[AHProxy] Stream complete: {bytes_sent} bytes", xbmc.LOGINFO)
                except Exception as e:
                    xbmc.log(f"[AHProxy] Stream iteration error after {bytes_sent} bytes: {e}", xbmc.LOGERROR)
            else:
                xbmc.log(f"[AHProxy] Unexpected status code: {status}", xbmc.LOGWARNING)
                try:
                    body = b""
                    for chunk in rsp.iter_content(chunk_size=4096):
                        body += chunk
                        if len(body) > 2048:
                            break
                    xbmc.log(f"[AHProxy] Error body: {body[:500].decode('utf-8', errors='replace')}", xbmc.LOGWARNING)
                except Exception:
                    pass

            if use_chunked and not client_disconnected:
                try:
                    self._write_chunked_terminator()
                except Exception:
                    pass

        except Exception as e:
            xbmc.log(f"[AHProxy] GET error: {e}", xbmc.LOGERROR)
            if not headers_committed:
                try:
                    self.send_error(502, f"Upstream error: {e}")
                except Exception:
                    pass
            elif use_chunked:
                try:
                    self._write_chunked_terminator()
                except Exception:
                    pass
        finally:
            if rsp is not None:
                try:
                    rsp.close()
                except Exception:
                    pass

            if hasattr(self.upstream, "_close_active"):
                try:
                    cancel_ev = getattr(rsp, "_cancel", None)
                    if cancel_ev is not None:
                        self.upstream._close_active(only_if_cancel=cancel_ev)
                except Exception:
                    pass

            if client_disconnected:
                self.close_connection = True


class _HTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._client_socks = set()
        self._client_lock = threading.Lock()
        self._shutting_down = False

    def process_request(self, request, client_address):
        with self._client_lock:
            self._client_socks.add(request)
        super().process_request(request, client_address)

    def shutdown_request(self, request):
        with self._client_lock:
            self._client_socks.discard(request)
        super().shutdown_request(request)

    def close_all_clients(self):
        """Kappt alle offenen Client-Verbindungen sofort (für stop())."""
        with self._client_lock:
            socks = list(self._client_socks)
            self._client_socks.clear()
            
        for sock in socks:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            try:
                sock.close()
            except Exception:
                pass


class ProxyController:
    def __init__(
        self,
        upstream_url,
        upstream_headers=None,
        cookies=None,
        session=None,
        host="127.0.0.1",
        port=0,
        skip_resolve=False,
        use_urllib=False,
        probe_size=True,
    ):
        if use_urllib:
            self.up = _UrllibUpstream(
                upstream_url,
                headers=upstream_headers,
                cookies=cookies,
                probe_size=probe_size,
            )
        else:
            self.up = _Upstream(
                upstream_url,
                headers=upstream_headers,
                cookies=cookies,
                session=session,
                skip_resolve=skip_resolve,
            )
        self.host = host
        self.port = port
        self.httpd = None
        self.thread = None
        self.local_url = None
        self.last_activity = time.time()

    def is_active(self, idle_seconds=15.0):
        """Liefert True, wenn der Proxy in den letzten idle_seconds Daten gesendet hat."""
        return (time.time() - self.last_activity) < idle_seconds

    def start(self):
        def _handler_factory(upstream_obj, controller_obj):
            class _H(_ProxyHandler):
                upstream = upstream_obj
                controller = controller_obj
            return _H

        self.httpd = _HTTPServer((self.host, self.port), _handler_factory(self.up, self))
        if self.port == 0:
            self.port = self.httpd.server_port
        self.thread = threading.Thread(target=self.httpd.serve_forever, name="AHProxyThread", daemon=True)
        self.thread.start()
        self.local_url = f"http://{self.host}:{self.port}/stream"
        xbmc.log(f"[AHProxy] Started on {self.local_url}", xbmc.LOGINFO)
        return self.local_url

    def stop(self, timeout=1.0):
        try:
            if self.httpd:
                # 1. Zuerst das shutting_down Flag setzen
                self.httpd._shutting_down = True
                
                # 2. Dann die accept()-Schleife beenden
                try:
                    self.httpd.shutdown()
                except:
                    pass
                
                # 3. Jetzt alle offenen Clients kappen
                try:
                    if hasattr(self.httpd, 'close_all_clients'):
                        self.httpd.close_all_clients()
                except Exception as e:
                    xbmc.log(f"[AHProxy] Error closing clients: {e}", xbmc.LOGDEBUG)
                
                # 4. Den Server schließen
                try:
                    self.httpd.server_close()
                except:
                    pass
                xbmc.log("[AHProxy] Stopped", xbmc.LOGINFO)
        except Exception as e:
            xbmc.log(f"[AHProxy] Error during stop: {e}", xbmc.LOGDEBUG)
        
        if hasattr(self.up, '_close_active'):
            self.up._close_active()
            
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=timeout)


class PlaybackGuard(threading.Thread):
    def __init__(self, kodi_player, monitor, target_path, controller, idle_timeout=60 * 60):
        super(PlaybackGuard, self).__init__(name="AHProxyGuard", daemon=True)
        self.player = kodi_player
        self.monitor = monitor
        self.target = target_path
        self.ctrl = controller
        self.idle_timeout = idle_timeout

    def run(self):
        start_ts = time.time()
        target_started = False
        
        # Maximal 180 Sekunden auf den Start warten (für sehr langsame CDNs)
        MAX_STARTUP_WAIT = 180

        while not self.monitor.abortRequested():
            elapsed = time.time() - start_ts
            proxy_active = self.ctrl.is_active(15.0) if hasattr(self.ctrl, 'is_active') else False
            
            if elapsed > MAX_STARTUP_WAIT:
                xbmc.log(f"[AHProxy] Timed out waiting for target: {self.target} (elapsed {elapsed:.0f}s)", xbmc.LOGWARNING)
                break
                
            # Wenn wir nach 30 Sekunden noch keine Wiedergabe haben UND der Proxy
            # seit 15 Sekunden keine Daten mehr geliefert hat, brechen wir ab.
            if elapsed > 30 and not proxy_active:
                xbmc.log(f"[AHProxy] Proxy inactive for 15s during startup wait, giving up (elapsed {elapsed:.0f}s)", xbmc.LOGWARNING)
                break

            if hasattr(self.player, 'isPlayingVideo') and self.player.isPlayingVideo():
                try:
                    current_file = self.player.getPlayingFile() if hasattr(self.player, 'getPlayingFile') else ""
                except Exception:
                    current_file = ""
                
                if current_file:
                    if int(time.time() - start_ts) % 5 == 0:
                        xbmc.log(f"[AHProxy-Guard] Current: {current_file[:120]}, Target: {self.target[:120]}", xbmc.LOGDEBUG)

                if (self.target == current_file) or (self.target and current_file and (self.target in current_file or current_file in self.target)):
                    target_started = True
                    xbmc.log(f"[AHProxy] Playback detected for {self.target} after {elapsed:.1f}s", xbmc.LOGINFO)
                    break
            
            self.monitor.waitForAbort(0.5)

        if not target_started:
            try:
                xbmc.log(f"[AHProxy] Guard stopping proxy for {self.target} (target not started)", xbmc.LOGWARNING)
                self.ctrl.stop()
            except Exception:
                pass
            return

        while not self.monitor.abortRequested():
            if hasattr(self.player, 'isPlayingVideo') and not self.player.isPlayingVideo():
                break
            
            try:
                current_file = self.player.getPlayingFile() if hasattr(self.player, 'getPlayingFile') else ""
            except Exception:
                current_file = ""
            
            if current_file != self.target:
                xbmc.log(f"[AHProxy] Player switched to {current_file}, stopping proxy for {self.target}", xbmc.LOGINFO)
                break
                
            if time.time() - start_ts > self.idle_timeout:
                break
                
            self.monitor.waitForAbort(1.0)

        try:
            self.ctrl.stop()
        except Exception:
            pass


class _HlsProxyHandler(BaseHTTPRequestHandler):
    server_version = "AHHlsProxy/1.0"
    controller = None

    def log_message(self, fmt, *args):
        return

    def handle(self):
        if getattr(self.server, '_shutting_down', False):
            try:
                self.send_response(503)
                self.end_headers()
            except Exception:
                pass
            return
        super().handle()

    def do_GET(self):
        if getattr(self.server, '_shutting_down', False):
            self.send_error(503, "Service shutting down")
            return
            
        if self.controller:
            self.controller.last_activity = time.time()

        parsed = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed.query)
        
        headers = {
            "User-Agent": _DEFAULT_UA,
            "Referer": "https://88z.io/",
            "Origin": "https://88z.io",
        }
        
        try:
            if parsed.path == "/playlist.m3u8":
                url = query.get("url")[0]
                res = requests.get(url, headers=headers, timeout=12)
                lines = []
                for line in res.text.splitlines():
                    if line.strip() and not line.startswith("#"):
                        segment_url = urllib.parse.urljoin(url, line.strip())
                        proxy_segment_url = "http://127.0.0.1:{}/segment?url={}".format(
                            self.server.server_address[1],
                            urllib.parse.quote_plus(segment_url)
                        )
                        lines.append(proxy_segment_url)
                    else:
                        lines.append(line)
                
                content = "\n".join(lines).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/vnd.apple.mpegurl")
                self.send_header("Content-Length", str(len(content)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(content)
                
            elif parsed.path == "/segment":
                url = query.get("url")[0]
                res = requests.get(url, headers=headers, stream=True, timeout=15)
                self.send_response(200)
                self.send_header("Content-Type", "video/mp2t")
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                
                first_chunk_read = False
                for chunk in res.iter_content(chunk_size=PROXY_CHUNK):
                    if getattr(self.server, '_shutting_down', False):
                        break
                    if not first_chunk_read:
                        first_chunk_read = True
                        if chunk.startswith(b"\x89PNG"):
                            chunk = chunk[120:]
                    if chunk:
                        try:
                            self.wfile.write(chunk)
                        except Exception:
                            break
            else:
                self.send_error(404, "Not Found")
        except Exception as e:
            xbmc.log(f"[AHHlsProxy] Handler error for {self.path}: {e}", xbmc.LOGERROR)
            try:
                self.send_error(502, f"Proxy error: {e}")
            except Exception:
                pass


class HlsProxyController:
    def __init__(self, master_playlist_url, host="127.0.0.1", port=0):
        self.master_url = master_playlist_url
        self.host = host
        self.port = port
        self.httpd = None
        self.thread = None
        self.local_url = None
        self.last_activity = time.time()

    def is_active(self, idle_seconds=15.0):
        return (time.time() - self.last_activity) < idle_seconds

    def start(self):
        def _handler_factory(controller_obj):
            class _H(_HlsProxyHandler):
                controller = controller_obj
            return _H

        self.httpd = _HTTPServer((self.host, self.port), _handler_factory(self))
        if self.port == 0:
            self.port = self.httpd.server_port
        self.thread = threading.Thread(target=self.httpd.serve_forever, name="AHHlsProxyThread", daemon=True)
        self.thread.start()
        self.local_url = "http://{}:{}/playlist.m3u8?url={}".format(
            self.host, self.port, urllib.parse.quote_plus(self.master_url)
        )
        xbmc.log(f"[AHHlsProxy] Started on {self.local_url}", xbmc.LOGINFO)
        return self.local_url

    def stop(self, timeout=1.0):
        try:
            if self.httpd:
                self.httpd._shutting_down = True
                try:
                    self.httpd.shutdown()
                except:
                    pass
                try:
                    if hasattr(self.httpd, 'close_all_clients'):
                        self.httpd.close_all_clients()
                except Exception as e:
                    xbmc.log(f"[AHHlsProxy] Error closing clients: {e}", xbmc.LOGDEBUG)
                try:
                    self.httpd.server_close()
                except:
                    pass
                xbmc.log("[AHHlsProxy] Stopped", xbmc.LOGINFO)
        except Exception as e:
            xbmc.log(f"[AHHlsProxy] Error during stop: {e}", xbmc.LOGDEBUG)
        
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=timeout)
