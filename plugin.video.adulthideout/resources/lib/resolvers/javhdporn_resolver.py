# -*- coding: utf-8 -*-
import base64
import html
import json
import os
import re
import sys
import urllib.parse

import requests
import threading
import tempfile
import socketserver
from http.server import BaseHTTPRequestHandler, HTTPServer

class ThreadingHTTPServer(socketserver.ThreadingMixIn, HTTPServer):
    daemon_threads = True


try:
    import xbmc
except Exception:
    xbmc = None

try:
    addon_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    vendor_path = os.path.join(addon_root, "resources", "lib", "vendor")
    if os.path.isdir(vendor_path) and vendor_path not in sys.path:
        sys.path.insert(0, vendor_path)
except Exception:
    pass

import cloudscraper


UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/123.0.0.0 Safari/537.36"
)


def _log(message, level=None):
    if xbmc:
        xbmc.log("[AdultHideout][JavHDPorn] {}".format(message), level or xbmc.LOGINFO)


def _b64decode(value):
    if isinstance(value, str):
        value = value.encode("latin-1")
    value += b"=" * ((4 - len(value) % 4) % 4)
    return base64.b64decode(value)


def _b64encode(value):
    if isinstance(value, str):
        value = value.encode("latin-1")
    return base64.b64encode(value).decode("latin-1")


def _rc4_b64(payload, key):
    state = list(range(256))
    j = 0
    key_bytes = [ord(ch) for ch in key]
    for i in range(256):
        j = (j + state[i] + key_bytes[i % len(key_bytes)]) % 256
        state[i], state[j] = state[j], state[i]

    i = 0
    j = 0
    output = []
    for byte in _b64decode(payload):
        i = (i + 1) % 256
        j = (j + state[i]) % 256
        state[i], state[j] = state[j], state[i]
        output.append(byte ^ state[(state[i] + state[j]) % 256])

    return _b64decode(bytes(output).decode("latin-1")).decode("latin-1")


def _cast_dex(video_id, payload, flag=False, data_ver="2"):
    salt = "_0x58fe15"
    if flag and data_ver == "1":
        salt = "QxLUF1bgIAdeQX"
    elif flag and data_ver == "2":
        salt = "SyntaxError"
    key = _b64encode(video_id + salt)[::-1]
    return _rc4_b64(payload, key)


def _player_decode_config(config_token, player_url):
    parsed = urllib.parse.urlparse(player_url)
    key_seed = parsed.path
    if parsed.query:
        key_seed += "?" + parsed.query
    key = _b64encode(_b64encode(key_seed)[4:20] + "_0x59a0e4")[::-1]
    decoded = _rc4_b64(config_token, key)
    return json.loads(decoded)


def _make_scraper():
    return cloudscraper.create_scraper(
        browser={"browser": "chrome", "platform": "windows", "desktop": True},
        interpreter="native",
        enable_stealth=False,
        rotate_tls_ciphers=True,
        min_request_interval=0.0,
        auto_refresh_on_403=False,
    )


def _headers(referer=None, accept=None):
    headers = {
        "User-Agent": UA,
        "Accept": accept or "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    if referer:
        headers["Referer"] = referer
    return headers


def _extract(pattern, text, label):
    match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
    if not match:
        raise ValueError("Missing {}".format(label))
    return html.unescape(match.group(1))


def resolve(url, referer=None, headers=None):
    scraper = _make_scraper()
    page = scraper.get(url, headers=_headers(referer or "https://www.javhdporn.net/"), timeout=30)
    page.raise_for_status()
    page_html = page.text

    video_id = _extract(r'data-video-id="([^"]+)"', page_html, "video id")
    data_mpu = _extract(r'data-mpu="([^"]+)"', page_html, "data mpu")
    data_ver = _extract(r'data-ver="([^"]+)"', page_html, "data ver")
    sources = _cast_dex(video_id, data_mpu, flag=True, data_ver=data_ver)

    api = scraper.post(
        "https://www.javhdporn.net/api/play/",
        data={"sources": sources, "ver": "2"},
        headers={
            "User-Agent": UA,
            "Referer": url,
            "Origin": "https://www.javhdporn.net",
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "application/json, text/javascript, */*; q=0.01",
        },
        timeout=30,
    )
    api.raise_for_status()
    api_data = api.json()
    if not api_data.get("status") or not api_data.get("data"):
        raise ValueError("API returned no playable data")

    player_path = _cast_dex(video_id, api_data["data"], flag=False, data_ver=data_ver)
    player_url = urllib.parse.urljoin("https://www.javhdporn.net/", player_path)
    player_page = scraper.get(player_url, headers=_headers(url), timeout=30)
    player_page.raise_for_status()

    config_token = _extract(r'id="jwplayer"[^>]+data-config="([^"]+)"', player_page.text, "player config")
    config = _player_decode_config(config_token, player_url)
    sources = config.get("sources") or []
    if not sources and config.get("src"):
        sources = json.loads(_b64decode(config["src"]).decode("utf-8"))
    if not sources:
        raise ValueError("Player config contains no sources")

    selected = sources[0]
    for candidate in sources:
        if candidate.get("file") and candidate.get("type") in ("hls", "mp4"):
            selected = candidate
            break

    stream_url = html.unescape(selected.get("file") or "")
    if not stream_url:
        raise ValueError("Selected source has no file")

    stream_headers = {
        "User-Agent": UA,
        "Referer": player_url,
        "Accept": "*/*",
    }
    _log("Resolved {} via {}".format(url, urllib.parse.urlparse(stream_url).netloc))
    return stream_url, stream_headers

class ImageStripHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_GET(self):
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        if 'url' not in qs:
            self.send_response(400)
            self.end_headers()
            return
            
        target_url = base64.b64decode(qs['url'][0]).decode('utf-8')
        headers = {
            'User-Agent': UA,
            'Referer': 'https://streamhls.click/'
        }
        
        try:
            resp = requests.get(target_url, headers=headers, stream=True, timeout=15)
            self.send_response(200)
            self.send_header('Content-Type', 'video/mp2t')
            self.send_header('Connection', 'close')
            self.end_headers()
            
            first_chunk = resp.raw.read(1024)
            ts_start = -1
            for i in range(len(first_chunk) - 188):
                if first_chunk[i] == 0x47 and first_chunk[i+188] == 0x47:
                    ts_start = i
                    break
            
            if ts_start != -1:
                self.wfile.write(first_chunk[ts_start:])
            else:
                self.wfile.write(first_chunk)
                
            while True:
                chunk = resp.raw.read(32768)
                if not chunk:
                    break
                self.wfile.write(chunk)
                
        except Exception as e:
            _log("Proxy error: {}".format(e))

class TiktokImageProxy:
    def __init__(self, port=0):
        self.host = '127.0.0.1'
        self.port = port
        self.httpd = None
        self.thread = None

    def start(self):
        self.httpd = ThreadingHTTPServer((self.host, self.port), ImageStripHandler)
        self.port = self.httpd.server_port
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        return "http://{}:{}".format(self.host, self.port)
        
    def stop(self):
        if self.httpd:
            try:
                self.httpd.shutdown()
                self.httpd.server_close()
            except:
                pass

def rewrite_playlist(master_url, headers, proxy_base_url):
    scraper = _make_scraper()
    resp = scraper.get(master_url, headers=headers, timeout=15)
    resp.raise_for_status()
    
    lines = resp.text.splitlines()
    best_index_url = None
    best_bw = -1
    for i, line in enumerate(lines):
        if line.startswith("#EXT-X-STREAM-INF"):
            m = re.search(r'BANDWIDTH=(\d+)', line)
            bw = int(m.group(1)) if m else 0
            if bw > best_bw and i + 1 < len(lines):
                best_bw = bw
                idx = lines[i+1].strip()
                if not idx.startswith("http"):
                    idx = urllib.parse.urljoin(master_url, idx)
                best_index_url = idx
                
    if not best_index_url:
        best_index_url = master_url
        
    resp_idx = scraper.get(best_index_url, headers=headers, timeout=15)
    resp_idx.raise_for_status()
    
    new_lines = []
    for line in resp_idx.text.splitlines():
        if line.startswith("#") or not line.strip():
            new_lines.append(line)
        else:
            seg_url = line.strip()
            if not seg_url.startswith("http"):
                seg_url = urllib.parse.urljoin(best_index_url, seg_url)
            
            b64_url = base64.b64encode(seg_url.encode('utf-8')).decode('utf-8')
            new_lines.append("{}/?url={}".format(proxy_base_url, b64_url))
            
    try:
        temp_dir = xbmc.translatePath('special://temp')
    except:
        temp_dir = tempfile.gettempdir()
        
    local_m3u8 = os.path.join(temp_dir, "javhdporn_rewritten.m3u8")
    with open(local_m3u8, "w") as f:
        f.write("\n".join(new_lines))
        
    return local_m3u8

