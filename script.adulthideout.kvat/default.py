import importlib.util
import os
import sys


ADDON_ROOT = os.path.abspath(os.path.dirname(__file__))
LIB_DIR = os.path.join(ADDON_ROOT, "resources", "lib")


def _load_module(name, filename):
    spec = importlib.util.spec_from_file_location(name, os.path.join(LIB_DIR, filename))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_load_module("adulthideout_kvat_core", "core.py")
main = _load_module("adulthideout_kvat_app", "app.py").main


if __name__ == "__main__":
    main(sys.argv[1:])
