import logging
import yt_dlp
from .yoshlar import Yoshlar

def search_music(query, limit=5):
    # Normalize query (smart quotes to straight quotes)
    query = query.replace("‘", "'").replace("’", "'").replace("`", "'")

    results = []

    # 0. Try Yoshlar.com FIRST (User Request: "take from here")
    try:
        yoshlar_results = Yoshlar.search_music(query)
        if yoshlar_results:
             # logging.info(f"Yoshlar found {len(yoshlar_results)} results")
             results.extend(yoshlar_results)
             # If we have enough results, we can just return, or mix them. 
             # Let's return immediate if good match, but limited to 'limit'
             if len(results) >= limit:
                 return results[:limit]
    except Exception as e:
        logging.error(f"Yoshlar search integration error: {e}")

    # 1. Try SoundCloud first (WITHOUT Cookies usually works better for public search)
    ydl_opts_sc = {
        'format': 'bestaudio/best',
        'quiet': True,
        'noplaylist': True,
        'extract_flat': True,
        # 'cookiefile': 'cookies.txt',  # SoundCloud usually works better without generic cookies
    }

    # results = [] # Removed to preserve Yoshlar results
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts_sc) as ydl:
            # scsearch
            info = ydl.extract_info(f"scsearch{limit}:{query}", download=False)
            results = info.get('entries', [])
    except Exception as e:
        logging.error(f"SoundCloud search error: {e}")
        # print(f"SoundCloud search error: {e}") # Debug

    
    if results:
        return results
        
    # 2. If no results, fallback to YouTube (WITH Cookies if needed)
    print("SoundCloud returned 0 results, falling back to YouTube...")
    
    ydl_opts_yt = {
        'format': 'bestaudio/best',
        'quiet': True,
        'noplaylist': True,
        'extract_flat': True,
        'cookiefile': 'cookies.txt',  # Use cookies for YouTube
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts_yt) as ydl:
            # ytsearch
            info = ydl.extract_info(f"ytsearch{limit}:{query}", download=False)
            results = info.get('entries', [])
    except Exception as e:
        logging.error(f"YouTube search error: {e}")
        print(f"YouTube search error: {e}")
        
    # 3. Last Result: YouTube WITHOUT Cookies (if cookies matched nothing or failed)
    if not results:
        print("YouTube (with cookies) returned 0 results, trying without cookies...")
        ydl_opts_no_cookie = {
            'format': 'bestaudio/best',
            'quiet': True,
            'ignoreerrors': True,
            'no_warnings': True,
        }
        try:
             with yt_dlp.YoutubeDL(ydl_opts_no_cookie) as ydl:
                info = ydl.extract_info(f"ytsearch{limit}:{query}", download=False)
                results = info.get('entries', [])
        except Exception as e:
             logging.error(f"YouTube (no cookie) search error: {e}")

    return results
