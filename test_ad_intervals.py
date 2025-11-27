#!/usr/bin/env python3
"""
Тестовый скрипт для проверки логики показа рекламы с разными интервалами
"""

def simulate_ad_system(ads, num_profiles=200):
    """
    Симуляция системы показа рекламы

    Args:
        ads: список словарей с рекламой [{id, interval}, ...]
        num_profiles: количество анкет для просмотра
    """
    import random

    print("=" * 80)
    print("СИМУЛЯЦИЯ ПОКАЗА РЕКЛАМЫ")
    print("=" * 80)
    print(f"\nРеклам в системе: {len(ads)}")
    for ad in ads:
        print(f"  Реклама #{ad['id']}: интервал {ad['interval']}")
    print(f"\nБудет просмотрено анкет: {num_profiles}\n")

    # Инициализация
    ads_queue_ids = [ad['id'] for ad in ads]
    random.shuffle(ads_queue_ids)

    current_ad_index = 0
    first_ad = next((ad for ad in ads if ad['id'] == ads_queue_ids[0]), None)
    next_ad_at = first_ad['interval']

    profiles_shown = 0
    ads_shown = []

    print(f"Инициализация: Очередь ID: {ads_queue_ids}")
    print(f"Первая реклама: #{first_ad['id']} через {next_ad_at} анкет\n")
    print("-" * 80)

    # Симуляция просмотра анкет
    for i in range(1, num_profiles + 1):
        profiles_shown = i

        # Проверяем, пора ли показать рекламу
        if profiles_shown >= next_ad_at and current_ad_index < len(ads_queue_ids):
            current_ad_id = ads_queue_ids[current_ad_index]
            ad = next((a for a in ads if a['id'] == current_ad_id), None)

            if ad:
                print(f"📍 Анкета {profiles_shown}: ПОКАЗЫВАЕМ РЕКЛАМУ #{ad['id']} (интервал {ad['interval']})")
                ads_shown.append({
                    'ad_id': ad['id'],
                    'at_profile': profiles_shown,
                    'interval': ad['interval']
                })

                # Переходим к следующей рекламе
                new_ad_index = current_ad_index + 1

                # Если дошли до конца - перемешиваем
                if new_ad_index >= len(ads_queue_ids):
                    random.shuffle(ads_queue_ids)
                    new_ad_index = 0
                    print(f"   🔄 Цикл завершён, новая очередь: {ads_queue_ids}")

                current_ad_index = new_ad_index
                next_ad = next((a for a in ads if a['id'] == ads_queue_ids[new_ad_index]), None)

                if next_ad:
                    next_ad_at = profiles_shown + next_ad['interval']
                    print(f"   ➡️  Следующая: реклама #{next_ad['id']} (интервал {next_ad['interval']}) на шаге {next_ad_at}")

    print("-" * 80)
    print(f"\n📊 ИТОГОВАЯ СТАТИСТИКА")
    print("=" * 80)
    print(f"Всего анкет просмотрено: {num_profiles}")
    print(f"Всего показов рекламы: {len(ads_shown)}\n")

    # Статистика по каждой рекламе
    ad_stats = {}
    for show in ads_shown:
        ad_id = show['ad_id']
        if ad_id not in ad_stats:
            ad_stats[ad_id] = []
        ad_stats[ad_id].append(show['at_profile'])

    print("Показы по рекламам:")
    for ad in ads:
        count = len(ad_stats.get(ad['id'], []))
        positions = ad_stats.get(ad['id'], [])
        print(f"\n  Реклама #{ad['id']} (интервал {ad['interval']}): {count} показов")
        if positions:
            print(f"    Показана на позициях: {positions}")
            if len(positions) > 1:
                intervals_between = [positions[i] - positions[i-1] for i in range(1, len(positions))]
                avg_interval = sum(intervals_between) / len(intervals_between) if intervals_between else 0
                print(f"    Средний интервал между показами: {avg_interval:.1f} анкет")

    print("\n" + "=" * 80)

if __name__ == "__main__":
    print("\n🧪 ТЕСТ 1: Малые интервалы (старая система)")
    print("Рекламы: #1(5), #2(10), #3(15)")
    simulate_ad_system([
        {'id': 1, 'interval': 5},
        {'id': 2, 'interval': 10},
        {'id': 3, 'interval': 15}
    ], num_profiles=100)

    print("\n\n")

    print("🧪 ТЕСТ 2: Большие интервалы")
    print("Рекламы: #1(50), #2(100), #3(150)")
    simulate_ad_system([
        {'id': 1, 'interval': 50},
        {'id': 2, 'interval': 100},
        {'id': 3, 'interval': 150}
    ], num_profiles=500)

    print("\n\n")

    print("🧪 ТЕСТ 3: Экстремально большие интервалы")
    print("Рекламы: #1(200), #2(300), #3(500)")
    simulate_ad_system([
        {'id': 1, 'interval': 200},
        {'id': 2, 'interval': 300},
        {'id': 3, 'interval': 500}
    ], num_profiles=1000)

    print("\n\n")

    print("🧪 ТЕСТ 4: Смешанные интервалы (новая система)")
    print("Рекламы: #1(10), #2(50), #3(100), #4(25)")
    simulate_ad_system([
        {'id': 1, 'interval': 10},
        {'id': 2, 'interval': 50},
        {'id': 3, 'interval': 100},
        {'id': 4, 'interval': 25}
    ], num_profiles=300)
