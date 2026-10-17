"""Movie cards shared by the current Panda-network layouts."""

import re
import urllib.parse
from html.parser import HTMLParser


class _Cards(HTMLParser):
    def __init__(self, base_url):
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.items = []
        self.card = None
        self.text = []
        self.seen = set()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "a":
            self.card = None
            target = urllib.parse.urljoin(self.base_url + "/", attrs.get("href", ""))
            parsed = urllib.parse.urlsplit(target)
            if (parsed.netloc == urllib.parse.urlsplit(self.base_url).netloc
                    and re.match(r"/(?:watch-[^/]+|movies?/[^/]+|[a-z0-9-]+)(?:/|$)", parsed.path)):
                self.card = {"url": target, "title": attrs.get("title", ""), "thumb": ""}
                self.text = []
        elif tag == "img" and self.card is not None:
            if not {"card__img", "fcar__img"}.intersection(attrs.get("class", "").split()):
                return
            self.card["thumb"] = attrs.get("data-src") or attrs.get("data-original") or attrs.get("src", "")
            self.card["title"] = self.card["title"] or attrs.get("alt", "")

    def handle_data(self, data):
        if self.card is not None:
            self.text.append(data)

    def handle_endtag(self, tag):
        if tag != "a" or self.card is None:
            return
        card = self.card
        self.card = None
        if not card["thumb"] or card["thumb"].startswith("data:") or card["url"] in self.seen:
            return
        title = card["title"] or " ".join(self.text)
        title = re.sub(r"^Watch\s+|\s+(?:Porn\s+)?Online Free$", "", title, flags=re.I)
        title = re.sub(r"\s+", " ", title).strip()
        if not title:
            return
        self.seen.add(card["url"])
        self.items.append({"title": title, "url": card["url"],
                           "thumb": urllib.parse.urljoin(self.base_url + "/", card["thumb"]),
                           "info": {"title": title, "plot": title}})


def parse_movie_cards(content, base_url):
    parser = _Cards(base_url)
    parser.feed(content or "")
    return parser.items
