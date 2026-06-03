import json
import base64
import aiohttp
import asyncio
from datetime import datetime, date
from flask import Flask, request, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes

# ============ CONFIGURATION ============
API_URL = "https://kanhaiya-raikwar.vercel.app/"
ENCODED_KEY = "WkVYWFk="
API_KEY = base64.b64decode(ENCODED_KEY).decode()

BOT_TOKEN = "8437758795:AAFbeCsPUT4DkFMBsaa_ibPK4IeWwzS5yJc"
ADMIN_IDS = [7890824548]

DATA_FILES = {
    'allowed': '/tmp/allowed_groups.json',
    'stats': '/tmp/daily_stats.json',
    'users': '/tmp/user_limits.json',
    'config': '/tmp/bot_config.json'
}

bot_status = "on"
bot_mode = "public"
allowed_groups = {}
daily_stats = {}
user_limits = {}
daily_limit = 2

app = Flask(__name__)
tg_app = Application.builder().token(BOT_TOKEN).build()

def load_data():
    global allowed_groups, daily_stats, user_limits, bot_status, bot_mode, daily_limit
    try:
        with open(DATA_FILES['allowed'], 'r') as f: allowed_groups = json.load(f)
    except: allowed_groups = {}
    try:
        with open(DATA_FILES['stats'], 'r') as f: daily_stats = json.load(f)
    except: daily_stats = {}
    try:
        with open(DATA_FILES['users'], 'r') as f: user_limits = json.load(f)
    except: user_limits = {}
    try:
        with open(DATA_FILES['config'], 'r') as f:
            cfg = json.load(f)
            bot_status = cfg.get('status', 'on')
            bot_mode = cfg.get('mode', 'public')
            daily_limit = cfg.get('limit', 2)
    except:
        bot_status, bot_mode, daily_limit = 'on', 'public', 2

def save_all():
    try:
        with open(DATA_FILES['allowed'], 'w') as f: json.dump(allowed_groups, f, indent=2)
        with open(DATA_FILES['stats'], 'w') as f: json.dump(daily_stats, f, indent=2)
        with open(DATA_FILES['users'], 'w') as f: json.dump(user_limits, f, indent=2)
        with open(DATA_FILES['config'], 'w') as f: json.dump({'status': bot_status, 'mode': bot_mode, 'limit': daily_limit}, f, indent=2)
    except Exception as e:
        print(f"Error saving data: {e}")

def is_admin(uid): return uid in ADMIN_IDS
def today_str(): return str(date.today())

def can_user_like(uid):
    if is_admin(uid): return True
    t = today_str()
    if uid not in user_limits or user_limits[uid]['date'] != t:
        user_limits[uid] = {'date': t, 'count': 0}
        return True
    return user_limits[uid]['count'] < daily_limit

def update_user_like(uid):
    if is_admin(uid): return
    t = today_str()
    if uid not in user_limits or user_limits[uid]['date'] != t:
        user_limits[uid] = {'date': t, 'count': 0}
    user_limits[uid]['count'] += 1
    
    if t not in daily_stats:
        daily_stats[t] = {'total': 0, 'users': {}}
    daily_stats[t]['total'] += 1
    uid_str = str(uid)
    if uid_str not in daily_stats[t]['users']:
        daily_stats[t]['users'][uid_str] = 0
    daily_stats[t]['users'][uid_str] += 1
    save_all()

async def call_like_api(region, uid):
    try:
        url = f"{API_URL}like?uid={uid}&region={region}&key={API_KEY}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200: return await resp.json()
                return {"error": f"HTTP {resp.status}"}
    except asyncio.TimeoutError: return {"error": "Timeout"}
    except Exception as e: return {"error": str(e)}

def is_group_allowed(chat_id, chat_type):
    if chat_type == "private" or bot_mode == "public": return True
    return str(chat_id) in allowed_groups

async def block_non_admin_private(update: Update) -> bool:
    chat_type = update.effective_chat.type
    user_id = update.effective_user.id
    if chat_type == "private" and not is_admin(user_id):
        await update.message.reply_text("🚫 *बॉट केवल ग्रुप में काम करता है!*\n(एडमिन इसे प्राइवेट में इस्तेमाल कर सकते हैं)", parse_mode='Markdown')
        return True
    return False

async def reply(update, text):
    await update.message.reply_text(text, parse_mode='Markdown')

# ============ USER COMMANDS ============
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await block_non_admin_private(update): return
    if bot_status == "off":
        await reply(update, "🔴 *बॉट अभी बंद (OFF) है*")
        return
    msg = (
        "┌─[ 👑 S.KANHAIYA LIKE BOT ]─🥷\n"
        "│\n"
        "├─► 💬 `/like REGION UID` – लाइक भेजने के लिए\n"
        "├─► 💬 `/help` – सभी कमांड्स देखने के लिए\n"
        "├─► 💬 `/info` – अपने बचे हुए लाइक्स देखने के लिए\n"
        "│\n"
        "├─► 📌 *उदाहरण:* `/like IND 14160011100`\n"
        f"├─► 🔥 आपकी दैनिक सीमा: `{daily_limit}` लाइक्स\n"
        "│\n"
        "└─[ ⚡️ ᴘᴏᴡᴇʀᴇᴅ ʙʏ ᴋ.ʀ sᴇʀᴠɪᴄᴇ ]──"
    )
    await reply(update, msg)

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await block_non_admin_private(update): return
    if bot_status == "off": return
    msg = (
        "┌─[ 📖 COMMAND MENU ]─📝\n"
        "│\n"
        "├─► 🔹 `/like REGION UID` – 1 लाइक भेजें\n"
        "├─► 🔹 `/info` – बचे हुए लाइक्स चेक करें\n"
        "├─► 🔹 `/start` – स्वागत संदेश\n"
        "│\n"
        "👑 *एडमिन कमांड्स:*\n"
        "├─► `/allow` – ग्रुप अनुमति दें\n"
        "├─► `/off` / `/on` – बॉट चालू/बंद\n"
        "├─► `/stats` – आज का उपयोग देखें\n"
        "├─► `/setprivate` / `/setpublic` – मोड बदलें\n"
        "├─► `/setlimit <संख्या>` – दैनिक सीमा बदलें\n"
        "│\n"
        "└─[ ⚡️ ᴘᴏᴡᴇʀᴇᴅ ʙʏ ᴋ.ʀ sᴇʀᴠɪᴄᴇ ]──"
    )
    await reply(update, msg)

async def info_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await block_non_admin_private(update): return
    if bot_status == "off": return
    uid = update.effective_user.id
    if is_admin(uid):
        await reply(update, "┌─[ 👑 ADMIN ACCOUNT ]─🥷\n│\n├─► 🔥 असीमित लाइक्स उपलब्ध हैं।\n│\n└─[ ⚡️ ᴘᴏᴡᴇʀᴇᴅ ʙʏ ᴋ.ʀ sᴇʀᴠɪᴄᴇ ]──")
        return
    t = today_str()
    used = user_limits.get(uid, {}).get('count', 0) if uid in user_limits and user_limits[uid]['date'] == t else 0
    remaining = daily_limit - used
    msg = (
        "┌─[ 🤖 USER INFO ]─📊\n"
        "│\n"
        f"├─► ⚙️ मोड: `{bot_mode.upper()}`\n"
        f"├─► 🟢 स्टेटस: `{bot_status.upper()}`\n"
        f"├─► 📅 दैनिक सीमा: `{daily_limit}` लाइक्स\n"
        f"├─► ✅ आज उपयोग किया: `{used}`\n"
        f"├─► 🟢 शेष लाइक्स: `{remaining}`\n"
        "│\n"
        "└─[ ⚡️ ᴘᴏᴡᴇʀᴇᴅ ʙʏ ᴋ.ʀ sᴇʀᴠɪᴄᴇ ]──"
    )
    await reply(update, msg)

async def like_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await block_non_admin_private(update): return
    if bot_status == "off": return
    
    chat_id = update.effective_chat.id
    chat_type = update.effective_chat.type
    if chat_type != "private" and not is_group_allowed(chat_id, chat_type):
        await reply(update, "🚫 *यह बॉट केवल अनुमति प्राप्त ग्रुप्स में ही काम करता है!*")
        return
    
    if len(context.args) != 2:
        await reply(update, "❌ *सही तरीका:* `/like REGION UID`")
        return
    
    region = context.args[0].upper()
    uid = context.args[1]
    if not uid.isdigit():
        await reply(update, "❌ *UID में केवल नंबर होने चाहिए!*")
        return
    
    user_id = update.effective_user.id
    if not can_user_like(user_id):
        used = user_limits.get(user_id, {}).get('count', 0)
        await reply(update, f"⚠️ *दैनिक सीमा समाप्त!*\nआप आज `{used}/{daily_limit}` लाइक्स का उपयोग कर चुके हैं।")
        return
    
    proc_msg = await update.message.reply_text(
        "┌─[ 👑 S.KANHAIYA LIKE BOT ]─🥷\n"
        "│\n"
        f"├─► 🔄 *प्रक्रिया जारी है...*\n"
        f"├─► 🆔 यूआईडी: `{uid}`\n"
        f"├─► 🌍 रीजन: {region}\n"
        "│\n"
        "└─[ ⚡️ ᴘᴏᴡᴇʀᴇᴅ ʙʏ ᴋ.ʀ sᴇʀᴠɪᴄᴇ ]──", 
        parse_mode='Markdown'
    )
    
    data = await call_like_api(region, uid)
    
    if data is None or "error" in data:
        await proc_msg.edit_text(
            "┌─[ 👑 S.KANHAIYA LIKE BOT ]─🥷\n"
            "│\n"
            "├─► ❌ *[ERROR] API रेस्पॉन्स फेल*\n"
            "│\n"
            "└─[ ⚡️ ᴘᴏᴡᴇʀᴇᴅ ʙʏ ᴋ.ʀ sᴇʀᴠɪᴄᴇ ]──", 
            parse_mode='Markdown'
        )
        return
    
    status = data.get('status')
    player = data.get('PlayerNickname', 'Unknown')
    before = data.get('LikesbeforeCommand', 0)
    after = data.get('LikesafterCommand', 0)
    given = data.get('LikesGivenByAPI', 0)
    
    # ✅ सफलता (SUCCESS INTERFACE)
    if status == 1:
        update_user_like(user_id)
        result = (
            f"┌─[ 👑 S.KANHAIYA LIKE BOT ]─🥷\n"
            f"│\n"
            f"├─► ✅ लाइक भेज दिया गया है 😍\n"
            f"│\n"
            f"├─► 👤 खिलाड़ी: {player}\n"
            f"├─► 🆔 यूआईडी: `{uid}`\n"
            f"├─► 🌍 रीजन: {region}\n"
            f"│\n"
            f"├─► 📊 ओल्ड स्कोर: {before}\n"
            f"├─► 🔄 न्यू स्कोर: {after}\n"
            f"├─► ➕ प्लस लाइक: +{given}\n"
            f"│\n"
            f"└─[ ⚡️ ᴘᴏᴡᴇʀᴇᴅ ʙʏ ᴋ.ʀ sᴇʀᴠɪᴄᴇ ]──"
        )
        await proc_msg.edit_text(result, parse_mode='Markdown')
        
    # ⚠️ असफलता (ERROR INTERFACE)
    else:
        result = (
            f"┌─[ 👑 S.KANHAIYA LIKE BOT ]─🥷\n"
            f"│\n"
            f"├─► ⚠️ [ERROR] लाइक नहीं भेजा जा सका\n"
            f"│\n"
            f"├─► 👤 खिलाड़ी: {player}\n"
            f"├─► 🆔 यूआईडी: `{uid}`\n"
            f"├─► 🌍 रीजन: {region}\n"
            f"│\n"
            f"├─► 📊 ओल्ड स्कोर: {before}\n"
            f"├─► 🔄 न्यू स्कोर: {after}\n"
            f"├─► ➕ प्लस लाइक: {given}\n"
            f"│\n"
            f"└─[ ⚡️ ᴘᴏᴡᴇʀᴇᴅ ʙʏ ᴋ.ʀ sᴇʀᴠɪᴄᴇ ]──"
        )
        keyboard = [[InlineKeyboardButton("Instagram Support", url="https://www.instagram.com/s.kanhaiya.7m")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await proc_msg.edit_text(result, parse_mode='Markdown', reply_markup=reply_markup)

# ============ ADMIN COMMANDS ============
async def allow_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    chat = update.effective_chat
    allowed_groups[str(chat.id)] = {'name': chat.title, 'by': update.effective_user.id, 'date': today_str()}
    save_all()
    await reply(update, f"✅ *ग्रुप को अनुमति दे दी गई है*")

async def off_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    global bot_status; bot_status = "off"; save_all()
    await reply(update, "🔴 *बॉट बंद है*")

async def on_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    global bot_status; bot_status = "on"; save_all()
    await reply(update, "🟢 *बॉट चालू है*")

async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    t = today_str()
    if t not in daily_stats: return
    await reply(update, f"📊 कुल लाइक: `{daily_stats[t]['total']}`")

async def set_private(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    global bot_mode; bot_mode = "private"; save_all()
    await reply(update, "🔒 *प्राइवेट मोड चालू*")

async def set_public(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    global bot_mode; bot_mode = "public"; save_all()
    await reply(update, "🌍 *पब्लिक मोड चालू*")

async def set_limit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    if len(context.args) != 1 or not context.args[0].isdigit(): return
    global daily_limit; daily_limit = int(context.args[0]); save_all()
    await reply(update, f"✅ सीमा `{daily_limit}` की गई")

def setup_handlers(app_instance):
    app_instance.add_handler(CommandHandler("start", start))
    app_instance.add_handler(CommandHandler("help", help_cmd))
    app_instance.add_handler(CommandHandler("info", info_cmd))
    app_instance.add_handler(CommandHandler("like", like_cmd))
    app_instance.add_handler(CommandHandler("allow", allow_group))
    app_instance.add_handler(CommandHandler("off", off_cmd))
    app_instance.add_handler(CommandHandler("on", on_cmd))
    app_instance.add_handler(CommandHandler("stats", stats_cmd))
    app_instance.add_handler(CommandHandler("setprivate", set_private))
    app_instance.add_handler(CommandHandler("setpublic", set_public))
    app_instance.add_handler(CommandHandler("setlimit", set_limit))

@app.route('/api/bot-webhook', methods=['POST'])
def webhook():
    load_data()
    if request.method == "POST":
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            if not tg_app.handlers:
                setup_handlers(tg_app)
            update = Update.de_json(request.get_json(force=True), tg_app.bot)
            loop.run_until_complete(tg_app.initialize())
            loop.run_until_complete(tg_app.process_update(update))
            return jsonify({"status": "ok"}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    return jsonify({"status": "failed"}), 405

@app.route('/')
def home(): return "Bot Running!"
