# Развертывание TeammateBot на сервере

Полное руководство по развертыванию Telegram-бота на сервере с использованием Docker.

## Требования

- Docker Engine 20.10+
- Docker Compose 2.0+
- Git
- Минимум 1GB RAM
- Минимум 10GB дискового пространства

## Быстрый старт

### 1. Клонирование репозитория

```bash
git clone <repository-url> cgdv
cd cgdv
```

### 2. Настройка переменных окружения

Скопируйте пример конфигурации и отредактируйте его:

```bash
cp .env.example .env
nano .env  # или используйте другой редактор
```

**Обязательные параметры для изменения:**

```env
BOT_TOKEN=your_bot_token_here          # Токен от @BotFather
ADMIN_ID=your_telegram_id              # Ваш Telegram ID
DOTA_CHANNEL_ID=@your_dota_channel     # Канал для Dota 2
CS_CHANNEL_ID=@your_cs_channel         # Канал для CS2
DB_PASSWORD=your_secure_password       # Надежный пароль для PostgreSQL
```

**ВАЖНО для Docker:**
- `DB_HOST` и `REDIS_HOST` автоматически переопределяются в docker-compose.yml
- Не нужно менять хосты в .env файле - это сделает docker-compose

### 3. Запуск

```bash
# Запуск всех сервисов (PostgreSQL, Redis, Bot)
docker compose up -d

# Проверка статуса
docker compose ps

# Просмотр логов
docker compose logs -f bot
```

### 4. Проверка работы

Бот автоматически:
- Дождется готовности PostgreSQL и Redis
- Подключится к базе данных
- Создаст необходимые таблицы (если их нет)
- Отправит уведомление админу о запуске
- Начнет обработку сообщений

**Примечание:** Миграции (migrate*.py) запускаются вручную при необходимости

## Команды управления

### Основные команды

```bash
# Запуск
docker compose up -d

# Остановка
docker compose down

# Перезапуск
docker compose restart

# Остановка с удалением данных (ОСТОРОЖНО!)
docker compose down -v

# Просмотр логов
docker compose logs -f bot              # Только бот
docker compose logs -f postgres         # База данных
docker compose logs -f                  # Все сервисы

# Проверка статуса
docker compose ps
```

### Обновление бота

```bash
# Получить последние изменения
git pull

# Пересобрать и перезапустить
docker compose up -d --build

# Или поэтапно
docker compose build bot
docker compose restart bot
```

### Резервное копирование

#### Бэкап базы данных

```bash
# Создать бэкап
docker compose exec postgres pg_dump -U teammates_user teammates > backup_$(date +%Y%m%d_%H%M%S).sql

# Восстановить из бэкапа
docker compose exec -T postgres psql -U teammates_user teammates < backup_20241219_120000.sql
```

#### Бэкап Redis (опционально)

```bash
# Создать snapshot
docker compose exec redis redis-cli SAVE

# Скопировать dump.rdb
docker cp teammates_redis:/data/dump.rdb ./redis_backup_$(date +%Y%m%d_%H%M%S).rdb
```

## Структура проекта

```
cgdv/
├── Dockerfile              # Образ бота
├── docker-compose.yml      # Оркестрация сервисов
├── init-db.sh             # Скрипт инициализации БД
├── .env                   # Конфигурация (НЕ коммитить!)
├── .env.example           # Пример конфигурации
├── .dockerignore          # Игнорируемые файлы
├── main.py                # Точка входа
├── requirements.txt       # Python зависимости
├── migrate*.py            # Скрипты миграций
├── logs/                  # Логи (монтируется как volume)
├── assets/                # Ресурсы (монтируется как volume)
├── config/                # Настройки
├── database/              # Работа с БД
├── handlers/              # Обработчики
├── keyboards/             # Клавиатуры
├── middleware/            # Middleware
└── utils/                 # Утилиты
```

## Docker-сервисы

### PostgreSQL
- **Образ:** postgres:16-alpine
- **Порт:** 5432
- **База:** teammates
- **Пользователь:** teammates_user
- **Volume:** postgres_data (постоянное хранение)
- **Healthcheck:** автоматическая проверка готовности

### Redis
- **Образ:** redis:7-alpine
- **Порт:** 6379
- **Режим:** appendonly (персистентность)
- **Volume:** redis_data (постоянное хранение)
- **Healthcheck:** автоматическая проверка готовности

### Bot
- **Образ:** собирается из Dockerfile (Python 3.13-slim)
- **Зависимости:** PostgreSQL, Redis (с healthcheck)
- **Инициализация:** через init-db.sh (ожидание готовности БД)
- **Volumes:**
  - `./logs:/app/logs` - логи бота
  - `./assets:/app/assets` - ресурсы
- **Restart:** unless-stopped (автоперезапуск)

## Логирование

Логи доступны в папке `./logs/`:

- **bot.log** - основной лог (ротация: 10MB, 5 файлов)
- **errors.log** - только ошибки (ротация: 5MB, 3 файла)
- **daily.log** - детальный debug (если DEBUG=true, 7 дней)

```bash
# Просмотр логов в реальном времени
tail -f logs/bot.log

# Просмотр только ошибок
tail -f logs/errors.log

# Логи через Docker
docker compose logs -f bot
```

## Мониторинг

### Проверка здоровья сервисов

```bash
# Статус всех контейнеров
docker compose ps

# Проверка PostgreSQL
docker compose exec postgres pg_isready -U teammates_user

# Проверка Redis
docker compose exec redis redis-cli ping

# Проверка бота (должен быть в логах "CGDV TeammateBot успешно запущен")
docker compose logs bot | grep "успешно запущен"
```

### Использование ресурсов

```bash
# Статистика контейнеров
docker stats teammates_bot teammates_postgres teammates_redis

# Размер volumes
docker system df -v
```

## Безопасность

### Рекомендации

1. **Измените пароли:**
   ```bash
   # Используйте надежный пароль для PostgreSQL
   DB_PASSWORD=$(openssl rand -base64 32)
   ```

2. **Ограничьте доступ:**
   ```bash
   # Если бот на сервере, закройте порты БД от внешнего мира
   # Отредактируйте docker-compose.yml, удалив секцию ports для postgres и redis
   ```

3. **Регулярные обновления:**
   ```bash
   # Обновляйте образы
   docker compose pull
   docker compose up -d
   ```

4. **Защита .env файла:**
   ```bash
   chmod 600 .env
   ```

## Производительность

### Настройка PostgreSQL

Для production нагрузки отредактируйте `docker-compose.yml`:

```yaml
postgres:
  environment:
    POSTGRES_SHARED_BUFFERS: 256MB
    POSTGRES_MAX_CONNECTIONS: 100
```

### Настройка Redis

```yaml
redis:
  command: redis-server --appendonly yes --maxmemory 256mb --maxmemory-policy allkeys-lru
```

### Настройка бота

В `.env`:
```env
DB_POOL_SIZE=20          # Увеличьте для высоких нагрузок
CACHE_TTL=300            # Уменьшите для более свежих данных
```

## Траблшутинг

### Бот не запускается

```bash
# Проверьте логи
docker compose logs bot

# Проверьте готовность БД
docker compose exec postgres pg_isready -U teammates_user

# Проверьте Redis
docker compose exec redis redis-cli ping

# Проверьте .env файл
cat .env | grep BOT_TOKEN
```

### База данных не подключается

```bash
# Проверьте что PostgreSQL запущен
docker compose ps postgres

# Проверьте логи PostgreSQL
docker compose logs postgres

# Подключитесь вручную
docker compose exec postgres psql -U teammates_user -d teammates
```

### Ошибки миграций

```bash
# Зайдите в контейнер бота
docker compose exec bot bash

# Запустите миграции вручную
python migrate.py
python migrate_ads_games.py
# и т.д.
```

### Контейнер постоянно перезапускается

```bash
# Проверьте логи
docker compose logs --tail=100 bot

# Проверьте ресурсы
docker stats

# Посмотрите состояние
docker compose ps
```

## Миграции

**ВАЖНО:** Миграции НЕ применяются автоматически и требуют ручного запуска с подтверждением.

При первом запуске бот создаст базовую схему БД автоматически. Дополнительные миграции запускайте по необходимости.

Доступные миграции:
- `migrate.py` - базовая структура ad_posts
- `migrate_ads_games.py` - поддержка игр в рекламе
- `migrate_fix.py` - исправления
- `migrate_ad_type.py` - типы рекламы
- `migrate_ad_expires.py` - срок действия рекламы

Ручной запуск:
```bash
docker compose exec bot python migrate.py
```

## Поддержка

Для вопросов и проблем:
1. Проверьте логи: `docker compose logs -f bot`
2. Проверьте статус: `docker compose ps`
3. Проверьте конфигурацию: `docker compose config`

## Дополнительно

### Запуск в фоне с systemd (опционально)

Создайте файл `/etc/systemd/system/teammates-bot.service`:

```ini
[Unit]
Description=TeammateBot Docker Compose
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/path/to/cgdv
ExecStart=/usr/bin/docker compose up -d
ExecStop=/usr/bin/docker compose down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
```

Затем:
```bash
sudo systemctl daemon-reload
sudo systemctl enable teammates-bot
sudo systemctl start teammates-bot
```

### Мониторинг с помощью Portainer (опционально)

```bash
docker volume create portainer_data
docker run -d -p 9000:9000 --name portainer --restart=always \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v portainer_data:/data \
  portainer/portainer-ce
```

Откройте `http://your-server:9000` для веб-интерфейса управления.
