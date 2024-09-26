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
    if "latest-updates" not in url and "search" not in url and "channels" not in url:
        url = url + "/latest-updates/"
  
    content = make_request(url).replace('\n', '').replace('\r', '')
    match = re.compile('<a target="_blank" href="([^"]+)">.+?data-original="([^"]+)" alt="([^"]+)"', re.DOTALL).findall(content)
    
    for video_url, thumb, name in match:
        name = html.unescape(name)
        add_link(name, video_url, 4, thumb, fanart)
    
    try:
        parsed_url = urlparse(url)
        base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
        
        match = re.compile('<a href="([^"]+)">Next<').findall(content)
        next_url = match[0]
        
        if not next_url.startswith('http'):
            next_url = base_url + next_url
        
        add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', next_url, 2, logos + 'realcuckoldsex.png', fanart)
    except Exception as e:
        logging.error(f"Error processing next page link: {e}")
        pass


def play_realcuckoldsex_video(url):
    content = make_request(url).replace('\n', '').replace('\r', '')
    media_url = re.compile(r"video_url: '([^']+\.mp4)'").findall(content)[0]
    media_url = media_url.replace('amp;', '')
    return media_url
