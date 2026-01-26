
import sqlite3
import datetime
import os

DB_NAME = "bot.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            chat_id INTEGER PRIMARY KEY,
            language TEXT DEFAULT 'uz',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Favorites table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS favorites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            url TEXT,
            title TEXT,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(chat_id) REFERENCES users(chat_id)
        )
    ''')

    # Stats/Logs table (Optional but requested)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            action TEXT,
            details TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.commit()
    conn.close()

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

# User Operations
def db_save_user(chat_id, language='uz'):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO users (chat_id, language, last_active) 
        VALUES (?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(chat_id) DO UPDATE SET 
        language=excluded.language, 
        last_active=CURRENT_TIMESTAMP
    ''', (chat_id, language))
    conn.commit()
    conn.close()

def db_get_user_language(chat_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT language FROM users WHERE chat_id = ?', (chat_id,))
    row = cursor.fetchone()
    conn.close()
    return row['language'] if row else 'uz'

# Favorites Operations
def db_add_favorite(chat_id, url, title):
    conn = get_db_connection()
    cursor = conn.cursor()
    # Check duplicate
    cursor.execute('SELECT id FROM favorites WHERE chat_id = ? AND url = ?', (chat_id, url))
    if cursor.fetchone():
        conn.close()
        return False
        
    cursor.execute('INSERT INTO favorites (chat_id, url, title) VALUES (?, ?, ?)', (chat_id, url, title))
    conn.commit()
    conn.close()
    return True

def db_get_favorites(chat_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM favorites WHERE chat_id = ? ORDER BY added_at DESC', (chat_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows] # Convert to dicts

# Stats Operations
def db_log_action(chat_id, action, details=""):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('INSERT INTO stats (chat_id, action, details) VALUES (?, ?, ?)', (chat_id, action, details))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"DB Log Error: {e}")

def db_get_stats():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) as total_users FROM users')
    total_users = cursor.fetchone()['total_users']
    
    cursor.execute('SELECT COUNT(*) as total_actions FROM stats')
    total_actions = cursor.fetchone()['total_actions']
    
    # Active users in last 24h
    cursor.execute("SELECT COUNT(*) as active_24h FROM users WHERE last_active >= datetime('now', '-1 day')")
    active_24h = cursor.fetchone()['active_24h']
    
    conn.close()
    return {
        'total_users': total_users,
        'total_actions': total_actions,
        'active_24h': active_24h
    }
