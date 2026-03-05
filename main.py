"""
╔══════════════════════════════════════════════════════════════════╗
║                    MerAI & Monitoring                            ║
║               Main Application Entry Point                       ║
╚══════════════════════════════════════════════════════════════════╝
"""

import asyncio
import logging
import sys
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

# Добавляем путь к модулям
sys.path.insert(0, str(Path(__file__).parent))

from config import (
    BOT_TOKEN,
    BRAND_NAME,
    BRAND_EMOJI,
    LOG_LEVEL,
    LOG_FORMAT,
    LOG_FILE,
    VERSION,
    BUILD_DATE,
)
from database import db
from bot.handlers import get_router as get_bot_router
from bot.additional_handlers import get_additional_router
from admin.handlers import get_admin_router

# Настройка логирования
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format=LOG_FORMAT,
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


async def on_startup(bot: Bot):
    """Действия при запуске бота"""
    logger.info(f"╔{'═' * 66}╗")
    logger.info(f"║{BRAND_EMOJI} {BRAND_NAME:^62} {BRAND_EMOJI}║")
    logger.info(f"║{'Advanced Telegram Monitoring System':^66}║")
    logger.info(f"║{f'Version {VERSION} - Build {BUILD_DATE}':^66}║")
    logger.info(f"╚{'═' * 66}╝")
    
    # Получаем информацию о боте
    bot_info = await bot.get_me()
    logger.info(f"Бот запущен: @{bot_info.username} (ID: {bot_info.id})")
    
    # Проверка базы данных
    stats = db.get_statistics()
    logger.info(f"База данных подключена. Пользователей: {stats.get('total_users', 0)}")
    
    # Логируем запуск
    db.log_action("system_startup", f"Система запущена v{VERSION}")
    
    logger.info("✅ Система готова к работе!")


async def on_shutdown(bot: Bot):
    """Действия при остановке бота"""
    logger.info("Остановка системы...")
    
    # Закрываем соединение с БД
    db.close()
    
    # Логируем остановку
    db.log_action("system_shutdown", "Система остановлена")
    
    logger.info("👋 Система остановлена")


async def main():
    """Главная функция запуска"""
    try:
        # Создаем бота
        bot = Bot(
            token=BOT_TOKEN,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML)
        )
        
        # Создаем диспетчер
        dp = Dispatcher(storage=MemoryStorage())
        
        # Регистрируем роутеры
        dp.include_router(get_bot_router())
        dp.include_router(get_additional_router())
        dp.include_router(get_admin_router())
        
        # Регистрируем startup/shutdown
        dp.startup.register(on_startup)
        dp.shutdown.register(on_shutdown)
        
        # Запускаем поллинг
        logger.info("Запуск polling...")
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    
    except KeyboardInterrupt:
        logger.info("Получен сигнал остановки (Ctrl+C)")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}", exc_info=True)
    finally:
        logger.info("Завершение работы...")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.critical(f"Фатальная ошибка при запуске: {e}", exc_info=True)
        sys.exit(1)
