import re
import json
import urllib.parse as urllib_parse
import logging
import html
from urllib.parse import urlparse
from ..functions import add_dir, add_link, make_request, fanart, logos

def process_redtube_content(url, page=1):
    if "search" not in url and "/newest" not in url:
        url = url + "/newest"
    if page == 1:
        add_dir(f'Search redtube', 'redtube', 5, logos + 'redtube.png', fanart)
    content = make_request(url)
    match = re.compile('class="video_link.+?data-o_thumb="([^"]+).+?duration">\s*(?:<span.+?</span>)?\s*([\d:]+).+?href="([^"]+)"\s*>\s*(.*?)\s*<', re.DOTALL).findall(content)
    parsed_url = urlparse(url)
    base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
    for thumb, duration, url, name in match:
        clean_url = html.unescape(url)
        clean_name = html.unescape(name)
        add_link(clean_name + ' [COLOR lime]('+ duration + ')[/COLOR]', base_url + clean_url, 4, thumb, fanart)
    try:
        match = re.compile('<link rel="next" href="([^"]+)" />').findall(content)
        add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', match[0], 2, logos + 'redtube.png', fanart)
    except:
        pass


def play_redtube_video(url):
    content = make_request(url)
    media_definition_match = re.search(r'mediaDefinition\s*:\s*(\[[^\]]+\])', content)
    if media_definition_match:
        media_definition_json = media_definition_match.group(1)
        media_definition = json.loads(media_definition_json)
        hls_url = None
        for media in media_definition:
            if media['format'] == 'hls':
                hls_url = media['videoUrl'].replace('\\', '')
                break
        if hls_url:
            full_hls_url = "https://redtube.com" + hls_url
            hls_content = make_request(full_hls_url)
            video_links = json.loads(hls_content)
            best_video_url = None
            for video in video_links:
                if video.get('quality') == '1080':
                    best_video_url = video['videoUrl']
                    break
                elif video.get('quality') == '720' and not best_video_url:
                    best_video_url = video['videoUrl']
            if best_video_url:
                best_video_url = best_video_url.replace('\\', '')
                logging.info(f"Beste Video-URL: {best_video_url}")
                return best_video_url
            else:
                logging.error("Keine Video-URL in der gewünschten Qualität gefunden.")
                return None
        else:
            logging.error("HLS-URL nicht gefunden.")
            return None
    else:
        logging.error("mediaDefinition nicht gefunden.")
        return None
