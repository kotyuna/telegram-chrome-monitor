# -*- coding: utf-8 -*-
import json
import re
import time
from datetime import datetime
from pathlib import Path
from functools import wraps

import requests
from bs4 import BeautifulSoup

# =========================
#     К О Н Ф І Г У Р А Ц І Я
# =========================
BOT_TOKEN = "8174479461:AAH0gxk4SFqqxaQTMtvUVM8LphkD53yL4Bo"

# ✅ БІЛИЙ СПИСОК ДОЗВОЛЕНИХ КОРИСТУВАЧІВ (chat_id)
ALLOWED_USERS = [
    "540851454", "8099175747", "7396474416","962178937" # Ваш ID
    # Додайте сюди ID інших дозволених користувачів
    # "123456789",
    # "987654321",
]

ADMIN_CHAT_ID = "540851454"  # Адміністратор (для сповіщень про зміни)

# Години запуску перевірки
CHECK_HOURS = {7, 11, 15, 21}
last_run_hour = None

SEND_SUMMARY_AFTER_RUN = True
DATA_FILE = Path(__file__).resolve().parent / "extension_data.json"

EXTENSIONS = [
    {
        "name": "MyColorPick",
        "url": "https://chromewebstore.google.com/detail/mycolorpick-one-click-col/jckoejjnaljgkmgblmbodoegoefofhee"
    },
    {
        "name": "Font Finder",
        "url": "https://chromewebstore.google.com/detail/font-finder-identifier-fr/ajabpfgngbkodbhcfjhmmedgnaojinnn"
    },
    {
        "name": "SnipCapture",
        "url": "https://chromewebstore.google.com/detail/snipcapture-easy-screensh/jlpchojjamcikhgmedobmfodcefjmccn"
    },
    {
        "name": "PowerSound",
        "url": "https://chromewebstore.google.com/detail/powersound-high-quality-v/hinkijopmipplcccjeiblmiipdpagdbl"
    },
    {
        "name": "RecZap",
        "url": "https://chromewebstore.google.com/detail/reczap-%E2%80%93-screen-audio-cam/oocephjckjidfgiaaffnmkiiikmadkml"
    },
]

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
})
SESSION.cookies.set("CONSENT", "YES+cb", domain=".google.com")

# ✅ ДЕКОРАТОР ДЛЯ ПЕРЕВІРКИ ДОСТУПУ
def restricted(func):
    """Декоратор для обмеження доступу тільки для whitelist користувачів"""
    @wraps(func)
    def wrapped(chat_id, *args, **kwargs):
        if chat_id not in ALLOWED_USERS:
            username = kwargs.get('username', 'Unknown')
            print(f"⛔ Доступ заборонено для @{username} (chat_id={chat_id})")
            send_telegram_message(
                "⛔️ <b>Доступ заборонено</b>\n\n"
                "Цей бот доступний тільки для авторизованих користувачів.\n"
                "Зверніться до адміністратора для отримання доступу.",
                chat_id
            )
            # Повідомлення адміну про спробу доступу
            send_telegram_message(
                f"⚠️ Спроба доступу від неавторизованого користувача:\n"
                f"👤 @{username}\n"
                f"🆔 chat_id: <code>{chat_id}</code>",
                ADMIN_CHAT_ID
            )
            return
        return func(chat_id, *args, **kwargs)
    return wrapped

def send_telegram_message(message: str, chat_id: str = None):
    """Відправка повідомлення в Telegram"""
    if chat_id is None:
        chat_id = ADMIN_CHAT_ID
    
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    try:
        resp = SESSION.post(url, json=payload, timeout=15)
        if resp.status_code == 200:
            print(f"✅ Повідомлення відправлено до chat_id={chat_id}")
            return True
        else:
            print(f"⚠️ Помилка відправки: {resp.status_code}")
            return False
    except Exception as e:
        print(f"❌ Помилка відправки: {e}")
        return False

def load_previous_data() -> dict:
    """Завантаження попередніх даних"""
    try:
        if DATA_FILE.exists():
            data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
            print(f"📂 Завантажено дані: {len(data)} розширень")
            return data
        else:
            print(f"📂 Файл {DATA_FILE.name} не існує")
    except Exception as e:
        print(f"❌ Помилка читання: {e}")
    return {}

def save_data(data: dict):
    """Збереження даних"""
    try:
        DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"💾 Дані збережено: {len(data)} розширень")
    except Exception as e:
        print(f"❌ Помилка запису: {e}")

def get_extension_data(url: str):
    """Отримання даних про розширення"""
    try:
        resp = SESSION.get(url, timeout=20)
        html = resp.text
        soup = BeautifulSoup(html, "html.parser")

        rating = "N/A"
        reviews = "N/A"
        users = "N/A"

        # Рейтинг
        rating_patterns = [
            r'(\d(?:\.\d)?)\s+out of 5',
            r'"ratingValue"\s*:\s*"?([0-5](?:\.\d+)?)"?',
        ]
        for pattern in rating_patterns:
            m = re.search(pattern, html, re.IGNORECASE)
            if m:
                val = float(m.group(1))
                if 0 <= val <= 5:
                    rating = str(val)
                    break

        # Відгуки
        review_patterns = [
            r'\((\d+)\s+ratings?\)',
            r'(\d+)\s+ratings?[^\d]',
            r'"ratingCount"\s*:\s*"?(\d+)"?',
        ]
        for pattern in review_patterns:
            m = re.search(pattern, html, re.IGNORECASE)
            if m:
                reviews = m.group(1)
                break

        # Користувачі
        user_patterns = [
            r'([\d,]+)\s+users?(?!\w)',
            r'"userInteractionCount"\s*:\s*"?([\d,]+)"?',
        ]
        for pattern in user_patterns:
            m = re.search(pattern, html, re.IGNORECASE)
            if m:
                users = m.group(1).strip()
                break

        # Meta теги
        if rating == "N/A":
            meta_rating = soup.find("meta", attrs={"itemprop": "ratingValue"})
            if meta_rating and meta_rating.get("content"):
                try:
                    val = float(meta_rating["content"].strip())
                    if 0 <= val <= 5:
                        rating = str(val)
                except:
                    pass

        if reviews == "N/A":
            meta_reviews = soup.find("meta", attrs={"itemprop": "ratingCount"})
            if meta_reviews and meta_reviews.get("content"):
                reviews = meta_reviews["content"].strip()

        # JSON-LD
        for script in soup.find_all("script", {"type": "application/ld+json"}):
            try:
                data = json.loads(script.string or "")
                if isinstance(data, dict):
                    aggr = data.get("aggregateRating", {})
                    if rating == "N/A" and aggr.get("ratingValue"):
                        val = float(aggr["ratingValue"])
                        if 0 <= val <= 5:
                            rating = str(val)
                    if reviews == "N/A" and aggr.get("ratingCount"):
                        reviews = str(aggr["ratingCount"])
                    
                    stats = data.get("interactionStatistic", [])
                    if isinstance(stats, list) and users == "N/A":
                        for stat in stats:
                            if "UserDownloads" in str(stat.get("interactionType", "")):
                                users = str(stat.get("userInteractionCount", "N/A"))
            except:
                pass

        return {
            "rating": rating,
            "users": users,
            "reviews": reviews,
            "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
    except Exception as e:
        print(f"❌ Помилка отримання даних: {e}")
        return None

def check_extensions():
    """Перевірка всіх розширень"""
    previous_data = load_previous_data()
    current_data = {}

    print(f"\n🔍 Перевірка розширень о {datetime.now().strftime('%H:%M:%S')}")

    for ext in EXTENSIONS:
        name, url = ext["name"], ext["url"]
        print(f"Перевіряю {name}...")
        data = get_extension_data(url)
        
        if not data:
            time.sleep(2)
            continue

        print(f" → {name}: ⭐ {data['rating']} | 📝 {data['reviews']} | 👥 {data['users']}")
        current_data[name] = data

if name in previous_data:
    old, new = previous_data[name], data
    changes = []

    # РЕЙТИНГ
    if old.get("rating") != new.get("rating") and "N/A" not in (old.get("rating"), new.get("rating")):
        old_rating = float(old.get("rating"))
        new_rating = float(new.get("rating"))
        diff = new_rating - old_rating
        emoji = "📈" if diff > 0 else "📉"
        sign = "+" if diff > 0 else ""
        changes.append(
            f"⭐ Рейтинг: <b>{old_rating}</b> → <b>{new_rating}</b> "
            f"({sign}{diff:.1f}) {emoji}"
        )

    # ВІДГУКИ
    if old.get("reviews") != new.get("reviews") and "N/A" not in (old.get("reviews"), new.get("reviews")):
        try:
            old_reviews = int(old.get("reviews").replace(",", ""))
            new_reviews = int(new.get("reviews").replace(",", ""))
            diff = new_reviews - old_reviews
            emoji = "📈" if diff > 0 else "📉"
            sign = "+" if diff > 0 else ""
            changes.append(
                f"📝 Відгуки: <b>{old.get('reviews')}</b> → <b>{new.get('reviews')}</b> "
                f"({sign}{diff}) {emoji}"
            )
        except:
            # Якщо не вдалося перетворити в число, показуємо як раніше
            changes.append(f"📝 Відгуки: <b>{old.get('reviews')}</b> → <b>{new.get('reviews')}</b>")

    # КОРИСТУВАЧІ
    if old.get("users") != new.get("users") and "N/A" not in (old.get("users"), new.get("users")):
        try:
            # Очищаємо від ком і символу +
            old_users_str = old.get("users").replace(",", "").replace("+", "")
            new_users_str = new.get("users").replace(",", "").replace("+", "")
            old_users = int(old_users_str)
            new_users = int(new_users_str)
            diff = new_users - old_users
            emoji = "📈" if diff > 0 else "📉"
            sign = "+" if diff > 0 else ""
            
            # Форматуємо різницю з комами для великих чисел
            diff_formatted = f"{diff:,}".replace(",", " ")
            
            changes.append(
                f"👥 Користувачі: <b>{old.get('users')}</b> → <b>{new.get('users')}</b> "
                f"({sign}{diff_formatted}) {emoji}"
            )
        except:
            # Якщо не вдалося перетворити в число, показуємо як раніше
            changes.append(f"👥 Користувачі: <b>{old.get('users')}</b> → <b>{new.get('users')}</b>")

    if changes:
        msg = (
            f"🔔 <b>{name}</b>\n"
            f"🔗 <a href=\"{url}\">Відкрити в Chrome Web Store</a>\n\n" +
            "\n".join(f"• {c}" for c in changes)
        )
        # Відправляємо ВСІм дозволеним користувачам
        for user_id in ALLOWED_USERS:
            send_telegram_message(msg, user_id)
        print(f"✅ Зміни знайдено для {name}")

        else:
            msg = (
                f"✅ <b>{name}</b> додано до моніторингу\n"
                f"🔗 <a href=\"{url}\">Chrome Web Store</a>\n\n"
                f"⭐ Рейтинг: <b>{data['rating']}</b>\n"
                f"📝 Відгуки: <b>{data['reviews']}</b>\n"
                f"👥 Користувачі: <b>{data['users']}</b>"
            )
            for user_id in ALLOWED_USERS:
                send_telegram_message(msg, user_id)

        time.sleep(3)

    if current_data:
        save_data(current_data)
        
        if SEND_SUMMARY_AFTER_RUN:
            lines = []
            for ext in EXTENSIONS:
                n = ext["name"]
                d = current_data.get(n, {})
                lines.append(f"• <b>{n}</b>: ⭐ {d.get('rating','N/A')} | 📝 {d.get('reviews','N/A')} | 👥 {d.get('users','N/A')}")
            summary = "📊 <b>Підсумок перевірки</b>\n\n" + "\n".join(lines)
            for user_id in ALLOWED_USERS:
                send_telegram_message(summary, user_id)

    print("✅ Перевірка завершена\n")

@restricted
def handle_start_command(chat_id: str, username: str = "Unknown"):
    """Обробка команди /start - тільки для whitelist користувачів"""
    print(f"🔹 /start від @{username} (chat_id={chat_id})")
    previous_data = load_previous_data()
    
    if not previous_data:
        msg = (
            "👋 Вітаю!\n\n"
            "⏳ Дані ще не завантажені.\n"
            "Спробуйте пізніше або натисніть /check"
        )
    else:
        lines = ["📊 <b>Статистика розширень Chrome</b>\n"]
        for ext in EXTENSIONS:
            n = ext["name"]
            d = previous_data.get(n, {})
            url = ext["url"]
            
            if d:
                lines.append(
                    f"• <b>{n}</b>\n"
                    f"  ⭐ Рейтинг: {d.get('rating','N/A')}\n"
                    f"  📝 Відгуки: {d.get('reviews','N/A')}\n"
                    f"  👥 Користувачі: {d.get('users','N/A')}\n"
                    f"  🔗 <a href=\"{url}\">Відкрити</a>\n"
                )
        
        checked_at = "N/A"
        for d in previous_data.values():
            if d.get("checked_at"):
                checked_at = d["checked_at"]
                break
        
        lines.append(f"\n🕐 Оновлено: {checked_at}")
        
        # Показуємо /check тільки адміну
        if chat_id == ADMIN_CHAT_ID:
            lines.append("\n💡 /check — запустити перевірку зараз")
        
        msg = "\n".join(lines)
    
    send_telegram_message(msg, chat_id)

@restricted
def handle_check_command(chat_id: str, username: str = "Unknown"):
    """Обробка /check - тільки для адміністратора"""
    if chat_id != ADMIN_CHAT_ID:
        send_telegram_message("⛔️ Ця команда доступна тільки адміністратору", chat_id)
        return
    
    print(f"🔹 /check від адміна")
    send_telegram_message("🔄 Запускаю перевірку...\n⏳ ~20 секунд", chat_id)
    try:
        check_extensions()
        send_telegram_message("✅ Перевірка завершена!", chat_id)
    except Exception as e:
        send_telegram_message(f"⚠️ Помилка: {e}", chat_id)

last_update_id = 0

def check_telegram_updates():
    """Перевірка нових повідомлень"""
    global last_update_id
    
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
        params = {"offset": last_update_id + 1, "timeout": 5}
        resp = SESSION.get(url, params=params, timeout=10)
        data = resp.json()
        
        if data.get("ok") and data.get("result"):
            for update in data["result"]:
                update_id = update.get("update_id", 0)
                last_update_id = max(last_update_id, update_id)
                
                message = update.get("message", {})
                text = message.get("text", "").strip()
                chat_id = str(message.get("chat", {}).get("id", ""))
                username = message.get("from", {}).get("username", "Unknown")
                
                print(f"📨 '{text}' від @{username} (chat_id={chat_id})")
                
                # Обробка команд (перевірка доступу всередині функцій через @restricted)
                if text == "/start":
                    handle_start_command(chat_id, username=username)
                elif text == "/check":
                    handle_check_command(chat_id, username=username)
                elif text.startswith("/"):
                    # Тільки для дозволених користувачів показуємо список команд
                    if chat_id in ALLOWED_USERS:
                        send_telegram_message(
                            f"❌ Невідома команда: {text}\n\n"
                            "Доступні команди:\n"
                            "/start - показати статистику",
                            chat_id
                        )
                    
    except Exception as e:
        print(f"❌ Помилка перевірки команд: {e}")

def main():
    global last_run_hour

    print("🤖 Chrome Extension Monitor Bot запущено!")
    print(f"👥 Дозволені користувачі: {len(ALLOWED_USERS)}")
    print(f"👤 Адмін: {ADMIN_CHAT_ID}\n")
    
    send_telegram_message(
        "🤖 Бот запущено!\n\n"
        f"👥 Дозволено користувачів: {len(ALLOWED_USERS)}\n\n"
        "💡 Команди:\n"
        "/start - статистика\n"
        "/check - перевірка (тільки адмін)"
    )

    print("⏳ Перша перевірка...")
    try:
        check_extensions()
    except Exception as e:
        print(f"⚠️ Помилка: {e}")

    print("\n🔄 Основний цикл запущено\n")

    while True:
        try:
            check_telegram_updates()
            
            now = datetime.now()
            if now.hour in CHECK_HOURS and now.minute == 0 and now.hour != last_run_hour:
                print(f"\n⏱ Перевірка за розкладом: {now.strftime('%H:%M')}")
                try:
                    check_extensions()
                except Exception as e:
                    print(f"⚠️ Помилка: {e}")
                last_run_hour = now.hour
                
        except KeyboardInterrupt:
            print("\n🛑 Бот зупинено")
            break
        except Exception as e:
            print(f"❌ Помилка: {e}")
        
        time.sleep(5)

if __name__ == "__main__":
    main()
