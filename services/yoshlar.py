
import requests
from bs4 import BeautifulSoup
import logging

class Yoshlar:
    BASE_URL = "https://yoshlar.com"
    SEARCH_URL = "https://yoshlar.com/search"

    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    @classmethod
    def search_music(cls, query):
        """
        Searches yoshlar.com for music.
        Returns a list of dictionaries with 'title', 'artist', 'url', 'source', 'duration'.
        """
        params = {'q': query}
        try:
            # logging.info(f"Searching Yoshlar for: {query}")
            response = requests.get(cls.SEARCH_URL, params=params, headers=cls.HEADERS, timeout=10)
            if response.status_code != 200:
                logging.error(f"Yoshlar search failed: {response.status_code}")
                return []

            soup = BeautifulSoup(response.text, 'html.parser')
            results = []

            # Find all song items (a.yosh)
            items = soup.find_all('a', class_='yosh')
            
            for item in items:
                href = item.get('href')
                if not href: continue
                
                full_url = cls.BASE_URL + href
                
                # Extract title/artist
                artist_div = item.find('div', class_='yosh-artist')
                title_text = artist_div.get_text(strip=True) if artist_div else "Unknown"
                
                # Try to separate Artist - Title
                if ' - ' in title_text:
                    parts = title_text.split(' - ', 1)
                    artist = parts[0]
                    title = parts[1]
                else:
                    artist = "Yoshlar"
                    title = title_text

                results.append({
                    'title': title,
                    'artist': artist,
                    'url': full_url,
                    'source': 'yoshlar', # Mark as yoshlar source
                    'duration': 0, # Unknown
                    'thumbnail': None # No thumb in list usually
                })
            
            return results

        except Exception as e:
            logging.error(f"Yoshlar Exception: {e}")
            return []

    @classmethod
    def get_download_url(cls, url):
        """
        Resolves the song page URL to the direct MP3 download URL.
        """
        try:
            # logging.info(f"Resolving Yoshlar URL: {url}")
            response = requests.get(url, headers=cls.HEADERS, timeout=10)
            if response.status_code != 200:
                return None
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find download button (a.fdl)
            dl_btn = soup.find('a', class_='fdl')
            if dl_btn and dl_btn.get('href'):
                 # Ensure full URL if relative
                 dl_url = dl_btn.get('href')
                 if dl_url.startswith('//'):
                     dl_url = "https:" + dl_url
                 elif dl_url.startswith('/'):
                     dl_url = cls.BASE_URL + dl_url
                     
                 return dl_url
            
            return None

        except Exception as e:
            logging.error(f"Yoshlar Resolve Error: {e}")
            return None
    @classmethod
    def get_new_songs(cls):
        """
        Scrapes 'New Songs' section from the homepage.
        """
        return cls._get_songs_from_section("НОВЫЕ ПЕСНИ")

    @classmethod
    def get_trending_songs(cls):
        """
        Scrapes 'Trending Music' section from the homepage.
        """
        return cls._get_songs_from_section("Музыка в тренде")

    @classmethod
    def _get_songs_from_section(cls, section_title):
        try:
            logging.info(f"Fetching Yoshlar homepage for section: {section_title}")
            response = requests.get(cls.BASE_URL, headers=cls.HEADERS, timeout=10)
            if response.status_code != 200:
                logging.error(f"Yoshlar home fetch failed: {response.status_code}")
                return []

            soup = BeautifulSoup(response.text, 'html.parser')
            results = []

            # Find the section
            # Structure: div.sect -> h2.sect-t (Text) -> div.sect-c -> a.yosh...
            sections = soup.find_all('div', class_='sect')
            target_section = None
            
            for sect in sections:
                title_node = sect.find('h2', class_='sect-t')
                if title_node and section_title.lower() in title_node.get_text(strip=True).lower():
                    target_section = sect
                    break
            
            if not target_section:
                logging.warning(f"Section '{section_title}' not found on Yoshlar homepage.")
                return []

            # Parse songs in this section
            items = target_section.find_all('a', class_='yosh')
            for item in items:
                href = item.get('href')
                if not href: continue
                
                full_url = cls.BASE_URL + href
                
                artist_div = item.find('div', class_='yosh-artist')
                title_div = item.find('div', class_='yosh-title') # Use dedicated title class if available
                
                artist = artist_div.get_text(strip=True) if artist_div else "Yoshlar"
                title = title_div.get_text(strip=True) if title_div else "Unknown"
                
                # Cleanup
                if artist == "Yoshlar": # Fallback logic
                     pass

                results.append({
                    'title': title,
                    'artist': artist,
                    'url': full_url,
                    'source': 'yoshlar',
                    'duration': 0,
                    'thumbnail': None
                })
                
            return results

        except Exception as e:
            logging.error(f"Yoshlar Section Error ({section_title}): {e}")
            return []
