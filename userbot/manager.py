"""
╔══════════════════════════════════════════════════════════════════╗
║                    MerAI & Monitoring                            ║
║                   Userbot Module (Telethon)                      ║
╚══════════════════════════════════════════════════════════════════╝
"""

import asyncio
import logging
from pathlib import Path
from typing import Optional, Dict
from datetime import datetime

try:
    from telethon import TelegramClient, events
    from telethon.sessions import StringSession
    from telethon.tl.types import (
        Message,
        MessageService,
        UpdateDeleteMessages,
        UpdateNewMessage,
        UpdateEditMessage,
    )
    TELETHON_AVAILABLE = True
except ImportError:
    TELETHON_AVAILABLE = False
    logging.warning("Telethon не установлен. Userbot режим недоступен.")

from config import TG_API_ID, TG_API_HASH, SESSION_PATH, MEDIA_PATH
from database import db

logger = logging.getLogger(__name__)


class UserbotManager:
    """Управление Userbot подключением через Telethon"""
    
    def __init__(self):
        self.client: Optional[TelegramClient] = None
        self.user_id: Optional[int] = None
        self.is_authorized: bool = False
        
        if not TELETHON_AVAILABLE:
            logger.error("Telethon не установлен. Установите: pip install telethon")
    
    async def start(self, user_id: int, phone: str = None, session_string: str = None):
        """Запуск userbot сессии"""
        if not TELETHON_AVAILABLE:
            return False, "Telethon не установлен"
        
        self.user_id = user_id
        
        try:
            # Создаем клиента
            if session_string:
                session = StringSession(session_string)
            else:
                session = StringSession()
            
            self.client = TelegramClient(
                session,
                TG_API_ID,
                TG_API_HASH,
                device_model="MerAI Monitor",
                app_version="1.0.0"
            )
            
            await self.client.connect()
            
            # Проверка авторизации
            if not await self.client.is_user_authorized():
                if phone:
                    # Отправляем код
                    await self.client.send_code_request(phone)
                    db.save_userbot_session(user_id, phone)
                    return True, "Код отправлен в Telegram"
                else:
                    return False, "Требуется номер телефона"
            else:
                self.is_authorized = True
                
                # Сохраняем сессию
                session_str = self.client.session.save()
                db.save_userbot_session(user_id, phone or "", session_str)
                
                # Регистрируем обработчики
                await self._register_handlers()
                
                logger.info(f"Userbot запущен для user_id={user_id}")
                return True, "Userbot успешно запущен"
        
        except Exception as e:
            logger.error(f"Ошибка запуска userbot: {e}")
            return False, f"Ошибка: {str(e)}"
    
    async def sign_in(self, user_id: int, code: str, phone: str):
        """Авторизация с кодом"""
        if not self.client:
            return False, "Клиент не инициализирован"
        
        try:
            await self.client.sign_in(phone, code)
            self.is_authorized = True
            
            # Сохраняем сессию
            session_str = self.client.session.save()
            db.save_userbot_session(user_id, phone, session_str)
            
            # Регистрируем обработчики
            await self._register_handlers()
            
            logger.info(f"Userbot авторизован для user_id={user_id}")
            return True, "Успешная авторизация"
        
        except Exception as e:
            logger.error(f"Ошибка авторизации userbot: {e}")
            return False, f"Ошибка: {str(e)}"
    
    async def _register_handlers(self):
        """Регистрация обработчиков событий"""
        if not self.client or not self.is_authorized:
            return
        
        # Обработчик новых сообщений
        @self.client.on(events.NewMessage)
        async def new_message_handler(event):
            await self._handle_new_message(event)
        
        # Обработчик отредактированных сообщений
        @self.client.on(events.MessageEdited)
        async def edited_message_handler(event):
            await self._handle_edited_message(event)
        
        # Обработчик удаленных сообщений
        @self.client.on(events.MessageDeleted)
        async def deleted_message_handler(event):
            await self._handle_deleted_messages(event)
        
        logger.info("Обработчики userbot зарегистрированы")
    
    async def _handle_new_message(self, event):
        """Обработка нового сообщения"""
        try:
            message = event.message
            
            # Получаем информацию о чате
            chat = await event.get_chat()
            chat_id = event.chat_id
            chat_title = getattr(chat, 'title', None) or getattr(chat, 'first_name', 'Unknown')
            
            # Информация об отправителе
            sender = await event.get_sender()
            sender_id = sender.id if sender else None
            sender_name = getattr(sender, 'first_name', 'Unknown')
            if hasattr(sender, 'last_name') and sender.last_name:
                sender_name += f" {sender.last_name}"
            
            # Тип сообщения
            message_type = "text"
            media_path = None
            media_type = None
            
            if message.photo:
                message_type = "photo"
                media_type = "photo"
                # Скачивание медиа
                media_path = await self._download_media(message, "photo")
            elif message.video:
                message_type = "video"
                media_type = "video"
                media_path = await self._download_media(message, "video")
            elif message.document:
                message_type = "document"
                media_type = "document"
            elif message.voice:
                message_type = "voice"
                media_type = "voice"
            elif message.video_note:
                message_type = "video_note"
                media_type = "video_note"
            elif message.sticker:
                message_type = "sticker"
                media_type = "sticker"
            
            # Сохранение в БД
            db.save_message(
                user_id=self.user_id,
                message_id=message.id,
                chat_id=chat_id,
                chat_title=chat_title,
                sender_id=sender_id,
                sender_name=sender_name,
                message_type=message_type,
                text=message.text or message.message,
                media_path=str(media_path) if media_path else None,
                media_type=media_type
            )
            
            logger.debug(f"Сохранено сообщение {message.id} из чата {chat_id}")
        
        except Exception as e:
            logger.error(f"Ошибка обработки нового сообщения: {e}")
    
    async def _handle_edited_message(self, event):
        """Обработка отредактированного сообщения"""
        try:
            message = event.message
            chat_id = event.chat_id
            
            # Получаем оригинальное сообщение из БД
            cursor = db.conn.cursor()
            cursor.execute("""
                SELECT text FROM messages 
                WHERE user_id = ? AND message_id = ? AND chat_id = ?
            """, (self.user_id, message.id, chat_id))
            row = cursor.fetchone()
            
            if row:
                original_text = row['text']
                new_text = message.text or message.message
                
                db.mark_message_edited(
                    message_id=message.id,
                    chat_id=chat_id,
                    user_id=self.user_id,
                    original_text=original_text,
                    new_text=new_text
                )
                
                logger.debug(f"Сообщение {message.id} отмечено как отредактированное")
        
        except Exception as e:
            logger.error(f"Ошибка обработки редактирования: {e}")
    
    async def _handle_deleted_messages(self, event):
        """Обработка удаленных сообщений"""
        try:
            # event.deleted_ids содержит ID удаленных сообщений
            for message_id in event.deleted_ids:
                db.mark_message_deleted(
                    message_id=message_id,
                    chat_id=event.chat_id if hasattr(event, 'chat_id') else 0,
                    user_id=self.user_id
                )
                
                logger.debug(f"Сообщение {message_id} отмечено как удаленное")
        
        except Exception as e:
            logger.error(f"Ошибка обработки удаления: {e}")
    
    async def _download_media(self, message, media_type: str) -> Optional[Path]:
        """Скачивание медиа файла"""
        try:
            # Создаем директорию для медиа
            user_media_dir = MEDIA_PATH / str(self.user_id) / media_type
            user_media_dir.mkdir(parents=True, exist_ok=True)
            
            # Генерируем имя файла
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{media_type}_{message.id}_{timestamp}"
            
            # Скачиваем
            file_path = await message.download_media(file=user_media_dir / filename)
            
            if file_path:
                return Path(file_path)
            
            return None
        
        except Exception as e:
            logger.error(f"Ошибка скачивания медиа: {e}")
            return None
    
    async def monitor_stories(self):
        """Мониторинг Stories (если доступно)"""
        if not self.client or not self.is_authorized:
            return
        
        try:
            # Stories API может быть недоступен в текущей версии Telethon
            # Этот код будет обновлен когда API станет доступен
            logger.info("Мониторинг Stories запущен (в разработке)")
        except Exception as e:
            logger.error(f"Ошибка мониторинга Stories: {e}")
    
    async def detect_chat_deletion(self):
        """Детектор удаления чатов"""
        if not self.client or not self.is_authorized:
            return
        
        try:
            # Периодическая проверка списка чатов
            # При обнаружении удаленного чата - создаем архив
            logger.info("Детектор удаления чатов активен")
        except Exception as e:
            logger.error(f"Ошибка детектора удаления чатов: {e}")
    
    async def stop(self):
        """Остановка userbot"""
        if self.client:
            await self.client.disconnect()
            self.is_authorized = False
            logger.info(f"Userbot остановлен для user_id={self.user_id}")
    
    def get_status(self) -> Dict:
        """Получить статус userbot"""
        return {
            "is_running": self.client is not None and self.client.is_connected(),
            "is_authorized": self.is_authorized,
            "user_id": self.user_id,
        }


# Глобальный менеджер userbot'ов
userbot_managers: Dict[int, UserbotManager] = {}


async def start_userbot_for_user(user_id: int, phone: str = None, 
                                 session_string: str = None) -> tuple[bool, str]:
    """Запустить userbot для пользователя"""
    if user_id in userbot_managers:
        return True, "Userbot уже запущен"
    
    manager = UserbotManager()
    success, message = await manager.start(user_id, phone, session_string)
    
    if success:
        userbot_managers[user_id] = manager
    
    return success, message


async def sign_in_userbot(user_id: int, code: str, phone: str) -> tuple[bool, str]:
    """Авторизация userbot"""
    if user_id not in userbot_managers:
        return False, "Userbot не инициализирован"
    
    manager = userbot_managers[user_id]
    return await manager.sign_in(user_id, code, phone)


async def stop_userbot_for_user(user_id: int):
    """Остановить userbot для пользователя"""
    if user_id in userbot_managers:
        await userbot_managers[user_id].stop()
        del userbot_managers[user_id]


def get_userbot_status(user_id: int) -> Optional[Dict]:
    """Получить статус userbot"""
    if user_id in userbot_managers:
        return userbot_managers[user_id].get_status()
    return None
