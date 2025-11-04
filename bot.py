import json
import os
import logging
import asyncio
import re
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# === ВАШИ ДАННЫЕ ===
ADMIN_ID = 547184563
BOT_TOKEN = "8040981560:AAEWrS0UirkiPA_u1yATkgoSmhbTrFYl414"
SECRET_PASSWORD = "1914777"
DATA_FILE = "data.json"

# Загрузка данных
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
            return data.get("contacts", {}), data.get("groups", {}), data.get("permissions", {})
    return {}, {}, {}

def save_data(contacts, groups, permissions):
    with open(DATA_FILE, "w") as f:
        json.dump({"contacts": contacts, "groups": groups, "permissions": permissions}, f, indent=2)

contacts, groups, permissions = load_data()

# === Вспомогательные функции ===
def is_valid_group(group):
    return re.fullmatch(r"[A-Z]", group) is not None

def is_valid_contact_id(cid):
    return re.fullmatch(r"\d{3}", cid) is not None and 1 <= int(cid) <= 999

def is_valid_full_code(code):
    return re.fullmatch(r"[A-Z]\d{3}", code) is not None

def get_contact_id_from_code(code):
    if is_valid_full_code(code):
        return code[1:]
    return None

def get_user_permission_level(user_id):
    for cid, uid in contacts.items():
        if uid == user_id:
            return permissions.get(cid, 0)
    return 0

def resolve_recipients(recipient_input):
    result = set()
    for item in recipient_input:
        item = item.strip()
        if item == "VSEM":
            result.update(contacts.keys())
        elif is_valid_group(item):
            if item in groups:
                result.update(groups[item])
        elif is_valid_contact_id(item):
            if item in contacts:
                result.add(item)
        elif is_valid_full_code(item):
            cid = get_contact_id_from_code(item)
            if cid and cid in contacts:
                result.add(cid)
    return list(result)

# === Команды админа ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id == ADMIN_ID:
        await update.message.reply_text(
            "🔐 Админ-панель:\n"
            "/add <001> <123456789> — добавить контакт\n"
            "/assign <001> <A> — добавить в группу\n"
            "/unassign <001> <A> — удалить из группы\n"
            "/rename_group <A> <Z> — переименовать группу\n"
            "/del <001> — удалить контакт\n"
            "/delgroup <A> — удалить группу\n"
            "/export_contacts — выгрузить контакты\n"
            "/import_contacts — загрузить контакты\n"
            "/set_permission <001> <0|1|2|3> — выдать права\n"
            "/list — показать всё"
        )
    else:
        level = get_user_permission_level(user_id)
        perm_desc = {
            0: "Личные сообщения",
            1: "Личные + группа",
            2: "Личные + всем в группах",
            3: "Все (личные, группы, VSEM)"
        }
        await update.message.reply_text(
            f"Ваши права: {perm_desc.get(level, 'Неизвестно')}\n\n"
            "Шаблон отправки:\n"
            "Кому: [ID]\n"
            "Пароль: [Password]\n"
            "Сообщение: [Текст]\n\n"
            "Пример:\n"
            "Кому: A001\n"
            "Пароль: <пароль>\n"
            "Сообщение: Привет!"
        )

async def add_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    if len(context.args) != 2: await update.message.reply_text("Использование: /add 001 123456789"); return
    cid, user_id_str = context.args
    if not is_valid_contact_id(cid) or not user_id_str.isdigit(): await update.message.reply_text("Неверный формат"); return
    contacts[cid] = int(user_id_str)
    save_data(contacts, groups, permissions)
    await update.message.reply_text(f"✅ Контакт {cid} → {user_id_str}")

async def assign_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    if len(context.args) != 2: await update.message.reply_text("Использование: /assign 001 A"); return
    cid, grp = context.args
    if not (is_valid_contact_id(cid) and is_valid_group(grp)): await update.message.reply_text("Неверный формат"); return
    if cid not in contacts: await update.message.reply_text("Контакт не существует"); return
    if grp not in groups: groups[grp] = []
    if cid not in groups[grp]: groups[grp].append(cid)
    save_data(contacts, groups, permissions)
    await update.message.reply_text(f"✅ {cid} добавлен в группу {grp}")

async def unassign_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    if len(context.args) != 2: await update.message.reply_text("Использование: /unassign 001 A"); return
    cid, grp = context.args
    if not (is_valid_contact_id(cid) and is_valid_group(grp)): await update.message.reply_text("Неверный формат"); return
    if grp in groups and cid in groups[grp]: groups[grp].remove(cid)
    save_data(contacts, groups, permissions)
    await update.message.reply_text(f"🗑️ {cid} удалён из группы {grp}")

async def rename_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    if len(context.args) != 2: await update.message.reply_text("Использование: /rename_group A Z"); return
    old_grp, new_grp = context.args
    if not (is_valid_group(old_grp) and is_valid_group(new_grp)): await update.message.reply_text("Неверный формат"); return
    if old_grp not in groups: await update.message.reply_text("Группа не существует"); return
    if new_grp not in groups: groups[new_grp] = []
    groups[new_grp].extend(groups[old_grp])
    del groups[old_grp]
    save_data(contacts, groups, permissions)
    await update.message.reply_text(f"✅ Группа {old_grp} переименована в {new_grp}")

async def del_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    if len(context.args) != 1: await update.message.reply_text("Использование: /del 001"); return
    cid = context.args[0]
    if not is_valid_contact_id(cid): await update.message.reply_text("Неверный формат"); return
    if cid in contacts:
        del contacts[cid]
        for grp in groups:
            if cid in groups[grp]: groups[grp].remove(cid)
        if cid in permissions: del permissions[cid]
    save_data(contacts, groups, permissions)
    await update.message.reply_text(f"🗑️ Контакт {cid} удалён")

async def del_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    if len(context.args) != 1: await update.message.reply_text("Использование: /delgroup A"); return
    grp = context.args[0]
    if not is_valid_group(grp): await update.message.reply_text("Неверный формат"); return
    if grp in groups: del groups[grp]
    save_data(contacts, groups, permissions)
    await update.message.reply_text(f"🗑️ Группа {grp} удалена")

async def export_contacts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    await update.message.reply_document(document=open(DATA_FILE, 'rb'), filename="data.json")

async def import_contacts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    file = await context.bot.get_file(update.message.document.file_id)
    await file.download_to_drive("temp_data.json")
    with open("temp_data.json", "r") as f:
        data = json.load(f)
        global contacts, groups, permissions
        contacts = data.get("contacts", {})
        groups = data.get("groups", {})
        permissions = data.get("permissions", {})
    save_data(contacts, groups, permissions)
    await update.message.reply_text("✅ Контакты загружены")

async def set_permission(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    if len(context.args) != 2: await update.message.reply_text("Использование: /set_permission 001 1"); return
    cid, level_str = context.args
    if not (is_valid_contact_id(cid) and level_str.isdigit() and 0 <= int(level_str) <= 3): await update.message.reply_text("Неверный формат"); return
    permissions[cid] = int(level_str)
    save_data(contacts, groups, permissions)
    await update.message.reply_text(f"✅ Права для {cid} изменены на {level_str}")

async def list_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    text = "📇 Контакты:\n"
    for cid, uid in sorted(contacts.items()):
        perm = permissions.get(cid, 0)
        text += f"  {cid} → {uid} (права: {perm})\n"
    text += "\n📁 Группы:\n"
    for grp in sorted(groups.keys()):
        members = groups[grp]
        if members: text += f"  {grp}: {', '.join(sorted(members))}\n"
        else: text += f"  {grp}: (пусто)\n"
    await update.message.reply_text(text)

# === Отправка сообщений ===
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    message = update.message
    text = message.text.strip()
    original_message_id = message.message_id

    # Попробовать распознать шаблон
    pattern = r"Кому:\s*(\w+)\s*\nПароль:\s*([^\n]+)\s*\nСообщение:\s*(.+)"
    match = re.search(pattern, text, re.DOTALL)

    if match:
        recipient_input_raw = match.group(1)
        password = match.group(2)
        message_body = match.group(3).strip()
    else:
        # Старый формат
        parts = text.split(" ", 2)
        if len(parts) < 3: return
        recipient_input_raw, password, message_body = parts

    if password != SECRET_PASSWORD: return

    # Проверка прав
    user_perm = get_user_permission_level(user_id)
    if user_perm < 1 and recipient_input_raw in groups:
        return
    if user_perm < 2 and recipient_input_raw == "VSEM":
        return

    recipient_input = [x.strip() for x in recipient_input_raw.split(",")]
    contact_ids = resolve_recipients(recipient_input)
    valid_recipients = [cid for cid in contact_ids if cid in contacts]
    if not valid_recipients: return

    # Найти код отправителя
    sender_cid = None
    for cid, uid in contacts.items():
        if uid == user_id:
            sender_cid = cid
            break
    if sender_cid is None: return

    # Подтверждение
    sent_msg = await context.bot.send_message(chat_id=user_id, text=f"✅ Сообщение отправлено {len(valid_recipients)} получателям")

    # Отправка
    for cid in valid_recipients:
        recipient_id = contacts[cid]
        try:
            await context.bot.send_message(chat_id=recipient_id, text=f"📩 От: {sender_cid}\n\n{message_body}")
        except Exception as e: logging.warning(f"Не удалось доставить {cid}: {e}")

    # Удаление
    await asyncio.sleep(1.5)
    try: await context.bot.delete_message(chat_id=user_id, message_id=sent_msg.message_id)
    except: pass
    try: await context.bot.delete_message(chat_id=user_id, message_id=original_message_id)
    except: pass

# === Запуск ===
def main():
    logging.basicConfig(level=logging.INFO)
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("add", add_contact))
    app.add_handler(CommandHandler("assign", assign_contact))
    app.add_handler(CommandHandler("unassign", unassign_contact))
    app.add_handler(CommandHandler("rename_group", rename_group))
    app.add_handler(CommandHandler("del", del_contact))
    app.add_handler(CommandHandler("delgroup", del_group))
    app.add_handler(CommandHandler("export_contacts", export_contacts))
    app.add_handler(CommandHandler("import_contacts", import_contacts))
    app.add_handler(CommandHandler("set_permission", set_permission))
    app.add_handler(CommandHandler("list", list_data))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("✅ Бот запускается...")
    app.run_polling()

if __name__ == "__main__":
    main()

