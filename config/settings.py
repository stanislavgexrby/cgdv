import os
import json
import logging

from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(), override=True)

logger = logging.getLogger(__name__)

def _parse_admin_ids(raw: str) -> set[int]:
    ids = set()
    for chunk in (raw or "").replace(" ", "").split(","):
        if not chunk:
            continue
        try:
            ids.add(int(chunk))
        except ValueError:
            pass
    return ids

ADMIN_IDS: set[int] = _parse_admin_ids(os.getenv("ADMIN_ID", ""))

def is_admin(user_id: int) -> bool:
    return int(user_id) in ADMIN_IDS

BOT_TOKEN = os.getenv("BOT_TOKEN", "")

admin_id_str = os.getenv("ADMIN_ID", "0")
try:
    if admin_id_str and admin_id_str.isdigit():
        ADMIN_ID = int(admin_id_str)
    else:
        ADMIN_ID = 0
except (ValueError, TypeError):
    ADMIN_ID = 0

ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'assets')
PHOTO_CACHE_FILE = os.path.join(ASSETS_DIR, 'photo_cache.json')

MENU_PHOTOS = {
    'default': os.path.join(ASSETS_DIR, 'main_menu.png'),
    'dota': os.path.join(ASSETS_DIR, 'dota2.png'),
    'cs': os.path.join(ASSETS_DIR, 'cs2.png')
}

def load_photo_cache():
    """Загрузить кеш file_id из файла"""
    try:
        if os.path.exists(PHOTO_CACHE_FILE):
            with open(PHOTO_CACHE_FILE, 'r') as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def save_photo_cache(cache):
    """Сохранить кеш file_id в файл"""
    try:
        os.makedirs(ASSETS_DIR, exist_ok=True)
        with open(PHOTO_CACHE_FILE, 'w') as f:
            json.dump(cache, f)
    except Exception as e:
        logger.warning(f"Ошибка сохранения кеша фото: {e}")

_photo_cache = load_photo_cache()

def get_cached_photo_id(photo_key: str) -> str:
    """Получить кешированный file_id"""
    return _photo_cache.get(photo_key)

def cache_photo_id(photo_key: str, file_id: str):
    """Кешировать file_id"""
    _photo_cache[photo_key] = file_id
    save_photo_cache(_photo_cache)

DOTA_CHANNEL = os.getenv("DOTA_CHANNEL", "@testbotasdasd")
CS_CHANNEL = os.getenv("CS_CHANNEL", "@test89898922")
CHECK_SUBSCRIPTION = os.getenv("CHECK_SUBSCRIPTION", "true").lower() == "true"

DATABASE_PATH = os.getenv("DATABASE_PATH", "data/teammates.db")

MAX_NAME_LENGTH = 50
MAX_NICKNAME_LENGTH = 30
MAX_INFO_LENGTH = 500
MIN_AGE = 0
MAX_AGE = 100

GAMES = {
    "dota": "Dota 2",
    "cs": "CS2"
}

RATINGS = {
    "dota": {
        "herald": "Herald (0-770)",
        "guardian": "Guardian (770-1540)", 
        "crusader": "Crusader (1540-2310)",
        "archon": "Archon (2310-3080)",
        "legend": "Legend (3080-3850)",
        "ancient": "Ancient (3850-4620)",
        "divine": "Divine (4620-5620)",
        "immortal1": "Immortal (5620-7000)",
        "immortal2": "Immortal (7000-9000)",
        "immortal3": "Immortal (9000-11000)",
        "immortal4": "Immortal (11000+)"
    },
    "cs": {
        "1": "FACEIT Level 1 (100-500)",
        "2": "FACEIT Level 2 (501-750)",
        "3": "FACEIT Level 3 (751-900)",
        "4": "FACEIT Level 4 (901-1050)",
        "5": "FACEIT Level 5 (1051-1200)",
        "6": "FACEIT Level 6 (1201-1350)",
        "7": "FACEIT Level 7 (1351-1530)",
        "8": "FACEIT Level 8 (1531-1750)",
        "9": "FACEIT Level 9 (1751-2000)",
        "10": "FACEIT Level 10 (2001-2400)",
        "10_plus": "FACEIT Level 10 (2401-2800)",
        "10_advanced": "FACEIT Level 10 (2801-3200)",
        "10_elite": "FACEIT Level 10 (3201-3500)",
        "pro": "FACEIT Level 10 (3500+)"
    }
}

POSITIONS = {
    "dota": {
        "pos1": "Carry",
        "pos2": "Midlaner", 
        "pos3": "Offlaner",
        "pos4": "Soft-Support",
        "pos5": "Hard-Support"
    },
    "cs": {
        "support": "Support",
        "sniper": "Sniper", 
        "lurker": "Lurker",
        "entry": "Entry-Fragger",
        "igl": "IGL"
    }
}

REGIONS = {
    "eeu": "Восточная Европа (EEU)",
    "weu": "Западная Европа (WEU)",
    "asia": "Азия (Asia)"
}

GOALS = {
    "publics": "Паблики",
    "tournaments": "Турниры",
    "communication": "Общение",
}

MAIN_MENU_PHOTO_DOTA = ""
MAIN_MENU_PHOTO_CS = ""
MAIN_MENU_PHOTO_DEFAULT = ""

def get_main_menu_photo(game: str = None) -> str:
    """Получить фото для главного меню в зависимости от игры"""
    if game == "dota":
        return MAIN_MENU_PHOTO_DOTA
    elif game == "cs":
        return MAIN_MENU_PHOTO_CS
    else:
        return MAIN_MENU_PHOTO_DEFAULT