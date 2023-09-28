import re
import xbmc
from ..functions import add_dir, add_link, make_request, fanart, logos
import xbmcgui
import xbmcplugin
import xbmcaddon
import urllib.parse as urllib_parse
from urllib.parse import urlparse
import html
import sys


def process_punishbang_content(url):
    #xbmc.log("process_punishbang_content: " + url, #xbmc.logINFO)
    if "search" not in url and "channels" not in url:
        url = url + "/videos/"
    if 'https://www.punishbang.com/channels/' == url:
        process_punishbang_categories(url)
    else:
        content = make_request(url).replace('\n', '').replace('\r', '')
        #xbmc.log("punishbang content: " + content, #xbmc.logINFO)
        add_dir("Categories", "https://www.punishbang.com/channels/", 2, logos + 'punishbang.png', fanart)
        add_dir(f'Search punishbang', 'punishbang', 5, logos + 'punishbang.png', fanart)
        match = re.compile('<a href="([^"]+)".+?data-src="([^"]+)".+?alt="([^"]+)"', re.DOTALL).findall(content)
        for video_url, thumb, name in match:
            #xbmc.log("punishbang match: " + name, #xbmc.logINFO)
            name = html.unescape(name)
            add_link(name, video_url, 4, thumb, fanart)
        add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', 'https://www.punishbang.com/videos/#videos', 2, logos + 'punishbang.png', fanart)

def process_punishbang_categories(url):
    content = make_request(url).replace('\n', '').replace('\r', '')
    #xbmc.log("punishbang category content: " + content, #xbmc.logINFO)
    #categories = re.compile('<a href="([^"]+)" class="card card--primary" title="([^"]+)".+?<img src="([^"]+)"', re.DOTALL).findall(content)
    categories = re.compile('<a href="([^"]+)".+?data-src="([^"]+)".+?alt="([^"]+)"', re.DOTALL).findall(content)
    for video_url, thumb, name  in categories:
        #xbmc.log("punishbang category: " + name, #xbmc.logINFO)
        add_dir(name, video_url, 2, thumb, fanart)

def play_punishbang_video(url):
    #xbmc.log("Play punishbang URL: " + url, #xbmc.logINFO)
    content = make_request(url).replace('\n', '').replace('\r', '')
    #xbmc.log("Play punishbang content: " + content, #xbmc.logINFO)
    media_url = re.compile('video_url: \'([^"]+)\/\'').findall(content)[0]
    media_url = media_url.replace('amp;', '')
    #xbmc.log("Media URL: " + media_url, #xbmc.logINFO)
    return media_url
