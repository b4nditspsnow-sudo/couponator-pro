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

# ------------------------
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ------------------------
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
    # добавляем системные кнопки
    kb.button(text="👥 Пригласить друзей", callback_data="invite")
    kb.adjust(1)
    return kb.as_markup()

def offers_kb(cat, offs):
    kb = InlineKeyboardBuilder()
    for o in offs:
        kb.button(text=o["title"], callback_data=f"offer:{o['id']}")
    kb.button(text="⬅️ Назад", callback_data="back:cats")
    kb.adjust(1)
    return kb.as_markup()

async def get_ref_link(bot, user_id: int) -> str:
    bot_username = (await bot.get_me()).username
    return f"https://t.me/{bot_username}?start={user_id}"

# -------------
# СТАРТ / МЕНЮ
# -------------
@router.message(CommandStart(deep_link=True))
async def start_deeplink(m: Message):
    await ensure_user(m.from_user)
    # deep-link рефералка
    ref = m.text.split(" ", 1)[1] if len(m.text.split(" ", 1)) > 1 else None
    if ref and ref.isdigit():
        await set_referrers(m.from_user.id, int(ref))
    await start(m)

@router.message(CommandStart())
async def start(m: Message):
    await ensure_user(m.from_user)
    data, _ = load_offers()
    await m.answer(
        "Привет! Я «Купонатор» 🎟\n"
        "Выбирай категорию купонов или жми /earn, чтобы зарабатывать вместе с нами.\n"
        "Твою реферальную ссылку можно взять в /ref или кнопкой «👥 Пригласить друзей».",
        reply_markup=cats_kb(data.get("categories", []))
    )

@router.message(Command("promos"))
async def promos(m: Message):
    data, _ = load_offers()
    await m.answer("Категории:", reply_markup=cats_kb(data.get("categories", [])))

# --------------------
# РЕФЕРАЛЬНЫЕ ХЕНДЛЕРЫ
# --------------------
@router.message(Command("ref"))
@router.message(Command("invite"))
async def ref_link(m: Message):
    await ensure_user(m.from_user)
    link = await get_ref_link(m.bot, m.from_user.id)

    # 1) Текст
    await m.answer("👥 Вот твоя персональная реферальная ссылка:")

    # 2) Ссылка отдельным сообщением — удобно копировать/переслать
    await m.answer(link)

    # 3) Кнопка «Поделиться»
    kb = InlineKeyboardBuilder()
    kb.button(text="📤 Поделиться", switch_inline_query=link)
    await m.answer("Удобно переслать 👇", reply_markup=kb.as_markup())

@router.callback_query(F.data == "invite")
async def invite_cb(c: CallbackQuery):
    # тот же сценарий, что и /ref
    link = await get_ref_link(c.bot, c.from_user.id)
    await c.message.answer("👥 Вот твоя персональная реферальная ссылка:")
    await c.message.answer(link)
    kb = InlineKeyboardBuilder()
    kb.button(text="📤 Поделиться", switch_inline_query=link)
    await c.message.answer("Удобно переслать 👇", reply_markup=kb.as_markup())
    await c.answer()

@router.message(Command("earn"))
async def earn(m: Message):
    uid = m.from_user.id
    await ensure_user(m.from_user)
    link = await get_ref_link(m.bot, uid)

    # Баланс и статистика
    async with db() as conn:
        cur = await conn.execute("SELECT amount FROM balances WHERE user_id=?", (uid,))
        row = await cur.fetchone()
        bal = row[0] if row else 0

        cur = await conn.execute("SELECT COUNT(*) FROM users WHERE ref1_id=?", (uid,))
        r1 = (await cur.fetchone())[0]

        cur = await conn.execute("SELECT COUNT(*) FROM users WHERE ref2_id=?", (uid,))
        r2 = (await cur.fetchone())[0]

    # 1) Стата
    text = (
        "💸 *Заработать с ботом*\n\n"
        f"Рефералы 1-го уровня: {r1}\n"
        f"Рефералы 2-го уровня: {r2}\n"
        f"Баланс: {bal/100:.2f} ₽\n\n"
        "Ниже твоя персональная ссылка 👇"
    )
    await m.answer(text, parse_mode="Markdown")

    # 2) Ссылка отдельным сообщением
    await m.answer(link)

    # 3) Кнопка «Поделиться»
    kb = InlineKeyboardBuilder()
    kb.button(text="📤 Поделиться ссылкой", switch_inline_query=link)
    await m.answer("Удобно переслать 👇", reply_markup=kb.as_markup())

# ---------------
# НАВИГАЦИЯ / КАТЕГОРИИ
# ---------------
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
        # ВАЖНО: base_url должен быть валидным доменом (без заглушек YOUR_CPA_LINK)
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

    # parse_mode=HTML включён глобально, поэтому угловые скобки экранируем через <code>
    await c.message.edit_text(
        f"✅ Заявка #{pid} создана.\n"
        f"Сумма: {price} ₽.\n\n"
        f"Оплатить переводом (СБП/Тинькофф/Сбер). После оплаты админ подтвердит и бот выдаст код.\n"
        f"Подтверждение делает админ командой /confirm {pid} <code>КОД</code>",
        parse_mode="HTML"
    )
    await c.answer()
