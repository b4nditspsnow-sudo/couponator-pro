import os, json
from dotenv import load_dotenv
from .db import db
load_dotenv()

REF1_PERCENT = float(os.getenv("REF1_PERCENT", "0.20"))
REF2_PERCENT = float(os.getenv("REF2_PERCENT", "0.05"))

async def ensure_user(user):
    async with db() as conn:
        await conn.execute("""
            INSERT OR IGNORE INTO users (user_id, username, first_name, last_name)
            VALUES (?,?,?,?)
        """, (user.id, user.username, user.first_name, user.last_name))
        await conn.execute("INSERT OR IGNORE INTO balances (user_id, amount) VALUES (?, 0)", (user.id,))
        await conn.commit()

async def set_referrers(user_id: int, ref1_id: int | None):
    if not ref1_id or ref1_id == user_id:
        return
    async with db() as conn:
        cur = await conn.execute("SELECT ref1_id FROM users WHERE user_id=?", (ref1_id,))
        row = await cur.fetchone()
        ref2 = row[0] if row else None
        await conn.execute(
            "UPDATE users SET ref1_id=?, ref2_id=? WHERE user_id=? AND ref1_id IS NULL",
            (ref1_id, ref2, user_id)
        )
        await conn.commit()

async def add_transaction(user_id: int, kind: str, amount_kop: int, meta: dict | None = None):
    async with db() as conn:
        await conn.execute(
            "INSERT INTO transactions(user_id, kind, amount, meta) VALUES (?,?,?,?)",
            (user_id, kind, amount_kop, json.dumps(meta or {}, ensure_ascii=False))
        )
        await conn.execute(
            "UPDATE balances SET amount = amount + ? WHERE user_id=?",
            (amount_kop, user_id)
        )
        await conn.commit()

async def distribute_purchase_profit(buyer_id: int, price_rub: int, offer_id: str):
    price_kop = price_rub * 100
    ref1_amt = int(price_kop * REF1_PERCENT)
    ref2_amt = int(price_kop * REF2_PERCENT)
    owner_amt = price_kop - ref1_amt - ref2_amt

    async with db() as conn:
        cur = await conn.execute("SELECT ref1_id, ref2_id FROM users WHERE user_id=?", (buyer_id,))
        row = await cur.fetchone()
        ref1_id, ref2_id = (row[0], row[1]) if row else (None, None)

    if ref1_id:
        await add_transaction(ref1_id, "reward_ref1", ref1_amt, {"from": buyer_id, "offer": offer_id})
    if ref2_id:
        await add_transaction(ref2_id, "reward_ref2", ref2_amt, {"from": buyer_id, "offer": offer_id})
    await add_transaction(0, "owner_income", owner_amt, {"from": buyer_id, "offer": offer_id})
