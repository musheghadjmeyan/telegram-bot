import aiosqlite
from datetime import datetime, timezone, timedelta

DB_NAME = "bot.db"

async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS subs (
            user_id INTEGER PRIMARY KEY,
            expire_at TEXT,
            type TEXT
        )
        """)
        await db.commit()

async def add_sub(user_id: int, day: int | None, sub_type: str):
    expire = None
    if day:
        expire = (datetime.now(timezone.utc) + timedelta(day=day)).isoformat()

    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
        INSERT OR REPLACE INTO subs (user_id, expire_at, type)
        VALUES (?, ?, ?)
        """, (user_id, expire, sub_type))
        await db.commit()

async def get_expired():
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute("""
        SELECT user_id FROM subs
        WHERE expire_at IS NOT NULL AND expire_at < ?
        """, (datetime.now(timezone.utc).isoformat(),))
        return await cur.fetchall()
    
async def delete_sub(user_id: int):
    # Подключаемся к нашей базе bot.db
    async with aiosqlite.connect(DB_NAME) as db:
        # Пишем команду "УДАЛИТЬ ИЗ таблицы subs ТУ СТРОКУ, ГДЕ user_id равен нашему"
        await db.execute("""
        DELETE FROM subs WHERE user_id = ?
        """, (user_id,))
        # Сохраняем изменения в файле
        await db.commit()