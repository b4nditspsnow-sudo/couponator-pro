import aiosqlite, os
from contextlib import asynccontextmanager
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

DATABASE_PATH = os.getenv("DATABASE_PATH", "./data/db.sqlite")

@asynccontextmanager
async def db():
    conn = await aiosqlite.connect(DATABASE_PATH)
    await conn.execute("PRAGMA journal_mode=WAL;")
    try:
        yield conn
    finally:
        await conn.close()

async def init_db():
    sql_path = Path(__file__).parent / "models.sql"
    async with db() as conn:
        await conn.executescript(sql_path.read_text())
        await conn.commit()
