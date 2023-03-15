import six
import json
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


def parse_content(content):
	match = re.compile('<a  href="([^"]*)" title="([^"]*)".+?https://(.*?).jpg').findall(content)
	for url, name, thumb in match:
		name = name.replace('&amp;', '&').replace('&quot;', '"').replace('&#039;', '\'')
		add_link(name, url , 4, 'https://' + thumb + '.jpg', fanart)
	try:
		match = re.compile('class="anchored_item active ">.+?</a><a href="(.+?)"').findall(content)
		add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', efukt + match[0], 2, logos + 'efukt.png', fanart)
	except:
		pass