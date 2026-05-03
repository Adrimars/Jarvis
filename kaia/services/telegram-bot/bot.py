import asyncio
import json
import logging
import os
import uuid

import redis as redis_lib
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
    constants,
)
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from security import is_allowed

logger = logging.getLogger("telegram-bot")

TOKEN = os.getenv("TELEGRAM_TOKEN", "")
CHAT_ID = int(os.getenv("TELEGRAM_CHAT_ID", "0"))
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

r = redis_lib.Redis.from_url(REDIS_URL, decode_responses=True)

AGENT_INBOX = "queue:agent:inbox"


# ─── Helpers ───────────────────────────────────────────────────────────────

async def send_to_agent(user_id: str, text: str) -> str:
    request_id = str(uuid.uuid4())
    payload = json.dumps({"request_id": request_id, "user_id": user_id, "text": text})
    r.rpush(AGENT_INBOX, payload)

    response_key = f"response:{request_id}"
    result = await asyncio.get_event_loop().run_in_executor(
        None, lambda: r.blpop(response_key, timeout=180)
    )
    if result:
        return json.loads(result[1])["text"]
    return "⏳ No response yet — Mistral might be busy. Try again in a moment."


async def ask_approval(context: ContextTypes.DEFAULT_TYPE, description: str, action_id: str):
    keyboard = [[
        InlineKeyboardButton("✅ Confirm", callback_data=f"approve_{action_id}"),
        InlineKeyboardButton("❌ Cancel",  callback_data="cancel"),
    ]]
    await context.bot.send_message(
        CHAT_ID,
        f"⚠️ Approval required:\n{description}",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


# ─── Handlers ──────────────────────────────────────────────────────────────

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return
    user_id = str(update.effective_user.id)
    await context.bot.send_chat_action(update.effective_chat.id, constants.ChatAction.TYPING)
    response = await send_to_agent(user_id, update.message.text)
    if response:
        await update.message.reply_text(response)


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return
    user_id = str(update.effective_user.id)
    photo = update.message.photo[-1]
    file = await photo.get_file()
    path = f"/data/kaia/photos/ref_{update.message.message_id}.jpg"
    await file.download_to_drive(path)

    response = await send_to_agent(user_id, f"__photo__:{path}")
    await update.message.reply_text(response)


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return
    if not update.message.document.file_name.endswith(".yaml"):
        return
    user_id = str(update.effective_user.id)
    file = await update.message.document.get_file()
    content = await file.download_as_bytearray()
    response = await send_to_agent(user_id, f"__yaml__:{content.decode('utf-8')}")
    await update.message.reply_text(response)


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "cancel":
        await query.edit_message_text("❌ Cancelled.")
        return

    if data.startswith("approve_"):
        action_id = data[len("approve_"):]
        user_id = str(update.effective_user.id)
        response = await send_to_agent(user_id, f"__approved__:{action_id}")
        await query.edit_message_text(f"✅ Confirmed.\n{response}")
        return

    if data.startswith("feedback_"):
        _, sentiment, item_id = data.split("_", 2)
        user_id = str(update.effective_user.id)
        await send_to_agent(user_id, f"__feedback__:{sentiment}:{item_id}")
        await query.edit_message_reply_markup(reply_markup=None)
        return


async def cmd_addsite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return
    if not context.args:
        await update.message.reply_text("Usage: /addsite <url>\nExample: /addsite https://www.no362.com")
        return
    url = context.args[0]
    user_id = str(update.effective_user.id)
    response = await send_to_agent(user_id, f"__addsite__:{url}")
    await update.message.reply_text(response)


async def cmd_listsites(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return
    user_id = str(update.effective_user.id)
    response = await send_to_agent(user_id, "__listsites__")
    await update.message.reply_text(response)


async def cmd_module(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /module <name> <on|off>")
        return
    user_id = str(update.effective_user.id)
    response = await send_to_agent(user_id, f"__module__:{context.args[0]}:{context.args[1]}")
    await update.message.reply_text(response)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return
    await context.bot.send_chat_action(update.effective_chat.id, constants.ChatAction.TYPING)
    user_id = str(update.effective_user.id)
    response = await send_to_agent(user_id, "__start__")
    await update.message.reply_text(response)


# ─── Proactive message poller ───────────────────────────────────────────────

async def proactive_poller(bot):
    """Background task — polls Redis for module-generated messages and sends them."""
    logger.info("Proactive poller started")
    loop = asyncio.get_event_loop()
    while True:
        try:
            result = await loop.run_in_executor(
                None, lambda: r.blpop("queue:telegram:outbox", timeout=5)
            )
            if result:
                msg = json.loads(result[1])
                text = msg.get("text", "")
                if not text:
                    continue
                buttons = msg.get("buttons", [])
                markup = None
                if buttons:
                    keyboard = [[InlineKeyboardButton(b["label"], callback_data=b["data"]) for b in row] for row in buttons]
                    markup = InlineKeyboardMarkup(keyboard)
                await bot.send_message(CHAT_ID, text, reply_markup=markup)
        except Exception as e:
            logger.error(f"Proactive poller error: {e}")
            await asyncio.sleep(5)


# ─── Entry point ────────────────────────────────────────────────────────────

async def post_init(app: Application):
    asyncio.create_task(proactive_poller(app.bot))


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] [telegram-bot] %(message)s",
    )

    app = (
        Application.builder()
        .token(TOKEN)
        .post_init(post_init)
        .build()
    )

    app.add_handler(CommandHandler("start",     cmd_start))
    app.add_handler(CommandHandler("addsite",   cmd_addsite))
    app.add_handler(CommandHandler("listsites", cmd_listsites))
    app.add_handler(CommandHandler("module",    cmd_module))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.PHOTO,    handle_photo))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(CallbackQueryHandler(handle_callback))

    logger.info("KAIA Telegram Bot starting...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
