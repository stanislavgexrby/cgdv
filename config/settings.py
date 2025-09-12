import os

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0")) if os.getenv("ADMIN_ID", "").isdigit() else 0

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
        "divine": "Divine (4620-5420)",
        "immortal": "Immortal (5420+)"
    },
    "cs": {
        "1": "Уровень 1",
        "2": "Уровень 2",
        "3": "Уровень 3",
        "4": "Уровень 4",
        "5": "Уровень 5",
        "6": "Уровень 6",
        "7": "Уровень 7",
        "8": "Уровень 8",
        "9": "Уровень 9",
        "10": "Уровень 10"
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