# -*- coding: utf-8 -*-

import xbmcaddon
import xbmcgui


ADDON = xbmcaddon.Addon("plugin.video.adulthideout")

RESOLVERS = [
    ("88z", "resolver_enable_88z"),
    ("Bigwarp", "resolver_enable_bigwarp"),
    ("Dood", "resolver_enable_doodstream"),
    ("Hglink", "resolver_enable_hglink"),
    ("LuluStream", "resolver_enable_lulustream"),
    ("MixDrop", "resolver_enable_mixdrop"),
    ("MyDaddy", "resolver_enable_mydaddy"),
    ("Netu", "resolver_enable_dirtyvideo"),
    ("StreamTape", "resolver_enable_streamtape"),
    ("TubexPlayer", "resolver_enable_tubexplayer"),
    ("TurboPlayers", "resolver_enable_turboplayers"),
    ("Vidhide", "resolver_enable_vidhide"),
    ("Vidello", "resolver_enable_vidello"),
    ("Voe", "resolver_enable_voe"),
    ("Vsonic", "resolver_enable_vsonic"),
    ("VTube", "resolver_enable_vtube"),
    ("WatchStreamHD", "resolver_enable_watchstreamhd"),
]


def main():
    enabled = [
        index
        for index, (_, setting_id) in enumerate(RESOLVERS)
        if ADDON.getSetting(setting_id) != "false"
    ]
    selected = xbmcgui.Dialog().multiselect(
        ADDON.getLocalizedString(30820),
        [name for name, _ in RESOLVERS],
        preselect=enabled,
    )
    if selected is None:
        return
    selected = set(selected)
    for index, (_, setting_id) in enumerate(RESOLVERS):
        ADDON.setSetting(setting_id, "true" if index in selected else "false")


if __name__ == "__main__":
    main()
