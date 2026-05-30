import logging
import asyncio
from datetime import time
import pytz

from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes, ConversationHandler
)

from database import Database
from hh_parser import HHParser
from ai_analyzer import AIAnalyzer
from config import BOT_TOKEN, TIMEZONE

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Состояния онбординга
NAME, EXPERIENCE, SPECIALIZATION, CITY = range(4)

db = Database()
parser = HHParser()
ai = AIAnalyzer()


# ─── /start ──────────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    existing = db.get_user(user_id)

    if existing:
        await update.message.reply_text(
            f"С возвращением, {existing['name']}! 👋\n\n"
            "Используй меню ниже:",
            reply_markup=main_menu()
        )
        return ConversationHandler.END

    await update.message.reply_text(
        "Привет! 👋\n\n"
        "Помогу следить за новыми вакансиями в маркетинге — "
        "SMM, digital, brand, performance, PR и другие направления.\n\n"
        "Пара коротких вопросов, чтобы я знал кто ты. "
        "Это нужно чтобы в будущем делать подборку под тебя.\n\n"
        "Как тебя зовут? (имя и фамилия)",
        reply_markup=ReplyKeyboardRemove()
    )
    return NAME


async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["name"] = update.message.text.strip()

    keyboard = ReplyKeyboardMarkup(
        [["Нет опыта (0–1 год)", "Junior (1–2 года)"],
         ["Middle (2–4 года)", "Senior (4+ лет)"]],
        resize_keyboard=True, one_time_keyboard=True
    )
    await update.message.reply_text(
        f"Приятно познакомиться, {context.user_data['name']}! 🙌\n\n"
        "Какой у тебя опыт в маркетинге?",
        reply_markup=keyboard
    )
    return EXPERIENCE


async def get_experience(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["experience"] = update.message.text.strip()

    keyboard = ReplyKeyboardMarkup(
        [["SMM / Соцсети", "Digital / Performance"],
         ["Brand / Маркетинг", "PR / Коммуникации"],
         ["Контент / Копирайтинг", "Другое"]],
        resize_keyboard=True, one_time_keyboard=True
    )
    await update.message.reply_text(
        "Какое направление тебе ближе?",
        reply_markup=keyboard
    )
    return SPECIALIZATION


async def get_specialization(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["specialization"] = update.message.text.strip()

    await update.message.reply_text(
        "В каком городе ищешь работу? (или напиши «Удалённо»)",
        reply_markup=ReplyKeyboardRemove()
    )
    return CITY


async def get_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["city"] = update.message.text.strip()
    user_id = update.effective_user.id

    db.save_user(
        user_id=user_id,
        name=context.user_data["name"],
        experience=context.user_data["experience"],
        specialization=context.user_data["specialization"],
        city=context.user_data["city"]
    )

    await update.message.reply_text(
        f"Отлично! Всё сохранено ✅\n\n"
        f"👤 {context.user_data['name']}\n"
        f"📊 Опыт: {context.user_data['experience']}\n"
        f"🎯 Направление: {context.user_data['specialization']}\n"
        f"📍 Город: {context.user_data['city']}\n\n"
        "Каждый день буду присылать свежие вакансии 📬\n"
        "Используй /jobs чтобы получить подборку прямо сейчас!",
        reply_markup=main_menu()
    )
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Отменено.", reply_markup=main_menu())
    return ConversationHandler.END


# ─── Меню ────────────────────────────────────────────────────────────────────

def main_menu():
    return ReplyKeyboardMarkup(
        [["📋 Вакансии сейчас", "📄 Анализ резюме /cv"],
         ["⚙️ Мой профиль", "ℹ️ Помощь"]],
        resize_keyboard=True
    )


# ─── /jobs ───────────────────────────────────────────────────────────────────

async def send_jobs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = db.get_user(user_id)

    if not user:
        await update.message.reply_text("Сначала пройди онбординг — нажми /start")
        return

    await update.message.reply_text("🔍 Ищу свежие вакансии для тебя...")

    jobs = parser.fetch_jobs(
        specialization=user["specialization"],
        city=user["city"],
        experience=user["experience"]
    )

    if not jobs:
        await update.message.reply_text(
            "😔 Сейчас ничего не нашлось. Попробуй позже — обновляю базу каждый день."
        )
        return

    text = f"📋 *Свежие вакансии — {user['specialization']}*\n"
    text += f"📍 {user['city']} | {user['experience']}\n\n"

    for i, job in enumerate(jobs[:8], 1):
        text += (
            f"*{i}. {job['name']}*\n"
            f"🏢 {job['employer']}\n"
            f"💰 {job['salary']}\n"
            f"🔗 [Открыть]({job['url']})\n\n"
        )

    await update.message.reply_text(
        text,
        parse_mode="Markdown",
        disable_web_page_preview=True
    )


# ─── /cv ─────────────────────────────────────────────────────────────────────

async def cv_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📄 Пришли своё резюме в формате PDF или текстом, "
        "и я подберу топ-5 подходящих вакансий специально под тебя."
    )


async def handle_cv_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = db.get_user(user_id)

    if not user:
        await update.message.reply_text("Сначала пройди онбординг — нажми /start")
        return

    await update.message.reply_text("⏳ Анализирую резюме, подожди 10–20 секунд...")

    doc = update.message.document
    file = await context.bot.get_file(doc.file_id)
    file_bytes = await file.download_as_bytearray()
    cv_text = ai.extract_text_from_pdf(bytes(file_bytes))

    jobs = parser.fetch_jobs(
        specialization=user["specialization"],
        city=user["city"],
        experience=user["experience"],
        limit=20
    )

    top5 = await ai.match_cv_to_jobs(cv_text, jobs)

    text = "🎯 *Топ-5 вакансий под твоё резюме:*\n\n"
    for i, job in enumerate(top5, 1):
        text += (
            f"*{i}. {job['name']}*\n"
            f"🏢 {job['employer']}\n"
            f"💰 {job['salary']}\n"
            f"✅ {job.get('reason', '')}\n"
            f"🔗 [Открыть]({job['url']})\n\n"
        )

    await update.message.reply_text(
        text,
        parse_mode="Markdown",
        disable_web_page_preview=True
    )


async def handle_cv_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка резюме, присланного текстом (только если предыдущее сообщение было /cv)"""
    pass  # Реализуется через ConversationHandler при желании


# ─── Профиль ─────────────────────────────────────────────────────────────────

async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = db.get_user(user_id)

    if not user:
        await update.message.reply_text("Сначала пройди онбординг — нажми /start")
        return

    await update.message.reply_text(
        f"👤 *Твой профиль*\n\n"
        f"Имя: {user['name']}\n"
        f"Опыт: {user['experience']}\n"
        f"Направление: {user['specialization']}\n"
        f"Город: {user['city']}\n\n"
        "Чтобы обновить профиль — нажми /start",
        parse_mode="Markdown"
    )


# ─── Помощь ──────────────────────────────────────────────────────────────────

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "ℹ️ *Что умею:*\n\n"
        "📋 *Вакансии сейчас* — свежая подборка с hh.ru\n"
        "📄 */cv* — анализ резюме и топ-5 вакансий под тебя\n"
        "⚙️ *Профиль* — посмотреть свои данные\n\n"
        "Вакансии обновляются ежедневно в 9:00 🕘\n\n"
        "Источники: hh.ru, корпоративные сайты",
        parse_mode="Markdown",
        reply_markup=main_menu()
    )


# ─── Текстовые кнопки меню ───────────────────────────────────────────────────

async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if "Вакансии" in text:
        await send_jobs(update, context)
    elif "резюме" in text or "/cv" in text:
        await cv_command(update, context)
    elif "профиль" in text.lower() or "Профиль" in text:
        await profile(update, context)
    elif "Помощь" in text:
        await help_command(update, context)


# ─── Ежедневная рассылка ─────────────────────────────────────────────────────

async def daily_broadcast(context: ContextTypes.DEFAULT_TYPE):
    users = db.get_all_users()
    logger.info(f"Daily broadcast: {len(users)} users")

    for user in users:
        try:
            jobs = parser.fetch_jobs(
                specialization=user["specialization"],
                city=user["city"],
                experience=user["experience"]
            )
            if not jobs:
                continue

            text = f"☀️ *Доброе утро, {user['name']}!*\n\n"
            text += f"📋 Свежие вакансии по направлению *{user['specialization']}*:\n\n"

            for i, job in enumerate(jobs[:5], 1):
                text += (
                    f"*{i}. {job['name']}*\n"
                    f"🏢 {job['employer']} | 💰 {job['salary']}\n"
                    f"🔗 [Открыть]({job['url']})\n\n"
                )

            text += "Чтобы получить больше вакансий — нажми 📋 *Вакансии сейчас*"

            await context.bot.send_message(
                chat_id=user["user_id"],
                text=text,
                parse_mode="Markdown",
                disable_web_page_preview=True
            )
        except Exception as e:
            logger.error(f"Failed to send to {user['user_id']}: {e}")


# ─── main ─────────────────────────────────────────────────────────────────────

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # Онбординг
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            EXPERIENCE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_experience)],
            SPECIALIZATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_specialization)],
            CITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_city)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("jobs", send_jobs))
    app.add_handler(CommandHandler("cv", cv_command))
    app.add_handler(CommandHandler("profile", profile))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.Document.PDF, handle_cv_document))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_menu))

    # Ежедневная рассылка в 9:00 по Москве
    tz = pytz.timezone(TIMEZONE)
    app.job_queue.run_daily(
        daily_broadcast,
        time=time(hour=9, minute=0, tzinfo=tz)
    )

    logger.info("Bot started!")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
