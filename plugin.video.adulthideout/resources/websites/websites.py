from importlib import import_module
from .website_config import website_list
import os
import importlib
import xbmc


def create_default_module(module_name):
    module_file_path = os.path.join(os.path.dirname(__file__), f"{module_name}.py")
    if not os.path.exists(module_file_path):
        with open(module_file_path, "w") as f:
            f.write("import re\n")
            f.write("import xbmc\n")
            f.write("from ..functions import add_dir, add_link, make_request, fanart, logos\n")
            f.write("import xbmcgui\n")
            f.write("import xbmcplugin\n")
            f.write("import xbmcaddon\n")
            f.write("import urllib.parse as urllib_parse\n\n")
            f.write(f"def process_{module_name}_content(url, page=1):\n")
            f.write("    if page == 1:\n")
            f.write(f"        add_dir(f'Search {module_name.capitalize()}', '{module_name}', 5, logos + '{module_name}.png', fanart)\n")
            f.write("    content = make_request(url)\n")
            f.write("    match = re.compile('<a  href=\"([^\\\"]*)\" title=\"([^\\\"]*)\".+?https://(.*?).jpg').findall(content)\n")
            f.write("    for url, name, thumb in match:\n")
            f.write("        name = name.replace('&amp;', '&').replace('&quot;', '\"').replace('&#039;', \"'\")\n")
            f.write("        add_link(name, url, 4, f'https://{thumb}.jpg', fanart)\n\n")
            f.write("    try:\n")
            f.write("        match = re.compile('class=\"anchored_item active \">.+?</a><a href=\"(.+?)\"').findall(content)\n")
            f.write("        if match:\n")
            f.write(f"            add_dir('[COLOR blue]Next Page >>>>[/COLOR]', {module_name} + match[0], 2, logos + '{module_name}.png', fanart)\n")
            f.write("    except:\n")
            f.write("        pass\n\n")
            f.write(f"def play_{module_name}_video(url):\n")
            f.write("    content = make_request(url)\n")
            f.write("    media_url = re.compile('<source src=\"(.+?)\" type=\"video/mp4\">').findall(content)[0]\n")
            f.write("    media_url = media_url.replace('amp;', '')\n")
            f.write("    return media_url\n")


websites = []

for website in website_list:
    module_name = website["module_name"]
    create_default_module(module_name)
    try:
        module = import_module(f".{module_name}", package="resources.websites")

        websites.append({
            "name": website["name"],
            "url": website["url"],
            "search_url": website["search_url"],
            "function": module.__dict__.get(f"process_{module_name}_content"),
            "play_function": module.__dict__.get(f"play_{module_name}_video"),
        })
    except Exception as e:
        xbmc.log(f"Error importing module {module_name}: {e}", xbmc.LOGERROR)
