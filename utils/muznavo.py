import requests
from bs4 import BeautifulSoup
import urllib.parse
import re
import logging

BASE_URL = "https://muznavo.tv"

def get_headers():
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3",
        "Referer": "https://muznavo.tv/"
    }

def clean_text(text):
    if not text:
        return ""
    # Remove HTML tags (like <b> for search highlighting)
    text = re.sub(r'<[^>]+>', '', text)
    return text.strip()

def search_songs(query, limit=20):
    """
    Search for songs on Muznavo.tv
    Returns a list of dicts: {'title': str, 'artist': str, 'url': str, 'duration': str, 'thumbnail': str}
    """
    results = []
    try:
        search_url = f"{BASE_URL}/search"
        params = {'q': query}
        
        logging.info(f"Muznavo searching: {query}")
        response = requests.get(search_url, params=params, headers=get_headers(), timeout=10)
        
        if response.status_code != 200:
            logging.error(f"Muznavo search failed: {response.status_code}")
            return []

        soup = BeautifulSoup(response.text, 'html.parser')
        
        # New Selector Logic: Look for .track-item
        track_items = soup.find_all('div', class_='track-item')
        
        if not track_items:
             logging.info("No .track-item found, trying alternative selectors...")
             pass

        for item in track_items:
            try:
                # 1. Title & Artist
                title = item.get('data-title')
                artist = item.get('data-artist')
                
                # Fallback to scraping text components if data attributes missing
                if not title:
                     title_div = item.find('div', class_='td02') or item.find('div', class_='top-item-subtitle')
                     title = title_div.get_text(strip=True) if title_div else "Unknown"

                if not artist:
                     artist_div = item.find('div', class_='td01') or item.find('div', class_='top-item-title')
                     artist = artist_div.get_text(strip=True) if artist_div else "Unknown"
                
                # 2. URL
                link_tag = item.find('a', class_='track-desc') or item.find('a', href=True)
                if not link_tag:
                    continue
                
                href = link_tag['href']
                full_url = href if href.startswith('http') else BASE_URL + href
                
                if 'javascript' in full_url or '#' in full_url:
                    continue

                # 3. Thumbnail
                thumb = "https://muznavo.tv/images/muznavo200.png"
                
                data_img = item.get('data-img')
                if data_img:
                     thumb = data_img if data_img.startswith('http') else BASE_URL + data_img
                else:
                    img_tag = item.find('img')
                    if img_tag:
                        src = img_tag.get('src') or img_tag.get('data-src')
                        if src:
                            thumb = src if src.startswith('http') else BASE_URL + src

                # 4. Check for direct download link (optimization)
                data_track = item.get('data-track')
                if data_track and data_track.endswith('.mp3'):
                     full_url = data_track if data_track.startswith('http') else BASE_URL + data_track

                results.append({
                    'title': clean_text(title),
                    'artist': clean_text(artist),
                    'url': full_url,
                    'thumbnail': thumb,
                    'duration': '',
                    'source': 'muznavo'
                })
                
                if len(results) >= limit:
                    break
                    
            except Exception as e:
                logging.warning(f"Error parsing item: {e}")
                continue
        
        logging.info(f"Muznavo found {len(results)} results")
                
    except Exception as e:
        logging.error(f"Error searching muznavo: {e}")
        
    return results

def get_top_songs(category="trend", limit=20):
    """
    Get top songs. 
    category: 'trend', 'uzbek', 'world', 'new'
    """
    urls = {
        'trend': BASE_URL, 
        'uzbek': f"{BASE_URL}/load/uzbek_mp3", 
        'world': f"{BASE_URL}/load/xorij_mp3",
        'new': f"{BASE_URL}/load/yangi_mp3"
    }
    
    target_url = urls.get(category, urls['trend'])
    results = []
    
    try:
        logging.info(f"Fetching top songs from: {target_url}")
        response = requests.get(target_url, headers=get_headers(), timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        track_items = soup.find_all('div', class_='track-item')
        if not track_items:
             track_items = soup.find_all('div', class_='top-item')

        for item in track_items:
            try:
                title = item.get('data-title')
                artist = item.get('data-artist')
                
                if not title or not artist:
                     title_div = item.find('div', class_='top-item-subtitle') or item.find('div', class_='td02')
                     artist_div = item.find('div', class_='top-item-title') or item.find('div', class_='td01')
                     
                     title = title_div.get_text(strip=True) if title_div else "Track"
                     artist = artist_div.get_text(strip=True) if artist_div else "Artist"

                # Link
                desc_link = item.find('a', class_='track-desc') or item.find('a', class_='top-item-desc')
                link_tag = item.find('a', href=True) 
                
                if desc_link:
                    href = desc_link['href']
                elif link_tag:
                    href = link_tag['href']
                else:
                    continue 

                full_url = href if href.startswith('http') else BASE_URL + href

                # Thumbnail
                thumb = "https://muznavo.tv/images/muznavo200.png"
                data_img = item.get('data-img')
                if data_img:
                     thumb = data_img if data_img.startswith('http') else BASE_URL + data_img
                else:
                    img_tag = item.find('img')
                    if img_tag:
                        src = img_tag.get('src') or img_tag.get('data-src') or img_tag.get('data-original')
                        if src:
                            thumb = src if src.startswith('http') else BASE_URL + src

                # MP3 Optimization
                data_track = item.get('data-track')
                if data_track and data_track.endswith('.mp3'):
                     full_url = data_track if data_track.startswith('http') else BASE_URL + data_track

                if any(r['url'] == full_url for r in results):
                    continue

                results.append({
                    'title': clean_text(title),
                    'artist': clean_text(artist),
                    'url': full_url,
                    'thumbnail': thumb,
                    'duration': '',
                    'source': 'muznavo'
                })
                
                if len(results) >= limit:
                    break

            except Exception as e:
                pass
                
        logging.info(f"Muznavo Top found {len(results)} results")

    except Exception as e:
        print(f"Error fetching top songs: {e}")
        
    return results

def get_download_url(page_url, proxy=None):
    """
    Extract direct MP3 link from a song page OR return if it's already an MP3 link.
    """
    if page_url.endswith('.mp3'):
        return page_url
        
    try:
        logging.info(f"Resolving Muznavo URL: {page_url} (Proxy: {proxy})")
        
        proxies = None
        if proxy:
            proxies = {'http': proxy, 'https': proxy}
            
        response = requests.get(page_url, headers=get_headers(), proxies=proxies, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Strategy 1: Look for data-track attribute in the main player div
        # <div class="fplay-wr js-item" data-track="...">
        player_div = soup.find('div', class_='fplay-wr')
        if player_div and player_div.get('data-track'):
             track = player_div['data-track']
             return track if track.startswith('http') else BASE_URL + track

        # Strategy 2: Look for the main download button
        # <a class="fbtn fdl anim" href="..." download>
        dl_btn = soup.find('a', class_='fbtn fdl')
        if dl_btn and dl_btn.get('href'):
             href = dl_btn['href']
             if href.endswith('.mp3'):
                 return href if href.startswith('http') else BASE_URL + href
             
        # Strategy 3: Look for any valid MP3 link in specific classes
        links = soup.find_all('a', href=True)
        for link in links:
            href = link['href']
            # Strict check for MP3
            if href.endswith('.mp3'):
                final = href if href.startswith('http') else BASE_URL + href
                logging.info(f"Muznavo resolved MP3: {final}")
                return final
            
            # Legacy check (be careful not to pick up page links)
            if 'download' in href and 'id=' in href and href.endswith('.mp3'): # Added .mp3 check to be safe
                 final = href if href.startswith('http') else BASE_URL + href
                 return final
        
        logging.warning(f"No MP3 link found on {page_url}")

    except Exception as e:
        logging.error(f"Error parsing page {page_url}: {e}")
        
    return None

if __name__ == "__main__":
    # Test
    print("Testing Search...")
    res = search_songs("uzbek")
    if not res:
        print("Search returned NO results!")
    for r in res[:5]:
        print(r)
        
    print("\nTesting Top...")
    res_top = get_top_songs("trend")
    if not res_top:
        print("Top songs returned NO results!")
    for r in res_top[:5]:
        print(r)
