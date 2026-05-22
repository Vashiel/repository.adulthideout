# -*- coding: utf-8 -*-
import base64
import json
import os
import random
import re
import tempfile
import urllib.parse

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

from resources.lib.resolvers import resolver_utils


ACTION_MOVE_LEFT = getattr(xbmcgui, "ACTION_MOVE_LEFT", 1)
ACTION_MOVE_RIGHT = getattr(xbmcgui, "ACTION_MOVE_RIGHT", 2)
ACTION_MOVE_UP = getattr(xbmcgui, "ACTION_MOVE_UP", 3)
ACTION_MOVE_DOWN = getattr(xbmcgui, "ACTION_MOVE_DOWN", 4)
ACTION_SELECT_ITEM = getattr(xbmcgui, "ACTION_SELECT_ITEM", 7)
ACTION_NAV_BACK = getattr(xbmcgui, "ACTION_NAV_BACK", 92)
ACTION_PREVIOUS_MENU = getattr(xbmcgui, "ACTION_PREVIOUS_MENU", 10)


class _NetuCaptchaWindow(xbmcgui.WindowDialog):
    def __init__(self, image_bytes, width=400, height=400):
        super(_NetuCaptchaWindow, self).__init__()
        self.orig_width = width
        self.orig_height = height
        self.display_width = min(width, max(260, self.getWidth() - 260))
        self.display_height = int(float(height) * self.display_width / float(width))
        if self.display_height > self.getHeight() - 220:
            self.display_height = self.getHeight() - 220
            self.display_width = int(float(width) * self.display_height / float(height))

        self.orig_x = (self.getWidth() - self.display_width) // 2
        self.orig_y = (self.getHeight() - self.display_height) // 2
        self.marker_size = max(36, int(48 * (self.display_width / float(width))))
        # DirtyVideo usually wants the visible play button. Start in the center instead of a corner.
        self.frame_x = self.orig_x + ((self.display_width - self.marker_size) // 2)
        self.frame_y = self.orig_y + ((self.display_height - self.marker_size) // 2)
        self.finished = False
        self.click_cells = {}
        self.temp_file = self._write_temp_image(image_bytes)

        self._build_controls()

    def _profile_path(self):
        try:
            path = xbmcaddon.Addon().getAddonInfo("profile")
            try:
                path = xbmcvfs.translatePath(path)
            except AttributeError:
                path = xbmc.translatePath(path)
            if path and not xbmcvfs.exists(path):
                xbmcvfs.mkdirs(path)
            return path
        except Exception:
            return tempfile.gettempdir()

    def _write_temp_image(self, image_bytes):
        path = os.path.join(self._profile_path(), "netu_captcha.jpg")
        self._remove_temp_image(path)
        with open(path, "wb") as handle:
            handle.write(image_bytes)
        return path

    def _remove_temp_image(self, path=None):
        try:
            target = path or self.temp_file
            if target and os.path.exists(target):
                os.remove(target)
        except Exception:
            pass

    @property
    def solution_x(self):
        center_x = self.frame_x - self.orig_x + (self.marker_size // 2)
        return max(0, min(self.orig_width - 1, int(center_x * self.orig_width / float(self.display_width))))

    @property
    def solution_y(self):
        center_y = self.frame_y - self.orig_y + (self.marker_size // 2)
        return max(0, min(self.orig_height - 1, int(center_y * self.orig_height / float(self.display_height))))

    def _build_controls(self):
        label_y = max(20, self.orig_y - 118)
        self.addControl(
            xbmcgui.ControlLabel(
                self.orig_x - 120,
                label_y,
                self.display_width + 240,
                34,
                "Netu/DirtyVideo: click the play triangle or move the red + with arrows.",
                textColor="0xFFFFFFFF",
                alignment=6,
            )
        )
        self.addControl(
            xbmcgui.ControlLabel(
                self.orig_x - 120,
                label_y + 34,
                self.display_width + 240,
                34,
                "Click the triangle once, fine-adjust with arrows if needed, then select OK.",
                textColor="0xFFCCCCCC",
                alignment=6,
            )
        )

        self.captcha_image = xbmcgui.ControlImage(
            self.orig_x,
            self.orig_y,
            self.display_width,
            self.display_height,
            self.temp_file,
        )
        self.addControl(self.captcha_image)
        self._add_click_grid()

        arrow_w = 110
        arrow_h = 60
        self.top_arrow = xbmcgui.ControlButton(
            self.orig_x + (self.display_width - arrow_w) // 2,
            self.orig_y - arrow_h - 10,
            arrow_w,
            arrow_h,
            "^",
            textColor="0xFF9FFB05",
            alignment=6,
        )
        self.bottom_arrow = xbmcgui.ControlButton(
            self.orig_x + (self.display_width - arrow_w) // 2,
            self.orig_y + self.display_height + 10,
            arrow_w,
            arrow_h,
            "v",
            textColor="0xFF9FFB05",
            alignment=6,
        )
        self.left_arrow = xbmcgui.ControlButton(
            self.orig_x - arrow_h - 10,
            self.orig_y + (self.display_height - arrow_w) // 2,
            arrow_h,
            arrow_w,
            "<",
            textColor="0xFF9FFB05",
            alignment=6,
        )
        self.right_arrow = xbmcgui.ControlButton(
            self.orig_x + self.display_width + 10,
            self.orig_y + (self.display_height - arrow_w) // 2,
            arrow_h,
            arrow_w,
            ">",
            textColor="0xFF9FFB05",
            alignment=6,
        )
        for control in (self.top_arrow, self.bottom_arrow, self.left_arrow, self.right_arrow):
            self.addControl(control)

        self.submit_button = xbmcgui.ControlButton(
            self.orig_x + (self.display_width - 180) // 2,
            min(self.getHeight() - 80, self.orig_y + self.display_height + 78),
            180,
            58,
            "OK",
            textColor="0xFF9FFB05",
            alignment=6,
        )
        self.addControl(self.submit_button)

        # The marker is intentionally a normal Kodi button so it stays visible on every skin.
        self.marker = xbmcgui.ControlButton(
            self.frame_x,
            self.frame_y,
            self.marker_size,
            self.marker_size,
            "+",
            textColor="0xFFFF3333",
            alignment=6,
        )
        self.addControl(self.marker)
        try:
            self.setFocus(self.marker)
        except Exception:
            pass

    def _add_click_grid(self):
        cell = 16
        cols = int((self.display_width + cell - 1) // cell)
        rows = int((self.display_height + cell - 1) // cell)
        for row in range(rows):
            for col in range(cols):
                x = self.orig_x + (col * cell)
                y = self.orig_y + (row * cell)
                width = min(cell, self.orig_x + self.display_width - x)
                height = min(cell, self.orig_y + self.display_height - y)
                if width <= 0 or height <= 0:
                    continue
                button = xbmcgui.ControlButton(
                    x,
                    y,
                    width,
                    height,
                    "",
                    focusTexture="",
                    noFocusTexture="",
                    textColor="0x00000000",
                    focusedColor="0x00000000",
                )
                self.addControl(button)
                self.click_cells[button.getId()] = (
                    min(self.display_width - 1, (col * cell) + (width // 2)),
                    min(self.display_height - 1, (row * cell) + (height // 2)),
                )

    def _action_id(self, action_or_control):
        if hasattr(action_or_control, "getId"):
            return action_or_control.getId()
        return action_or_control

    def _update_marker(self):
        self.marker.setPosition(self.frame_x, self.frame_y)

    def _set_marker_center(self, center_x, center_y):
        max_x = self.orig_x + self.display_width - self.marker_size
        max_y = self.orig_y + self.display_height - self.marker_size
        self.frame_x = self.orig_x + int(center_x) - (self.marker_size // 2)
        self.frame_y = self.orig_y + int(center_y) - (self.marker_size // 2)
        self.frame_x = max(self.orig_x, min(max_x, self.frame_x))
        self.frame_y = max(self.orig_y, min(max_y, self.frame_y))
        self._update_marker()

    def _move(self, dx, dy):
        max_x = self.orig_x + self.display_width - self.marker_size
        max_y = self.orig_y + self.display_height - self.marker_size
        self.frame_x += dx
        self.frame_y += dy
        if self.frame_x < self.orig_x:
            self.frame_x = max_x
        elif self.frame_x > max_x:
            self.frame_x = self.orig_x
        if self.frame_y < self.orig_y:
            self.frame_y = max_y
        elif self.frame_y > max_y:
            self.frame_y = self.orig_y
        self._update_marker()

    def _handle(self, action_or_control):
        action_id = self._action_id(action_or_control)
        if action_id in (ACTION_MOVE_LEFT, self.left_arrow.getId()):
            self._move(-4, 0)
        elif action_id in (ACTION_MOVE_RIGHT, self.right_arrow.getId()):
            self._move(4, 0)
        elif action_id in (ACTION_MOVE_UP, self.top_arrow.getId()):
            self._move(0, -4)
        elif action_id in (ACTION_MOVE_DOWN, self.bottom_arrow.getId()):
            self._move(0, 4)
        elif action_id in self.click_cells:
            center_x, center_y = self.click_cells[action_id]
            self._set_marker_center(center_x, center_y)
        elif action_id == self.submit_button.getId():
            self.finished = True
            self.close()
        elif action_id in (ACTION_NAV_BACK, ACTION_PREVIOUS_MENU):
            self.close()

    def onAction(self, action):
        action_id = self._action_id(action)
        if action_id == ACTION_SELECT_ITEM:
            try:
                focus = self.getFocus()
            except Exception:
                focus = None
            if focus:
                self._handle(focus)
            return
        self._handle(action_id)

    def onControl(self, control):
        self._handle(control)

    def close(self):
        self._remove_temp_image()
        return super(_NetuCaptchaWindow, self).close()


def _random_sha1():
    return "".join(random.choice("0123456789abcdef") for _ in range(40))


def _decode_obf_link(value):
    if not value or value == "#":
        return ""
    if "." in value:
        return value

    value = value[1:]
    chars = []
    for idx in range(0, len(value), 3):
        try:
            chars.append(chr(int(value[idx : idx + 3], 16)))
        except ValueError:
            return ""
    return "".join(chars)


def _extract_var(page_html, name, default=""):
    match = re.search(r"(?:var\s+)?{}\s*=\s*(['\"])(.*?)\1".format(re.escape(name)), page_html or "")
    return match.group(2) if match else default


def _extract_literal(page_html, pattern, default=""):
    match = re.search(pattern, page_html or "", re.IGNORECASE)
    return match.group(1) if match else default


def _normalize_stream_url(value):
    value = (value or "").replace("\\/", "/").strip()
    if value.startswith("//"):
        value = "https:" + value
    return value


def _probe_stream(session, stream_url, headers):
    try:
        response = session.get(stream_url, headers=headers, timeout=8, stream=True, allow_redirects=True)
        status_code = response.status_code
        response.close()
        if status_code in (200, 206):
            return True
        xbmc.log("[AdultHideout][dirtyvideo] stream probe HTTP {} for {}".format(status_code, stream_url), xbmc.LOGWARNING)
    except Exception as exc:
        xbmc.log("[AdultHideout][dirtyvideo] stream probe failed for {}: {}".format(stream_url, exc), xbmc.LOGWARNING)
    return False


def _decode_captcha_image(image_data):
    image_data = (image_data or "").replace("\\/", "/")
    if "," in image_data:
        image_data = image_data.split(",", 1)[1]
    return base64.b64decode(image_data + "==")


def _get_captcha_solution(image_data):
    image_bytes = _decode_captcha_image(image_data.get("image", ""))
    window = _NetuCaptchaWindow(image_bytes, 400, 400)
    window.doModal()
    if not window.finished:
        return None
    return window.solution_x, window.solution_y


def resolve(embed_url, referer=None, headers=None):
    xbmc.log("[AdultHideout][dirtyvideo] Resolving: {}".format(embed_url), xbmc.LOGINFO)
    headers = dict(headers or {})
    headers.setdefault("User-Agent", resolver_utils.get_ua())
    headers["Referer"] = referer or embed_url

    page_html = resolver_utils.http_get(embed_url, headers=headers, timeout=25)
    if not page_html:
        return "", headers

    host_root = "{}://{}".format(urllib.parse.urlparse(embed_url).scheme, urllib.parse.urlparse(embed_url).netloc)
    ajax_headers = dict(headers)
    ajax_headers.update(
        {
            "Referer": embed_url,
            "Origin": host_root,
            "X-Requested-With": "XMLHttpRequest",
            "Content-Type": "application/json",
            "Accept": "application/json, text/javascript, */*; q=0.01",
        }
    )

    media_id = embed_url.rstrip("/").split("/")[-1]
    video_key = _extract_literal(page_html, r"'videokey'\s*:\s*'([^']+)'", media_id)
    video_id = _extract_literal(page_html, r"'videoid'\s*:\s*'([^']+)'")
    adbn = _extract_var(page_html, "adbn")

    if video_id and video_key and adbn:
        image_payload = {
            "videoid": video_id,
            "videokey": video_key,
            "width": 400,
            "height": 400,
        }
        try:
            try:
                import cloudscraper

                session = cloudscraper.create_scraper(
                    browser={"browser": "chrome", "platform": "windows", "mobile": False}
                )
            except Exception:
                import requests

                session = requests.Session()
            session.headers.update({"User-Agent": headers["User-Agent"]})
            session.get(embed_url, headers=headers, timeout=25)
            image_response = session.post(
                urllib.parse.urljoin(embed_url, "/player/get_player_image.php"),
                headers=ajax_headers,
                data=json.dumps(image_payload, separators=(",", ":")),
                timeout=25,
            )
            try:
                image_data = image_response.json() if image_response.status_code == 200 else {}
            except Exception:
                xbmc.log(
                    "[AdultHideout][dirtyvideo] get_player_image invalid JSON status={} body={}".format(
                        image_response.status_code, image_response.text[:240]
                    ),
                    xbmc.LOGWARNING,
                )
                return "", ajax_headers
            if not isinstance(image_data, dict):
                xbmc.log("[AdultHideout][dirtyvideo] get_player_image unexpected payload", xbmc.LOGWARNING)
                return "", ajax_headers
            xbmc.log(
                "[AdultHideout][dirtyvideo] get_player_image status={} keys={} try_again={} has_image={}".format(
                    image_response.status_code,
                    ",".join(sorted(image_data.keys())),
                    image_data.get("try_again"),
                    bool(image_data.get("image")),
                ),
                xbmc.LOGINFO,
            )
            if image_data.get("try_again") == "1":
                resolver_utils.notify(
                    "Netu asks to wait {} seconds".format(image_data.get("isec", "a few")),
                    xbmcgui.NOTIFICATION_WARNING,
                )
                return "", ajax_headers
            if not image_data.get("image"):
                resolver_utils.notify("Netu/DirtyVideo captcha image missing", xbmcgui.NOTIFICATION_WARNING)
                return "", ajax_headers

            solution = _get_captcha_solution(image_data)
            if not solution:
                resolver_utils.notify("Netu/DirtyVideo captcha cancelled", xbmcgui.NOTIFICATION_WARNING)
                return "", ajax_headers
            click_x, click_y = solution
            xbmc.log("[AdultHideout][dirtyvideo] click captcha coords x={} y={}".format(click_x, click_y), xbmc.LOGINFO)

            md5_payload = {
                "adb": adbn,
                "sh": _random_sha1(),
                "ver": "4",
                "secure": _extract_var(page_html, "secure", "0"),
                "htoken": _extract_var(page_html, "htoken"),
                "v": urllib.parse.quote(video_key, safe=""),
                "token": "",
                "gt": _extract_var(page_html, "gtr"),
                "embed_from": _extract_var(page_html, "embedfrm", "0"),
                "wasmcheck": 1,
                "adscore": "",
                "click_hash": urllib.parse.quote(image_data.get("hash_image", ""), safe=""),
                "clickx": click_x,
                "clicky": click_y,
            }
            md5_response = session.post(
                urllib.parse.urljoin(embed_url, "/player/get_md5.php"),
                headers=ajax_headers,
                data=json.dumps(md5_payload, separators=(",", ":")),
                timeout=25,
            )
            if md5_response.status_code != 200:
                xbmc.log(
                    "[AdultHideout][dirtyvideo] get_md5 HTTP {} body={}".format(
                        md5_response.status_code, md5_response.text[:240]
                    ),
                    xbmc.LOGWARNING,
                )
                resolver_utils.notify("Netu/DirtyVideo blocked get_md5 request", xbmcgui.NOTIFICATION_WARNING)
                return "", ajax_headers

            try:
                md5_data = md5_response.json()
            except Exception:
                xbmc.log(
                    "[AdultHideout][dirtyvideo] get_md5 invalid JSON body={}".format(md5_response.text[:240]),
                    xbmc.LOGWARNING,
                )
                return "", ajax_headers
            if not isinstance(md5_data, dict):
                xbmc.log("[AdultHideout][dirtyvideo] get_md5 unexpected payload", xbmc.LOGWARNING)
                return "", ajax_headers
            xbmc.log(
                "[AdultHideout][dirtyvideo] get_md5 keys={} need_captcha={} try_again={} wrong_recaptcha={}".format(
                    ",".join(sorted(md5_data.keys())),
                    md5_data.get("need_captcha"),
                    md5_data.get("try_again"),
                    md5_data.get("wrong_recaptcha"),
                ),
                xbmc.LOGINFO,
            )
            obf_link = _decode_obf_link(md5_data.get("obf_link"))
            if obf_link:
                stream_url = _normalize_stream_url("https:" + obf_link)
                if ".mp4.m3u8" not in stream_url:
                    stream_url += ".mp4.m3u8"
                play_headers = {"User-Agent": headers["User-Agent"], "Referer": embed_url, "Origin": host_root}
                if not _probe_stream(session, stream_url, play_headers):
                    resolver_utils.notify("Netu click accepted, CDN unreachable", xbmcgui.NOTIFICATION_WARNING)
                    return "", ajax_headers
                return stream_url, play_headers
            if md5_data.get("need_captcha") == "1" or md5_data.get("try_again") == "1":
                resolver_utils.notify("Netu/DirtyVideo click not accepted", xbmcgui.NOTIFICATION_WARNING)
                return "", ajax_headers
            return "", ajax_headers
        except Exception as exc:
            xbmc.log("[AdultHideout][dirtyvideo] get_md5 flow failed: {}".format(exc), xbmc.LOGWARNING)
            return "", ajax_headers

    direct_match = re.search(r"(https?:\\?/\\?/[^\s\"'<>]+?\.(?:m3u8|mp4)[^\s\"'<>]*)", page_html, re.IGNORECASE)
    if direct_match:
        stream_url = _normalize_stream_url(direct_match.group(1))
        play_headers = {"User-Agent": headers["User-Agent"], "Referer": embed_url, "Origin": host_root}
        return stream_url, play_headers

    resolver_utils.notify("Netu/DirtyVideo stream not resolvable", xbmcgui.NOTIFICATION_WARNING)
    return "", ajax_headers
