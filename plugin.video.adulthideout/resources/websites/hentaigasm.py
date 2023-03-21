import re
import xbmc
from ..functions import add_dir, add_link, make_request, fanart, logos
import xbmcgui
import xbmcplugin
import xbmcaddon
import urllib.parse as urllib_parse

def process_hentaigasm_content(url, page=1):
    if page == 1:
        add_dir(f'Search Hentaigasm', 'hentaigasm', 5, logos + 'hentaigasm.png', fanart)
    content = make_request(url)
    match = re.compile('href="([^"]*)"', re.DOTALL).findall(content)
    for url in match:
        name = url
        add_link('[COLOR lime] [Raw] [/COLOR]' + name, url, 4, logos + 'hentaigasm.png', fanart)



def play_hentaigasm_video(url):
    content = make_request(url)
    media_url = re.compile('<source src="(.+?)" type="video/mp4">').findall(content)[0]
    media_url = media_url.replace('amp;', '')
    return media_url
