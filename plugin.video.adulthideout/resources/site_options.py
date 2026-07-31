# -*- coding: utf-8 -*-

import os
import xml.etree.ElementTree as ET

import xbmcaddon
import xbmcgui


ADDON = xbmcaddon.Addon("plugin.video.adulthideout")

SITE_SETTINGS = {
    "AShemaleTube": [
        "ashemaletube_pf_country",
        "ashemaletube_pf_penis",
        "ashemaletube_pf_breast",
        "ashemaletube_pf_hair",
        "ashemaletube_pf_birthday",
        "ashemaletube_pf_eyes",
        "ashemaletube_pf_gender",
    ],
    "Eporner": [
        "eporner_gay_filter",
        "eporner_quality_filter",
        "eporner_min_duration",
    ],
    "Erome": ["erome_content_type"],
    "FreeOMovie": ["freeomovie_autoplay_hoster"],
    "MissAV": [
        "missav_actress_filter_height",
        "missav_actress_filter_cup",
        "missav_actress_filter_age",
        "missav_actress_filter_debut",
    ],
    "PornSlash": ["pornslash_content_type"],
    "Rule34Video": ["rule34video_content_type"],
    "SpankBang": [
        "spankbang_orientation",
        "spankbang_quality",
        "spankbang_duration",
    ],
    "SuperPorn": ["superporn_content_type"],
    "TubePornClassic": ["tubepornclassic_min_duration"],
    "TXXX": ["txxx_content_type"],
    "Wow.xxx": ["wowxxx_quality"],
    "xHamster": [
        "xhamster_category",
        "xhamster_min_duration",
        "xhamster_resolution",
    ],
    "XNXX": [
        "xnxx_content_type",
        "xnxx_duration",
        "xnxx_quality",
    ],
}

VALUE_OVERRIDES = {
    "missav_actress_filter_height": [
        "",
        "131-135",
        "136-140",
        "141-145",
        "146-150",
        "151-155",
        "156-160",
        "161-165",
        "166-170",
        "171-175",
        "176-180",
        "181-185",
        "186-190",
    ],
    "missav_actress_filter_cup": [""] + list("ABCDEFGHIJKLMNOPQ"),
    "missav_actress_filter_age": ["", "0-20", "20-30", "30-40", "40-50", "50-60", "60-99"],
    "missav_actress_filter_debut": [""] + [str(year) for year in range(2025, 2009, -1)],
}

LABEL_OVERRIDES = {
    "Content": 30005,
    "Quality": 30223,
    "Duration": 30224,
}


def localize(value):
    text = (value or "").strip()
    if text.isdigit():
        translated = ADDON.getLocalizedString(int(text))
        return translated or text
    if text in LABEL_OVERRIDES:
        return ADDON.getLocalizedString(LABEL_OVERRIDES[text]) or text
    return text


def read_definitions():
    settings_path = os.path.join(ADDON.getAddonInfo("path"), "resources", "settings.xml")
    root = ET.parse(settings_path).getroot()
    return {
        item.get("id"): item
        for category in root.findall("category")
        for item in category.findall("setting")
        if item.get("id")
    }


def choices_for(item):
    if item.get("type") == "bool":
        labels = [ADDON.getLocalizedString(30817), ADDON.getLocalizedString(30818)]
        return list(zip(labels, ("false", "true")))
    if item.get("lvalues"):
        labels = [localize(value) for value in item.get("lvalues").split("|")]
    else:
        labels = [value.strip() for value in item.get("values", "").split("|")]
    values = VALUE_OVERRIDES.get(item.get("id"), labels)
    return list(zip(labels, values))


def selected_index(item, choices):
    raw = ADDON.getSetting(item.get("id"))
    if item.get("type") == "bool":
        return 1 if raw == "true" else 0
    if item.get("type") == "enum":
        try:
            return max(0, min(int(raw or item.get("default", "0")), len(choices) - 1))
        except (TypeError, ValueError):
            return 0
    try:
        return [value for _, value in choices].index(raw)
    except ValueError:
        try:
            return max(0, min(int(raw), len(choices) - 1))
        except (TypeError, ValueError):
            return 0


def set_choice(item, choices, index):
    setting_id = item.get("id")
    if item.get("type") == "bool":
        ADDON.setSetting(setting_id, "true" if index else "false")
    elif item.get("type") == "enum":
        ADDON.setSetting(setting_id, str(index))
    else:
        ADDON.setSetting(setting_id, choices[index][1])


def reset_site(setting_ids, definitions):
    for setting_id in setting_ids:
        item = definitions.get(setting_id)
        if item is not None:
            ADDON.setSetting(setting_id, item.get("default", ""))


def configure_site(site, setting_ids, definitions):
    dialog = xbmcgui.Dialog()
    available = [setting_id for setting_id in setting_ids if setting_id in definitions]
    while True:
        rows = []
        items = []
        for setting_id in available:
            item = definitions[setting_id]
            choices = choices_for(item)
            if not choices:
                continue
            index = selected_index(item, choices)
            rows.append(
                "{}: [COLOR yellow]{}[/COLOR]".format(
                    localize(item.get("label")), choices[index][0]
                )
            )
            items.append((item, choices, index))
        rows.append(ADDON.getLocalizedString(30815))
        selected = dialog.select(site, rows)
        if selected < 0:
            return
        if selected == len(items):
            if dialog.yesno(site, ADDON.getLocalizedString(30816)):
                reset_site(available, definitions)
            continue
        item, choices, current = items[selected]
        choice = dialog.select(
            localize(item.get("label")),
            [label for label, _ in choices],
            preselect=current,
        )
        if choice >= 0:
            set_choice(item, choices, choice)


def main():
    definitions = read_definitions()
    sites = sorted(SITE_SETTINGS, key=str.lower)
    selected = xbmcgui.Dialog().select(ADDON.getLocalizedString(30813), sites)
    if selected >= 0:
        configure_site(sites[selected], SITE_SETTINGS[sites[selected]], definitions)


if __name__ == "__main__":
    main()
