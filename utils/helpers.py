import time
import os
import shutil
import logging
from urllib.parse import urlparse
from collections import UserDict

class TimedCache(UserDict):
    """
    A dictionary-like object that automatically expires entries after a given TTL (time-to-live).
    """
    def __init__(self, ttl_seconds=3600):
        super().__init__()
        self.ttl_seconds = ttl_seconds
        self._timestamps = {}

    def __setitem__(self, key, value):
        self._cleanup()
        super().__setitem__(key, value)
        self._timestamps[key] = time.time()

    def __getitem__(self, key):
        self._cleanup()
        if key not in self.data:
            raise KeyError(key)
        # Optional: Reset TTL on access? For now, let's keep it simple (absolute expiry)
        return super().__getitem__(key)

    def _cleanup(self):
        """Remove expired entries."""
        now = time.time()
        keys_to_remove = [k for k, ts in self._timestamps.items() if now - ts > self.ttl_seconds]
        for k in keys_to_remove:
            if k in self.data:
                del self.data[k]
            if k in self._timestamps:
                del self._timestamps[k]

class TempFileManager:
    """
    Context manager to ensure temporary files are deleted.
    Usage:
        with TempFileManager('file1.mp3', 'file2.mp4') as files:
            # do stuff
    """
    def __init__(self, *file_paths, cleanup_pattern=None):
        self.file_paths = list(file_paths)
        self.cleanup_pattern = cleanup_pattern

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()

    def cleanup(self):
        # Register pattern matches if any
        if self.cleanup_pattern:
            import glob
            try:
                for f in glob.glob(self.cleanup_pattern):
                    self.add_file(f)
            except Exception as e:
                logging.error(f"Error scanning pattern {self.cleanup_pattern}: {e}")

        for path in self.file_paths:
            if not path: continue
            try:
                if os.path.exists(path):
                    self._remove_with_retry(path)
            except Exception as e:
                logging.error(f"Error cleaning up {path}: {e}")

    def _remove_with_retry(self, path, retries=5, delay=1.0):
        """Try to remove a file with retries to handle Windows file locks."""
        import gc
        for i in range(retries):
            try:
                if os.path.isdir(path):
                    shutil.rmtree(path, ignore_errors=True)
                else:
                    os.remove(path)
                return True
            except PermissionError:
                if i < retries - 1:
                    # Force garbage collection to release file handles
                    gc.collect()
                    time.sleep(delay)
                else:
                    raise

    def add_file(self, path):
        """Add a file to be cleaned up later."""
        if path not in self.file_paths:
            self.file_paths += (path,)

def check_disk_space(min_mb=100):
    """Diskda yetarli joy borligini tekshirish"""
    stat = shutil.disk_usage('.')
    free_mb = stat.free / (1024 * 1024)
    return free_mb > min_mb

def validate_url(url):
    """URL manzilini tekshirish"""
    import re
    pattern = re.compile(
        r'^(?:http|ftp)s?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    return re.match(pattern, url) is not None

def clean_filename(filename):
    """
    Filenamedan ortiqcha belgi va so'zlarni olib tashlash
    """
    import re
    # 1. Remove Extension
    name, _ = os.path.splitext(filename)
    
    # 2. General Cleanup (allow alphanumeric, spaces, hyphens)
    # Replace underscores with spaces
    name = name.replace('_', ' ')
    
    # 3. Known Promo Prefixes/Suffixes to Remove
    noise_patterns = [
        r'RizaNova(\w+)?', # RizaNova, RizaNovaUZ etc
        r'RizaNovaUZ',
        # r'Sardor Rasulov', # Removed: This is an artist name
        r'www\.\S+',
        r'\.com',
        r'@\w+', # usernames
        r'#\w+', # hashtags
        r'\(.*?\)', # anything in brackets
        r'\[.*?\]', # anything in square brackets
        r'\d{2}:\d{2}', # timestamps like 04:03
    ]
    
    for pattern in noise_patterns:
        name = re.sub(pattern, '', name, flags=re.IGNORECASE)
        
    # 4. Remove extra separators
    name = re.sub(r'\s+-\s+', ' ', name)
    name = re.sub(r'\s+', ' ', name).strip()
    
    return name

def sanitize_filename(filename):
    """
    Remove invalid characters from filename for Windows/Linux.
    """
    import re
    # Remove invalid characters: < > : " / \ | ? *
    return re.sub(r'[<>:"/\\|?*]', '', filename)



def compress_video(input_path, output_path, target_size_mb, ffmpeg_path='ffmpeg'):
    """
    Compress video to target size in MB.
    Returns True if successful, False otherwise.
    """
    import subprocess
    import math
    import json
    
    try:
        # Get video duration
        cmd_probe = [
            'ffprobe', 
            '-v', 'quiet', 
            '-print_format', 'json', 
            '-show_format', 
            '-show_streams', 
            input_path
        ]
        
        result = subprocess.run(cmd_probe, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        data = json.loads(result.stdout)
        
        duration = float(data['format']['duration'])
        
        # Calculate target bitrate
        # buffer for audio (assume 128k audio) and container overhead
        # Target total bitrate = (Target Size MB * 8192) / Duration
        # Video bitrate = Total - Audio
        
        target_total_bitrate = (target_size_mb * 8192) / duration
        audio_bitrate = 128 # kbps
        video_bitrate = target_total_bitrate - audio_bitrate
        
        if video_bitrate < 1:
             video_bitrate = 1 # Edge case
             
        logging.info(f"Compressing {input_path} to {target_size_mb}MB. Duration: {duration}s. Target VBitrate: {video_bitrate}k")
        
        # Two-pass encoding is best for targeting size, but single pass with CRF + maxrate is faster/easier for bot
        # We will use simple CRF with maxrate limiting to approximate
        
        cmd = [
            ffmpeg_path,
            '-y',
            '-i', input_path,
            '-c:v', 'libx264',
            '-b:v', f'{int(video_bitrate)}k',
            '-maxrate', f'{int(video_bitrate * 1.5)}k', # Allow some variability
            '-bufsize', f'{int(video_bitrate * 2)}k',
            '-preset', 'fast',
            '-c:a', 'aac',
            '-b:a', '128k',
            '-movflags', '+faststart',
            output_path
        ]
        
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            return True
        return False
        
    except Exception as e:
        logging.error(f"Compression error: {e}")
        return False

def compress_audio(input_path, output_path, target_size_mb, ffmpeg_path='ffmpeg'):
    """
    Compress audio to target size in MB.
    Returns True if successful, False otherwise.
    """
    import subprocess
    import json
    import logging
    
    try:
        # Get duration
        cmd_probe = [
            'ffprobe', '-v', 'quiet', '-print_format', 'json', 
            '-show_format', '-show_streams', input_path
        ]
        
        result = subprocess.run(cmd_probe, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        data = json.loads(result.stdout)
        duration = float(data['format']['duration'])
        
        # Target bitrate = (Target Size * 8192) / Duration
        # 1 MB = 8192 kbits (approx, actually 1024*8 kb) -> 1 byte = 8 bits. 
        # Size (MB) * 1024 * 1024 * 8 = Bits.
        # Duration (s).
        # Bitrate (bps) = Bits / Duration.
        # Bitrate (kbps) = (Size * 8192) / Duration.
        
        target_bitrate = (target_size_mb * 8192) / duration
        
        # Clamp bitrate
        if target_bitrate < 32:
            target_bitrate = 32 # Minimum hearable
        if target_bitrate > 320:
            target_bitrate = 320 # Max mp3
            
        logging.info(f"Compressing audio {input_path} to {target_size_mb}MB. Target Bitrate: {target_bitrate}k")
        
        cmd = [
            ffmpeg_path, '-y', '-i', input_path,
            '-c:a', 'libmp3lame',
            '-b:a', f'{int(target_bitrate)}k',
            output_path
        ]
        
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            return True
        return False
        
    except Exception as e:
        logging.error(f"Audio compression error: {e}")
        return False
