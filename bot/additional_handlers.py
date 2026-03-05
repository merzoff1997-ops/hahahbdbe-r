"""
╔══════════════════════════════════════════════════════════════════╗
║                    MerAI & Monitoring                            ║
║              Additional Feature Handlers Module                  ║
╚══════════════════════════════════════════════════════════════════╝
"""

import logging
from datetime import datetime

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.enums import ParseMode
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import EXPORT_FORMATS
from database import db
from bot.keyboards import (
    get_main_menu,
    get_checklist_keyboard,
    get_contacts_filter_keyboard,
    get_export_format_keyboard,
    pagination_keyboard,
    get_dual_mode_keyboard,
)
from bot.utils import (
    format_message_for_display,
    format_contact_list,
    format_checklist,
    export_to_json,
    export_to_csv,
    export_to_html,
    generate_export_filename,
)

logger = logging.getLogger(__name__)

router = Router()


# ═══════════════════════════════════════════════════════════
#  СОСТОЯНИЯ FSM ДЛЯ ДОПОЛНИТЕЛЬНЫХ ФУНКЦИЙ
# ═══════════════════════════════════════════════════════════

class ChecklistStates(StatesGroup):
    waiting_for_title = State()
    waiting_for_item = State()


class DualModeStates(StatesGroup):
    waiting_for_phone = State()
    waiting_for_code = State()


# ═══════════════════════════════════════════════════════════
#  УДАЛЕННЫЕ СООБЩЕНИЯ
# ═══════════════════════════════════════════════════════════

@router.callback_query(F.data == "deleted_messages")
async def show_deleted_messages(callback: CallbackQuery):
    """Показать удаленные сообщения"""
    user_id = callback.from_user.id
    
    messages = db.get_deleted_messages(user_id)
    
    if not messages:
        await callback.message.edit_text(
            "📭 У вас нет удаленных сообщений",
            reply_markup=get_main_menu(user_id)
        )
        return
    
    text = f"🗑 <b>Удаленные сообщения ({len(messages)})</b>\n\n"
    
    # Показываем первые 10
    for msg in messages[:10]:
        text += format_message_for_display(msg, show_details=True)
        text += "\n" + "─" * 30 + "\n\n"
    
    builder = InlineKeyboardBuilder()
    builder.row(
        callback.types.InlineKeyboardButton(text="📥 Экспорт", callback_data="export_deleted"),
        callback.types.InlineKeyboardButton(text="🔄 Обновить", callback_data="deleted_messages")
    )
    builder.row(
        callback.types.InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")
    )
    
    await callback.message.edit_text(
        text,
        reply_markup=builder.as_markup(),
        parse_mode=ParseMode.HTML
    )


# ═══════════════════════════════════════════════════════════
#  ОТРЕДАКТИРОВАННЫЕ СООБЩЕНИЯ
# ═══════════════════════════════════════════════════════════

@router.callback_query(F.data == "edited_messages")
async def show_edited_messages(callback: CallbackQuery):
    """Показать отредактированные сообщения"""
    user_id = callback.from_user.id
    
    messages = db.get_edited_messages(user_id)
    
    if not messages:
        await callback.message.edit_text(
            "📭 У вас нет отредактированных сообщений",
            reply_markup=get_main_menu(user_id)
        )
        return
    
    text = f"✏️ <b>Отредактированные сообщения ({len(messages)})</b>\n\n"
    
    # Показываем первые 10
    for msg in messages[:10]:
        text += format_message_for_display(msg, show_details=True)
        text += "\n" + "─" * 30 + "\n\n"
    
    builder = InlineKeyboardBuilder()
    builder.row(
        callback.types.InlineKeyboardButton(text="📥 Экспорт", callback_data="export_edited"),
        callback.types.InlineKeyboardButton(text="🔄 Обновить", callback_data="edited_messages")
    )
    builder.row(
        callback.types.InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")
    )
    
    await callback.message.edit_text(
        text,
        reply_markup=builder.as_markup(),
        parse_mode=ParseMode.HTML
    )


# ═══════════════════════════════════════════════════════════
#  ДЕТЕКТОР КОНТАКТОВ
# ═══════════════════════════════════════════════════════════

@router.callback_query(F.data == "detected_contacts")
async def show_contacts_menu(callback: CallbackQuery):
    """Меню детектора контактов"""
    await callback.message.edit_text(
        "📞 <b>Детектор контактов</b>\n\n"
        "Выберите тип контактов для просмотра:",
        reply_markup=get_contacts_filter_keyboard(),
        parse_mode=ParseMode.HTML
    )


@router.callback_query(F.data.startswith("contacts_"))
async def show_filtered_contacts(callback: CallbackQuery):
    """Показать контакты по типу"""
    user_id = callback.from_user.id
    contact_type = callback.data.split("_")[1]
    
    if contact_type == "all":
        contacts = db.get_detected_contacts(user_id)
    else:
        contacts = db.get_detected_contacts(user_id, contact_type)
    
    text = format_contact_list(contacts, None if contact_type == "all" else contact_type)
    
    builder = InlineKeyboardBuilder()
    builder.row(
        callback.types.InlineKeyboardButton(text="📥 Экспорт", callback_data=f"export_contacts_{contact_type}")
    )
    builder.row(
        callback.types.InlineKeyboardButton(text="🔙 Назад", callback_data="detected_contacts")
    )
    
    await callback.message.edit_text(
        text,
        reply_markup=builder.as_markup(),
        parse_mode=ParseMode.HTML
    )


# ═══════════════════════════════════════════════════════════
#  ЧЕКЛИСТЫ
# ═══════════════════════════════════════════════════════════

@router.callback_query(F.data == "checklists")
async def show_checklists(callback: CallbackQuery):
    """Показать чеклисты пользователя"""
    user_id = callback.from_user.id
    
    checklists = db.get_user_checklists(user_id)
    
    text = "✅ <b>Ваши чеклисты</b>\n\n"
    
    if not checklists:
        text += "У вас пока нет чеклистов.\n\n"
    else:
        for checklist in checklists:
            progress = 0
            if checklist['total_items'] > 0:
                progress = int((checklist['completed_items'] or 0) / checklist['total_items'] * 100)
            
            text += f"📋 <b>{checklist['title']}</b>\n"
            text += f"Прогресс: {checklist['completed_items'] or 0}/{checklist['total_items']} ({progress}%)\n\n"
    
    builder = InlineKeyboardBuilder()
    
    for checklist in checklists:
        builder.row(
            callback.types.InlineKeyboardButton(
                text=f"📋 {checklist['title']}",
                callback_data=f"view_checklist_{checklist['id']}"
            )
        )
    
    builder.row(
        callback.types.InlineKeyboardButton(text="➕ Создать чеклист", callback_data="create_checklist")
    )
    builder.row(
        callback.types.InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")
    )
    
    await callback.message.edit_text(
        text,
        reply_markup=builder.as_markup(),
        parse_mode=ParseMode.HTML
    )


@router.callback_query(F.data == "create_checklist")
async def create_checklist_start(callback: CallbackQuery, state: FSMContext):
    """Начать создание чеклиста"""
    await callback.message.edit_text(
        "📝 <b>Создание чеклиста</b>\n\n"
        "Введите название чеклиста:",
        parse_mode=ParseMode.HTML
    )
    await state.set_state(ChecklistStates.waiting_for_title)


@router.message(ChecklistStates.waiting_for_title)
async def process_checklist_title(message: Message, state: FSMContext):
    """Обработка названия чеклиста"""
    title = message.text.strip()
    user_id = message.from_user.id
    
    if len(title) > 100:
        await message.answer("❌ Название слишком длинное. Максимум 100 символов.")
        return
    
    # Создаем чеклист
    checklist_id = db.create_checklist(user_id, title)
    
    await state.update_data(checklist_id=checklist_id)
    await state.set_state(ChecklistStates.waiting_for_item)
    
    await message.answer(
        f"✅ Чеклист «{title}» создан!\n\n"
        "Теперь добавьте элементы. Отправьте текст элемента или /done для завершения:",
        parse_mode=ParseMode.HTML
    )


@router.message(ChecklistStates.waiting_for_item)
async def process_checklist_item(message: Message, state: FSMContext):
    """Добавление элемента в чеклист"""
    if message.text == "/done":
        data = await state.get_data()
        checklist_id = data.get('checklist_id')
        
        await state.clear()
        
        # Показываем чеклист
        items = db.get_checklist_items(checklist_id)
        cursor = db.conn.cursor()
        cursor.execute("SELECT * FROM checklists WHERE id = ?", (checklist_id,))
        checklist = dict(cursor.fetchone())
        
        text = format_checklist(checklist, items)
        
        await message.answer(
            text + "\n\n✅ Чеклист готов!",
            reply_markup=get_checklist_keyboard(checklist_id),
            parse_mode=ParseMode.HTML
        )
        return
    
    data = await state.get_data()
    checklist_id = data.get('checklist_id')
    
    item_text = message.text.strip()
    if len(item_text) > 200:
        await message.answer("❌ Текст элемента слишком длинный. Максимум 200 символов.")
        return
    
    # Добавляем элемент
    db.add_checklist_item(checklist_id, item_text)
    
    await message.answer(
        f"✅ Элемент добавлен: {item_text}\n\n"
        "Добавьте еще элементы или отправьте /done для завершения:"
    )


@router.callback_query(F.data.startswith("view_checklist_"))
async def view_checklist(callback: CallbackQuery):
    """Просмотр чеклиста"""
    checklist_id = int(callback.data.split("_")[2])
    
    cursor = db.conn.cursor()
    cursor.execute("SELECT * FROM checklists WHERE id = ?", (checklist_id,))
    checklist = dict(cursor.fetchone())
    
    items = db.get_checklist_items(checklist_id)
    
    text = format_checklist(checklist, items)
    
    await callback.message.edit_text(
        text,
        reply_markup=get_checklist_keyboard(checklist_id),
        parse_mode=ParseMode.HTML
    )


@router.callback_query(F.data.startswith("toggle_item_"))
async def toggle_checklist_item(callback: CallbackQuery):
    """Переключить состояние элемента"""
    item_id = int(callback.data.split("_")[2])
    
    db.toggle_checklist_item(item_id)
    
    # Получаем checklist_id для обновления отображения
    cursor = db.conn.cursor()
    cursor.execute("SELECT checklist_id FROM checklist_items WHERE id = ?", (item_id,))
    checklist_id = cursor.fetchone()['checklist_id']
    
    await view_checklist(callback)
    await callback.answer("✅ Статус изменен")


# ═══════════════════════════════════════════════════════════
#  DUAL MODE НАСТРОЙКИ
# ═══════════════════════════════════════════════════════════

@router.callback_query(F.data == "dual_mode_settings")
async def dual_mode_settings(callback: CallbackQuery):
    """Настройки Dual Mode"""
    user_id = callback.from_user.id
    
    user = db.get_user(user_id)
    current_mode = user.get('monitoring_mode', 'business')
    
    # Статус userbot
    from userbot import get_userbot_status
    userbot_status = get_userbot_status(user_id)
    
    text = "🔄 <b>Dual Mode</b>\n\n"
    text += "<b>Режимы работы:</b>\n\n"
    text += "🤖 <b>Business API</b>\n"
    text += "Работает с бизнес-чатами (требует Telegram Premium)\n"
    text += "Ограничения: не сохраняет сообщения с таймером самоуничтожения\n\n"
    
    text += "👤 <b>Userbot</b>\n"
    text += "Работает со всеми чатами\n"
    text += "Может обходить некоторые ограничения Business API\n\n"
    
    text += "🔄 <b>Dual Mode</b>\n"
    text += "Использует оба режима одновременно для максимального покрытия\n\n"
    
    text += f"<b>Текущий режим:</b> {current_mode}\n"
    
    if userbot_status:
        text += f"<b>Userbot статус:</b> {'✅ Активен' if userbot_status['is_running'] else '❌ Неактивен'}\n"
    
    await callback.message.edit_text(
        text,
        reply_markup=get_dual_mode_keyboard(current_mode),
        parse_mode=ParseMode.HTML
    )


@router.callback_query(F.data.startswith("set_mode_"))
async def set_monitoring_mode(callback: CallbackQuery, state: FSMContext):
    """Установить режим мониторинга"""
    user_id = callback.from_user.id
    mode = callback.data.split("_")[2]
    
    # Обновляем режим в БД
    cursor = db.conn.cursor()
    cursor.execute("UPDATE users SET monitoring_mode = ? WHERE user_id = ?", (mode, user_id))
    db.conn.commit()
    
    # Если выбран userbot или dual режим, запрашиваем телефон
    if mode in ['userbot', 'dual']:
        from userbot import get_userbot_status
        userbot_status = get_userbot_status(user_id)
        
        if not userbot_status or not userbot_status['is_authorized']:
            await callback.message.edit_text(
                "📱 <b>Настройка Userbot</b>\n\n"
                "Для работы Userbot режима необходима авторизация.\n\n"
                "Введите номер телефона в международном формате\n"
                "(например, +79991234567):",
                parse_mode=ParseMode.HTML
            )
            await state.set_state(DualModeStates.waiting_for_phone)
            return
    
    await callback.answer(f"✅ Режим изменен на {mode}")
    await dual_mode_settings(callback)


@router.message(DualModeStates.waiting_for_phone)
async def process_userbot_phone(message: Message, state: FSMContext):
    """Обработка номера телефона для userbot"""
    phone = message.text.strip()
    user_id = message.from_user.id
    
    if not phone.startswith('+'):
        await message.answer("❌ Номер должен начинаться с + и кода страны")
        return
    
    # Запускаем userbot
    from userbot import start_userbot_for_user
    
    success, msg = await start_userbot_for_user(user_id, phone)
    
    if success:
        await state.update_data(phone=phone)
        await state.set_state(DualModeStates.waiting_for_code)
        
        await message.answer(
            f"📱 {msg}\n\n"
            "Введите код подтверждения из Telegram:"
        )
    else:
        await message.answer(f"❌ {msg}")
        await state.clear()


@router.message(DualModeStates.waiting_for_code)
async def process_userbot_code(message: Message, state: FSMContext):
    """Обработка кода подтверждения"""
    code = message.text.strip()
    user_id = message.from_user.id
    
    data = await state.get_data()
    phone = data.get('phone')
    
    from userbot import sign_in_userbot
    
    success, msg = await sign_in_userbot(user_id, code, phone)
    
    if success:
        await message.answer(
            f"✅ {msg}\n\n"
            "Userbot успешно авторизован и начал мониторинг!",
            reply_markup=get_main_menu(user_id)
        )
    else:
        await message.answer(f"❌ {msg}")
    
    await state.clear()


# ═══════════════════════════════════════════════════════════
#  ЭКСПОРТ ДАННЫХ
# ═══════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("export_"))
async def start_export(callback: CallbackQuery):
    """Начать экспорт данных"""
    export_type = callback.data.split("_")[1]
    
    await callback.message.edit_text(
        f"📥 <b>Экспорт данных</b>\n\n"
        f"Выберите формат экспорта:",
        reply_markup=get_export_format_keyboard(),
        parse_mode=ParseMode.HTML
    )
    
    # Сохраняем тип экспорта в callback_data
    await callback.answer()


# ═══════════════════════════════════════════════════════════
#  НАВИГАЦИЯ
# ═══════════════════════════════════════════════════════════

@router.callback_query(F.data == "back_to_main")
async def back_to_main_menu(callback: CallbackQuery):
    """Вернуться в главное меню"""
    user_id = callback.from_user.id
    
    text = "🏠 <b>Главное меню</b>\n\n"
    text += "Выберите действие:"
    
    await callback.message.edit_text(
        text,
        reply_markup=get_main_menu(user_id),
        parse_mode=ParseMode.HTML
    )


def get_additional_router() -> Router:
    """Получить router дополнительных функций"""
    return router
