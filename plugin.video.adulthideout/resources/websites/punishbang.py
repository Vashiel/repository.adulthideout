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
from urllib.parse import urlparse, parse_qs, urlencode

def process_punishbang_content(url):
    if "videos" not in url and "search" not in url and "channels" not in url:
        url = url + "/videos/?from=1"
    
    if 'https://www.punishbang.com/channels/' == url:
        process_punishbang_categories(url)
    else:
        content = make_request(url).replace('\n', '').replace('\r', '')
        
        add_dir("Categories", "https://www.punishbang.com/channels/", 2, logos + 'punishbang.png', fanart)
        add_dir(f'Search punishbang', 'punishbang', 5, logos + 'punishbang.png', fanart)
        
        match = re.compile('<a href="([^"]+)".+?data-src="([^"]+)".+?alt="([^"]+)"', re.DOTALL).findall(content)
        for video_url, thumb, name in match:
            name = html.unescape(name)
            add_link(name, video_url, 4, thumb, fanart)

        parsed_url = urlparse(url)
        query_params = parse_qs(parsed_url.query)
        current_from = int(query_params.get('from', [1])[0])  
        next_from = current_from + 1  
        
        base_url = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}"
        next_query_params = query_params
        next_query_params['from'] = next_from  
        next_url = f"{base_url}?{urlencode(next_query_params, doseq=True)}"
        
        add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', next_url, 2, logos + 'punishbang.png', fanart)


def process_punishbang_categories(url):
    content = make_request(url).replace('\n', '').replace('\r', '')
    categories = re.compile('<a href="([^"]+)".+?data-src="([^"]+)".+?alt="([^"]+)"', re.DOTALL).findall(content)
    for video_url, thumb, name  in categories:
        add_dir(name, video_url, 2, thumb, fanart)

def play_punishbang_video(url):
    content = make_request(url).replace('\n', '').replace('\r', '')
    media_url = re.compile('video_url: \'([^"]+)\/\'').findall(content)[0]
    media_url = media_url.replace('amp;', '')
    return media_url



