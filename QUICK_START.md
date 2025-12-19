# Быстрый старт на сервере

## Установка Docker (если не установлен)

### Ubuntu/Debian
```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
```

Выйдите и войдите снова для применения группы.

## Развертывание бота

### 1. Клонировать проект
```bash
git clone <your-repo-url> teammates-bot
cd teammates-bot
```

### 2. Настроить окружение
```bash
cp .env.example .env
nano .env
```

Обязательно измените:
- `BOT_TOKEN` - токен от @BotFather
- `ADMIN_ID` - ваш Telegram ID
- `DOTA_CHANNEL_ID` и `CS_CHANNEL_ID` - ID каналов
- `DB_PASSWORD` - надежный пароль

### 3. Запустить
```bash
docker compose up -d
```

### 4. Проверить
```bash
# Статус
docker compose ps

# Логи
docker compose logs -f bot

# Должно появиться: "CGDV TeammateBot успешно запущен"
```

## Полезные команды

```bash
# Остановить
docker compose down

# Перезапустить
docker compose restart bot

# Обновить код и перезапустить
git pull
docker compose up -d --build

# Бэкап БД
docker compose exec postgres pg_dump -U teammates_user teammates > backup.sql

# Просмотр логов
tail -f logs/bot.log
```

## Если что-то не работает

1. Проверьте логи: `docker compose logs bot`
2. Проверьте .env файл: `cat .env | grep BOT_TOKEN`
3. Проверьте статус: `docker compose ps`
4. Смотрите подробную документацию в DEPLOYMENT.md

## Автозапуск при перезагрузке сервера

Создайте `/etc/systemd/system/teammates-bot.service`:
```ini
[Unit]
Description=TeammateBot
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/path/to/teammates-bot
ExecStart=/usr/bin/docker compose up -d
ExecStop=/usr/bin/docker compose down

[Install]
WantedBy=multi-user.target
```

Затем:
```bash
sudo systemctl daemon-reload
sudo systemctl enable teammates-bot
sudo systemctl start teammates-bot
```

Готово! Бот будет автоматически запускаться при перезагрузке сервера.
