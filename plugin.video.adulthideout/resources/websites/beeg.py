import sys, os, json, re, urllib.parse
import xbmc, xbmcaddon, xbmcgui, xbmcplugin
from resources.lib.base_website import BaseWebsite

try:
    ADDON = xbmcaddon.Addon()
    ADDON_PATH = ADDON.getAddonInfo('path')
    VENDOR_PATH = os.path.join(ADDON_PATH, 'resources', 'lib', 'vendor')
    if VENDOR_PATH not in sys.path:
        sys.path.insert(0, VENDOR_PATH)
except: pass

try:
    import cloudscraper
    HAS_CLOUDSCRAPER = True
except ImportError:
    HAS_CLOUDSCRAPER = False
    import requests

class BeegWebsite(BaseWebsite):
    def __init__(self, addon_handle):
        super().__init__(name='beeg', base_url='https://beeg.com', search_url='https://beeg.com/search?q={}', addon_handle=addon_handle)
        self.scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True}) if HAS_CLOUDSCRAPER else requests.Session()
        self.scraper.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36', 'Referer': 'https://beeg.com/', 'Origin': 'https://beeg.com'})
        self.sort_options = []

    def make_request(self, url):
        try:
            r = self.scraper.get(url, timeout=20)
            return r.text if r.status_code == 200 else None
        except: return None

    def _fetch_api_json(self, url):
        try:
            headers = self.scraper.headers.copy()
            headers.update({'Accept': 'application/json, text/plain, */*', 'Sec-Fetch-Dest': 'empty', 'Sec-Fetch-Mode': 'cors', 'Sec-Fetch-Site': 'cross-site'})
            r = self.scraper.get(url, headers=headers, timeout=20)
            if r.status_code == 200:
                return r.json()
        except:
            pass
        return None

    def _build_video_url(self, resource):
        if not resource:
            return None

        resource = str(resource).strip()
        if not resource:
            return None

        if resource.startswith('//'):
            vurl = 'https:' + resource
        elif resource.startswith('http://') or resource.startswith('https://'):
            vurl = resource
        elif resource.startswith('/'):
            vurl = 'https://video.externulls.com' + resource
        else:
            vurl = 'https://video.externulls.com/' + resource

        if not urllib.parse.urlsplit(vurl).path.endswith('.m3u8'):
            vurl += '.m3u8'

        return vurl

    def _collect_recent_tags(self, max_pages=5):
        people = {}
        other = {}

        for page_idx in range(max_pages):
            offset = page_idx * 24
            data = self._fetch_api_json(f"https://store.externulls.com/facts/tag?id=27173&limit=24&offset={offset}")
            if not isinstance(data, list):
                continue

            for video in data:
                for tag in video.get('tags', []):
                    slug = tag.get('tg_slug')
                    name = tag.get('tg_name')
                    if not slug or not name:
                        continue

                    icon = self.icons.get('default')
                    if tag.get('thumbs') and tag['thumbs'][0].get('crops'):
                        icon = f"https://thumbs.externulls.com/photos/{tag['thumbs'][0]['id']}/to.webp?crop_id={tag['thumbs'][0]['crops'][0]['id']}&size_new=300x300"

                    bucket = people if tag.get('is_person') else other
                    bucket[slug] = {
                        'name': name,
                        'slug': slug,
                        'icon': icon,
                    }

        return {
            'human': sorted(people.values(), key=lambda item: item['name'].lower()),
            'other': sorted(other.values(), key=lambda item: item['name'].lower()),
        }

    def process_content(self, url):
        final_url = url
        if url == "BOOTSTRAP" or url == self.base_url or url == self.base_url + "/":
            final_url = "https://store.externulls.com/facts/tag?id=27173&limit=24&offset=0"
        elif "/tag/" in url:
            final_url = f"https://store.externulls.com/facts/tag?slug={url.split('/tag/')[-1].strip('/')}&limit=24&offset=0"
        elif url == "TAGS_MENU":
            return self.process_categories('all')
        elif url.startswith("CAT_TYPE:"):
             return self.process_categories(url.split(":")[1])

        if "id=27173" in final_url:
            self.add_dir('[COLOR blue]Search[/COLOR]', '', 5, self.icons.get('search'))
            self.add_dir('[COLOR yellow]Categories[/COLOR]', 'TAGS_MENU', 2, self.icons.get('categories'))

        data = self._fetch_api_json(final_url)
        if data is None:
            return self.notify_error("API Error") or self.end_directory()

        count = 0
        if isinstance(data, list):
            for v in data:
                try:
                    vid = str(v.get('file', {}).get('id', ''))
                    if not vid: continue
                    title = f"Video {vid}"
                    for d in v.get('file', {}).get('data', []):
                        if d.get('cd_column') == 'sf_name': title = d.get('cd_value', title); break
                    
                    thumb = self.icons.get('default')
                    if v.get('fc_facts') and v['fc_facts'][0].get('fc_thumbs'):
                        thumb = f"https://thumbs.externulls.com/videos/{vid}/{v['fc_facts'][0]['fc_thumbs'][0]}.webp?size=1280x720"
                    
                    self.add_link(title, f"{self.base_url}/{vid}", 4, thumb, self.fanart)
                    count += 1
                except: pass

        if count >= 20:
            if "offset" in final_url:
                c = int(re.search(r'offset=(\d+)', final_url).group(1))
                nxt = re.sub(r'offset=\d+', f'offset={c+24}', final_url)
                self.add_dir(f"[COLOR blue]Next Page ({c//24 + 2})[/COLOR]", nxt, 2, self.icons.get('next'))
            else:
                self.add_dir("[COLOR blue]Next Page (2)[/COLOR]", final_url + "&offset=24", 2, self.icons.get('next'))
        self.end_directory()

    def process_categories(self, cat_key):
        collected = self._collect_recent_tags()
        if cat_key == 'all':
            tags = collected.get('other', []) + collected.get('human', [])
        else:
            tags = collected.get(cat_key, [])
        for tag in tags:
            self.add_dir(tag['name'].title(), f"https://store.externulls.com/facts/tag?slug={tag['slug']}&limit=24&offset=0", 2, tag['icon'])
        self.end_directory()

    def search(self, query):
        if not query: return
        query_lower = query.lower()
        collected = self._collect_recent_tags()
        matches = [tag for group in collected.values() for tag in group if query_lower in tag['name'].lower()]

        if len(matches) == 1:
            self.process_content(f"https://store.externulls.com/facts/tag?slug={matches[0]['slug']}&limit=24&offset=0")
            return

        if matches:
            for tag in matches:
                self.add_dir(f"{tag['name'].title()} [Tag]", f"https://store.externulls.com/facts/tag?slug={tag['slug']}&limit=24&offset=0", 2, tag['icon'])
            self.end_directory()
            return

        # Fallback: search recent feed titles when the tag index has no direct match.
        for page_idx in range(5):
            offset = page_idx * 24
            data = self._fetch_api_json(f"https://store.externulls.com/facts/tag?id=27173&limit=24&offset={offset}")
            if not isinstance(data, list):
                continue

            found = False
            for v in data:
                try:
                    vid = str(v.get('file', {}).get('id', ''))
                    if not vid:
                        continue
                    title = f"Video {vid}"
                    for d in v.get('file', {}).get('data', []):
                        if d.get('cd_column') == 'sf_name':
                            title = d.get('cd_value', title)
                            break
                    if query_lower not in title.lower():
                        continue
                    thumb = self.icons.get('default')
                    if v.get('fc_facts') and v['fc_facts'][0].get('fc_thumbs'):
                        thumb = f"https://thumbs.externulls.com/videos/{vid}/{v['fc_facts'][0]['fc_thumbs'][0]}.webp?size=1280x720"
                    self.add_link(title, f"{self.base_url}/{vid}", 4, thumb, self.fanart)
                    found = True
                except:
                    pass

            if found:
                self.end_directory()
                return

        self.notify_error(f"No results for: {query}")

    def play_video(self, url):
        vid = url.split('/')[-1]
        try:
            r = self.scraper.get(f"https://store.externulls.com/facts/file/{vid}", headers={'Accept': 'application/json'}, timeout=20)
            if r.status_code == 200:
                d = r.json()
                hls = d.get('file', {}).get('hls_resources') or d.get('fc_facts', [{}])[0].get('hls_resources')
                vurl = None
                if hls:
                    vurl = self._build_video_url(hls.get('fl_cdn_multi'))
                    if not vurl:
                        for q in ['fl_cdn_1080', 'fl_cdn_720', 'fl_cdn_480', 'fl_cdn_360']:
                            vurl = self._build_video_url(hls.get(q))
                            if vurl:
                                break
                
                if vurl:
                    li = xbmcgui.ListItem(path=vurl)
                    li.setMimeType('application/vnd.apple.mpegurl')
                    li.setProperty('inputstream', 'inputstream.adaptive')
                    li.setProperty('inputstream.adaptive.manifest_type', 'hls')
                    xbmcplugin.setResolvedUrl(self.addon_handle, True, li)
                    return
        except: pass
        self.notify_error("Video not found")
