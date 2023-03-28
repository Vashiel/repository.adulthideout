import re
import xbmc
import base64
from ..functions import add_dir, add_link, make_request, fanart, logos
import xbmcgui
import xbmcplugin
import xbmcaddon
import urllib.parse as urllib_parse


def process_uflash_content(url, mode=None):
    if "search" not in url:
        url = url + "/videos?g=female&o=mr&type=public"

    content = make_request(url)
    add_dir('[COLOR blue]Search[/COLOR]', 'uflash', 5, logos + 'uflash.png', fanart)
    match = re.compile('<a href="([^"]*)">.+?<img src="([^"]*)" alt="([^"]*)"/>', re.DOTALL).findall(content)
    for url, thumb, name in match:
        name = name.replace('&amp;', '&').replace('&quot;', '"').replace('&#039;', '\'')
        add_link(name, 'http://www.uflash.tv' + url,  4, 'http://www.uflash.tv/' + thumb, fanart)
    try:
        next_page = uflash_nextpage(url, content)
        add_dir('[COLOR blue]Next Page >>[/COLOR]', next_page, 1, logos + 'uflash.png', fanart)
    except Exception as e:
        xbmc.log(str(e), xbmc.LOGERROR)
        pass

def play_uflash_video(url):
    content = make_request(url)
    match = re.compile(r'_8xHp9vZ2\s*=\s*"([^"]+)"', re.IGNORECASE | re.DOTALL).findall(content)
    for media_url in match:
        media_url = base64.b64decode(match[0]).decode("utf-8")
        return media_url

def uflash_nextpage(current_url, content):
    match = re.search(r'href="([^"]+)"\s*rel="next"', content)
    if match:
        next_page = match.group(1)
        return 'http://www.uflash.tv' + next_page
    else:
        raise Exception("Next page not found")
