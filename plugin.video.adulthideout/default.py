#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os
import time
import json
import re
import urllib.parse
import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
import xbmcvfs
import traceback
import inspect
from importlib import import_module
from resources.lib import dns_retry
from resources.lib.view_utils import end_directory_with_view

ADDON = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo('id')
ADDON_PATH = ADDON.getAddonInfo('path')
ADDON_HANDLE = int(sys.argv[1])
RESOURCES_DIR = os.path.join(ADDON_PATH, 'resources')
WEBSITES_DIR = os.path.join(RESOURCES_DIR, 'websites')
LOGOS_DIR = os.path.join(RESOURCES_DIR, 'logos')
FANART_PATH = os.path.join(LOGOS_DIR, 'fanart.jpg')
DEFAULT_ICON_PATH = os.path.join(LOGOS_DIR, 'icon.png')
VAULT_ICON_PATH = os.path.join(LOGOS_DIR, 'vault.png')
VIEW_SERVICE_PATH = os.path.join(ADDON_PATH, 'resources', 'lib', 'view_service.py')
VIEW_SERVICE_VERSION = "20"
DIAGNOSTICS_ADDON_ID = "script.adulthideout.kvat"
OPT_IN_WEBSITE_SETTINGS = {
    "crazyshit": "show_crazyshit",
    "pervclips": "show_pervclips",
}

MAIN_MENU_SORT_KEYS = ("az", "za", "newest", "category")
CONTENT_FILTER_KEYS = ("general", "trans", "hentai", "jav", "rule34", "fetish", "live", "creator")
TYPE_FILTER_KEYS = ("tube", "archive", "live", "resolver")
CONTENT_LABEL_IDS = {
    "general": 30787,
    "trans": 30788,
    "hentai": 30789,
    "jav": 30790,
    "rule34": 30791,
    "fetish": 30792,
    "live": 30793,
    "creator": 30794,
}
TYPE_LABEL_IDS = {
    "tube": 30795,
    "archive": 30796,
    "live": 30797,
    "resolver": 30798,
}
WEBSITE_LABEL_OVERRIDES = {
    "giantessporn": "Giantess Porn",
    "tickleporn": "Tickle Porn",
}
WEBSITE_CATALOG_PATH = os.path.join(RESOURCES_DIR, "website_catalog.json")
_website_catalog = None
_website_taxonomy_index = None
_hidden_websites_cache = None

dns_retry.install()

def log(msg, level=xbmc.LOGINFO):
    xbmc.log(f"[{ADDON_ID}] {msg}", level)

def notify_user(msg):
    xbmcgui.Dialog().notification('AdultHideout Error', str(msg), xbmcgui.NOTIFICATION_ERROR, 3000)

def ensure_view_service():
    try:
        window = xbmcgui.Window(10000)
        service_running = window.getProperty("AdultHideout.ViewServiceRunning") == "true"
        service_version = window.getProperty("AdultHideout.ViewServiceVersion")
        if (not service_running or service_version != VIEW_SERVICE_VERSION) and xbmcvfs.exists(VIEW_SERVICE_PATH):
            if service_running and service_version != VIEW_SERVICE_VERSION:
                xbmc.executebuiltin("StopScript({})".format(VIEW_SERVICE_PATH))
                xbmc.sleep(500)
            xbmc.executebuiltin("RunScript({})".format(VIEW_SERVICE_PATH))
    except Exception as exc:
        log("Could not start view service: {}".format(exc), xbmc.LOGWARNING)

def get_setting_id_from_name(name):
    return f"show_{name.lower().replace('-', '').replace('_', '')}"

def get_website_label(name):
    return WEBSITE_LABEL_OVERRIDES.get(
        name,
        name.replace("_", " ").replace("-", " ").title(),
    )

def get_main_menu_art(icon_path):
    return {
        "icon": icon_path,
        "thumb": icon_path,
        "poster": icon_path,
        "banner": icon_path,
        "landscape": icon_path,
        "fanart": FANART_PATH,
    }

def get_hidden_websites():
    global _hidden_websites_cache
    if _hidden_websites_cache is not None:
        return set(_hidden_websites_cache)
    try:
        values = json.loads(ADDON.getSetting("hidden_websites") or "[]")
    except (TypeError, ValueError):
        values = []
    _hidden_websites_cache = {str(value) for value in values if value}
    return set(_hidden_websites_cache)

def save_hidden_websites(names):
    global _hidden_websites_cache
    _hidden_websites_cache = set(names)
    ADDON.setSetting("hidden_websites", json.dumps(sorted(_hidden_websites_cache)))

def migrate_legacy_website_visibility(modules):
    if ADDON.getSetting("website_visibility_migrated") == "true":
        return
    hidden = get_hidden_websites()
    false_setting_ids = set()
    try:
        profile_path = xbmcvfs.translatePath(ADDON.getAddonInfo("profile"))
        settings_path = os.path.join(profile_path, "settings.xml")
        if os.path.exists(settings_path):
            with open(settings_path, "r", encoding="utf-8") as handle:
                settings_text = handle.read()
            false_setting_ids.update(re.findall(
                r'<setting\b[^>]*\bid=["\'](show_[^"\']+)["\'][^>]*>\s*false\s*</setting>',
                settings_text,
                re.IGNORECASE,
            ))
    except Exception as exc:
        log("Could not read legacy website visibility: {}".format(exc), xbmc.LOGDEBUG)
    for name in modules:
        setting_id = get_setting_id_from_name(name)
        if setting_id in false_setting_ids and name not in OPT_IN_WEBSITE_SETTINGS:
            hidden.add(name)
    save_hidden_websites(hidden)
    ADDON.setSetting("website_visibility_migrated", "true")

def is_website_hidden(name):
    opt_in_setting = OPT_IN_WEBSITE_SETTINGS.get(name)
    if opt_in_setting and ADDON.getSetting(opt_in_setting) != "true":
        return True
    return name in get_hidden_websites()

def hide_website(name):
    if not name:
        return
    opt_in_setting = OPT_IN_WEBSITE_SETTINGS.get(name)
    if opt_in_setting:
        ADDON.setSetting(opt_in_setting, "false")
    else:
        hidden = get_hidden_websites()
        hidden.add(name)
        save_hidden_websites(hidden)
    xbmcgui.Dialog().notification(
        localized(30801, "Website hidden"),
        get_website_label(name),
        xbmcgui.NOTIFICATION_INFO,
        2500,
    )
    xbmc.executebuiltin("Container.Update({},replace)".format(sys.argv[0]))

def get_currently_hidden_websites():
    hidden = get_hidden_websites()
    for name, setting_id in OPT_IN_WEBSITE_SETTINGS.items():
        if ADDON.getSetting(setting_id) != "true":
            hidden.add(name)
    return sorted(hidden)

def manage_hidden_websites():
    hidden = get_currently_hidden_websites()
    if not hidden:
        xbmcgui.Dialog().notification(
            localized(30802, "Hidden websites"),
            localized(30805, "No hidden websites"),
            xbmcgui.NOTIFICATION_INFO,
            2500,
        )
        return
    labels = [get_website_label(name) for name in hidden]
    selected = xbmcgui.Dialog().multiselect(
        localized(30804, "Select websites to restore"),
        labels,
    )
    if not selected:
        return
    restored = {hidden[index] for index in selected}
    stored = get_hidden_websites() - restored
    save_hidden_websites(stored)
    for name in restored:
        setting_id = OPT_IN_WEBSITE_SETTINGS.get(name)
        if setting_id:
            ADDON.setSetting(setting_id, "true")
    xbmc.executebuiltin("Container.Update({},replace)".format(sys.argv[0]))

def restore_all_websites():
    if not xbmcgui.Dialog().yesno(
        localized(30803, "Restore all websites"),
        localized(30806, "Make every website visible again?"),
    ):
        return
    save_hidden_websites(set())
    for setting_id in OPT_IN_WEBSITE_SETTINGS.values():
        ADDON.setSetting(setting_id, "true")
    xbmc.executebuiltin("Container.Update({},replace)".format(sys.argv[0]))

def get_main_menu_sort_index():
    try:
        index = int(ADDON.getSetting("main_menu_website_sort") or "0")
    except (TypeError, ValueError):
        index = 0
    return index if 0 <= index < len(MAIN_MENU_SORT_KEYS) else 0

def localized(label_id, fallback):
    return ADDON.getLocalizedString(label_id) or fallback

def get_website_catalog():
    global _website_catalog
    if _website_catalog is not None:
        return _website_catalog
    try:
        with open(WEBSITE_CATALOG_PATH, "r", encoding="utf-8") as handle:
            _website_catalog = json.load(handle)
    except Exception as exc:
        log("Could not load website catalog: {}".format(exc), xbmc.LOGWARNING)
        _website_catalog = {}
    return _website_catalog

def get_website_catalog_order():
    sites = get_website_catalog().get("sites", {})
    return {
        name: int(metadata.get("catalog_id", 0))
        for name, metadata in sites.items()
    }

def get_website_taxonomy_index():
    global _website_taxonomy_index
    if _website_taxonomy_index is not None:
        return _website_taxonomy_index
    taxonomy = get_website_catalog().get("taxonomy", {})
    _website_taxonomy_index = {}
    for section in ("content", "types"):
        memberships = {}
        for key, names in taxonomy.get(section, {}).items():
            for name in names:
                memberships.setdefault(name, []).append(key)
        _website_taxonomy_index[section] = memberships
    return _website_taxonomy_index

def get_website_taxonomy(name):
    taxonomy = get_website_taxonomy_index()
    return (
        taxonomy.get("content", {}).get(name, ["general"]),
        taxonomy.get("types", {}).get(name, ["tube"]),
    )

def _read_filter_setting(setting_id, allowed):
    try:
        values = json.loads(ADDON.getSetting(setting_id) or "[]")
    except (TypeError, ValueError):
        values = []
    return [value for value in values if value in allowed]

def get_active_website_filters():
    return (
        _read_filter_setting("main_menu_website_content_filter", CONTENT_FILTER_KEYS),
        _read_filter_setting("main_menu_website_type_filter", TYPE_FILTER_KEYS),
    )

def website_matches_filters(name):
    selected_content, selected_types = get_active_website_filters()
    content, source_types = get_website_taxonomy(name)
    content_match = not selected_content or bool(set(content) & set(selected_content))
    type_match = not selected_types or bool(set(source_types) & set(selected_types))
    return content_match and type_match

def get_primary_category(name):
    content, _ = get_website_taxonomy(name)
    return next((key for key in CONTENT_FILTER_KEYS if key in content), "general")

def sort_website_modules(modules):
    mode = get_main_menu_sort_index()
    if mode == 1:
        return sorted(modules, reverse=True)
    if mode == 2:
        catalog_order = get_website_catalog_order()
        return sorted(modules, key=lambda name: (-catalog_order.get(name, 0), name.lower()))
    if mode == 3:
        category_order = {key: index for index, key in enumerate(CONTENT_FILTER_KEYS)}
        return sorted(
            modules,
            key=lambda name: (category_order.get(get_primary_category(name), 999), name.lower()),
        )
    return sorted(modules)

def select_main_menu_sort():
    current = get_main_menu_sort_index()
    options = [
        "A-Z",
        "Z-A",
        localized(30782, "Newest Websites"),
        localized(30783, "Category"),
    ]
    selected = xbmcgui.Dialog().select(localized(30778, "Sort websites..."), options, preselect=current)
    if selected == -1:
        return
    ADDON.setSetting("main_menu_website_sort", str(selected))
    xbmc.executebuiltin("Container.Update({},replace)".format(sys.argv[0]))

def select_main_menu_filters():
    selected_content, selected_types = get_active_website_filters()
    entries = [localized(30799, "All Websites")]
    entries.extend(
        "{}: {}".format(localized(30784, "Content"), localized(CONTENT_LABEL_IDS[key], key.title()))
        for key in CONTENT_FILTER_KEYS
    )
    entries.extend(
        "{}: {}".format(localized(30785, "Website type"), localized(TYPE_LABEL_IDS[key], key.title()))
        for key in TYPE_FILTER_KEYS
    )
    preselect = []
    preselect.extend(1 + CONTENT_FILTER_KEYS.index(key) for key in selected_content)
    type_offset = 1 + len(CONTENT_FILTER_KEYS)
    preselect.extend(type_offset + TYPE_FILTER_KEYS.index(key) for key in selected_types)
    selected = xbmcgui.Dialog().multiselect(
        localized(30779, "Filter websites..."),
        entries,
        preselect=preselect,
    )
    if selected is None:
        return
    if 0 in selected:
        content_values = []
        type_values = []
    else:
        content_values = [
            CONTENT_FILTER_KEYS[index - 1]
            for index in selected
            if 1 <= index < type_offset
        ]
        type_values = [
            TYPE_FILTER_KEYS[index - type_offset]
            for index in selected
            if type_offset <= index < type_offset + len(TYPE_FILTER_KEYS)
        ]
    ADDON.setSetting("main_menu_website_content_filter", json.dumps(content_values))
    ADDON.setSetting("main_menu_website_type_filter", json.dumps(type_values))
    xbmc.executebuiltin("Container.Update({},replace)".format(sys.argv[0]))

def run_diagnostics(site=""):
    try:
        diagnostics = xbmcaddon.Addon(DIAGNOSTICS_ADDON_ID)
    except Exception:
        # InstallAddon already presents Kodi's native confirmation dialog. A
        # separate yes/no prompt here caused users to confirm the same install
        # twice and raced Kodi's asynchronous add-on registry refresh.
        xbmc.executebuiltin(
            "InstallAddon({})".format(DIAGNOSTICS_ADDON_ID),
            True,
        )
        xbmc.executebuiltin("UpdateLocalAddons", True)
        monitor = xbmc.Monitor()
        diagnostics = None
        for _attempt in range(40):
            if monitor.waitForAbort(0.25):
                break
            try:
                diagnostics = xbmcaddon.Addon(DIAGNOSTICS_ADDON_ID)
                if diagnostics.getAddonInfo("path"):
                    break
            except Exception:
                diagnostics = None

        if diagnostics is None:
            xbmcgui.Dialog().ok(
                localized(30821, "AdultHideout Diagnostics"),
                localized(
                    30845,
                    "Installation failed. Install AdultHideout Diagnostics from the AdultHideout Repository.",
                ),
            )
            return

    script_path = os.path.join(
        xbmcvfs.translatePath(diagnostics.getAddonInfo("path")),
        "default.py",
    )
    arguments = []
    if site:
        arguments.append("site={}".format(urllib.parse.quote_plus(site)))
    quoted_arguments = "".join(',"{}"'.format(value) for value in arguments)
    xbmc.executebuiltin('RunScript("{}"{})'.format(script_path, quoted_arguments))


def get_website_menu_context(download_menu_command):
    return [
        (
            localized(30778, "Sort websites..."),
            "RunPlugin({}?mode=1&action=select_main_menu_sort)".format(sys.argv[0]),
        ),
        (
            localized(30779, "Filter websites..."),
            "RunPlugin({}?mode=1&action=select_main_menu_filters)".format(sys.argv[0]),
        ),
        (localized(30733, "Open Download Manager"), download_menu_command),
    ]

def build_main_menu_fast():
    if not os.path.exists(WEBSITES_DIR):
        log(f"ERROR: Websites folder not found at: {WEBSITES_DIR}", xbmc.LOGERROR)
        notify_user(f"Missing folder: {WEBSITES_DIR}")
        xbmcplugin.endOfDirectory(ADDON_HANDLE)
        return

    log(f"Scanning for websites in: {WEBSITES_DIR}", xbmc.LOGDEBUG)

    try:
        available_logos = set(os.listdir(LOGOS_DIR))
    except OSError:
        available_logos = set()

    found_any = False

    global_search_item = xbmcgui.ListItem(label="[COLOR yellow]Global Search[/COLOR]")
    global_search_icon = os.path.join(LOGOS_DIR, "search.png")
    if "search.png" not in available_logos:
        global_search_icon = DEFAULT_ICON_PATH
    global_search_item.setArt(get_main_menu_art(global_search_icon))
    download_menu_command = 'Container.Update({}?mode=31)'.format(sys.argv[0])
    global_search_item.addContextMenuItems(get_website_menu_context(download_menu_command))
    xbmcplugin.addDirectoryItem(
        handle=ADDON_HANDLE,
        url=f"{sys.argv[0]}?mode=20&website=global_search",
        listitem=global_search_item,
        isFolder=True,
    )

    vault_item = xbmcgui.ListItem(label="[COLOR yellow]{}[/COLOR]".format(ADDON.getLocalizedString(30700) or "Vault"))
    vault_icon = VAULT_ICON_PATH if os.path.exists(VAULT_ICON_PATH) else DEFAULT_ICON_PATH
    vault_item.setArt(get_main_menu_art(vault_icon))
    vault_item.addContextMenuItems(get_website_menu_context(download_menu_command))
    xbmcplugin.addDirectoryItem(
        handle=ADDON_HANDLE,
        url=f"{sys.argv[0]}?mode=40",
        listitem=vault_item,
        isFolder=True,
    )

    show_downloads = ADDON.getSetting("show_download_manager") == "true"
    try:
        from resources.lib.download_manager import has_active_downloads, start_next_download
        start_next_download()
        if not show_downloads:
            show_downloads = has_active_downloads()
    except Exception as exc:
        log("Could not inspect download history: {}".format(exc), xbmc.LOGDEBUG)
    if show_downloads:
        downloads_item = xbmcgui.ListItem(label="[COLOR yellow]{}[/COLOR]".format(
            ADDON.getLocalizedString(30641) or "Downloads"
        ))
        downloads_item.setArt(get_main_menu_art(DEFAULT_ICON_PATH))
        xbmcplugin.addDirectoryItem(
            handle=ADDON_HANDLE,
            url=f"{sys.argv[0]}?mode=31",
            listitem=downloads_item,
            isFolder=True,
        )

    if ADDON.getSetting("enable_offline_library") == "true":
        offline_item = xbmcgui.ListItem(label="[COLOR yellow]{}[/COLOR]".format(
            ADDON.getLocalizedString(30642) or "Offline videos"
        ))
        offline_item.setArt(get_main_menu_art(DEFAULT_ICON_PATH))
        xbmcplugin.addDirectoryItem(
            handle=ADDON_HANDLE,
            url=f"{sys.argv[0]}?mode=32",
            listitem=offline_item,
            isFolder=True,
        )

    website_modules = [
        filename[:-3] for filename in os.listdir(WEBSITES_DIR)
        if filename.endswith('.py') and filename != '__init__.py'
    ]
    migrate_legacy_website_visibility(website_modules)
    website_modules = [name for name in website_modules if not is_website_hidden(name)]
    website_modules = [name for name in website_modules if website_matches_filters(name)]
    category_mode = get_main_menu_sort_index() == 3
    for module_raw_name in sort_website_modules(website_modules):
        
        label = get_website_label(module_raw_name)
        if category_mode:
            category = get_primary_category(module_raw_name)
            category_label = localized(CONTENT_LABEL_IDS[category], category.title())
            label = "[COLOR gray]{}[/COLOR]  {}".format(category_label, label)
        
        icon_name = f"{module_raw_name}.png"
        fallback_name = f"{module_raw_name.replace('_', '-')}.png"
        if icon_name in available_logos:
            icon_path = os.path.join(LOGOS_DIR, icon_name)
        elif fallback_name in available_logos:
            icon_path = os.path.join(LOGOS_DIR, fallback_name)
        else:
            icon_path = DEFAULT_ICON_PATH

        context_menu = get_website_menu_context(download_menu_command)
        if ADDON.getSetting("enable_website_collections") == "true":
            context_menu.insert(0, (
                localized(30827, "Add to Collection..."),
                "RunPlugin({}?mode=70&action=add_to_collection&site={})".format(
                    sys.argv[0],
                    urllib.parse.quote_plus(module_raw_name),
                ),
            ))
        context_menu.insert(3, (
            localized(30800, "Hide website"),
            "RunPlugin({}?mode=1&action=hide_website&target={})".format(
                sys.argv[0],
                urllib.parse.quote_plus(module_raw_name),
            ),
        ))
        if module_raw_name == 'chaturbate':
            context_menu.append(
                ('Filter...', f'RunPlugin({sys.argv[0]}?mode=7&action=select_filter&website={module_raw_name})')
            )

        url_params = f"?mode=2&website={module_raw_name}&url=BOOTSTRAP"
        url = f"{sys.argv[0]}{url_params}"
        
        li = xbmcgui.ListItem(label=label)
        li.setArt(get_main_menu_art(icon_path))
        li.addContextMenuItems(context_menu)
        
        xbmcplugin.addDirectoryItem(handle=ADDON_HANDLE, url=url, listitem=li, isFolder=True)
        found_any = True

    if not found_any:
        selected_content, selected_types = get_active_website_filters()
        if selected_content or selected_types:
            log("No enabled websites match the active website filters", xbmc.LOGINFO)
        else:
            log("No website files found (.py)!", xbmc.LOGWARNING)

    end_directory_with_view(ADDON_HANDLE, ADDON)

def load_single_website(website_name):
    if ADDON_PATH not in sys.path:
        sys.path.insert(0, ADDON_PATH)
        
    from resources.lib.base_website import BaseWebsite

    try:
        module = import_module(f'resources.websites.{website_name}')
        for attr in dir(module):
            cls = getattr(module, attr)
            if isinstance(cls, type) and issubclass(cls, BaseWebsite) and cls is not BaseWebsite and cls.__module__ == module.__name__:
                return cls(ADDON_HANDLE)
    except ImportError:
        log(f"ImportError for {website_name}, trying fallback search.", xbmc.LOGWARNING)

    target_clean = website_name.replace('-', '').replace('_', '').lower()
    
    if os.path.exists(WEBSITES_DIR):
        for filename in os.listdir(WEBSITES_DIR):
            if filename.endswith('.py') and filename != '__init__.py':
                fname_clean = filename[:-3].replace('-', '').replace('_', '').lower()
                if fname_clean == target_clean:
                    try:
                        module = import_module(f'resources.websites.{filename[:-3]}')
                        for attr in dir(module):
                            cls = getattr(module, attr)
                            if isinstance(cls, type) and issubclass(cls, BaseWebsite) and cls is not BaseWebsite and cls.__module__ == module.__name__:
                                return cls(ADDON_HANDLE)
                    except Exception as e:
                        log(f"Error loading fallback module {filename}: {e}", xbmc.LOGERROR)
    
    return None

def call_with_item_count(target_website, callback):
    original_add = xbmcplugin.addDirectoryItem
    count = {"items": 0}
    started = time.time()

    def counting_add(*args, **kwargs):
        count["items"] += 1
        return original_add(*args, **kwargs)

    xbmcplugin.addDirectoryItem = counting_add
    try:
        callback()
    except Exception:
        raise
    finally:
        xbmcplugin.addDirectoryItem = original_add
    return count["items"], time.time() - started

def handle_website_collections(params):
    from resources.lib.website_collections import CustomCollectionsManager
    mgr = CustomCollectionsManager(ADDON)
    action = params.get('action', 'collections_menu')

    def collection_label(name):
        labels = {
            "Favorites": localized(30839, "Favorites"),
            "My Top Sites": localized(30840, "My Top Sites"),
        }
        return labels.get(name, name)

    if action == 'add_to_collection':
        site_id = params.get('site') or params.get('website')
        if not site_id:
            return
        collections = mgr.get_collection_names()
        dialog_options = [collection_label(name) for name in collections] + ["[COLOR yellow]+ {}[/COLOR]".format(
            localized(30828, "New Collection")
        )]
        selected = xbmcgui.Dialog().select(localized(30827, "Add to Collection..."), dialog_options)
        if selected == -1:
            return
        if selected == len(collections):
            kb = xbmc.Keyboard("", localized(30829, "Enter Collection Name"))
            kb.doModal()
            if kb.isConfirmed() and kb.getText().strip():
                new_name = kb.getText().strip()
                mgr.create_collection(new_name)
                mgr.add_site(new_name, site_id)
                xbmcgui.Dialog().notification(
                    localized(30826, "Website Collections"),
                    localized(30831, "Added to Collection").format(new_name),
                    xbmcgui.NOTIFICATION_INFO,
                    2000,
                )
        else:
            col_name = collections[selected]
            mgr.add_site(col_name, site_id)
            xbmcgui.Dialog().notification(
                localized(30826, "Website Collections"),
                    localized(30831, "Added to Collection").format(collection_label(col_name)),
                xbmcgui.NOTIFICATION_INFO,
                2000,
            )
        return

    if action == 'remove_from_collection':
        col_name = params.get('collection')
        site_id = params.get('site')
        if col_name and site_id:
            mgr.remove_site(col_name, site_id)
            xbmc.executebuiltin("Container.Refresh")
        return

    if action == 'create_collection':
        kb = xbmc.Keyboard("", localized(30829, "Enter Collection Name"))
        kb.doModal()
        if kb.isConfirmed() and kb.getText().strip():
            new_name = kb.getText().strip()
            ok, msg = mgr.create_collection(new_name)
            if ok:
                xbmc.executebuiltin("Container.Refresh")
            else:
                message_id = 30837 if msg == "exists" else 30838
                xbmcgui.Dialog().notification(
                    localized(30832, "Error"),
                    localized(message_id, "Collection already exists" if msg == "exists" else "Collection name cannot be empty"),
                    xbmcgui.NOTIFICATION_ERROR,
                    2500,
                )
        return

    if action == 'delete_collection':
        col_name = params.get('collection')
        if col_name and xbmcgui.Dialog().yesno(
            localized(30833, "Delete"),
            localized(30834, "Delete collection '{}'?").format(col_name),
        ):
            mgr.delete_collection(col_name)
            xbmc.executebuiltin("Container.Refresh")
        return

    if action == 'view_collection':
        col_name = params.get('collection')
        sites = mgr.get_collection_sites(col_name)
        try:
            available_logos = set(os.listdir(LOGOS_DIR))
        except OSError:
            available_logos = set()

        for module_raw_name in sites:
            if not os.path.isfile(os.path.join(WEBSITES_DIR, "{}.py".format(module_raw_name))):
                continue
            label = get_website_label(module_raw_name)
            icon_name = f"{module_raw_name}.png"
            fallback_name = f"{module_raw_name.replace('_', '-')}.png"
            if icon_name in available_logos:
                icon_path = os.path.join(LOGOS_DIR, icon_name)
            elif fallback_name in available_logos:
                icon_path = os.path.join(LOGOS_DIR, fallback_name)
            else:
                icon_path = DEFAULT_ICON_PATH

            context_menu = [
                (localized(30835, "Remove from Collection"), f"RunPlugin({sys.argv[0]}?mode=70&action=remove_from_collection&collection={urllib.parse.quote_plus(col_name)}&site={urllib.parse.quote_plus(module_raw_name)})")
            ]

            url = f"{sys.argv[0]}?mode=2&website={module_raw_name}&url=BOOTSTRAP"
            li = xbmcgui.ListItem(label=label)
            li.setArt(get_main_menu_art(icon_path))
            li.addContextMenuItems(context_menu)
            xbmcplugin.addDirectoryItem(handle=ADDON_HANDLE, url=url, listitem=li, isFolder=True)

        xbmcplugin.endOfDirectory(ADDON_HANDLE, succeeded=True, cacheToDisc=False)
        return

    # Default: collections_menu
    collections = mgr.get_collections()

    new_item = xbmcgui.ListItem(label="[COLOR yellow]+ {}[/COLOR]".format(
        localized(30828, "New Collection")
    ))
    new_item.setArt(get_main_menu_art(DEFAULT_ICON_PATH))
    xbmcplugin.addDirectoryItem(
        handle=ADDON_HANDLE,
        url=f"{sys.argv[0]}?mode=70&action=create_collection",
        listitem=new_item,
        isFolder=False,
    )

    for col_name, site_list in collections.items():
        label = f"{collection_label(col_name)} [COLOR gray]({len(site_list)})[/COLOR]"
        col_item = xbmcgui.ListItem(label=label)
        col_item.setArt(get_main_menu_art(DEFAULT_ICON_PATH))
        context_menu = [
            (localized(30836, "Delete Collection"), f"RunPlugin({sys.argv[0]}?mode=70&action=delete_collection&collection={urllib.parse.quote_plus(col_name)})")
        ]
        col_item.addContextMenuItems(context_menu)
        xbmcplugin.addDirectoryItem(
            handle=ADDON_HANDLE,
            url=f"{sys.argv[0]}?mode=70&action=view_collection&collection={urllib.parse.quote_plus(col_name)}",
            listitem=col_item,
            isFolder=True,
        )

    xbmcplugin.endOfDirectory(ADDON_HANDLE, succeeded=True, cacheToDisc=False)

def handle_routing():
    ensure_view_service()
    params = {}
    try:
        if len(sys.argv) > 2 and sys.argv[2]:
            params = dict(urllib.parse.parse_qsl(sys.argv[2][1:]))
    except Exception:
        pass

    mode = params.get('mode')
    website_name = params.get('website')
    action = params.get('action')
    
    log(f"Routing: mode={mode}, website={website_name}, action={action}")

    if mode == '70' or action in ('collections_menu', 'view_collection', 'add_to_collection', 'remove_from_collection', 'create_collection', 'delete_collection'):
        handle_website_collections(params)
        return

    if mode is None:
        try:
            from resources.lib.official_source import verify_and_warn
            verify_and_warn(ADDON, show_dialog=True)
        except Exception as exc:
            log(f"Official source check failed unexpectedly: {exc}", xbmc.LOGWARNING)

    if mode is None and action != 'direct_search':
        build_main_menu_fast()
        return

    website_menu_actions = (
        'select_main_menu_sort',
        'select_main_menu_filters',
        'hide_website',
        'manage_hidden_websites',
        'restore_all_websites',
        'run_diagnostics',
    )
    if mode == '1' and params.get('action') in website_menu_actions:
        if params.get('action') == 'select_main_menu_sort':
            select_main_menu_sort()
        elif params.get('action') == 'select_main_menu_filters':
            select_main_menu_filters()
        elif params.get('action') == 'hide_website':
            hide_website(params.get('target', ''))
        elif params.get('action') == 'manage_hidden_websites':
            manage_hidden_websites()
        elif params.get('action') == 'restore_all_websites':
            restore_all_websites()
        elif params.get('action') == 'run_diagnostics':
            run_diagnostics(params.get('target', ''))
        xbmcplugin.endOfDirectory(ADDON_HANDLE, succeeded=True, updateListing=False, cacheToDisc=False)
        return

    if website_name == 'global_search' or mode in ('20', '21') or action == 'direct_search':
        from resources.lib.global_search import GlobalSearch
        global_search = GlobalSearch(ADDON_HANDLE, addon=ADDON, loader=load_single_website, logger=log)
        if action == 'direct_search' or params.get('direct_query') or params.get('q'):
            query = params.get('query') or params.get('direct_query') or params.get('q') or ''
            if len(query.strip()) < 3:
                xbmcplugin.endOfDirectory(ADDON_HANDLE, succeeded=True, cacheToDisc=False)
                return
            try:
                page = int(params.get('page', '1') or '1')
            except Exception:
                page = 1
            global_search.run(
                query,
                refresh=params.get('refresh') == '1',
                page=page,
                search_mode=params.get('search_mode', 'skin'),
            )
            return
        elif action == 'new_search':
            global_search.new_search(params.get('search_mode', 'selected'))
        elif action == 'show_presets':
            global_search.show_presets()
        elif action == 'apply_preset':
            global_search.apply_preset(params.get('profile'))
        elif action == 'combine_presets':
            global_search.combine_presets()
        elif action == 'save_custom_preset':
            global_search.save_custom_preset()
        elif action == 'show_custom_presets':
            global_search.show_custom_presets()
        elif action == 'apply_custom_preset':
            global_search.apply_custom_preset(params.get('preset_id'))
        elif action == 'delete_custom_preset':
            global_search.delete_custom_preset()
        elif action == 'choose_sources':
            global_search.choose_sources()
        elif action == 'select_all_sources':
            global_search.select_all_sources()
        elif action == 'show_sources':
            global_search.show_sources()
        elif action == 'clear_history':
            global_search.clear_history()
        elif action == 'edit_search':
            global_search.edit_search(params.get('query', ''), search_mode=params.get('search_mode', 'selected'))
        elif action == 'refresh_search':
            try:
                page = int(params.get('page', '1') or '1')
            except Exception:
                page = 1
            global_search.refresh_search(params.get('query', ''), page=page, search_mode=params.get('search_mode', 'selected'))
        elif action == 'select_page_to_vault':
            global_search.select_page_to_vault(
                params.get('query', ''),
                page=params.get('page', '1'),
                search_mode=params.get('search_mode', 'selected'),
            )
        elif action == 'configure_results':
            global_search.configure_results(
                params.get('query', ''),
                search_mode=params.get('search_mode', 'selected'),
            )
        elif mode == '21':
            try:
                page = int(params.get('page', '1') or '1')
            except Exception:
                page = 1
            global_search.run(
                params.get('query', ''),
                refresh=params.get('refresh') == '1',
                page=page,
                search_mode=params.get('search_mode', 'selected'),
            )
        else:
            global_search.show_menu()
        return

    if mode == '40':
        from resources.lib.personal_library import PersonalLibrary
        PersonalLibrary(ADDON_HANDLE, sys.argv[0]).handle(params.get('action'), params)
        return

    if mode == '31':
        from resources.lib import download_manager
        from resources.lib import offline_library
        action = params.get('action')
        if action == 'delete_offline':
            offline_library.delete(params.get('path', ''))
            xbmcplugin.endOfDirectory(ADDON_HANDLE, succeeded=True, updateListing=False, cacheToDisc=False)
        else:
            download_manager.handle_manager_action(ADDON_HANDLE, sys.argv[0], action, params)
        return

    if mode == '32':
        from resources.lib import offline_library
        offline_library.show(ADDON_HANDLE, sys.argv[0], params.get('path', ''))
        return

    target_website = None
    if website_name:
        target_website = load_single_website(website_name)
    
    if not target_website:
        log(f"Could not load website module for: {website_name}", xbmc.LOGERROR)
        notify_user(f"Module not found: {website_name}")
        xbmcplugin.endOfDirectory(ADDON_HANDLE)
        return

    url = params.get('url')
    action = params.get('action')
    original_url = params.get('url')

    websites_with_internal_bootstrap = ['drtuber', 'cumlouder', 'pornhat']
    
    if url == 'BOOTSTRAP' and mode == '2' and website_name not in websites_with_internal_bootstrap:
        if hasattr(target_website, 'get_start_url_and_label'):
             url, _ = target_website.get_start_url_and_label()
        else:
             url = target_website.base_url

    if mode == '2':
        page = int(params.get('page', '1'))
        
        # Safe call: check if process_content supports 'page' argument
        call_with_item_count(
            target_website,
            lambda: target_website.process_content(url, page=page)
            if 'page' in inspect.signature(target_website.process_content).parameters
            else target_website.process_content(url)
        )
        
    elif mode == '4':
        target_website.play_video(url)

    elif mode == '30':
        from resources.lib.download_manager import enqueue_download
        enqueue_download(
            target_website,
            params.get('original_url') or url,
            title=params.get('name', ''),
            thumbnail=params.get('thumbnail', ''),
        )
        xbmcplugin.endOfDirectory(ADDON_HANDLE, succeeded=True, updateListing=False, cacheToDisc=False)
        
    elif mode == '5':
        target_website.show_search_menu()
        
    elif mode == '6':
        target_website.handle_search_entry(url, mode, target_website.name, action)
        
    elif mode == '7':
        original_url = params.get('original_url') or params.get('url')
        filter_type = params.get('filter_type')
        
        if action and hasattr(target_website, action):
            try:
                if action in ('download_with_ffmpeg', 'record_with_ffmpeg'):
                    getattr(target_website, action)(original_url, params.get('name'))
                elif filter_type:
                    getattr(target_website, action)(filter_type, original_url)
                else:
                    getattr(target_website, action)(original_url)
            except TypeError:
                getattr(target_website, action)()
        else:
            notify_user("Action not supported or implemented")
        xbmcplugin.endOfDirectory(ADDON_HANDLE, succeeded=True, updateListing=False, cacheToDisc=False)
            
    elif mode == '8':
        if hasattr(target_website, 'process_categories'):
            call_with_item_count(target_website, lambda: target_website.process_categories(url))
        else:
            xbmcplugin.endOfDirectory(ADDON_HANDLE)
            
    elif mode == '9':
        if hasattr(target_website, 'process_pornstars'):
            call_with_item_count(target_website, lambda: target_website.process_pornstars(url))
        elif hasattr(target_website, 'process_actresses_list'):
            call_with_item_count(target_website, lambda: target_website.process_actresses_list(url))
        else:
            xbmcplugin.endOfDirectory(ADDON_HANDLE)
            
    elif mode == '10':
        if hasattr(target_website, 'process_channels'):
            call_with_item_count(target_website, lambda: target_website.process_channels(url))
        else:
            xbmcplugin.endOfDirectory(ADDON_HANDLE)
            
    elif mode == '11':
        if hasattr(target_website, 'process_collections'):
            call_with_item_count(target_website, lambda: target_website.process_collections(url))
        else:
            xbmcplugin.endOfDirectory(ADDON_HANDLE)
            
    else:
        xbmcplugin.endOfDirectory(ADDON_HANDLE)

if __name__ == '__main__':
    try:
        handle_routing()
    except Exception as e:
        log(f"CRITICAL ERROR: {e}\n{traceback.format_exc()}", xbmc.LOGERROR)
        notify_user(f"Critical Error: {str(e)}")
        xbmcplugin.endOfDirectory(ADDON_HANDLE)
