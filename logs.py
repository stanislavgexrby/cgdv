#!/usr/bin/env python3
"""
Утилита для просмотра и мониторинга логов TeammateBot
"""

import os
import sys
import argparse
import subprocess
from pathlib import Path
from datetime import datetime, timedelta
import re

def check_logs_exist():
    """Проверка наличия папки с логами"""
    logs_dir = Path("logs")
    if not logs_dir.exists():
        print("❌ Папка logs не найдена!")
        print("💡 Запустите бота хотя бы раз: python main.py")
        return False
    return True

def show_log_stats():
    """Показать статистику логов"""
    logs_dir = Path("logs")
    
    print("📊 СТАТИСТИКА ЛОГОВ")
    print("=" * 50)
    
    log_files = {
        "bot.log": "Основные логи",
        "errors.log": "Ошибки",
        "daily.log": "Детальные логи"
    }
    
    total_size = 0
    for log_file, description in log_files.items():
        log_path = logs_dir / log_file
        if log_path.exists():
            size_mb = log_path.stat().st_size / (1024 * 1024)
            total_size += size_mb
            mtime = datetime.fromtimestamp(log_path.stat().st_mtime)
            print(f"📄 {log_file:15} - {description}")
            print(f"   Размер: {size_mb:.1f} MB")
            print(f"   Изменен: {mtime.strftime('%Y-%m-%d %H:%M:%S')}")
            
            # Показываем последнюю строку
            try:
                with open(log_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    if lines:
                        last_line = lines[-1].strip()
                        if len(last_line) > 80:
                            last_line = last_line[:77] + "..."
                        print(f"   Последняя запись: {last_line}")
            except Exception:
                pass
            print()
        else:
            print(f"📄 {log_file:15} - НЕ НАЙДЕН")
    
    print(f"📊 Общий размер логов: {total_size:.1f} MB")
    
    # Показываем архивные файлы
    archive_files = list(logs_dir.glob("*.log.*"))
    if archive_files:
        print(f"\n📦 Архивных файлов: {len(archive_files)}")
        archive_size = sum(f.stat().st_size for f in archive_files) / (1024 * 1024)
        print(f"📊 Размер архивов: {archive_size:.1f} MB")

def tail_log(log_name="bot.log", lines=50):
    """Показать последние строки лога"""
    logs_dir = Path("logs")
    log_path = logs_dir / log_name
    
    if not log_path.exists():
        print(f"❌ Лог файл {log_name} не найден!")
        return
    
    print(f"📄 Последние {lines} строк из {log_name}:")
    print("=" * 80)
    
    try:
        if sys.platform.startswith('win'):
            # Windows
            subprocess.run(['powershell', f'Get-Content "{log_path}" -Tail {lines}'])
        else:
            # Linux/Mac
            subprocess.run(['tail', f'-{lines}', str(log_path)])
    except FileNotFoundError:
        # Fallback для систем без tail
        with open(log_path, 'r', encoding='utf-8') as f:
            lines_list = f.readlines()
            for line in lines_list[-lines:]:
                print(line.rstrip())

def follow_log(log_name="bot.log"):
    """Следить за логом в реальном времени (аналог tail -f)"""
    logs_dir = Path("logs")
    log_path = logs_dir / log_name
    
    if not log_path.exists():
        print(f"❌ Лог файл {log_name} не найден!")
        return
    
    print(f"👁️  Мониторинг {log_name} в реальном времени...")
    print("💡 Нажмите Ctrl+C для остановки")
    print("=" * 80)
    
    try:
        if sys.platform.startswith('win'):
            # Windows - используем PowerShell
            subprocess.run(['powershell', f'Get-Content "{log_path}" -Wait -Tail 10'])
        else:
            # Linux/Mac - используем tail -f
            subprocess.run(['tail', '-f', str(log_path)])
    except KeyboardInterrupt:
        print("\n👋 Мониторинг остановлен")
    except FileNotFoundError:
        print("❌ Команда tail недоступна. Используйте: python logs.py --tail")

def search_logs(pattern, log_name="bot.log", context_lines=2):
    """Поиск по логам"""
    logs_dir = Path("logs")
    log_path = logs_dir / log_name
    
    if not log_path.exists():
        print(f"❌ Лог файл {log_name} не найден!")
        return
    
    print(f"🔍 Поиск '{pattern}' в {log_name}:")
    print("=" * 80)
    
    try:
        with open(log_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        matches_found = 0
        for i, line in enumerate(lines):
            if re.search(pattern, line, re.IGNORECASE):
                matches_found += 1
                
                # Показываем контекст
                start = max(0, i - context_lines)
                end = min(len(lines), i + context_lines + 1)
                
                print(f"\n📍 Совпадение {matches_found} (строка {i+1}):")
                for j in range(start, end):
                    prefix = ">>> " if j == i else "    "
                    print(f"{prefix}{lines[j].rstrip()}")
        
        if matches_found == 0:
            print("❌ Совпадений не найдено")
        else:
            print(f"\n✅ Найдено совпадений: {matches_found}")
            
    except Exception as e:
        print(f"❌ Ошибка поиска: {e}")

def analyze_errors():
    """Анализ ошибок в логах"""
    logs_dir = Path("logs")
    
    print("🔍 АНАЛИЗ ОШИБОК")
    print("=" * 50)
    
    error_files = ["errors.log", "bot.log"]
    total_errors = 0
    
    for log_name in error_files:
        log_path = logs_dir / log_name
        if not log_path.exists():
            continue
            
        print(f"\n📄 Анализ {log_name}:")
        
        try:
            with open(log_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Считаем разные типы ошибок
            error_patterns = {
                "ERROR": r"ERROR",
                "CRITICAL": r"CRITICAL",
                "Exception": r"Exception",
                "Traceback": r"Traceback",
                "Database errors": r"(PostgreSQL|Redis|asyncpg).*error",
                "Telegram errors": r"(aiogram|telegram).*error"
            }
            
            file_errors = 0
            for error_type, pattern in error_patterns.items():
                matches = re.findall(pattern, content, re.IGNORECASE)
                count = len(matches)
                if count > 0:
                    file_errors += count
                    print(f"   {error_type}: {count}")
            
            total_errors += file_errors
            if file_errors == 0:
                print("   ✅ Ошибок не найдено")
                
        except Exception as e:
            print(f"   ❌ Ошибка чтения: {e}")
    
    print(f"\n📊 Всего ошибок найдено: {total_errors}")
    
    if total_errors > 0:
        print("\n💡 Для детального просмотра используйте:")
        print("   python logs.py --search 'ERROR|CRITICAL'")

def clean_old_logs(days=30):
    """Очистка старых архивных логов"""
    logs_dir = Path("logs")
    
    if not logs_dir.exists():
        print("❌ Папка logs не найдена")
        return
    
    cutoff_date = datetime.now() - timedelta(days=days)
    
    # Ищем архивные файлы (*.log.*)
    archive_files = list(logs_dir.glob("*.log.*"))
    
    deleted_count = 0
    deleted_size = 0
    
    for archive_file in archive_files:
        file_date = datetime.fromtimestamp(archive_file.stat().st_mtime)
        
        if file_date < cutoff_date:
            file_size = archive_file.stat().st_size
            try:
                archive_file.unlink()
                deleted_count += 1
                deleted_size += file_size
                print(f"🗑️  Удален: {archive_file.name} ({file_size/1024/1024:.1f} MB)")
            except Exception as e:
                print(f"❌ Ошибка удаления {archive_file.name}: {e}")
    
    if deleted_count == 0:
        print(f"✅ Старых логов (старше {days} дней) не найдено")
    else:
        print(f"\n🧹 Очищено файлов: {deleted_count}")
        print(f"💾 Освобождено: {deleted_size/1024/1024:.1f} MB")

def main():
    parser = argparse.ArgumentParser(description="Утилита для работы с логами TeammateBot")
    parser.add_argument('--stats', action='store_true', help='Показать статистику логов')
    parser.add_argument('--tail', metavar='N', type=int, default=50, help='Показать последние N строк (по умолчанию 50)')
    parser.add_argument('--follow', action='store_true', help='Следить за логами в реальном времени')
    parser.add_argument('--search', metavar='PATTERN', help='Поиск по логам')
    parser.add_argument('--log', metavar='FILE', default='bot.log', help='Имя лог файла (по умолчанию bot.log)')
    parser.add_argument('--errors', action='store_true', help='Анализ ошибок')
    parser.add_argument('--clean', metavar='DAYS', type=int, help='Удалить архивные логи старше N дней')
    
    args = parser.parse_args()
    
    # Проверяем наличие логов
    if not check_logs_exist():
        return
    
    # Выполняем команды
    if args.stats:
        show_log_stats()
    elif args.follow:
        follow_log(args.log)
    elif args.search:
        search_logs(args.search, args.log)
    elif args.errors:
        analyze_errors()
    elif args.clean:
        clean_old_logs(args.clean)
    else:
        # По умолчанию показываем последние строки
        tail_log(args.log, args.tail)

if __name__ == "__main__":
    main()