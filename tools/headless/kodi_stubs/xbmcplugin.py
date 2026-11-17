# -*- coding: utf-8 -*-
"""Stub of the xbmcplugin module: records directory items and resolved URLs."""

DIRECTORY = []
RESOLVED = []
CONTENT = []


def reset():
    del DIRECTORY[:]
    del RESOLVED[:]
    del CONTENT[:]


def addDirectoryItem(handle, url, listitem=None, isFolder=False, totalItems=0):
    DIRECTORY.append({
        "handle": handle,
        "url": url,
        "is_folder": bool(isFolder),
        "item": listitem.as_dict() if hasattr(listitem, "as_dict") else None,
    })
    return True


def addDirectoryItems(handle, items, totalItems=0):
    for url, listitem, isFolder in items:
        addDirectoryItem(handle, url, listitem, isFolder)
    return True


def endOfDirectory(handle, succeeded=True, updateListing=False, cacheToDisc=True):
    return None


def setResolvedUrl(handle, succeeded, listitem=None):
    RESOLVED.append({
        "handle": handle,
        "succeeded": bool(succeeded),
        "item": listitem.as_dict() if hasattr(listitem, "as_dict") else None,
    })
    return None


def setContent(handle, content):
    CONTENT.append(content)
    return None


def setPluginCategory(handle, category):
    return None


def setPluginFanart(handle, image, *args, **kwargs):
    return None


def addSortMethod(handle, sortMethod, label2Mask="", *args, **kwargs):
    return None


def setSetting(handle, id, value):
    return None


def __getattr__(name):
    def _noop(*args, **kwargs):
        return ""
    return _noop
