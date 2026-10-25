from pathlib import Path


CONFIG_PATH = Path(__file__).resolve().parents[2] / ".library_media_root"


def get_media_root():
    try:
        configured = CONFIG_PATH.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return Path(configured).expanduser().resolve() if configured else None

