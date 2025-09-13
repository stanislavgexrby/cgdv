#!/usr/bin/env python3
"""
Скрипт для автоматического обновления handlers файлов
для перехода на async Database
"""

import os
import re
from pathlib import Path

def update_handler_file(file_path: Path):
    """Обновление одного handler файла"""
    print(f"🔄 Обновляю {file_path.name}...")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # 1. Замена импорта
        content = re.sub(
            r'from database\.database import Database.*\n',
            '',
            content
        )
        content = re.sub(
            r'db = Database\(.*?\)\n',
            '',
            content
        )
        
        # 2. Добавление нового импорта (если его еще нет)
        if 'from main import get_database' not in content:
            # Находим место для вставки импорта (после других импортов)
            import_pattern = r'(import config\.settings as settings)'
            replacement = r'\1\nfrom main import get_database'
            content = re.sub(import_pattern, replacement, content)
        
        # 3. Добавление db = get_database() в начало функций которые используют БД
        # Ищем функции с вызовами db.method()
        function_pattern = r'(async def|def) ([^(]+)\([^)]*\):'
        
        def add_db_getter(match):
            func_def = match.group(0)
            func_name = match.group(2)
            
            # Пропускаем служебные функции
            if func_name in ['register_handlers', '__init__', 'signal_handler']:
                return func_def
            
            return func_def
        
        # Более простой подход: добавляем комментарий для ручного обновления
        content = content.replace(
            'def check_ban_and_profile',
            '# TODO: Обновить этот декоратор для async\ndef check_ban_and_profile'
        )
        
        # 4. Замена синхронных вызовов БД на асинхронные (базовые случаи)
        db_methods = [
            'get_user', 'create_user', 'switch_game', 'get_user_profile', 
            'has_profile', 'update_user_profile', 'delete_profile',
            'get_potential_matches', 'add_search_skip', 'add_like',
            'get_likes_for_user', 'get_matches', 'skip_like',
            'is_user_banned', 'get_user_ban', 'add_ban', 'unban_user',
            'add_report', 'get_pending_reports', 'process_report'
        ]
        
        for method in db_methods:
            # Заменяем db.method( на await db.method(
            pattern = f'db\.{method}\('
            replacement = f'await db.{method}('
            content = re.sub(pattern, replacement, content)
        
        # 5. Добавление await к проверенным вызовам
        content = re.sub(r'= db\.', '= await db.', content)
        content = re.sub(r'if db\.', 'if await db.', content)
        content = re.sub(r'elif db\.', 'elif await db.', content)
        
        # 6. Исправление дублирующихся await
        content = re.sub(r'await await', 'await', content)
        
        # Сохраняем файл если были изменения
        if content != original_content:
            # Создаем бэкап
            backup_path = file_path.with_suffix(file_path.suffix + '.backup')
            with open(backup_path, 'w', encoding='utf-8') as f:
                f.write(original_content)
            
            # Сохраняем обновленный файл
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            print(f"  ✅ {file_path.name} обновлен (бэкап: {backup_path.name})")
            return True
        else:
            print(f"  ℹ️ {file_path.name} не требует изменений")
            return False
    
    except Exception as e:
        print(f"  ❌ Ошибка обновления {file_path.name}: {e}")
        return False

def create_manual_todo_file():
    """Создание файла с задачами для ручного обновления"""
    todo_content = """# TODO: Ручное обновление handlers файлов

После запуска update_handlers.py нужно вручную:

## 1. В КАЖДОМ handlers/*.py файле (кроме __init__.py):

### Добавить в начало КАЖДОЙ функции которая использует БД:
```python
db = get_database()
```

### Пример:
```python
# БЫЛО:
@router.callback_query(F.data == "create_profile")
async def start_create_profile(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    # ...

# СТАЛО:
@router.callback_query(F.data == "create_profile")  
async def start_create_profile(callback: CallbackQuery, state: FSMContext):
    db = get_database()  # ← ДОБАВИТЬ ЭТУ СТРОКУ
    user_id = callback.from_user.id
    # ...
```

## 2. Сделать все функции async:

### Если функция была:
```python
def my_function(callback: CallbackQuery):
```

### Сделать:
```python
async def my_function(callback: CallbackQuery):
```

## 3. Обновить декораторы в handlers/basic.py:

Найти функцию check_ban_and_profile и обновить по примеру в 
документации.

## 4. Проверить что все работает:
```bash
python main.py
```

## Файлы которые нужно обновить:
- handlers/basic.py
- handlers/profile.py  
- handlers/profile_editing.py
- handlers/search.py
- handlers/likes.py

## В случае проблем:
1. Восстановить из бэкапов: *.backup
2. Обновить вручную по примерам в документации
"""
    
    with open('TODO_handlers.md', 'w', encoding='utf-8') as f:
        f.write(todo_content)
    
    print("📋 Создан файл TODO_handlers.md с инструкциями")

def main():
    """Основная функция обновления"""
    print("🔧 Автоматическое обновление handlers файлов")
    print("=" * 50)
    
    handlers_dir = Path("handlers")
    if not handlers_dir.exists():
        print("❌ Папка handlers не найдена")
        return
    
    # Находим все Python файлы в handlers
    python_files = list(handlers_dir.glob("*.py"))
    python_files = [f for f in python_files if f.name != "__init__.py"]
    
    if not python_files:
        print("❌ Не найдены handlers файлы")
        return
    
    updated_count = 0
    for file_path in python_files:
        if update_handler_file(file_path):
            updated_count += 1
    
    # Создаем TODO файл
    create_manual_todo_file()
    
    print("\n" + "=" * 50)
    print(f"📊 Результат: обновлено {updated_count}/{len(python_files)} файлов")
    print("\n🔧 Что сделано автоматически:")
    print("  ✅ Убраны старые импорты Database")
    print("  ✅ Добавлен импорт get_database")
    print("  ✅ Добавлен await к вызовам БД")
    
    print("\n📋 Что нужно сделать вручную:")
    print("  🔸 Добавить db = get_database() в функции")
    print("  🔸 Проверить что все функции async")
    print("  🔸 Обновить декораторы")
    print("\n📄 Подробные инструкции в файле: TODO_handlers.md")
    
    print("\n🚀 После ручного обновления:")
    print("  python main.py")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n❌ Обновление прервано пользователем")
    except Exception as e:
        print(f"\n💥 Ошибка: {e}")
        print("Обновите файлы вручную по примерам")