import os
import sys
import subprocess
from pathlib import Path
import shutil

def check_python_version():
    if sys.version_info < (3, 8):
        print("❌ Требуется Python 3.8 или выше")
        print(f"Установлена версия: {sys.version}")
        return False

    print(f"✅ Python {sys.version_info.major}.{sys.version_info.minor} найден")
    return True

def create_virtual_env():
    venv_path = Path("venv")

    if venv_path.exists():
        print("✅ Виртуальное окружение уже существует")
        return True

    print("📦 Создание виртуального окружения...")
    try:
        subprocess.run([sys.executable, "-m", "venv", "venv"], check=True)
        print("✅ Виртуальное окружение создано")
        return True
    except subprocess.CalledProcessError:
        print("❌ Ошибка создания виртуального окружения")
        return False

def get_pip_command():
    if os.name == 'nt':
        return str(Path("venv/Scripts/pip.exe"))
    else:
        return str(Path("venv/bin/pip"))

def install_dependencies():
    """Установка зависимостей"""
    print("📥 Установка зависимостей...")

    pip_cmd = get_pip_command()

    try:
        subprocess.run([pip_cmd, "install", "--upgrade", "pip"], check=True)

        subprocess.run([pip_cmd, "install", "-r", "requirements.txt"], check=True)

        print("✅ Зависимости установлены")
        return True
    except subprocess.CalledProcessError:
        print("❌ Ошибка установки зависимостей")
        return False

def create_env_file():
    env_path = Path(".env")
    env_example_path = Path(".env.example")

    if env_path.exists():
        print("✅ Файл .env уже существует")
        return True

    if not env_example_path.exists():
        print("⚠️  Файл .env.example не найден, создаем базовый .env")

        env_content = """
            # TeammateBot Configuration
            BOT_TOKEN=your_bot_token_here
            ADMIN_ID=123456789
            DOTA_CHANNEL_ID=@your_dota_channel
            CS_CHANNEL_ID=@your_cs_channel
            CHECK_SUBSCRIPTION=false
            DATABASE_PATH=data/teammates.db
        """

        try:
            with open(env_path, 'w', encoding='utf-8') as f:
                f.write(env_content)
            print("✅ Базовый файл .env создан")
        except Exception as e:
            print(f"❌ Ошибка создания .env файла: {e}")
            return False
    else:
        try:
            shutil.copy(env_example_path, env_path)
            print("✅ Файл .env создан из .env.example")
        except Exception as e:
            print(f"❌ Ошибка создания .env файла: {e}")
            return False

    print("")
    print("🔧 ВАЖНО: Отредактируйте файл .env и укажите:")
    print("   - BOT_TOKEN (получите у @BotFather)")
    print("   - ADMIN_ID (ваш Telegram ID от @userinfobot)")
    print("   - DOTA_CHANNEL_ID (канал для Dota 2)")
    print("   - CS_CHANNEL_ID (канал для CS2)")
    print("")
    return True

def main():
    print("🎮 Установка TeammateBot")
    print("=" * 40)

    if not check_python_version():
        return False

    if not create_virtual_env():
        return False

    if not install_dependencies():
        return False

    create_env_file()

    print("Запустите бота:")

    if os.name == 'nt':
        print("   python main.py")
    else:
        print("   python main.py")

    return True

if __name__ == "__main__":
    try:
        success = main()
        if not success:
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n❌ Установка прервана пользователем")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Неожиданная ошибка: {e}")
        sys.exit(1)