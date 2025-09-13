#!/usr/bin/env python3
"""
Проверка переменных окружения и подключений
"""
import os
from dotenv import load_dotenv

def main():
    print("🔍 Проверка настроек .env файла")
    print("=" * 50)
    
    # Загружаем переменные
    load_dotenv()
    
    # Проверяем обязательные переменные
    required_vars = {
        'BOT_TOKEN': 'Токен Telegram бота',
        'DB_HOST': 'Хост PostgreSQL',
        'DB_PORT': 'Порт PostgreSQL',
        'DB_NAME': 'Имя базы данных',
        'DB_USER': 'Пользователь PostgreSQL',
        'DB_PASSWORD': 'Пароль PostgreSQL',
        'REDIS_HOST': 'Хост Redis',
        'REDIS_PORT': 'Порт Redis'
    }
    
    print("Проверяем переменные окружения:")
    print("-" * 30)
    
    all_ok = True
    for var, description in required_vars.items():
        value = os.getenv(var)
        if not value or value in ['None', 'your_bot_token_here', 'your_password']:
            print(f"❌ {var}: НЕ УСТАНОВЛЕНА ({description})")
            all_ok = False
        else:
            # Скрываем пароли в выводе
            if 'PASSWORD' in var or 'TOKEN' in var:
                display_value = '***'
            else:
                display_value = value
            print(f"✅ {var}: {display_value}")
    
    print("-" * 30)
    
    if all_ok:
        print("🎉 Все переменные настроены!")
        
        # Показываем строки подключения
        print("\n📡 Строки подключения:")
        postgres_url = f"postgresql://{os.getenv('DB_USER')}:***@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
        redis_url = f"redis://{os.getenv('REDIS_HOST')}:{os.getenv('REDIS_PORT')}/{os.getenv('REDIS_DB', 0)}"
        
        print(f"  PostgreSQL: {postgres_url}")
        print(f"  Redis: {redis_url}")
        
        print("\n🚀 Теперь можно запускать:")
        print("  python test_connections.py  # для проверки подключений")
        print("  python main.py              # для запуска бота")
    else:
        print("💥 Исправьте переменные в .env файле!")
        print("\nПример правильного .env файла:")
        print("""
DB_HOST=localhost
DB_PORT=5432
DB_NAME=teammates
DB_USER=teammates_user
DB_PASSWORD=07072112sS
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
BOT_TOKEN=1234567890:ABCdef...
ADMIN_ID=123456789
""")

if __name__ == "__main__":
    main()