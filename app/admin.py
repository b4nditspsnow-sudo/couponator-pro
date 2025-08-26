import os
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from dotenv import load_dotenv
from .db import db
from .referral import distribute_purchase_profit

load_dotenv()
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]
router = Router()

def is_admin(uid: int) -> bool:
    return uid in ADMIN_IDS

@router.message(Command("admin"))
async def admin_menu(m: Message):
    if not is_admin(m.from_user.id):
        return
    kb = InlineKeyboardBuilder()
    kb.button(text="📊 Статистика", callback_data="adm:stats")
    kb.button(text="🧾 Покупки (ожидают)", callback_data="adm:orders")
    kb.adjust(1)
    await m.answer("Админ-меню:", reply_markup=kb.as_markup())

@router.callback_query(F.data == "adm:stats")
async def adm_stats(c: CallbackQuery):
    if not is_admin(c.from_user.id):
        return
    async with db() as conn:
        users = (await (await conn.execute("SELECT COUNT(*) FROM users")).fetchone())[0]
        clicks = (await (await conn.execute("SELECT COUNT(*) FROM clicks")).fetchone())[0]
        orders = (await (await conn.execute("SELECT COUNT(*) FROM purchases")).fetchone())[0]
        owner = (await (await conn.execute(
            "SELECT COALESCE(SUM(amount),0) FROM transactions WHERE user_id=0"
        )).fetchone())[0]
    await c.message.edit_text(
        f"👥 Пользователи: {users}\n"
        f"🖱 Клики: {clicks}\n"
        f"🧾 Покупки: {orders}\n"
        f"💰 Доход владельца: {owner/100:.2f} ₽"
    )
    await c.answer()

@router.callback_query(F.data == "adm:orders")
async def adm_orders(c: CallbackQuery):
    if not is_admin(c.from_user.id):
        return
    async with db() as conn:
        cur = await conn.execute(
            "SELECT id,buyer_id,offer_id,price,status "
            "FROM purchases WHERE status='pending' "
            "ORDER BY id DESC LIMIT 30"
        )
        rows = await cur.fetchall()
    if not rows:
        await c.message.edit_text("Нет заявок в ожидании.")
        await c.answer()
        return
    lines = [f"#{r[0]} | user {r[1]} | {r[2]} | {r[3]} ₽ | {r[4]}" for r in rows]
    lines.append("\nПодтвердить: /confirm <id> <CODE>\nОтменить: /cancel <id>")
    await c.message.edit_text("\n".join(lines))
    await c.answer()

@router.message(Command("confirm"))
async def confirm(m: Message):
    if not is_admin(m.from_user.id):
        return
    parts = m.text.strip().split(maxsplit=2)
    if len(parts) < 3:
        await m.answer("Формат: /confirm <purchase_id> <CODE>")
        return
    pid = int(parts[1]); code = parts[2]
    async with db() as conn:
        cur = await conn.execute(
            "SELECT buyer_id, offer_id, price, status FROM purchases WHERE id=?",
            (pid,)
        )
        row = await cur.fetchone()
        if not row:
            await m.answer("Заявка не найдена.")
            return
        buyer_id, offer_id, price, status = row
        if status != "pending":
            await m.answer("Эта заявка уже обработана.")
            return
        await conn.execute(
            "UPDATE purchases SET status='delivered', code=? WHERE id=?",
            (code, pid)
        )
        await conn.commit()
    await distribute_purchase_profit(buyer_id, int(price), offer_id)
    await m.bot.send_message(
        buyer_id,
        f"🎁 Покупка #{pid} подтверждена!\nТвой код: `{code}`",
        parse_mode="Markdown"
    )
    await m.answer("Готово: код выдан, проценты начислены.")

@router.message(Command("cancel"))
async def cancel(m: Message):
    if not is_admin(m.from_user.id):
        return
    parts = m.text.strip().split()
    if len(parts) < 2:
        await m.answer("Формат: /cancel <purchase_id>")
        return
    pid = int(parts[1])
    async with db() as conn:
        await conn.execute("UPDATE purchases SET status='canceled' WHERE id=?", (pid,))
        await conn.commit()
    await m.answer("Отменено.")
