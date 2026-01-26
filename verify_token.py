import os
from dotenv import load_dotenv
import telebot

# Load .env explicitly
load_dotenv()

token = os.getenv("TELEGRAM_BOT_TOKEN")

print(f"Loaded Token from .env: '{token}'")

if not token:
    print("ERROR: Token is empty! Check your .env file.")
    exit()

try:
    bot = telebot.TeleBot(token)
    user = bot.get_me()
    print(f"SUCCESS! Token is valid.")
    print(f"Bot Username: @{user.username}")
    print(f"Bot Name: {user.first_name}")
except Exception as e:
    print(f"FAILED. Telegram API Error: {e}")
