#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os
import xbmcaddon

# Vendor-Pfad für requests registrieren
try:
    addon_path = xbmcaddon.Addon().getAddonInfo('path')
    vendor_path = os.path.join(addon_path, 'resources', 'lib', 'vendor')
    if vendor_path not in sys.path:
        sys.path.insert(0, vendor_path)
except Exception:
    pass

import json
import base64
import random
import urllib.parse
import xbmcgui
import xbmcplugin
import requests
from resources.lib.base_website import BaseWebsite

class Beeg(BaseWebsite):
    def __init__(self, addon_handle):
        super(Beeg, self).__init__(
            name='beeg',
            base_url='https://beeg.com',
            search_url=None, # Beeg hat keine einfache Such-URL Struktur für direkte Links
            addon_handle=addon_handle
        )
        self.sort_options = ['Newest', 'Popular', 'Top Rated']
        self.sort_ids = {'Newest': '27173', 'Popular': '13', 'Top Rated': '14'}
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
            'Referer': self.base_url
        })

    def get_start_url_and_label(self):
        label = "Beeg"
        setting_id = f"{self.name}_sort_by"
        try:
            sort_idx = int(self.addon.getSetting(setting_id) or 0)
            sort_option = self.sort_options[sort_idx]
        except (ValueError, IndexError, TypeError):
            sort_option = self.sort_options[0]
            self.addon.setSetting(setting_id, "0")

        sort_id = self.sort_ids.get(sort_option, '27173')
        # API URL construction
        url = f'https://store.externulls.com/facts/tag?id={sort_id}&limit=48&offset=0'
        final_label = f"{label} [COLOR yellow]{sort_option}[/COLOR]"
        return url, final_label
        
    def _get_json_content(self, url):
        try:
            self.logger.info(f"Fetching API: {url}")
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.logger.error(f"Failed to fetch API content from {url}: {e}")
            self.notify_error("Could not load content from API.")
            return None

    def process_content(self, url):
        if not url or url == "BOOTSTRAP":
            url, _ = self.get_start_url_and_label()

        # Manuelles Kontextmenü für Ordner
        encoded_url = urllib.parse.quote_plus(url)
        context_menu = [('Sort by...', f'RunPlugin({sys.argv[0]}?mode=7&action=select_sort&website={self.name}&original_url={encoded_url})')]

        self.add_dir('[COLOR cyan]Categories[/COLOR]', 'other', 8, self.icons['categories'], context_menu=context_menu)
        self.add_dir('[COLOR cyan]Channels[/COLOR]', 'productions', 8, self.icons['groups'], context_menu=context_menu)
        self.add_dir('[COLOR cyan]Models[/COLOR]', 'human', 8, self.icons['pornstars'], context_menu=context_menu)

        json_data = self._get_json_content(url)
        if not json_data:
            self.end_directory()
            return

        # JSON ist bei Beeg oft eine Liste von Videos
        if isinstance(json_data, list):
            self.parse_video_list(json_data)
            self.add_next_button(json_data, url)
        
        self.end_directory()

    def parse_video_list(self, json_data):
        for video in json_data:
            try:
                file_data = video.get("file", {})
                if not file_data: continue

                # Metadaten extrahieren
                owner_tag = next((t for t in video.get("tags", []) if t.get("is_owner")), {})
                
                # Titel finden (manchmal verschachtelt)
                video_title = "Untitled"
                data_fields = file_data.get("data", [])
                for d in data_fields:
                    if d.get("cd_column") == "sf_name":
                        video_title = d.get("cd_value")
                        break
                
                studio_name = owner_tag.get("tg_name", "")
                display_title = f'{studio_name} - {video_title}' if studio_name else video_title
                
                # Plot finden
                plot = display_title
                for d in data_fields:
                    if d.get("cd_column") == "sf_story":
                        plot = d.get("cd_value")
                        break
                
                duration_sec = file_data.get("fl_duration", 0)
                
                # Thumbnails
                thumb_url = self.icons['default']
                fc_facts = video.get("fc_facts", [])
                if fc_facts:
                    fc_fact = fc_facts[0]
                    thumbs = fc_fact.get("fc_thumbs", [])
                    if thumbs:
                        thumb_offset = random.choice(thumbs)
                        video_id = file_data.get("id")
                        if video_id:
                            thumb_url = f'https://thumbs.externulls.com/videos/{video_id}/{thumb_offset}.webp?size=480x270'
                
                # Wir packen das ganze Video-Objekt in den Link, um einen weiteren API Call beim Abspielen zu sparen
                # Das ist effizienter als nur die ID zu übergeben
                video_payload = base64.b64encode(json.dumps(video).encode('utf-8')).decode('utf-8')
                
                info_labels = {
                    'title': display_title, 
                    'duration': duration_sec, 
                    'plot': plot, 
                    'studio': studio_name,
                    'mediatype': 'video'
                }
                
                # BaseWebsite fügt "Sort by" automatisch hinzu für Videos
                self.add_link(
                    name=display_title, 
                    url=video_payload, 
                    mode=4, 
                    icon=thumb_url, 
                    fanart=self.fanart, 
                    info_labels=info_labels
                )

            except Exception as e:
                self.logger.error(f"Error processing video item: {e}")
                continue

    def add_next_button(self, json_data, current_url):
        # Beeg API liefert standardmäßig 48 Items. Wenn wir weniger haben, sind wir am Ende.
        if len(json_data) >= 48:
            try:
                parsed_url = urllib.parse.urlparse(current_url)
                query_params = urllib.parse.parse_qs(parsed_url.query)
                
                current_offset = int(query_params.get('offset', ['0'])[0])
                next_offset = current_offset + 48
                
                query_params['offset'] = [str(next_offset)]
                next_page_url = urllib.parse.urlunparse((
                    parsed_url.scheme, 
                    parsed_url.netloc, 
                    parsed_url.path, 
                    parsed_url.params, 
                    urllib.parse.urlencode(query_params, doseq=True), 
                    ''
                ))
                
                self.add_dir('[COLOR blue]Next Page >>[/COLOR]', next_page_url, 2, self.icons['default'])
            except Exception: 
                pass

    def process_categories(self, url):
        # "url" ist hier der key, z.B. 'other', 'productions', 'human'
        category_key = url
        api_url = 'https://store.externulls.com/tag/facts/tags?get_original=true&slug=index'
        
        json_data = self._get_json_content(api_url)
        
        if not json_data or category_key not in json_data:
            self.notify_error(f"Could not load '{category_key}' categories.")
            self.end_directory()
            return

        category_list = json_data[category_key]
        
        # Manuelles Kontextmenü
        context_menu = [('Sort by...', f'RunPlugin({sys.argv[0]}?mode=7&action=select_sort&website={self.name})')]

        for cat in sorted(category_list, key=lambda x: x.get("tg_name", "")):
            name = cat.get("tg_name", "Unknown")
            slug = cat.get("tg_slug", "")
            
            # Thumb resolution
            img = self.icons['default']
            thumbs = cat.get("thumbs")
            if thumbs and isinstance(thumbs, dict):
                thumb_id = thumbs.get('id')
                crops = thumbs.get('crops')
                if thumb_id and crops and len(crops) > 0:
                    crop_id = crops[0].get('id')
                    img = f"https://thumbs.externulls.com/photos/{thumb_id}/to.webp?crop_id={crop_id}&size_new=112x112"

            cat_url = f'https://store.externulls.com/facts/tag?slug={slug}&limit=48&offset=0'
            
            self.add_dir(name, cat_url, 2, img, context_menu=context_menu)
        
        self.end_directory()

    def play_video(self, url_payload):
        try:
            # Payload ist das base64 codierte JSON Objekt von process_content
            video_data_json = base64.b64decode(url_payload).decode('utf-8')
            video_data = json.loads(video_data_json)
            
            hls_resources = video_data.get("file", {}).get("hls_resources", {}) 
            # Fallback falls file leer ist
            if not hls_resources:
                fc_facts = video_data.get("fc_facts", [{}])
                if fc_facts:
                    hls_resources = fc_facts[0].get("hls_resources", {})

            if not hls_resources:
                self.notify_error("No video streams found.")
                return

            # Qualitäten mappen (Schlüssel wie 'fl_cdn_1080')
            streams = {key.replace('fl_cdn_', ''): val for key, val in hls_resources.items()}
            
            # Qualität wählen (Bevorzugt 1080 -> 720 -> 480 -> 360)
            qualities = ['1080', '720', '480', '360']
            stream_key = None
            for q in qualities:
                if q in streams:
                    stream_key = streams[q]
                    self.logger.info(f"Selected quality: {q}p")
                    break
            
            if not stream_key:
                stream_key = streams.get('multi')

            if not stream_key:
                self.notify_error("Could not find a playable stream URL.")
                return

            # URL zusammenbauen
            playback_url = f"https://video.externulls.com/{stream_key}"
            
            # Header für Kodi Player anhängen
            # WICHTIG: Beeg braucht oft keinen speziellen Referer für den Stream selbst, 
            # aber User-Agent schadet nicht.
            headers = f"User-Agent={urllib.parse.quote(self.session.headers['User-Agent'])}"
            final_url = f"{playback_url}|{headers}"
            
            list_item = xbmcgui.ListItem(path=final_url)
            list_item.setMimeType('video/mp4') # Beeg streams sind oft mp4 oder m3u8, mp4 header helps
            xbmcplugin.setResolvedUrl(self.addon_handle, True, list_item)

        except Exception as e:
            self.logger.error(f"Error resolving video for playback: {e}")
            self.notify_error("Failed to play video.")