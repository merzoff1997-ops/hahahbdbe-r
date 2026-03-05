"""
╔══════════════════════════════════════════════════════════════════╗
║                    MerAI & Monitoring                            ║
║                   Admin Panel Handlers                           ║
╚══════════════════════════════════════════════════════════════════╝
"""

import logging
from datetime import datetime, timedelta

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.enums import ParseMode
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import ADMIN_ID, SUBSCRIPTION_PLANS, BRAND_NAME
from database import db
from bot.keyboards import get_user_management_keyboard, pagination_keyboard, get_admin_menu

logger = logging.getLogger(__name__)

router = Router()


# Проверка прав администратора
def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID


# ═══════════════════════════════════════════════════════════
#  СПИСОК ПОЛЬЗОВАТЕЛЕЙ
# ═══════════════════════════════════════════════════════════

@router.callback_query(F.data == "admin_users")
async def admin_users_list(callback: CallbackQuery):
    """Список всех пользователей"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return
    
    users = db.get_all_users()
    
    text = f"👥 <b>Список пользователей ({len(users)})</b>\n\n"
    
    for i, user in enumerate(users[:20], 1):  # Показываем первые 20
        username = f"@{user['username']}" if user['username'] else "Без username"
        blocked = "🚫" if user['is_blocked'] else ""
        
        # Проверяем подписку
        subscription = db.get_active_subscription(user['user_id'])
        sub_status = "✅" if subscription else "❌"
        
        text += f"{i}. {blocked} {user['first_name']} ({username})\n"
        text += f"   ID: <code>{user['user_id']}</code> | Подписка: {sub_status}\n\n"
    
    # Создаем inline кнопки с ID пользователей
    builder = InlineKeyboardBuilder()
    
    for user in users[:10]:  # Первые 10 для кнопок
        builder.row(
            InlineKeyboardButton(
                text=f"{user['first_name']} - {user['user_id']}",
                callback_data=f"admin_user_{user['user_id']}"
            )
        )
    
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data="admin_panel")
    )
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode=ParseMode.HTML)


@router.callback_query(F.data.startswith("admin_user_"))
async def admin_user_details(callback: CallbackQuery):
    """Детали пользователя"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return
    
    user_id = int(callback.data.split("_")[2])
    user = db.get_user(user_id)
    
    if not user:
        await callback.answer("❌ Пользователь не найден", show_alert=True)
        return
    
    subscription = db.get_active_subscription(user_id)
    stats = db.get_statistics(user_id)
    
    text = f"👤 <b>Пользователь {user['first_name']}</b>\n\n"
    text += f"ID: <code>{user['user_id']}</code>\n"
    text += f"Username: @{user['username'] or 'нет'}\n"
    text += f"Язык: {user['language_code']}\n"
    text += f"Статус: {'🚫 Заблокирован' if user['is_blocked'] else '✅ Активен'}\n\n"
    
    text += f"<b>Статистика:</b>\n"
    text += f"Сообщений: {stats.get('total_messages', 0)}\n"
    text += f"Удаленных: {stats.get('deleted_messages', 0)}\n"
    text += f"Отредактированных: {stats.get('edited_messages', 0)}\n\n"
    
    if subscription:
        from bot.utils import format_subscription_info
        text += format_subscription_info(subscription)
    else:
        text += "⚠️ Нет активной подписки"
    
    await callback.message.edit_text(
        text,
        reply_markup=get_user_management_keyboard(user_id),
        parse_mode=ParseMode.HTML
    )


# ═══════════════════════════════════════════════════════════
#  УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ
# ═══════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("admin_toggle_block_"))
async def admin_toggle_block(callback: CallbackQuery):
    """Блокировка/разблокировка пользователя"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return
    
    user_id = int(callback.data.split("_")[3])
    user = db.get_user(user_id)
    
    if not user:
        await callback.answer("❌ Пользователь не найден", show_alert=True)
        return
    
    # Переключаем блокировку
    new_blocked_status = not user['is_blocked']
    db.block_user(user_id, new_blocked_status)
    
    # Логируем
    action = "заблокирован" if new_blocked_status else "разблокирован"
    db.log_action(
        "admin_block_toggle",
        f"Пользователь {user_id} {action}",
        user_id=callback.from_user.id
    )
    
    await callback.answer(f"✅ Пользователь {action}")
    
    # Обновляем информацию
    await admin_user_details(callback)


@router.callback_query(F.data.startswith("admin_give_sub_"))
async def admin_give_subscription(callback: CallbackQuery):
    """Выдача подписки пользователю"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return
    
    user_id = int(callback.data.split("_")[3])
    
    # Создаем меню выбора плана
    builder = InlineKeyboardBuilder()
    
    for plan_key, plan in SUBSCRIPTION_PLANS.items():
        if plan_key == "trial":
            continue
        
        builder.row(
            InlineKeyboardButton(
                text=f"{plan['name']} ({plan['duration_days']} дней)",
                callback_data=f"admin_grant_{plan_key}_{user_id}"
            )
        )
    
    builder.row(
        InlineKeyboardButton(
            text="🔙 Отмена",
            callback_data=f"admin_user_{user_id}"
        )
    )
    
    await callback.message.edit_text(
        "💎 Выберите план подписки для выдачи:",
        reply_markup=builder.as_markup()
    )


@router.callback_query(F.data.startswith("admin_grant_"))
async def admin_grant_plan(callback: CallbackQuery):
    """Выдать выбранный план"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return
    
    parts = callback.data.split("_")
    plan_key = parts[2]
    user_id = int(parts[3])
    
    # Создаем подписку
    db.create_subscription(user_id, plan_key, stars_paid=0, auto_renew=False)
    
    # Логируем
    db.log_action(
        "admin_grant_subscription",
        f"Админ выдал подписку {plan_key} пользователю {user_id}",
        user_id=callback.from_user.id
    )
    
    await callback.answer("✅ Подписка выдана!")
    
    # Возвращаемся к пользователю
    await admin_user_details(callback)


@router.callback_query(F.data.startswith("admin_clear_chat_"))
async def admin_clear_chat(callback: CallbackQuery):
    """Очистка диалога с пользователем"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return
    
    user_id = int(callback.data.split("_")[3])
    
    try:
        # Удаляем все сообщения бота в чате с пользователем
        await callback.bot.send_message(
            user_id,
            "🗑 Администратор очистил историю диалога."
        )
        
        db.log_action(
            "admin_clear_chat",
            f"Админ очистил диалог с пользователем {user_id}",
            user_id=callback.from_user.id
        )
        
        await callback.answer("✅ Диалог очищен")
    except Exception as e:
        logger.error(f"Ошибка очистки диалога: {e}")
        await callback.answer("❌ Ошибка при очистке", show_alert=True)


# ═══════════════════════════════════════════════════════════
#  СТАТИСТИКА
# ═══════════════════════════════════════════════════════════

@router.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    """Общая статистика системы"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return
    
    stats = db.get_statistics()
    
    # Получаем дополнительную статистику
    cursor = db.conn.cursor()
    
    # Статистика по подпискам
    cursor.execute("""
        SELECT plan_type, COUNT(*) as count 
        FROM subscriptions 
        WHERE is_active = 1 AND end_date > ?
        GROUP BY plan_type
    """, (datetime.now(),))
    subscriptions_by_plan = {row['plan_type']: row['count'] for row in cursor.fetchall()}
    
    # Новые пользователи за неделю
    week_ago = datetime.now() - timedelta(days=7)
    cursor.execute("""
        SELECT COUNT(*) as count FROM users WHERE created_at > ?
    """, (week_ago,))
    new_users_week = cursor.fetchone()['count']
    
    # Активных пользователей за день
    day_ago = datetime.now() - timedelta(days=1)
    cursor.execute("""
        SELECT COUNT(*) as count FROM users WHERE last_activity > ?
    """, (day_ago,))
    active_today = cursor.fetchone()['count']
    
    text = f"📊 <b>Статистика {BRAND_NAME}</b>\n\n"
    text += f"<b>Пользователи:</b>\n"
    text += f"Всего: {stats.get('total_users', 0)}\n"
    text += f"Новых за неделю: {new_users_week}\n"
    text += f"Активных за день: {active_today}\n\n"
    
    text += f"<b>Подписки:</b>\n"
    text += f"Активных: {stats.get('active_subscriptions', 0)}\n"
    for plan_key, count in subscriptions_by_plan.items():
        plan = SUBSCRIPTION_PLANS.get(plan_key, {})
        text += f"  • {plan.get('name', plan_key)}: {count}\n"
    text += "\n"
    
    text += f"<b>Сообщения:</b>\n"
    text += f"Всего сохранено: {stats.get('total_messages', 0)}\n"
    
    await callback.message.edit_text(
        text,
        reply_markup=get_admin_menu(),
        parse_mode=ParseMode.HTML
    )


# ═══════════════════════════════════════════════════════════
#  ТРАНЗАКЦИИ
# ═══════════════════════════════════════════════════════════

@router.callback_query(F.data == "admin_transactions")
async def admin_transactions(callback: CallbackQuery):
    """Список транзакций"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return
    
    cursor = db.conn.cursor()
    cursor.execute("""
        SELECT t.*, u.first_name, u.username
        FROM transactions t
        LEFT JOIN users u ON t.user_id = u.user_id
        ORDER BY t.created_at DESC
        LIMIT 20
    """)
    transactions = [dict(row) for row in cursor.fetchall()]
    
    text = f"💳 <b>Последние транзакции</b>\n\n"
    
    total_stars = 0
    for tx in transactions:
        created_at = datetime.fromisoformat(tx['created_at']).strftime('%d.%m %H:%M')
        username = f"@{tx['username']}" if tx['username'] else tx['first_name']
        
        text += f"• {created_at} - {username}\n"
        text += f"  {tx['stars_amount']} ⭐ ({tx['rub_equivalent']} ₽)\n"
        text += f"  {tx['description']}\n\n"
        
        total_stars += tx['stars_amount']
    
    text += f"\n<b>Всего получено:</b> {total_stars} ⭐"
    
    await callback.message.edit_text(
        text,
        reply_markup=get_admin_menu(),
        parse_mode=ParseMode.HTML
    )


# ═══════════════════════════════════════════════════════════
#  ЛОГИ
# ═══════════════════════════════════════════════════════════

@router.callback_query(F.data == "admin_logs")
async def admin_logs(callback: CallbackQuery):
    """Просмотр логов"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return
    
    logs = db.get_action_logs(limit=20)
    
    text = f"📝 <b>Последние действия</b>\n\n"
    
    for log in logs:
        created_at = datetime.fromisoformat(log['created_at']).strftime('%d.%m %H:%M')
        user_id = log['user_id'] or 'System'
        
        text += f"• {created_at} - User {user_id}\n"
        text += f"  {log['action_type']}: {log['description']}\n\n"
    
    await callback.message.edit_text(
        text,
        reply_markup=get_admin_menu(),
        parse_mode=ParseMode.HTML
    )


# ═══════════════════════════════════════════════════════════
#  БРЕНДИНГ
# ═══════════════════════════════════════════════════════════

@router.callback_query(F.data == "admin_branding")
async def admin_branding(callback: CallbackQuery):
    """Управление брендингом"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return
    
    current_welcome = db.get_branding("welcome_message") or "Не установлено"
    
    text = f"🎨 <b>Управление брендингом</b>\n\n"
    text += f"<b>Текущее приветствие:</b>\n{current_welcome}\n\n"
    text += "Отправьте новый текст приветствия для изменения."
    
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data="admin_panel")
    )
    
    await callback.message.edit_text(
        text,
        reply_markup=builder.as_markup(),
        parse_mode=ParseMode.HTML
    )


# ═══════════════════════════════════════════════════════════
#  РАССЫЛКА
# ═══════════════════════════════════════════════════════════

@router.callback_query(F.data == "admin_broadcast")
async def admin_broadcast(callback: CallbackQuery):
    """Рассылка сообщений"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return
    
    text = f"📢 <b>Рассылка сообщений</b>\n\n"
    text += "Отправьте сообщение, которое нужно разослать всем пользователям.\n\n"
    text += "⚠️ Будьте осторожны, это действие нельзя отменить!"
    
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_panel")
    )
    
    await callback.message.edit_text(
        text,
        reply_markup=builder.as_markup(),
        parse_mode=ParseMode.HTML
    )


def get_admin_router() -> Router:
    """Получить router админ панели"""
    return router
