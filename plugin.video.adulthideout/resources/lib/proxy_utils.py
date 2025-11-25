#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os
import urllib.parse
import xbmc
import xbmcaddon
import threading
import socket
import json
import re
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

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

DEFAULT_CHUNK = 512 * 1024  # 512 KB chunks for faster streaming
_DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)


class _Upstream:
    def __init__(
        self,
        url,
        headers=None,
        cookies=None,
        session=None,
    ):
        self.original_url = url
        self.resolved_url = None
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
        except Exception:
            pass

        self._resolve_url()

    def _resolve_url(self):
        try:
            xbmc.log("[AHProxy] Checking if URL needs resolution...", xbmc.LOGINFO)
            try:
                head_resp = self.session.head(self.original_url, timeout=5, allow_redirects=True)
                content_type = head_resp.headers.get('Content-Type', '').lower()
                if 'video/' in content_type or 'octet-stream' in content_type:
                    xbmc.log("[AHProxy] HEAD shows video content, no resolution needed", xbmc.LOGINFO)
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


class _ProxyHandler(BaseHTTPRequestHandler):
    server_version = "AHProxy/2.0"
    upstream = None 

    def log_message(self, fmt, *args):
        return 

    def _extract_range(self):
        rng = self.headers.get("Range")
        return rng if rng else None

    def _infer_origin(self):
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
        extra = {
            "Accept": "video/mp4,application/octet-stream;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Connection": "keep-alive",
            "Accept-Encoding": "identity",
            "Sec-Fetch-Site": "cross-site",
            "Sec-Fetch-Mode": "no-cors",
            "Sec-Fetch-Dest": "video",
        }
        origin = self._infer_origin()
        if origin:
            extra["Origin"] = origin
        return extra

    def _write_head_from_upstream(self, rsp):
        status = getattr(rsp, "status_code", 502)
        self.send_response(status)
        
        hop_by_hop = {
            "transfer-encoding", "connection", "proxy-authenticate", "proxy-authorization",
            "te", "trailer", "upgrade", "keep-alive",
        }
        for k, v in getattr(rsp, "headers", {}).items():
            lk = k.lower()
            if lk in hop_by_hop:
                continue
            if lk in ("content-length", "content-type", "accept-ranges", "content-range", "etag", "last-modified"):
                self.send_header(k, v)
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
        
        try:
            rsp = self.upstream.make_get(extra=extra, stream=True)
            self._write_head_from_upstream(rsp)
            self.end_headers()

            status = getattr(rsp, "status_code", 0)
            
            if status in (200, 206):
                bytes_sent = 0
                chunk_count = 0
                try:
                    for chunk in rsp.iter_content(chunk_size=DEFAULT_CHUNK):
                        if not chunk:
                            continue
                        try:
                            self.wfile.write(chunk)
                            bytes_sent += len(chunk)
                            chunk_count += 1
                            
                            if chunk_count % 2 == 0: 
                                self.wfile.flush()
                                
                            if chunk_count == 1:
                                xbmc.log(f"[AHProxy] First chunk sent: {bytes_sent} bytes", xbmc.LOGINFO)
                        except (socket.error, ConnectionResetError, ConnectionAbortedError) as e:
                            xbmc.log(f"[AHProxy] Connection broken after {bytes_sent} bytes: {e}", xbmc.LOGDEBUG)
                            break
                    xbmc.log(f"[AHProxy] Stream complete: {bytes_sent} bytes", xbmc.LOGINFO)
                except Exception as e:
                    xbmc.log(f"[AHProxy] Stream error: {e}", xbmc.LOGERROR)
            else:
                xbmc.log(f"[AHProxy] Unexpected status code: {status}", xbmc.LOGWARNING)
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
    ):
        self.up = _Upstream(
            upstream_url,
            headers=upstream_headers,
            cookies=cookies,
            session=session, 
        )
        self.host = host
        self.port = port
        self.httpd = None
        self.thread = None
        self.local_url = None

    def start(self):
        if self.port == 0:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind((self.host, 0))
                self.port = s.getsockname()[1]

        def _handler_factory(upstream_obj):
            class _H(_ProxyHandler):
                upstream = upstream_obj
            return _H

        self.httpd = _HTTPServer((self.host, self.port), _handler_factory(self.up))
        self.thread = threading.Thread(target=self.httpd.serve_forever, name="AHProxyThread", daemon=True)
        self.thread.start()
        self.local_url = f"http://{self.host}:{self.port}/stream"
        xbmc.log(f"[AHProxy] Started on {self.local_url}", xbmc.LOGINFO)
        return self.local_url

    def stop(self, timeout=3.0):
        try:
            if self.httpd:
                self.httpd.shutdown()
                self.httpd.server_close()
                xbmc.log("[AHProxy] Stopped", xbmc.LOGINFO)
        except Exception:
            pass
        if self.thread:
            self.thread.join(timeout=timeout)


class PlaybackGuard(threading.Thread):
    def __init__(self, kodi_player, monitor, target_path, controller, idle_timeout=60 * 60):
        # daemon=False hält das Skript am Leben
        super(PlaybackGuard, self).__init__(name="AHProxyGuard", daemon=False)
        self.player = kodi_player
        self.monitor = monitor
        self.target = target_path
        self.ctrl = controller
        self.idle_timeout = idle_timeout

    def run(self):
        import time
        start_ts = time.time()

        # PHASE 1: Warten, bis DIESER spezifische Proxy-Link abgespielt wird.
        # Das verhindert, dass der Proxy beendet wird, während das ALTE Video noch ausläuft.
        target_started = False
        while not self.monitor.abortRequested():
            # Timeout nach 30 Sekunden
            if time.time() - start_ts > 30:
                xbmc.log(f"[AHProxy] Timed out waiting for target: {self.target}", xbmc.LOGWARNING)
                break

            # Prüfen, ob Player aktiv
            if self.player.isPlayingVideo():
                try:
                    current_file = self.player.getPlayingFile()
                except Exception:
                    current_file = ""
                
                # Nur weitermachen, wenn der Player wirklich UNSERE Datei spielt
                if current_file == self.target:
                    target_started = True
                    xbmc.log(f"[AHProxy] Playback detected for {self.target}", xbmc.LOGINFO)
                    break
            
            self.monitor.waitForAbort(0.5)

        # Wenn unser Video nie gestartet wurde, Proxy beenden
        if not target_started:
            try:
                self.ctrl.stop()
            except Exception:
                pass
            return

        # PHASE 2: Überwachen (Proxy aktiv halten, solange unser Video läuft)
        while not self.monitor.abortRequested():
            if not self.player.isPlayingVideo():
                break
            
            try:
                current_file = self.player.getPlayingFile()
            except Exception:
                current_file = ""
            
            # Wenn der Player zu einem anderen Video wechselt, Proxy beenden
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