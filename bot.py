import logging
from datetime import time
import pytz

from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes, ConversationHandler
)

from database import Database
from hh_parser import HHParser, SPECIALIZATION_GROUPS
from ai_analyzer import AIAnalyzer
from config import BOT_TOKEN, TIMEZONE, ADMIN_ID

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

NAME, EXPERIENCE, SPEC_GROUP, SPECIALIZATION, CITY = range(5)

db = Database()
parser = HHParser()
ai = AIAnalyzer()


def main_menu():
    return ReplyKeyboardMarkup(
        [["📋 Вакансии сейчас", "📄 Анализ резюме /cv"],
         ["⚙️ Мой профиль", "ℹ️ Помощь"]],
        resize_keyboard=True
    )


def spec_group_menu():
    groups = list(SPECIALIZATION_GROUPS.keys())
    return ReplyKeyboardMarkup(
        [[g] for g in groups],
        resize_keyboard=True, one_time_keyboard=True
    )


def spec_menu(group: str):
    specs = SPECIALIZATION_GROUPS.get(group, [])
    rows = [[s] for s in specs]
    return ReplyKeyboardMarkup(rows, resize_keyboard=True, one_time_keyboard=True)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    existing = db.get_user(user_id)

    if existing:
        await update.message.reply_text(
            f"С возвращением, {existing['name']}! 👋",
            reply_markup=main_menu()
        )
        return ConversationHandler.END

    await update.message.reply_text(
        "Привет! 👋\n\n"
        "Помогу следить за удалёнными вакансиями в любой сфере.\n\n"
        "Как тебя зовут?",
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
        f"Приятно познакомиться, {context.user_data['name']}! 🙌\n\nКакой у тебя опыт?",
        reply_markup=keyboard
    )
    return EXPERIENCE


async def get_experience(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["experience"] = update.message.text.strip()
    await update.message.reply_text(
        "Выбери направление:",
        reply_markup=spec_group_menu()
    )
    return SPEC_GROUP


async def get_spec_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    group = update.message.text.strip()
    if group not in SPECIALIZATION_GROUPS:
        await update.message.reply_text("Выбери из списка 👇", reply_markup=spec_group_menu())
        return SPEC_GROUP
    context.user_data["spec_group"] = group
    await update.message.reply_text(
        "Теперь точнее — какая специализация?",
        reply_markup=spec_menu(group)
    )
    return SPECIALIZATION


async def get_specialization(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["specialization"] = update.message.text.strip()
    await update.message.reply_text(
        "В каком городе ты находишься? (или напиши «Удалённо»)",
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
        f"Готово! ✅\n\n"
        f"👤 {context.user_data['name']}\n"
        f"📊 Опыт: {context.user_data['experience']}\n"
        f"🎯 Сфера: {context.user_data['specialization']}\n"
        f"📍 Город: {context.user_data['city']}\n\n"
        "Каждый день в 9:00 буду присылать свежие вакансии 📬\n"
        "Или нажми *📋 Вакансии сейчас*!",
        parse_mode="Markdown",
        reply_markup=main_menu()
    )
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Отменено.", reply_markup=main_menu())
    return ConversationHandler.END


async def send_jobs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = db.get_user(user_id)

    if not user:
        await update.message.reply_text("Сначала пройди онбординг — нажми /start")
        return

    await update.message.reply_text("🔍 Ищу свежие вакансии...")

    jobs = parser.fetch_jobs(specialization=user["specialization"])

    if not jobs:
        await update.message.reply_text("😔 Сейчас ничего не нашлось. Попробуй позже.")
        return

    text = f"📋 *Удалённые вакансии — {user['specialization']}*\n\n"
    for i, job in enumerate(jobs[:8], 1):
        text += (
            f"*{i}. {job['name']}*\n"
            f"🏢 {job['employer']}\n"
            f"💰 {job['salary']}\n"
            f"🔗 [Открыть]({job['url']})\n\n"
        )

    await update.message.reply_text(text, parse_mode="Markdown", disable_web_page_preview=True)


async def cv_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📄 Пришли резюме в формате PDF — подберу топ-5 вакансий под тебя."
    )


async def handle_cv_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = db.get_user(user_id)

    if not user:
        await update.message.reply_text("Сначала пройди онбординг — нажми /start")
        return

    await update.message.reply_text("⏳ Анализирую резюме...")

    doc = update.message.document
    file = await context.bot.get_file(doc.file_id)
    file_bytes = await file.download_as_bytearray()
    cv_text = ai.extract_text_from_pdf(bytes(file_bytes))

    jobs = parser.fetch_jobs(specialization=user["specialization"], limit=20)
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

    await update.message.reply_text(text, parse_mode="Markdown", disable_web_page_preview=True)


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
        f"Сфера: {user['specialization']}\n"
        f"Город: {user['city']}\n\n"
        "Чтобы обновить профиль — нажми /start",
        parse_mode="Markdown"
    )


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if ADMIN_ID and update.effective_user.id != int(ADMIN_ID):
        return

    s = db.get_stats()
    text = (
        f"📊 *Статистика бота*\n\n"
        f"👥 Всего пользователей: *{s['total']}*\n"
        f"🆕 За последние 7 дней: *{s['new_week']}*\n\n"
        f"*По специализациям:*\n"
    )
    for spec, count in s["by_spec"]:
        text += f"• {spec}: {count}\n"

    await update.message.reply_text(text, parse_mode="Markdown")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "ℹ️ *Что умею:*\n\n"
        "📋 *Вакансии сейчас* — свежая удалённая подборка\n"
        "📄 */cv* — анализ резюме, топ-5 вакансий под тебя\n"
        "⚙️ *Профиль* — посмотреть свои данные\n\n"
        "Вакансии обновляются ежедневно в 9:00 🕘",
        parse_mode="Markdown",
        reply_markup=main_menu()
    )


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


async def daily_broadcast(context: ContextTypes.DEFAULT_TYPE):
    users = db.get_all_users()
    logger.info(f"Daily broadcast: {len(users)} users")

    for user in users:
        try:
            jobs = parser.fetch_jobs(specialization=user["specialization"])
            if not jobs:
                continue

            text = f"☀️ *Доброе утро, {user['name']}!*\n\n"
            text += f"📋 Свежие вакансии — *{user['specialization']}*:\n\n"
            for i, job in enumerate(jobs[:5], 1):
                text += (
                    f"*{i}. {job['name']}*\n"
                    f"🏢 {job['employer']} | 💰 {job['salary']}\n"
                    f"🔗 [Открыть]({job['url']})\n\n"
                )

            await context.bot.send_message(
                chat_id=user["user_id"],
                text=text,
                parse_mode="Markdown",
                disable_web_page_preview=True
            )
        except Exception as e:
            logger.error(f"Broadcast error for {user['user_id']}: {e}")


def main():
    app = Application.builder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            NAME:           [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            EXPERIENCE:     [MessageHandler(filters.TEXT & ~filters.COMMAND, get_experience)],
            SPEC_GROUP:     [MessageHandler(filters.TEXT & ~filters.COMMAND, get_spec_group)],
            SPECIALIZATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_specialization)],
            CITY:           [MessageHandler(filters.TEXT & ~filters.COMMAND, get_city)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(conv)
    app.add_handler(CommandHandler("jobs", send_jobs))
    app.add_handler(CommandHandler("cv", cv_command))
    app.add_handler(CommandHandler("profile", profile))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.Document.PDF, handle_cv_document))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_menu))

    tz = pytz.timezone(TIMEZONE)
    app.job_queue.run_daily(
        daily_broadcast,
        time=time(hour=9, minute=0, tzinfo=tz)
    )

    logger.info("Bot started!")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
