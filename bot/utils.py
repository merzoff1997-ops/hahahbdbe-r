"""
╔══════════════════════════════════════════════════════════════════╗
║                    MerAI & Monitoring                            ║
║                       Utils Module                               ║
╚══════════════════════════════════════════════════════════════════╝
"""

import re
import json
import zipfile
from datetime import datetime
from pathlib import Path
from typing import List, Tuple, Optional, Dict

from config import CONTACT_DETECTOR_PATTERNS, MEDIA_PATH, AUTO_ARCHIVE_THRESHOLD
from database import db


def format_subscription_info(subscription: Dict) -> str:
    """Форматирование информации о подписке"""
    from config import SUBSCRIPTION_PLANS
    
    plan = SUBSCRIPTION_PLANS.get(subscription['plan_type'], {})
    end_date = datetime.fromisoformat(subscription['end_date'])
    days_left = (end_date - datetime.now()).days
    
    status_emoji = "✅" if days_left > 0 else "❌"
    
    text = f"{status_emoji} <b>Текущая подписка</b>\n\n"
    text += f"План: {plan.get('name', subscription['plan_type'])}\n"
    text += f"Активна до: {end_date.strftime('%d.%m.%Y')}\n"
    text += f"Осталось дней: {days_left}\n"
    
    if subscription['auto_renew']:
        text += "♻️ Автопродление: Включено\n"
    
    return text


def check_subscription(user_id: int) -> bool:
    """Проверка наличия активной подписки"""
    subscription = db.get_active_subscription(user_id)
    
    if not subscription:
        return False
    
    end_date = datetime.fromisoformat(subscription['end_date'])
    return end_date > datetime.now()


def detect_contacts_in_text(text: str) -> List[Tuple[str, str]]:
    """Детектор контактов в тексте"""
    contacts = []
    
    for contact_type, pattern in CONTACT_DETECTOR_PATTERNS.items():
        matches = re.findall(pattern, text)
        for match in matches:
            contacts.append((contact_type, match))
    
    return contacts


async def create_archive_from_messages(
    messages: List[Dict],
    chat_id: int,
    user_id: int
) -> Optional[Path]:
    """Создание ZIP архива из удаленных сообщений"""
    try:
        # Создаем директорию для архивов
        archive_dir = MEDIA_PATH / "archives" / str(user_id)
        archive_dir.mkdir(parents=True, exist_ok=True)
        
        # Имя архива
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archive_name = f"deleted_chat_{chat_id}_{timestamp}.zip"
        archive_path = archive_dir / archive_name
        
        # Создаем архив
        with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Добавляем JSON с метаданными
            metadata = {
                "chat_id": chat_id,
                "user_id": user_id,
                "created_at": timestamp,
                "messages_count": len(messages),
                "messages": []
            }
            
            for msg in messages:
                msg_data = {
                    "message_id": msg['message_id'],
                    "sender_name": msg['sender_name'],
                    "text": msg['text'],
                    "message_type": msg['message_type'],
                    "created_at": msg['created_at'],
                    "deleted_at": msg.get('deleted_at')
                }
                
                metadata["messages"].append(msg_data)
                
                # Если есть медиа - добавляем в архив
                if msg.get('media_path') and Path(msg['media_path']).exists():
                    media_file = Path(msg['media_path'])
                    arcname = f"media/{msg['message_id']}_{media_file.name}"
                    zipf.write(media_file, arcname=arcname)
            
            # Сохраняем метаданные
            zipf.writestr("metadata.json", json.dumps(metadata, ensure_ascii=False, indent=2))
        
        return archive_path
        
    except Exception as e:
        import logging
        logging.error(f"Ошибка создания архива: {e}")
        return None


def format_message_for_display(message: Dict, show_details: bool = True) -> str:
    """Форматирование сообщения для отображения"""
    text = ""
    
    if show_details:
        created_at = datetime.fromisoformat(message['created_at'])
        text += f"🕐 {created_at.strftime('%d.%m.%Y %H:%M')}\n"
        text += f"👤 {message['sender_name']}\n"
        text += f"💬 Чат: {message['chat_title']}\n\n"
    
    if message['is_edited']:
        text += "✏️ <b>Было:</b>\n"
        text += f"{message['original_text']}\n\n"
        text += "📝 <b>Стало:</b>\n"
        text += f"{message['text']}\n"
    elif message['is_deleted']:
        if message['text']:
            text += f"🗑 <b>Удалено:</b>\n{message['text']}\n"
        else:
            text += f"🗑 <b>Удалено {message['message_type']}</b>\n"
    else:
        if message['text']:
            text += message['text']
    
    return text


def format_contact_list(contacts: List[Dict], contact_type: str = None) -> str:
    """Форматирование списка обнаруженных контактов"""
    if not contacts:
        return "📭 Контакты не обнаружены"
    
    contact_icons = {
        "phone": "📞",
        "email": "📧",
        "telegram": "🔗",
        "url": "🌐"
    }
    
    text = f"<b>Обнаруженные контакты</b>\n\n"
    
    grouped_contacts = {}
    for contact in contacts:
        ctype = contact['contact_type']
        if ctype not in grouped_contacts:
            grouped_contacts[ctype] = []
        grouped_contacts[ctype].append(contact)
    
    for ctype, items in grouped_contacts.items():
        if contact_type and ctype != contact_type:
            continue
            
        icon = contact_icons.get(ctype, "📌")
        text += f"{icon} <b>{ctype.upper()}</b>:\n"
        
        unique_values = set(item['contact_value'] for item in items)
        for value in sorted(unique_values):
            text += f"  • {value}\n"
        text += "\n"
    
    return text


def format_checklist(checklist: Dict, items: List[Dict]) -> str:
    """Форматирование чеклиста"""
    total = len(items)
    completed = sum(1 for item in items if item['is_completed'])
    progress = int((completed / total * 100)) if total > 0 else 0
    
    text = f"📋 <b>{checklist['title']}</b>\n"
    text += f"Прогресс: {completed}/{total} ({progress}%)\n\n"
    
    for item in items:
        status = "✅" if item['is_completed'] else "⬜"
        text += f"{status} {item['text']}\n"
    
    return text


def sanitize_filename(filename: str) -> str:
    """Очистка имени файла от недопустимых символов"""
    # Убираем недопустимые символы
    filename = re.sub(r'[<>:"/\\|?*]', '', filename)
    # Ограничиваем длину
    if len(filename) > 200:
        filename = filename[:200]
    return filename


def format_file_size(size_bytes: int) -> str:
    """Форматирование размера файла"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"


def is_business_api_compatible(message_type: str) -> bool:
    """Проверка совместимости типа сообщения с Business API"""
    incompatible_types = [
        'self_destruct',
        'view_once',
        'secret_chat'
    ]
    return message_type not in incompatible_types


def generate_export_filename(export_format: str, user_id: int) -> str:
    """Генерация имени файла для экспорта"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"merai_export_{user_id}_{timestamp}.{export_format}"


async def export_to_json(messages: List[Dict]) -> str:
    """Экспорт сообщений в JSON"""
    export_data = {
        "exported_at": datetime.now().isoformat(),
        "total_messages": len(messages),
        "messages": messages
    }
    return json.dumps(export_data, ensure_ascii=False, indent=2)


async def export_to_csv(messages: List[Dict]) -> str:
    """Экспорт сообщений в CSV"""
    import csv
    import io
    
    output = io.StringIO()
    
    if not messages:
        return ""
    
    fieldnames = ['message_id', 'chat_title', 'sender_name', 'text', 
                  'message_type', 'is_deleted', 'is_edited', 'created_at']
    
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    
    for msg in messages:
        row = {k: msg.get(k, '') for k in fieldnames}
        writer.writerow(row)
    
    return output.getvalue()


async def export_to_html(messages: List[Dict], user_info: Dict = None) -> str:
    """Экспорт сообщений в HTML"""
    from config import BRAND_NAME
    
    html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{BRAND_NAME} - Экспорт</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            max-width: 900px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }}
        .header {{
            background: #6C5CE7;
            color: white;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
        }}
        .message {{
            background: white;
            padding: 15px;
            margin-bottom: 10px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .deleted {{ border-left: 4px solid #e74c3c; }}
        .edited {{ border-left: 4px solid #f39c12; }}
        .meta {{
            color: #7f8c8d;
            font-size: 0.9em;
            margin-bottom: 10px;
        }}
        .text {{
            line-height: 1.5;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>{BRAND_NAME}</h1>
        <p>Экспорт сообщений от {datetime.now().strftime('%d.%m.%Y %H:%M')}</p>
        <p>Всего сообщений: {len(messages)}</p>
    </div>
"""
    
    for msg in messages:
        css_class = ""
        if msg.get('is_deleted'):
            css_class = "deleted"
        elif msg.get('is_edited'):
            css_class = "edited"
        
        created_at = datetime.fromisoformat(msg['created_at']).strftime('%d.%m.%Y %H:%M')
        
        html += f"""
    <div class="message {css_class}">
        <div class="meta">
            <strong>{msg.get('sender_name', 'Unknown')}</strong> | 
            {msg.get('chat_title', 'Unknown')} | 
            {created_at}
        </div>
        <div class="text">
            {msg.get('text', f"[{msg.get('message_type', 'unknown')}]")}
        </div>
    </div>
"""
    
    html += """
</body>
</html>
"""
    
    return html


def calculate_message_limit(plan_type: str) -> int:
    """Получить лимит сообщений для плана"""
    from config import SUBSCRIPTION_PLANS
    
    plan = SUBSCRIPTION_PLANS.get(plan_type)
    if not plan:
        return 0
    
    return plan.get('max_messages', 100)


def can_save_message(user_id: int) -> Tuple[bool, Optional[str]]:
    """Проверить может ли пользователь сохранить еще сообщения"""
    subscription = db.get_active_subscription(user_id)
    
    if not subscription:
        return False, "Нет активной подписки"
    
    plan_type = subscription['plan_type']
    max_messages = calculate_message_limit(plan_type)
    
    # -1 означает безлимит
    if max_messages == -1:
        return True, None
    
    current_count = db.get_message_count(user_id)
    
    if current_count >= max_messages:
        return False, f"Достигнут лимит сообщений ({max_messages})"
    
    return True, None
