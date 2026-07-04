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
INFO_API_URL = "https://s-kanhaiya-ff-info.vercel.app/player-info"
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

async def call_info_api(region, uid):
    try:
        url = f"{INFO_API_URL}?region={region.lower()}&uid={uid}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=12)) as resp:
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
        "├─► 💬 `/info` – अपनी लिमिट देखने के लिए\n"
        "├─► 💬 `/info REGION UID` – प्लेयर डेटा देखने के लिए\n"
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
        "├─► 🔹 `/info` – खुद के बचे हुए लाइक्स चेक करें\n"
        "├─► 🔹 `/info REGION UID` – किसी प्लेयर की डिटेल्स निकालें\n"
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
    
    if len(context.args) == 2:
        chat_id = update.effective_chat.id
        chat_type = update.effective_chat.type
        if chat_type != "private" and not is_group_allowed(chat_id, chat_type):
            await reply(update, "🚫 *यह बॉट केवल अनुमति प्राप्त ग्रुप्स में ही काम करता है!*")
            return
            
        region = context.args[0].upper()
        uid = context.args[1]
        if not uid.isdigit():
            await reply(update, "❌ *UID में केवल नंबर होने चाहिए!*")
            return
            
        proc_msg = await update.message.reply_text(
            "┌─[ 🔍 PLAYER INFO SEARCH ]─📊\n"
            "│\n"
            "├─► 🔄 *डेटा निकाला जा रहा है...*\n"
            f"├─► 🆔 यूआईडी: `{uid}`\n"
            f"├─► 🌍 रीजन: {region}\n"
            "│\n"
            "└─[ ⚡️ ᴘᴏᴡᴇʀᴇᴅ ʙʏ ᴋ.ʀ sᴇʀᴠɪᴄᴇ ]──",
            parse_mode='Markdown'
        )
        
        raw_data = await call_info_api(region, uid)
        
        if raw_data is None or "error" in raw_data or not (raw_data.get("BasicInfo") or raw_data.get("basicInfo")):
            await proc_msg.edit_text(
                "┌─[ 🔍 PLAYER INFO SEARCH ]─📊\n"
                "│\n"
                "├─► ❌ *खिलाड़ी का डेटा नहीं मिल पाया या API फेल हो गई!*\n"
                "│\n"
                "└─[ ⚡️ ᴘᴏᴡᴇʀᴇᴅ ʙʏ ᴋ.ʀ sᴇʀᴠɪᴄᴇ ]──",
                parse_mode='Markdown'
            )
            return

        # एपीआई कीस (Keys) को निकालना (Safe Handling)
        basic = raw_data.get("BasicInfo") or raw_data.get("basicInfo") or {}
        guild = raw_data.get("guildInfo") or raw_data.get("GuildInfo") or {}

        # 1. खास इन्फॉर्मेशन (Main Summary Section)
        nickname = basic.get("nickname") or basic.get("Nickname") or "Unknown"
        level = basic.get("level", "N/A")
        likes = basic.get("liked") or basic.get("Liked") or 0
        guild_name = guild.get("name", "Not Found")
        guild_id = guild.get("id", "Not Found")

        # टाइमस्टैम्प को सही फॉर्मेट में बदलना
        create_time = basic.get("createTime") or basic.get("createdAt") or "N/A"
        last_login = basic.get("lastLogin") or basic.get("lastLoginTime") or "N/A"
        if str(create_time).isdigit():
            create_time = datetime.fromtimestamp(int(create_time)).strftime('%d-%m-%Y %I:%M %p')
        if str(last_login).isdigit():
            last_login = datetime.fromtimestamp(int(last_login)).strftime('%d-%m-%Y %I:%M %p')

        # Raw JSON डेटा को स्ट्रिंग में बदलना (ताकि सारा का सारा डेटा अलग से दिखे)
        try:
            full_raw_string = json.dumps(raw_data, indent=2, ensure_ascii=False)
        except Exception:
            full_raw_string = str(raw_data)

        # नया कस्टमाइज्ड लेआउट: खास इन्फो अलग और सारा डेटा नीचे कोड ब्लॉक में
        info_res = (
            f"┌─[ 👑 *खास प्लेयर जानकारी* ]──\n"
            f"├─👤 *नाम:* {nickname}\n"
            f"├─🆔 *यूआईडी:* `{uid}`\n"
            f"├─🌍 *रीजन:* {region}\n"
            f"├─🆙 *लेवल:* {level}\n"
            f"├─❤️ *लाइक्स:* {likes}\n"
            f"├─🛡️ *गिल्ड नाम:* {guild_name}\n"
            f"├─🔑 *गिल्ड आईडी:* `{guild_id}`\n"
            f"└───────────────────\n\n"
            
            f"┌─[ 📅 *एक्टिविटी स्टेटस* ]──\n"
            f"├─⏰ *अकाउंट बना:* {create_time}\n"
            f"├─🚪 *आखिरी लॉगिन:* {last_login}\n"
            f"└───────────────────\n\n"
            
            f"⚙️ *[ API का सारा डेटा (RAW DATA) ]* 👇\n"
            f"```json\n"
            f"{full_raw_string}\n"
            f"
```\n\n"
            f"└─ [ ⚡️ ᴘᴏᴡᴇʀᴇᴅ ʙʏ ᴋ.ʀ sᴇʀᴠɪᴄᴇ ] ──"
        )
        
        await proc_msg.edit_text(info_res, parse_mode='Markdown')
        return

    uid = update.effective_user.id
    if is_admin(uid):
        await reply(update, "┌─[ 👑 ADMIN ACCOUNT ]─🥷\n│\n├─► 🔥 असीमित लाइक्स उपलब्ध हैं।\n│\n└─[ ⚡️ ᴘᴏᴡᴇʀᴇᴅ ʙʏ ᴋ.ʀ sᴇʀᴠɪᴄᴇ ]──")
        return
    t = today_str()
    used = user_limits.get(uid, {}).get('count', 0) if uid in user_limits and user_limits[uid]['date'] == t else 0
    remaining = daily_limit - used
import os
import json
import base64
import aiohttp
import asyncio
from datetime import date, datetime
from flask import Flask, request, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes
import logging

# ============ LOGGING ============
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ============ FLASK APP ============
app = Flask(__name__)

# ============ CONFIGURATION ============
BOT_TOKEN = os.getenv("BOT_TOKEN", "8752690086:AAGEdWri8qtC6vHw2wHDObUmWmoa-hyyh-M")

# APIs
VISIT_API_URL = "https://kanhaiya-vvvvbvvb.vercel.app/"
LIKE_API_URL = "https://kanhaiya-raikwar.vercel.app/"
ENCODED_KEY = "WkVYWFk="
API_KEY = base64.b64decode(ENCODED_KEY).decode()
INFO_API_URL = "https://s-kanhaiya-ff-info.vercel.app/player-info"

# ============ DATA STORAGE (Vercel /tmp/) ============
DATA_FILE = '/tmp/bot_data.json'

def load_data():
    try:
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    except:
        return {'users': {}, 'stats': {}}

def save_data(data):
    try:
        with open(DATA_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    except:
        pass

# ============ USER LIMITS ============
DAILY_LIMIT = 2

def today_str():
    return str(date.today())

def can_user_like(user_id):
    data = load_data()
    t = today_str()
    if str(user_id) not in data['users'] or data['users'][str(user_id)]['date'] != t:
        return True
    return data['users'][str(user_id)]['count'] < DAILY_LIMIT

def update_user_like(user_id):
    data = load_data()
    t = today_str()
    uid = str(user_id)
    
    if uid not in data['users'] or data['users'][uid]['date'] != t:
        data['users'][uid] = {'date': t, 'count': 0}
    data['users'][uid]['count'] += 1
    
    if t not in data['stats']:
        data['stats'][t] = 0
    data['stats'][t] += 1
    
    save_data(data)

# ============ FORMAT FUNCTIONS ============

def format_like_result(data):
    return (
        "┏━━━━━━━━━━━━━━━━━━━━━━┓\n"
        "┃ ╔════════════════════╗ \n"
        "┃ ║ ✦ S.KANHAIYA BOT ✦║\n"
        "┃ ║ 💝 LIKE SENT 💝   ║\n"
        "┃ ╚════════════════════╝ \n"
        "┃                        \n"
        "┃ ┌─ 👤 PROFILE ──────┐\n"
        f"┃ │ NAME : {data.get('player', 'Unknown')}\n"
        f"┃ │ UID  : {data.get('uid', 'N/A')}\n"
        f"┃ │ REGION: {data.get('region', 'N/A')}\n"
        "┃ └────────────────────┘\n"
        "┃                        \n"
        "┃ ┌─ ❤️ DETAILS ──────┐\n"
        f"┃ │ BEFORE: {data.get('before', 0)}\n"
        f"┃ │ AFTER : {data.get('after', 0)}\n"
        f"┃ │ GIVEN : +{data.get('given', 0)}\n"
        "┃ └────────────────────┘\n"
        "┃                        \n"
        "┃ ══════════════════════ \n"
        "┃ 💫 @S.KANHAIYA 💫     \n"
        "┗━━━━━━━━━━━━━━━━━━━━━━┛"
    )

def format_visit_result(data):
    return (
        "┏━━━━━━━━━━━━━━━━━━━━━━┓\n"
        "┃ ╔════════════════════╗ \n"
        "┃ ║ ✦ S.KANHAIYA BOT ✦║\n"
        "┃ ║ 📊 VISIT SENT 📊  ║\n"
        "┃ ╚════════════════════╝ \n"
        "┃                        \n"
        "┃ ┌─ 👤 PROFILE ──────┐\n"
        f"┃ │ NAME : {data.get('nickname', 'Unknown')}\n"
        f"┃ │ UID  : {data.get('uid', 'N/A')}\n"
        f"┃ │ REGION: {data.get('region', 'N/A')}\n"
        f"┃ │ LEVEL: {data.get('level', 'N/A')}\n"
        "┃ └────────────────────┘\n"
        "┃                        \n"
        "┃ ┌─ 📊 DETAILS ──────┐\n"
        f"┃ │ ✅SUCCESS: {data.get('success', 0)}\n"
        f"┃ │ ❌FAILED : {data.get('fail', 0)}\n"
        "┃ └────────────────────┘\n"
        "┃                        \n"
        "┃ ══════════════════════ \n"
        "┃ 💫 @S.KANHAIYA 💫     \n"
        "┗━━━━━━━━━━━━━━━━━━━━━━┛"
    )

def format_info_result(data):
    filtered_info = (
        "┏━━━━━━━━━━━━━━━━━━━━━━┓\n"
        "┃ ╔════════════════════╗ \n"
        "┃ ║ ✦ S.KANHAIYA BOT ✦║\n"
        "┃ ║ 👤 PLAYER INFO 👤 ║\n"
        "┃ ╚════════════════════╝ \n"
        "┃                        \n"
        "┃ ┌─ 🎮 BASIC ────────┐\n"
        f"┃ │ NAME : {data.get('nickname', 'Unknown')}\n"
        f"┃ │ UID  : {data.get('uid', 'N/A')}\n"
        f"┃ │ REGION: {data.get('region', 'N/A')}\n"
        f"┃ │ LEVEL: {data.get('level', 'N/A')}\n"
        f"┃ │ LIKES: {data.get('likes', 0)}\n"
        f"┃ │ EXP  : {data.get('exp', 'N/A')}\n"
        f"┃ │ ACCT : {data.get('account_type', 'N/A')}\n"
        "┃ └────────────────────┘\n"
        "┃                        \n"
        "┃ ┌─ 🏆 RANK ─────────┐\n"
        f"┃ │ BR   : {data.get('br_points', 'N/A')}\n"
        f"┃ │ CS   : {data.get('cs_points', 'N/A')}\n"
        f"┃ │ MAX  : {data.get('max_rank', 'N/A')}\n"
        f"┃ │ CREDIT: {data.get('credit_score', 'N/A')}\n"
        "┃ └────────────────────┘\n"
        "┃                        \n"
        "┃ ┌─ 🐾 OTHER ────────┐\n"
        f"┃ │ PET  : {data.get('pet_id', 'N/A')}\n"
        f"┃ │ PET LVL: {data.get('pet_level', 'N/A')}\n"
        f"┃ │ GENDER: {data.get('gender', 'N/A')}\n"
        f"┃ │ SIGN : {data.get('signature', 'No Sig')[:15]}...\n"
        "┃ └────────────────────┘\n"
    )
    
    raw_data = data.get('raw', {})
    raw_json = json.dumps(raw_data, indent=2, ensure_ascii=False)
    raw_lines = raw_json.split('\n')
    raw_part = ""
    for line in raw_lines[:12]:
        if len(line) > 35:
            line = line[:35] + "..."
        raw_part += f"┃ {line}\n"
    if len(raw_lines) > 12:
        raw_part += "┃ ...(truncated)\n"
    
    return (
        filtered_info +
        "┃                        \n"
        "┃ ┌─ 📊 RAW DATA ──────┐\n"
        f"{raw_part}"
        "┃ └────────────────────┘\n"
        "┃                        \n"
        "┃ ══════════════════════ \n"
        "┃ 💫 @S.KANHAIYA 💫     \n"
        "┗━━━━━━━━━━━━━━━━━━━━━━┛"
    )

# ============ API FUNCTIONS ============

async def call_visit_api(region, uid):
    url = f"{VISIT_API_URL}{region}/{uid}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=15) as resp:
                if resp.status != 200:
                    return {"error": f"HTTP {resp.status}"}
                return await resp.json()
    except:
        return {"error": "API request failed"}

async def call_like_api(region, uid):
    region_upper = region.upper()
    url = f"{LIKE_API_URL}like?uid={uid}&region={region_upper}&key={API_KEY}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=15) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get('status') == 1:
                        return {
                            "player": data.get('PlayerNickname', 'Unknown'),
                            "uid": data.get('UID', uid),
                            "region": data.get('Region', region_upper),
                            "given": data.get('LikesGivenByAPI', 0),
                            "before": data.get('LikesbeforeCommand', 0),
                            "after": data.get('LikesafterCommand', 0)
                        }
                    else:
                        return {"error": "API returned error"}
                return {"error": f"HTTP {resp.status}"}
    except:
        return {"error": "API request failed"}

async def call_info_api(region, uid):
    url = f"{INFO_API_URL}?region={region}&uid={uid}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=15) as resp:
                if resp.status == 200:
                    raw_data = await resp.json()
                    basic = raw_data.get("BasicInfo") or raw_data.get("basicInfo") or {}
                    social = raw_data.get("socialInfo") or raw_data.get("SocialInfo") or {}
                    credit = raw_data.get("creditScoreInfo") or raw_data.get("CreditScoreInfo") or {}
                    pet = raw_data.get("petInfo") or raw_data.get("PetInfo") or {}
                    
                    create_at_ts = basic.get("createAt") or basic.get("createTime") or 0
                    try:
                        create_at = datetime.fromtimestamp(int(create_at_ts)).strftime('%d-%m-%Y') if create_at_ts else "N/A"
                    except:
                        create_at = "N/A"
                    
                    gender_raw = social.get("gender", "N/A")
                    if "FEMALE" in str(gender_raw).upper():
                        gender = "Female ♀️"
                    elif "MALE" in str(gender_raw).upper():
                        gender = "Male ♂️"
                    else:
                        gender = "N/A"
                    
                    return {
                        "nickname": basic.get("nickname") or basic.get("Nickname") or "Unknown",
                        "uid": basic.get("accountId") or uid,
                        "region": basic.get("region", region.upper()),
                        "level": basic.get("level", "N/A"),
                        "exp": basic.get("exp", "N/A"),
                        "likes": basic.get("liked") or basic.get("Liked") or 0,
                        "account_type": "Google/FB" if basic.get("accountType") == 1 else "Guest/Other",
                        "create_at": create_at,
                        "br_points": basic.get("rankingPoints", "N/A"),
                        "cs_points": basic.get("csRank", "N/A"),
                        "max_rank": basic.get("maxRank", "N/A"),
                        "credit_score": credit.get("creditScore", "N/A"),
                        "pet_id": pet.get("id", "No Pet"),
                        "pet_level": pet.get("level", "N/A"),
                        "gender": gender,
                        "signature": social.get("signature") or "No Signature Set",
                        "raw": raw_data
                    }
                return {"error": f"HTTP {resp.status}"}
    except:
        return {"error": "API request failed"}

# ============ TELEGRAM HANDLERS ============

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📊 Visit", callback_data="help_visit")],
        [InlineKeyboardButton("❤️ Likes", callback_data="help_like")],
        [InlineKeyboardButton("👤 Info", callback_data="help_info")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🌟 *S.KANHAIYA BOT* 🌟\n\n"
        "🔥 *Features:*\n"
        "• 📊 Profile Visit\n"
        "• ❤️ Send Likes\n"
        "• 👤 Player Info\n\n"
        "📌 *Commands:*\n"
        "/start – Show menu\n"
        "/visit `<region>` `<uid>` – Visit\n"
        "/like `<region>` `<uid>` – Likes\n"
        "/info `<region>` `<uid>` – Info\n\n"
        f"⚡ *Powered by @S.KANHAIYA*",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔧 *How to use this bot*\n\n"
        "📊 *Visit:* `/visit IN 123456789`\n"
        "❤️ *Like:* `/like IN 123456789`\n"
        "👤 *Info:* `/info IN 123456789`\n\n"
        "🌍 Regions: IN, BD, PK, USA, BR\n"
        "⚠️ Daily limit: 2 likes\n\n"
        f"⚡ *Powered by @S.KANHAIYA*",
        parse_mode="Markdown"
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        f"📌 *Command Info*\n\n"
        f"Use: `/{query.data.replace('help_', '')} <region> <uid>`\n"
        f"Example: `/{query.data.replace('help_', '')} IN 123456789`",
        parse_mode="Markdown"
    )

async def visit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 2:
        await update.message.reply_text("❌ Use: `/visit IN 123456789`", parse_mode="Markdown")
        return
    
    region = context.args[0].upper()
    try:
        uid = int(context.args[1])
    except ValueError:
        await update.message.reply_text("❌ UID must be a number!", parse_mode="Markdown")
        return
    
    msg = await update.message.reply_text("⏳ *Processing Visit...*", parse_mode="Markdown")
    result = await call_visit_api(region, uid)
    
    if "error" in result:
        await msg.edit_text(f"🚫 *Error:* {result['error']}", parse_mode="Markdown")
        return
    
    result['region'] = region
    await msg.edit_text(format_visit_result(result), parse_mode="Markdown")

async def like(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 2:
        await update.message.reply_text("❌ Use: `/like IN 123456789`", parse_mode="Markdown")
        return
    
    region = context.args[0].upper()
    try:
        uid = int(context.args[1])
    except ValueError:
        await update.message.reply_text("❌ UID must be a number!", parse_mode="Markdown")
        return
    
    user_id = update.effective_user.id
    if not can_user_like(user_id):
        await update.message.reply_text(
            "❌ *Daily limit reached!*\nYou can send 2 likes per day.",
            parse_mode="Markdown"
        )
        return
    
    msg = await update.message.reply_text("⏳ *Processing Like...*", parse_mode="Markdown")
    result = await call_like_api(region, uid)
    
    if "error" in result:
        await msg.edit_text(f"🚫 *Error:* {result['error']}", parse_mode="Markdown")
        return
    
    update_user_like(user_id)
    result['region'] = region
    await msg.edit_text(format_like_result(result), parse_mode="Markdown")

async def info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 2:
        await update.message.reply_text("❌ Use: `/info IN 123456789`", parse_mode="Markdown")
        return
    
    region = context.args[0].upper()
    try:
        uid = int(context.args[1])
    except ValueError:
        await update.message.reply_text("❌ UID must be a number!", parse_mode="Markdown")
        return
    
    msg = await update.message.reply_text("⏳ *Fetching Player Info...*", parse_mode="Markdown")
    result = await call_info_api(region, uid)
    
    if "error" in result:
        await msg.edit_text(f"🚫 *Error:* {result['error']}", parse_mode="Markdown")
        return
    
    final_msg = format_info_result(result)
    if len(final_msg) > 4096:
        await msg.edit_text(final_msg[:2000], parse_mode="Markdown")
        await update.message.reply_text(final_msg[2000:4000], parse_mode="Markdown")
    else:
        await msg.edit_text(final_msg, parse_mode="Markdown")

# ============ TELEGRAM APP SETUP ============
tg_app = Application.builder().token(BOT_TOKEN).build()
tg_app.add_handler(CommandHandler("start", start))
tg_app.add_handler(CommandHandler("help", help_command))
tg_app.add_handler(CommandHandler("visit", visit))
tg_app.add_handler(CommandHandler("like", like))
tg_app.add_handler(CommandHandler("info", info))
tg_app.add_handler(CallbackQueryHandler(button_handler))

# ============ FLASK ROUTES ============

@app.route('/api/webhook', methods=['POST'])
def webhook():
    try:
        data = request.get_json(force=True)
        update = Update.de_json(data, tg_app.bot)
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(tg_app.initialize())
        loop.run_until_complete(tg_app.process_update(update))
        
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/')
def home():
    return "🚀 S.KANHAIYA BOT is running on Vercel!"

@app.route('/health')
def health():
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()})

# ============ FOR VERCEL ============
# Vercel will use this as the entry point

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
