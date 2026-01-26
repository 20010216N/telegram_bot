
import telebot
from utils.database import db_get_stats
from config import Config
from utils.helpers import get_text

def register_admin_handlers(bot):
    
    @bot.message_handler(commands=['admin'])
    def admin_panel(msg):
        chat_id = msg.chat.id
        if chat_id not in Config.ADMIN_IDS:
            return
            
        kb = telebot.types.InlineKeyboardMarkup()
        kb.add(telebot.types.InlineKeyboardButton("📊 Statistika", callback_data="admin_stats"))
        kb.add(telebot.types.InlineKeyboardButton("📢 Xabar yuborish", callback_data="admin_broadcast"))
        
        bot.send_message(chat_id, "Admin Panel", reply_markup=kb)

    @bot.callback_query_handler(func=lambda call: call.data == "admin_stats")
    def handle_admin_stats(call):
        chat_id = call.message.chat.id
        if chat_id not in Config.ADMIN_IDS:
            return

        stats = db_get_stats()
        text = f"""
📊 <b>Bot Statistikasi</b>

👤 Jami foydalanuvchilar: {stats['total_users']}
⚡️ Jami harakatlar: {stats['total_actions']}
🕒 24 soat ichida faol: {stats['active_24h']}
        """
        bot.send_message(chat_id, text, parse_mode="HTML")
        bot.answer_callback_query(call.id)

    @bot.callback_query_handler(func=lambda call: call.data == "admin_broadcast")
    def handle_admin_broadcast(call):
        chat_id = call.message.chat.id
        if chat_id not in Config.ADMIN_IDS:
            return
            
        bot.send_message(chat_id, "Xabar yuborish funksiyasi hali ishlab chiqilmoqda (Todo).")
        bot.answer_callback_query(call.id)
