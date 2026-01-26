
import telebot
from utils.helpers import get_text
from services.search_service import search_music
from services.downloader import download_video

# Global State (Ideally should be in a database or Redis)
user_search_results = {}
user_search_page = {}
user_search_type = {}
user_links = {}
user_current_titles = {}

def send_search_page(bot, chat_id, results, page):
    items_per_page = 10
    total_items = len(results)
    total_pages = (total_items + items_per_page - 1) // items_per_page
    
    # Limit check
    if page >= total_pages:
        return

    start_idx = page * items_per_page
    end_idx = min(start_idx + items_per_page, total_items)
    current_items = results[start_idx:end_idx]
    
    first_item = current_items[0] if current_items else {}
    title_full = first_item.get('title', 'Unknown Title')
    artist = "Unknown Artist"
    track_name = title_full
    
    if " - " in title_full:
        parts = title_full.split(" - ", 1)
        artist = parts[0]
        track_name = parts[1]
    
    header = f"Ijrochi: <b>{artist}</b>\nQo'shiq nomi: <b>{track_name}</b>\n\n"
    response_text = header
    
    kb = telebot.types.InlineKeyboardMarkup(row_width=5)
    
    buttons = []
    for idx, entry in enumerate(current_items):
        abs_idx = start_idx + idx
        title = entry.get('title', 'No Title')
        duration = entry.get('duration_string', '')
        if not duration and 'duration' in entry:
             m, s = divmod(entry['duration'], 60)
             duration = f"{int(m)}:{int(s):02d}"
        
        response_text += f"{abs_idx + 1}. {title} {duration}\n"
        buttons.append(telebot.types.InlineKeyboardButton(str(abs_idx + 1), callback_data=f"select_{abs_idx}"))
    
    kb.add(*buttons)
    
    nav_buttons = []
    if page > 0:
        nav_buttons.append(telebot.types.InlineKeyboardButton("⬅️", callback_data="page_prev"))
    
    nav_buttons.append(telebot.types.InlineKeyboardButton("❌", callback_data="page_close"))
    
    if page < total_pages - 1:
        nav_buttons.append(telebot.types.InlineKeyboardButton("➡️", callback_data="page_next"))
        
    kb.row(*nav_buttons)
    
    # Store current page
    user_search_page[chat_id] = page
    
    # Image handling
    thumbnail = "https://github.com/telegramdesktop/tdesktop/assets/10398327/9d5a7aee-9333-4da2-9b2c-686c1264c125" # Default placeholder
    if first_item.get('thumbnail'):
        thumbnail = first_item['thumbnail']
    
    bot.send_photo(chat_id, thumbnail, caption=response_text, reply_markup=kb)


def register_search_handlers(bot):
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith("page_"))
    def handle_pagination(call):
        chat_id = call.message.chat.id
        action = call.data.split("_")[1]
        
        if action == "close":
            bot.delete_message(chat_id, call.message.message_id)
            return

        results = user_search_results.get(chat_id)
        if not results:
            bot.answer_callback_query(call.id, get_text(chat_id, 'search_results_expired'))
            return

        current_page = user_search_page.get(chat_id, 0)
        
        if action == "prev":
            new_page = max(0, current_page - 1)
        elif action == "next":
            new_page = current_page + 1
        else:
            return

        if new_page == current_page:
            return

        # Redraw
        # Logic to edit message is slightly different than sending new, but for simplicity reusing logic or copying relevant parts
        # Since send_search_page sends a new photo, we should change it to edit media or caption.
        # But for now let's just use a simplified version for pagination editing.
        # To avoid duplicated code, we assume send_search_page is reused but we need to handle "Editing" vs "Sending". 
        # For this refactor, let's keep it simple: delete and send new or edit caption.
        # A proper refactor would pass 'edit_msg_id' to send_search_page.
        
        # We will Implement a local edit logic here for safety or import a specialized function.
        # Let's import the one from bot.py logic if possible, or rewrite.
        # I'll rewrite a simplified edit flow here.
        
        items_per_page = 10
        total_items = len(results)
        total_pages = (total_items + items_per_page - 1) // items_per_page
        
        if new_page >= total_pages: return
        
        start_idx = new_page * items_per_page
        end_idx = min(start_idx + items_per_page, total_items)
        current_items = results[start_idx:end_idx]
        
        # Text builder... (duplicated from send_search_page)
        first_item = current_items[0] if current_items else {}
        title_full = first_item.get('title', 'Unknown Title')
        track_name = title_full.split(" - ", 1)[1] if " - " in title_full else title_full
        artist = title_full.split(" - ", 1)[0] if " - " in title_full else "Unknown Artist"
        
        response_text = f"Ijrochi: <b>{artist}</b>\nQo'shiq nomi: <b>{track_name}</b>\n\n"
        
        kb = telebot.types.InlineKeyboardMarkup(row_width=5)
        buttons = []
        for idx, entry in enumerate(current_items):
            abs_idx = start_idx + idx
            t = entry.get('title', 'No Title')
            buttons.append(telebot.types.InlineKeyboardButton(str(abs_idx + 1), callback_data=f"select_{abs_idx}"))
            response_text += f"{abs_idx + 1}. {t}\n"
        kb.add(*buttons)
        
        nav_buttons = []
        if new_page > 0:
             nav_buttons.append(telebot.types.InlineKeyboardButton("⬅️", callback_data="page_prev"))
        nav_buttons.append(telebot.types.InlineKeyboardButton("❌", callback_data="page_close"))
        if new_page < total_pages - 1:
             nav_buttons.append(telebot.types.InlineKeyboardButton("➡️", callback_data="page_next"))
        kb.row(*nav_buttons)
        
        user_search_page[chat_id] = new_page
        
        # Construct Media
        thumbnail = first_item.get('thumbnail', "https://github.com/telegramdesktop/tdesktop/assets/10398327/9d5a7aee-9333-4da2-9b2c-686c1264c125")
        
        try:
            bot.edit_message_media(
                media=telebot.types.InputMediaPhoto(thumbnail, caption=response_text),
                chat_id=chat_id,
                message_id=call.message.message_id,
                reply_markup=kb
            )
        except Exception as e:
            try:
                bot.edit_message_caption(response_text, chat_id, call.message.message_id, reply_markup=kb)
            except: pass

    @bot.callback_query_handler(func=lambda call: call.data.startswith("select_"))
    def handle_search_selection(call):
        chat_id = call.message.chat.id
        try:
            selection_index = int(call.data.split("_")[1])
            results = user_search_results.get(chat_id)
            
            if not results or selection_index >= len(results):
                bot.answer_callback_query(call.id, get_text(chat_id, 'search_results_expired'))
                return

            selected_video = results[selection_index]
            video_url = selected_video.get('url') or selected_video.get('webpage_url')
            title = selected_video.get('title', 'Video')
            
            # Save state
            user_links[chat_id] = video_url
            user_current_titles[chat_id] = title
            
            # Direct Download (Skip Menu)
            bot.answer_callback_query(call.id, get_text(chat_id, 'downloading'))
            download_video(bot, chat_id, video_url, "mp3")

        except Exception as e:
            bot.send_message(chat_id, f"Xatolik: {e}")
