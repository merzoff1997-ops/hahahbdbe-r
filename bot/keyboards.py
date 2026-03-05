"""
╔══════════════════════════════════════════════════════════════════╗
║                    MerAI & Monitoring                            ║
║                     Keyboards Module                             ║
╚══════════════════════════════════════════════════════════════════╝
"""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import SUBSCRIPTION_PLANS, ADMIN_ID
from database import db


def get_main_menu(user_id: int) -> InlineKeyboardMarkup:
    """Главное меню"""
    builder = InlineKeyboardBuilder()
    
    # Проверка подписки
    subscription = db.get_active_subscription(user_id)
    has_subscription = subscription is not None
    
    builder.row(
        InlineKeyboardButton(text="📊 Моя статистика", callback_data="my_stats"),
        InlineKeyboardButton(text="💎 Подписки", callback_data="subscriptions")
    )
    
    builder.row(
        InlineKeyboardButton(text="📋 Удаленные сообщения", callback_data="deleted_messages"),
        InlineKeyboardButton(text="✏️ Отредактированные", callback_data="edited_messages")
    )
    
    builder.row(
        InlineKeyboardButton(text="📞 Детектор контактов", callback_data="detected_contacts"),
        InlineKeyboardButton(text="✅ Чеклисты", callback_data="checklists")
    )
    
    builder.row(
        InlineKeyboardButton(text="🤖 Dual Mode", callback_data="dual_mode_settings"),
        InlineKeyboardButton(text="⚙️ Настройки", callback_data="settings")
    )
    
    builder.row(
        InlineKeyboardButton(text="🎁 Бонус +7 дней", callback_data="add_bot_bonus")
    )
    
    # Админ кнопка
    if user_id == ADMIN_ID:
        builder.row(
            InlineKeyboardButton(text="👑 Админ Панель", callback_data="admin_panel")
        )
    
    return builder.as_markup()


def get_subscription_menu(user_id: int) -> InlineKeyboardMarkup:
    """Меню подписок"""
    builder = InlineKeyboardBuilder()
    
    # Кнопки для каждого тарифа
    for plan_key, plan in SUBSCRIPTION_PLANS.items():
        # Проверка доступности trial
        if plan_key == "trial" and db.has_trial_used(user_id):
            continue
        
        button_text = f"{plan['name']} ({plan['stars_price']} ⭐)"
        builder.row(
            InlineKeyboardButton(text=button_text, callback_data=f"buy_{plan_key}")
        )
    
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")
    )
    
    return builder.as_markup()


def get_admin_menu() -> InlineKeyboardMarkup:
    """Админ меню"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="👥 Пользователи", callback_data="admin_users"),
        InlineKeyboardButton(text="💳 Транзакции", callback_data="admin_transactions")
    )
    
    builder.row(
        InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats"),
        InlineKeyboardButton(text="📝 Логи", callback_data="admin_logs")
    )
    
    builder.row(
        InlineKeyboardButton(text="🎨 Брендинг", callback_data="admin_branding"),
        InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast")
    )
    
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")
    )
    
    return builder.as_markup()


def get_user_management_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Клавиатура управления пользователем"""
    builder = InlineKeyboardBuilder()
    
    is_blocked = db.is_user_blocked(user_id)
    
    builder.row(
        InlineKeyboardButton(
            text="🚫 Разблокировать" if is_blocked else "❌ Заблокировать",
            callback_data=f"admin_toggle_block_{user_id}"
        )
    )
    
    builder.row(
        InlineKeyboardButton(text="💎 Выдать подписку", callback_data=f"admin_give_sub_{user_id}"),
        InlineKeyboardButton(text="📊 Статистика", callback_data=f"admin_user_stats_{user_id}")
    )
    
    builder.row(
        InlineKeyboardButton(text="🗑 Очистить диалог", callback_data=f"admin_clear_chat_{user_id}")
    )
    
    builder.row(
        InlineKeyboardButton(text="🔙 К списку", callback_data="admin_users")
    )
    
    return builder.as_markup()


def get_checklist_keyboard(checklist_id: int) -> InlineKeyboardMarkup:
    """Клавиатура чеклиста"""
    builder = InlineKeyboardBuilder()
    
    items = db.get_checklist_items(checklist_id)
    
    for item in items:
        status = "✅" if item['is_completed'] else "⬜"
        button_text = f"{status} {item['text']}"
        builder.row(
            InlineKeyboardButton(
                text=button_text,
                callback_data=f"toggle_item_{item['id']}"
            )
        )
    
    builder.row(
        InlineKeyboardButton(text="➕ Добавить", callback_data=f"add_item_{checklist_id}"),
        InlineKeyboardButton(text="🗑 Удалить", callback_data=f"delete_checklist_{checklist_id}")
    )
    
    builder.row(
        InlineKeyboardButton(text="🔙 К чеклистам", callback_data="checklists")
    )
    
    return builder.as_markup()


def get_dual_mode_keyboard(current_mode: str) -> InlineKeyboardMarkup:
    """Клавиатура настройки Dual Mode"""
    builder = InlineKeyboardBuilder()
    
    modes = {
        "business": "🤖 Business API",
        "userbot": "👤 Userbot",
        "dual": "🔄 Dual Mode"
    }
    
    for mode_key, mode_name in modes.items():
        selected = "✅ " if mode_key == current_mode else ""
        builder.row(
            InlineKeyboardButton(
                text=f"{selected}{mode_name}",
                callback_data=f"set_mode_{mode_key}"
            )
        )
    
    builder.row(
        InlineKeyboardButton(text="ℹ️ О режимах", callback_data="mode_info")
    )
    
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")
    )
    
    return builder.as_markup()


def get_contacts_filter_keyboard() -> InlineKeyboardMarkup:
    """Фильтр для детектора контактов"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="📞 Телефоны", callback_data="contacts_phone"),
        InlineKeyboardButton(text="📧 Email", callback_data="contacts_email")
    )
    
    builder.row(
        InlineKeyboardButton(text="🔗 Telegram", callback_data="contacts_telegram"),
        InlineKeyboardButton(text="🌐 URL", callback_data="contacts_url")
    )
    
    builder.row(
        InlineKeyboardButton(text="📋 Все контакты", callback_data="contacts_all")
    )
    
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")
    )
    
    return builder.as_markup()


def get_export_format_keyboard() -> InlineKeyboardMarkup:
    """Выбор формата экспорта"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="📄 JSON", callback_data="export_json"),
        InlineKeyboardButton(text="📊 CSV", callback_data="export_csv")
    )
    
    builder.row(
        InlineKeyboardButton(text="🌐 HTML", callback_data="export_html")
    )
    
    builder.row(
        InlineKeyboardButton(text="🔙 Отмена", callback_data="back_to_main")
    )
    
    return builder.as_markup()


def pagination_keyboard(
    callback_prefix: str,
    current_page: int,
    total_pages: int,
    back_callback: str = "back_to_main"
) -> InlineKeyboardMarkup:
    """Клавиатура пагинации"""
    builder = InlineKeyboardBuilder()
    
    buttons = []
    
    if current_page > 0:
        buttons.append(
            InlineKeyboardButton(text="◀️", callback_data=f"{callback_prefix}_{current_page - 1}")
        )
    
    buttons.append(
        InlineKeyboardButton(text=f"{current_page + 1}/{total_pages}", callback_data="noop")
    )
    
    if current_page < total_pages - 1:
        buttons.append(
            InlineKeyboardButton(text="▶️", callback_data=f"{callback_prefix}_{current_page + 1}")
        )
    
    builder.row(*buttons)
    
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data=back_callback)
    )
    
    return builder.as_markup()
