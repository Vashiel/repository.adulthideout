# -*- coding: utf-8 -*-
"""Stub of the xbmc module: logging plus the few calls the site modules make."""

import time

LOGDEBUG = 0
LOGINFO = 1
LOGWARNING = 2
LOGERROR = 3
LOGFATAL = 4
LOGNONE = -1

_LOG = []
INFO = {}


def log(msg, level=LOGINFO):
    _LOG.append((level, str(msg)))


def loglines():
    return list(_LOG)


def clear_log():
    _LOG.clear()


def translatePath(path):
    return path


def getCondVisibility(condition):
    return False


def getInfoLabel(label):
    return INFO.get(label, "")


def getInfoBool(label):
    return False


def executebuiltin(command, wait=False):
    INFO.setdefault("builtins", []).append(command)


def sleep(ms):
    time.sleep(min(ms, 2000) / 1000.0)


def getLanguage(*args, **kwargs):
    return "en"


def getSkinDir():
    return "skin.estuary"


def getRegion(*args, **kwargs):
    return ""


def endOfService():
    return None


def abortRequested():
    return False


class Monitor(object):
    def waitForAbort(self, timeout=0.0):
        if timeout:
            time.sleep(min(timeout, 0.2))
        return False

    def abortRequested(self):
        return False


class Player(object):
    def __init__(self, *args, **kwargs):
        self._playing = False

    def play(self, *args, **kwargs):
        self._playing = True

    def playList(self, *args, **kwargs):
        self._playing = True

    def stop(self):
        self._playing = False

    def isPlaying(self):
        return self._playing

    def isPlayingVideo(self):
        return self._playing

    def getPlayingFile(self):
        return ""

    def getTime(self):
        return 0.0

    def getTotalTime(self):
        return 0.0

    def getProperty(self, *args, **kwargs):
        return ""

    def setProperty(self, *args, **kwargs):
        return None


class PlayList(object):
    def __init__(self, *args, **kwargs):
        self._items = []

    def clear(self):
        self._items = []

    def add(self, *args, **kwargs):
        self._items.append(args[0] if args else None)

    def size(self):
        return len(self._items)

    def __len__(self):
        return len(self._items)


def __getattr__(name):
    """Any other xbmc.* call the addon makes: a no-op returning ''."""
    def _noop(*args, **kwargs):
        return ""
    return _noop
