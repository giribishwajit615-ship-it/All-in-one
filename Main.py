# bot_and_server_fixed.py
import sqlite3
import string
import random
from flask import Flask, g, render_template_string
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
import asyncio
import threading
import os

# ========== CONFIG ==========
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN") or "8311890150:AAE2a13FqcmHMflWc_me4Z6cmv7FoIJ-XGs"
ADMIN_ID = 7681308594  # optional
# Agar BASE_URL nahi set hai to default localhost use karega
BASE_URL = os.environ.get("BASE_URL", "http://localhost:5000")
DB_PATH = "links.db"
# ============================

app = Flask(__name__)

# ---------- DB helpers ----------
def get_db():
    if not hasattr(g, "_database"):
        g._database = sqlite3.connect(DB_PATH)
        g._database.row_factory = sqlite3.Row
    return g._database

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS groups (
        id TEXT PRIMARY KEY,
        title TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS links (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        group_id TEXT,
        url TEXT,
        label TEXT,
        pos INTEGER DEFAULT 0,
        FOREIGN KEY(group_id) REFERENCES groups(id)
    )
    """)
    conn.commit()
    conn.close()

def make_id(n=6):
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(n))

def save_group(title, urls):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    gid = make_id()
    while True:
        c.execute("SELECT 1 FROM groups WHERE id=?", (gid,))
        if c.fetchone():
            gid = make_id()
        else:
            break
    c.execute("INSERT INTO groups (id, title) VALUES (?, ?)", (gid, title))
    for i, u in enumerate(urls):
        c.execute("INSERT INTO links (group_id, url, label, pos) VALUES (?, ?, ?, ?)", (gid, u.strip(), u.strip(), i))
    conn.commit()
    conn.close()
    return gid

def get_group(gid):
    db = get_db()
    grp = db.execute("SELECT * FROM groups WHERE id=?", (gid,)).fetchone()
    if not grp:
        return None
    links = db.execute("SELECT * FROM links WHERE group_id=? ORDER BY pos", (gid,)).fetchall()
    return {"id": grp["id"], "title": grp["title"], "links": links}

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()

# ---------- Flask page ----------
TEMPLATE = """
<!doctype html>
<html><head>
  <meta charset="utf-8">
  <title>{{ title }}</title>
  <style>
    body { font-family:sans-serif; padding:20px; background:#fafafa; }
    .card { max-width:600px; margin:auto; background:#fff; padding:20px; border-radius:12px; box-shadow:0 0 8px rgba(0,0,0,0.1); }
    a { display:block; margin:8px 0; text-decoration:none; color:#007bff; }
  </style>
</head><body>
  <div class="card">
    <h2>{{ title }}</h2>
    <p>Total links: {{ links|length }}</p><hr>
    {% for l in links %}
      <a href="{{ l['url'] }}" target="_blank">{{ l['label'] }}</a>
    {% endfor %}
  </div>
</body></html>
"""

@app.route("/g/<gid>")
def show_group(gid):
    data = get_group(gid)
    if not data:
        return "Not found", 404
    return render_template_string(TEMPLATE, title=data["title"], links=data["links"])

# ---------- Telegram bot ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Namaste! Mujhe ek ya multiple links bhejo (har ek alag line me).\n"
        "Main tumhe ek short link dunga jo sabko dikhayega.\n\n"
        "Example:\nhttps://a.com\nhttps://b.com"
    )

async def handle_links(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if ADMIN_ID and update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Aap authorized nahi ho.")
        return

    text = update.message.text.strip()
    urls = [l.strip() for l in text.splitlines() if l.strip().startswith(("http://", "https://"))]
    if not urls:
        await update.message.reply_text("Koi valid link nahi mila. Har link ko alag line me bhejo.")
        return

    gid = save_group(f"Shared by {update.effective_user.first_name}", urls)
    short_link = f"{BASE_URL}/g/{gid}"
    await update.message.reply_text(f"✅ Ye lo aapka combined link:\n{short_link}")

def run_flask():
    app.run(host="0.0.0.0", port=5000)

async def run_bot():
    init_db()
    bot = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    bot.add_handler(CommandHandler("start", start))
    bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_links))
    await bot.initialize()
    await bot.start()
    await bot.updater.wait_for_stop()

def main():
    init_db()
    threading.Thread(target=run_flask, daemon=True).start()
    asyncio.run(run_bot())

if __name__ == "__main__":
    main()
