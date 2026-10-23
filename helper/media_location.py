"""Resolve the local media library directory chosen in the import page."""

from pathlib import Path
import os


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = Path(os.environ.get("YOURTUBE_DATA_DIR", PROJECT_ROOT)).resolve()
DEFAULT_MEDIA_ROOT = Path(os.environ.get("YOURTUBE_MEDIA_ROOT", DATA_ROOT / "media")).resolve()
CONFIG_PATH = DATA_ROOT / ".library_media_root"


def get_media_root():
    try:
        configured = CONFIG_PATH.read_text(encoding="utf-8").strip()
    except OSError:
        configured = ""
    return Path(configured).expanduser().resolve() if configured else DEFAULT_MEDIA_ROOT.resolve()


def set_media_root(path):
    resolved = Path(path).expanduser().resolve()
    CONFIG_PATH.write_text(str(resolved), encoding="utf-8")
    return resolved

