
import os
import time
import uuid
import telebot
import logging
import yt_dlp
from utils.messages import get_text
from config import Config
from tenacity import retry, stop_after_attempt, wait_exponential
import re # Added import

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
def download_video(bot, chat_id, url, quality):
    status_msg = bot.send_message(chat_id, get_text(chat_id, 'downloading'))
    last_update_time = 0
    
    # Progress hook function
    def progress_hook(d):
        nonlocal last_update_time
        
        # Log progress to file
        # Log progress to file (Removed)
        # try:
        #      with open("debug_log.txt", "a") as log:
        #          log.write(f"DEBUG: Hook status: {d.get('status')} - Filename: {d.get('filename')}\n")
        # except:
        #      pass

        if d['status'] == 'downloading':
            current_time = time.time()
            # Update every 2 seconds
            if current_time - last_update_time > 2:
                percent = "..."
                if d.get('total_bytes') and d.get('downloaded_bytes'):
                    p = d['downloaded_bytes'] / d['total_bytes'] * 100
                    percent = f"{p:.1f}%"
                elif d.get('total_bytes_estimate') and d.get('downloaded_bytes'):
                    p = d['downloaded_bytes'] / d['total_bytes_estimate'] * 100
                    percent = f"{p:.1f}%"
                elif d.get('_percent_str'):
                     ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
                     percent = ansi_escape.sub('', d['_percent_str'])
                
                try:
                    bot.edit_message_text(get_text(chat_id, 'downloading_percent', {'percent': percent}), chat_id, status_msg.message_id)
                    last_update_time = current_time
                except Exception as e:
                    pass
        elif d['status'] == 'finished':
            try:
                bot.edit_message_text(get_text(chat_id, 'finished_uploading'), chat_id, status_msg.message_id)
            except:
                pass

    # Generate unique ID for this download
    unique_id = str(uuid.uuid4())
    temp_filename_base = f"download_{unique_id}"
    
    try:
        common_opts = {
            'quiet': True,
            'progress_hooks': [progress_hook],
            'cookiefile': 'cookies.txt',
            'no_warnings': True,
            'socket_timeout': Config.DOWNLOAD_TIMEOUT,
            'retries': 10,
            'fragment_retries': 10,
            'file_access_retries': 5,
            'restrictfilenames': True,
            'windowsfilenames': True,
            'force_ipv4': True,
        }

        if quality == "mp3":
            # Audio Download Logic
            ydl_opts = {
                **common_opts,
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
                'outtmpl': f'{temp_filename_base}.%(ext)s',
                'writethumbnail': True,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                final_filename = f"{temp_filename_base}.mp3"
                
                # Metadata extraction
                duration = info.get('duration')
                title = info.get('title', 'Audio')
                artist = info.get('artist') or info.get('uploader') or "Universal Bot"
                
                # Find thumbnail
                thumb_path = None
                possible_exts = ['jpg', 'jpeg', 'png', 'webp']
                for e in possible_exts:
                    if os.path.exists(f"{temp_filename_base}.{e}"):
                        thumb_path = f"{temp_filename_base}.{e}"
                        break
                
                if os.path.exists(final_filename):
                    # Check size
                    file_size = os.path.getsize(final_filename)
                    if file_size > 50 * 1024 * 1024:
                        size_mb = round(file_size / (1024 * 1024), 2)
                        bot.send_message(chat_id, get_text(chat_id, 'file_too_large', {'size': size_mb}))
                        bot.delete_message(chat_id, status_msg.message_id)
                        return

                    with open(final_filename, 'rb') as audio_file:
                        caption_text = get_text(chat_id, 'audio_caption', {'artist': artist, 'title': title})
                        
                        kb = telebot.types.InlineKeyboardMarkup()
                        kb.row(
                            telebot.types.InlineKeyboardButton(get_text(chat_id, 'btn_8d'), callback_data="effect_8d"),
                            telebot.types.InlineKeyboardButton(get_text(chat_id, 'btn_concert'), callback_data="effect_concert")
                        )
                        kb.row(
                            telebot.types.InlineKeyboardButton(get_text(chat_id, 'btn_slowed'), callback_data="effect_slowed"),
                            telebot.types.InlineKeyboardButton(get_text(chat_id, 'btn_bass'), callback_data="effect_bass")
                        )
                        kb.row(telebot.types.InlineKeyboardButton(get_text(chat_id, 'btn_add_group'), url=f"https://t.me/{bot.get_me().username}?startgroup=true"))

                        if thumb_path:
                            with open(thumb_path, 'rb') as thumb_file:
                                bot.send_audio(
                                    chat_id, 
                                    audio_file, 
                                    caption=caption_text,
                                    parse_mode="HTML",
                                    duration=duration,
                                    performer=artist,
                                    title=title,
                                    thumbnail=thumb_file,
                                    reply_markup=kb
                                )
                        else:
                            bot.send_audio(
                                chat_id, 
                                audio_file, 
                                caption=caption_text,
                                parse_mode="HTML",
                                duration=duration,
                                performer=artist,
                                title=title,
                                reply_markup=kb
                            )
                            
                    bot.delete_message(chat_id, status_msg.message_id)
                else:
                    bot.edit_message_text(get_text(chat_id, 'download_error'), chat_id, status_msg.message_id)
        
        else:
            # Universal Media Download (Video/Image)

            if quality == "best":
                # Prioritize H.264 (avc) for Telegram compatibility
                format_str = 'bestvideo[vcodec^=avc]+bestaudio[ext=m4a]/best[ext=mp4]/best'
            else:
                # Prioritize H.264 (avc) for specific quality
                format_str = f'bv*[height<={quality}][vcodec^=avc]+ba[ext=m4a]/b[ext=mp4]/b'

            ydl_opts = {
                **common_opts,
                'format': format_str,
                'outtmpl': f'{temp_filename_base}.%(ext)s',
                'writethumbnail': True, 
                'noplaylist': False,
                'merge_output_format': 'mp4',
                'postprocessors': [{
                    'key': 'FFmpegThumbnailsConvertor',
                    'format': 'jpg',
                }],
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                
                title = info.get('title', 'Media')
                width = info.get('width')
                height = info.get('height')
                duration = info.get('duration')
                
                # Scan for downloaded files
                downloaded_files = []
                video_files = []
                image_files = []
                
                # Get all files starting with base
                for f in os.listdir('.'):
                    if f.startswith(temp_filename_base):
                        ext = f.split('.')[-1].lower()
                        if ext in ['mp4', 'mkv', 'mov', 'webm', 'avi']:
                            video_files.append(f)
                        elif ext in ['jpg', 'jpeg', 'png', 'webp']:
                            image_files.append(f)
                        downloaded_files.append(f)

                # Identify content type
                if not video_files and not image_files:
                     bot.edit_message_text(get_text(chat_id, 'download_error'), chat_id, status_msg.message_id)
                     return

                # Common Keyboard
                kb = telebot.types.InlineKeyboardMarkup()
                kb.row(telebot.types.InlineKeyboardButton(get_text(chat_id, 'btn_find_music'), callback_data="find_music"))
                kb.row(telebot.types.InlineKeyboardButton("MP3 🎧", callback_data="mp3"))
                kb.row(telebot.types.InlineKeyboardButton(get_text(chat_id, 'btn_add_group'), url=f"https://t.me/{bot.get_me().username}?startgroup=true"))

                caption = get_text(chat_id, 'video_caption', {'title': title})

                # LOGIC:
                # 1. Multiple Media (Carousel/Album)
                if (len(video_files) + len(image_files)) > 1:
                    media_group = []
                    
                    # Sort files
                    all_media = sorted(video_files + image_files)
                    all_media = all_media[:10]

                    for idx, filename in enumerate(all_media):
                         ext = filename.split('.')[-1].lower()
                         try:
                             if ext in ['mp4', 'mkv', 'mov', 'webm']:
                                 media_group.append(telebot.types.InputMediaVideo(open(filename, 'rb'), caption="", parse_mode="HTML"))
                             elif ext in ['jpg', 'jpeg', 'png', 'webp']:
                                 media_group.append(telebot.types.InputMediaPhoto(open(filename, 'rb'), caption="", parse_mode="HTML"))
                         except Exception as e:
                             print(f"Error adding media to group: {e}")

                    if media_group:
                        try:
                            bot.send_media_group(chat_id, media_group)
                            bot.send_message(chat_id, caption, reply_markup=kb, parse_mode="HTML")
                        except Exception as e:
                             bot.send_message(chat_id, get_text(chat_id, 'error_general', {'error': str(e)}))

                # 2. Single Video
                elif video_files:
                    final_filename = video_files[0]
                    
                    # Check size
                    file_size = os.path.getsize(final_filename)
                    if file_size > 50 * 1024 * 1024:
                        size_mb = round(file_size / (1024 * 1024), 2)
                        bot.send_message(chat_id, get_text(chat_id, 'file_too_large', {'size': size_mb}))
                        bot.delete_message(chat_id, status_msg.message_id)
                        return

                    # Thumb check (distinct from the video itself)
                    thumb_path = None
                    if image_files:
                        thumb_path = image_files[0] 

                    try:
                        with open(final_filename, 'rb') as video_file:
                            if thumb_path:
                                with open(thumb_path, 'rb') as thumb_file:
                                    bot.send_video(
                                        chat_id, 
                                        video_file, 
                                        caption=caption,
                                        parse_mode="HTML",
                                        width=width, 
                                        height=height, 
                                        duration=duration, 
                                        thumbnail=thumb_file,
                                        supports_streaming=True,
                                        reply_markup=kb,
                                        timeout=120
                                    )
                            else:
                                bot.send_video(
                                    chat_id, 
                                    video_file, 
                                    caption=caption,
                                    parse_mode="HTML",
                                    width=width, 
                                    height=height, 
                                    duration=duration, 
                                    supports_streaming=True,
                                    reply_markup=kb,
                                    timeout=120
                                )
                    except Exception as e:
                        # Fallback: Try sending without thumbnail if that was the issue
                        if thumb_path:
                            try:
                                with open(final_filename, 'rb') as video_file_retry:
                                    bot.send_video(
                                        chat_id,
                                        video_file_retry,
                                        caption=caption,
                                        parse_mode="HTML",
                                        width=width, 
                                        height=height, 
                                        duration=duration, 
                                        supports_streaming=True,
                                        reply_markup=kb,
                                        timeout=120
                                    )
                            except Exception as final_e:
                                raise final_e # Raise original error if fallback fails
                        else:
                            raise e
                
                # 3. Single Image
                elif image_files:
                    final_filename = image_files[0]
                    with open(final_filename, 'rb') as photo_file:
                        bot.send_photo(
                            chat_id,
                            photo_file,
                            caption=caption,
                            parse_mode="HTML",
                            reply_markup=kb
                        )
                    
            bot.delete_message(chat_id, status_msg.message_id)

    except Exception as e:
        import traceback
        logging.error(f"Download Error: {str(e)}\n{traceback.format_exc()}")
        bot.send_message(chat_id, get_text(chat_id, 'error_general', {'error': str(e)}))
        # Cleanup if error
        try:
             import glob
             for f in glob.glob(f"*{unique_id}*"):
                 # Force remove
                 try:
                     os.remove(f)
                 except:
                     pass
        except:
             pass

    finally:
        # Cleanup
         try:
             import glob
             for f in glob.glob(f"*{unique_id}*"):
                 try:
                     os.remove(f)
                 except:
                     pass
         except:
             pass
