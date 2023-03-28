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
        match = re.compile('title="([^"]*)" href="([^"]*)".+?<img src="([^"]*)"', re.DOTALL).findall(content)
        for name, url, thumb in match:
            thumb = thumb.replace(' ', '%20')
            if "Raw" in name :
                add_link('[COLOR lime] [Raw] [/COLOR]' + name, url, 4, thumb, fanart)
            else :
                add_link('[COLOR yellow] [Subbed] [/COLOR]' + name, url, 4, thumb, fanart)
        try:
            match = re.compile("<a href='([^']*)' class=\"next\">»").findall(content)
            add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', match[0], 2, logos + 'hentaigasm.png', fanart)
        except:
            pass


def play_hentaigasm_video(url):
    content = make_request(url)
    media_url = re.compile('file: "(.+?)",').findall(content)[0]
    return media_url
