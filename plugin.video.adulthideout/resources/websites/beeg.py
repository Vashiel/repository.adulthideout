#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import base64
import random
import urllib.parse
import urllib.request
import xbmcgui
import xbmcplugin
from resources.lib.base_website import BaseWebsite

class Beeg(BaseWebsite):
    def __init__(self, addon_handle):
        super(Beeg, self).__init__(
            name='beeg',
            base_url='https://beeg.com',
            search_url=None,
            addon_handle=addon_handle
        )
        self.sort_options = ['Newest', 'Popular', 'Top Rated']
        self.sort_ids = {'Newest': '27173', 'Popular': '13', 'Top Rated': '14'}

    def get_start_url_and_label(self):
        label = "Beeg"
        setting_id = f"{self.name}_sort_by"
        try:
            sort_idx = int(self.addon.getSetting(setting_id))
            sort_option = self.sort_options[sort_idx]
        except (ValueError, IndexError, TypeError):
            sort_option = self.sort_options[0]
            self.addon.setSetting(setting_id, str(self.sort_options.index(sort_option)))

        sort_id = self.sort_ids.get(sort_option, '27173')
        url = f'https://store.externulls.com/facts/tag?id={sort_id}&limit=48&offset=0'
        final_label = f"{label} [COLOR yellow]{sort_option}[/COLOR]"
        return url, final_label
        
    def _get_json_content(self, url):
        try:
            headers = {'Referer': self.base_url}
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as response:
                return json.loads(response.read().decode('utf-8'))
        except Exception as e:
            self.logger.error(f"Failed to fetch API content from {url}: {e}")
            self.notify_error("Could not load content from API.")
            return None

    def process_content(self, url):
        self.add_dir('[COLOR cyan]Categories[/COLOR]', 'other', 8, self.icons['categories'])
        self.add_dir('[COLOR cyan]Channels[/COLOR]', 'productions', 8, self.icons['groups'])
        self.add_dir('[COLOR cyan]Models[/COLOR]', 'human', 8, self.icons['pornstars'])

        json_data = self._get_json_content(url)
        if not json_data:
            self.end_directory(); return

        for video in json_data:
            try:
                owner_tag = next((t for t in video.get("tags", []) if t.get("is_owner")), {})
                video_title = next((d["cd_value"] for d in video.get("file", {}).get("data", []) if d["cd_column"] == "sf_name"), "Untitled")
                display_title = f'{owner_tag.get("tg_name", "")} - {video_title}'
                plot = next((d["cd_value"] for d in video.get("file", {}).get("data", []) if d["cd_column"] == "sf_story"), display_title)
                duration_sec = video.get("file", {}).get("fl_duration", 0)
                fc_fact = video.get("fc_facts", [{}])[0]
                thumb_offset = random.choice(fc_fact.get("fc_thumbs", [0]))
                thumb_url = f'https://thumbs.externulls.com/videos/{video["file"]["id"]}/{thumb_offset}.webp?size=480x270'
                video_payload = base64.b64encode(json.dumps(video).encode('utf-8')).decode('utf-8')
                info_labels = {'title': display_title, 'duration': duration_sec, 'plot': plot, 'studio': owner_tag.get("tg_name")}
                self.add_link(name=display_title, url=video_payload, mode=4, icon=thumb_url, fanart=self.fanart, info_labels=info_labels)
            except Exception as e:
                self.logger.error(f"Error processing video item: {e}")
                continue

        if len(json_data) >= 48:
            try:
                parsed_url = urllib.parse.urlparse(url)
                query_params = urllib.parse.parse_qs(parsed_url.query)
                current_offset = int(query_params.get('offset', ['0'])[0])
                next_offset = current_offset + 48
                query_params['offset'] = [str(next_offset)]
                next_page_url = urllib.parse.urlunparse((parsed_url.scheme, parsed_url.netloc, parsed_url.path, '', urllib.parse.urlencode(query_params, doseq=True), ''))
                self.add_dir('[COLOR yellow]Next Page[/COLOR]', next_page_url, 2)
            except Exception: pass

        self.end_directory()

    def process_categories(self, url):
        category_key = url
        api_url = 'https://store.externulls.com/tag/facts/tags?get_original=true&slug=index'
        json_data = self._get_json_content(api_url)
        
        if not json_data or category_key not in json_data:
            self.notify_error(f"Could not load '{category_key}' categories.")
            self.end_directory(); return

        category_list = json_data[category_key]
        for cat in sorted(category_list, key=lambda x: x["tg_name"]):
            name = cat["tg_name"]
            slug = cat["tg_slug"]
            thumbs = random.choice(cat.get("thumbs")) if cat.get("thumbs") else None
            img = f"https://thumbs.externulls.com/photos/{thumbs['id']}/to.webp?crop_id={thumbs['crops'][0]['id']}&size_new=112x112" if thumbs else self.icons['default']
            cat_url = f'https://store.externulls.com/facts/tag?slug={slug}&limit=48&offset=0'
            self.add_dir(name, cat_url, 2, img)
        
        self.end_directory()

    def play_video(self, url_payload):
        try:
            video_data_json = base64.b64decode(url_payload).decode('utf-8')
            video_data = json.loads(video_data_json)
            
            hls_resources = video_data.get("file", {}).get("hls_resources", {}) or video_data.get("fc_facts", [{}])[0].get("hls_resources", {})

            if not hls_resources:
                self.notify_error("No video streams found."); return

            streams = {key.replace('fl_cdn_', ''): val for key, val in hls_resources.items()}
            qualities = ['1080', '720', '480', '360']
            stream_key = next((streams[q] for q in qualities if q in streams), streams.get('multi'))

            if not stream_key:
                self.notify_error("Could not find a playable stream URL."); return

            playback_url = f"https://video.externulls.com/{stream_key}|Referer={self.base_url}"
            
            list_item = xbmcgui.ListItem(path=playback_url)
            xbmcplugin.setResolvedUrl(self.addon_handle, True, list_item)

        except Exception as e:
            self.logger.error(f"Error resolving video for playback: {e}")
            self.notify_error(f"Failed to play video: {e}")