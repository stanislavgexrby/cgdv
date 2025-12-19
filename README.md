# TeammateBot

Telegram-бот для поиска тимейтов в Dota 2 и CS2 с системой лайков и матчей.

## Быстрый старт

### Docker (рекомендуется для production)

```bash
# 1. Клонировать репозиторий
git clone <repo-url> cgdv && cd cgdv

# 2. Настроить окружение
cp .env.example .env
nano .env  # Укажите BOT_TOKEN, ADMIN_ID и другие параметры

# 3. Запустить все сервисы
docker compose up -d

# 4. Проверить логи
docker compose logs -f bot
```

Подробная документация по развертыванию: [DEPLOYMENT.md](DEPLOYMENT.md)

### Локальная разработка

```bash
# 1. Установить зависимости
pip install -r requirements.txt

# 2. Настроить .env
cp .env.example .env
nano .env

# 3. Запустить PostgreSQL и Redis
docker compose up -d postgres redis

# 4. Запустить бота
python main.py
```

## Технологии

- **Python 3.13**
- **Aiogram 3.21** - асинхронный фреймворк для Telegram ботов
- **PostgreSQL 15** - основная база данных
- **Redis 7** - кэширование
- **Docker & Docker Compose** - контейнеризация

## Основные возможности

- Создание игровых профилей (Dota 2 / CS2)
- Поиск игроков по фильтрам (ранг, позиция, регион)
- Система лайков и мэтчей
- Уведомления о новых совпадениях
- Рекламные посты с автоудалением
- Система репортов и банов
- Подписка на каналы

## Структура

```
cgdv/
├── handlers/       # Обработчики команд и колбэков
├── database/       # Работа с PostgreSQL и Redis
├── keyboards/      # Telegram клавиатуры
├── middleware/     # Middleware (БД, восстановление состояния)
├── config/         # Настройки игр и регионов
├── utils/          # Вспомогательные функции
└── main.py         # Точка входа
```

## Документация

- [DEPLOYMENT.md](DEPLOYMENT.md) - Полное руководство по развертыванию
- [CLAUDE.md](CLAUDE.md) - Техническая документация для разработки

## Лицензия

Проприетарный проект
