"""Run: python -I tests/test_core_transport.py  (needs requests; without -I if requests sits in user site-packages)"""
import json, os, sys, threading
from http.server import BaseHTTPRequestHandler, HTTPServer

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "plugin.video.adulthideout"))
import requests
from resources.lib import core_transport as ct

core_status = {"value": 200, "body": "from core ü"}
seen = {"core": [], "site": []}


class Core(BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        seen["core"].append(body)
        reply = {"status": "ok", "solution": {"url": body["url"], "status": core_status["value"],
                                              "headers": {"content-type": "text/html"}, "response": core_status["body"],
                                              "cookies": [{"name": "cf", "value": "1", "domain": "example.test", "path": "/"}]}}
        data = json.dumps(reply).encode()
        self.send_response(200); self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)

    def log_message(self, *a): pass


class Site(BaseHTTPRequestHandler):
    def do_GET(self):
        seen["site"].append(self.path)
        data = b"from python"
        self.send_response(200); self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)

    do_POST = do_GET

    def log_message(self, *a): pass


core = HTTPServer(("127.0.0.1", 0), Core); site = HTTPServer(("127.0.0.1", 0), Site)
for server in (core, site):
    threading.Thread(target=server.serve_forever, daemon=True).start()
ct.CORE_ENDPOINT = "http://127.0.0.1:%d/v1" % core.server_port
# The test site is local, which the hook skips on purpose; treat it as remote here.
ct._LOCAL_HOSTS = {"localhost"}
site_url = "http://127.0.0.1:%d/page" % site.server_port
ct.install(); ct.install()  # second call must not double-wrap

s = requests.Session()
s.cookies.set("sess", "abc")
r = s.get(site_url, timeout=5)
assert r.status_code == 200 and r.text == "from core ü", r.text
assert seen["site"] == [], "core answer must not hit the site"
assert seen["core"][-1]["cookies"][0]["name"] == "sess", "session cookies go to the core"
assert s.cookies.get("cf") == "1", "core cookies land in the session"
sent = {k.lower() for k in seen["core"][-1]["headers"]}
assert not sent & {"accept-encoding", "connection", "user-agent"}, sent
assert seen["core"][-1]["headers"].get("Accept-Language", "").startswith("en"), "pages must not come back translated"

core_status["body"] = ""  # what the Core returns for gzip or non-UTF-8 bodies
r = s.get(site_url, timeout=5)
assert r.text == "from python", "an empty core page falls back to python"
core_status["body"] = "from core ü"; seen["site"].clear()

core_status["value"] = 403
r = s.get(site_url, timeout=5)
assert r.text == "from python" and seen["site"] == ["/page"], "challenge falls back to python"

core_status["value"] = 200
n = len(seen["core"])
s.post(site_url, data="x", timeout=5); s.get(site_url, stream=True, timeout=5)
s.get(site_url.replace("/page", "/a.jpg"), timeout=5)
with ct.bypass():
    s.get(site_url, timeout=5)
assert len(seen["core"]) == n, "post, stream, media and bypass skip the core"
print("ok", ct.stats())
