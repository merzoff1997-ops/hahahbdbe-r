"""
╔══════════════════════════════════════════════════════════════════╗
║                    MerAI & Monitoring                            ║
║                   Main Bot Handlers Module                       ║
╚══════════════════════════════════════════════════════════════════╝
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message,
    CallbackQuery,
    BusinessConnection,
    BusinessMessagesDeleted,
    PreCheckoutQuery,
    SuccessfulPayment,
)

from config import (
    BOT_TOKEN,
    ADMIN_ID,
    BRAND_NAME,
    BRAND_EMOJI,
    SUBSCRIPTION_PLANS,
    BONUS_DAYS_FOR_BOT_ADD,
    STARS_TO_RUB,
)
from database import db
from bot.keyboards import (
    get_main_menu,
    get_subscription_menu,
    get_admin_menu,
    get_checklist_keyboard,
)
from bot.utils import (
    format_subscription_info,
    check_subscription,
    detect_contacts_in_text,
    create_archive_from_messages,
)

logger = logging.getLogger(__name__)

# Состояния FSM
class BotStates(StatesGroup):
    waiting_for_bot_token = State()
    waiting_for_phone = State()
    waiting_for_code = State()


router = Router()


# ═══════════════════════════════════════════════════════════
#  КОМАНДА /START
# ═══════════════════════════════════════════════════════════

@router.message(CommandStart())
async def cmd_start(message: Message):
    """Обработка команды /start"""
    user = message.from_user
    
    # Регистрация пользователя
    db.add_user(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
        language_code=user.language_code or "ru"
    )
    
    # Логирование
    db.log_action("start", "Пользователь запустил бота", user_id=user.id)
    
    # Проверка блокировки
    if db.is_user_blocked(user.id):
        await message.answer("❌ Вы заблокированы администратором.")
        return
    
    # Приветственное сообщение
    branding_welcome = db.get_branding("welcome_message")
    welcome_text = branding_welcome if branding_welcome else f"""
{BRAND_EMOJI} <b>Добро пожаловать в {BRAND_NAME}!</b>

🎯 Мы поможем вам отслеживать все изменения в ваших Telegram чатах:
• Удаленные сообщения
• Отредактированные сообщения  
• Детектор контактов
• Чеклисты и напоминания
• И многое другое!

<b>Dual Mode:</b>
🤖 Business API - для бизнес-чатов
👤 Userbot - для всех чатов

Выберите действие в меню ниже:
"""
    
    # Проверка активной подписки
    subscription = db.get_active_subscription(user.id)
    if not subscription and not db.has_trial_used(user.id):
        welcome_text += "\n🎁 <b>Доступен пробный период 3 дня!</b>"
    
    await message.answer(
        welcome_text,
        reply_markup=get_main_menu(user.id),
        parse_mode=ParseMode.HTML
    )


# ═══════════════════════════════════════════════════════════
#  ПОДПИСКИ
# ═══════════════════════════════════════════════════════════

@router.callback_query(F.data == "subscriptions")
async def show_subscriptions(callback: CallbackQuery):
    """Показать тарифы подписок"""
    user_id = callback.from_user.id
    
    # Текущая подписка
    subscription = db.get_active_subscription(user_id)
    
    text = f"{BRAND_EMOJI} <b>Подписки {BRAND_NAME}</b>\n\n"
    
    if subscription:
        text += format_subscription_info(subscription) + "\n\n"
    
    text += "<b>Доступные тарифы:</b>\n\n"
    
    for plan_key, plan in SUBSCRIPTION_PLANS.items():
        if plan_key == "trial" and db.has_trial_used(user_id):
            continue
            
        text += f"<b>{plan['name']}</b>\n"
        text += f"💫 {plan['stars_price']} Stars (~{plan['rub_equivalent']} ₽)\n"
        text += f"⏱ {plan['duration_days']} дней\n"
        text += "📋 Возможности:\n"
        for feature in plan['features']:
            text += f"  • {feature}\n"
        text += "\n"
    
    await callback.message.edit_text(
        text,
        reply_markup=get_subscription_menu(user_id),
        parse_mode=ParseMode.HTML
    )


@router.callback_query(F.data.startswith("buy_"))
async def buy_subscription(callback: CallbackQuery):
    """Покупка подписки"""
    user_id = callback.from_user.id
    plan_key = callback.data.split("_")[1]
    
    if plan_key not in SUBSCRIPTION_PLANS:
        await callback.answer("❌ Неверный тариф", show_alert=True)
        return
    
    plan = SUBSCRIPTION_PLANS[plan_key]
    
    # Проверка trial
    if plan_key == "trial":
        if db.has_trial_used(user_id):
            await callback.answer("❌ Пробный период уже использован", show_alert=True)
            return
        
        # Активация trial
        db.create_subscription(user_id, "trial")
        db.log_action("subscription_activated", f"Trial период активирован", user_id=user_id)
        
        await callback.message.edit_text(
            f"🎁 <b>Пробный период активирован!</b>\n\n"
            f"Вы получили 3 дня полного доступа к {BRAND_NAME}.\n"
            f"Используйте это время, чтобы оценить все возможности!",
            parse_mode=ParseMode.HTML,
            reply_markup=get_main_menu(user_id)
        )
        return
    
    # Для платных подписок создаем invoice
    if plan['stars_price'] > 0:
        # Используем Telegram Stars для оплаты
        from aiogram.types import LabeledPrice
        
        prices = [LabeledPrice(label=plan['name'], amount=plan['stars_price'])]
        
        await callback.bot.send_invoice(
            chat_id=user_id,
            title=f"Подписка {plan['name']}",
            description=f"Подписка на {plan['duration_days']} дней\n" + "\n".join(plan['features']),
            payload=f"subscription_{plan_key}",
            provider_token="",  # Для Stars не нужен
            currency="XTR",  # Telegram Stars
            prices=prices,
        )
        
        await callback.answer("💳 Счет отправлен!")


@router.pre_checkout_query()
async def pre_checkout_handler(pre_checkout_query: PreCheckoutQuery):
    """Обработка pre-checkout для Stars"""
    await pre_checkout_query.answer(ok=True)


@router.message(F.successful_payment)
async def successful_payment_handler(message: Message):
    """Обработка успешного платежа"""
    payment = message.successful_payment
    user_id = message.from_user.id
    
    # Извлекаем plan_key из payload
    payload = payment.invoice_payload
    if not payload.startswith("subscription_"):
        return
    
    plan_key = payload.replace("subscription_", "")
    plan = SUBSCRIPTION_PLANS.get(plan_key)
    
    if not plan:
        return
    
    # Создаем подписку
    db.create_subscription(
        user_id=user_id,
        plan_type=plan_key,
        stars_paid=payment.total_amount,
        auto_renew=False
    )
    
    # Записываем транзакцию
    db.add_transaction(
        user_id=user_id,
        transaction_type="subscription",
        stars_amount=payment.total_amount,
        rub_equivalent=plan['rub_equivalent'],
        description=f"Подписка {plan['name']}",
        telegram_payment_id=payment.telegram_payment_charge_id
    )
    
    db.log_action("payment_success", f"Оплата подписки {plan_key}", user_id=user_id)
    
    await message.answer(
        f"✅ <b>Платеж успешно выполнен!</b>\n\n"
        f"Подписка <b>{plan['name']}</b> активирована на {plan['duration_days']} дней.\n\n"
        f"Спасибо за покупку! {BRAND_EMOJI}",
        parse_mode=ParseMode.HTML,
        reply_markup=get_main_menu(user_id)
    )


# ═══════════════════════════════════════════════════════════
#  BUSINESS CONNECTION
# ═══════════════════════════════════════════════════════════

@router.business_connection()
async def on_business_connection(business_connection: BusinessConnection):
    """Обработка подключения Business API"""
    user_id = business_connection.user.id
    
    # Сохранение подключения
    cursor = db.conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO business_connections 
        (id, user_id, business_user_id, is_enabled, can_reply)
        VALUES (?, ?, ?, ?, ?)
    """, (
        business_connection.id,
        user_id,
        business_connection.user_chat_id,
        1 if business_connection.is_enabled else 0,
        1 if business_connection.can_reply else 0
    ))
    db.conn.commit()
    
    # Если это первое подключение и нет активной подписки - даем trial
    subscription = db.get_active_subscription(user_id)
    if not subscription and not db.has_trial_used(user_id):
        db.create_subscription(user_id, "trial")
        db.log_action("auto_trial", "Автоматический trial при подключении Business", user_id=user_id)
    
    logger.info(f"Business подключение: user_id={user_id}, connection_id={business_connection.id}")


@router.business_message()
async def on_business_message(message: Message, bot: Bot):
    """Обработка сообщений из Business чатов"""
    # Проверяем что это сообщение из Business подключения
    if not message.business_connection_id:
        return
    
    # Находим пользователя по business_connection_id
    cursor = db.conn.cursor()
    cursor.execute("""
        SELECT user_id FROM business_connections WHERE id = ?
    """, (message.business_connection_id,))
    row = cursor.fetchone()
    
    if not row:
        return
    
    user_id = row['user_id']
    
    # Проверка подписки
    if not check_subscription(user_id):
        return
    
    # Сохранение сообщения
    chat_id = message.chat.id
    chat_title = message.chat.title or message.chat.first_name or "Unknown"
    sender_id = message.from_user.id if message.from_user else None
    sender_name = message.from_user.full_name if message.from_user else "Unknown"
    
    # Определение типа сообщения и сохранение
    message_type = "text"
    text = message.text or message.caption
    media_path = None
    media_type = None
    
    if message.photo:
        message_type = "photo"
        media_type = "photo"
        # Скачивание фото будет в отдельном обработчике
    elif message.video:
        message_type = "video"
        media_type = "video"
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
    msg_db_id = db.save_message(
        user_id=user_id,
        message_id=message.message_id,
        chat_id=chat_id,
        chat_title=chat_title,
        sender_id=sender_id,
        sender_name=sender_name,
        message_type=message_type,
        text=text,
        media_path=media_path,
        media_type=media_type
    )
    
    # Детектор контактов
    if text:
        contacts = detect_contacts_in_text(text)
        for contact_type, contact_value in contacts:
            db.save_detected_contact(
                user_id=user_id,
                message_id=msg_db_id,
                contact_type=contact_type,
                contact_value=contact_value,
                chat_id=chat_id
            )


@router.edited_business_message()
async def on_business_message_edited(message: Message):
    """Обработка отредактированных сообщений"""
    if not message.business_connection_id:
        return
    
    # Находим пользователя
    cursor = db.conn.cursor()
    cursor.execute("""
        SELECT user_id FROM business_connections WHERE id = ?
    """, (message.business_connection_id,))
    row = cursor.fetchone()
    
    if not row:
        return
    
    user_id = row['user_id']
    
    # Проверка подписки
    if not check_subscription(user_id):
        return
    
    # Получаем оригинальное сообщение
    cursor.execute("""
        SELECT text FROM messages 
        WHERE user_id = ? AND message_id = ? AND chat_id = ?
    """, (user_id, message.message_id, message.chat.id))
    original_row = cursor.fetchone()
    
    if original_row:
        original_text = original_row['text']
        new_text = message.text or message.caption
        
        db.mark_message_edited(
            message_id=message.message_id,
            chat_id=message.chat.id,
            user_id=user_id,
            original_text=original_text,
            new_text=new_text
        )
        
        # Уведомление пользователя
        notification = (
            f"✏️ <b>Сообщение отредактировано</b>\n\n"
            f"Чат: {message.chat.title or 'Unknown'}\n"
            f"Отправитель: {message.from_user.full_name if message.from_user else 'Unknown'}\n\n"
            f"<b>Было:</b>\n{original_text}\n\n"
            f"<b>Стало:</b>\n{new_text}"
        )
        
        try:
            await message.bot.send_message(
                chat_id=user_id,
                text=notification,
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления: {e}")


@router.deleted_business_messages()
async def on_business_messages_deleted(event: BusinessMessagesDeleted, bot: Bot):
    """Обработка удаленных сообщений из Business чатов"""
    # Находим пользователя
    cursor = db.conn.cursor()
    cursor.execute("""
        SELECT user_id FROM business_connections WHERE id = ?
    """, (event.business_connection_id,))
    row = cursor.fetchone()
    
    if not row:
        return
    
    user_id = row['user_id']
    
    # Проверка подписки
    if not check_subscription(user_id):
        return
    
    deleted_messages = []
    
    for message_id in event.message_ids:
        # Отмечаем как удаленное
        db.mark_message_deleted(
            message_id=message_id,
            chat_id=event.chat.id,
            user_id=user_id
        )
        
        # Получаем информацию об удаленном сообщении
        cursor.execute("""
            SELECT * FROM messages 
            WHERE user_id = ? AND message_id = ? AND chat_id = ?
        """, (user_id, message_id, event.chat.id))
        msg_row = cursor.fetchone()
        if msg_row:
            deleted_messages.append(dict(msg_row))
    
    # Если удалено 5+ сообщений - создаем архив
    if len(deleted_messages) >= 5:
        archive_path = await create_archive_from_messages(deleted_messages, event.chat.id, user_id)
        if archive_path:
            try:
                from aiogram.types import FSInputFile
                await bot.send_document(
                    chat_id=user_id,
                    document=FSInputFile(archive_path),
                    caption=f"📦 Архив удаленных сообщений из чата: {event.chat.title or 'Unknown'}"
                )
            except Exception as e:
                logger.error(f"Ошибка отправки архива: {e}")
    else:
        # Отправляем уведомления о каждом удаленном сообщении
        for msg in deleted_messages:
            notification = (
                f"🗑 <b>Сообщение удалено</b>\n\n"
                f"Чат: {msg['chat_title']}\n"
                f"Отправитель: {msg['sender_name']}\n"
                f"Тип: {msg['message_type']}\n\n"
            )
            
            if msg['text']:
                notification += f"<b>Текст:</b>\n{msg['text']}\n\n"
            
            try:
                await bot.send_message(
                    chat_id=user_id,
                    text=notification,
                    parse_mode=ParseMode.HTML
                )
            except Exception as e:
                logger.error(f"Ошибка отправки уведомления об удалении: {e}")


# ═══════════════════════════════════════════════════════════
#  БОНУС ЗА ДОБАВЛЕНИЕ БОТА
# ═══════════════════════════════════════════════════════════

@router.callback_query(F.data == "add_bot_bonus")
async def add_bot_bonus_start(callback: CallbackQuery, state: FSMContext):
    """Начало процесса добавления бота для получения бонуса"""
    await callback.message.edit_text(
        f"🤖 <b>Получите +{BONUS_DAYS_FOR_BOT_ADD} дней подписки!</b>\n\n"
        f"Создайте своего бота через @BotFather и отправьте мне его токен.\n\n"
        f"Токен выглядит так:\n"
        f"<code>123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11</code>\n\n"
        f"Отправьте токен вашего бота:",
        parse_mode=ParseMode.HTML
    )
    await state.set_state(BotStates.waiting_for_bot_token)


@router.message(BotStates.waiting_for_bot_token)
async def process_bot_token(message: Message, state: FSMContext, bot: Bot):
    """Обработка токена бота"""
    token = message.text.strip()
    user_id = message.from_user.id
    
    # Проверка формата токена
    if not token or ":" not in token:
        await message.answer("❌ Неверный формат токена. Попробуйте еще раз.")
        return
    
    try:
        # Создаем временного бота для проверки токена
        test_bot = Bot(token=token)
        bot_info = await test_bot.get_me()
        await test_bot.session.close()
        
        # Сохраняем подключенного бота
        db.add_connected_bot(
            user_id=user_id,
            bot_token=token,
            bot_username=bot_info.username,
            bot_id=bot_info.id
        )
        
        # Даем бонус +7 дней
        db.extend_subscription(user_id, BONUS_DAYS_FOR_BOT_ADD)
        
        db.log_action("bot_connected", f"Подключен бот @{bot_info.username}", user_id=user_id)
        
        await message.answer(
            f"✅ <b>Бот успешно подключен!</b>\n\n"
            f"Бот: @{bot_info.username}\n"
            f"Бонус: +{BONUS_DAYS_FOR_BOT_ADD} дней подписки\n\n"
            f"Теперь ваша подписка продлена! {BRAND_EMOJI}",
            parse_mode=ParseMode.HTML,
            reply_markup=get_main_menu(user_id)
        )
        
        await state.clear()
        
    except Exception as e:
        logger.error(f"Ошибка проверки токена: {e}")
        await message.answer(
            "❌ <b>Ошибка проверки токена</b>\n\n"
            "Убедитесь что:\n"
            "• Токен корректен\n"
            "• Бот активен в @BotFather\n\n"
            "Попробуйте еще раз:",
            parse_mode=ParseMode.HTML
        )


# ═══════════════════════════════════════════════════════════
#  СТАТИСТИКА
# ═══════════════════════════════════════════════════════════

@router.callback_query(F.data == "my_stats")
async def show_my_stats(callback: CallbackQuery):
    """Показать статистику пользователя"""
    user_id = callback.from_user.id
    
    stats = db.get_statistics(user_id)
    subscription = db.get_active_subscription(user_id)
    
    text = f"{BRAND_EMOJI} <b>Ваша статистика</b>\n\n"
    text += f"📊 Всего сообщений: {stats.get('total_messages', 0)}\n"
    text += f"🗑 Удаленных: {stats.get('deleted_messages', 0)}\n"
    text += f"✏️ Отредактированных: {stats.get('edited_messages', 0)}\n\n"
    
    if subscription:
        text += format_subscription_info(subscription)
    else:
        text += "⚠️ Нет активной подписки"
    
    await callback.message.edit_text(
        text,
        reply_markup=get_main_menu(user_id),
        parse_mode=ParseMode.HTML
    )


# ═══════════════════════════════════════════════════════════
#  АДМИН ПАНЕЛЬ
# ═══════════════════════════════════════════════════════════

@router.callback_query(F.data == "admin_panel")
async def show_admin_panel(callback: CallbackQuery):
    """Показать админ панель"""
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return
    
    stats = db.get_statistics()
    
    text = f"👑 <b>Админ Панель</b>\n\n"
    text += f"👥 Всего пользователей: {stats.get('total_users', 0)}\n"
    text += f"✅ Активных подписок: {stats.get('active_subscriptions', 0)}\n"
    text += f"📊 Всего сообщений: {stats.get('total_messages', 0)}\n"
    
    await callback.message.edit_text(
        text,
        reply_markup=get_admin_menu(),
        parse_mode=ParseMode.HTML
    )


def get_router() -> Router:
    """Получить router для регистрации в диспетчере"""
    return router
