#!/usr/bin/env python
# -*- coding: utf-8 -*-
import html
import json
import re
import urllib.parse
import requests
import xbmcgui
import xbmcplugin
from resources.lib.base_website import BaseWebsite

class BornToBeFuck(BaseWebsite):
    label = "BornToBeFuck"
    def __init__(self, addon_handle, addon=None):
        super().__init__('borntobefuck', 'https://de.borntobefuck.com/', 'https://de.borntobefuck.com/search/results?search={}', addon_handle, addon)
        self.session=requests.Session(); self.headers={'User-Agent':'Mozilla/5.0','Referer':self.base_url}
    def _get(self,url,ajax=False):
        try:
            h=dict(self.headers)
            if ajax: h.update({'X-Requested-With':'XMLHttpRequest','Accept':'application/json'})
            r=self.session.get(url,headers=h,timeout=20);r.raise_for_status();return r.text
        except Exception as exc: self.logger.warning('BornToBeFuck request failed: %s',exc);return ''
    @staticmethod
    def _clean(v): return re.sub(r'\s+',' ',re.sub(r'<[^>]+>',' ',html.unescape(v or ''))).strip()
    def _cards(self,content):
        out=[];seen=set()
        for b in re.split(r'(?=<div\b[^>]+class=["\'][^"\']*\bvideo\b)',content or '',flags=re.I):
            link=re.search(r'href=["\']([^"\']+/watch/\d+)',b,re.I);img=re.search(r'<img\b(?=[^>]*\bclass=["\'][^"\']*\bthumbnail\b)[^>]*\bsrc=["\']([^"\']+)',b,re.I);title=re.search(r'<h3[^>]*class=["\'][^"\']*video-title[^"\']*["\'][^>]*>(.*?)</h3>',b,re.I|re.S);dur=re.search(r'data-duration=["\'](\d+)',b,re.I)
            if not link or not title: continue
            u=html.unescape(link.group(1))
            if u in seen:continue
            seen.add(u);name=self._clean(title.group(1)); info={'title':name,'plot':name}
            if dur:info['duration']=int(dur.group(1))
            self.add_link(name,u,4,html.unescape(img.group(1)) if img else self.icon,self.fanart,info_labels=info);out.append(u)
        return out
    def process_content(self,url,page=1):
        top=not url or url=='BOOTSTRAP' or url.rstrip('/')==self.base_url.rstrip('/'); url=self.base_url if top else url
        if top:self.add_dir('Search','',5,self.icons.get('search',self.icon));self.add_dir('Categories',self.base_url+'categories',8,self.icons.get('categories',self.icon))
        if page>1:
            sep='&' if '?' in url else '?';raw=self._get(url+sep+'sort=trending&page='+str(page),True)
            try: data=json.loads(raw); content=data.get('html','');more=data.get('hasMorePages',False)
            except Exception: content='';more=False
        else: content=self._get(url);more='id="load-more"' in content
        videos=self._cards(content)
        if videos and more:self.add_dir('Next Page',url,2,self.icon,page=page+1)
        self.end_directory('videos')
    def process_categories(self,url):
        c=self._get(url);seen=set()
        for href,body in re.findall(r'<a\b[^>]+href=["\']([^"\']+/categories/[^"\']+)["\'][^>]*>([\s\S]{0,1200}?)</a>',c,re.I):
            u=html.unescape(href);name=self._clean(body)
            title=re.search(r'(?:title|alt)=["\']([^"\']+)',body,re.I)
            if title:name=self._clean(title.group(1))
            if name and u not in seen:seen.add(u);self.add_dir(name,u,2,self.icons.get('categories',self.icon))
        self.end_directory('videos')
    @staticmethod
    def _stream_from(content):
        content=(content or '').replace('\\/','/')
        m=re.search(r'https?://[^"\'\s<>]+\.m3u8[^"\'\s<>]*',content,re.I)
        if m:return html.unescape(m.group(0))
        # Telegram-gated pages ship no player markup, but the watch page still names the
        # public CDN folder (thumbnail/poster); its index.m3u8 is the same stream.
        m=re.search(r'(https://content\.zavastream\.com/\d+/[0-9a-f-]{36})/',content,re.I)
        return m.group(1)+'/index.m3u8' if m else ''
    def play_video(self,url):
        video_id=re.search(r'/watch/(\d+)',url)
        if not video_id:return self.notify_error('Could not resolve BornToBeFuck stream')
        vid=video_id.group(1)
        stream=self._stream_from(self._get(self.base_url+'videos/'+vid+'/player?lang=de')) or self._stream_from(self._get(self.base_url+'watch/'+vid))
        if not stream:return self.notify_error('Could not resolve BornToBeFuck stream')
        item=xbmcgui.ListItem(path=stream+'|'+urllib.parse.urlencode(self.headers));item.setProperty('IsPlayable','true');item.setMimeType('application/vnd.apple.mpegurl');item.setContentLookup(False);xbmcplugin.setResolvedUrl(self.addon_handle,True,item)
