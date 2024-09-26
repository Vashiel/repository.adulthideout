import re
import xbmc
from ..functions import add_link, add_dir, make_request, fanart, logos
import xbmcgui
import xbmcplugin
import xbmcaddon
from urllib.parse import urlparse, urljoin

def process_hentaigasm_content(url, page=1):
    xbmc.log("Entering process_hentaigasm_content with URL: " + url, xbmc.LOGINFO)
    content = make_request(url)
    # Add search option
    add_dir(f'Search Hentaigasm', 'hentaigasm', 5, logos + 'hentaigasm.png', fanart)
    # Find video links
    match = re.findall(r'<div class="thumb">.*?<a class="clip-link" data-id="\d+" title="([^"]+)" href="([^"]+)">.*?<img src="([^"]+)"', content, re.DOTALL)
    
    if match:
        for title, video_url, thumb in match:
            video_url = video_url.replace(' ', '%20')
            thumb = thumb.replace(' ', '%20')
            add_link(f'[COLOR yellow] [Subbed] [/COLOR]{title}', video_url, 4, thumb, fanart)
    else:
        xbmc.log("No video links found on the main page.", xbmc.LOGERROR)

    # Find next page link
    next_page_match = re.search(r'<a class="nextpostslink" rel="next" aria-label="Next Page" href="([^"]+)">»</a>', content)
    if next_page_match:
        next_page_url = next_page_match.group(1).replace(' ', '%20')
        add_dir('[COLOR blue]Next Page >>>[/COLOR]', next_page_url, 2, logos + 'hentaigasm.png', fanart)
    
    # Find previous page link
    previous_page_match = re.search(r'<a class="prevpostslink" rel="prev" aria-label="Previous Page" href="([^"]+)">«</a>', content)
    if previous_page_match:
        previous_page_url = previous_page_match.group(1).replace(' ', '%20')
        add_dir('[COLOR blue]<<< Previous Page[/COLOR]', previous_page_url, 2, logos + 'hentaigasm.png', fanart)

def play_hentaigasm_video(url):
    content = make_request(url)
    match = re.search(r'file:\s*"([^"]+)"', content)
    if match:
        media_url = match.group(1).replace(' ', '%20')
        return media_url
    else:
        xbmc.log("No media URL found in Hentaigasm content.", xbmc.LOGERROR)
        return None
