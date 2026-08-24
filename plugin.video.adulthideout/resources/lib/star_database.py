# -*- coding: utf-8 -*-
"""Compact local performer index with on-demand remote movie shards."""

import gzip
import hashlib
import json
import os


def _json_list(value):
    if not value:
        return []
    try:
        result = json.loads(value)
        return result if isinstance(result, list) else []
    except (TypeError, ValueError):
        return []


class StarDatabase:
    def __init__(self, addon_path):
        data_dir = os.path.join(addon_path, "resources", "data")
        self.path = os.path.join(data_dir, "star_index.json.gz")
        self.movies_dir = os.path.join(data_dir, "star_movies")
        self.manifest_path = os.path.join(data_dir, "star_movies_manifest.json")
        self._performers = None
        self._by_id = None
        self._manifest = None
        self._movie_shards = {}

    @property
    def available(self):
        return os.path.isfile(self.path)

    def _load_index(self):
        if self._performers is None:
            with gzip.open(self.path, "rt", encoding="utf-8") as source:
                payload = json.load(source)
            rows = payload.get("performers", []) if isinstance(payload, dict) else []
            self._performers = [row for row in rows if isinstance(row, dict)]
            self._by_id = {str(row.get("id")): row for row in self._performers if row.get("id")}
        return self._performers

    def _load_manifest(self):
        if self._manifest is None:
            try:
                with open(self.manifest_path, "r", encoding="utf-8") as source:
                    self._manifest = json.load(source)
            except (OSError, TypeError, ValueError):
                self._manifest = {"shards": {}}
        return self._manifest

    def _movie_shard(self, performer_id):
        manifest = self._load_manifest()
        prefix_length = int(manifest.get("shard_prefix_length") or 1)
        shard_id = hashlib.sha256(str(performer_id).encode("utf-8")).hexdigest()[:prefix_length]
        if shard_id in self._movie_shards:
            return self._movie_shards[shard_id]
        metadata = manifest.get("shards", {}).get(shard_id, {})
        expected = str(metadata.get("sha256") or "").lower()
        if not expected:
            return {}
        path = os.path.join(self.movies_dir, "{}.json.gz".format(shard_id))
        try:
            with open(path, "rb") as source:
                compressed = source.read()
            if hashlib.sha256(compressed).hexdigest().lower() != expected:
                return {}
            payload = json.loads(gzip.decompress(compressed).decode("utf-8"))
            shard = payload.get("performers", {}) if isinstance(payload, dict) else {}
        except Exception:
            return {}
        self._movie_shards[shard_id] = shard
        return shard

    def count(self):
        return len(self._load_index()) if self.available else 0

    def get(self, performer_id):
        if not self.available:
            return None
        self._load_index()
        row = self._by_id.get(str(performer_id))
        return dict(row) if row else None

    def list(self, query=None, letter=None, offset=0, limit=100):
        if not self.available:
            return [], 0
        rows = self._load_index()
        if query:
            term = query.strip().casefold()
            rows = [row for row in rows if term in str(row.get("name") or "").casefold()
                    or any(term in str(alias).casefold() for alias in row.get("aliases", []))]
        if letter:
            if letter == "#":
                rows = [row for row in rows if not str(row.get("name") or "")[:1].upper().isalpha()]
            else:
                rows = [row for row in rows if str(row.get("name") or "")[:1].upper() == letter.upper()]
            rows = sorted(rows, key=lambda row: str(row.get("name") or "").casefold())
        else:
            rows = sorted(rows, key=lambda row: int(row.get("rank") or 999999))
        total = len(rows)
        return [dict(row) for row in rows[offset:offset + limit]], total

    def movies(self, performer_id):
        if not self.available:
            return []
        shard = self._movie_shard(performer_id)
        rows = shard.get(str(performer_id), [])
        return [
            {"title": row[0], "release_year": row[1] or 0, "duration_seconds": row[2] or 0}
            for row in rows
            if isinstance(row, list) and len(row) >= 3
        ]
