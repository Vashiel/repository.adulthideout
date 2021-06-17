# -*- coding: utf-8 -*-
'''
Copyright (C) 2017

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program. If not, see <http://www.gnu.org/licenses/>
'''
import six
import urllib, re, os, sys
import settings
from six.moves import urllib_request, urllib_parse, http_cookiejar
from kodi_six import xbmc, xbmcvfs, xbmcaddon, xbmcplugin, xbmcgui

# python 2 and 3 compatibility defs
INFO = xbmc.LOGINFO if six.PY3 else xbmc.LOGNOTICE
TRANSLATEPATH = xbmcvfs.translatePath if six.PY3 else xbmc.translatePath


addon = xbmcaddon.Addon(id='plugin.video.adulthideout')
home = addon.getAddonInfo('path')
if home[-1] == ';':
    home = home[0:-1]
cacheDir = os.path.join(home, 'cache')
cookiePath = os.path.join(home, 'cookies.lwp')
fanart = os.path.join(home, 'resources/fanart.jpg')
icon = os.path.join(home, 'resources/icon.png')
logos = os.path.join(home, 'resources/logos\\')  # subfolder for logos
homemenu = os.path.join(home, 'resources', 'playlists')
urlopen = urllib_request.urlopen
cookiejar = http_cookiejar.LWPCookieJar()
cookie_handler = urllib_request.HTTPCookieProcessor(cookiejar)
urllib_request.build_opener(cookie_handler)


#Ideally, one day this should be moved to a settings page to make it configurable
maxRetryAttempts = 3

#define webpages in order they were added.
redtube = 'https://www.redtube.com'
xvideos = 'https://www.xvideos.com'
xhamster = 'https://xhamster.com'
vikiporn = 'https://www.vikiporn.com'
pornxs = 'http://pornxs.com'
youjizz = 'http://www.youjizz.com'
motherless = 'http://motherless.com'
efukt = 'http://efukt.com/'
hentaigasm = 'http://hentaigasm.com/'
ashemaletube = 'https://www.ashemaletube.com'
heavyr = 'http://www.heavy-r.com'
empflix = 'http://www.empflix.com'
fantasti = 'https://fantasti.cc'
porngo = 'https://www.porngo.com'
uflash = 'http://www.uflash.tv'
javbangers = 'https://www.javbangers.com'
luxuretv = 'http://en.luxuretv.com'
porn300 = 'https://www.porn300.com'
tubedupe = 'https://www.tubedupe.com'

def menulist():
	try:
		mainmenu = open(homemenu, 'r')
		content = mainmenu.read()
		mainmenu.close()
		match = re.compile('#.+,(.+?)\n(.+?)\n').findall(content)
		return match
	except:
		pass

def make_request(url):
	try:
		req = urllib_request.Request(url)
		req.add_header('User-Agent', 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.11 (KHTML, like Gecko) Chrome/23.0.1271.64 Safari/537.11')
		response = urllib_request.urlopen(req, timeout = 60)
		link = response.read().decode('utf-8') if six.PY3 else response.read()
		response.close()
		return link
	#except httplib.IncompleteRead, e:
	#	if attempt < maxRetryAttempts:
	#		xbmc.log("Attempt {0}/{1} to load url {2}".format(attempt + 1, maxAttempts, url))
	#		return make_request_ext(url, attempt + 1)
	except urllib.error.URLError as e:
		print('We failed to open "%s".' % url)
		if hasattr(e, 'code'):
			print('We failed with error code - %s.' % e.code)
		elif hasattr(e, 'reason'):
			print('We failed to reach a server.')
			print('Reason: ', e.reason)

def home():
	add_dir('...[COLOR yellow]  Home  [/COLOR]...', '', None, icon, fanart)

#define main directory and starting page
def main():
	add_dir('A Shemale Tube [COLOR yellow] Videos[/COLOR]', ashemaletube + '/videos/newest/' , 2, logos + 'ashemaletube.png', fanart)
	add_dir('Efukt [COLOR yellow] Videos[/COLOR]', efukt, 2, logos + 'efukt.png', fanart)
	add_dir('Empflix [COLOR yellow] Videos[/COLOR]', empflix + '/new/' , 2, logos + 'empflix.png', fanart)
	add_dir('Fantasti.cc [COLOR yellow] Videos[/COLOR]', fantasti + '/ajax/widgets/widget.php?media=videos&filters=upload_improved&sort=latest&pro=null&filter=0&q=&limit=500&page=1&tpl=user/videos_search_users.tpl&cache=5&pager=true&div=featured_videos&clear=true', 2, logos + 'fantasti.png', fanart)
	add_dir('Hentaigasm [COLOR yellow] Videos[/COLOR]', hentaigasm, 2, logos + 'hentaigasm.png', fanart)
	add_dir('Heavy-R [COLOR yellow] Videos[/COLOR]', heavyr + '/videos/recent/' , 2, logos + 'heavyr.png', fanart)
	add_dir('Javbangers [COLOR yellow] Videos[/COLOR]', javbangers + '/latest-updates/', 2, logos + 'javbangers.png', fanart)
	add_dir('LuxureTV [COLOR yellow] Videos[/COLOR]', luxuretv + '/page1.html', 2, logos + 'luxuretv.png', fanart)
	add_dir('Motherless [COLOR yellow] Videos[/COLOR]', motherless + '/videos/recent?page=1', 2, logos + 'motherless.png', fanart)
	add_dir('Porn300 [COLOR yellow] Videos[/COLOR]', porn300 , 2, logos + 'porn300.png', fanart)	
	add_dir('PornXS [COLOR yellow] Videos[/COLOR]', pornxs + '/?o=t', 39, logos + 'pornxs.png', fanart)
	add_dir('RedTube [COLOR yellow] Videos[/COLOR]', redtube + '/newest', 2, logos + 'redtube.png', fanart)
	add_dir('Tubedupe [COLOR yellow] Videos[/COLOR]', tubedupe + '/latest-updates/', 2, logos + 'tubedupe.png', fanart)
	add_dir('Uflash.TV [COLOR yellow] Videos[/COLOR]', uflash + '/videos?o=mr&type=public', 2, logos + 'uflash.png', fanart)
	add_dir('ViKiPorn [COLOR yellow] Videos[/COLOR]', vikiporn + '/latest-updates/', 2, logos + 'vikiporn.png', fanart)
	add_dir('xHamster [COLOR yellow] Videos[/COLOR]', xhamster + '/new/1.html', 2, logos + 'xhamster.png', fanart)
	add_dir('Xvideos [COLOR yellow] Videos[/COLOR]', xvideos + '/new/1/' , 2, logos + 'xvideos.png', fanart)
	#add_dir('Porngo [COLOR yellow] Videos[/COLOR]', porngo + '/latest-updates/', 2, logos + 'porngo.png', fanart)
	add_dir('YouJizz [COLOR yellow] Videos[/COLOR]', youjizz + '/newest-clips/1.html', 2, logos + 'youjizz.png', fanart)
	setView('videos', 'DEFAULT')

#Search part. Add url + search expression + searchtext
def search():
	try:
		keyb = xbmc.Keyboard('', '[COLOR yellow]Enter search text[/COLOR]')
		keyb.doModal()
		if (keyb.isConfirmed()):
			searchText = urllib_parse.quote_plus(keyb.getText())
		if 'ashemaletube' in name:
			url = ashemaletube + '/search/' + searchText + '/page1.html'
			start(url)
		elif 'efukt' in name:
			url = efukt + '/search/' + searchText + '/'
			start(url)
		elif 'hentaigasm' in name:
			url = hentaigasm + '/?s=' + searchText
			start(url)
		elif 'heavy-r' in name:
			url = heavyr + '/free_porn/' + searchText + '.html'
			start(url)
		elif 'motherless' in name:
			if 'Groups' in name:
				url = motherless + '/search/groups?term=' + searchText + '&member=&sort=date&range=0&size=0'
				motherless_groups_cat(url)
			if 'Galleries' in name:
				url = motherless + '/search/Galleries?term=' + searchText + '&member=&sort=date&range=0&size=0'
				motherless_galeries_cat(url)
			else:
				url = motherless + '/term/videos/' + searchText
				start(url)
		elif 'fantasti' in name:
			url = 'https://fantasti.cc/ajax/widgets/widget.php?media=videos&filters=upload_improved&sort=latest&pro=null&filter=3&q=' + searchText + '&limit=24&page=1&tpl=user/videos_search_users.tpl&cache=5&pager=true&div=featured_videos&clear=true&'
			start(url)
		elif 'pornxs' in name:
			url = 'http://pornxs.com/search.php?s=' + searchText
			start(url)
		elif 'redtube.com' in name:
			url = redtube + '/?search=' + searchText
			start(url)
		elif 'vikiporn.com' in name:
			url = vikiporn + '/search/?q=' + searchText
			start(url)
		elif 'xhamster.com' in name:
			url = 'https://xhamster.com/search.php?q=' + searchText
			start(url)
		elif 'xvideos.com' in name:
			url = xvideos + '/?k=' + searchText
			start(url)
		elif 'youjizz.com' in name:
			url = youjizz + '/search/' + searchText + '-1.html'
			start(url)
		elif 'empflix' in name:
			url = empflix + '/search.php?what=' + searchText
			start(url)
		elif 'porngo' in name:
			url = porngo + '/search/' + searchText + '/'
			start(url)
		elif '.uflash.tv' in name:
			url = uflash + '/search?search_type=videos&search_query=' + searchText
			xbmc.log("Search url uflash: %s" % url, xbmc.LOGERROR)
			start(url)
		elif 'jav.' in name:
			url = 'https://www.javbangers.com/search/' + searchText + '%20latest-updates/'
			start(url)
		elif 'luxuretv' in name:
			url = luxuretv + '/search/videos/' + searchText + '/'
			start(url)
		elif 'tubedupe' in name:
			url = luxuretv + '/search/?q=' + searchText 
			start(url)			
	except:
		pass

def start(url):
	home()
	setView('Videos', 'DEFAULT')
	if 'ashemaletube' in url:
		add_dir('[COLOR lightgreen]ashemaletube.com	 [COLOR red]Search[/COLOR]', ashemaletube, 1, logos + 'ashemaletube.png', fanart)
		add_dir('[COLOR lime]Categories[/COLOR]', 'https://m.ashemaletube.com/tags/', 30, logos + 'ashemaletube.png', fanart)
		add_dir('[COLOR lime]Models[/COLOR]', ashemaletube + '/models/', 55, logos + 'ashemaletube.png', fanart)
		add_dir('[COLOR lime]Sorting[/COLOR]', ashemaletube, 31, logos + 'ashemaletube.png', fanart)
		content = make_request(url)
		if 'model' in url:
			match = re.compile('<span class="thumb-inner-wrapper">.+?<a href="([^"]*)" >.+?<img src="([^"]*)" alt="([^"]*)"', re.DOTALL).findall(content)
			for url, thumb, name in match:
				add_link(name, ashemaletube + url, 4, thumb, fanart)
		else:
			match = re.compile('<div class="thumb vidItem" data-video-id=".+?">.+?<a href="([^"]*)" >.+?src="([^"]*)" alt="([^"]*)"(.+?)<span>.+?([:\d]+).+?</span>', re.DOTALL).findall(content)
			for url, thumb, name, dummy, duration in match:
				name = name.replace('&amp;', '&')
				if 'HD' in dummy:
					add_link(name + '[COLOR yellow]' +' [HD]' +'[/COLOR]' +' [COLOR lime]('+ duration + ')[/COLOR]', ashemaletube + url, 4, thumb, fanart)
				else:
					add_link(name + ' [COLOR lime]('+ duration + ')[/COLOR]', ashemaletube + url, 4, thumb, fanart)
		try:
			match = re.compile('<a class="rightKey" href="(.+?)">Next</a>').findall(content)
			add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', ashemaletube + match[0], 2, logos + 'ashemaletube.png', fanart)
		except:
			match = re.compile('<a class="pageitem rightKey" href="(.+?)" title="Next">Next</a>').findall(content)
			add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', ashemaletube + match[0], 2, logos + 'ashemaletube.png', fanart)

	elif 'efukt' in url:
		content = make_request(url)
		add_dir('[COLOR lightgreen]efukt.com	 [COLOR red]Search[/COLOR]', efukt, 1, logos + 'efukt.png', fanart)
		match = re.compile('<a  href="([^"]*)" title="([^"]*)" class="thumb"><img src="([^"]*)"').findall(content)
		for url, name, thumb in match:
			name = name.replace('&amp;', '&').replace('&quot;', '"').replace('&#039;', '\'')
			add_link(name, url , 4, thumb, fanart)
		try:
			match = re.compile('class="anchored_item active ">.+?</a><a href="(.+?)"').findall(content)
			add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', efukt + match[0], 2, logos + 'efukt.png', fanart)
		except:
			pass

	elif 'empflix' in url:
		content = make_request(url)
		add_dir('[COLOR lightgreen]empflix.com	 [COLOR red]Search[/COLOR]', empflix, 1, logos + 'empflix.png', fanart)
		add_dir('[COLOR lime]Categories[/COLOR]', empflix + '/categories.php',  45, logos + 'empflix.png', fanart)
		add_dir('[COLOR lime]Sorting[/COLOR]', empflix + '/browse.php?category=mr',  46, logos + 'empflix.png', fanart)
		match = re.compile("<a class='thumb no_ajax' href='(.+?)' data-width='0'>.+?<img class='lazy' src='/images/loader.jpg' data-original='(.+?)' alt=\"(.+?)\"><div class='videoDuration'>(.+?)</div>", re.DOTALL).findall(content)
		for url, thumb, name, duration in match:
			add_link(name + ' [COLOR lime]('+ duration + ')[/COLOR]', 'https://m.empflix.com/' + url , 4, thumb, fanart)
		try:
			match = re.compile('<a class="llNav" href="([^"]+)">').findall(content)
			add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', empflix + match[0], 2, logos + 'empflix.png', fanart)
		except:
			pass

	elif 'fantasti' in url:
		content = make_request(url)
		add_dir('[COLOR lightgreen]fantasti.cc	 [COLOR red]Search[/COLOR]', fantasti, 1, logos + 'fantasti.png', fanart)
		add_dir('[COLOR lime]Collection[/COLOR]', fantasti + '/videos/collections/popular/31days/', 48, logos + 'fantasti.png', fanart)
		add_dir('[COLOR lime]Category [/COLOR]', fantasti + '/category/',  18, logos + 'fantasti.png', fanart)
		add_dir('[COLOR lime]Sorting [/COLOR]', fantasti + '/videos/popular/today/',  49, logos + 'fantasti.png', fanart)
		add_dir('[COLOR lime]Change Content[/COLOR]', fantasti, 50, logos + 'fantasti.png', fanart)
		try:
			match = re.compile('<a class=".+?" href="([^"]*)".+?src="([^"]*)".+?alt="A video by .+?: (.+?)uploaded.+?"', re.DOTALL).findall(content)
			for url, thumb, name in match:
				name = name.replace('&amp;', '&').replace('&quot;', '"').replace('&#39;', '\'').replace('  ', '')
				add_link(name, fantasti + url, 4, thumb, fanart)
		except:
			pass

	elif 'hentaigasm' in url:
		add_dir('[COLOR lime]hentaigasm	 [COLOR red]Search[/COLOR]', hentaigasm, 1, logos + 'hentaigasm.png', fanart)
		add_dir('[COLOR lime]Categories[/COLOR]', hentaigasm, 29, logos + 'hentaigasm.png', fanart)
		content = make_request(url)
		match = re.compile('title="(.+?)" href="(.+?)">\s*\s*.+?\s*\s*.+?<img src="(.+?)"').findall(content)
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

	elif 'heavy-r' in url:
		add_dir('[COLOR lightgreen]heavy-r	   [COLOR red]Search[/COLOR]', heavyr, 1, logos + 'heavyr.png', fanart)
		add_dir('[COLOR lime]Categories[/COLOR]', heavyr + '/categories/', 33, logos + 'heavyr.png', fanart)
		content = make_request(url)
		match = re.compile('<a href="([^"]+)" class="image">.+?src="([^"]+)".+?alt="([^"]+)".+?<span class="duration"><i class="fa fa-clock-o"></i> ([\d:]+)</span>', re.DOTALL).findall(content)
		for url, thumb, name, duration in match:
			add_link(name + ' [COLOR lime]('+ duration + ')[/COLOR]', heavyr + url, 4, thumb, fanart)
		try:
			match = re.compile('<li><a class="nopopoff" href="([^"]+)">Next</a></li>').findall(content)
			add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', heavyr + match[0], 2, logos + 'heavyr.png', fanart)
		except:
			pass

	elif 'javbangers' in url:
		add_dir('[COLOR lightgreen]jav.	   [COLOR red]Search[/COLOR]', javbangers, 1, logos + 'javbangers.png', fanart)
		add_dir('[COLOR lime]Categories[/COLOR]', javbangers + '/categories/', 64, logos + 'javbangers.png', fanart)
		content = make_request(url)
		if "search" in url :
			match = re.compile('<div class="video-item   ">.+?<a href="(.+?)".+?data-original="(.+?)" alt="(.+?)".+?<i class="fa fa-clock-o"></i> ([\d:]+)</div>', re.DOTALL).findall(content)
			for url, thumb, name, duration in match:
				add_link(name + ' [COLOR lime]('+ duration + ')[/COLOR]', url, 4, thumb, fanart)
		else:
			match = re.compile('<div class="video-item   ">.+?<a href="(.+?)" title="(.+?)".+?data-original="(.+?)".+?<i class="fa fa-clock-o"></i> ([\d:]+)</div>', re.DOTALL).findall(content)
			for url, name, thumb, duration in match:
				add_link(name + ' [COLOR lime]('+ duration + ')[/COLOR]', url, 4, thumb, fanart)
		try:
			match = re.compile('<h1>			Videos for: (.+?)		</h1>.+?data-action="ajax" data-container-id="list_videos_videos_list_search_result_pagination" data-block-id="list_videos_videos_list_search_result" data-parameters=".+?">([^"]+)</a></li>', re.DOTALL).findall(content)
			for url, name in match:
				url = url.replace(', Page .+?','')	
				add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', 'https://www.javbangers.com/search/' + url + '/?mode=async&function=get_block&block_id=list_videos_videos_list_search_result&category_ids=&sort_by=&from_videos=' + name, 2, logos + 'javbangers.png', fanart)
			match = re.compile('<li class="next"><a href="([^"]*)" data-action="ajax"').findall(content)
			add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', javbangers + match[0].replace('&amp;','&'), 2, logos + 'javbangers.png', fanart)
		except:
			match = re.compile('<li class="next"><a href="([^"]*)" data-action="ajax"').findall(content)
			add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', javbangers + match[0].replace('&amp;','&'), 2, logos + 'javbangers.png', fanart)

	elif 'luxuretv' in url:
		content = make_request(url)
		add_dir('[COLOR lightgreen]luxuretv.com	 [COLOR red]Search[/COLOR]', luxuretv, 1, logos + 'luxuretv.png', fanart)
		add_dir('[COLOR lime]Categories[/COLOR]', luxuretv + '/channels/', 68, logos + 'luxuretv.png', fanart)
		match = re.compile('<a href="([^"]*)" title="([^"]*)"><img class="img" src="(.+?)".+?<div class="time"><b>([\d:]+)</b></div>', re.DOTALL).findall(content)
		for url, name, thumb, duration in match:
			add_link(name + '[COLOR lime] (' + duration + ')[/COLOR]', url, 4, thumb, fanart)
		try:
			match = re.compile('a href=\'([^"]*)\'>Next').findall(content)
			add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', luxuretv + '/' +  match[0], 2, logos + 'luxuretv.png', fanart)
		except:
			pass

	elif 'motherless' in url:
		content = make_request(url)
		###Search in def search(): and media_list(url)
		add_dir('[COLOR lightgreen]motherless.com	 [COLOR red]Search[/COLOR]', motherless, 1, logos + 'motherless.png', fanart)
		####Subfolders
		add_dir('[COLOR lime]Being watched now[/COLOR]', motherless +  '/live/videos',  61, logos + 'motherless.png', fanart)
		add_dir('[COLOR lime]Sorting[/COLOR]', motherless +  '/videos/',  44, logos + 'motherless.png', fanart)
		add_dir('[COLOR magenta]Galleries[/COLOR]', motherless + '/galleries/updated?page=1', 60, logos + 'motherless.png', fanart)
		add_dir('[COLOR magenta]Groups[/COLOR]', motherless + '/groups?s=u', 62, logos + 'motherless.png', fanart)
		###sending video URL to resolve_url(url)
		match = re.compile('data-frames="12">.+?<a href="([^"]+)".+?<span class="size">([:\d]+)</span>.+?<img class="static" src="([^"]+)".+?alt="([^"]+)"/>', re.DOTALL).findall(content)
		for url, duration, thumb, name in match:
			name = name.replace('Shared by ', '').replace('&quot;', '"').replace('&#39;', '\'')
			if 'motherless' in url:
				add_link(name + ' [COLOR lime]('+ duration + ')[/COLOR]', url, 4, thumb, fanart)
			else:
				add_link(name + ' [COLOR lime]('+ duration + ')[/COLOR]', motherless + url, 4, thumb, fanart)
		###Next Button
		try :
			match = re.compile('<link rel="next" href="([^"]+)"/>').findall(content)
			add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', match[0], 2, logos + 'motherless.png', fanart)
		except:
			pass

	elif 'porn300' in url:
		content = make_request(url)
		add_dir('[COLOR lightgreen]porn300.com	 [COLOR red]Search[/COLOR]', pornxs, 1, logos + 'porn300.png', fanart)
		match = re.compile('a href="([^"]*)" data-video-id="?".+?data-src="([^"]*)" alt="([^"]*)".+?<span class="duration-video">.+?([:\d]+).+?</span>', re.DOTALL).findall(content)
		for url, thumb, name, duration in match:
			add_link(name + ' [COLOR lime]('+ duration + ')[/COLOR]', porn300 + url, 4, thumb, fanart)
		try:
			match = re.compile('<link rel="next" href="([^"]*)" />').findall(content)
			add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', match[0], 2, logos + 'porn300.png', fanart)
		except:
			pass
	elif 'pornxs' in url:
		content = make_request(url)
		add_dir('[COLOR lightgreen]pornxs.com	 [COLOR red]Search[/COLOR]', pornxs, 1, logos + 'pornxs.png', fanart)
		match = re.compile('<a href="([^"]+)".+?title="([^"]+)".+?data-loader-src="([^"]+)">.+?<div class="squares__item_numbers js-video-time">.+?([:\d]+).+?</div>', re.DOTALL).findall(content)
		for url, name, thumb, duration in match:
			add_link(name + ' [COLOR lime]('+ duration + ')[/COLOR]', pornxs + url, 4, thumb, fanart)
		try:
			match = re.compile('<a class="pagination-next" href="([^"]*)"><span></span></a></li> ').findall(content)
			add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', pornxs + match[0], 2, logos + 'pornxs.png', fanart)
		except:
			pass

	elif 'redtube' in url:
		content = make_request(url)
		add_dir('[COLOR lightgreen]redtube.com	 [COLOR red]Search[/COLOR]', redtube, 1, logos + 'redtube.png', fanart)
		add_dir('[COLOR lime]Sorting[/COLOR]', redtube , 8, logos + 'redtube.png', fanart)
		add_dir('[COLOR lime]Categories[/COLOR]', redtube + '/categories', 9, logos + 'redtube.png', fanart)
		try:
			if '/redtube/' in url:
				match = re.compile('<a class="video_link js_mpop js-pop " href="([^"]+)".+?data-src="([^"]+)".+?alt="([^"]+)"', re.DOTALL).findall(content)
				for url, thumb, name in match:
					add_link(name, redtube + url, 4, thumb, fanart)
			else:
				match = re.compile('<a class="video_link.+?" href="([^"]+)".+?alt="([^"]+)".+?data-src="([^"]+)"', re.DOTALL).findall(content)
				for url, name, thumb in match:
					add_link(name, redtube + url, 4, thumb, fanart)
		except:
			pass
		try:
			match = re.compile('<link rel="next" href="([^"]+)" />').findall(content)
			add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', match[0], 2, logos + 'redtube.png', fanart)
		except:
			pass
	
	elif 'tubedupe' in url:
		content = make_request(url)
		add_dir('[COLOR lightgreen]Tubedupe.com	 [COLOR red]Search[/COLOR]', tubedupe, 1, logos + 'tubedupe.png', fanart)
		add_dir('[COLOR lime]Categories[/COLOR]', tubedupe + '/categories/?sort_by=avg_videos_popularity', 15, logos + 'tubedupe.png', fanart)
		add_dir('[COLOR lime]Rankings[/COLOR]', tubedupe , 19, logos + 'tubedupe.png', fanart)
		add_dir('[COLOR lime]Change Content[/COLOR]', tubedupe , 20, logos + 'tubedupe.png', fanart)			
		match = re.compile('<a href="([^"]+)" class="kt_imgrc" title="([^"]+)">.+?<img src="([^"]+)".+?<var class="duree">([:\d]+)</var>', re.DOTALL).findall(content)
		for url, name, thumb, duration in match:
			add_link(name + ' [COLOR lime]('+ duration + ')[/COLOR]', tubedupe + url, 4, thumb, fanart)
		try:
			match = re.compile('<link href="([^"]*)" rel="next"/>').findall(content)
			add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', match[0], 2, logos + 'tubedupe.png', fanart)
		except:
			pass
			
	elif '.uflash.tv' in url:
		xbmc.log("saga: Making request to %s" % url, xbmc.LOGERROR)
		content = make_request(url)
		current_url = url
		add_dir('[COLOR lightgreen].uflash.tv   [COLOR red]Search[/COLOR]', uflash, 1, logos + 'uflash.png', fanart)
		add_dir('[COLOR lime]Categories[/COLOR]', uflash + '/videos?o=mr', 54, logos + 'uflash.png', fanart)
		add_dir('[COLOR magenta]Female Exhibitionist Videos[/COLOR]', uflash + '/videos?g=female&type=public&o=mr',  2, logos + 'uflash.png', fanart)
		add_dir('[COLOR magenta]Male Exhibitionist Videos[/COLOR]', uflash + '/videos?type=public&o=mr&g=male',  2, logos + 'uflash.png', fanart)
		add_dir('[COLOR magenta]Recently Viewed - Exhibitionist Videos[/COLOR]', uflash + '/videos?o=mr&type=public',  2, logos + 'uflash.png', fanart)
		match = re.compile('<a href="/video/(.+?)/.+?<img src="(.+?)" alt="(.+?)".+?<span class="duration">.+?([:\d]+).+?</span>', re.DOTALL).findall(content)
		for url, thumb, name, duration in match:
			name = name.replace('&amp;', '&').replace('&quot;', '"').replace('&#039;', '\'')
			add_link(name + ' [COLOR lime]('+ duration + ')[/COLOR]', 'http://www.uflash.tv/media/player/config.v89x.php?vkey=' + url,  4, 'http://www.uflash.tv/' + thumb, fanart)
		try:
			next_page = uflash_nextpage(current_url, content)
			raise Exception(next_page)
		except Exception as e:
			xbmc.log(str(e), xbmc.LOGERROR)
			pass
	elif 'vikiporn' in url:
		content = make_request(url)
		add_dir('[COLOR lightgreen]vikiporn.com	 [COLOR red]Search[/COLOR]', vikiporn, 1, logos + 'vikiporn.png', fanart)
		add_dir('[COLOR lime]Categories[/COLOR]', vikiporn + '/categories/', 16, logos + 'vikiporn.png', fanart)
		match = re.compile('ImageObject\">.+?<a href="([^"]*)".+?<img src="([^"]*)" alt="([^"]*)">', re.DOTALL).findall(content)
		for url, thumb, name in match:
			add_link(name, url,  4, thumb, fanart)
		try:
			match = re.compile('<a href="(.+?)">Next</a>').findall(content)
			add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', vikiporn + match[0], 2, logos + 'vikiporn.png', fanart)
		except:
			pass
			
	elif 'xhamster' in url:
		content = make_request(url)
		add_dir('[COLOR lightgreen]xhamster.com	 [COLOR red]Search[/COLOR]', xhamster, 1, logos + 'xhamster.png', fanart)
		add_dir('[COLOR lime]Categories[/COLOR]', xhamster + '/categories', 17, logos + 'xhamster.png', fanart)
		add_dir('[COLOR lime]Rankings[/COLOR]', xhamster + '/rankings/weekly-top-viewed.html' , 42, logos + 'xhamster.png', fanart)
		add_dir('[COLOR lime]Change Content[/COLOR]', xhamster , 24, logos + 'xhamster.png', fanart)
		match = re.compile('href="https://xhamster.com/videos/([^"]*)" data-sprite=".+?"(.+?)src="(.+?)".+?alt="(.+?)">.+?<span data-role-video-duration>(.+?)</span>', re.DOTALL).findall(content)
		for url, dummy, thumb, name, duration in match:
			name = name.replace('&amp;', '&').replace('&quot;', '"').replace('&#39;', '\'')
			if '?from=video_promo' in url:
				pass
			if 'icon--hd' in dummy:
				add_link(name + '[COLOR yellow]' +' [HD]' +'[/COLOR]' +' [COLOR lime]('+ duration + ')[/COLOR]', 'http://xhamster.com/videos/' + url, 4, thumb, fanart)
			else:
				add_link(name + ' [COLOR lime]('+ duration +')[/COLOR]', 'http://xhamster.com/videos/' + url, 4, thumb, fanart)
		match = re.compile('<div id="cType"><div class="([^"]*)"></div>').findall(content)
		if "iconL iconTrans" in match :
			match = re.compile('<link rel="next" href="([^"]*)"><link rel="dns-prefetch"').findall(content)
			add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', match[0] + '?content=shemale', 2, logos + 'xhamster.png', fanart)
		if "iconL iconGays" in match :
			match = re.compile('<link rel="next" href="([^"]*)"><link rel="dns-prefetch"').findall(content)
			add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', match[0] + '?content=gay', 2, logos + 'xhamster.png', fanart)
		if "iconL iconStraight" in match :
			match = re.compile('<link rel="next" href="([^"]*)"><link rel="dns-prefetch"').findall(content)
			add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', match[0] + '?content=straight', 2, logos + 'xhamster.png', fanart)
		try:
			match = re.compile('data-page="next" href="([^"]*)">').findall(content)
			add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', match[0] , 2, logos + 'xhamster.png', fanart)
		except:
			pass

	elif 'xvideos' in url:
		content = make_request(url)
		add_dir('[COLOR lightgreen]xvideos.com	 [COLOR red]Search[/COLOR]', xvideos, 1, logos + 'xvideos.png', fanart)
		add_dir('[COLOR lime]Categories[/COLOR]', xvideos,  27, logos + 'xvideos.png', fanart)
		add_dir('[COLOR lime]Pornstars[/COLOR]', xvideos + '/pornstars-index/3months',  32, logos + 'xvideos.png', fanart)
		add_dir('[COLOR lime]Rankings[/COLOR]', xvideos + '/best' , 71, logos + 'xvideos.png', fanart)
		if 'channels' in url:
			match = re.compile('<p class="title"><a href="/([^"]*)" title="([^"]*)">', re.DOTALL).findall(content)
			for url, name in match:
				add_link(name, xvideos + url, 4, logos + 'xvideos.png', fanart)
		else:
			match = re.compile('<img src=".+?" data-src="([^"]*)"(.+?)<p class="title"><a href="([^"]*)" title="([^"]*)".+?<span class="duration">([^"]*)</span>', re.DOTALL).findall(content)
			for thumb, dummy, url, name, duration in match:
				name = name.replace('&amp;', '&').replace('&quot;', '"').replace('&#39;', '`')
				url = url.replace('THUMBNUM/','')
				if '>1080p<' in dummy:
					add_link(name + '[COLOR yellow]' +' [1080p]' +'[/COLOR]' +' [COLOR lime]('+ duration + ')[/COLOR]', xvideos + url, 4, thumb, fanart)
				elif '>HD<' in dummy:
					add_link(name + '[COLOR yellow]' +' [720p]' +'[/COLOR]' +' [COLOR lime]('+ duration + ')[/COLOR]', xvideos + url, 4, thumb, fanart)
				else:
					add_link(name + ' [COLOR lime]('+ duration + ')[/COLOR]', xvideos + url, 4, thumb, fanart)
		try:
			match = re.compile('<a href="([^"]+)" class="no-page next-page">Next</a>').findall(content)
			match = [item.replace('&amp;', '&') for item in match]
			add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', xvideos + match[0], 2, logos + 'xvideos.png', fanart)
		except:
			pass

	elif 'youjizz' in url:
		content = make_request(url)
		add_dir('[COLOR lightgreen]youjizz.com  [COLOR red]Search[/COLOR]', youjizz, 1, logos + 'youjizz.png', fanart)
		add_dir('[COLOR lime]Categories[/COLOR]', youjizz + '/newest-clips/1.html' , 28, logos + 'youjizz.png', fanart)
		match = re.compile('data-original="([^"]+)" alt=""(.+?).+?<div class="video-title">.+?<a href=\'([^\']+)\'>(.+?)</a>.+?<span class="time">([:\d]+)</span>', re.DOTALL).findall(content)
		for thumb, dummy, url, name, duration in match:
			if 'hd' in dummy:
				add_link(name + '[COLOR yellow]' +' [HD]' +'[/COLOR]'+ ' [COLOR lime]('+ duration + ')[/COLOR]', 'https://www.youjizz.com' + url, 4, 'https:' + thumb, fanart)
			else:
				add_link(name + ' [COLOR lime]('+ duration + ')[/COLOR]', 'https://www.youjizz.com' + url, 4, 'https:' + thumb, fanart)
		try:
			match = re.compile('<a class="pagination-next" href="([^"]+)">Next &raquo;</a></li>', re.DOTALL).findall(content)
			add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', youjizz + match[0], 2, logos + 'youjizz.png', fanart)
		except:
			pass

	elif 'porngo' in url:
		content = make_request(url)
		add_dir('[COLOR lightgreen]porngo	[COLOR red]Search[/COLOR]', porngo, 1, logos + 'porngo.png', fanart)
		add_dir('[COLOR lime]Categories[/COLOR]', porngo + '/categories/', 52, logos + 'porngo.png', fanart)
		match = re.compile('<a href="([^"]*)" class="thumb__top ">.+?<div class="thumb__img" data-preview=".+?">.+?<img src="([^"]*)" alt="([^"]*)".+?<span class="thumb__duration">([:\d]+)</span>', re.DOTALL).findall(content)
		for url, thumb, name, duration in match:
			add_link(name + ' [COLOR lime]('+ duration + ')[/COLOR]', url,  4, thumb, fanart)
		try:
			match = re.compile('href="([^"]+)">Next</a></div>').findall(content)
			add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', porngo + match[0], 2, logos + 'porngo.png', fanart)
		except:
			pass

def motherless_galeries_cat(url):
	home()
	setView('Videos', 'DEFAULT')
	add_dir('[COLOR lightgreen]motherless.com Galleries	[COLOR red]Search[/COLOR]', motherless + '/search/Galleries', 1, logos + 'motherless.png', fanart)
	content = make_request(url)
	match = re.compile('href="/G(.+?)".+?<img class="static" src="(.+?)".+?alt="(.+?)"', re.DOTALL).findall(content)
	for url, thumb, name in match:
		name = name.replace('&amp;', '&').replace('&quot;', '"').replace('&#39;', '\'')
		url = '/GV' + url
		add_dir(name, motherless + url, 2, thumb, fanart)
	match = re.compile('<link rel="next" href="([^"]*)"/>').findall(content)
	add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', match[0], 60, logos + 'motherless.png', fanart)

def motherless_groups_cat(url):
	home()
	setView('Videos', 'DEFAULT')
	add_dir('[COLOR lightgreen]motherless.com Groups	[COLOR red]Search[/COLOR]', motherless + '/search/groups?term=', 1, logos + 'motherless.png', fanart)
	content = make_request(url)
	match = re.compile('<a href="/g/(.+?)">.+?src="(.+?)".+?Groups: </span>.+?(.+?)</a>', re.DOTALL).findall(content)
	for url, thumb, name in match:
		name = name.replace('&amp;', '&').replace('&quot;', '"').replace('&#39;', '\'').replace('  ', '')
		add_dir(name, motherless + '/gv/' + url, 2, thumb, fanart)
	match = re.compile('<a href="(.+?)" class="pop" rel="next">NEXT<i class="fas icon fa-angle-double-right"></i></a></div>').findall(content)
	add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', motherless + match[0], 62, logos + 'motherless.png', fanart)

def motherless_being_watched_now(url):
	home()
	setView('Videos', 'DEFAULT')
	content = make_request(url)
	add_dir('[COLOR lime]REFRESH[COLOR orange]  Page[COLOR red]  >>>>[/COLOR]', 'https://motherless.com/live/videos' , 61, logos + 'motherless.png', fanart)
	match = re.compile('<span class="size">([:\d]+)</span>.+?<img class="static" src="([^"]+)".+?<a href="([^"]+)" title="([^"]+)"', re.DOTALL).findall(content)
	for duration, thumb, url, name in match:
		name = name.replace('&amp;', '&').replace('&quot;', '"').replace('&#39;', '\'')
		add_link(name + ' [COLOR lime]('+ duration + ')[/COLOR]', url , 4, thumb, fanart)

def redtube_sorting(url):
	home()
	setView('Movies', 'DEFAULT')
	content = make_request(url)
	add_dir('[COLOR lime]Newest[/COLOR]', redtube + '/newest', 2, logos + 'redtube.png', fanart)
	add_dir('[COLOR lime]Top[/COLOR]', redtube + '/top', 2, logos + 'redtube.png', fanart)
	add_dir('[COLOR lime]Mostviewed[/COLOR]', redtube + '/mostviewed', 2, logos + 'redtube.png', fanart)
	add_dir('[COLOR lime]Mostfavored[/COLOR]', redtube + '/mostfavored', 2, logos + 'redtube.png', fanart)
	add_dir('[COLOR lime]Longest[/COLOR]', redtube + '/longest', 2, logos + 'redtube.png', fanart)

def redtube_categories(url):
	home()
	setView('Movies', 'DEFAULT')
	content = make_request(url)
	match = re.compile('<div class="category_item_wrapper tm_cat_wrapper">.+?<a href="(.+?)" class="category_thumb_link js_mpop js-pop"  >.+?.+?data-src="(.+?)".+?alt="(.+?)"', re.DOTALL).findall(content)
	for url, thumb, name in match:
		add_dir(name, 'https://www.redtube.com' + url, 2, thumb, fanart)

def vikiporn_categories(url):
	home()
	setView('Movies', 'DEFAULT')
	content = make_request(url)
	match = re.compile('<a href="([^"]+)" title="([^"]+)">.+?<img src="([^"]+)"', re.DOTALL).findall(content)
	for url, name, thumb in match:
		add_dir(name, url,  2, thumb, fanart)

def xhamster_categories(url):
	home()
	setView('Movies', 'DEFAULT')
	content = make_request(url)
	match = re.compile('a href=".+?/categories/([^"]*)"').findall(content)
	for url in match:
		name = url
		name = name.replace('&amp;', '&').replace('&quot;', '"').replace('&#39;', '´').replace('new-', '').replace('-1.html', '').replace('_', '')
		name = name.capitalize()
		add_dir(name, xhamster + '/categories/' + url, 2, logos + 'xhamster.png', fanart)

def xhamster_content(url) :
	home()
	setView('Movies', 'DEFAULT')
	content = make_request(url)
	add_dir('[COLOR lime]Transgender[/COLOR]', xhamster + '/shemale', 2, logos + 'xhamster.png', fanart)
	add_dir('[COLOR lime]Gay[/COLOR]', xhamster + '/gay', 2, logos + 'xhamster.png', fanart)
	add_dir('[COLOR lime]Hetero[/COLOR]', xhamster, 2, logos + 'xhamster.png', fanart)

def xhamster_rankigs(url) :
	home()
	setView('Movies', 'DEFAULT')
	content = make_request(url)
	add_dir('[COLOR lime]Best[/COLOR]', xhamster + '/best/weekly', 2, logos + 'xhamster.png', fanart)
	add_dir('[COLOR lime]Most viewed[/COLOR]', xhamster + '/most-viewed/weekly', 2, logos + 'xhamster.png', fanart)
	add_dir('[COLOR lime]Most commented[/COLOR]', xhamster + '/most-commented/weekly', 2, logos + 'xhamster.png', fanart)
	add_dir('[COLOR lime]Latest[/COLOR]', xhamster + '/videos/latest', 2, logos + 'xhamster.png', fanart)
	add_dir('[COLOR lime]Recommended[/COLOR]', xhamster + '/videos/recommended', 2, logos + 'xhamster.png', fanart)
	
def youjizz_categories(url) :
	home()
	setView('Movies', 'DEFAULT')
	content = make_request(url)
	match = re.compile('<li><a href="/categories/([^"]+)">([^"]+)</a></li>').findall(content)
	for url,name in match:
		url = url.replace('High Definition', 'HighDefinition');
		add_dir(name, youjizz + '/categories/' + url, 2, logos + 'youjizz.png', fanart)

def hentaigasm_categories(url) :
	home()
	setView('Movies', 'DEFAULT')
	content = make_request(url)
	match = re.compile("<a href='http://hentaigasm.com/genre/([^']+)'").findall(content)
	for url in match:
		name = url.replace('http://hentaigasm.com/genre/', '').replace ('/', '')
		add_dir(name, 'http://hentaigasm.com/genre/' + url, 2, logos + 'hentaigasm.png', fanart)

def ashemaletube_categories(url) :
	home()
	setView('Videos', 'DEFAULT')
	content = make_request(url)
	match = re.compile('href="([^"]+)" class="btn btn-colored">([^"]+)</a>', re.DOTALL).findall(content)
	for url, name in match:
		add_dir(name, 'https://ashemaletube.com' + url, 2, logos + 'ashemaletube.png', fanart)

def ashemaletube_pornstars(url) :
	home()
	setView('movies', 'DEFAULT')
	content = make_request(url)
	match = re.compile('<li class="modelspot modelItem" data-model-id=".+?">.+?<a href="(.+?)".+?alt="(.+?)" src="(.+?)"', re.DOTALL).findall(content)
	for url, name, thumb in match:
		add_dir(name, ashemaletube + url, 2, thumb, fanart)
	try:
		match = re.compile('<link rel="next" href="(.+?)" />').findall(content)
		add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', ashemaletube + match[0], 55, logos + 'ashemaletube.png', fanart)
	except:
		pass

def ashemaletube_sorting(url) :
	home()
	setView('Movies', 'DEFAULT')
	content = make_request(url)
	add_dir('[COLOR lime]Date Added[/COLOR]', ashemaletube + '/videos/newest/?s=', 2, logos + 'ashemaletube.png', fanart)
	add_dir('[COLOR lime]Most Popular[/COLOR]', ashemaletube + '/videos/most-popular/today/?s=', 2, logos + 'ashemaletube.png', fanart)
	add_dir('[COLOR lime]Top Rated[/COLOR]', ashemaletube + '/videos/top-rated/?s=', 2, logos + 'ashemaletube.png', fanart)
	add_dir('[COLOR lime]Longest[/COLOR]', ashemaletube + '/videos/longest/?s=', 2, logos + 'ashemaletube.png', fanart)

def heavyr_categories(url) :
	home()
	setView('Movies', 'DEFAULT')
	content = make_request(url)
	match = re.compile('<a href="([^"]+)" class="image nopopoff">.+?<img src="([^"]+)" alt="([^"]+)"', re.DOTALL).findall(content)
	for url, thumb, name in match:
		add_dir(name, heavyr + url, 2, heavyr + thumb, fanart)

def xvideos_categories(url) :
	home()
	setView('videos', 'DEFAULT')
	content = make_request(url)
	match = re.compile('<a class="btn btn-default" href="(.+?)">(.+?)</a></li>', re.DOTALL).findall(content)
	for url, name in match:
		url = url.replace('\\','')
		add_dir(name, xvideos + url, 2, logos + 'xvideos.png', fanart)

def xvideos_pornstars(url) :
	home()
	setView('Movies', 'DEFAULT')
	content = make_request(url)
	match = re.compile('<img src="([^"]+)".+?<a href="([^"]+)">([^"]+)</a>', re.DOTALL).findall(content)
	for thumb, url, name in match:
		thumb = thumb.replace('\\', '')
		add_dir(name, xvideos + url + '/videos/new', 2, thumb, fanart)
	try:
		match = re.compile('<a class="active" href=".+?">.+?</a></li><li><a href="([^"]+)">.+?</a></li><li>', re.DOTALL).findall(content)
		add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', xvideos + match[0], 32, logos + 'xvideos.png', fanart)
	except:
		pass

def pornxs_categories(url) :
	home()
	setView('Videos', 'DEFAULT')
	content = make_request(url)
	match = re.compile('<a href="(.+?)" class="squares__item">.+?<div class="squares__item_thumb js-loader" data-loader-src="(.+?)">.+?<div class="squares__item_title">(.+?)</div>', re.DOTALL).findall(content)
	for url, thumb, name in match:
		name = name.replace (' ', '')
		add_dir(name, pornxs + url,  2, thumb, fanart)

def tubedupe_categories(url) :
	home()
	setView('Videos', 'DEFAULT')
	content = make_request(url)
	match = re.compile('<a href="([^"]+)" class="list-item" title="([^"]+)">.+?<img src="([^"]+)".+?<var class="duree">(.+?)</var>', re.DOTALL).findall(content)
	for url, name, thumb, duration in match:
		name = name.replace (' ', '')
		add_dir(name + ' [COLOR lime]('+ duration + ')[/COLOR]', tubedupe + url,  2, thumb, fanart)
		
def tubedupe_rankings(url) :
	home()
	setView('Movies', 'DEFAULT')
	content = make_request(url)
	add_dir('[COLOR lime]Most Popular XXX Videos[/COLOR]', tubedupe + '/most-popular/today/', 2, logos + 'tubedupe.png', fanart)
	add_dir('[COLOR lime]Top Rated Porn Videos[/COLOR]', tubedupe + '/top-rated/today/', 2, logos + 'tubedupe.png', fanart)
	add_dir('[COLOR lime]Most Recent Videos in our Porn Tube[/COLOR]', tubedupe + '/videos/latest', 2, logos + 'tubedupe.png', fanart)

def tubedupe_content(url) :
	home()
	setView('Movies', 'DEFAULT')
	content = make_request(url)
	add_dir('[COLOR lime]Transgender[/COLOR]', tubedupe + '/shemale/', 2, logos + 'tubedupe.png', fanart)
	add_dir('[COLOR lime]Gay[/COLOR]', tubedupe + '/gay/', 2, logos + 'tubedupe.png', fanart)
	add_dir('[COLOR lime]Hetero[/COLOR]', tubedupe, 2, logos + 'tubedupe.png', fanart)

def motherless_sorting(url) :
	home()
	setView('Movies', 'DEFAULT')
	content = make_request(url)
	match = re.compile('<a href="([^"]+)" title=".+?">(Most.+?|Popular.+?)</a>').findall(content)
	for url, name in match:
		add_dir(name, motherless + url,  2, logos + 'motherless.png', fanart)

def emplix_categories(url) :
	home()
	setView('Movies', 'DEFAULT')
	content = make_request(url)
	match = re.compile(' <a class="thumb" href="(.+?)">.+?<img src="(.+?)" alt="(.+?)">.+?<div class="vidcountSp">(.+?)</div>', re.DOTALL).findall(content)
	for url, thumb, name, duration in match:
		name = name.replace('&amp;', '&').replace('&quot;', '"').replace('&#39;', '\'')
		add_dir(name + ' [COLOR lime]('+ duration + ')[/COLOR]', empflix + url, 2, 'http:' + thumb, fanart)

def emplix_sorting(url) :
	home()
	setView('Movies', 'DEFAULT')
	content = make_request(url)
	match = re.compile('<a href="([^"]*)">(Most Recent|Most Popular|Top Rated)</a>').findall(content)
	for url, name in match:
		add_dir(name, empflix  + url,  2, logos + 'empflix.png', fanart)

def fantasti_collections(url):
	home()
	setView('Movies', 'DEFAULT')
	content = make_request(url)
	add_dir('[COLOR lightgreen]fantasti.cc  collections   [COLOR red]Search[/COLOR]', fantasti, 1, logos + 'fantasti.png', fanart)
	add_dir('[COLOR lime]Sorting [/COLOR]', fantasti + '/videos/collections/popular/today/',  49, logos + 'fantasti.png', fanart)
	match = re.compile('<a class="clnk" href="([^"]+)">([^"]+)</a>.+?https:(.+?).jpg', re.DOTALL).findall(content)
	for url, name, thumb in match:
		name = name.replace('&amp;', '&').replace('&quot;', '"').replace('&#39;', '\'')
		add_dir(name, fantasti + url + '#collectionSubmittedVideos',  2, 'https:' + thumb + '.jpg', fanart)
	try:
		match = re.compile('<a href="(.+?)">next &gt;&gt;</a>').findall(content)
		add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', fantasti + match[0], 48, logos + 'fantasti.png', fanart)
	except:
		pass

def fatasti_sorting(url) :
	home()
	setView('Movies', 'DEFAULT')
	content = make_request(url)
	if 'collections' in url:
		match = re.compile('<a href="/videos/collections/popular/(.+?)">(Today|This Week|This Month|All Time)</a>').findall(content)
		for url, name in match:
			add_dir('Popular Videos ' + name, fantasti + '/videos/collections/popular/' + url + '/',  48, logos + 'fantasti.png', fanart)
	else:
		match = re.compile('<a href="/videos/popular/(.+?)" style=".+?">(today|this week|this month|all time)</a>').findall(content)
		for url, name in match:
			add_dir('Popular Videos ' + name, fantasti + '/videos/popular/' + url,  2, logos + 'fantasti.png', fanart)

def fantasti_categories(url):
	home()
	setView('Movies', 'DEFAULT')
	add_dir('[COLOR lightgreen]fantasti.cc	 [COLOR red]Search[/COLOR]', fantasti, 1, logos + 'fantasti.png', fanart)
	add_dir('[COLOR lime]Collection[/COLOR]', fantasti + '/videos/collections/popular/31days/', 48, logos + 'fantasti.png', fanart)
	add_dir('[COLOR lime]Category [/COLOR]', fantasti + '/category/',  18, logos + 'fantasti.png', fanart)
	add_dir('[COLOR lime]Sorting [/COLOR]', fantasti + '/videos/popular/today/',  49, logos + 'fantasti.png', fanart)
	content = make_request(url)
	match = re.compile('<a class="yesPopunder" href="/category/(.+?)/">.+?<div.+?class="thumb catThumb".+?data-src="(.+?)"', re.DOTALL).findall(content)
	for url, thumb in match:
		name = url
		add_dir(name, fantasti + '/search/' + url + '/tube/date/' , 2, thumb, fanart)

def fantasti_content(url):
	home()
	setView('Movies', 'DEFAULT')
	add_dir('[COLOR lightgreen]fantasti.cc	 [COLOR red]Search[/COLOR]', fantasti, 1, logos + 'fantasti.png', fanart)
	add_dir('Fantasti.cc [COLOR yellow] Transgendered[/COLOR]', fantasti + '/ajax/widgets/widget.php?media=videos&filters=upload_improved&sort=latest&pro=null&filter=7&q=&limit=500&page=1&tpl=user/videos_search_users.tpl&cache=5&pager=true&div=featured_videos&clear=true', 2, logos + 'fantasti.png', fanart)

def porngo_categories(url):
	home()
	setView('Movies', 'DEFAULT')
	content = make_request(url)
	match = re.compile('<div class="letter-block__item">.+?<a href="(.+?)" class="letter-block__link">.+?<span>(.+?)</span>', re.DOTALL).findall(content)
	for url, name in match:
		add_dir(name, url,  2, logos + 'porngo.png', fanart)

def uflash_categories(url):
	home()
	setView('Movies', 'DEFAULT')
	content = make_request(url)
	match = re.compile('<li><a href="(.+?)">([^<]+)</a></li>', re.DOTALL).findall(content)
	for url, name in match:
		add_dir(name, uflash + url,  2, logos + 'uflash.png', fanart)

def javbangers_categories(url):
	home()
	setView('Movies', 'DEFAULT')
	content = make_request(url)
	match = re.compile('<a class="item" href="(.+?)" title="(.+?)">.+?<img class="thumb" src="(.+?)"', re.DOTALL).findall(content)
	for url, name, thumb in match:
		add_dir(name, url,  2, javbangers + thumb, fanart)

def luxuretv_categories(url):
	home()
	setView('Movies', 'DEFAULT')
	content = make_request(url)
	match = re.compile('<a href="(.+?)">.+?<img class="img" src="(.+?)" alt="(.+?)"', re.DOTALL).findall(content)
	for url, thumb, name in match:
		add_dir(name, url,  2, thumb, fanart)

def xvideos_sorting(url) :
	home()
	setView('Movies', 'DEFAULT')
	content = make_request(url)
	match = re.compile('<li><a href="/best/([^"]+)" class="btn btn.+?">(.+?)</a></li', re.DOTALL).findall(content)
	for url, name in match:
		add_dir(name, xvideos + '/best/' + url,  2, logos + 'xvideos.png', fanart)

def resolve_url(url):
	content = make_request(url)
	if 'xvideos' in url:
		if '[1080p]' in name:
			media_url = re.compile('html5player.setVideoHLS(.+?);').findall(content) [0]
			media_url = media_url.replace('(\'','').replace(')','').replace('hls.m3u8','hls-1080p.m3u8').replace('\'','')
		elif '[720p]' in name:
			media_url = re.compile('html5player.setVideoHLS(.+?);').findall(content) [0]
			media_url = media_url.replace('(\'','').replace(')','').replace('hls.m3u8','hls-720p.m3u8').replace('\'','')
		else:
			media_url = urllib.unquote(re.compile("flv_url=(.+?)&amp").findall(content)[-1])
	elif 'motherless' in url:		
		media_url = re.compile('__fileurl = \'(.+?)\';').findall(content)[0]
	elif 'efukt' in url:	
		media_url = re.compile('<source src="(.+?)" type="video/mp4">').findall(content)[0]	
		media_url = media_url.replace('amp;','')
	elif 'redtube' in url:
		media_url = re.compile('{"defaultQuality":true,"format":"","quality":".+?","videoUrl":"(.+?)"},').findall(content)[0]
		media_url = media_url.replace('\\','')
	elif 'vikiporn.com' in url:
		media_url = re.compile("video_url: '(.+?)',").findall(content)[0]
	elif 'xh' in url:
		media_url = re.compile('"mp4File":"(.+?)",').findall(content)[0]
		media_url = media_url.replace('\\','')
	elif 'pornxs.com' in url:
		media_url = 'https:' + re.compile('<source src="(.+?)" type="video/mp4">').findall(content)[0]
		media_url = media_url.replace('&amp;','&')
	elif 'youjizz' in url:
		try:
			media_url = 'https:' + re.compile('"filename":"([^"]+.mp4[^"]*)",').findall(content)[-1]
			media_url = media_url.replace('/','')
		except:
			media_url = 'https:' + re.compile('"filename":"([^"]+.mp4[^"]*)",').findall(content)[0]
			media_url = media_url.replace('/','')
	elif 'hentaigasm' in url:
		media_url = re.compile('file: "(.+?)",').findall(content)[0]
	elif 'ashemaletube' in url:
		media_url = re.compile('"src":"(.+?)","desc":".+?"').findall(content)[0]
		media_url = media_url.replace('/','')
	elif 'heavy-r' in url:
			media_url = re.compile('<source type="video/mp4" src="([^"]+)">').findall(content)[0]
	elif 'empflix' in url:
		media_url = re.compile('<meta itemprop="contentUrl" content="(.+?)" />').findall(content)[0]
	elif 'porngo' in url:
		media_url = re.compile("<source src='(.+?)' type='video/mp4'").findall(content)[0]
	elif 'fantasti' in url:
		media_url = re.compile('<source src="(.+?)">').findall(content)[0]
		#return resolve_url(url)
	elif 'uflash' in url:
		try:
			media_url = re.compile('<hd>(.+?)</hd>').findall(content)[0]
		except:
			media_url = re.compile('<src>(.+?)</src>').findall(content)[0]
	elif 'jav' in url:
		try:
			media_url = re.compile("video_alt_url: '(.+?)'").findall(content)[0]
		except:
			media_url = re.compile("video_url: 'function/0/(.+?)'").findall(content)[0]
	elif 'luxuretv.com' in url:
		media_url = re.compile('source src="(.+?)" type=').findall(content)[0]
	elif 'porn300' in url:
		media_url = re.compile('<source src="(.+?)" type="video/mp4">').findall(content)[0]	
		media_url = media_url.replace('amp;','')
	elif 'tubedupe' in url:
		media_url = re.compile("video_alt_url: '(.+?)',                 video_alt_url_text: '720p',").findall(content)[0]	
	else:
		media_url = url
	item = xbmcgui.ListItem(name, path = media_url)
	item.setMimeType('video/mp4')
	xbmcplugin.setResolvedUrl(int(sys.argv[1]), True, item)
	return

def get_params():
	param = []
	paramstring = sys.argv[2]
	if len(paramstring)>= 2:
		params = sys.argv[2]
		cleanedparams = params.replace('?', '')
		if (params[len(params)-1] == '/'):
			params = params[0:len(params)-2]
		pairsofparams = cleanedparams.split('&')
		param = {}
		for i in range(len(pairsofparams)):
			splitparams = {}
			splitparams = pairsofparams[i].split('=')
			if (len(splitparams)) == 2:
				param[splitparams[0]] = splitparams[1]
	return param

def add_dir(name, url, mode, iconimage, fanart):
	u = sys.argv[0] + '?url=' + urllib_parse.quote_plus(url) + '&mode=' + str(mode) +\
		'&name=' + urllib_parse.quote_plus(name) + '&iconimage=' + str(iconimage)
	ok = True
	liz = xbmcgui.ListItem(name)
	liz.setArt({ 'thumb': iconimage, 'icon': icon, 'fanart': fanart})
	ok = xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]), url=u,
									listitem=liz, isFolder=True)
	return ok

def add_link(name, url, mode, iconimage, fanart):
	quoted_url = urllib_parse.quote(url)
	u = sys.argv[0] + '?url=' + quoted_url + '&mode=' + str(mode)\
		+ '&name=' + str(name) + "&iconimage=" + str(iconimage)
	ok = True
	liz = xbmcgui.ListItem(name)
	liz.setArt({'thumb': iconimage, 'icon': icon, 'fanart': iconimage})
	liz.setInfo(type="Video", infoLabels={"Title": name})
	try:
		liz.setContentLookup(False)
	except:
		pass
	liz.setProperty('IsPlayable', 'true')
	ok = xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]), url=u,
									listitem=liz, isFolder=False)
	return ok

def uflash_nextpage(current_url, content):
	match = re.compile('<span class="currentpage">([0-9]+)</span>', re.DOTALL).findall(content)
	next_page = int(match.pop()) + 1
	parsed_url = urlparse.urlparse(current_url)
	queries = parsed_url.query.split('&')
	result = []
	has_page = False

	for query in queries:
		if query.startswith('page='):
			next_page_query = "page=%s" % str(next_page)
			result.append(next_page_query)
			has_page = True
			continue
		result.append(query)
	# First page doesn't have page query parameter
	if not has_page:
		result.append("page=%s" % str(next_page))

	modified_query = '&'.join(result)
	parsed_url = parsed_url._replace(query=modified_query)
	add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', parsed_url.geturl(), 2, logos + 'uflash.png', fanart)
	return parsed_url.geturl()

params = get_params()
url = None
name = None
mode = None
iconimage = None

try:
	url = urllib_parse.unquote_plus(params["url"])
except:
	pass
try:
	name = urllib_parse.unquote_plus(params["name"])
except:
	pass
try:
	mode = int(params["mode"])
except:
	pass
try:
	iconimage = urllib_parse.unquote_plus(params["iconimage"])
except:
	pass

print ("Mode: " + str(mode))
print ("URL: " + str(url))
print ("Name: " + str(name))
print ("iconimage: " + str(iconimage))

def setView(content, viewType):
	# set content type so library shows more views and info
	if content:
		xbmcplugin.setContent(int(sys.argv[1]), content)
	if addon.getSetting('auto-view') == 'true':
		xbmc.executebuiltin("Container.SetViewMode(%s)" % addon.getSetting(viewType) )

if mode == None or url == None or len(url) < 1:
	main()

elif mode == 1:
	search()

elif mode == 2:
	xbmc.log("mode==2, starturl=%s" % url, xbmc.LOGERROR)
	start(url)

elif mode == 3:
	media_list(url)
elif mode == 4:
	resolve_url(url)
elif mode == 8:
	redtube_sorting(url)
elif mode == 9:
	redtube_categories(url)
elif mode == 12:
	lubtetube_pornstars(url)
elif mode == 13:
	flv_channels_list(url)
elif mode == 14:
	porn300_categories(url)
elif mode == 15:
	tubedupe_categories(url)	
elif mode == 16:
	vikiporn_categories(url)
elif mode == 17:
	xhamster_categories(url)
elif mode == 18:
	fantasti_categories(url)
elif mode == 19:
	tubedupe_rankings(url)
elif mode == 20:
	tubedupe_content(url)	
elif mode == 24:
	xhamster_content(url)
elif mode == 27:
	xvideos_categories(url)
elif mode == 28:
	youjizz_categories(url)
elif mode == 29:
	hentaigasm_categories(url)
elif mode == 30:
	ashemaletube_categories(url)
elif mode == 31:
	ashemaletube_sorting(url)    
elif mode == 32:
	xvideos_pornstars(url)
elif mode == 33:
	heavyr_categories(url)
elif mode == 39:
	pornxs_categories(url)
elif mode == 42:
	xhamster_rankigs(url)
elif mode == 44:
	motherless_sorting(url)
elif mode == 45:
	emplix_categories(url)
elif mode == 46:
	emplix_sorting(url)
elif mode == 48:
	fantasti_collections(url)
elif mode == 49:
	fatasti_sorting(url)
elif mode == 50:
	fatasti_content(url)
elif mode == 52:
	porngo_categories(url)
elif mode == 54:
	uflash_categories(url)
elif mode == 55:
	ashemaletube_pornstars(url)
elif mode == 60:
	motherless_galeries_cat(url)
elif mode == 61:
	motherless_being_watched_now(url)
elif mode == 62:
	motherless_groups_cat(url)
elif mode == 64:
	javbangers_categories(url)
elif mode == 68:
	luxuretv_categories(url)
elif mode == 71:
	xvideos_sorting(url)
elif mode == 70:
	item = xbmcgui.ListItem(name, path = url)
	item.setMimeType('video/mp4')
	xbmcplugin.setResolvedUrl(int(sys.argv[1]), True, item)
xbmcplugin.endOfDirectory(int(sys.argv[1]))