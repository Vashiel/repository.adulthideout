# -*- coding: utf-8 -*-
"""One way to save user data: a crash mid-write must never leave a half-written file."""

import json
import os
import threading


def write_json_atomic(path, value, **dump_options):
    options = {"ensure_ascii": False}
    options.update(dump_options)
    # Per-thread temp name: two threads saving the same file must not share one temp file.
    temporary = "{}.{}.tmp".format(path, threading.get_ident())
    try:
        with open(temporary, "w", encoding="utf-8") as handle:
            json.dump(value, handle, **options)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.remove(temporary)
