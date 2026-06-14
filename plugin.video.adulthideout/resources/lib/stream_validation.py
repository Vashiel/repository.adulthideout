# -*- coding: utf-8 -*-
import socket
import urllib.parse

import xbmc


def is_stream_host_resolvable(url, logger=None, timeout=4):
    """Return False when Kodi would clearly fail before opening the stream."""
    try:
        host = urllib.parse.urlparse(url).hostname
    except Exception:
        host = None
    if not host:
        return False

    previous_timeout = socket.getdefaulttimeout()
    try:
        socket.setdefaulttimeout(timeout)
        socket.getaddrinfo(host, None)
        return True
    except Exception as exc:
        message = "[AdultHideout][stream_validation] Stream host not resolvable: {} ({})".format(host, exc)
        if logger:
            try:
                logger.warning(message)
            except Exception:
                try:
                    logger(message, xbmc.LOGWARNING)
                except Exception:
                    xbmc.log(message, xbmc.LOGWARNING)
        else:
            xbmc.log(message, xbmc.LOGWARNING)
        return False
    finally:
        socket.setdefaulttimeout(previous_timeout)
