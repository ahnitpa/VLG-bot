import os
import sqlite3


def resolve_db_path() -> str:
    env_db = os.environ.get("DB_PATH") or os.environ.get("BOT_DB_PATH")
    db_path = env_db.strip() if env_db else os.path.join(os.getcwd(), "bot.db")
    directory = os.path.dirname(db_path)
    if directory and not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)
    return db_path


if __name__ == "__main__":
    db_path = resolve_db_path()
    conn = sqlite3.connect(db_path)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS users (
        guild_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        coins INTEGER NOT NULL DEFAULT 0,
        bank INTEGER NOT NULL DEFAULT 0,
        xp INTEGER NOT NULL DEFAULT 0,
        last_daily REAL NOT NULL DEFAULT 0,
        daily_streak INTEGER NOT NULL DEFAULT 0,
        last_work REAL NOT NULL DEFAULT 0,
        last_msg REAL NOT NULL DEFAULT 0,
        boost_until REAL NOT NULL DEFAULT 0,
        PRIMARY KEY (guild_id, user_id)
    );
    """)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS inventory (
        guild_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        item TEXT NOT NULL,
        qty INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY (guild_id, user_id, item)
    );
    """)
    conn.commit()
    conn.close()
    print(f"SQLite database initialized at: {db_path}")
