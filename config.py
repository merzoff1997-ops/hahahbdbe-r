"""
╔══════════════════════════════════════════════════════════════════╗
║                    MerAI & Monitoring                            ║
║              Advanced Telegram Monitoring System                 ║
║                     Configuration Module                         ║
╚══════════════════════════════════════════════════════════════════╝
"""

import os
from pathlib import Path

# ═══════════════════════════════════════════════════════════
#  ОСНОВНАЯ КОНФИГУРАЦИЯ
# ═══════════════════════════════════════════════════════════

# Telegram Bot API
BOT_TOKEN = os.getenv("BOT_TOKEN", "8505484152:AAHXEFt0lyeMK5ZSJHRYpdPhhFJ0s142Bng")

# Telegram API для Userbot (Telethon)
TG_API_ID = int(os.getenv("TG_API_ID", "38362277"))
TG_API_HASH = os.getenv("TG_API_HASH", "1e1fbdde4c349760db99c9374adf956e")

# Администратор
ADMIN_ID = int(os.getenv("ADMIN_ID", "7785371505"))

# Пути
BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "database" / "merai.db"
MEDIA_PATH = BASE_DIR / "media"
LOGS_PATH = BASE_DIR / "logs"
SESSION_PATH = BASE_DIR / "userbot" / "session.session"

# Создание необходимых директорий
for path in [DB_PATH.parent, MEDIA_PATH, LOGS_PATH, SESSION_PATH.parent]:
    path.mkdir(parents=True, exist_ok=True)

# ═══════════════════════════════════════════════════════════
#  БРЕНДИНГ
# ═══════════════════════════════════════════════════════════

BRAND_NAME = "MerAI & Monitoring"
BRAND_EMOJI = "🤖"
BRAND_DESCRIPTION = "Умный мониторинг ваших Telegram чатов"

# Брендинг управляется через БД, но это значения по умолчанию
DEFAULT_BRANDING = {
    "welcome_message": f"{BRAND_EMOJI} Добро пожаловать в {BRAND_NAME}!\n\nМы поможем вам отслеживать все изменения в ваших чатах.",
    "footer_text": f"\n\n💎 Powered by {BRAND_NAME}",
    "primary_color": "#6C5CE7",  # Фиолетовый
    "secondary_color": "#A29BFE",  # Светло-фиолетовый
}

# ═══════════════════════════════════════════════════════════
#  ПОДПИСКИ И PRICING (Telegram Stars)
# ═══════════════════════════════════════════════════════════

# 1 Stars ≈ 2 рубля (примерный курс)
STARS_TO_RUB = 2

SUBSCRIPTION_PLANS = {
    "trial": {
        "name": "🎁 Пробный период",
        "duration_days": 3,
        "stars_price": 0,
        "rub_equivalent": 0,
        "features": ["Базовый мониторинг", "До 100 сообщений"],
        "max_messages": 100,
    },
    "basic": {
        "name": "⭐ Базовый",
        "duration_days": 30,
        "stars_price": 50,  # 100 рублей
        "rub_equivalent": 100,
        "features": ["Мониторинг до 1000 сообщений", "Экспорт данных", "Поиск по сообщениям"],
        "max_messages": 1000,
    },
    "premium": {
        "name": "💎 Премиум",
        "duration_days": 30,
        "stars_price": 150,  # 300 рублей
        "rub_equivalent": 300,
        "features": [
            "Безлимитный мониторинг",
            "Dual Mode (Bot + Userbot)",
            "Детектор контактов",
            "Приоритетная поддержка",
            "Чеклисты и теги"
        ],
        "max_messages": -1,  # Безлимит
    },
    "lifetime": {
        "name": "👑 Навсегда",
        "duration_days": 36500,  # 100 лет
        "stars_price": 500,  # 1000 рублей
        "rub_equivalent": 1000,
        "features": [
            "Все функции Премиум",
            "Lifetime доступ",
            "VIP поддержка",
            "Эксклюзивные функции"
        ],
        "max_messages": -1,
    },
}

# Бонус за приглашение бота
BONUS_DAYS_FOR_BOT_ADD = 7

# ═══════════════════════════════════════════════════════════
#  DUAL MODE НАСТРОЙКИ
# ═══════════════════════════════════════════════════════════

# Режимы работы
class MonitoringMode:
    BUSINESS_API = "business"  # Через Business API (требует Telegram Premium)
    USERBOT = "userbot"        # Через userbot (работает везде)
    DUAL = "dual"              # Оба режима одновременно

DEFAULT_MODE = MonitoringMode.BUSINESS_API

# ═══════════════════════════════════════════════════════════
#  ОГРАНИЧЕНИЯ TELEGRAM
# ═══════════════════════════════════════════════════════════

# Business API ограничения
BUSINESS_API_LIMITATIONS = {
    "no_self_destruct_messages": True,  # Не может сохранять сообщения с таймером
    "no_view_once_messages": True,      # Не может сохранять сообщения с лимитом просмотра
    "no_secret_chats": True,            # Не работает в секретных чатах
    "no_chat_deletion_event": True,     # Не получает событие удаления чата
}

# Userbot может обходить некоторые ограничения
USERBOT_CAPABILITIES = {
    "can_monitor_secret_chats": False,  # Секретные чаты все равно не доступны
    "can_detect_chat_deletion": True,   # Может отследить удаление чата
    "can_save_media_from_deleted": True,  # Может сохранить медиа из удаленных сообщений
}

# ═══════════════════════════════════════════════════════════
#  ФУНКЦИИ И ЛИМИТЫ
# ═══════════════════════════════════════════════════════════

# Максимальные размеры файлов
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB

# Автоархивация
AUTO_ARCHIVE_THRESHOLD = 5  # При удалении 5+ сообщений создавать архив

# Детектор контактов
CONTACT_DETECTOR_PATTERNS = {
    "phone": r"\+?\d{1,3}[-.\s]?\(?\d{1,4}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,9}",
    "email": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
    "telegram": r"@[a-zA-Z0-9_]{5,32}",
    "url": r"https?://[^\s]+",
}

# Чеклисты (нативные Telegram чеклисты через Bot API)
CHECKLIST_MAX_ITEMS = 20

# ═══════════════════════════════════════════════════════════
#  TELEGRAM PREMIUM GIFTS
# ═══════════════════════════════════════════════════════════

# Подарки Telegram Premium (через paid media)
PREMIUM_GIFTS = {
    "1_month": {
        "stars_price": 250,
        "rub_equivalent": 500,
        "duration_months": 1,
    },
    "3_months": {
        "stars_price": 650,
        "rub_equivalent": 1300,
        "duration_months": 3,
    },
    "6_months": {
        "stars_price": 1200,
        "rub_equivalent": 2400,
        "duration_months": 6,
    },
}

# ═══════════════════════════════════════════════════════════
#  СТОРИС
# ═══════════════════════════════════════════════════════════

# Настройки для Stories (если доступны через API)
STORIES_ENABLED = True
STORIES_AUTO_SAVE = True  # Автоматически сохранять Stories

# ═══════════════════════════════════════════════════════════
#  ЛОГИРОВАНИЕ
# ═══════════════════════════════════════════════════════════

LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_FILE = LOGS_PATH / "merai.log"

# ═══════════════════════════════════════════════════════════
#  БЕЗОПАСНОСТЬ
# ═══════════════════════════════════════════════════════════

# Шифрование медиа (опционально)
ENCRYPT_MEDIA = False
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY", "default_key_change_in_production")

# ═══════════════════════════════════════════════════════════
#  ВЕБХУКИ И УВЕДОМЛЕНИЯ
# ═══════════════════════════════════════════════════════════

# Webhook для админ панели (если используется)
WEBHOOK_ENABLED = False
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST", "0.0.0.0")
WEBHOOK_PORT = int(os.getenv("WEBHOOK_PORT", "8080"))

# ═══════════════════════════════════════════════════════════
#  ЭКСПОРТ И БЭКАПЫ
# ═══════════════════════════════════════════════════════════

EXPORT_FORMATS = ["json", "html", "csv"]
AUTO_BACKUP_ENABLED = False
BACKUP_SCHEDULE = "0 3 * * *"  # Каждый день в 3:00

# ═══════════════════════════════════════════════════════════
#  DEVELOPMENT / PRODUCTION
# ═══════════════════════════════════════════════════════════

DEBUG = os.getenv("DEBUG", "False").lower() == "true"
ENVIRONMENT = os.getenv("ENVIRONMENT", "production")

# ═══════════════════════════════════════════════════════════
#  ВЕРСИЯ
# ═══════════════════════════════════════════════════════════

VERSION = "1.0.0"
BUILD_DATE = "2026-03-05"
