import os

import psycopg2


def resolve_database_url() -> str:
    url = os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_URL") or os.environ.get("DB_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set. Example: postgresql://postgres:password@localhost:5432/vlg_bot"
        )
    return url


def init_db() -> str:
    dsn = resolve_database_url()
    conn = psycopg2.connect(dsn)
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    guild_id BIGINT NOT NULL,
                    user_id BIGINT NOT NULL,
                    coins INTEGER NOT NULL DEFAULT 0,
                    bank INTEGER NOT NULL DEFAULT 0,
                    xp INTEGER NOT NULL DEFAULT 0,
                    last_daily DOUBLE PRECISION NOT NULL DEFAULT 0,
                    daily_streak INTEGER NOT NULL DEFAULT 0,
                    last_work DOUBLE PRECISION NOT NULL DEFAULT 0,
                    last_msg DOUBLE PRECISION NOT NULL DEFAULT 0,
                    boost_until DOUBLE PRECISION NOT NULL DEFAULT 0,
                    PRIMARY KEY (guild_id, user_id)
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS inventory (
                    guild_id BIGINT NOT NULL,
                    user_id BIGINT NOT NULL,
                    item TEXT NOT NULL,
                    qty INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (guild_id, user_id, item)
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS level_roles (
                    guild_id BIGINT NOT NULL,
                    level INTEGER NOT NULL,
                    role_id BIGINT NOT NULL,
                    PRIMARY KEY (guild_id, level)
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS message_counts (
                    guild_id BIGINT NOT NULL,
                    user_id BIGINT NOT NULL,
                    total INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (guild_id, user_id)
                );
            """)
        conn.commit()
    finally:
        conn.close()
    return dsn


if __name__ == "__main__":
    dsn = init_db()
    print(f"PostgreSQL database initialized using DATABASE_URL: {dsn}")
