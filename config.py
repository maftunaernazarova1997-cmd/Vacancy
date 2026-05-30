import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
TIMEZONE = os.getenv("TIMEZONE", "Asia/Tashkent")
ADMIN_ID = os.getenv("ADMIN_ID", "")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не задан!")
