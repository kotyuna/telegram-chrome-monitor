# -*- coding: utf-8 -*-
import json
import re
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse

import requests
from bs4 import BeautifulSoup

# =========================
#     К О Н Ф І Г У Р А Ц І Я
# =========================
BOT_TOKEN = "8174479461:AAH0gxk4SFqqxaQTMtvUVM8LphkD53yL4Bo"
CHAT_ID   = "540851454"

# Години запуску перевірки (24-годинний формат)
CHECK_HOURS = {7, 11, 15, 21}  # Київський час: 9, 13, 17, 23
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

def send_telegram_message(message: str):
    """Відправка повідомлення в Telegram"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    try:
        SESSION.post(url, json=payload, timeout=15)
    except Exception as e:
        print(f"Помилка відправки в Telegram: {e}")

def load_previous_data() -> dict:
    """Завантаження попередніх даних"""
    try:
        if DATA_FILE.exists():
            return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"Помилка читання {DATA_FILE.name}: {e}")
    return {}

def save_data(data: dict):
    """Збереження даних"""
    try:
        DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"Помилка запису {DATA_FILE.name}: {e}")

def get_extension_data(url: str):
    """Отримання даних про розширення через множинні методи"""
    try:
        resp = SESSION.get(url, timeout=20)
        html = resp.text
        soup = BeautifulSoup(html, "html.parser")

        print(f"Завантажено {len(html)} байт з {url}")

        rating = "N/A"
        reviews = "N/A"
        users = "N/A"

        # Метод 1: Пошук формату "X out of 5" або "X.X out of 5"
        rating_patterns = [
            r'(\d(?:\.\d)?)\s+out of 5',  # "4 out of 5" або "4.5 out of 5"
            r'"ratingValue"\s*:\s*"?([0-5](?:\.\d+)?)"?',
            r'Rated\s+([0-5](?:\.\d+)?)\s+out of 5',
            r'"averageRating"\s*:\s*"?([0-5](?:\.\d+)?)"?',
        ]
        for pattern in rating_patterns:
            m = re.search(pattern, html, re.IGNORECASE)
            if m:
                val = float(m.group(1))
                if 0 <= val <= 5:
                    rating = str(val)
                    break

        # Відгуки: шукаємо числа (в дужках або після ratings/reviews)
        review_patterns = [
            r'\((\d+)\s+ratings?\)',  # "(4 ratings)"
            r'(\d+)\s+ratings?[^\d]',  # "4 ratings"
            r'"ratingCount"\s*:\s*"?(\d+)"?',
            r'"reviewCount"\s*:\s*"?(\d+)"?',
        ]
        for pattern in review_patterns:
            m = re.search(pattern, html, re.IGNORECASE)
            if m:
                reviews = m.group(1)
                break

        # Користувачі: шукаємо патерни з "users"
        user_patterns = [
            r'([\d,]+)\s+users?(?!\w)',  # "2,000 users"
            r'"userInteractionCount"\s*:\s*"?([\d,]+)"?',
            r'UserDownloads["\s:]+([0-9,]+\+?)',
            r'"interactionCount".*?([\d,]+\+?)',
        ]
        for pattern in user_patterns:
            m = re.search(pattern, html, re.IGNORECASE)
            if m:
                users = m.group(1).strip()
                break

        # Метод 2: Пошук в aria-label атрибутах
        if rating == "N/A":
            for elem in soup.find_all(attrs={"aria-label": True}):
                label = elem.get("aria-label", "")
                m = re.search(r'([3-5]\.\d+)\s+star', label, re.IGNORECASE)
                if m:
                    val = float(m.group(1))
                    if 0 <= val <= 5:
                        rating = m.group(1)
                        break

        # Метод 3: Пошук в meta тегах
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

        # Метод 4: JSON-LD структуровані дані
        if rating == "N/A" or reviews == "N/A" or users == "N/A":
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
        print(f"Помилка отримання даних: {e}")
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

            if old.get("rating") != new.get("rating") and "N/A" not in (old.get("rating"), new.get("rating")):
                changes.append(f"⭐ Рейтинг: <b>{old.get('rating')}</b> → <b>{new.get('rating')}</b>")

            if old.get("reviews") != new.get("reviews") and "N/A" not in (old.get("reviews"), new.get("reviews")):
                changes.append(f"📝 Відгуки: <b>{old.get('reviews')}</b> → <b>{new.get('reviews')}</b>")

            if old.get("users") != new.get("users") and "N/A" not in (old.get("users"), new.get("users")):
                changes.append(f"👥 Користувачі: <b>{old.get('users')}</b> → <b>{new.get('users')}</b>")

            if changes:
                msg = (
                    f"🔔 <b>{name}</b>\n"
                    f"🔗 <a href=\"{url}\">Відкрити в Chrome Web Store</a>\n\n" +
                    "\n".join(f"• {c}" for c in changes)
                )
                send_telegram_message(msg)
                print(f"✅ Зміни знайдено для {name}")
        else:
            msg = (
                f"✅ <b>{name}</b> додано до моніторингу\n"
                f"🔗 <a href=\"{url}\">Chrome Web Store</a>\n\n"
                f"⭐ Рейтинг: <b>{data['rating']}</b>\n"
                f"📝 Відгуки: <b>{data['reviews']}</b>\n"
                f"👥 Користувачі: <b>{data['users']}</b>"
            )
            send_telegram_message(msg)

        time.sleep(3)

    if SEND_SUMMARY_AFTER_RUN:
        lines = []
        for ext in EXTENSIONS:
            n = ext["name"]
            d = current_data.get(n, {})
            lines.append(f"• <b>{n}</b>: ⭐ {d.get('rating','N/A')} | 📝 {d.get('reviews','N/A')} | 👥 {d.get('users','N/A')}")
        summary = "📊 <b>Підсумок перевірки</b>\n\n" + "\n".join(lines)
        send_telegram_message(summary)

    save_data(current_data)
    print("✅ Перевірка завершена\n")

def handle_start_command():
    """Обробка команди /start - показує останні дані"""
    previous_data = load_previous_data()
    
    if not previous_data:
        msg = "👋 Вітаю!\n\n⏳ Перевірка ще не проводилась.\nНаступна перевірка о 9:00, 13:00, 17:00 або 23:00 (Київський час)"
    else:
        lines = ["📊 <b>Остання перевірка</b>\n"]
        for ext in EXTENSIONS:
            n = ext["name"]
            d = previous_data.get(n, {})
            url = ext["url"]
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
        msg = "\n".join(lines)
    
    send_telegram_message(msg)

# Глобальна змінна для відстеження останнього update_id
last_update_id = 0

def check_telegram_updates():
    """Перевірка нових повідомлень від користувачів"""
    global last_update_id
    
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
        params = {"offset": last_update_id + 1, "timeout": 5}
        resp = SESSION.get(url, params=params, timeout=10)
        data = resp.json()
        
        if data.get("ok") and data.get("result"):
            for update in data["result"]:
                last_update_id = max(last_update_id, update.get("update_id", 0))
                
                message = update.get("message", {})
                text = message.get("text", "")
                chat_id = str(message.get("chat", {}).get("id", ""))
                
                # Відповідаємо тільки вашому chat_id
                if text.strip() == "/start" and chat_id == CHAT_ID:
                    print(f"📱 Отримано команду /start від {chat_id}")
                    handle_start_command()
    except Exception as e:
        print(f"Помилка перевірки команд: {e}")

def main():
    global last_run_hour

    print("🤖 Chrome Extension Monitor Bot запущено!")
    send_telegram_message("🤖 Бот моніторингу розширень запущено.\n\n💡 Натисніть /start щоб побачити останні дані")

    try:
        check_extensions()
    except Exception as e:
        send_telegram_message(f"⚠️ Помилка першої перевірки: {e}")

    while True:
        now = datetime.now()
        if now.hour in CHECK_HOURS and now.minute == 0 and now.hour != last_run_hour:
            print(f"\n⏱ Запуск перевірки: {now.strftime('%H:%M')}")
            try:
                check_extensions()
            except Exception as e:
                send_telegram_message(f"⚠️ Помилка виконання: {e}")
            last_run_hour = now.hour

        time.sleep(30)

if __name__ == "__main__":
    main()
