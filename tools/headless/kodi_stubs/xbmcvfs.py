# -*- coding: utf-8 -*-
"""Stub of the xbmcvfs module backed by the real file system."""

import os
import shutil


def translatePath(path):
    return path


def exists(path):
    return os.path.exists(path)


def mkdir(path):
    try:
        os.makedirs(path, exist_ok=True)
        return True
    except OSError:
        return False


def mkdirs(path):
    return mkdir(path)


def listdir(path):
    # Kodi returns plain names in both lists, not (name, path) tuples.
    try:
        dirs = []
        files = []
        for name in os.listdir(path):
            full = os.path.join(path, name)
            if os.path.isdir(full):
                dirs.append(name)
            else:
                files.append(name)
        return dirs, files
    except OSError:
        return [], []


def delete(path):
    try:
        os.remove(path)
        return True
    except OSError:
        return False


def rmdir(path, force=False):
    try:
        if force:
            shutil.rmtree(path, ignore_errors=True)
        else:
            os.rmdir(path)
        return True
    except OSError:
        return False


def rename(source, destination):
    try:
        os.replace(source, destination)
        return True
    except OSError:
        return False


def copy(source, destination):
    try:
        shutil.copy(source, destination)
        return True
    except OSError:
        return False


def stat(path):
    try:
        info = os.stat(path)
        return {
            "size": info.st_size,
            "mtime": int(info.st_mtime),
            "mode": info.st_mode,
        }
    except OSError:
        return None


class File(object):
    def __init__(self, path, mode="r"):
        self.path = path
        self.mode = mode.replace("b", "") if "b" in mode else mode
        self._handle = None
        # Kodi opens the file on construction; callers call readBytes() straight away.
        if not str(path).startswith(("http://", "https://")):
            self.open()

    def open(self):
        try:
            self._handle = open(self.path, self.mode, encoding=None if "b" in self.mode else "utf-8")
            return True
        except OSError:
            return False

    def write(self, data):
        if self._handle is None and "w" in self.mode:
            self.open()
        self._handle.write(data)
        return True

    def read(self):
        return self._handle.read() if self._handle else b""

    def readBytes(self, numbytes):
        return self._handle.read(numbytes) if self._handle else b""

    def close(self):
        if self._handle:
            self._handle.close()

    def size(self):
        try:
            return os.path.getsize(self.path)
        except OSError:
            return 0


def __getattr__(name):
    def _noop(*args, **kwargs):
        return ""
    return _noop
