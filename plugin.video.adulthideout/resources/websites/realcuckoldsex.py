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


def process_realcuckoldsex_content(url):
    xbmc.log("process_realcuckoldsex_content: " + url, xbmc.LOGINFO)
    if "search" not in url and "channels" not in url:
        url = url + "/latest-updates/"
  
    content = make_request(url).replace('\n', '').replace('\r', '')
    #xbmc.log("realcuckoldsex content: " + content, xbmc.LOGINFO)
    match = re.compile('<a target="_blank" href="([^"]+)" title="([^"]+)">.+?<img src="([^"]+)"', re.DOTALL).findall(content)
    for video_url, name, thumb in match:
        #xbmc.log("realcuckoldsex match: " + name, xbmc.LOGINFO)
        name = html.unescape(name)
        add_link(name, video_url, 4, thumb, fanart)

    try:
        parsed_url = urlparse(url)
        base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
        match = re.compile('<a href="([^"]+)">Next<').findall(content)
        next_url = base_url + match[0]
        add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', next_url, 2, logos + 'realcuckoldsex.png', fanart)
    except:
        pass

def play_realcuckoldsex_video(url):
    xbmc.log("Play realcuckoldsex URL: " + url, xbmc.LOGINFO)
    content = make_request(url).replace('\n', '').replace('\r', '')
    xbmc.log("Play realcuckoldsex content: " + content, xbmc.LOGINFO)
    media_url = re.compile('video_url: \'([^"]+)mp4').findall(content)[0]+'mp4'
    media_url = media_url.replace('amp;', '')
    xbmc.log("Media URL: " + media_url, xbmc.LOGINFO)
    return media_url

