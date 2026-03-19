# -*- coding: utf-8 -*-
import argparse
import html
import os
import re
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

try:
    from http.server import ThreadingHTTPServer
except ImportError:
    import socketserver

    class ThreadingHTTPServer(socketserver.ThreadingMixIn, HTTPServer):
        daemon_threads = True


vendor_path = os.path.join(os.path.dirname(__file__), "vendor")
if os.path.isdir(vendor_path) and vendor_path not in sys.path:
    sys.path.insert(0, vendor_path)

import requests

try:
    import cloudscraper
except Exception:
    cloudscraper = None

addon_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if addon_root not in sys.path:
    sys.path.insert(0, addon_root)

try:
    from resources.lib.decoders.kvs_decoder import kvs_decode_url
except Exception:
    kvs_decode_url = None


def _parse_cookie_string(cookie_string):
    cookies = {}
    if not cookie_string:
        return cookies
    for part in cookie_string.split(";"):
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        cookies[key.strip()] = value.strip()
    return cookies


class _IdleState:
    def __init__(self):
        self.last_request = time.time()

    def touch(self):
        self.last_request = time.time()


class _BootstrapStream:
    def __init__(self):
        self.response = None
        self.lock = threading.Lock()
        self.used = False


def build_session(user_agent):
    if cloudscraper is not None:
        try:
            session = cloudscraper.create_scraper(browser={"custom": user_agent})
            return session
        except Exception:
            pass
    session = requests.Session()
    return session


def resolve_stream_url(session, page_url, home_url, user_agent):
    page_headers = {
        "User-Agent": user_agent,
        "Referer": home_url,
    }
    response = session.get(
        page_url,
        headers=page_headers,
        timeout=20,
    )
    page_html = response.text
    stream_match = re.search(r"video_url:\s*'([^']+\.mp4/)'", page_html, re.IGNORECASE)
    license_match = re.search(r"license_code:\s*'([^']+)'", page_html, re.IGNORECASE)
    if not stream_match:
        return ""

    stream_url = html.unescape(stream_match.group(1).strip())
    if stream_url.startswith("function/0/") and license_match and kvs_decode_url is not None:
        stream_url = kvs_decode_url(stream_url, license_match.group(1).strip())
    return stream_url


def probe_stream(session, stream_url, headers):
    response = session.get(
        stream_url,
        headers=dict(headers, **{"Range": "bytes=0-"}),
        stream=True,
        timeout=30,
        allow_redirects=True,
    )
    if response.status_code in (200, 206):
        return response
    response.close()
    return None


def make_handler(session, upstream_url, base_headers, idle_state, bootstrap_stream):
    class ProxyHandler(BaseHTTPRequestHandler):
        server_version = "AHSystemProxy/1.0"

        def log_message(self, fmt, *args):
            return

        def _send_from_upstream(self, method="GET"):
            idle_state.touch()
            headers = dict(base_headers)
            range_header = self.headers.get("Range")
            if range_header:
                headers["Range"] = range_header
            response = None
            with bootstrap_stream.lock:
                if (
                    not bootstrap_stream.used
                    and bootstrap_stream.response is not None
                    and method == "GET"
                    and (not range_header or range_header == "bytes=0-")
                ):
                    response = bootstrap_stream.response
                    bootstrap_stream.used = True
                    bootstrap_stream.response = None

            if response is None:
                response = session.get(
                    upstream_url,
                    headers=headers,
                    stream=True,
                    timeout=30,
                    allow_redirects=True,
                )

            self.send_response(response.status_code)
            for key, value in response.headers.items():
                lowered = key.lower()
                if lowered in (
                    "content-type",
                    "content-length",
                    "content-range",
                    "accept-ranges",
                    "last-modified",
                    "etag",
                ):
                    self.send_header(key, value)
            self.end_headers()

            if method == "GET" and response.status_code in (200, 206):
                try:
                    for chunk in response.iter_content(64 * 1024):
                        if chunk:
                            self.wfile.write(chunk)
                finally:
                    response.close()
            else:
                response.close()

        def do_HEAD(self):
            self._send_from_upstream(method="HEAD")

        def do_GET(self):
            self._send_from_upstream(method="GET")

    return ProxyHandler


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="")
    parser.add_argument("--page-url", default="")
    parser.add_argument("--referer", required=True)
    parser.add_argument("--origin", required=True)
    parser.add_argument("--user-agent", required=True)
    parser.add_argument("--cookie", default="")
    parser.add_argument("--prime-url", default="")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--idle-timeout", type=int, default=120)
    args = parser.parse_args()

    session = build_session(args.user_agent)
    session.headers.update(
        {
            "User-Agent": args.user_agent,
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "Connection": "keep-alive",
        }
    )

    home_url = args.origin.rstrip("/") + "/"
    try:
        session.get(
            home_url,
            headers={
                "User-Agent": args.user_agent,
                "Referer": home_url,
            },
            timeout=20,
        )
    except Exception:
        pass

    cookies = _parse_cookie_string(args.cookie)
    if cookies:
        try:
            session.cookies.update(cookies)
        except Exception:
            pass

    if args.prime_url and not args.page_url:
        try:
            session.get(
                args.prime_url,
                headers={
                    "User-Agent": args.user_agent,
                    "Referer": home_url,
                },
                timeout=20,
            )
        except Exception:
            pass

    base_headers = {
        "User-Agent": args.user_agent,
        "Referer": args.referer,
        "Origin": args.origin,
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "keep-alive",
    }

    idle_state = _IdleState()
    bootstrap_stream = _BootstrapStream()
    selected_url = ""
    if args.url:
        try:
            bootstrap_stream.response = probe_stream(session, args.url, base_headers)
        except Exception:
            bootstrap_stream.response = None
        if bootstrap_stream.response is not None:
            selected_url = args.url

    if not selected_url and args.page_url:
        for _ in range(2):
            try:
                resolved_url = resolve_stream_url(session, args.page_url, home_url, args.user_agent)
            except Exception:
                resolved_url = ""
            if not resolved_url:
                time.sleep(0.25)
                continue
            try:
                bootstrap_stream.response = probe_stream(session, resolved_url, base_headers)
            except Exception:
                bootstrap_stream.response = None
            if bootstrap_stream.response is not None:
                selected_url = resolved_url
                break
            time.sleep(0.25)

    if not selected_url:
        print("")
        sys.stdout.flush()
        return

    handler = make_handler(session, selected_url, base_headers, idle_state, bootstrap_stream)
    server = ThreadingHTTPServer((args.host, args.port), handler)

    print("http://{}:{}/stream".format(args.host, server.server_address[1]))
    sys.stdout.flush()

    thread = threading.Thread(target=server.serve_forever)
    thread.daemon = True
    thread.start()

    try:
        while True:
            time.sleep(1)
            if time.time() - idle_state.last_request > args.idle_timeout:
                break
    finally:
        try:
            server.shutdown()
        except Exception:
            pass
        try:
            server.server_close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
