# -*- coding: utf-8 -*-
import re
import xbmc
import urllib.parse
from resources.lib.resolvers import resolver_utils
from resources.lib.resolvers import doodstream_resolver
from resources.lib.resolvers import lulustream_resolver
from resources.lib.resolvers import voesx_resolver
from resources.lib.resolvers import bigwarp_resolver

def resolve(url, referer="", headers=None):
    xbmc.log("[AdultHideout][resolver] Input: {}".format(url), xbmc.LOGINFO)

    hoster_map = {
        "dood": doodstream_resolver,
        "dsvplay": doodstream_resolver,
        "lulu": lulustream_resolver,
        "lulustream": lulustream_resolver,
        "voe.sx": voesx_resolver,
        "voe-unblock": voesx_resolver,
        "voeunblock": voesx_resolver,
        "un-block-voe": voesx_resolver,
        "v-o-e-unblock": voesx_resolver,
        "audaciousdefaulthouse.com": voesx_resolver,
        "launchreliantcleaverriver.com": voesx_resolver,
        "fittingcentermondaysunday.com": voesx_resolver,
        "bigwarp": bigwarp_resolver,
        "bgwp": bigwarp_resolver,

    }

    selected_module = None
    try:
        parsed_url = urllib.parse.urlparse(url)
        hostname = parsed_url.netloc if parsed_url.netloc else ""
    except Exception:
        hostname = ""
        xbmc.log(f"[AdultHideout][resolver] Failed to parse hostname from URL: {url}", xbmc.LOGWARNING)

    for key, module in hoster_map.items():
        if key == hostname or hostname.endswith('.' + key):
            selected_module = module
            xbmc.log("[AdultHideout][resolver] Using {} for {} (Hostname Match)".format(module.__name__, url), xbmc.LOGINFO)
            break

    if selected_module is None:
         for key, module in hoster_map.items():
             if key in hostname:
                   selected_module = module
                   xbmc.log("[AdultHideout][resolver] Using {} for {} (Substring Hostname Match)".format(module.__name__, url), xbmc.LOGINFO)
                   break
             elif key in url:
                   selected_module = module
                   xbmc.log("[AdultHideout][resolver] Using {} for {} (URL Fallback Match - Less Reliable)".format(module.__name__, url), xbmc.LOGINFO)
                   break

    if selected_module:
         try:
              xbmc.log("[AdultHideout][resolver] Executing custom resolver {} for {}".format(selected_module.__name__, url), xbmc.LOGINFO)
              return selected_module.resolve(url, referer, headers)
         except Exception as e:
              import traceback
              xbmc.log("[AdultHideout][resolver] Error in custom resolver {}: {}\n{}".format(selected_module.__name__, e, traceback.format_exc()), xbmc.LOGERROR)
              return "", {}


    xbmc.log("[AdultHideout][resolver] No custom resolver found for {}. Passing URL to Kodi/ResolveURL.".format(url), xbmc.LOGINFO)
    final_headers = headers or {}
    final_headers.setdefault("User-Agent", resolver_utils.get_ua())
    if referer:
         final_headers["Referer"] = referer

    header_string = urllib.parse.urlencode(final_headers)
    return url + "|" + header_string, {}