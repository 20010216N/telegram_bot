
import telebot
from utils.helpers import get_text, save_user_language

def register_start_handlers(bot):
    @bot.message_handler(commands=['start'])
    def start(msg):
        chat_id = msg.chat.id
        
        # ReplyKeyboardMarkup
        markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
        # Add buttons if needed, logic seems to have been commented out or implied in original
        
        bot.send_message(chat_id, get_text(chat_id, 'start_welcome'), reply_markup=markup)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("lang_"))
    def handle_language(call):
        chat_id = call.message.chat.id
        lang_code = call.data.split("_")[1]
        save_user_language(chat_id, lang_code)
        
        # Determine language name for confirmation
        lang_name = "O'zbekcha 🇺🇿"
        if lang_code == 'ru': lang_name = "Русский 🇷🇺"
        elif lang_code == 'en': lang_name = "English 🇺🇸"
        
        bot.answer_callback_query(call.id, f"Language set to {lang_name}")
        bot.delete_message(chat_id, call.message.message_id)
        
        # Send new welcome or menu
        bot.send_message(chat_id, get_text(chat_id, 'start_welcome'))
