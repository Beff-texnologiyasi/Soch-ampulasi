import os, io, re
from contextlib import contextmanager
import psycopg2
from psycopg2.pool import ThreadedConnectionPool
from openpyxl import Workbook

DB = os.environ["DATABASE_URL"]
_pool = None

@contextmanager
def cur():
    global _pool
    if _pool is None:
        _pool = ThreadedConnectionPool(1, 20, DB)
    c = _pool.getconn()
    try:
        with c.cursor() as k:
            yield k
        c.commit()
    except Exception:
        c.rollback()
        raise
    finally:
        _pool.putconn(c)

def init_db():
    with cur() as k:
        k.execute("""CREATE TABLE IF NOT EXISTS leads(
            id SERIAL PRIMARY KEY, name TEXT NOT NULL, phone TEXT NOT NULL UNIQUE,
            src TEXT, ip TEXT, created_at TIMESTAMPTZ NOT NULL DEFAULT now())""")
        k.execute("""CREATE TABLE IF NOT EXISTS bot_users(
            chat_id BIGINT PRIMARY KEY, added_at TIMESTAMPTZ NOT NULL DEFAULT now())""")

def norm_phone(raw):
    d = re.sub(r"\D", "", raw or "")
    if len(d) == 9:
        d = "998" + d
    return d if len(d) == 12 and d.startswith("998") else None

def add_lead(name, phone, src, ip):
    """True если новая заявка, False если номер уже был."""
    with cur() as k:
        k.execute("INSERT INTO leads(name,phone,src,ip) VALUES(%s,%s,%s,%s) "
                    "ON CONFLICT (phone) DO NOTHING RETURNING id", (name, phone, src, ip))
        return k.fetchone() is not None

def count(since=None):
    with cur() as k:
        if since:
            k.execute("SELECT count(*) FROM leads WHERE created_at >= %s", (since,))
        else:
            k.execute("SELECT count(*) FROM leads")
        return k.fetchone()[0]

def leads(since=None):
    q = "SELECT id,name,phone,src,created_at AT TIME ZONE 'Asia/Tashkent' FROM leads"
    with cur() as k:
        if since:
            k.execute(q + " WHERE created_at >= %s ORDER BY id", (since,))
        else:
            k.execute(q + " ORDER BY id")
        return k.fetchall()

def is_authed(chat_id):
    with cur() as k:
        k.execute("SELECT 1 FROM bot_users WHERE chat_id=%s", (chat_id,))
        return k.fetchone() is not None

def authorize(chat_id):
    with cur() as k:
        k.execute("INSERT INTO bot_users(chat_id) VALUES(%s) ON CONFLICT DO NOTHING", (chat_id,))

def authed_ids():
    with cur() as k:
        k.execute("SELECT chat_id FROM bot_users")
        return [r[0] for r in k.fetchall()]

def build_xlsx(rows):
    wb = Workbook(); ws = wb.active; ws.title = "Leads"
    ws.append(["№", "Ism Familiya", "Telefon", "Manba", "Sana"])
    for r in rows:
        ws.append([r[0], r[1], r[2], r[3], r[4].strftime("%Y-%m-%d %H:%M")])
    for col, w in zip("ABCDE", (6, 32, 18, 28, 18)):
        ws.column_dimensions[col].width = w
    buf = io.BytesIO(); wb.save(buf); buf.seek(0)
    return buf
