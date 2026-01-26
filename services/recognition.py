
import requests
import os
from config import Config

def recognize_music(file_path):
    if not os.path.exists(file_path):
        return None
        
    data = {
        'api_token': Config.AUDD_API_TOKEN,
        'return': 'apple_music,spotify,youtube',
    }
    files = {
        'file': open(file_path, 'rb'),
    }
    
    try:
        result = requests.post('https://api.audd.io/', data=data, files=files)
        return result.json()
    except Exception as e:
        print(f"AudD recognition error: {e}")
        return None
