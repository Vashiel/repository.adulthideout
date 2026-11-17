# -*- coding: utf-8 -*-
"""Stub of the xbmcgui module. List items and dialogs record what they were asked to do."""

DIALOG_ICON = 0
DIALOG_YES_NO = 1
DIALOG_OK_CANCEL = 2
DIALOG_MSG_YES_NO = 1
DIALOG_NUMERIC = 3
NOTIFICATION_INFO = "info"
NOTIFICATION_WARNING = "warning"
NOTIFICATION_ERROR = "error"


class ListItem(object):
    def __init__(self, label="", label2="", path="", offscreen=False):
        self.label = label
        self.label2 = label2
        self.path = path
        self._properties = {}
        self._info = {}
        self._art = {}
        self._mime = ""
        self._content_lookup = True

    # path / media
    def setPath(self, path):
        self.path = path

    def getPath(self):
        return self.path

    def setMimeType(self, mime):
        self._mime = mime

    def getMimeType(self):
        return self._mime

    def setContentLookup(self, enable):
        self._content_lookup = bool(enable)

    def setLabel(self, label):
        self.label = label

    def getLabel(self):
        return self.label

    def setLabel2(self, label):
        self.label2 = label

    # properties
    def setProperty(self, key, value):
        self._properties[key] = value

    def getProperty(self, key):
        return self._properties.get(key, "")

    def setProperties(self, values):
        for key, value in (values or {}).items():
            self._properties[key] = value

    # info / art
    def setInfo(self, type, infoLabels):
        self._info.update(infoLabels or {})

    def getInfo(self, key):
        return self._info.get(key, "")

    def infos(self):
        return dict(self._info)

    def setArt(self, values):
        self._art.update(values or {})

    def setArtwork(self, values):
        self._art.update(values or {})

    def addStreamInfo(self, *args, **kwargs):
        return None

    def setIsPlayable(self, value=True):
        self._properties["IsPlayable"] = "true" if value else "false"

    def addContextMenuItems(self, items, replaceItems=False):
        self._properties.setdefault("context", []).extend(items or [] if isinstance(items, list) else [items])

    def getVideoInfoTag(self):
        return InfoTag()

    def setUniqueIDs(self, values, defaultrating=""):
        return None

    def addAvailableArtwork(self, *args, **kwargs):
        return None

    def setSubtitles(self, subtitles):
        return None

    def __getattr__(self, name):
        # Any further ListItem call: a no-op that returns ''.
        def _noop(*args, **kwargs):
            return ""
        return _noop

    def as_dict(self):
        return {
            "label": self.label,
            "path": self.path,
            "properties": dict(self._properties),
            "info": dict(self._info),
            "art": dict(self._art),
            "mime": self._mime,
        }


class InfoTag(object):
    def __getattr__(self, name):
        def _noop(*args, **kwargs):
            return ""
        return _noop


class Dialog(object):
    def __init__(self):
        self.calls = []

    def ok(self, heading, message=""):
        self.calls.append(("ok", heading, message))
        return True

    def notification(self, heading, message="", icon="", time=5000, sound=True):
        self.calls.append(("notification", heading, message))
        return None

    def yesno(self, heading, message="", *args, **kwargs):
        self.calls.append(("yesno", heading, message))
        return False

    def input(self, heading, default="", type=0, option=0, autoclose=0):
        return ""

    def select(self, heading, list, autoclose=0, preselect=-1, useDetails=False):
        return -1

    def numeric(self, type, heading, default=""):
        return ""

    def textviewer(self, heading, text, usemono=False):
        return None

    def browse(self, *args, **kwargs):
        return ""

    def multiselect(self, heading, options, autoclose=0, preselect=None, useDetails=False):
        return None


class DialogProgress(object):
    def __init__(self, *args, **kwargs):
        self._messages = []

    def create(self, heading="", message=""):
        return None

    def update(self, percent=0, message=""):
        self._messages.append((percent, message))
        return None

    def close(self):
        return None

    def iscanceled(self):
        return False


class DialogProgressBG(object):
    def create(self, *args, **kwargs):
        return None

    def update(self, *args, **kwargs):
        return None

    def close(self):
        return None


class Window(object):
    def __init__(self, *args, **kwargs):
        self._props = {}

    def getProperty(self, key):
        return self._props.get(key, "")

    def setProperty(self, key, value):
        self._props[key] = value

    def clearProperty(self, key):
        self._props.pop(key, None)

    def clearProperties(self):
        self._props.clear()

    def doModal(self):
        return None

    def close(self):
        return None

    def show(self):
        return None


class WindowXML(Window):
    pass


class WindowDialogMixin(object):
    pass


class WindowXMLDialog(Window):
    pass


def __getattr__(name):
    def _noop(*args, **kwargs):
        return ""
    return _noop
