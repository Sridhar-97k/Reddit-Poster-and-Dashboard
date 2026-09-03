import os
import sys

_APP_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(_APP_DIR)

if getattr(sys, 'frozen', False):
    # Running as a PyInstaller bundle:
    #  - persistent data (config, logs) lives next to the .exe
    #  - bundled read-only assets live in the temp extraction dir (_MEIPASS)
    DATA_DIR = os.path.join(os.path.dirname(sys.executable), 'data')
    _RESOURCE_ROOT = getattr(sys, '_MEIPASS', ROOT_DIR)
else:
    DATA_DIR = os.path.join(ROOT_DIR, 'data')
    _RESOURCE_ROOT = ROOT_DIR

ASSETS_DIR = os.path.join(_RESOURCE_ROOT, 'assets')
ICON_PATH = os.path.join(ASSETS_DIR, 'icon.png')

os.makedirs(DATA_DIR, exist_ok=True)
