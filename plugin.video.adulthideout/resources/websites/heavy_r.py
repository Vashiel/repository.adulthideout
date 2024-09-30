import re
import sys
import threading
import os
import hashlib
import urllib.parse as urllib_parse
from urllib.parse import urlparse, urljoin
import urllib.request as urllib_request
import xbmc
import xbmcvfs
import xbmcgui
import xbmcplugin
import xbmcaddon
from http.server import SimpleHTTPRequestHandler
import socketserver
from kodi_six import xbmc, xbmcaddon

from ..functions import add_dir, add_link, make_request, fanart, logos

addon = xbmcaddon.Addon()
handle = int(sys.argv[1])

httpd = None

def delete_downloaded_videos():
    folder_path = xbmcvfs.translatePath('special://home/addons/plugin.video.adulthideout/temp/')
    
    if xbmcvfs.exists(folder_path):
        for filename in os.listdir(folder_path):
            if filename.endswith(".mp4"):
                file_path = os.path.join(folder_path, filename)
                xbmcvfs.delete(file_path)
                xbmc.log(f"Deleted file: {file_path}", xbmc.LOGINFO)

delete_downloaded_videos()


def process_heavy_r_content(url, mode=None):
    if "search" not in url and "newest" not in url:
        url = url
    if url == 'https://www.heavy-r.com/categories/':
        process_heavy_r_categories(url)
    else:
        content = make_request(url)
        add_dir('[COLOR blue]Search[/COLOR]', 'heavy-r', 5, logos + 'heavy-r.png', fanart)
        add_dir("Categories", "https://www.heavy-r.com/categories/", 2, logos + 'heavy-r.png', fanart)
        match = re.compile('<a href="([^"]+)" class="image">.+?<img src="([^"]+)".+?alt="([^"]+)"', re.DOTALL).findall(content)
        parsed_url = urlparse(url)
        base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
        for video_url, thumb, name in match:
            full_url = urljoin(base_url, video_url)
            add_link(name, full_url, 4, thumb, fanart)

        try:
            match = re.compile('<li><a class="nopopoff" href="([^"]+)">Next</a></li>').findall(content)
            add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', urljoin(base_url, match[0]), 2, logos + 'heavy-r.png', fanart)
        except:
            pass

def process_heavy_r_categories(url):
    content = make_request(url)
    parsed_url = urlparse(url)
    base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
    categories = re.compile('<a href="([^"]*)" class="image nopopoff">.+?<img src="([^"]*)" alt="([^"]*)" class="img-responsive">', re.DOTALL).findall(content)
    for video_url, thumb, name in categories:
        full_url = urljoin(base_url, video_url)
        add_dir(name, full_url, 2, urljoin(base_url, thumb), fanart)

def play_heavy_r_video(url):
    xbmc.log(f"play_heavy_r_video aufgerufen mit URL: {url}", xbmc.LOGINFO)
    content = make_request(url)

    media_url_match = re.compile('<source type="video/mp4" src="([^"]+)">').findall(content)
    if not media_url_match:
        xbmc.log("Fehler: Keine Medien-URL auf der Seite gefunden.", xbmc.LOGERROR)
        return
    media_url = media_url_match[0]

    headers = {
        "Referer": "https://www.heavy-r.com/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, wie Gecko)"
    }

    video_path = download_video_with_urllib(media_url, headers)
    if video_path:
        server_thread, port = start_local_http_server(video_path, headers)
        if port:
            local_url = f'http://127.0.0.1:{port}/{os.path.basename(video_path)}'
            play_video(local_url)

            monitor = xbmc.Monitor()
            while not xbmc.Player().isPlaying():
                if monitor.waitForAbort(1):
                    break

            while xbmc.Player().isPlaying():
                if monitor.waitForAbort(1):
                    break

            stop_local_http_server()
        else:
            xbmc.log("Fehler: Konnte lokalen HTTP-Server nicht starten.", xbmc.LOGERROR)
    else:
        xbmc.log(f"Fehler: Konnte Video von {media_url} nicht herunterladen.", xbmc.LOGERROR)

def download_video_with_urllib(media_url, headers):
    addon_data_dir = xbmcvfs.translatePath(addon.getAddonInfo('path'))
    folder_path = os.path.join(addon_data_dir, 'temp')

    if not xbmcvfs.exists(folder_path):
        xbmcvfs.mkdirs(folder_path)

    filename_hash = hashlib.md5(media_url.encode('utf-8')).hexdigest()
    video_filename = f"video_{filename_hash}.mp4"
    video_path = os.path.join(folder_path, video_filename)

    if xbmcvfs.exists(video_path):
        xbmc.log(f"Video bereits heruntergeladen: {video_path}", xbmc.LOGINFO)
        return video_path

    request = urllib_request.Request(media_url, headers=headers)

    try:
        with urllib_request.urlopen(request) as response:
            with xbmcvfs.File(video_path, 'wb') as out_file:
                while True:
                    data = response.read(1024 * 1024)  # Lese in 1MB-Blöcken
                    if not data:
                        break
                    out_file.write(data)
        xbmc.log(f"Video heruntergeladen: {video_path}", xbmc.LOGINFO)
        return video_path
    except Exception as e:
        xbmc.log(f"Fehler beim Herunterladen des Videos: {e}", xbmc.LOGERROR)
        return None

def start_local_http_server(file_path, headers):
    import shutil
    global httpd

    class ThreadingHTTPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
        daemon_threads = True
        allow_reuse_address = True

    class RangeRequestHandler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            self.directory = os.path.dirname(file_path)
            self.headers_to_add = headers
            super().__init__(*args, directory=self.directory, **kwargs)

        def end_headers(self):
            for key, value in self.headers_to_add.items():
                self.send_header(key, value)
            super().end_headers()

        def send_head(self):
            path = self.translate_path(self.path)
            if not os.path.exists(path):
                self.send_error(404, "Datei nicht gefunden")
                return None

            file_size = os.path.getsize(path)
            ctype = self.guess_type(path)
            range_header = self.headers.get('Range', None)
            if range_header:
                byte1, byte2 = 0, None
                match = re.search(r'bytes=(\d+)-(\d*)', range_header)
                if match:
                    byte1 = int(match.group(1))
                    if match.group(2):
                        byte2 = int(match.group(2))
                else:
                    self.send_error(400, "Ungültiger Range-Header")
                    return None

                if byte2 is None or byte2 >= file_size:
                    byte2 = file_size - 1
                self.send_response(206)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Range", f"bytes {byte1}-{byte2}/{file_size}")
                self.send_header("Content-Length", str(byte2 - byte1 + 1))
                self.send_header("Accept-Ranges", "bytes")
                self.end_headers()
                return open(path, 'rb'), byte1, byte2
            else:
                self.send_response(200)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(file_size))
                self.send_header("Accept-Ranges", "bytes")
                self.end_headers()
                return open(path, 'rb'), None, None

        def do_HEAD(self):
            result = self.send_head()
            if result:
                f, _, _ = result
                f.close()

        def do_GET(self):
            result = self.send_head()
            if result:
                f, start, end = result
                try:
                    if start is not None and end is not None:
                        f.seek(start)
                        chunk_size = 1024 * 1024  # 1MB
                        bytes_to_send = end - start + 1
                        while bytes_to_send > 0:
                            chunk = f.read(min(chunk_size, bytes_to_send))
                            if not chunk:
                                break
                            self.wfile.write(chunk)
                            bytes_to_send -= len(chunk)
                    else:
                        shutil.copyfileobj(f, self.wfile)
                finally:
                    f.close()

        def log_message(self, format, *args):
            pass

    server_address = ('127.0.0.1', 0) 
    httpd = ThreadingHTTPServer(server_address, RangeRequestHandler)
    port = httpd.server_address[1]

    def run_server():
        try:
            httpd.serve_forever()
        except Exception as e:
            xbmc.log(f"Lokaler HTTP-Server fehlgeschlagen: {e}", xbmc.LOGERROR)

    server_thread = threading.Thread(target=run_server)
    server_thread.start()
    return server_thread, port

def stop_local_http_server():
    global httpd
    if httpd:
        httpd.shutdown()
        httpd = None

def play_video(video_url):
    listitem = xbmcgui.ListItem(path=video_url)
    listitem.setProperty('IsPlayable', 'true')
    xbmcplugin.setResolvedUrl(handle, True, listitem)

if __name__ == '__main__':
    delete_temp_folder()
    params = dict(urllib_parse.parse_qsl(sys.argv[2][1:]))
    url = params.get('url')
    mode = params.get('mode')

    if mode is None:
        process_heavy_r_content('https://www.heavy-r.com/videos/')
    elif mode == '2':
        process_heavy_r_content(url)
    elif mode == '4':
        play_heavy_r_video(url)
    elif mode == '5':
        pass
    else:
        process_heavy_r_content('https://www.heavy-r.com/videos/')
