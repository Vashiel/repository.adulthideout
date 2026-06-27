# -*- coding: utf-8 -*-
import json
import os
import socket
import time

try:
    import xbmc
except Exception:
    xbmc = None

try:
    import xbmcaddon
    import xbmcvfs
except Exception:
    xbmcaddon = None
    xbmcvfs = None

_INSTALLED = False
_ORIGINAL_GETADDRINFO = socket.getaddrinfo
_CACHE = None
_CACHE_FILE = "dns_cache.json"
_CACHE_TTL = 6 * 60 * 60


def _log(message, level=None):
    if xbmc is None:
        return
    try:
        xbmc.log("[AdultHideout][dns_retry] {}".format(message), level or xbmc.LOGDEBUG)
    except Exception:
        pass


def _host_key(host):
    if host is None:
        return None
    try:
        if isinstance(host, bytes):
            host = host.decode("idna")
        host = str(host).strip().lower().rstrip(".")
        if not host:
            return None
        try:
            socket.inet_pton(socket.AF_INET, host)
            return None
        except Exception:
            pass
        try:
            socket.inet_pton(socket.AF_INET6, host)
            return None
        except Exception:
            pass
        return host
    except Exception:
        return None


def _profile_dir():
    if xbmcaddon is None:
        return None
    try:
        profile = xbmcaddon.Addon().getAddonInfo("profile")
        if xbmcvfs is not None:
            profile = xbmcvfs.translatePath(profile)
        if not profile:
            return None
        try:
            os.makedirs(profile, exist_ok=True)
        except Exception:
            pass
        return profile
    except Exception:
        return None


def _cache_path():
    profile = _profile_dir()
    if not profile:
        return None
    return os.path.join(profile, _CACHE_FILE)


def _load_cache():
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    _CACHE = {}
    path = _cache_path()
    if not path or not os.path.exists(path):
        return _CACHE
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(data, dict):
            _CACHE = data
    except Exception:
        _CACHE = {}
    return _CACHE


def _save_cache():
    path = _cache_path()
    if not path:
        return
    try:
        tmp_path = path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as handle:
            json.dump(_CACHE or {}, handle, separators=(",", ":"))
        os.replace(tmp_path, path)
    except Exception:
        pass


def _serialize_result(result):
    records = []
    for family, socktype, proto, canonname, sockaddr in result or []:
        try:
            records.append([
                int(family),
                int(socktype),
                int(proto),
                canonname or "",
                list(sockaddr),
            ])
        except Exception:
            continue
    return records


def _restore_result(records, family, socktype, proto):
    result = []
    for record in records or []:
        try:
            rec_family, rec_socktype, rec_proto, canonname, sockaddr = record
            if family not in (0, rec_family):
                continue
            if socktype not in (0, rec_socktype):
                continue
            if proto not in (0, rec_proto):
                continue
            result.append((rec_family, rec_socktype, rec_proto, canonname or "", tuple(sockaddr)))
        except Exception:
            continue
    return result


def _store_result(host, result):
    key = _host_key(host)
    records = _serialize_result(result)
    if not key or not records:
        return
    cache = _load_cache()
    cache[key] = {"timestamp": time.time(), "records": records}
    _save_cache()


def _cached_result(host, family, socktype, proto):
    key = _host_key(host)
    if not key:
        return None
    entry = _load_cache().get(key)
    if not isinstance(entry, dict):
        return None
    try:
        age = time.time() - float(entry.get("timestamp", 0))
    except Exception:
        return None
    if age < 0 or age > _CACHE_TTL:
        return None
    result = _restore_result(entry.get("records"), family, socktype, proto)
    if result:
        _log("using cached DNS for {} after getaddrinfo 11002".format(key))
        return result
    return None


def install(retries=7, delay=0.35):
    global _INSTALLED
    if _INSTALLED or os.name != "nt":
        return

    def getaddrinfo_with_retry(host, port, family=0, type=0, proto=0, flags=0):
        last_error = None
        for attempt in range(1, int(retries) + 1):
            try:
                result = _ORIGINAL_GETADDRINFO(host, port, family, type, proto, flags)
                _store_result(host, result)
                return result
            except socket.gaierror as exc:
                last_error = exc
                if getattr(exc, "errno", None) != 11002:
                    raise
                if attempt >= int(retries):
                    cached = _cached_result(host, family, type, proto)
                    if cached:
                        return cached
                    raise
                _log("retrying DNS for {} after getaddrinfo 11002 ({}/{})".format(host, attempt, retries))
                time.sleep(float(delay) * attempt)
        raise last_error

    socket.getaddrinfo = getaddrinfo_with_retry
    _INSTALLED = True
    _log("installed Windows getaddrinfo retry")
