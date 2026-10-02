import os, hmac, time, asyncio
from datetime import datetime, timedelta, time as dtime
from zoneinfo import ZoneInfo
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import db

TZ = ZoneInfo("Asia/Tashkent")
PASSWORD = os.environ["BOT_PASSWORD"]
BTN = "📊 Отчёт (Excel)"
KB = ReplyKeyboardMarkup([[BTN]], resize_keyboard=True)
_fails = {}   # chat_id -> [попытки, заблокирован_до]

def day_start():
    return datetime.now(TZ).replace(hour=0, minute=0, second=0, microsecond=0)

async def send_report(bot, chat_id, rows, caption, name):
    if rows:
        f = await asyncio.to_thread(db.build_xlsx, rows)
        await bot.send_document(chat_id, document=f, filename=name, caption=caption, reply_markup=KB)
    else:
        await bot.send_message(chat_id, caption, reply_markup=KB)

async def report(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    total, today, week = await asyncio.gather(
        asyncio.to_thread(db.count), asyncio.to_thread(db.count, day_start()),
        asyncio.to_thread(db.count, datetime.now(TZ) - timedelta(days=7)))
    rows = await asyncio.to_thread(db.leads)
    cap = f"Всего: {total}\nСегодня: +{today}\nЗа 7 дней: +{week}"
    await send_report(ctx.bot, update.effective_chat.id, rows, cap, f"leads_{datetime.now(TZ):%Y-%m-%d}.xlsx")

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if await asyncio.to_thread(db.is_authed, update.effective_chat.id):
        await update.message.reply_text("Готово. Нажмите кнопку для отчёта.", reply_markup=KB)
    else:
        await update.message.reply_text("Напишите пароль:")

async def text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    msg = update.message.text or ""
    if await asyncio.to_thread(db.is_authed, cid):
        if msg == BTN:
            await report(update, ctx)
        return
    n, until = _fails.get(cid, [0, 0])
    if time.time() < until:
        await update.message.reply_text("Слишком много попыток. Подождите 10 минут.")
        return
    if hmac.compare_digest(msg.strip().encode(), PASSWORD.encode()):
        _fails.pop(cid, None)
        await asyncio.to_thread(db.authorize, cid)
        try:
            await update.message.delete()      # убрать пароль из чата
        except Exception:
            pass
        await ctx.bot.send_message(cid, "Доступ открыт ✅ Отчёты будут приходить каждый день в 21:00 и по воскресеньям за неделю.", reply_markup=KB)
    else:
        n += 1
        _fails[cid] = [0, time.time() + 600] if n >= 5 else [n, 0]
        await update.message.reply_text("Неверный пароль.")

async def daily(ctx: ContextTypes.DEFAULT_TYPE):
    now = datetime.now(TZ)
    total = await asyncio.to_thread(db.count)
    jobs = [("📅 Итог дня", day_start(), "day")]
    if now.weekday() == 6:                           # воскресенье: ещё и недельный
        jobs.append(("📆 Итог недели", now - timedelta(days=7), "week"))
    ids = await asyncio.to_thread(db.authed_ids)
    for title, since, tag in jobs:
        rows = await asyncio.to_thread(db.leads, since)
        cap = f"{title}: +{len(rows)} новых\nВсего: {total}"
        for cid in ids:
            try:
                await send_report(ctx.bot, cid, rows, cap, f"leads_{tag}_{now:%Y-%m-%d}.xlsx")
            except Exception:
                pass

def run():
    app = Application.builder().token(os.environ["BOT_TOKEN"]).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text))
    app.job_queue.run_daily(daily, time=dtime(21, 0, tzinfo=TZ))
    app.run_polling(drop_pending_updates=True)
