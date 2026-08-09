"""Build current AdultHideout repository metadata and release packages."""

import hashlib
import os
import shutil
import zipfile
import xml.etree.ElementTree as ET


ROOT = os.path.abspath(os.path.dirname(__file__))
ZIPS_ROOT = os.path.join(ROOT, "zips")
ADDON_PREFIXES = ("plugin.", "repository.", "script.")
SKIP_DIRS = {".git", "__pycache__"}


def addon_directories():
    entries = []
    for name in sorted(os.listdir(ROOT)):
        path = os.path.join(ROOT, name)
        manifest = os.path.join(path, "addon.xml")
        if name.startswith(ADDON_PREFIXES) and os.path.isdir(path) and os.path.isfile(manifest):
            entries.append((name, path, manifest))
    return entries


def generate_addons_xml(entries):
    lines = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>', "<addons>"]
    for _name, _path, manifest in entries:
        content = open(manifest, "r", encoding="utf-8-sig").read().splitlines()
        lines.extend(line.rstrip() for line in content if "<?xml" not in line)
        lines.append("")
    lines.append("</addons>")
    data = ("\n".join(lines).rstrip() + "\n").encode("utf-8")
    with open(os.path.join(ROOT, "addons.xml"), "wb") as handle:
        handle.write(data)
    with open(os.path.join(ROOT, "addons.xml.md5"), "w", encoding="ascii", newline="\n") as handle:
        handle.write(hashlib.md5(data).hexdigest())


def clean_package_directory(path):
    if os.path.isdir(path):
        shutil.rmtree(path)
    os.makedirs(path)


def zip_addon(addon_id, source, version, destination):
    archive = os.path.join(destination, "{}-{}.zip".format(addon_id, version))
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, allowZip64=True) as bundle:
        for base, dirs, files in os.walk(source):
            dirs[:] = sorted(directory for directory in dirs if directory not in SKIP_DIRS)
            for filename in sorted(files):
                if filename.endswith((".pyc", ".pyo")):
                    continue
                path = os.path.join(base, filename)
                relative = os.path.relpath(path, source).replace(os.sep, "/")
                bundle.write(path, "{}/{}".format(addon_id, relative))
    return archive


def copy_if_present(source, destination, target_name=None):
    if os.path.isfile(source):
        shutil.copy2(source, os.path.join(destination, target_name or os.path.basename(source)))


def package_addon(addon_id, source, manifest):
    version = ET.parse(manifest).getroot().attrib["version"]
    destination = os.path.join(ZIPS_ROOT, addon_id)
    clean_package_directory(destination)
    archive = zip_addon(addon_id, source, version, destination)

    changelog = os.path.join(source, "changelog.txt")
    copy_if_present(changelog, destination)
    copy_if_present(changelog, destination, "changelog-{}.txt".format(version))

    artwork_locations = (
        source,
        os.path.join(source, "resources"),
        os.path.join(source, "resources", "logos"),
    )
    for artwork in ("icon.png", "fanart.jpg"):
        for location in artwork_locations:
            candidate = os.path.join(location, artwork)
            if os.path.isfile(candidate):
                copy_if_present(candidate, destination, artwork)
                break

    if addon_id == "repository.adulthideout":
        for filename in os.listdir(ROOT):
            if filename.startswith("repository.adulthideout-") and filename.endswith(".zip"):
                os.remove(os.path.join(ROOT, filename))
        shutil.copy2(archive, os.path.join(ROOT, os.path.basename(archive)))

    return version, archive


def main():
    entries = addon_directories()
    os.makedirs(ZIPS_ROOT, exist_ok=True)
    generate_addons_xml(entries)
    for addon_id, source, manifest in entries:
        version, archive = package_addon(addon_id, source, manifest)
        print("{} {} -> {}".format(addon_id, version, os.path.relpath(archive, ROOT)))
    print("Generated addons.xml, checksum and {} current packages.".format(len(entries)))


if __name__ == "__main__":
    main()
