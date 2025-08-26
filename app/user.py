import json, os
from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from dotenv import load_dotenv
from .db import db
from .referral import ensure_user, set_referrers

load_dotenv()
OFFERS_PATH = os.getenv("OFFERS_PATH", "./data/offers.json")
router = Router()

def load_offers():
    with open(OFFERS_PATH, "r", encoding="utf-8") as f:
        j = json.load(f)
    flat = {}
    for c in j.get("categories", []):
        for o in c.get("offers", []):
            o["category"] = c["name"]
            flat[o["id"]] = o
    return j, flat

def cats_kb(cats):
    kb = InlineKeyboardBuilder()
    for c in cats:
        kb.button(text=c["name"], callback_data=f"cat:{c['name']}")
    kb.adjust(1)
    return kb.as_markup()

def offers_kb(cat, offs):
    kb = InlineKeyboardBuilder()
    for o in offs:
        kb.button(text=o["title"], callback_data=f"offer:{o['id']}")
    kb.button(text="⬅️ Назад", callback_data="back:cats")
    kb.adjust(1)
    return kb.as_markup()

@router.message(CommandStart(deep_link=True))
async def start_deeplink(m: Message):
    await ensure_user(m.from_user)
    ref = m.text.split(" ", 1)[1] if len(m.text.split(" ", 1)) > 1 else None
    if ref and ref.isdigit():
        await set_referrers(m.from_user.id, int(ref))
    await start(m)

@router.message(CommandStart())
async def start(m: Message):
    await ensure_user(m.from_user)
    data, _ = load_offers()
    await m.answer(
        "Привет! Я «Купонатор» 🎟\nВыбирай категорию купонов или нажми /earn, чтобы зарабатывать с нами.",
        reply_markup=cats_kb(data.get("categories", []))
    )

@router.message(Command("promos"))
async def promos(m: Message):
    data, _ = load_offers()
    await m.answer("Категории:", reply_markup=cats_kb(data.get("categories", [])))

@router.message(Command("earn"))
async def earn(m: Message):
    uid = m.from_user.id
    link = f"https://t.me/{(await m.bot.get_me()).username}?start={uid}"
    async with db() as conn:
        cur = await conn.execute("SELECT amount FROM balances WHERE user_id=?", (uid,))
        row = await cur.fetchone()
        bal = row[0] if row else 0
        cur = await conn.execute("SELECT COUNT(*) FROM users WHERE ref1_id=?", (uid,))
        r1 = (await cur.fetchone())[0]
        cur = await conn.execute("SELECT COUNT(*) FROM users WHERE ref2_id=?", (uid,))
        r2 = (await cur.fetchone())[0]
    text = (f"💸 *Заработать с ботом*\n\n"
            f"Твоя ссылка: `{link}`\n"
            f"Рефералы 1-го уровня: {r1}\n"
            f"Рефералы 2-го уровня: {r2}\n"
            f"Баланс: {bal/100:.2f} ₽")
    await m.answer(text, parse_mode="Markdown")

@router.callback_query(F.data == "back:cats")
async def back_cats(c: CallbackQuery):
    data, _ = load_offers()
    await c.message.edit_text("Категории:", reply_markup=cats_kb(data.get("categories", [])))
    await c.answer()

@router.callback_query(F.data.startswith("cat:"))
async def open_cat(c: CallbackQuery):
    _, cat = c.data.split(":", 1)
    data, _ = load_offers()
    offs = []
    for group in data["categories"]:
        if group["name"] == cat:
            offs = [o for o in group["offers"] if o.get("active")]
            break
    await c.message.edit_text(f"{cat} — выбери предложение:", reply_markup=offers_kb(cat, offs))
    await c.answer()

@router.callback_query(F.data.startswith("offer:"))
async def open_offer(c: CallbackQuery):
    _, oid = c.data.split(":", 1)
    data, flat = load_offers()
    o = flat.get(oid)
    if not o or not o.get("active"):
        await c.answer("Предложение недоступно", show_alert=True)
        return

    kb = InlineKeyboardBuilder()
    if o["type"] == "cpa":
        url = f'{o["base_url"]}?sub1={c.from_user.id}'
        kb.button(text="Открыть скидку 🔗", url=url)
    elif o["type"] == "coupon":
        kb.button(text=f"Купить за {o.get('price', 0)} ₽", callback_data=f"buy:{o['id']}")
    kb.button(text="⬅️ Назад", callback_data=f"cat:{o['category']}")
    kb.adjust(1)
    await c.message.edit_text(f"🎟 {o['title']}", reply_markup=kb.as_markup())
    await c.answer()

@router.callback_query(F.data.startswith("buy:"))
async def buy_coupon(c: CallbackQuery):
    _, oid = c.data.split(":", 1)
    data, flat = load_offers()
    o = flat.get(oid)
    if not o:
        await c.answer("Нет такого оффера", show_alert=True)
        return
    price = int(o.get("price", 0))
    async with db() as conn:
        await conn.execute(
            "INSERT INTO purchases(buyer_id, offer_id, price, status) VALUES (?,?,?, 'pending')",
            (c.from_user.id, oid, price)
        )
        await conn.commit()
        cur = await conn.execute("SELECT last_insert_rowid()")
        pid = (await cur.fetchone())[0]
    await c.message.edit_text(
        f"✅ Заявка #{pid} создана.\n"
        f"Сумма: {price} ₽.\n\n"
        f"Оплатить переводом (СБП/Тинькофф/Сбер). После оплаты админ подтвердит и бот выдаст код.\n"
        f"Подтверждение делает админ командой /confirm {pid} <КОД>"
    )
    await c.answer()
