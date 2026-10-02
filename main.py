import os, threading
import db
db.init_db()
from web import app
import bot

def serve():
    from waitress import serve as s
    s(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)), threads=8)

if __name__ == "__main__":
    threading.Thread(target=serve, daemon=True).start()
    bot.run()
