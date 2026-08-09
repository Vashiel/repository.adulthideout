# -*- coding: utf-8 -*-
import json
import os
import xbmc
import xbmcaddon
import xbmcvfs


class CustomCollectionsManager:
    DEFAULT_COLLECTIONS = []

    def __init__(self, addon=None):
        if addon is None:
            self.addon = xbmcaddon.Addon()
        else:
            self.addon = addon
            
        profile_path = xbmcvfs.translatePath(self.addon.getAddonInfo("profile"))
        if not os.path.exists(profile_path):
            os.makedirs(profile_path, exist_ok=True)
            
        self.file_path = os.path.join(profile_path, "custom_collections.json")
        self._ensure_file()

    def _ensure_file(self):
        if not os.path.exists(self.file_path):
            initial_data = {
                "collections": {
                    col: [] for col in self.DEFAULT_COLLECTIONS
                }
            }
            self._save_data(initial_data)

    def _load_data(self):
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if "collections" not in data:
                    data = {"collections": {col: [] for col in self.DEFAULT_COLLECTIONS}}
                collections = data.get("collections", {})
                changed = False
                if "Meine Top Sites" in collections:
                    legacy_sites = collections.pop("Meine Top Sites")
                    current_sites = collections.setdefault("My Top Sites", [])
                    for site_id in legacy_sites:
                        if site_id not in current_sites:
                            current_sites.append(site_id)
                    changed = True
                for seeded_name in ("Favorites", "My Top Sites", "JAV", "Trans"):
                    if seeded_name in collections and not collections[seeded_name]:
                        collections.pop(seeded_name)
                        changed = True
                if changed:
                    self._save_data(data)
                return data
        except Exception as exc:
            xbmc.log(f"[CustomCollectionsManager] Error loading collections: {exc}", xbmc.LOGERROR)
            return {"collections": {col: [] for col in self.DEFAULT_COLLECTIONS}}

    def _save_data(self, data):
        temp_path = self.file_path + ".tmp"
        try:
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            os.replace(temp_path, self.file_path)
        except Exception as exc:
            xbmc.log(f"[CustomCollectionsManager] Error saving collections: {exc}", xbmc.LOGERROR)
            try:
                os.remove(temp_path)
            except OSError:
                pass

    def get_collections(self):
        data = self._load_data()
        return data.get("collections", {})

    def get_collection_names(self):
        collections = self.get_collections()
        return list(collections.keys())

    def get_collection_sites(self, name):
        collections = self.get_collections()
        return collections.get(name, [])

    def create_collection(self, name):
        name = name.strip()
        if not name:
            return False, "empty"
        data = self._load_data()
        collections = data.get("collections", {})
        if name in collections:
            return False, "exists"
        collections[name] = []
        data["collections"] = collections
        self._save_data(data)
        return True, "created"

    def delete_collection(self, name):
        data = self._load_data()
        collections = data.get("collections", {})
        if name not in collections:
            return False, "missing"
        del collections[name]
        data["collections"] = collections
        self._save_data(data)
        return True, "deleted"

    def add_site(self, collection_name, site_id):
        data = self._load_data()
        collections = data.get("collections", {})
        if collection_name not in collections:
            collections[collection_name] = []
        if site_id not in collections[collection_name]:
            collections[collection_name].append(site_id)
            data["collections"] = collections
            self._save_data(data)
            return True, "added"
        return True, "exists"

    def remove_site(self, collection_name, site_id):
        data = self._load_data()
        collections = data.get("collections", {})
        if collection_name in collections and site_id in collections[collection_name]:
            collections[collection_name].remove(site_id)
            data["collections"] = collections
            self._save_data(data)
            return True, "removed"
        return False, "missing"
