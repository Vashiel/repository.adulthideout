#!/usr/bin/env python
# -*- coding: utf-8 -*-

import hashlib
import json
import os
import xml.etree.ElementTree as ET
import urllib.request

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs


OFFICIAL_REPOSITORY_ID = "repository.adulthideout"
OFFICIAL_REPOSITORY_URL = "https://vashiel.github.io/repository.adulthideout/"
OFFICIAL_GITHUB_URL = "https://github.com/Vashiel/repository.adulthideout"
OFFICIAL_RAW_BASE = "https://github.com/Vashiel/repository.adulthideout/raw/master"
OFFICIAL_ADDONS_XML = OFFICIAL_RAW_BASE + "/addons.xml"
OFFICIAL_ADDONS_MD5 = OFFICIAL_RAW_BASE + "/addons.xml.md5"
OFFICIAL_HASHES = (
    OFFICIAL_RAW_BASE
    + "/plugin.video.adulthideout/resources/official_hashes.json"
)

EXPECTED_REPO_URLS = {
    OFFICIAL_ADDONS_XML,
    OFFICIAL_ADDONS_MD5,
    OFFICIAL_RAW_BASE + "/zips",
}

_REMOTE_TIMEOUT = 4
_ADDON = xbmcaddon.Addon()
_FALLBACK_STRINGS = {
    30600: "The official repository add-on '{}' is not installed.",
    30601: "The installed repository add-on does not have a readable addon.xml.",
    30602: "The installed repository has an unexpected add-on ID.",
    30603: "The repository URLs do not fully point to the official GitHub repository.",
    30604: "The official online metadata could not be checked: {}",
    30605: "The official addons.xml does not match its MD5 file.",
    30606: "This add-on was not found in the official addons.xml.",
    30607: "Installed version {} does not match official version {}.",
    30608: "The official metadata has an unexpected provider.",
    30609: "The official metadata does not contain the expected GitHub source.",
    30610: "The official file hash list could not be read.",
    30611: "The official file hash list is empty or invalid.",
    30612: "Hash check: file is missing or empty: {}",
    30613: "Hash check failed: {}",
    30614: "No files from the official hash list could be checked.",
    30615: "...and {} more notices.",
    30616: "AdultHideout could not confirm the official installation.",
    30617: "Official repository:",
    30618: "Official source code:",
    30619: "If you installed AdultHideout from another repository, it may be modified or outdated.",
    30620: "AdultHideout: unofficial installation?",
    30621: "Official installation could not be confirmed.",
}


def _lang(string_id, *args):
    text = _ADDON.getLocalizedString(string_id) or _FALLBACK_STRINGS.get(string_id, "")
    if args:
        try:
            return text.format(*args)
        except Exception:
            return text
    return text


def _log(message, level=xbmc.LOGINFO):
    xbmc.log("[AdultHideout][OfficialSource] {}".format(message), level)


def _translate(path):
    try:
        return xbmcvfs.translatePath(path)
    except Exception:
        return path


def _read_text(path):
    try:
        with xbmcvfs.File(path, "r") as fh:
            data = fh.read()
        if isinstance(data, bytes):
            return data.decode("utf-8", errors="replace")
        return data
    except Exception:
        try:
            with open(_translate(path), "r", encoding="utf-8", errors="replace") as fh:
                return fh.read()
        except Exception:
            return ""


def _read_bytes(path):
    try:
        with xbmcvfs.File(path, "rb") as fh:
            data = fh.read()
        if isinstance(data, str):
            return data.encode("utf-8")
        return data
    except Exception:
        try:
            with open(_translate(path), "rb") as fh:
                return fh.read()
        except Exception:
            return b""


def _fetch_text(url, timeout=_REMOTE_TIMEOUT):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "AdultHideout official-source-check",
            "Accept": "text/plain,application/xml,application/json,*/*",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def _parse_xml(text):
    try:
        return ET.fromstring(text)
    except Exception:
        return None


def _find_addon(root, addon_id):
    if root is None:
        return None
    if root.tag == "addon" and root.attrib.get("id") == addon_id:
        return root
    for addon in root.findall(".//addon"):
        if addon.attrib.get("id") == addon_id:
            return addon
    return None


def _check_installed_repository():
    issues = []
    try:
        repo = xbmcaddon.Addon(OFFICIAL_REPOSITORY_ID)
        repo_path = repo.getAddonInfo("path")
    except Exception:
        return [_lang(30600, OFFICIAL_REPOSITORY_ID)]

    addon_xml_path = os.path.join(repo_path, "addon.xml")
    root = _parse_xml(_read_text(addon_xml_path))
    if root is None:
        return [_lang(30601)]

    if root.attrib.get("id") != OFFICIAL_REPOSITORY_ID:
        issues.append(_lang(30602))

    urls = set()
    for tag in ("info", "checksum", "datadir"):
        for element in root.findall(".//{}".format(tag)):
            if element.text:
                urls.add(element.text.strip().rstrip("/"))

    expected = set(url.rstrip("/") for url in EXPECTED_REPO_URLS)
    if not expected.issubset(urls):
        issues.append(_lang(30603))
    return issues


def _check_official_metadata(addon_id, addon_version):
    issues = []
    try:
        addons_xml = _fetch_text(OFFICIAL_ADDONS_XML)
        expected_md5 = _fetch_text(OFFICIAL_ADDONS_MD5).strip().split()[0].lower()
    except Exception as exc:
        return [_lang(30604, exc)]

    actual_md5 = hashlib.md5(addons_xml.encode("utf-8")).hexdigest().lower()
    if expected_md5 and expected_md5 != actual_md5:
        issues.append(_lang(30605))

    root = _parse_xml(addons_xml)
    addon = _find_addon(root, addon_id)
    if addon is None:
        issues.append(_lang(30606))
        return issues

    official_version = addon.attrib.get("version", "")
    if official_version and addon_version and official_version != addon_version:
        issues.append(_lang(30607, addon_version, official_version))

    if addon.attrib.get("provider-name") != "Vashiel":
        issues.append(_lang(30608))

    metadata = addon.find("extension[@point='xbmc.addon.metadata']")
    mainsource = ""
    if metadata is not None:
        source_element = metadata.find("mainsource")
        mainsource = source_element.text.strip() if source_element is not None and source_element.text else ""
    if OFFICIAL_GITHUB_URL not in mainsource:
        issues.append(_lang(30609))

    return issues


def _load_hash_manifest(addon_path, prefer_remote=True):
    manifest_text = ""
    if prefer_remote:
        try:
            manifest_text = _fetch_text(OFFICIAL_HASHES)
        except Exception as exc:
            _log("Remote hash manifest unavailable: {}".format(exc), xbmc.LOGWARNING)

    if not manifest_text:
        local_path = os.path.join(addon_path, "resources", "official_hashes.json")
        manifest_text = _read_text(local_path)

    try:
        manifest = json.loads(manifest_text)
    except Exception:
        return None
    return manifest if isinstance(manifest, dict) else None


def _check_hashes(addon_path, prefer_remote=True):
    manifest = _load_hash_manifest(addon_path, prefer_remote=prefer_remote)
    if not manifest:
        return [_lang(30610)]

    hashes = manifest.get("hashes")
    if not isinstance(hashes, dict) or not hashes:
        return [_lang(30611)]

    issues = []
    checked = 0
    for rel_path, expected_hash in sorted(hashes.items()):
        if not rel_path or not expected_hash:
            continue
        local_path = os.path.join(addon_path, rel_path.replace("/", os.sep))
        data = _read_bytes(local_path)
        if not data:
            issues.append(_lang(30612, rel_path))
            continue
        actual_hash = hashlib.sha256(data).hexdigest().lower()
        if actual_hash != str(expected_hash).lower():
            issues.append(_lang(30613, rel_path))
            if len(issues) >= 5:
                break
        checked += 1

    if checked == 0:
        issues.append(_lang(30614))
    return issues


def _warning_text(issues):
    details = "\n".join("- {}".format(issue) for issue in issues[:6])
    if len(issues) > 6:
        details += "\n- {}".format(_lang(30615, len(issues) - 6))
    return (
        "{}\n\n"
        "{}\n\n"
        "{}\n"
        "{}\n\n"
        "{}\n"
        "{}\n\n"
        "{}"
    ).format(
        _lang(30616),
        details,
        _lang(30617),
        OFFICIAL_REPOSITORY_URL,
        _lang(30618),
        OFFICIAL_GITHUB_URL,
        _lang(30619),
    )


def verify_and_warn(addon, show_dialog=True):
    addon_id = addon.getAddonInfo("id")
    addon_path = addon.getAddonInfo("path")
    addon_version = addon.getAddonInfo("version")

    issues = []
    issues.extend(_check_installed_repository())
    if show_dialog:
        issues.extend(_check_official_metadata(addon_id, addon_version))
    issues.extend(_check_hashes(addon_path, prefer_remote=show_dialog))

    if not issues:
        _log("Official source check passed")
        return True

    message = _warning_text(issues)
    _log(message.replace("\n", " | "), xbmc.LOGWARNING)

    if show_dialog:
        xbmcgui.Dialog().ok(_lang(30620), message)
    else:
        xbmcgui.Dialog().notification(
            "AdultHideout",
            _lang(30621),
            xbmcgui.NOTIFICATION_WARNING,
            6000,
        )
    return False

