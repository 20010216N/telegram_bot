import requests
from bs4 import BeautifulSoup
import logging
import urllib.parse
import re

BASE_URL = "https://muzofond.fm"

def get_headers():
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Referer": "https://muzofond.fm/"
    }

def clean_text(text):
    if not text:
        return ""
    return re.sub(r'<[^>]+>', '', text).strip()

def search_songs(query, limit=20):
    """
    Search for songs on Muzofond.fm
    """
    results = []
    try:
        search_url = f"{BASE_URL}/search/{urllib.parse.quote(query)}"
        logging.info(f"Muzofond searching: {search_url}")
        
        response = requests.get(search_url, headers=get_headers(), timeout=10)
        
        if response.status_code != 200:
            logging.error(f"Muzofond search failed: {response.status_code}")
            return []

        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Selector based on inspection: li.item
        items = soup.find_all('li', class_='item')
        
        for item in items:
            try:
                # 1. Info extraction
                # Artist
                artist_tag = item.find('span', class_='artist')
                artist = artist_tag.get_text(strip=True) if artist_tag else "Unknown"
                
                # Title
                title_tag = item.find('span', class_='track')
                title = title_tag.get_text(strip=True) if title_tag else "Unknown"
                
                # Duration
                dur_tag = item.find('div', class_='duration')
                duration = dur_tag.get_text(strip=True) if dur_tag else ""
                
                # Thumbnail
                thumb = "https://muzofond.fm/img/logo.png" # Default
                data_img = item.get('data-img')
                if data_img:
                    if data_img.startswith('//'):
                        thumb = "https:" + data_img
                    elif data_img.startswith('/'):
                        thumb = BASE_URL + data_img
                    else:
                        thumb = data_img
                
                # URL (Direct from data-url in li.play)
                play_btn = item.find('li', class_='play')
                url = None
                if play_btn:
                    url = play_btn.get('data-url')
                
                # Fallback to download button if data-url missing (unlikely based on insp)
                if not url:
                    dl_btn = item.find('a', class_='dl')
                    if dl_btn:
                        href = dl_btn.get('href')
                        if href:
                             url = href if href.startswith('http') else BASE_URL + href

                if not url:
                    continue

                full_title = f"{artist} - {title}" if artist and title else title

                results.append({
                    'title': clean_text(title),
                    'artist': clean_text(artist),
                    'url': url,
                    'thumbnail': thumb,
                    'duration': duration,
                    'source': 'muzofond'
                })
                
                if len(results) >= limit:
                    break
                    
            except Exception as e:
                logging.warning(f"Error parsing muzofond item: {e}")
                continue
        
        logging.info(f"Muzofond found {len(results)} results")
                
    except Exception as e:
        logging.error(f"Error searching muzofond: {e}")
        
    return results

def get_top_songs(category="trend", limit=20):
    # Muzofond doesn't have simple category URLs like muznavo for 'world', 'uzbek' mapped simply?
    # Homepage has 'popular' tabs.
    # URLs: /popular/pop, /popular/rock, /popular/rap, /popular/dance...
    # And /collections/new (Novinki)
    # We can map:
    # 'trend' -> https://muzofond.fm/ (Homepage list) or /popular
    # 'new' -> https://muzofond.fm/collections/new
    # 'uzbek' -> https://muzofond.fm/search/uzbek (Search result is best/easiest proxy for category)
    
    url = BASE_URL
    if category == 'new':
        url = f"{BASE_URL}/collections/new"
    elif category == 'uzbek':
        return search_songs("uzbek", limit)
    elif category == 'world':
        url = f"{BASE_URL}/popular"
        
    results = []
    try:
        logging.info(f"Muzofond top: {url}")
        response = requests.get(url, headers=get_headers(), timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        items = soup.find_all('li', class_='item')
        
        for item in items:
            try:
                artist_tag = item.find('span', class_='artist')
                artist = artist_tag.get_text(strip=True) if artist_tag else "Unknown"
                title_tag = item.find('span', class_='track')
                title = title_tag.get_text(strip=True) if title_tag else "Unknown"
                
                play_btn = item.find('li', class_='play')
                url = play_btn.get('data-url') if play_btn else None
                
                if not url: continue
                
                thumb = "https://muzofond.fm/img/logo.png"
                data_img = item.get('data-img')
                if data_img:
                     thumb = BASE_URL + data_img if data_img.startswith('/') else data_img

                results.append({
                    'title': clean_text(title),
                    'artist': clean_text(artist),
                    'url': url,
                    'thumbnail': thumb,
                    'source': 'muzofond'
                })
                
                if len(results) >= limit:
                    break
            except: pass
            
    except Exception as e:
        logging.error(f"Error muzofond top: {e}")
        
    return results

if __name__ == "__main__":
    print("Testing Muzofond...")
    res = search_songs("shoxrux")
    for r in res[:5]:
        print(f"{r['artist']} - {r['title']} [{r['url']}]")
