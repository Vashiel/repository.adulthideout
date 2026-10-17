# -*- coding: utf-8 -*-
import json
from html import unescape
from html.parser import HTMLParser


class _HostLinkParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = []
        self.seen = set()

    def _add(self, value):
        value = unescape((value or "").strip()).replace("\\/", "/")
        if value.startswith(("http://", "https://")) and value not in self.seen:
            self.seen.add(value)
            self.links.append(value)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        for key in ("data-fl-url", "data-fl-source"):
            self._add(attrs.get(key))

        if attrs.get("id", "").lower() == "#iframe":
            self._add(attrs.get("href"))

        servers = attrs.get("data-servers")
        if not servers:
            return
        try:
            entries = json.loads(unescape(servers))
        except (TypeError, ValueError):
            return
        if not isinstance(entries, list):
            return
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            kind = str(entry.get("t") or entry.get("type") or "").lower()
            if kind and kind not in ("iframe", "embed", "url", "direct", "link"):
                continue
            self._add(entry.get("u") or entry.get("url"))


def extract_host_links(page_html):
    parser = _HostLinkParser()
    try:
        parser.feed(page_html or "")
    except Exception:
        pass
    return parser.links
