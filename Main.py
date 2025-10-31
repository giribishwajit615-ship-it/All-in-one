# file: video_proxy_bot.py
# Requires: pip install python-telegram-bot==20.5
import sqlite3
import secrets
import html
from telegram import Update, InputMediaVideo
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

DB = "videos.db"
BOT_USERNAME = "Oll_in_one_bot"   # without @, e.g. MyVideoProxyBot
BOT_TOKEN = "8311890150:AAE2a13FqcmHMflWc_me4Z6cmv7FoIJ-XGs"

# --- DB helpers ---
def init_db():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS files (
        token TEXT PRIMARY KEY,
        file_id TEXT NOT NULL,
        mime_type TEXT,
        file_name TEXT,
        channel_message_id INTEGER,
        media_group_id TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    conn.commit()
    conn.close()

def save_file(token, file_id, mime_type=None, file_name=None, channel_message_id=None, media_group_id=None):
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute("INSERT INTO files (token, file_id, mime_type, file_name, channel_message_id, media_group_id) VALUES (?, ?, ?, ?, ?, ?)",
                (token, file_id, mime_type, file_name, channel_message_id, media_group_id))
    conn.commit()
    conn.close()

def get_file(token):
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute("SELECT file_id, file_name FROM files WHERE token = ?", (token,))
    row = cur.fetchone()
    conn.close()
    return row

# --- Utility ---
def gen_token(nbytes=16):
    return secrets.token_urlsafe(nbytes)

# --- Handlers ---
async def channel_post_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # This receives posts made in the channel where bot is admin.
    post = update.channel_post
    if not post:
        return

    # For single video as 'video' field
    media_group = getattr(post, "media_group_id", None)
    channel_msg_id = post.message_id

    # Handle video, document, animation — treat these similarly
    candidates = []
    if post.video:
        candidates.append(("video", post.video))
    if post.document:
        candidates.append(("document", post.document))
    if post.animation:
        candidates.append(("animation", post.animation))

    # If post has caption_entities or media as attachment list, sometimes we may need to inspect
    # If none found, ignore.
    if not candidates:
        return

    # Save each candidate file and create token/link
    links = []
    for kind, obj in candidates:
        file_id = obj.file_id
        mime = getattr(obj, "mime_type", None)
        fname = getattr(obj, "file_name", None)
        token = gen_token()
        save_file(token, file_id, mime_type=mime, file_name=fname, channel_message_id=channel_msg_id, media_group_id=media_group)
        link = f"https://t.me/{BOT_USERNAME}?start={token}"
        links.append((token, link))

    # Optionally: reply in channel with the generated links (if you want), or log them somewhere.
    # WARNING: if channel is private you might not want to post these links in the channel itself.
    # Here we will send a confirmation to the bot owner (first ADMIN). Replace ADMIN_CHAT_ID with your chat id.
    ADMIN_CHAT_ID = None  # set your Telegram user id here (int) if you want notifications
    if ADMIN_CHAT_ID:
        text = "Links generated for new channel post:\n" + "\n".join(f"{l}" for _, l in links)
        await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=text)

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text("Hi! Provide a token link.")
        return
    token = args[0]
    row = get_file(token)
    if not row:
        await update.message.reply_text("Invalid or expired link.")
        return
    file_id, file_name = row
    # send the video/document by file_id so channel identity is not exposed
    try:
        # We don't know exact type saved; try send_video first, fall back to send_document
        await context.bot.send_video(chat_id=update.effective_chat.id, video=file_id, caption=(file_name or "Video"))
    except Exception:
        # fallback
        await context.bot.send_document(chat_id=update.effective_chat.id, document=file_id, caption=(file_name or "File"))

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Send me a token link (t.me/YourBot?start=TOKEN) and I'll send the video.")

# --- Run bot ---
if __name__ == "__main__":
    init_db()
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # channel_post handler: receives posts that appear in channels where bot is admin
    app.add_handler(MessageHandler(filters.CHANNEL, channel_post_handler))
    # start handler /start TOKEN
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("help", help_cmd))

    print("Bot running...")
    app.run_polling()
