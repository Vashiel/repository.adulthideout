import re
import xbmc
from ..functions import add_dir, add_link, make_request, fanart, logos
import xbmcgui
import xbmcplugin
import xbmcaddon
import urllib.parse as urllib_parse

def process_uflash_content(url, page=1):
    if page == 1:
        add_dir(f'Search Uflash', 'uflash', 5, logos + 'uflash.png', fanart)
    content = make_request(url)
    match = re.compile('<a href="/video/(.+?)/.+?<img src="(.+?)" alt="(.+?)".+?<span class="duration">.+?([:\d]+).+?</span>', re.DOTALL).findall(content)
    for url, thumb, name, duration in match:
        name = name.replace('&amp;', '&').replace('&quot;', '"').replace('&#039;', '\'')
        add_link(name + ' [COLOR lime]('+ duration + ')[/COLOR]', 'http://www.uflash.tv/media/player/config.v89x.php?vkey=' + url,  4, 'http://www.uflash.tv/' + thumb, fanart)
    try:
        next_page = uflash_nextpage(current_url, content)
        raise Exception(next_page)
    except Exception as e:
        xbmc.log(str(e), xbmc.LOGERROR)
        pass


def play_uflash_video(url):
    content = make_request(url)
    media_url = re.compile('<source src="(.+?)" type="video/mp4">').findall(content)[0]
    media_url = media_url.replace('amp;', '')
    return media_url
