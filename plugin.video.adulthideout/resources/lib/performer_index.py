# -*- coding: utf-8 -*-
import html
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

try:
    import xbmc
    import xbmcaddon
    import xbmcgui
    import xbmcplugin
    import xbmcvfs
except ImportError:
    xbmc = None
    xbmcaddon = None
    xbmcgui = None
    xbmcplugin = None
    xbmcvfs = None

try:
    from resources.lib.view_utils import end_directory_with_view
except ImportError:
    try:
        from view_utils import end_directory_with_view
    except ImportError:
        end_directory_with_view = None

try:
    from resources.lib.star_database import StarDatabase
except ImportError:
    try:
        from star_database import StarDatabase
    except ImportError:
        StarDatabase = None

_ADDON = None


def _get_addon():
    global _ADDON
    if _ADDON is None and xbmcaddon:
        _ADDON = xbmcaddon.Addon()
    return _ADDON


def _text(string_id, fallback=""):
    addon = _get_addon()
    if addon:
        try:
            val = addon.getLocalizedString(string_id)
            if val:
                return val
        except Exception:
            pass
    return fallback


def _end_dir(handle, addon, content_type="videos"):
    if end_directory_with_view and addon:
        try:
            end_directory_with_view(handle, addon, content_type=content_type)
            return
        except Exception:
            pass
    if xbmcplugin:
        xbmcplugin.endOfDirectory(handle)


DEFAULT_MATRIX = {
    "gender": "all",
    "ethnicity": "all",
    "height": "all",
    "cup": "all",
    "hair": "all",
    "eyes": "all",
    "build": "all",
    "decade": "all",
}


def _numeric_value(value):
    if isinstance(value, (int, float)):
        return float(value)
    match = re.search(r"\d+(?:[.,]\d+)?", str(value or ""))
    if not match:
        return None
    try:
        return float(match.group(0).replace(",", "."))
    except (TypeError, ValueError):
        return None


def matches_matrix(star, matrix):
    if not matrix:
        return True
    
    # Gender
    if matrix.get("gender") and matrix.get("gender") != "all":
        g = str(star.get("gender", "")).lower()
        target_g = str(matrix.get("gender", "")).lower()
        if target_g in ("ts", "trans", "t") and g not in ("t", "ts", "trans") and "trans" not in star.get("tags", []):
            return False
        elif target_g in ("f", "female") and g not in ("f", "female"):
            return False
        elif target_g in ("m", "male") and g not in ("m", "male"):
            return False
        elif target_g not in ("ts", "trans", "t", "f", "female", "m", "male") and g != target_g:
            return False

    # Ethnicity
    if matrix.get("ethnicity") and matrix.get("ethnicity") != "all":
        def norm_e(e):
            e = str(e).lower()
            if e in ("black", "ebony", "african"): return "ebony"
            if e in ("latin", "latina", "hispanic"): return "latina"
            if e in ("white", "caucasian", "european"): return "caucasian"
            if e in ("asian", "oriental"): return "asian"
            if e in ("arab", "middle eastern"): return "arab"
            if e in ("indian", "south asian"): return "indian"
            return e

        target_e = norm_e(matrix.get("ethnicity"))
        star_e = norm_e(star.get("ethnicity", ""))
        star_tags = [norm_e(t) for t in star.get("tags", [])]
        if star_e != target_e and target_e not in star_tags:
            return False

    # Height
    if matrix.get("height") and matrix.get("height") != "all":
        h_cm = _numeric_value(star.get("height_cm") or star.get("height"))
        if h_cm is None:
            return False
        target_h = matrix.get("height")
        if target_h == "petite" and h_cm >= 162:
            return False
        elif target_h == "average" and not (162 <= h_cm <= 174):
            return False
        elif target_h == "tall" and h_cm < 175:
            return False
        elif target_h == "giant" and h_cm < 185:
            return False

    # Cup / Breast
    if matrix.get("cup") and matrix.get("cup") != "all":
        target_cup = matrix.get("cup")
        cup = star.get("cup", "C")
        b_type = star.get("breast_type", "natural")
        if target_cup == "A-B" and cup not in ("A", "B"):
            return False
        elif target_cup == "C-D" and cup not in ("C", "D"):
            return False
        elif target_cup == "DD-E" and cup not in ("DD", "E"):
            return False
        elif target_cup == "F+" and cup not in ("F", "G", "G+"):
            return False
        elif target_cup == "natural" and b_type != "natural":
            return False
        elif target_cup == "enhanced" and b_type != "enhanced":
            return False

    # Hair
    if matrix.get("hair") and matrix.get("hair") != "all" and star.get("hair") != matrix.get("hair"):
        return False

    # Eyes
    if matrix.get("eyes") and matrix.get("eyes") != "all" and star.get("eyes") != matrix.get("eyes"):
        return False

    # Build
    if matrix.get("build") and matrix.get("build") != "all" and star.get("build") != matrix.get("build") and matrix.get("build") not in star.get("tags", []):
        return False

    # Decade
    if matrix.get("decade") and matrix.get("decade") != "all":
        target_d = matrix.get("decade")
        if target_d == "vintage" and not star.get("decade", "").startswith("vintage"):
            return False
        elif target_d != "vintage" and star.get("decade") != target_d:
            return False

    return True


class PerformerIndex:
    def __init__(self, addon_handle, plugin_url, addon=None):
        self.addon_handle = addon_handle
        self.plugin_url = plugin_url
        self.addon = addon or _get_addon()
        self.addon_path = self.addon.getAddonInfo("path") if self.addon else ""
        self._cache = None
        self.star_db = StarDatabase(self.addon_path) if StarDatabase else None

    @staticmethod
    def _name_key(value):
        return " ".join(str(value or "").casefold().split())

    def _decorate_performer(self, performer):
        return dict(performer) if performer else performer

    def _get_performer(self, performer_id):
        if self.star_db and self.star_db.available:
            performer = self.star_db.get(performer_id)
            if performer:
                return self._decorate_performer(performer)
        for performer in self._load_performers():
            if str(performer.get("id")) == str(performer_id):
                return performer
        return None

    def _get_profile_path(self):
        base = None
        if xbmcvfs and self.addon:
            try:
                profile_dir = self.addon.getAddonInfo("profile")
                if profile_dir and isinstance(profile_dir, str):
                    base = xbmcvfs.translatePath(profile_dir)
            except Exception:
                pass
        if not base or not isinstance(base, str) or "MagicMock" in str(base):
            base = os.path.join(os.path.expanduser("~"), ".kodi_adulthideout")
        try:
            os.makedirs(base, exist_ok=True)
        except Exception:
            pass
        return base

    def _get_favorites_path(self):
        return os.path.join(self._get_profile_path(), "performer_favorites.json")

    def _get_matrix_path(self):
        return os.path.join(self._get_profile_path(), "performer_matrix.json")

    def _load_performers(self):
        if self._cache is not None:
            return self._cache
        if self.star_db and self.star_db.available:
            performers, _ = self.star_db.list(limit=max(1, self.star_db.count()))
            self._cache = [self._decorate_performer(item) for item in performers]
            return self._cache
        self._cache = []
        return self._cache

    def _load_favorites(self):
        fav_file = self._get_favorites_path()
        if os.path.exists(fav_file):
            try:
                with open(fav_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return []

    def _save_favorites(self, favs):
        fav_file = self._get_favorites_path()
        try:
            with open(fav_file, "w", encoding="utf-8") as f:
                json.dump(favs, f, indent=2, ensure_ascii=False)
        except Exception as e:
            if xbmc:
                xbmc.log(f"[AdultHideout][PerformerIndex] Error saving favorites: {e}", xbmc.LOGERROR)

    def _load_matrix(self):
        m_file = self._get_matrix_path()
        if os.path.exists(m_file):
            try:
                with open(m_file, "r", encoding="utf-8") as f:
                    res = json.load(f)
                    matrix = dict(DEFAULT_MATRIX)
                    matrix.update(res)
                    return matrix
            except Exception:
                pass
        return dict(DEFAULT_MATRIX)

    def _save_matrix(self, matrix):
        m_file = self._get_matrix_path()
        try:
            with open(m_file, "w", encoding="utf-8") as f:
                json.dump(matrix, f, indent=2, ensure_ascii=False)
        except Exception as e:
            if xbmc:
                xbmc.log(f"[AdultHideout][PerformerIndex] Error saving matrix: {e}", xbmc.LOGERROR)

    def _format_plot(self, p):
        return PerformerIndex.format_static_plot(p)

    @staticmethod
    def format_static_plot(p):
        if not p or not isinstance(p, dict):
            return ""
        p_name = p.get("name", "")
        bio = p.get("bio", "").strip()
        country = p.get("country", "")
        birth_year = p.get("birth_year", "")
        cup = p.get("cup", "")
        b_type = p.get("breast_type", "")
        height = p.get("height", "")
        hair = p.get("hair", "")
        eyes = p.get("eyes", "")
        build = p.get("build", "")
        ethnicity = p.get("ethnicity", "")
        aliases = p.get("aliases", [])
        tags = p.get("tags", [])

        # If bio is missing, synthesize a rich descriptive summary
        if not bio:
            bio_parts = [f"{p_name} ist eine"]
            if ethnicity and ethnicity != "all":
                eth_map = {
                    "ebony": "afroamerikanische/Ebony",
                    "latina": "lateinamerikanische/Latina",
                    "caucasian": "europäische/kaukasische",
                    "asian": "asiatische",
                    "indian": "indische",
                    "arab": "arabische",
                    "mixed": "Mixed-Ethnicity",
                }
                bio_parts.append(eth_map.get(ethnicity.lower(), ethnicity.title()))
            if p.get("gender") in ("ts", "trans"):
                bio_parts.append("Transgender / TS Adult-Darstellerin")
            elif p.get("gender") in ("m", "male"):
                bio_parts.append("männlicher Adult-Darsteller")
            else:
                bio_parts.append("Adult-Darstellerin und Fotomodell")

            if country:
                bio_parts.append(f"aus {country.title()}")

            clean_tags = [t.title() for t in tags if t.lower() not in ("trending", "live")]
            if clean_tags:
                bio_parts.append(f", bekannt für Szenen in den Genres {', '.join(clean_tags[:4])}")
            bio_parts.append(".")
            bio = " ".join(bio_parts).replace(" .", ".").replace(" ,", ",")

        lines = [f"{bio}\n"]
        if country:
            lines.append(f"• Herkunft / Country: {country.title()}")
        if ethnicity:
            lines.append(f"• Typ / Ethnicity: {ethnicity.title()}")
        if birth_year:
            lines.append(f"• Geburtsjahr / Born: {birth_year}")
        if height:
            lines.append(f"• Größe / Height: {height}")
        if cup:
            cup_str = f"{cup} ({b_type.title()})" if b_type else cup
            lines.append(f"• Oberweite / Cup: {cup_str}")
        if hair:
            lines.append(f"• Haarfarbe / Hair: {hair.title()}")
        if eyes:
            lines.append(f"• Augenfarbe / Eyes: {eyes.title()}")
        if build:
            lines.append(f"• Körperbau / Build: {build.title()}")
        if aliases:
            lines.append(f"• Aliase / Known as: {', '.join(aliases)}")
        if tags:
            lines.append(f"• Sparten / Tags: {', '.join(tags)}")

        return "\n".join(lines)

    def show_main_menu(self):
        items = [
            (
                f"[COLOR yellow]• [/COLOR][B]{_text(30901, 'Darsteller suchen...')}[/B]",
                f"{self.plugin_url}?mode=60&action=search",
                "DefaultAddonsSearch.png",
            ),
            (
                f"[COLOR gold]★ [/COLOR][B]{_text(30920, 'Star-Finder Filter-Matrix')}[/B]",
                f"{self.plugin_url}?mode=60&action=matrix",
                "DefaultAddonVideo.png",
            ),
            (
                f"[COLOR cyan]★ [/COLOR][B]{_text(30902, 'Trending Stars')}[/B]",
                f"{self.plugin_url}?mode=60&action=browse&cat=trending",
                "DefaultAddonPVRClient.png",
            ),
            (
                f"[COLOR gold]★ [/COLOR][B]{_text(30903, 'Hall of Fame & Legenden')}[/B]",
                f"{self.plugin_url}?mode=60&action=browse&cat=hall_of_fame",
                "DefaultAddonVideo.png",
            ),
            (
                f"[COLOR cyan][ A–Z ][/COLOR] [B]{_text(30904, 'A – Z Darsteller-Index')}[/B]",
                f"{self.plugin_url}?mode=60&action=letters",
                "DefaultFolder.png",
            ),
            (
                f"[COLOR lightblue]• [/COLOR][B]{_text(30905, 'Kategorien & Sparten')}[/B]",
                f"{self.plugin_url}?mode=60&action=categories",
                "DefaultGenre.png",
            ),
            (
                f"[COLOR lime]★ [/COLOR][B]{_text(30906, 'Meine Lieblings-Darsteller')}[/B]",
                f"{self.plugin_url}?mode=60&action=favorites",
                "DefaultFavourites.png",
            ),
        ]

        for label, url, icon in items:
            li = xbmcgui.ListItem(label=label)
            li.setArt({"icon": icon, "thumb": icon, "poster": icon})
            xbmcplugin.addDirectoryItem(self.addon_handle, url, li, isFolder=True)

        _end_dir(self.addon_handle, self.addon, content_type="files")

    def show_matrix(self):
        matrix = self._load_matrix()
        all_performers = self._load_performers()
        matched = [p for p in all_performers if matches_matrix(p, matrix)]
        match_count = len(matched)

        # Field labels mapping
        ethnicity_labels = {
            "all": "Alle (All)",
            "ebony": "Black / Ebony",
            "latina": "Latina / Hispanic",
            "caucasian": "White / Caucasian",
            "asian": "Asian / JAV",
            "indian": "Indian / South Asian",
            "arab": "Arab / Middle Eastern",
            "mixed": "Mixed / Exotic",
        }
        gender_labels = {
            "all": "Alle (All)",
            "f": "Weiblich (Female)",
            "ts": "Trans / Shemale",
            "m": "Männlich (Male)",
        }
        height_labels = {
            "all": "Alle (All)",
            "petite": "Zierlich / Klein (< 1.62m)",
            "average": "Mittelgroß (1.62 – 1.74m)",
            "tall": "Groß (≥ 1.75m)",
            "giant": "Sehr Groß (≥ 1.85m)",
        }
        cup_labels = {
            "all": "Alle (All)",
            "A-B": "A – B Cup (Small)",
            "C-D": "C – D Cup (Medium)",
            "DD-E": "DD – E Cup (Large)",
            "F+": "F+ Cup (Huge / Mega)",
            "natural": "Natürlich (Natural)",
            "enhanced": "Silikon (Enhanced)",
        }
        hair_labels = {
            "all": "Alle (All)",
            "blonde": "Blond (Blonde)",
            "brunette": "Brünett (Brunette)",
            "black": "Schwarz (Black)",
            "redhead": "Rotschopf (Redhead)",
            "other": "Andere / Bunt",
        }
        eyes_labels = {
            "all": "Alle (All)",
            "blue": "Blau (Blue)",
            "brown": "Braun (Brown)",
            "green": "Grün (Green)",
            "hazel": "Haselnuss (Hazel)",
        }
        build_labels = {
            "all": "Alle (All)",
            "petite": "Petite / Zierlich",
            "slim": "Schlank / Slim",
            "athletic": "Athletisch / Sportlich",
            "curvy": "Kurvig / Curvy",
            "busty": "Große Oberweite / Busty",
            "bbw": "BBW / Vollschlank",
        }
        decade_labels = {
            "all": "Alle (All)",
            "2020s": "2020er (Moderne Ära)",
            "2010s": "2010er (Golden Era)",
            "2000s": "2000er (Millennium)",
            "vintage": "Vintage Klassiker (70s/80s/90s)",
        }

        # 1. Action: Show matching performers
        res_url = f"{self.plugin_url}?mode=60&action=show_matrix_results"
        li_res = xbmcgui.ListItem(label=f"[COLOR lime][B]★ {_text(30921, 'Gefilterte Stars anzeigen')} ({match_count} Treffer)[/B][/COLOR]")
        li_res.setArt({"icon": "DefaultFolder.png", "thumb": "DefaultFolder.png"})
        xbmcplugin.addDirectoryItem(self.addon_handle, res_url, li_res, isFolder=True)

        search_url = f"{self.plugin_url}?mode=60&action=matrix_global_search"
        li_search = xbmcgui.ListItem(
            label=f"[COLOR deepskyblue][B]★ {_text(30923, 'Global Search for Filtered Stars')}[/B][/COLOR]"
        )
        li_search.setArt({"icon": "DefaultAddonsSearch.png", "thumb": "DefaultAddonsSearch.png"})
        xbmcplugin.addDirectoryItem(self.addon_handle, search_url, li_search, isFolder=True)

        # 2. Action: Start 24/7 Multi-Star Smart Stream
        star_names = [p.get("name", "") for p in matched if p.get("name")]
        stars_param = ",".join(star_names)
        enc_stars = urllib.parse.quote_plus(stars_param)
        stream_pool = "trans" if matrix.get("gender") in ("ts", "trans") else "top_tubes"
        stream_url = f"{self.plugin_url}?mode=50&action=custom_zap&query={urllib.parse.quote_plus('Multi-Star Matrix')}&stars={enc_stars}&pool={stream_pool}&length=any"
        li_stream = xbmcgui.ListItem(label=f"[COLOR gold][B]★ {_text(30922, '24/7 Multi-Star Smart Stream starten')}[/B][/COLOR] [COLOR yellow]({match_count} Stars)[/COLOR]")
        li_stream.setArt({"icon": "DefaultVideo.png", "thumb": "DefaultVideo.png"})
        xbmcplugin.addDirectoryItem(self.addon_handle, stream_url, li_stream, isFolder=False)

        # 2b. Action: Start 24/7 Multi-Star Full Movies (>= 70 Min)
        movies_stream_url = f"{self.plugin_url}?mode=50&action=custom_zap&query={urllib.parse.quote_plus('Multi-Star Movies')}&stars={enc_stars}&pool={stream_pool}&length=movies"
        li_movies = xbmcgui.ListItem(label=f"[COLOR orange][B]★ 24/7 Full Movies (≥70 Min)[/B][/COLOR] [COLOR yellow]({match_count} Stars)[/COLOR]")
        li_movies.setArt({"icon": "DefaultVideo.png", "thumb": "DefaultVideo.png"})
        xbmcplugin.addDirectoryItem(self.addon_handle, movies_stream_url, li_movies, isFolder=False)

        # 3. Attributes rows
        fields = [
            ("gender", _text(30925, "Geschlecht / Gender"), gender_labels.get(matrix.get("gender", "all"), "Alle")),
            ("ethnicity", _text(30926, "Ethnizität & Herkunft"), ethnicity_labels.get(matrix.get("ethnicity", "all"), "Alle")),
            ("height", _text(30927, "Körpergröße / Height"), height_labels.get(matrix.get("height", "all"), "Alle")),
            ("cup", _text(30928, "Oberweite & Cup"), cup_labels.get(matrix.get("cup", "all"), "Alle")),
            ("hair", _text(30929, "Haarfarbe / Hair"), hair_labels.get(matrix.get("hair", "all"), "Alle")),
            ("eyes", _text(30930, "Augenfarbe / Eyes"), eyes_labels.get(matrix.get("eyes", "all"), "Alle")),
            ("build", _text(30931, "Körperbau / Build"), build_labels.get(matrix.get("build", "all"), "Alle")),
            ("decade", _text(30932, "Karriere-Ära / Dekade"), decade_labels.get(matrix.get("decade", "all"), "Alle")),
        ]

        for field_key, field_name, current_val in fields:
            f_url = f"{self.plugin_url}?mode=60&action=matrix_select&field={field_key}"
            li_f = xbmcgui.ListItem(label=f"[COLOR yellow]{field_name}:[/COLOR] [COLOR cyan][B]{current_val}[/B][/COLOR]")
            li_f.setArt({"icon": "DefaultAddonRepository.png", "thumb": "DefaultAddonRepository.png"})
            xbmcplugin.addDirectoryItem(self.addon_handle, f_url, li_f, isFolder=False)

        # 4. Action: Reset Filter Matrix
        reset_url = f"{self.plugin_url}?mode=60&action=matrix_reset"
        li_reset = xbmcgui.ListItem(label=f"[COLOR red]↻ {_text(30924, 'Filter-Matrix zurücksetzen')}[/COLOR]")
        li_reset.setArt({"icon": "DefaultFolder.png", "thumb": "DefaultFolder.png"})
        xbmcplugin.addDirectoryItem(self.addon_handle, reset_url, li_reset, isFolder=False)

        _end_dir(self.addon_handle, self.addon, content_type="files")

    def _do_matrix_select(self, field):
        options_map = {
            "gender": [
                ("all", "Alle (All)"),
                ("f", "Weiblich (Female)"),
                ("ts", "Trans / Shemale"),
                ("m", "Männlich (Male)"),
            ],
            "ethnicity": [
                ("all", "Alle (All)"),
                ("ebony", "Black / Ebony"),
                ("latina", "Latina / Hispanic"),
                ("caucasian", "White / Caucasian"),
                ("asian", "Asian / JAV"),
                ("indian", "Indian / South Asian"),
                ("arab", "Arab / Middle Eastern"),
                ("mixed", "Mixed / Exotic"),
            ],
            "height": [
                ("all", "Alle (All)"),
                ("petite", "Zierlich / Klein (< 1.62m)"),
                ("average", "Mittelgroß (1.62 – 1.74m)"),
                ("tall", "Groß (≥ 1.75m)"),
                ("giant", "Sehr Groß (≥ 1.85m)"),
            ],
            "cup": [
                ("all", "Alle (All)"),
                ("A-B", "A – B Cup (Small)"),
                ("C-D", "C – D Cup (Medium)"),
                ("DD-E", "DD – E Cup (Large)"),
                ("F+", "F+ Cup (Huge / Mega)"),
                ("natural", "Natürlich (Natural)"),
                ("enhanced", "Silikon (Enhanced)"),
            ],
            "hair": [
                ("all", "Alle (All)"),
                ("blonde", "Blond (Blonde)"),
                ("brunette", "Brünett (Brunette)"),
                ("black", "Schwarz (Black)"),
                ("redhead", "Rotschopf (Redhead)"),
                ("other", "Andere / Bunt"),
            ],
            "eyes": [
                ("all", "Alle (All)"),
                ("blue", "Blau (Blue)"),
                ("brown", "Braun (Brown)"),
                ("green", "Grün (Green)"),
                ("hazel", "Haselnuss (Hazel)"),
            ],
            "build": [
                ("all", "Alle (All)"),
                ("petite", "Petite / Zierlich"),
                ("slim", "Schlank / Slim"),
                ("athletic", "Athletisch / Sportlich"),
                ("curvy", "Kurvig / Curvy"),
                ("busty", "Große Oberweite / Busty"),
                ("bbw", "BBW / Vollschlank"),
            ],
            "decade": [
                ("all", "Alle (All)"),
                ("2020s", "2020er (Moderne Ära)"),
                ("2010s", "2010er (Golden Era)"),
                ("2000s", "2000er (Millennium)"),
                ("vintage", "Vintage Klassiker (70s/80s/90s)"),
            ],
        }

        if field not in options_map:
            return

        choices = options_map[field]
        labels = [c[1] for c in choices]
        keys = [c[0] for c in choices]

        matrix = self._load_matrix()
        current_val = matrix.get(field, "all")
        preselect = keys.index(current_val) if current_val in keys else 0

        dialog = xbmcgui.Dialog()
        selected = dialog.select(f"Filter auswählen: {field.title()}", labels, preselect=preselect)
        if selected >= 0:
            matrix[field] = keys[selected]
            self._save_matrix(matrix)

    def _do_matrix_reset(self):
        self._save_matrix(dict(DEFAULT_MATRIX))
        if xbmcgui:
            xbmcgui.Dialog().notification(
                _text(30900, "Darsteller & Pornstars"),
                "Filter-Matrix zurückgesetzt",
                xbmcgui.NOTIFICATION_INFO,
                1500,
            )

    def matrix_global_search(self):
        matrix = self._load_matrix()
        matched = [performer for performer in self._load_performers() if matches_matrix(performer, matrix)]
        matched.sort(key=lambda performer: performer.get("rank", 999))
        if not matched:
            xbmcgui.Dialog().notification(
                _text(30900, "Star Finder (Beta)"),
                _text(30935, "No performers match your filter"),
                xbmcgui.NOTIFICATION_WARNING,
                2000,
            )
            return self.show_matrix()

        labels = [performer.get("name", "Unknown") for performer in matched]
        selected = xbmcgui.Dialog().select(_text(30923, "Global Search for Filtered Stars"), labels)
        if selected < 0:
            return self.show_matrix()

        query = urllib.parse.quote_plus(labels[selected])
        target = f"{self.plugin_url}?mode=21&website=global_search&query={query}&search_mode=selected"
        xbmcplugin.endOfDirectory(self.addon_handle, succeeded=True, updateListing=False, cacheToDisc=False)
        xbmc.executebuiltin(f"Container.Update({target},replace)")

    def show_matrix_results(self):
        matrix = self._load_matrix()
        all_performers = self._load_performers()
        matched = [p for p in all_performers if matches_matrix(p, matrix)]
        matched.sort(key=lambda x: x.get("rank", 999))
        match_count = len(matched)

        if match_count > 0:
            star_names = [p.get("name", "") for p in matched if p.get("name")]
            stars_param = ",".join(star_names)
            enc_stars = urllib.parse.quote_plus(stars_param)

            # 1. Action: Start 24/7 Multi-Star Smart Stream directly from results list
            stream_pool = "trans" if matrix.get("gender") in ("ts", "trans") else "top_tubes"
            stream_url = f"{self.plugin_url}?mode=50&action=custom_zap&query={urllib.parse.quote_plus('Multi-Star Matrix')}&stars={enc_stars}&pool={stream_pool}&length=any"
            li_stream = xbmcgui.ListItem(label=f"[COLOR gold][B]★ {_text(30922, '24/7 Multi-Star Smart Stream starten')}[/B][/COLOR] [COLOR yellow]({match_count} Stars im Mix)[/COLOR]")
            li_stream.setArt({"icon": "DefaultVideo.png", "thumb": "DefaultVideo.png"})
            xbmcplugin.addDirectoryItem(self.addon_handle, stream_url, li_stream, isFolder=False)

            # 2. Action: Start 24/7 Multi-Star Full Movies (>= 70 Min)
            movies_stream_url = f"{self.plugin_url}?mode=50&action=custom_zap&query={urllib.parse.quote_plus('Multi-Star Movies')}&stars={enc_stars}&pool={stream_pool}&length=movies"
            li_movies = xbmcgui.ListItem(label=f"[COLOR orange][B]★ 24/7 Multi-Star Full Movies (≥70 Min)[/B][/COLOR] [COLOR yellow]({match_count} Stars im Mix)[/COLOR]")
            li_movies.setArt({"icon": "DefaultVideo.png", "thumb": "DefaultVideo.png"})
            xbmcplugin.addDirectoryItem(self.addon_handle, movies_stream_url, li_movies, isFolder=False)

        self._render_performer_list(matched, title_context=_text(30934, "Filter-Treffer"))

    def show_letters(self):
        letters = ["#"] + [chr(i) for i in range(ord("A"), ord("Z") + 1)]
        for l in letters:
            url = f"{self.plugin_url}?mode=60&action=browse&letter={l}"
            li = xbmcgui.ListItem(label=f"[COLOR cyan][B][ {l} ][/B][/COLOR] {_text(30907, 'Darsteller mit')} {l}")
            li.setArt({"icon": "DefaultFolder.png", "thumb": "DefaultFolder.png", "poster": "DefaultFolder.png"})
            xbmcplugin.addDirectoryItem(self.addon_handle, url, li, isFolder=True)
        _end_dir(self.addon_handle, self.addon, content_type="files")

    def show_categories(self):
        categories = [
            ("Darstellerinnen (Female Stars)", "female", "DefaultActor.png"),
            ("Darsteller (Male Stars)", "male", "DefaultActor.png"),
            ("Trans & Shemale Stars", "trans", "DefaultActor.png"),
            ("JAV & Asiatische Stars", "jav", "DefaultActor.png"),
            ("MILF & Mature", "milf", "DefaultActor.png"),
            ("Vintage & Golden Age Klassiker", "vintage", "DefaultActor.png"),
            ("Europaeische Stars", "european", "DefaultActor.png"),
        ]

        for label, cat_key, icon in categories:
            url = f"{self.plugin_url}?mode=60&action=browse&cat={cat_key}"
            li = xbmcgui.ListItem(label=f"[COLOR gold]• [/COLOR][B]{label}[/B]")
            li.setArt({"icon": icon, "thumb": icon, "poster": icon})
            xbmcplugin.addDirectoryItem(self.addon_handle, url, li, isFolder=True)
        _end_dir(self.addon_handle, self.addon, content_type="files")

    def _fetch_live_trending(self, page=1):
        results = []
        try:
            page_suffix = f"{page}/" if page > 1 else ""
            url = f"https://www.eporner.com/pornstars/{page_suffix}"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
            with urllib.request.urlopen(req, timeout=6) as response:
                html_text = response.read().decode('utf-8', errors='ignore')
            matches = re.findall(r'<a[^>]+href=["\'](/pornstar/[^"\']+)["\'][^>]*>(.*?)</a>', html_text, re.DOTALL)
            seen = set()
            for link, text in matches:
                clean_text = re.sub(r'<[^>]+>', ' ', text).strip()
                clean_name = re.sub(r'\s+\d+(?:\s+&raquo;)?$', '', clean_text).strip()
                if not clean_name or len(clean_name) < 3 or clean_name in seen:
                    continue
                seen.add(clean_name)
                babe_thumb = f"https://www.babepedia.com/pics/{urllib.parse.quote(clean_name)}.jpg"
                results.append({
                    "id": clean_name.lower().replace(" ", "_"),
                    "name": clean_name,
                    "thumb": babe_thumb,
                    "country": "Live Chart",
                    "tags": ["trending", "live"],
                    "bio": f"{clean_name} gehört zu den aktuell meistgesehenen und gefragtesten Adult-Darstellerinnen weltweit.",
                })
        except Exception:
            pass
        return results

    def browse(self, cat=None, letter=None, query=None, page=1):
        if self.star_db and self.star_db.available and not cat:
            page_size = 100
            results, total = self.star_db.list(
                query=query,
                letter=letter,
                offset=max(0, page - 1) * page_size,
                limit=page_size,
            )
            results = [self._decorate_performer(item) for item in results]
            self._render_performer_list(results, finish=False)
            if page * page_size < total:
                parts = ["mode=60", "action=browse", f"page={page + 1}"]
                if query:
                    parts.append("query=" + urllib.parse.quote_plus(query))
                if letter:
                    parts.append("letter=" + urllib.parse.quote_plus(letter))
                next_url = self.plugin_url + "?" + "&".join(parts)
                li = xbmcgui.ListItem(label=f"[COLOR cyan][B]{_text(30712, 'Next Page')} >>[/B][/COLOR]")
                li.setArt({"icon": "DefaultFolder.png", "thumb": "DefaultFolder.png"})
                xbmcplugin.addDirectoryItem(self.addon_handle, next_url, li, isFolder=True)
            _end_dir(self.addon_handle, self.addon, content_type="videos")
            return
        all_performers = self._load_performers()
        results = []

        if query:
            q_clean = query.strip().lower()
            for p in all_performers:
                name_match = q_clean in p.get("name", "").lower()
                alias_match = any(q_clean in a.lower() for a in p.get("aliases", []))
                tag_match = any(q_clean in t.lower() for t in p.get("tags", []))
                if name_match or alias_match or tag_match:
                    results.append(p)
            if not results:
                # Dynamic fallback entry for any searched performer!
                cap_name = query.strip().title()
                p_id = query.strip().lower().replace(" ", "_")
                thumb = f"https://www.babepedia.com/pics/{urllib.parse.quote(cap_name)}.jpg"
                results.append({
                    "id": p_id,
                    "name": cap_name,
                    "thumb": thumb,
                    "country": "Web",
                    "tags": ["search"],
                    "bio": f"Star-Hub & 24/7 Smart Stream für '{cap_name}'.",
                })
        elif letter:
            l_clean = letter.upper()
            for p in all_performers:
                first_char = p.get("name", "")[:1].upper()
                if l_clean == "#" and not first_char.isalpha():
                    results.append(p)
                elif first_char == l_clean:
                    results.append(p)
            results.sort(key=lambda x: x.get("name", "").lower())
        elif cat:
            for p in all_performers:
                tags = p.get("tags", [])
                gender = p.get("gender", "")
                if cat == "trending" and ("trending" in tags or p.get("rank", 999) <= 35):
                    results.append(p)
                elif cat == "hall_of_fame" and ("hall_of_fame" in tags or "legend" in tags):
                    results.append(p)
                elif cat == "female" and gender == "f":
                    results.append(p)
                elif cat == "male" and gender == "m":
                    results.append(p)
                elif cat == "trans" and (gender in ("t", "ts") or "trans" in tags):
                    results.append(p)
                elif cat == "jav" and ("jav" in tags or "asian" in tags):
                    results.append(p)
                elif cat == "milf" and "milf" in tags:
                    results.append(p)
                elif cat == "vintage" and ("vintage" in tags or "retro" in tags or "classic" in tags or "70s" in tags or "80s" in tags or "90s" in tags or str(p.get("decade", "")).startswith("vintage")):
                    results.append(p)
                elif cat == "european" and ("european" in tags or "euro" in tags or str(p.get("country", "")).lower() in ("czech republic", "czech", "germany", "france", "italy", "united kingdom", "uk", "england", "russia", "hungary", "spain", "poland", "sweden", "ukraine", "romania", "austria", "netherlands", "slovakia", "belgium", "switzerland", "portugal", "greece", "denmark", "norway", "finland", "ireland", "scotland", "croatia", "serbia", "bulgaria", "latvia", "lithuania", "estonia")):
                    results.append(p)
            results.sort(key=lambda x: x.get("rank", 999))

            # Merge live charts for trending
            if cat == "trending" and page == 1:
                live_stars = self._fetch_live_trending(page=1)
                existing_names = {p.get("name", "").lower() for p in results}
                for ls in live_stars:
                    if ls.get("name", "").lower() not in existing_names:
                        results.append(ls)
        else:
            results = list(all_performers)
            results.sort(key=lambda x: x.get("rank", 999))

        self._render_performer_list(results)

    def _render_performer_list(self, performers, title_context=None, finish=True):
        favorites = self._load_favorites()
        fav_ids = {f.get("id") for f in favorites if isinstance(f, dict)}
        fav_names = {
            self._name_key(f.get("name")) for f in favorites
            if isinstance(f, dict) and f.get("name")
        }

        if not performers:
            li = xbmcgui.ListItem(label=f"[COLOR red]{_text(30908, 'Keine Darsteller gefunden')}[/COLOR]")
            xbmcplugin.addDirectoryItem(self.addon_handle, "", li, isFolder=False)
            _end_dir(self.addon_handle, self.addon, content_type="videos")
            return

        for p in performers:
            p_id = str(p.get("id") or p.get("name") or "")
            p_name = str(p.get("name", "Unknown"))
            thumb = str(p.get("avatar") or p.get("thumb") or "")
            country = p.get("country", "")
            birth_year = p.get("birth_year", "")
            tags = p.get("tags", [])

            is_fav = (
                p_id in fav_ids
                or p.get("legacy_id") in fav_ids
                or self._name_key(p_name) in fav_names
            )
            fav_prefix = "[COLOR yellow]★ [/COLOR]" if is_fav else ""

            details = [str(country)] if country else []
            details.extend(str(tag) for tag in tags[:2] if tag)
            tag_str = f" [COLOR gray]({' • '.join(details)})[/COLOR]" if details else ""
            label = f"{fav_prefix}[COLOR gold][B]{p_name}[/B][/COLOR]{tag_str}"

            hub_url = f"{self.plugin_url}?mode=60&action=hub&id={urllib.parse.quote_plus(p_id)}&name={urllib.parse.quote_plus(p_name)}&thumb={urllib.parse.quote_plus(thumb)}"

            li = xbmcgui.ListItem(label=label)
            li.setArt({
                "icon": thumb or "DefaultActor.png",
                "thumb": thumb or "DefaultActor.png",
                "poster": thumb or "DefaultActor.png",
                "banner": thumb or "DefaultActor.png",
                "fanart": thumb or "DefaultActor.png",
            })

            plot_text = self._format_plot(p)
            li.setInfo("video", {
                "title": p_name,
                "plot": plot_text,
                "plotoutline": p.get("bio", f"Adult Performer: {p_name}"),
                "genre": ", ".join(tags),
                "year": int(birth_year) if birth_year and str(birth_year).isdigit() else 0,
            })

            # Context Menu Items
            fav_action = "remove_fav" if is_fav else "add_fav"
            fav_label = _text(30909, "Aus Favoriten entfernen") if is_fav else _text(30910, "Zu Favoriten hinzufügen")
            fav_cmd = f"RunPlugin({self.plugin_url}?mode=60&action={fav_action}&id={urllib.parse.quote_plus(p_id)}&name={urllib.parse.quote_plus(p_name)}&thumb={urllib.parse.quote_plus(thumb or '')})"

            stream_cmd = f"RunPlugin({self.plugin_url}?mode=50&action=custom_zap&query={urllib.parse.quote_plus(p_name)}&pool=top_tubes&length=any)"
            search_cmd = f"Container.Update({self.plugin_url}?mode=21&website=global_search&query={urllib.parse.quote_plus(p_name)})"
            bio_cmd = f"RunPlugin({self.plugin_url}?mode=60&action=bio&id={urllib.parse.quote_plus(p_id)})"

            context_menu = [
                (f"[ i ] {_text(30916, 'Biografie & Details')}", bio_cmd),
                (fav_label, fav_cmd),
                (f"★ {_text(30911, '24/7 Smart Stream starten')}", stream_cmd),
                (f"★ {_text(30912, 'Über alle 272 Webseiten suchen')}", search_cmd),
            ]
            li.addContextMenuItems(context_menu)

            xbmcplugin.addDirectoryItem(self.addon_handle, hub_url, li, isFolder=True)

        if finish:
            _end_dir(self.addon_handle, self.addon, content_type="videos")

    def show_favorites(self):
        favs = self._load_favorites()
        loaded = self._load_performers()
        all_performers = {p.get("id"): p for p in loaded}
        legacy_performers = {
            p.get("legacy_id"): p for p in loaded if p.get("legacy_id")
        }
        named_performers = {
            self._name_key(p.get("name")): p for p in loaded if p.get("name")
        }

        if not favs:
            li = xbmcgui.ListItem(label=f"[COLOR yellow]{_text(30913, 'Noch keine Favoriten gespeichert')}[/COLOR]")
            xbmcplugin.addDirectoryItem(self.addon_handle, "", li, isFolder=False)
            _end_dir(self.addon_handle, self.addon, content_type="videos")
            return

        for p_fav in favs:
            p_id = p_fav.get("id", "")
            p_name = p_fav.get("name", "Unknown")
            p = (
                all_performers.get(p_id)
                or legacy_performers.get(p_id)
                or named_performers.get(self._name_key(p_name))
                or p_fav
            )
            thumb = p.get("thumb") or p_fav.get("thumb", "")

            label = f"[COLOR yellow]★ [/COLOR][COLOR gold][B]{p_name}[/B][/COLOR]"
            hub_url = f"{self.plugin_url}?mode=60&action=hub&id={urllib.parse.quote_plus(p_id)}&name={urllib.parse.quote_plus(p_name)}&thumb={urllib.parse.quote_plus(thumb or '')}"

            li = xbmcgui.ListItem(label=label)
            li.setArt({
                "icon": thumb or "DefaultActor.png",
                "thumb": thumb or "DefaultActor.png",
                "poster": thumb or "DefaultActor.png",
                "banner": thumb or "DefaultActor.png",
                "fanart": thumb or "DefaultActor.png",
            })

            plot_text = self._format_plot(p)
            li.setInfo("video", {
                "title": p_name,
                "plot": plot_text,
                "plotoutline": p.get("bio", f"Adult Performer: {p_name}"),
            })

            fav_cmd = f"RunPlugin({self.plugin_url}?mode=60&action=remove_fav&id={urllib.parse.quote_plus(p_id)}&name={urllib.parse.quote_plus(p_name)})"
            stream_cmd = f"RunPlugin({self.plugin_url}?mode=50&action=custom_zap&query={urllib.parse.quote_plus(p_name)}&pool=top_tubes&length=any)"
            search_cmd = f"Container.Update({self.plugin_url}?mode=21&website=global_search&query={urllib.parse.quote_plus(p_name)})"
            bio_cmd = f"RunPlugin({self.plugin_url}?mode=60&action=bio&id={urllib.parse.quote_plus(p_id)})"

            context_menu = [
                (f"[ i ] {_text(30916, 'Biografie & Details')}", bio_cmd),
                (_text(30909, "Aus Favoriten entfernen"), fav_cmd),
                (f"★ {_text(30911, '24/7 Smart Stream starten')}", stream_cmd),
                (f"★ {_text(30912, 'Über alle 272 Webseiten suchen')}", search_cmd),
            ]
            li.addContextMenuItems(context_menu)

            xbmcplugin.addDirectoryItem(self.addon_handle, hub_url, li, isFolder=True)

        _end_dir(self.addon_handle, self.addon, content_type="videos")

    def search(self, query=None):
        if not query:
            kb = xbmc.Keyboard("", _text(30901, "Darsteller suchen..."))
            kb.doModal()
            if not kb.isConfirmed():
                return
            query = kb.getText()
        if not query or not query.strip():
            return
        self.browse(query=query.strip())

    def show_bio(self, performer_id):
        p = self._get_performer(performer_id)
        if not p:
            if xbmcgui:
                xbmcgui.Dialog().notification(_text(30900, "Darsteller & Pornstars"), "Keine Daten gefunden", xbmcgui.NOTIFICATION_WARNING)
            return

        p_name = p.get("name", "Unknown")
        bio_text = self._format_plot(p)

        if xbmcgui:
            xbmcgui.Dialog().textviewer(f"★ {p_name} — Biografie & Profil", bio_text)
        if xbmcplugin:
            xbmcplugin.endOfDirectory(self.addon_handle, succeeded=True, updateListing=False, cacheToDisc=False)

    def _detect_performer_genre(self, p):
        gender = str(p.get("gender", "")).lower()
        tags = [str(t).lower() for t in p.get("tags", [])]
        if gender in ("t", "ts") or "trans" in tags or "shemale" in tags:
            return "trans", "Trans & Shemale", "trans"
        if "jav" in tags or "asian" in tags or "japan" in tags:
            return "jav_asian", "JAV & Asian", "jav"
        if gender == "m" or "gay" in tags:
            return "gay", "Gay & Male", "gay"
        return "straight", "Top Tube", "top_tubes"

    def show_performer_hub(self, performer_id, performer_name, thumb=None):
        p = self._get_performer(performer_id) or {}
        if not thumb:
            thumb = p.get("thumb", "")

        favs = self._load_favorites()
        is_fav = any(
            f.get("id") in (performer_id, p.get("legacy_id"))
            or self._name_key(f.get("name")) == self._name_key(performer_name)
            for f in favs if isinstance(f, dict)
        )

        enc_name = urllib.parse.quote_plus(performer_name)
        enc_id = urllib.parse.quote_plus(performer_id)
        enc_thumb = urllib.parse.quote_plus(thumb or "")

        genre_key, genre_title, pool_key = self._detect_performer_genre(p)

        # 1. Bio & Profile Info
        bio_url = f"{self.plugin_url}?mode=60&action=bio&id={enc_id}"
        li_bio = xbmcgui.ListItem(label=f"[COLOR yellow][ i ][/COLOR] [B]{_text(30916, 'Biografie & Profil anzeigen')}[/B]")
        li_bio.setArt({"icon": thumb or "DefaultInfo.png", "thumb": thumb or "DefaultInfo.png", "poster": thumb or "DefaultInfo.png"})
        li_bio.setInfo("video", {"plot": self._format_plot(p)})
        xbmcplugin.addDirectoryItem(self.addon_handle, bio_url, li_bio, isFolder=False)

        # 2. Start 24/7 Smart Stream (Genre-pool aware!)
        stream_url = f"{self.plugin_url}?mode=50&action=custom_zap&query={enc_name}&pool={pool_key}&length=any"
        li_stream = xbmcgui.ListItem(label=f"[COLOR yellow]★ [/COLOR][COLOR gold][B]{_text(30911, '24/7 Smart Stream starten')} ({performer_name})[/B][/COLOR]")
        li_stream.setArt({"icon": thumb or "DefaultVideo.png", "thumb": thumb or "DefaultVideo.png", "poster": thumb or "DefaultVideo.png"})
        xbmcplugin.addDirectoryItem(self.addon_handle, stream_url, li_stream, isFolder=False)

        # 3. Multi-search across genre-specific network
        search_network_url = f"{self.plugin_url}?mode=21&website=global_search&query={enc_name}&search_mode={genre_key}"
        li_network = xbmcgui.ListItem(label=f"[COLOR cyan]★ [/COLOR][B]Search Videos & Clips ({genre_title} Network)[/B]")
        li_network.setArt({"icon": "DefaultAddonsSearch.png", "thumb": "DefaultAddonsSearch.png"})
        xbmcplugin.addDirectoryItem(self.addon_handle, search_network_url, li_network, isFolder=True)

        # 3b. Full Movies Multi-Search
        movie_search_mode = "full_movies_trans" if genre_key == "trans" else "full_movies"
        search_movies_url = f"{self.plugin_url}?mode=21&website=global_search&query={enc_name}&search_mode={movie_search_mode}"
        li_movies_search = xbmcgui.ListItem(label=f"[COLOR deepskyblue]★ [/COLOR][B]Search Full Movies ≥70 Min ({genre_title})[/B]")
        li_movies_search.setArt({"icon": "DefaultAddonsSearch.png", "thumb": "DefaultAddonsSearch.png"})
        xbmcplugin.addDirectoryItem(self.addon_handle, search_movies_url, li_movies_search, isFolder=True)

        movie_count = int(p.get("movie_count") or 0)
        if movie_count:
            movies_url = f"{self.plugin_url}?mode=60&action=movies&id={enc_id}&name={enc_name}"
            li_filmography = xbmcgui.ListItem(
                label=f"[COLOR orange]★ [/COLOR][B]Movies with {performer_name} ({movie_count})[/B]"
            )
            li_filmography.setArt({"icon": "DefaultVideo.png", "thumb": "DefaultVideo.png"})
            xbmcplugin.addDirectoryItem(self.addon_handle, movies_url, li_filmography, isFolder=True)

        # 4. Expand search across all other sites & custom filters
        expand_url = f"{self.plugin_url}?mode=20&website=global_search"
        li_expand = xbmcgui.ListItem(label=f"[COLOR lightblue]• [/COLOR][COLOR white]Search all websites and expand filters...[/COLOR]")
        li_expand.setArt({"icon": "DefaultAddonRepository.png", "thumb": "DefaultAddonRepository.png"})
        xbmcplugin.addDirectoryItem(self.addon_handle, expand_url, li_expand, isFolder=True)

        # 5. Favorite Toggle
        if is_fav:
            fav_label = f"[COLOR red]★ [/COLOR]{_text(30909, 'Aus Favoriten entfernen')}"
            fav_url = f"{self.plugin_url}?mode=60&action=remove_fav&id={enc_id}&name={enc_name}&thumb={enc_thumb}"
        else:
            fav_label = f"[COLOR lime]★ [/COLOR]{_text(30910, 'Zu Favoriten hinzufügen')}"
            fav_url = f"{self.plugin_url}?mode=60&action=add_fav&id={enc_id}&name={enc_name}&thumb={enc_thumb}"

        li_fav = xbmcgui.ListItem(label=fav_label)
        li_fav.setArt({"icon": "DefaultFavourites.png", "thumb": "DefaultFavourites.png"})
        xbmcplugin.addDirectoryItem(self.addon_handle, fav_url, li_fav, isFolder=False)

        _end_dir(self.addon_handle, self.addon, content_type="files")

    def show_movies(self, performer_id, performer_name):
        movies = self.star_db.movies(performer_id) if self.star_db and self.star_db.available else []
        performer = self.star_db.get(performer_id) if self.star_db and self.star_db.available else None
        movie_search_mode = "filmography_movies_trans" if performer and performer.get("gender") == "ts" else "filmography_movies"
        for movie in movies:
            title = movie.get("title", "")
            year = movie.get("release_year")
            minutes = int(movie.get("duration_seconds") or 0) // 60
            suffix = " · ".join(str(value) for value in (year, f"{minutes} min") if value)
            label = f"[B]{title}[/B] [COLOR gray]({suffix})[/COLOR]" if suffix else f"[B]{title}[/B]"
            url = (
                f"{self.plugin_url}?mode=21&website=global_search&"
                f"query={urllib.parse.quote_plus(title)}&search_mode={movie_search_mode}"
            )
            item = xbmcgui.ListItem(label=label)
            item.setArt({"icon": "DefaultVideo.png", "thumb": "DefaultVideo.png"})
            item.setInfo("video", {"title": title, "year": int(year or 0), "duration": int(movie.get("duration_seconds") or 0)})
            xbmcplugin.addDirectoryItem(self.addon_handle, url, item, isFolder=True)
        _end_dir(self.addon_handle, self.addon, content_type="videos")

    def add_favorite(self, performer_id, performer_name, thumb=None):
        favs = self._load_favorites()
        if not any(f.get("id") == performer_id for f in favs if isinstance(f, dict)):
            favs.append({
                "id": performer_id,
                "name": performer_name,
                "thumb": thumb or "",
                "added_at": int(time.time()),
            })
            self._save_favorites(favs)
            if xbmcgui:
                xbmcgui.Dialog().notification(
                    _text(30900, "Darsteller & Pornstars"),
                    f"'{performer_name}' {_text(30914, 'zu Favoriten hinzugefügt!')}",
                    xbmcgui.NOTIFICATION_INFO,
                    2000,
                )
        if xbmc:
            xbmc.executebuiltin("Container.Refresh")
        if xbmcplugin:
            xbmcplugin.endOfDirectory(self.addon_handle, succeeded=True, updateListing=False, cacheToDisc=False)

    def remove_favorite(self, performer_id, performer_name):
        favs = self._load_favorites()
        new_favs = [f for f in favs if isinstance(f, dict) and f.get("id") != performer_id]
        if len(new_favs) != len(favs):
            self._save_favorites(new_favs)
            if xbmcgui:
                xbmcgui.Dialog().notification(
                    _text(30900, "Darsteller & Pornstars"),
                    f"'{performer_name}' {_text(30915, 'aus Favoriten entfernt!')}",
                    xbmcgui.NOTIFICATION_INFO,
                    2000,
                )
        if xbmc:
            xbmc.executebuiltin("Container.Refresh")
        if xbmcplugin:
            xbmcplugin.endOfDirectory(self.addon_handle, succeeded=True, updateListing=False, cacheToDisc=False)

    def handle(self, action, params):
        if action in (None, "", "menu"):
            return self.show_main_menu()
        if action == "matrix":
            return self.show_matrix()
        if action == "matrix_select":
            self._do_matrix_select(params.get("field"))
            if xbmcplugin and self.addon_handle != -1:
                try:
                    xbmcplugin.endOfDirectory(self.addon_handle, succeeded=False, updateListing=False, cacheToDisc=False)
                except Exception:
                    pass
            if xbmc:
                xbmc.executebuiltin("Container.Refresh")
            return
        if action == "matrix_reset":
            self._do_matrix_reset()
            if xbmcplugin and self.addon_handle != -1:
                try:
                    xbmcplugin.endOfDirectory(self.addon_handle, succeeded=False, updateListing=False, cacheToDisc=False)
                except Exception:
                    pass
            if xbmc:
                xbmc.executebuiltin("Container.Refresh")
            return
        if action == "matrix_global_search":
            return self.matrix_global_search()
        if action == "show_matrix_results":
            return self.show_matrix_results()
        if action == "letters":
            return self.show_letters()
        if action == "categories":
            return self.show_categories()
        if action == "browse":
            try:
                page = int(params.get("page", "1") or "1")
            except Exception:
                page = 1
            return self.browse(
                cat=params.get("cat"),
                letter=params.get("letter"),
                query=params.get("query"),
                page=page,
            )
        if action == "search":
            return self.search(params.get("query"))
        if action == "favorites":
            return self.show_favorites()
        if action == "hub":
            return self.show_performer_hub(
                params.get("id", ""),
                params.get("name", "Unknown"),
                params.get("thumb"),
            )
        if action == "bio":
            return self.show_bio(params.get("id", ""))
        if action == "movies":
            return self.show_movies(params.get("id", ""), params.get("name", "Unknown"))
        if action == "add_fav":
            return self.add_favorite(
                params.get("id", ""),
                params.get("name", "Unknown"),
                params.get("thumb"),
            )
        if action == "remove_fav":
            return self.remove_favorite(
                params.get("id", ""),
                params.get("name", "Unknown"),
            )
        return self.show_main_menu()
