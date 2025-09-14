import os

from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(), override=True)

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

DOTA_CHANNEL = os.getenv("DOTA_CHANNEL", "@testbotasdasd")
CS_CHANNEL = os.getenv("CS_CHANNEL", "@test89898922")
CHECK_SUBSCRIPTION = os.getenv("CHECK_SUBSCRIPTION", "true").lower() == "true"

DATABASE_PATH = os.getenv("DATABASE_PATH", "data/teammates.db")

MAX_NAME_LENGTH = 50
MAX_NICKNAME_LENGTH = 30
MAX_INFO_LENGTH = 500
MIN_AGE = 0

GAMES = {
    "dota": "🎮 Dota 2",
    "cs": "🔫 CS2"
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
        "1": "FACEIT Уровень 1 (100-500)",
        "2": "FACEIT Уровень 2 (501-750)",
        "3": "FACEIT Уровень 3 (751-900)",
        "4": "FACEIT Уровень 4 (901-1050)",
        "5": "FACEIT Уровень 5 (1051-1200)",
        "6": "FACEIT Уровень 6 (1201-1350)",
        "7": "FACEIT Уровень 7 (1351-1530)",
        "8": "FACEIT Уровень 8 (1531-1750)",
        "9": "FACEIT Уровень 9 (1751-2000)",
        "10": "FACEIT Уровень 10 (2001-2400)",
        "10_plus": "FACEIT Уровень 10 (2401-2800)",
        "10_advanced": "FACEIT Уровень 10 (2801-3200)",
        "10_elite": "FACEIT Уровень 10 (3201-3500)",
        "pro": "FACEIT Уровень 10 (3500+)"
    }
}

POSITIONS = {
    "dota": {
        "pos1": "Керри (1 позиция)",
        "pos2": "Мидер (2 позиция)",
        "pos3": "Оффлейнер (3 позиция)",
        "pos4": "Софт саппорт (4 позиция)",
        "pos5": "Хард саппорт (5 позиция)"
    },
    "cs": {
        "rifler": "Райфлер",
        "awper": "AWP-ер",
        "support": "Саппорт",
        "entry": "Штурмовик",
        "igl": "Лидер команды"
    }
}

REGIONS = {
    "eeu": "Восточная Европа",
    "weu": "Западная Европа",
    "asia": "Азия"
}