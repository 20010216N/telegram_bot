
import telebot
import os
import uuid
import html
import speech_recognition as sr
import yt_dlp
from pydub import AudioSegment
from urllib.parse import urlparse

from utils.helpers import get_text, check_rate_limit, save_user_favorite, clean_filename # Added save_user_favorite, clean_filename
from services.search_service import search_music
from services.downloader import download_video
from services.recognition import recognize_music
from services.audio import apply_audio_effect
# Import shared state references (in a real app, use a state manager)
from handlers.search import user_search_results, user_search_type, send_search_page, user_links, user_current_titles

# State for recognized songs buttons
user_recognized_songs = {}

from concurrent.futures import ThreadPoolExecutor

# Thread Pool
executor = ThreadPoolExecutor(max_workers=5)

def register_media_handlers(bot):
    
    @bot.message_handler(func=lambda m: m.text and not m.text.startswith('/'))
    def handle_message(msg):
        chat_id = msg.chat.id
        # Submit to thread pool
        executor.submit(handle_message_thread, bot, msg)

    def handle_message_thread(bot, msg):
        chat_id = msg.chat.id
        
        if not check_rate_limit(chat_id):
            return

        text = msg.text.strip()
        
        # 1. Check if it's a URL
        is_url = False
        try:
            result = urlparse(text)
            if result.scheme and result.netloc:
                is_url = True
        except:
            pass

        # 2. If it is a URL, process
        if is_url:
            user_links[chat_id] = text
            user_current_titles[chat_id] = "To'g'ridan-to'g'ri havola"
            
            # Determine platform (simplified logic)
            # Default to best quality download
            download_video(bot, chat_id, text, "best")
            return

        # 3. If not URL, assume music search
        bot.send_message(chat_id, get_text(chat_id, 'search_music_searching', {'query': text}))
        results = search_music(text, limit=30)
        
        if not results:
            bot.send_message(chat_id, get_text(chat_id, 'nothing_found'))
        else:
            user_search_results[chat_id] = results
            user_search_type[chat_id] = 'music'
            send_search_page(bot, chat_id, results, 0)

    @bot.message_handler(content_types=['voice'])
    def handle_voice(msg):
        chat_id = msg.chat.id
        
        if not check_rate_limit(chat_id):
            return

        try:
            ogg_filename = None
            wav_filename = None
            
            bot.send_message(chat_id, get_text(chat_id, 'voice_listening'))
            
            # 1. Download voice file
            file_info = bot.get_file(msg.voice.file_id)
            downloaded_file = bot.download_file(file_info.file_path)
            
            unique_id = str(uuid.uuid4())
            ogg_filename = f"voice_{unique_id}.ogg"
            
            with open(ogg_filename, 'wb') as new_file:
                new_file.write(downloaded_file)
                
            # 2. Try AudD Music Recognition FIRST
            music_info = recognize_music(ogg_filename)
            
            if music_info and music_info.get('status') == 'success' and music_info.get('result'):
                result = music_info['result']
                artist = result.get('artist')
                title = result.get('title')
                links = result.get('song_link')
                
                response_text = get_text(chat_id, 'music_recognized')
                response_text += get_text(chat_id, 'music_artist', {'artist': artist})
                response_text += get_text(chat_id, 'music_title', {'title': title})
                
                # ... Previous Logic ...
                # Use simplified button for now
                kb = telebot.types.InlineKeyboardMarkup()
                bot.send_message(chat_id, response_text, parse_mode="HTML", reply_markup=kb)
                
                if os.path.exists(ogg_filename):
                    os.remove(ogg_filename)
                return

            # 3. Fallback: Speech to Text
            wav_filename = f"voice_{unique_id}.wav"
            
            try:
                audio = AudioSegment.from_ogg(ogg_filename)
                audio.export(wav_filename, format="wav")
            except Exception as e:
                bot.send_message(chat_id, get_text(chat_id, 'voice_convert_error'))
                if os.path.exists(ogg_filename): os.remove(ogg_filename)
                return

            r = sr.Recognizer()
            with sr.AudioFile(wav_filename) as source:
                audio_data = r.record(source)
                try:
                    text = r.recognize_google(audio_data, language='uz-UZ')
                    safe_text = html.escape(text)
                    bot.send_message(chat_id, get_text(chat_id, 'voice_you_said', {'text': safe_text}))
                    
                    bot.send_message(chat_id, get_text(chat_id, 'search_music_searching', {'query': text}))
                    results = search_music(text, limit=30)
                    
                    if not results:
                        bot.send_message(chat_id, get_text(chat_id, 'nothing_found'))
                    else:
                        user_search_results[chat_id] = results
                        user_search_type[chat_id] = 'video'
                        send_search_page(bot, chat_id, results, 0)
                        
                except sr.UnknownValueError:
                    bot.send_message(chat_id, get_text(chat_id, 'voice_error'))
                except sr.RequestError as e:
                    bot.send_message(chat_id, get_text(chat_id, 'voice_google_error', {'error': e}))

            if os.path.exists(wav_filename):
                os.remove(wav_filename)

        except Exception as e:
            bot.send_message(chat_id, f"Xatolik: {e}")
            
        finally:
            if ogg_filename and os.path.exists(ogg_filename):
                try: os.remove(ogg_filename)
                except: pass

    @bot.message_handler(content_types=['audio', 'video', 'video_note'])
    def handle_media_recognition(msg):
        chat_id = msg.chat.id
        status_msg = bot.send_message(chat_id, get_text(chat_id, 'recognition_processing'))
        
        try:
            file_id = None
            file_size = 0
            if msg.audio:
                file_id = msg.audio.file_id
                file_size = msg.audio.file_size
            elif msg.video:
                file_id = msg.video.file_id
                file_size = msg.video.file_size
            elif msg.video_note:
                file_id = msg.video_note.file_id
                file_size = msg.video_note.file_size
                
            if not file_id: return

            music_info = None
            temp_filename = ""
            
            # Telegram Bot API limit for download is 20MB
            if file_size and file_size < 20 * 1024 * 1024:
                file_info = bot.get_file(file_id)
                downloaded_file = bot.download_file(file_info.file_path)
                
                unique_id = str(uuid.uuid4())
                ext = 'mp3' if msg.audio else 'mp4'
                temp_filename = f"media_{unique_id}.{ext}"
                
                with open(temp_filename, 'wb') as new_file:
                    new_file.write(downloaded_file)
                    
                music_info = recognize_music(temp_filename)
            
            try: bot.delete_message(chat_id, status_msg.message_id)
            except: pass
            
            if music_info and music_info.get('status') == 'success' and music_info.get('result'):
                result = music_info['result']
                artist = result.get('artist')
                title = result.get('title')
                links = result.get('song_link')
                spotify_link = result.get('spotify', {}).get('external_urls', {}).get('spotify')
                youtube_link = result.get('youtube', {}).get('link')
                
                response_text = get_text(chat_id, 'music_recognized')
                response_text += get_text(chat_id, 'music_artist', {'artist': artist})
                response_text += get_text(chat_id, 'music_title', {'title': title})
                
                # Save for download
                search_query_formatted = f"{artist} - {title}"
                
                dl_callback = ""
                if len(search_query_formatted.encode('utf-8')) < 60:
                        dl_callback = f"dl|{search_query_formatted}"
                else:
                        dl_id = str(uuid.uuid4())[:8]
                        user_recognized_songs[dl_id] = search_query_formatted
                        dl_callback = f"dl_id|{dl_id}"
                
                kb = telebot.types.InlineKeyboardMarkup()
                kb.add(telebot.types.InlineKeyboardButton(get_text(chat_id, 'btn_telegram_search'), callback_data=dl_callback))
                
                if spotify_link: kb.add(telebot.types.InlineKeyboardButton("Spotify 💚", url=spotify_link))
                if youtube_link: kb.add(telebot.types.InlineKeyboardButton("YouTube 📺", url=youtube_link))
                if links: kb.add(telebot.types.InlineKeyboardButton(get_text(chat_id, 'btn_more_links'), url=links))
                        
                bot.send_message(chat_id, response_text, parse_mode="HTML", reply_markup=kb)
            else:
                # Fallback to Filename Search
                search_query = None
                if msg.audio and msg.audio.file_name:
                    search_query = msg.audio.file_name
                elif msg.video and hasattr(msg.video, 'file_name') and msg.video.file_name:
                    search_query = msg.video.file_name
                elif msg.caption:
                    search_query = msg.caption.split('\n')[0]
                    if len(search_query) > 80: search_query = None

                if search_query:
                    search_query = clean_filename(search_query)
                    
                    bot.send_message(chat_id, get_text(chat_id, 'music_fallback_search', {'query': search_query}))
                    results = search_music(search_query, limit=30)
                    if results:
                        user_search_results[chat_id] = results
                        user_search_type[chat_id] = 'music'
                        send_search_page(bot, chat_id, results, 0)
                    else:
                        bot.send_message(chat_id, get_text(chat_id, 'music_fallback_failed'))
                else:
                        bot.send_message(chat_id, get_text(chat_id, 'music_not_found'))

        except Exception as e:
            bot.send_message(chat_id, f"Xatolik: {e}")
        finally:
            if 'temp_filename' in locals() and os.path.exists(temp_filename):
                try: os.remove(temp_filename)
                except: pass

    @bot.callback_query_handler(func=lambda call: call.data.startswith("dl|") or call.data.startswith("dl_id|"))
    def handle_dl_callback(call):
        chat_id = call.message.chat.id
        data = call.data
        query = ""
        if data.startswith("dl|"):
            query = data.split("|")[1]
        elif data.startswith("dl_id|"):
             dl_id = data.split("|")[1]
             query = user_recognized_songs.get(dl_id)
        
        if query:
             bot.answer_callback_query(call.id, get_text(chat_id, 'search_music_searching', {'query': query}))
             results = search_music(query, limit=30)
             if results:
                 user_search_results[chat_id] = results
                 user_search_type[chat_id] = 'music'
                 send_search_page(bot, chat_id, results, 0)
             else:
                 bot.send_message(chat_id, get_text(chat_id, 'nothing_found'))
        else:
             bot.answer_callback_query(call.id, "Error: expired", show_alert=True)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("effect_"))
    def handle_audio_effect_callback(call):
        chat_id = call.message.chat.id
        effect = call.data.split("_")[1]
        
        # We need the original audio link to re-download or process?
        # In original bot code, it re-downloaded via yt-dlp using stored URL.
        # Check user_links state
        url = user_links.get(chat_id)
        if not url:
            bot.answer_callback_query(call.id, get_text(chat_id, 'error_link_expired'), show_alert=True)
            return

        bot.answer_callback_query(call.id, get_text(chat_id, 'downloading'))
        status_msg = bot.send_message(chat_id, "⏳ Audio qayta ishlanyapti...")
        
        try:
             # Download Logic specific for effects (needs clear mp3)
             # Use downloader service or ad-hoc?
             # For simplicity, implementing ad-hoc or we can extend downloader
             # Let's do ad-hoc reuse of yt-dlp logic for now as it returns filename
             
            unique_id = str(uuid.uuid4())
            input_file = f"temp_{unique_id}.mp3"
            output_file = f"out_{unique_id}.mp3"

            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': f'temp_{unique_id}.%(ext)s',
                'postprocessors': [{'key': 'FFmpegExtractAudio','preferredcodec': 'mp3','preferredquality': '192'}],
                'quiet': True,
                'cookiefile': 'cookies.txt', 
            }
            
            title = "Audio"
            artist = "Bot"
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                title = info.get('title', 'Audio')
                artist = info.get('artist') or info.get('uploader') or "Bot"
            
            # Identify actual file
            if not os.path.exists(input_file):
                # Fallback check
                import glob
                f = glob.glob(f"temp_{unique_id}*")
                if f: input_file = f[0]

            processed, title_suffix = apply_audio_effect(input_file, output_file, effect)
            title += title_suffix
            
            with open(output_file, 'rb') as f:
                bot.send_audio(chat_id, f, title=title, performer=artist)
            
            bot.delete_message(chat_id, status_msg.message_id)

        except Exception as e:
            bot.send_message(chat_id, f"Xatolik: {e}")
        finally:
             # Cleanup
             for f in [input_file, output_file]:
                 if os.path.exists(f):
                     try: os.remove(f)
                     except: pass
    
    @bot.callback_query_handler(func=lambda call: call.data == "find_music")
    def handle_find_music_callback(call):
        chat_id = call.message.chat.id
        # Logic to extract audio from video/media in message
        # In original bot, this callback was on a video message.
        # We need to access the message the button is attached to.
        msg = call.message
        
        # We need to download this media. 
        # But wait, send_video sent a file_id properly?
        # call.message is the message with the video.
        handle_media_recognition(msg) # Reuse the handler!
        bot.answer_callback_query(call.id)

    @bot.callback_query_handler(func=lambda call: call.data == "mp3")
    def handle_mp3_callback(call):
        chat_id = call.message.chat.id
        # Download MP3 from the video link
        url = user_links.get(chat_id)
        if url:
             bot.answer_callback_query(call.id, get_text(chat_id, 'downloading'))
             download_video(bot, chat_id, url, "mp3")
        else:
             bot.answer_callback_query(call.id, get_text(chat_id, 'error_link_expired'), show_alert=True)
