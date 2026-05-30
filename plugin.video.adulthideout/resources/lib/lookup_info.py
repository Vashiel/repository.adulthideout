# -*- coding: utf-8 -*-
import html
import re
import sys
import urllib.parse

import xbmc
import xbmcgui


def clean_label(value):
    value = re.sub(r"<[^>]+>", " ", value or "")
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def absolute_url(base_url, value):
    if not value:
        return ""
    return urllib.parse.urljoin(base_url.rstrip("/") + "/", html.unescape(value).strip())


def extract_html_items(html_content, base_url, patterns, default_mode=2):
    items = []
    seen = set()
    for group, pattern, mode in patterns:
        for match in re.findall(pattern, html_content or "", re.IGNORECASE | re.DOTALL):
            if isinstance(match, tuple):
                raw_url, raw_label = match[0], match[1]
            else:
                continue
            url = absolute_url(base_url, raw_url)
            label = clean_label(raw_label)
            if not url or not label:
                continue
            key = (group.lower(), label.lower(), url)
            if key in seen:
                continue
            seen.add(key)
            items.append(
                {
                    "group": group,
                    "label": label,
                    "url": url,
                    "mode": mode or default_mode,
                }
            )
    return items


def choose_and_open(items, website_name, title="Explore similar"):
    if not items:
        xbmcgui.Dialog().notification("AdultHideout", "No related info found", xbmcgui.NOTIFICATION_INFO, 3000)
        return False

    labels = ["{}: {}".format(item["group"], item["label"]) for item in items]
    idx = xbmcgui.Dialog().select(title, labels)
    if idx == -1:
        return False

    selected = items[idx]
    target = "{}?mode={}&website={}&url={}".format(
        sys.argv[0],
        selected.get("mode", 2),
        urllib.parse.quote_plus(website_name),
        urllib.parse.quote_plus(selected["url"]),
    )
    if "action" in selected:
        target += "&action={}".format(selected["action"])
    xbmc.executebuiltin("Container.Update({},replace)".format(target))
    return True
