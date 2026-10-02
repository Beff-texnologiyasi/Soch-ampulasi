import os, re, time, threading, requests
from flask import Flask, request, jsonify, send_file
import db

app = Flask(__name__)
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
NOTIFY_NEW = os.environ.get("NOTIFY_NEW") == "1"   # мгновенное уведомление о каждой заявке
_hits = {}

def limited(ip, n=40, per=60):
    now = time.time()
    h = [t for t in _hits.get(ip, []) if now - t < per] + [now]
    _hits[ip] = h
    return len(h) > n

def notify(text):
    for cid in db.authed_ids():
        try:
            requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                          json={"chat_id": cid, "text": text}, timeout=8)
        except Exception:
            pass

@app.get("/")
def index():
    return send_file("static/index.html")

@app.get("/health")
def health():
    return "ok"

@app.post("/api/register")
def register():
    j = request.get_json(silent=True) or {}
    ip = (request.headers.get("X-Forwarded-For", request.remote_addr) or "").split(",")[0].strip()
    if j.get("website"):
        return jsonify(ok=True)
    if limited(ip):
        return jsonify(ok=False, error="rate"), 429
    name = re.sub(r"\s+", " ", (j.get("name") or "")).strip()[:120]
    phone = db.norm_phone(j.get("phone"))
    if len(name) < 3 or not phone:
        return jsonify(ok=False, error="invalid"), 400
    new = db.add_lead(name, "+" + phone, (j.get("src") or "")[:200], ip)
    if new and NOTIFY_NEW and BOT_TOKEN:
        threading.Thread(target=notify, args=(f"Новая заявка\n{name}\n+{phone}",), daemon=True).start()
    return jsonify(ok=True, dup=not new)
