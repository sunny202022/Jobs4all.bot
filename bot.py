import logging
import asyncio
import requests
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler
)
from dotenv import load_dotenv
import os

# Load environment variables from .env
load_dotenv()

TOKEN = os.getenv("TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

START_JOB_ID = 4231139544
checkjob_progress = {}  # chat_id -> {'job_id': int, 'last_updated': datetime, 'clicks': int}

# === Utility ===

def check_job_urls(start_id, count):
    base_url = "https://www.linkedin.com/jobs/view/"
    headers = {"User-Agent": "Mozilla/5.0"}
    job_status = []
    current_id = start_id

    while len(job_status) < count:
        url = f"{base_url}{current_id}"
        try:
            response = requests.get(url, headers=headers, timeout=5)
            if response.status_code == 200:
                job_status.append((url, "✅ Live"))
            # skip if not 200
        except Exception:
            pass
        current_id += 1

    return job_status, current_id

# === Handlers ===

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome to the LinkedIn Job URL Bot!\n\n"
        "Use /checkjobs to get the next job link.\n"
        "Use /help for assistance."
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📌 Commands:\n"
        "/checkjobs - Get the next LinkedIn job link\n"
        "/help - Show this help message"
    )

async def check_jobs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    now = datetime.utcnow()

    if chat_id not in checkjob_progress:
        checkjob_progress[chat_id] = {
            'job_id': START_JOB_ID,
            'last_updated': now,
            'clicks': 0
        }

    user_data = checkjob_progress[chat_id]
    days_passed = (now - user_data['last_updated']).days
    if days_passed >= 1:
        user_data['job_id'] += 1000 * days_passed
        user_data['last_updated'] += timedelta(days=days_passed)

    current_id = user_data['job_id']
    url = f"https://www.linkedin.com/jobs/view/{current_id}"
    await update.message.reply_text(f"🔗 Job Link: {url}")

    user_data['job_id'] += 1
    user_data['clicks'] += 1

    # Show inline keyboard for 1 or 3 links
    keyboard = [
        [InlineKeyboardButton("Get 1 link", callback_data='more_1')],
        [InlineKeyboardButton("Get 3 links", callback_data='more_3')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("How many job links would you like to get?", reply_markup=reply_markup)

async def send_delayed_links(context, chat_id, start_id, count):
    if count == 1:
        await asyncio.sleep(120)
    elif count == 3:
        await asyncio.sleep(300)

    job_status, next_id = check_job_urls(start_id, count)
    message = "\n".join([f"{url} - {status}" for url, status in job_status])
    await context.bot.send_message(chat_id=chat_id, text=message)

    # Update after successful live link check
    if chat_id in checkjob_progress:
        checkjob_progress[chat_id]['job_id'] = next_id
        checkjob_progress[chat_id]['clicks'] += count

async def handle_more_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    count = int(query.data.split('_')[1])
    chat_id = query.message.chat_id
    now = datetime.utcnow()

    if chat_id not in checkjob_progress:
        checkjob_progress[chat_id] = {
            'job_id': START_JOB_ID,
            'last_updated': now,
            'clicks': 0
        }

    user_data = checkjob_progress[chat_id]
    days_passed = (now - user_data['last_updated']).days
    if days_passed >= 1:
        user_data['job_id'] += 1000 * days_passed
        user_data['last_updated'] += timedelta(days=days_passed)

    start_id = user_data['job_id']

    await query.message.reply_text(f"✅ Your {count} live job link{'s' if count > 1 else ''} will be sent in a few minutes.")

    asyncio.create_task(send_delayed_links(context, chat_id, start_id, count))

# === Main ===

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("checkjobs", check_jobs))
    app.add_handler(CallbackQueryHandler(handle_more_selection, pattern=r"^more_\d+$"))

    app.run_polling()

if __name__ == "__main__":
    main()
