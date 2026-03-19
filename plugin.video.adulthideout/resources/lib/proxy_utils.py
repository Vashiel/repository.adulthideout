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
    
    def __init__(self, url, headers=None, cookies=None):
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
        
        # Tracking der aktiven Verbindung für sauberes Cleanup bei Seek
        self._active_resp = None
        self._active_lock = threading.Lock()
        self._cancel_event = threading.Event()
        
        # Gesamtgröße der Datei (per HEAD ermittelt)
        self.total_size = None
        self._head_failed = False
        
        xbmc.log(f"[AHProxy-urllib] Upstream URL: {url[:200]}", xbmc.LOGINFO)
        
        # HEAD-Request um Dateigröße zu ermitteln (Kodi braucht das für Seeks)
        self._probe_size()

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
    
    def _close_active(self):
        """Schließt die aktive Upstream-Verbindung (z.B. bei Seek)."""
        # Signal any running iter_content to stop immediately
        self._cancel_event.set()
        with self._active_lock:
            if self._active_resp is not None:
                try:
                    # Close the underlying socket to unblock any pending read()
                    raw = getattr(self._active_resp, 'fp', None)
                    if raw:
                        raw_sock = getattr(raw, 'raw', getattr(raw, '_sock', None))
                        if raw_sock:
                            try:
                                raw_sock.close()
                            except Exception:
                                pass
                    self._active_resp.close()
                except Exception:
                    pass
                self._active_resp = None
    
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
    
    def make_get(self, extra=None, stream=True, timeout=60):
        # Alte Verbindung schließen — gibt Bandbreite frei für den neuen Request!
        self._close_active()
        # Reset cancel flag for the new request
        self._cancel_event.clear()
        
        req = self._build_request(self.url, extra)
        range_hdr = (extra or {}).get('Range', 'none')
        xbmc.log(f"[AHProxy-urllib] GET {self.url[:100]} Range={range_hdr}", xbmc.LOGINFO)
        try:
            resp = urllib.request.urlopen(req, timeout=timeout, context=self._ssl_ctx)
            
            with self._active_lock:
                self._active_resp = resp
            
            xbmc.log(
                f"[AHProxy-urllib] Response: {resp.status}, "
                f"Content-Length: {resp.headers.get('Content-Length', '?')}, "
                f"Content-Range: {resp.headers.get('Content-Range', 'none')}",
                xbmc.LOGINFO
            )
            return _UrllibResponse(resp, total_size=self.total_size, cancel_event=self._cancel_event)
        except urllib.error.HTTPError as e:
            xbmc.log(f"[AHProxy-urllib] HTTP Error: {e.code} {e.reason}", xbmc.LOGERROR)
            return _UrllibResponse(e, total_size=self.total_size)
        except Exception as e:
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
        try:
            while True:
                if self._cancel and self._cancel.is_set():
                    return
                try:
                    chunk = self._resp.read(chunk_size)
                except (OSError, Exception):
                    return
                if not chunk:
                    break
                yield chunk
        except Exception:
            return
    
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
        return self.session.head(self.url, headers=h, allow_redirects=True, timeout=timeout)

    def make_get(self, extra=None, stream=True, timeout=60):
        h = dict(getattr(self.session, "headers", {}) or {})
        if extra:
            h.update(extra)
        xbmc.log(f"[AHProxy] GET request to {self.url[:100]} (stream={stream})", xbmc.LOGINFO)
        try:
            resp = self.session.get(self.url, headers=h, allow_redirects=True, stream=stream, timeout=timeout)
            xbmc.log(f"[AHProxy] Response status: {resp.status_code}, Content-Type: {resp.headers.get('Content-Type')}", xbmc.LOGINFO)
            return resp
        except Exception as e:
            xbmc.log(f"[AHProxy] GET request failed: {e}", xbmc.LOGERROR)
            raise


# =============================================================================
# Proxy Handler (unterstützt beide Upstream-Typen)
# =============================================================================

class _ProxyHandler(BaseHTTPRequestHandler):
    server_version = "AHProxy/2.0"
    upstream = None 

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

    def do_HEAD(self):
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

    def do_GET(self):
        extra = self._extra_browser_headers()
        rng = self._extract_range()
        
        if rng:
            extra["Range"] = rng
            xbmc.log(f"[AHProxy] Kodi requested Range: {rng}", xbmc.LOGINFO)
        
        try:
            rsp = self.upstream.make_get(extra=extra, stream=True)
            self._write_head_from_upstream(rsp)
            self.end_headers()

            status = getattr(rsp, "status_code", 0)
            
            # Chunk-Size: klein für urllib (Seek-Performance), normal für requests
            if isinstance(self.upstream, _UrllibUpstream):
                chunk_size = PROXY_CHUNK  # 32 KB
            else:
                chunk_size = DEFAULT_CHUNK  # 512 KB
            
            if status in (200, 206):
                bytes_sent = 0
                chunk_count = 0
                try:
                    for chunk in rsp.iter_content(chunk_size=chunk_size):
                        if not chunk:
                            continue
                        try:
                            self.wfile.write(chunk)
                            bytes_sent += len(chunk)
                            chunk_count += 1
                            
                            # Flush nach jedem Chunk für minimale Latenz
                            if chunk_count <= 4 or chunk_count % 4 == 0:
                                self.wfile.flush()
                                
                            if chunk_count == 1:
                                xbmc.log(f"[AHProxy] First chunk sent: {bytes_sent} bytes (Range={rng})", xbmc.LOGINFO)
                        except (socket.error, ConnectionResetError, ConnectionAbortedError) as e:
                            xbmc.log(f"[AHProxy] Connection broken after {bytes_sent} bytes: {e}", xbmc.LOGDEBUG)
                            break
                    xbmc.log(f"[AHProxy] Stream complete: {bytes_sent} bytes", xbmc.LOGINFO)
                except Exception as e:
                    xbmc.log(f"[AHProxy] Stream error after {bytes_sent} bytes: {e}", xbmc.LOGERROR)
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
        except Exception as e:
            xbmc.log(f"[AHProxy] GET error: {e}", xbmc.LOGERROR)
            try:
                self.send_error(502, f"Upstream error: {e}")
            except:
                pass


class _HTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True


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
    ):
        """
        Args:
            upstream_url: Die Video-URL die geproxied werden soll.
            upstream_headers: Dict mit HTTP-Headers für den Upstream.
            cookies: Dict oder String mit Cookies.
            session: requests.Session (nur für requests-Modus).
            skip_resolve: Wenn True, wird _resolve_url() übersprungen.
            use_urllib: Wenn True, wird urllib.request statt requests benutzt.
                        Das umgeht TLS-Fingerprint-Probleme mit CDNs die
                        requests/urllib3 blocken (z.B. Cloudflare R2).
        """
        if use_urllib:
            self.up = _UrllibUpstream(
                upstream_url,
                headers=upstream_headers,
                cookies=cookies,
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

    def start(self):
        def _handler_factory(upstream_obj):
            class _H(_ProxyHandler):
                upstream = upstream_obj
            return _H

        self.httpd = _HTTPServer((self.host, self.port), _handler_factory(self.up))
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
                # Close the socket first to break any active do_GET loops
                try:
                    self.httpd.server_close()
                except:
                    pass
                self.httpd.shutdown()
                xbmc.log("[AHProxy] Stopped", xbmc.LOGINFO)
        except Exception as e:
            xbmc.log(f"[AHProxy] Error during stop: {e}", xbmc.LOGDEBUG)
        
        # Upstream-Verbindung sauber schließen
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
        import time
        start_ts = time.time()

        target_started = False
        while not self.monitor.abortRequested():
            if time.time() - start_ts > 30:
                xbmc.log(f"[AHProxy] Timed out waiting for target: {self.target}", xbmc.LOGWARNING)
                break

            if hasattr(self.player, 'isPlayingVideo') and self.player.isPlayingVideo():
                try:
                    current_file = self.player.getPlayingFile() if hasattr(self.player, 'getPlayingFile') else ""
                except Exception:
                    current_file = ""
                
                if current_file:
                    # Log what we see, helps debugging "target not found"
                    # Only log every few seconds to avoid spam
                    if int(time.time() - start_ts) % 5 == 0:
                        xbmc.log(f"[AHProxy-Guard] Current: {current_file[:120]}, Target: {self.target[:120]}", xbmc.LOGDEBUG)

                if (self.target == current_file) or (self.target and current_file and (self.target in current_file or current_file in self.target)):
                    target_started = True
                    xbmc.log(f"[AHProxy] Playback detected for {self.target}", xbmc.LOGINFO)
                    break
            
            self.monitor.waitForAbort(0.5)

        if not target_started:
            try:
                xbmc.log(f"[AHProxy] Timed out waiting for target: {self.target}. Last seen: {current_file if 'current_file' in locals() else 'None'}", xbmc.LOGWARNING)
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
