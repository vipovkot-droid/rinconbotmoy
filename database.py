import sqlite3
from datetime import datetime
from typing import Optional, Dict, List

DB_PATH = "fragment_deals.db"

def get_conn():
    return sqlite3.connect(DB_PATH)

def init_db():
    conn = get_conn()
    cur = conn.cursor()
    
    # Таблица пользователей
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            referrer_id INTEGER,
            balance_rub REAL DEFAULT 0,
            balance_ton REAL DEFAULT 0,
            balance_usdt REAL DEFAULT 0,
            balance_btc REAL DEFAULT 0,
            balance_stars INTEGER DEFAULT 0,
            completed_deals INTEGER DEFAULT 0,
            lang TEXT DEFAULT 'ru',
            is_admin INTEGER DEFAULT 0,
            reg_date TEXT,
            ton_wallet TEXT,
            card_number TEXT,
            stars_username TEXT,
            usdt_address TEXT,
            btc_address TEXT
        )
    ''')
    
    # Миграции для старых баз (добавляем недостающие колонки)
    try:
        cur.execute("ALTER TABLE users ADD COLUMN balance_stars INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    try:
        cur.execute("ALTER TABLE users ADD COLUMN stars_username TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        cur.execute("ALTER TABLE users ADD COLUMN usdt_address TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        cur.execute("ALTER TABLE users ADD COLUMN btc_address TEXT")
    except sqlite3.OperationalError:
        pass
    
    # Таблица сделок
    cur.execute('''
        CREATE TABLE IF NOT EXISTS deals (
            deal_id TEXT PRIMARY KEY,
            seller_id INTEGER,
            buyer_id INTEGER,
            currency TEXT,
            amount REAL,
            description TEXT,
            status TEXT,
            created_at TEXT,
            completed_at TEXT,
            creator_role TEXT
        )
    ''')
    try:
        cur.execute("ALTER TABLE deals ADD COLUMN creator_role TEXT")
    except sqlite3.OperationalError:
        pass
    
    # Таблица транзакций
    cur.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount REAL,
            currency TEXT,
            type TEXT,
            deal_id TEXT,
            created_at TEXT
        )
    ''')
    
    # Таблица рефералов
    cur.execute('''
        CREATE TABLE IF NOT EXISTS referrals_earn (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            referrer_id INTEGER,
            amount_ton REAL,
            from_user_id INTEGER,
            deal_id TEXT,
            created_at TEXT
        )
    ''')
    
    # Таблица логов
    cur.execute('''
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT,
            user_id INTEGER,
            username TEXT,
            deal_id TEXT,
            amount REAL,
            currency TEXT,
            old_value TEXT,
            new_value TEXT,
            description TEXT,
            created_at TEXT
        )
    ''')
    
    # Таблица настроек
    cur.execute('''
        CREATE TABLE IF NOT EXISTS bot_settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    
    # Настройки по умолчанию
    cur.execute("INSERT OR IGNORE INTO bot_settings (key, value) VALUES (?, ?)", ("ton_wallet", "UQAqdh0AMaPeA4bEMRUz5YEiYLcN0h2gaAB3DWYC46B8mKU"))
    cur.execute("INSERT OR IGNORE INTO bot_settings (key, value) VALUES (?, ?)", ("card_number", "2204120122508217"))
    cur.execute("INSERT OR IGNORE INTO bot_settings (key, value) VALUES (?, ?)", ("usdt_wallet", "TXi8ZhogkxyxiR36JvXBSLy8r5PRRKbH1c"))
    cur.execute("INSERT OR IGNORE INTO bot_settings (key, value) VALUES (?, ?)", ("btc_wallet", "bc1qgqryxap6vwdgr0pqvv4s5uLhmn567vaq87y56"))
    
    conn.commit()
    conn.close()

def add_log(event_type: str, user_id: int = None, username: str = None,
            deal_id: str = None, amount: float = None, currency: str = None,
            old_value: str = None, new_value: str = None, description: str = None):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('''
        INSERT INTO logs (event_type, user_id, username, deal_id, amount, currency, old_value, new_value, description, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (event_type, user_id, username, deal_id, amount, currency, old_value, new_value, description, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def get_logs(limit: int = 100, event_type: str = None) -> List[Dict]:
    conn = get_conn()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    if event_type:
        cur.execute("SELECT * FROM logs WHERE event_type = ? ORDER BY id DESC LIMIT ?", (event_type, limit))
    else:
        cur.execute("SELECT * FROM logs ORDER BY id DESC LIMIT ?", (limit,))
    rows = cur.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_user(user_id: int) -> Optional[Dict]:
    conn = get_conn()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None

def get_user_by_username(username: str) -> Optional[Dict]:
    conn = get_conn()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE username = ?", (username.lstrip('@'),))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None

def create_user(user_id: int, username: str, full_name: str, referrer_id: int = None):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('''
        INSERT OR IGNORE INTO users (user_id, username, full_name, referrer_id, reg_date, lang)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (user_id, username, full_name, referrer_id, datetime.now().isoformat(), 'ru'))
    conn.commit()
    conn.close()
    add_log('user_register', user_id, username, description=f"Новый пользователь @{username}")

def update_user(user_id: int, field: str, value: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(f"UPDATE users SET {field} = ? WHERE user_id = ?", (value, user_id))
    conn.commit()
    conn.close()

def update_balance(user_id: int, amount: float, currency: str, operation: str, deal_id: str = None):
    conn = get_conn()
    cur = conn.cursor()
    if currency == 'STARS':
        field = 'balance_stars'
        delta = int(amount) if operation == 'add' else -int(amount)
    else:
        field = f"balance_{currency.lower()}"
        delta = amount if operation == 'add' else -amount
    cur.execute(f"UPDATE users SET {field} = {field} + ? WHERE user_id = ?", (delta, user_id))
    cur.execute('''
        INSERT INTO transactions (user_id, amount, currency, type, deal_id, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (user_id, amount, currency, operation, deal_id, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def create_deal(deal_id: str, seller_id: int, currency: str, amount: float, description: str, creator_role: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('''
        INSERT INTO deals (deal_id, seller_id, currency, amount, description, status, created_at, creator_role)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (deal_id, seller_id, currency, amount, description, 'waiting_buyer', datetime.now().isoformat(), creator_role))
    conn.commit()
    conn.close()
    add_log('deal_created', seller_id, deal_id=deal_id, amount=amount, currency=currency)

def get_deal(deal_id: str) -> Optional[Dict]:
    conn = get_conn()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM deals WHERE deal_id = ?", (deal_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None

def update_deal(deal_id: str, **kwargs):
    old_deal = get_deal(deal_id)
    conn = get_conn()
    cur = conn.cursor()
    for key, value in kwargs.items():
        cur.execute(f"UPDATE deals SET {key} = ? WHERE deal_id = ?", (value, deal_id))
    if 'status' in kwargs and kwargs['status'] == 'completed':
        cur.execute("UPDATE deals SET completed_at = ? WHERE deal_id = ?", (datetime.now().isoformat(), deal_id))
    conn.commit()
    conn.close()
    if 'status' in kwargs and old_deal:
        add_log('deal_status_change', old_deal.get('seller_id'), deal_id=deal_id,
                old_value=old_deal.get('status'), new_value=kwargs['status'])

def get_user_deals(user_id: int) -> List[Dict]:
    conn = get_conn()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute('SELECT * FROM deals WHERE seller_id = ? OR buyer_id = ? ORDER BY created_at DESC', (user_id, user_id))
    rows = cur.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_all_users() -> List[Dict]:
    conn = get_conn()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM users ORDER BY reg_date DESC")
    rows = cur.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_all_active_deals() -> List[Dict]:
    conn = get_conn()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM deals WHERE status NOT IN ('completed', 'cancelled')")
    rows = cur.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_setting(key: str) -> str:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT value FROM bot_settings WHERE key = ?", (key,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else ""

def is_admin(user_id: int) -> bool:
    user = get_user(user_id)
    return user and user.get('is_admin', 0) == 1

def get_all_admins() -> List[int]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM users WHERE is_admin = 1")
    rows = cur.fetchall()
    conn.close()
    return [row[0] for row in rows]

def get_stats():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM users")
    users = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM deals WHERE status = 'completed'")
    completed = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM deals")
    total = cur.fetchone()[0]
    cur.execute("SELECT SUM(amount) FROM deals WHERE status = 'completed' AND currency = 'RUB'")
    volume = cur.fetchone()[0] or 0
    conn.close()
    return users, completed, total, volume

def get_deal_stats():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT status, COUNT(*) FROM deals GROUP BY status")
    by_status = {row[0]: row[1] for row in cur.fetchall()}
    cur.execute("SELECT currency, SUM(amount) FROM deals WHERE status = 'completed' GROUP BY currency")
    by_currency = {row[0]: row[1] for row in cur.fetchall()}
    conn.close()
    return by_status, by_currency

def set_user_language(user_id: int, lang: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE users SET lang = ? WHERE user_id = ?", (lang, user_id))
    conn.commit()
    conn.close()
    add_log('user_update', user_id, description=f"Пользователь сменил язык на {lang}")

def get_user_language(user_id: int) -> str:
    user = get_user(user_id)
    if user:
        return user.get('lang', 'ru')
    return 'ru'