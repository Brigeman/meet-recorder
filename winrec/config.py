import json
import logging
import os
APP_NAME = "Desktop Meeting Recorder"
APP_ID = "winrec"
LEGACY_APP_NAME = "Ghost Meet Recorder"

CONFIG_DIR = os.path.join(os.environ.get("APPDATA", ""), APP_NAME)
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
LEGACY_CONFIG_DIR = os.path.join(os.environ.get("APPDATA", ""), LEGACY_APP_NAME)
LEGACY_SETTINGS = os.path.join(LEGACY_CONFIG_DIR, "settings.json")
LOCK_FILE = os.path.join(CONFIG_DIR, "winrec.lock")

DEFAULT_RECORDINGS_DIR = os.path.join(
    os.path.expanduser("~"), "Documents", "Desktop Meeting Recordings"
)

AUDIO_FORMATS = ["wav", "mp3", "flac", "ogg", "m4a", "opus", "aac", "wma"]
BROWSER_PROCESSES = {"chrome.exe", "msedge.exe", "firefox.exe", "brave.exe", "opera.exe"}
POLL_INTERVAL = 1.5

DEFAULTS = {
    "prompt_threshold": 70,
    "web_sustain_seconds": 2.5,
    "desktop_sustain_seconds": 7.0,
    "dismiss_cooldown_seconds": 90,
    "post_stop_cooldown_seconds": 120,
    "enable_experimental_uia": False,
    "recordings_dir": DEFAULT_RECORDINGS_DIR,
    "audio_format": "wav",
    "filename_prefix": "meeting",
    "notifications": True,
    "supported_apps": {
        "teams": True,
        "zoom": True,
        "slack": True,
        "discord": True,
        "telegram": True,
        "whatsapp": True,
        "browser_meetings": True,
    },
}


def _migrate_legacy():
    if not os.path.exists(LEGACY_SETTINGS):
        return
    if os.path.exists(CONFIG_FILE):
        return
    try:
        with open(LEGACY_SETTINGS, encoding="utf-8") as f:
            old = json.load(f)
        merged = dict(DEFAULTS)
        if "recordings_dir" in old:
            merged["recordings_dir"] = old["recordings_dir"]
        if "audio_format" in old:
            merged["audio_format"] = old["audio_format"]
        if "filename_prefix" in old:
            merged["filename_prefix"] = old.get("filename_prefix", "meet")
        if "notifications" in old:
            merged["notifications"] = old["notifications"]
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(merged, f, indent=2)
        log = logging.getLogger(__name__)
        log.info("Migrated settings from legacy Ghost Meet Recorder")
    except OSError:
        pass


def load_config() -> dict:
    os.makedirs(CONFIG_DIR, exist_ok=True)
    _migrate_legacy()
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, encoding="utf-8") as f:
            saved = json.load(f)
        merged = {**DEFAULTS, **saved}
        merged["supported_apps"] = {
            **DEFAULTS["supported_apps"],
            **saved.get("supported_apps", {}),
        }
        return merged
    cfg = dict(DEFAULTS)
    save_config(cfg)
    return cfg


def save_config(config: dict) -> None:
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.StreamHandler()],
    )
