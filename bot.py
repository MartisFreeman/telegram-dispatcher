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
            return data.get("contacts", {}), data.get("groups", {})
    return {}, {}

def save_data(contacts, groups):
    with open(DATA_FILE, "w") as f:
        json.dump({"contacts": contacts, "groups": groups}, f, indent=2)

contacts, groups = load_data()

# === Вспомогательные функции ===
def is_valid_group(grp):
    return re.fullmatch(r"[A-Z]", grp) is not None

def is_valid_contact_id(cid):
    return re.fullmatch(r"\d{3}", cid) is not None and 1 <= int(cid) <= 999

def is_valid_full_code(code):
    return re.fullmatch(r"[A-Z]\d{3}", code) is not None

def get_contact_id_from_code(code):
    if is_valid_full_code(code):
        return code[1:]
    return None

def resolve_recipients(recipient_input):
    """Преобразует получателей: 'A', '001', 'A001', 'VSE' → список contact_id"""
    result = set()
    for item in recipient_input:
        item = item.strip()
        if item == "VSE":
            result.update(contacts.keys())
        elif is_valid_group(item):  # группа: A
            if item in groups:
                result.update(groups[item])
        elif is_valid_contact_id(item):  # контакт: 001
            if item in contacts:
                result.add(item)
        elif is_valid_full_code(item):  # полный код: A001
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
            "/assign <001> <A> — добавить контакт в группу\n"
            "/unassign <001> <A> — удалить из группы\n"
            "/del <001> — удалить контакт полностью\n"
            "/delgroup <A> — удалить группу (контакты сохраняются)\n"
            "/clearall — удалить ВСЁ\n"
            "/list — показать всё"
        )
    else:
        await update.message.reply_text(
            "📩 Отправьте: <код> <пароль> Текст\n"
            "Примеры:\n001 <пароль> Лично\nA <пароль> Всем из группы A\nVSE <пароль> Всем!"
        )

# Добавить контакт
async def add_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if len(context.args) != 2:
        await update.message.reply_text("Использование: /add 001 123456789")
        return
    cid, user_id_str = context.args
    if not is_valid_contact_id(cid):
        await update.message.reply_text("ID контакта: 001–999")
        return
    if not user_id_str.isdigit():
        await update.message.reply_text("ID должен быть числом.")
        return
    contacts[cid] = int(user_id_str)
    save_data(contacts, groups)
    await update.message.reply_text(f"✅ Контакт {cid} → {user_id_str}")

# Назначить контакт в группу
async def assign_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if len(context.args) != 2:
        await update.message.reply_text("Использование: /assign 001 A")
        return
    cid, grp = context.args
    if not is_valid_contact_id(cid):
        await update.message.reply_text("Неверный ID контакта.")
        return
    if not is_valid_group(grp):
        await update.message.reply_text("Неверная группа (A–Z).")
        return
    if cid not in contacts:
        await update.message.reply_text("Контакт не существует.")
        return
    if grp not in groups:
        groups[grp] = []
    if cid not in groups[grp]:
        groups[grp].append(cid)
        save_data(contacts, groups)
        await update.message.reply_text(f"✅ {cid} добавлен в группу {grp}")
    else:
        await update.message.reply_text(f"ℹ️ {cid} уже в группе {grp}")

# Удалить контакт из группы
async def unassign_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if len(context.args) != 2:
        await update.message.reply_text("Использование: /unassign 001 A")
        return
    cid, grp = context.args
    if not is_valid_contact_id(cid):
        await update.message.reply_text("Неверный ID контакта.")
        return
    if not is_valid_group(grp):
        await update.message.reply_text("Неверная группа.")
        return
    if grp in groups and cid in groups[grp]:
        groups[grp].remove(cid)
        save_data(contacts, groups)
        await update.message.reply_text(f"🗑️ {cid} удалён из группы {grp}")
    else:
        await update.message.reply_text(f"ℹ️ {cid} не в группе {grp}")

# Удалить контакт (из всех групп)
async def del_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if len(context.args) != 1:
        await update.message.reply_text("Использование: /del 001")
        return
    cid = context.args[0]
    if not is_valid_contact_id(cid):
        await update.message.reply_text("Неверный ID контакта.")
        return
    if cid not in contacts:
        await update.message.reply_text("Контакт не найден.")
        return
    # Удаляем из всех групп
    for grp in groups:
        if cid in groups[grp]:
            groups[grp].remove(cid)
    del contacts[cid]
    save_data(contacts, groups)
    await update.message.reply_text(f"🗑️ Контакт {cid} удалён полностью")

# Удалить группу (но не контакты)
async def del_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if len(context.args) != 1:
        await update.message.reply_text("Использование: /delgroup A")
        return
    grp = context.args[0]
    if not is_valid_group(grp):
        await update.message.reply_text("Неверная группа.")
        return
    if grp in groups:
        del groups[grp]
        save_data(contacts, groups)
        await update.message.reply_text(f"🗑️ Группа {grp} удалена")
    else:
        await update.message.reply_text(f"Группа {grp} не существует")

# Удалить всё
async def clear_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    global contacts, groups
    contacts.clear()
    groups.clear()
    save_data(contacts, groups)
    await update.message.reply_text("🗑️ ВСЁ удалено")

# Показать всё
async def list_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not contacts:
        await update.message.reply_text("📭 Нет контактов")
        return
    text = "📇 Контакты:\n"
    for cid, uid in sorted(contacts.items()):
        text += f"  {cid} → {uid}\n"
    text += "\n📁 Группы:\n"
    for grp in sorted(groups.keys()):
        members = groups[grp]
        if members:
            text += f"  {grp}: {', '.join(sorted(members))}\n"
        else:
            text += f"  {grp}: (пусто)\n"
    await update.message.reply_text(text)

# === Отправка сообщений ===
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    message = update.message
    text = message.text.strip()
    original_message_id = message.message_id

    parts = text.split(" ", 2)
    if len(parts) < 3:
        return

    recipients_str, password, message_body = parts
    if password != SECRET_PASSWORD:
        return

    recipient_input = [x.strip() for x in recipients_str.split(",")]
    contact_ids = resolve_recipients(recipient_input)
    valid_recipients = [cid for cid in contact_ids if cid in contacts]
    if not valid_recipients:
        return

    # Найти код отправителя (его contact_id)
    sender_cid = None
    for cid, uid in contacts.items():
        if uid == user_id:
            sender_cid = cid
            break
    if sender_cid is None:
        return

    # Подтверждение
    sent_msg = await context.bot.send_message(
        chat_id=user_id,
        text=f"✅ Сообщение отправлено {len(valid_recipients)} получателям"
    )

    # Отправка
    for cid in valid_recipients:
        recipient_id = contacts[cid]
        try:
            await context.bot.send_message(
                chat_id=recipient_id,
                text=f"📩 От: {sender_cid}\n\n{message_body}"
            )
        except Exception as e:
            logging.warning(f"Не удалось доставить {cid}: {e}")

    # Удаление через 1.5 сек
    await asyncio.sleep(1.5)
    try:
        await context.bot.delete_message(chat_id=user_id, message_id=sent_msg.message_id)
    except:
        pass
    try:
        await context.bot.delete_message(chat_id=user_id, message_id=original_message_id)
    except:
        pass

# === Запуск ===
def main():
    logging.basicConfig(level=logging.INFO)
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("add", add_contact))
    app.add_handler(CommandHandler("assign", assign_contact))
    app.add_handler(CommandHandler("unassign", unassign_contact))
    app.add_handler(CommandHandler("del", del_contact))
    app.add_handler(CommandHandler("delgroup", del_group))
    app.add_handler(CommandHandler("clearall", clear_all))
    app.add_handler(CommandHandler("list", list_data))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("✅ Бот запускается...")
    app.run_polling()

if __name__ == "__main__":
    main()
