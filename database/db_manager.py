import sqlite3
import os

class DBManager:
    def __init__(self, db_path):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self._create_tables()

    def _create_tables(self):
        cur = self.conn.cursor()
        # Main users table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                droid_name TEXT,
                lang TEXT DEFAULT 'en',
                frame_color TEXT DEFAULT 'FFFFFF',
                gradient TEXT DEFAULT NULL,
                seasonal_bg TEXT DEFAULT NULL
            )
        """)
        
        # Add seasonal_bg column if it doesn't exist (for backward compatibility)
        try:
            cur.execute("ALTER TABLE users ADD COLUMN seasonal_bg TEXT DEFAULT NULL")
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        # Table for PP history (needed for ppgraph)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS pp_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                pp_value REAL,
                date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.conn.commit()

    def ensure_user(self, user_id):
        """Create user record if it doesn't exist to make settings work"""
        cur = self.conn.cursor()
        cur.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
        self.conn.commit()

    # --- ACCOUNT MANAGEMENT ---
    def set_bind(self, user_id, name):
        cur = self.conn.cursor()
        cur.execute("""
            INSERT INTO users (user_id, droid_name) 
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET droid_name = excluded.droid_name
        """, (user_id, name))
        self.conn.commit()

    def get_bind(self, user_id):
        cur = self.conn.cursor()
        cur.execute("SELECT droid_name FROM users WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        return row[0] if row else None

    # --- НАСТРОЙКИ (lang, colors, gradient, seasonal_bg) ---
    def update_setting(self, user_id, column, value):
        self.ensure_user(user_id)
        # Проверка безопасности, чтобы нельзя было обновить произвольный столбец
        allowed_columns = ['lang', 'frame_color', 'gradient', 'seasonal_bg']
        if column not in allowed_columns:
            return
            
        cur = self.conn.cursor()
        cur.execute(f"UPDATE users SET {column} = ? WHERE user_id = ?", (value, user_id))
        self.conn.commit()

    def get_user_settings(self, user_id):
        cur = self.conn.cursor()
        cur.execute("SELECT lang, frame_color, seasonal_bg FROM users WHERE user_id = ?", (user_id,))
        return cur.fetchone() or ('en', 'FFFFFF', None)

    # --- СЕЗОННЫЕ ФОНЫ ---
    def set_user_seasonal_bg(self, user_id, bg_url):
        """Установить сезонный фон для пользователя"""
        self.ensure_user(user_id)
        cur = self.conn.cursor()
        cur.execute("UPDATE users SET seasonal_bg = ? WHERE user_id = ?", (bg_url, user_id))
        self.conn.commit()

    def get_user_seasonal_bg(self, user_id):
        """Получить сезонный фон пользователя"""
        cur = self.conn.cursor()
        cur.execute("SELECT seasonal_bg FROM users WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        return row[0] if row else None

    # --- ИСТОРИЯ PP (для графиков) ---
    def add_pp_record(self, user_id, pp):
        cur = self.conn.cursor()
        cur.execute("INSERT INTO pp_history (user_id, pp_value) VALUES (?, ?)", (user_id, pp))
        self.conn.commit()

    def get_pp_history(self, user_id, limit=20):
        cur = self.conn.cursor()
        cur.execute("""
            SELECT pp_value, date FROM pp_history 
            WHERE user_id = ? ORDER BY date DESC LIMIT ?
        """, (user_id, limit))
        return cur.fetchall()