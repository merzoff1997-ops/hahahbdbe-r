"""
╔══════════════════════════════════════════════════════════════════╗
║                    MerAI & Monitoring                            ║
║                   Database Management Module                     ║
╚══════════════════════════════════════════════════════════════════╝
"""

import asyncio
import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, List, Any
import logging

from config import DB_PATH, SUBSCRIPTION_PLANS

logger = logging.getLogger(__name__)


class Database:
    """Управление базой данных SQLite"""

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.conn = None
        self._ensure_db()

    def _ensure_db(self):
        """Создание БД и всех таблиц"""
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()
        logger.info(f"База данных инициализирована: {self.db_path}")

    def _create_tables(self):
        """Создание всех необходимых таблиц"""
        cursor = self.conn.cursor()

        # Таблица пользователей
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                language_code TEXT DEFAULT 'ru',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_activity TIMESTAMP,
                is_blocked INTEGER DEFAULT 0,
                monitoring_mode TEXT DEFAULT 'business',
                trial_used INTEGER DEFAULT 0
            )
        """)

        # Таблица подписок
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                plan_type TEXT NOT NULL,
                start_date TIMESTAMP NOT NULL,
                end_date TIMESTAMP NOT NULL,
                is_active INTEGER DEFAULT 1,
                stars_paid INTEGER DEFAULT 0,
                auto_renew INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)

        # Таблица транзакций (Stars платежи)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                transaction_type TEXT NOT NULL,
                stars_amount INTEGER NOT NULL,
                rub_equivalent REAL,
                description TEXT,
                telegram_payment_id TEXT,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)

        # Таблица бизнес-подключений
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS business_connections (
                id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                business_user_id INTEGER,
                is_enabled INTEGER DEFAULT 1,
                can_reply INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)

        # Таблица сохраненных сообщений
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                message_id INTEGER NOT NULL,
                chat_id INTEGER NOT NULL,
                chat_title TEXT,
                sender_id INTEGER,
                sender_name TEXT,
                message_type TEXT NOT NULL,
                text TEXT,
                media_path TEXT,
                media_type TEXT,
                is_deleted INTEGER DEFAULT 0,
                is_edited INTEGER DEFAULT 0,
                original_text TEXT,
                deleted_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)

        # Таблица детектора контактов
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS detected_contacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                message_id INTEGER,
                contact_type TEXT NOT NULL,
                contact_value TEXT NOT NULL,
                chat_id INTEGER,
                detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id),
                FOREIGN KEY (message_id) REFERENCES messages(id)
            )
        """)

        # Таблица чеклистов
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS checklists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)

        # Таблица элементов чеклистов
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS checklist_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                checklist_id INTEGER NOT NULL,
                text TEXT NOT NULL,
                is_completed INTEGER DEFAULT 0,
                position INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (checklist_id) REFERENCES checklists(id) ON DELETE CASCADE
            )
        """)

        # Таблица подключенных ботов (для бонусной системы)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS connected_bots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                bot_token TEXT NOT NULL,
                bot_username TEXT,
                bot_id INTEGER,
                is_active INTEGER DEFAULT 1,
                bonus_days_granted INTEGER DEFAULT 7,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)

        # Таблица настроек брендинга (для администратора)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS branding_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                setting_key TEXT UNIQUE NOT NULL,
                setting_value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Таблица Stories (если доступно через API)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS stories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                story_id INTEGER NOT NULL,
                sender_id INTEGER,
                sender_name TEXT,
                media_path TEXT,
                media_type TEXT,
                caption TEXT,
                expires_at TIMESTAMP,
                saved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)

        # Таблица логов действий (для админ панели)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS action_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                action_type TEXT NOT NULL,
                description TEXT,
                metadata TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Таблица userbot сессий
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS userbot_sessions (
                user_id INTEGER PRIMARY KEY,
                phone_number TEXT,
                session_string TEXT,
                is_authorized INTEGER DEFAULT 0,
                auth_code TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)

        self.conn.commit()
        logger.info("Все таблицы созданы успешно")

    # ═══════════════════════════════════════════════════════════
    #  ПОЛЬЗОВАТЕЛИ
    # ═══════════════════════════════════════════════════════════

    def add_user(self, user_id: int, username: str = None, first_name: str = None,
                 last_name: str = None, language_code: str = "ru") -> bool:
        """Добавить нового пользователя"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT OR IGNORE INTO users 
                (user_id, username, first_name, last_name, language_code, last_activity)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, username, first_name, last_name, language_code, datetime.now()))
            self.conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Ошибка добавления пользователя {user_id}: {e}")
            return False

    def get_user(self, user_id: int) -> Optional[Dict]:
        """Получить данные пользователя"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def update_user_activity(self, user_id: int):
        """Обновить время последней активности"""
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE users SET last_activity = ? WHERE user_id = ?
        """, (datetime.now(), user_id))
        self.conn.commit()

    def block_user(self, user_id: int, blocked: bool = True):
        """Заблокировать/разблокировать пользователя"""
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE users SET is_blocked = ? WHERE user_id = ?
        """, (1 if blocked else 0, user_id))
        self.conn.commit()

    def is_user_blocked(self, user_id: int) -> bool:
        """Проверить блокировку пользователя"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT is_blocked FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        return bool(row['is_blocked']) if row else False

    def get_all_users(self) -> List[Dict]:
        """Получить всех пользователей"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM users ORDER BY created_at DESC")
        return [dict(row) for row in cursor.fetchall()]

    # ═══════════════════════════════════════════════════════════
    #  ПОДПИСКИ
    # ═══════════════════════════════════════════════════════════

    def create_subscription(self, user_id: int, plan_type: str, 
                          duration_days: int = None, stars_paid: int = 0,
                          auto_renew: bool = False) -> bool:
        """Создать подписку"""
        try:
            if plan_type not in SUBSCRIPTION_PLANS:
                return False

            plan = SUBSCRIPTION_PLANS[plan_type]
            days = duration_days or plan['duration_days']

            start_date = datetime.now()
            end_date = start_date + timedelta(days=days)

            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO subscriptions 
                (user_id, plan_type, start_date, end_date, stars_paid, auto_renew)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, plan_type, start_date, end_date, stars_paid, 
                  1 if auto_renew else 0))
            self.conn.commit()

            # Отметить trial как использованный
            if plan_type == "trial":
                cursor.execute("UPDATE users SET trial_used = 1 WHERE user_id = ?", (user_id,))
                self.conn.commit()

            return True
        except Exception as e:
            logger.error(f"Ошибка создания подписки для {user_id}: {e}")
            return False

    def get_active_subscription(self, user_id: int) -> Optional[Dict]:
        """Получить активную подписку пользователя"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM subscriptions 
            WHERE user_id = ? AND is_active = 1 AND end_date > ?
            ORDER BY end_date DESC LIMIT 1
        """, (user_id, datetime.now()))
        row = cursor.fetchone()
        return dict(row) if row else None

    def extend_subscription(self, user_id: int, days: int):
        """Продлить подписку на N дней"""
        subscription = self.get_active_subscription(user_id)
        if subscription:
            cursor = self.conn.cursor()
            new_end_date = datetime.fromisoformat(subscription['end_date']) + timedelta(days=days)
            cursor.execute("""
                UPDATE subscriptions SET end_date = ? WHERE id = ?
            """, (new_end_date, subscription['id']))
            self.conn.commit()

    def deactivate_subscription(self, subscription_id: int):
        """Деактивировать подписку"""
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE subscriptions SET is_active = 0 WHERE id = ?
        """, (subscription_id,))
        self.conn.commit()

    def has_trial_used(self, user_id: int) -> bool:
        """Проверить использовал ли пользователь пробный период"""
        user = self.get_user(user_id)
        return bool(user['trial_used']) if user else False

    # ═══════════════════════════════════════════════════════════
    #  ТРАНЗАКЦИИ
    # ═══════════════════════════════════════════════════════════

    def add_transaction(self, user_id: int, transaction_type: str, 
                       stars_amount: int, rub_equivalent: float = None,
                       description: str = None, telegram_payment_id: str = None) -> int:
        """Добавить транзакцию"""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO transactions 
            (user_id, transaction_type, stars_amount, rub_equivalent, description, telegram_payment_id, status)
            VALUES (?, ?, ?, ?, ?, ?, 'completed')
        """, (user_id, transaction_type, stars_amount, rub_equivalent, description, telegram_payment_id))
        self.conn.commit()
        return cursor.lastrowid

    def get_user_transactions(self, user_id: int) -> List[Dict]:
        """Получить транзакции пользователя"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM transactions WHERE user_id = ? ORDER BY created_at DESC
        """, (user_id,))
        return [dict(row) for row in cursor.fetchall()]

    # ═══════════════════════════════════════════════════════════
    #  СООБЩЕНИЯ
    # ═══════════════════════════════════════════════════════════

    def save_message(self, user_id: int, message_id: int, chat_id: int,
                    chat_title: str = None, sender_id: int = None, 
                    sender_name: str = None, message_type: str = "text",
                    text: str = None, media_path: str = None, 
                    media_type: str = None) -> int:
        """Сохранить сообщение"""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO messages 
            (user_id, message_id, chat_id, chat_title, sender_id, sender_name, 
             message_type, text, media_path, media_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (user_id, message_id, chat_id, chat_title, sender_id, sender_name,
              message_type, text, media_path, media_type))
        self.conn.commit()
        return cursor.lastrowid

    def mark_message_deleted(self, message_id: int, chat_id: int, user_id: int):
        """Отметить сообщение как удаленное"""
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE messages SET is_deleted = 1, deleted_at = ?
            WHERE message_id = ? AND chat_id = ? AND user_id = ?
        """, (datetime.now(), message_id, chat_id, user_id))
        self.conn.commit()

    def mark_message_edited(self, message_id: int, chat_id: int, user_id: int,
                          original_text: str, new_text: str):
        """Отметить сообщение как отредактированное"""
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE messages SET is_edited = 1, original_text = ?, text = ?
            WHERE message_id = ? AND chat_id = ? AND user_id = ?
        """, (original_text, new_text, message_id, chat_id, user_id))
        self.conn.commit()

    def get_deleted_messages(self, user_id: int, chat_id: int = None) -> List[Dict]:
        """Получить удаленные сообщения"""
        cursor = self.conn.cursor()
        if chat_id:
            cursor.execute("""
                SELECT * FROM messages 
                WHERE user_id = ? AND chat_id = ? AND is_deleted = 1
                ORDER BY deleted_at DESC
            """, (user_id, chat_id))
        else:
            cursor.execute("""
                SELECT * FROM messages 
                WHERE user_id = ? AND is_deleted = 1
                ORDER BY deleted_at DESC
            """, (user_id,))
        return [dict(row) for row in cursor.fetchall()]

    def get_edited_messages(self, user_id: int, chat_id: int = None) -> List[Dict]:
        """Получить отредактированные сообщения"""
        cursor = self.conn.cursor()
        if chat_id:
            cursor.execute("""
                SELECT * FROM messages 
                WHERE user_id = ? AND chat_id = ? AND is_edited = 1
                ORDER BY created_at DESC
            """, (user_id, chat_id))
        else:
            cursor.execute("""
                SELECT * FROM messages 
                WHERE user_id = ? AND is_edited = 1
                ORDER BY created_at DESC
            """, (user_id,))
        return [dict(row) for row in cursor.fetchall()]

    def get_message_count(self, user_id: int) -> int:
        """Получить количество сохраненных сообщений"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM messages WHERE user_id = ?", (user_id,))
        return cursor.fetchone()['count']

    # ═══════════════════════════════════════════════════════════
    #  ДЕТЕКТОР КОНТАКТОВ
    # ═══════════════════════════════════════════════════════════

    def save_detected_contact(self, user_id: int, message_id: int, 
                             contact_type: str, contact_value: str,
                             chat_id: int = None):
        """Сохранить обнаруженный контакт"""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO detected_contacts (user_id, message_id, contact_type, contact_value, chat_id)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, message_id, contact_type, contact_value, chat_id))
        self.conn.commit()

    def get_detected_contacts(self, user_id: int, contact_type: str = None) -> List[Dict]:
        """Получить обнаруженные контакты"""
        cursor = self.conn.cursor()
        if contact_type:
            cursor.execute("""
                SELECT * FROM detected_contacts 
                WHERE user_id = ? AND contact_type = ?
                ORDER BY detected_at DESC
            """, (user_id, contact_type))
        else:
            cursor.execute("""
                SELECT * FROM detected_contacts 
                WHERE user_id = ?
                ORDER BY detected_at DESC
            """, (user_id,))
        return [dict(row) for row in cursor.fetchall()]

    # ═══════════════════════════════════════════════════════════
    #  ЧЕКЛИСТЫ
    # ═══════════════════════════════════════════════════════════

    def create_checklist(self, user_id: int, title: str) -> int:
        """Создать чеклист"""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO checklists (user_id, title) VALUES (?, ?)
        """, (user_id, title))
        self.conn.commit()
        return cursor.lastrowid

    def add_checklist_item(self, checklist_id: int, text: str, position: int = 0):
        """Добавить элемент в чеклист"""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO checklist_items (checklist_id, text, position)
            VALUES (?, ?, ?)
        """, (checklist_id, text, position))
        self.conn.commit()

    def toggle_checklist_item(self, item_id: int):
        """Переключить состояние элемента чеклиста"""
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE checklist_items 
            SET is_completed = CASE WHEN is_completed = 0 THEN 1 ELSE 0 END
            WHERE id = ?
        """, (item_id,))
        self.conn.commit()

    def get_user_checklists(self, user_id: int) -> List[Dict]:
        """Получить все чеклисты пользователя"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT c.*, 
                   COUNT(ci.id) as total_items,
                   SUM(ci.is_completed) as completed_items
            FROM checklists c
            LEFT JOIN checklist_items ci ON c.id = ci.checklist_id
            WHERE c.user_id = ?
            GROUP BY c.id
            ORDER BY c.created_at DESC
        """, (user_id,))
        return [dict(row) for row in cursor.fetchall()]

    def get_checklist_items(self, checklist_id: int) -> List[Dict]:
        """Получить элементы чеклиста"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM checklist_items 
            WHERE checklist_id = ?
            ORDER BY position, created_at
        """, (checklist_id,))
        return [dict(row) for row in cursor.fetchall()]

    # ═══════════════════════════════════════════════════════════
    #  ПОДКЛЮЧЕННЫЕ БОТЫ (БОНУСНАЯ СИСТЕМА)
    # ═══════════════════════════════════════════════════════════

    def add_connected_bot(self, user_id: int, bot_token: str, 
                         bot_username: str = None, bot_id: int = None) -> int:
        """Добавить подключенного бота"""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO connected_bots (user_id, bot_token, bot_username, bot_id)
            VALUES (?, ?, ?, ?)
        """, (user_id, bot_token, bot_username, bot_id))
        self.conn.commit()
        return cursor.lastrowid

    def get_connected_bots(self, user_id: int) -> List[Dict]:
        """Получить подключенные боты пользователя"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM connected_bots WHERE user_id = ? AND is_active = 1
        """, (user_id,))
        return [dict(row) for row in cursor.fetchall()]

    # ═══════════════════════════════════════════════════════════
    #  БРЕНДИНГ
    # ═══════════════════════════════════════════════════════════

    def set_branding(self, key: str, value: str):
        """Установить настройку брендинга"""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO branding_settings (setting_key, setting_value, updated_at)
            VALUES (?, ?, ?)
        """, (key, value, datetime.now()))
        self.conn.commit()

    def get_branding(self, key: str) -> Optional[str]:
        """Получить настройку брендинга"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT setting_value FROM branding_settings WHERE setting_key = ?
        """, (key,))
        row = cursor.fetchone()
        return row['setting_value'] if row else None

    # ═══════════════════════════════════════════════════════════
    #  ЛОГИ ДЕЙСТВИЙ
    # ═══════════════════════════════════════════════════════════

    def log_action(self, action_type: str, description: str = None, 
                  user_id: int = None, metadata: Dict = None):
        """Логировать действие"""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO action_logs (user_id, action_type, description, metadata)
            VALUES (?, ?, ?, ?)
        """, (user_id, action_type, description, json.dumps(metadata) if metadata else None))
        self.conn.commit()

    def get_action_logs(self, limit: int = 100, user_id: int = None) -> List[Dict]:
        """Получить логи действий"""
        cursor = self.conn.cursor()
        if user_id:
            cursor.execute("""
                SELECT * FROM action_logs WHERE user_id = ?
                ORDER BY created_at DESC LIMIT ?
            """, (user_id, limit))
        else:
            cursor.execute("""
                SELECT * FROM action_logs ORDER BY created_at DESC LIMIT ?
            """, (limit,))
        return [dict(row) for row in cursor.fetchall()]

    # ═══════════════════════════════════════════════════════════
    #  USERBOT СЕССИИ
    # ═══════════════════════════════════════════════════════════

    def save_userbot_session(self, user_id: int, phone_number: str, 
                            session_string: str = None):
        """Сохранить userbot сессию"""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO userbot_sessions 
            (user_id, phone_number, session_string, is_authorized)
            VALUES (?, ?, ?, ?)
        """, (user_id, phone_number, session_string, 1 if session_string else 0))
        self.conn.commit()

    def get_userbot_session(self, user_id: int) -> Optional[Dict]:
        """Получить userbot сессию"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM userbot_sessions WHERE user_id = ?
        """, (user_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    # ═══════════════════════════════════════════════════════════
    #  УТИЛИТЫ
    # ═══════════════════════════════════════════════════════════

    def cleanup_old_messages(self, days: int = 30):
        """Очистка старых сообщений"""
        cutoff_date = datetime.now() - timedelta(days=days)
        cursor = self.conn.cursor()
        cursor.execute("""
            DELETE FROM messages WHERE created_at < ? AND is_deleted = 0 AND is_edited = 0
        """, (cutoff_date,))
        self.conn.commit()
        return cursor.rowcount

    def get_statistics(self, user_id: int = None) -> Dict:
        """Получить статистику"""
        cursor = self.conn.cursor()
        stats = {}

        if user_id:
            # Статистика для конкретного пользователя
            cursor.execute("SELECT COUNT(*) as total FROM messages WHERE user_id = ?", (user_id,))
            stats['total_messages'] = cursor.fetchone()['total']

            cursor.execute("SELECT COUNT(*) as deleted FROM messages WHERE user_id = ? AND is_deleted = 1", (user_id,))
            stats['deleted_messages'] = cursor.fetchone()['deleted']

            cursor.execute("SELECT COUNT(*) as edited FROM messages WHERE user_id = ? AND is_edited = 1", (user_id,))
            stats['edited_messages'] = cursor.fetchone()['edited']
        else:
            # Общая статистика
            cursor.execute("SELECT COUNT(*) as total FROM users")
            stats['total_users'] = cursor.fetchone()['total']

            cursor.execute("SELECT COUNT(*) as active FROM subscriptions WHERE is_active = 1 AND end_date > ?", 
                         (datetime.now(),))
            stats['active_subscriptions'] = cursor.fetchone()['active']

            cursor.execute("SELECT COUNT(*) as total FROM messages")
            stats['total_messages'] = cursor.fetchone()['total']

        return stats

    def close(self):
        """Закрыть соединение с БД"""
        if self.conn:
            self.conn.close()
            logger.info("Соединение с БД закрыто")


# Глобальный экземпляр БД
db = Database()
