import re
import xbmc
from ..functions import add_dir, add_link, make_request, fanart, logos
import xbmcgui
import xbmcplugin
import xbmcaddon
import urllib.parse as urllib_parse

def process_tubedupe_content(url, page=1):
    if "search" not in url:
        url = url + "/latest-updates/"
    if page == 1:
        add_dir(f'Search Tubedupe', 'tubedupe', 5, logos + 'tubedupe.png', fanart)
    content = make_request(url)
    match = re.compile('<a href="([^"]+)" class="kt_imgrc" title="([^"]+)">.+?<img src="([^"]+)".+?<var class="duree">([:\d]+)</var>', re.DOTALL).findall(content)
    for url, name, thumb, duration in match:
        add_link(name + ' [COLOR lime]('+ duration + ')[/COLOR]', 'https://tubedupe.com' + url, 4, thumb, fanart)
    try:
        match = re.compile('<link href="([^"]*)" rel="next"/>').findall(content)
        add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', match[0], 2, logos + 'tubedupe.png', fanart)
    except:
        pass
        
def play_tubedupe_video(url):
    content = make_request(url)
    media_url = re.compile("video_alt_url: '(.+?)',                 video_alt_url_text: '720p',").findall(content)[0]
    return media_url
