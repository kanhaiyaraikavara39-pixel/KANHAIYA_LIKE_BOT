import os
import logging
import aiohttp
import asyncio
import base64
import json
import random
from datetime import date, datetime
from fastapi import FastAPI, Request, Response
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton
)
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler,
    MessageHandler,
    filters
)
from telegram.error import TelegramError

# ============ LOGGING CONFIGURATION ============
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", 
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ============ CONFIGURATIONS ============
BOT_TOKEN = os.getenv("BOT_TOKEN", "8752690086:AAHTtttHx7RxH3SsyecC2nl-D5nKN-wX-9U")
ADMIN_ID = int(os.getenv("ADMIN_ID", "7890824548"))

# गेम एपीआई
VISIT_API_URL = "https://kanhaiya-vvvvbvvb.vercel.app/"
LIKE_API_URL = "https://kanhaiya-raikwar.vercel.app/"
ENCODED_KEY = "WkVYWFk="
API_KEY = base64.b64decode(ENCODED_KEY).decode()
INFO_API_URL = "https://s-kanhaiya-ff-info.vercel.app/player-info"

# अनिवार्य चैनल और ग्रुप
CHANNEL_USERNAME = "@KANHAIYA_VIP"
GROUP_USERNAME = "@kanhaiyaanjj"
BROADCAST_CHANNEL = "@KANHAIYA_VIP"

# ============ PERSISTENT STORAGE (/tmp/) ============
STORAGE_FILE = "/tmp/kanhaiya_bot_data.json"

def load_storage():
    default_data = {
        "languages": {},       # {user_id: "en" / "hi"}
        "user_limits": {},     # {user_id: {"date": "...", "count": 0}}
        "verified_users": {},  # {user_id: true}  → permanent unlock
        "extra_channels": []   # admin द्वारा जोड़े गए अतिरिक्त चैनल/ग्रुप
    }
    if not os.path.exists(STORAGE_FILE):
        return default_data
    try:
        with open(STORAGE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            # backward compatibility
            if "extra_channels" not in data:
                data["extra_channels"] = []
            if "verified_users" not in data:
                data["verified_users"] = {}
            return data
    except Exception as e:
        logger.error(f"Error loading storage: {e}")
        return default_data

def save_storage(data):
    try:
        with open(STORAGE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Error saving storage: {e}")

# ============ KEYBOARDS (नीचे दिखने वाले बटन) ============
def get_main_reply_keyboard(user_id):
    """कीबोर्ड के नीचे हमेशा दिखने वाले बटन"""
    if user_id == ADMIN_ID:
        kb = [
            [KeyboardButton("📊 Visit"), KeyboardButton("❤️ Like"), KeyboardButton("👤 Info")],
            [KeyboardButton("📢 Broadcast / Send"), KeyboardButton("➕ Add Channel")],
            [KeyboardButton("🌐 Language"), KeyboardButton("📖 Help")]
        ]
    else:
        kb = [
            [KeyboardButton("📊 Visit"), KeyboardButton("❤️ Like")],
            [KeyboardButton("👤 Info"), KeyboardButton("🌐 Language")],
            [KeyboardButton("📖 Help")]
        ]
    return ReplyKeyboardMarkup(kb, resize_keyboard=True)

def get_join_verification_markup(user_id=None):
    """चैनल/ग्रुप लिंक्स और इनलाइन वेरीफाई बटन"""
    keyboard = [
        [InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}")],
        [InlineKeyboardButton("💬 Join Group", url=f"https://t.me/{GROUP_USERNAME.replace('@', '')}")]
    ]
    # अतिरिक्त चैनल्स जोड़ें (अगर एडमिन ने add किए हैं)
    try:
        storage = load_storage()
        for ch in storage.get("extra_channels", []):
            name = ch.get("name", "Channel")
            link = ch.get("link", "")
            if link:
                keyboard.append([InlineKeyboardButton(f"➕ {name}", url=link)])
    except Exception:
        pass

    keyboard.append([InlineKeyboardButton("✅ Verify / अनलॉक करें", callback_data="verify_membership")])
    keyboard.append([InlineKeyboardButton("🌐 Change Language", callback_data="open_lang_menu")])
    return InlineKeyboardMarkup(keyboard)

# ============ MULTI-LANGUAGE SYSTEM ============
MESSAGES = {
    "en": {
        "welcome": (
            "┏━━━━━━━━━━━━━━━━━━━━━━┓\n"
            "┃ ╔════════════════════╗ \n"
            "┃ ║ ✦ S.KANHAIYA BOT ✦║\n"
            "┃ ║ 🎮 MAIN MENU 🎮    ║\n"
            "┃ ╚════════════════════╝ \n"
            "┃                        \n"
            "┃ 🔥 *Active Features:*\n"
            "┃ • 📊 Profile Visit\n"
            "┃ • ❤️ Send Likes\n"
            "┃ • 👤 Player Info\n"
            "┃ • 🌐 Language Switch\n"
            "┃                        \n"
            "┃ 📌 *How to use:*\n"
            "┃ Use the buttons below or send:\n"
            "┃ `/visit <region> <uid>`\n"
            "┃ `/like <region> <uid>`\n"
            "┃ `/info <region> <uid>`\n"
            "┃                        \n"
            "┃ ══════════════════════ \n"
            "┃ 💫 @KANHAIYA_VIP 💫   \n"
            "┗━━━━━━━━━━━━━━━━━━━━━━┛"
        ),
        "help": (
            "🔧 *Command Guide:*\n\n"
            "📊 *Visit:* `/visit IN 123456789`\n"
            "❤️ *Like:* `/like IN 123456789`\n"
            "👤 *Info:* `/info IN 123456789`\n\n"
            "🌍 *Regions:* IN, BD, PK, USA, BR\n"
            "⚠️ *Daily Limit:* 2 likes\n\n"
            "⚡ *Powered by @KANHAIYA_VIP*"
        ),
        "lock_msg": (
            "🔒 *BOT ACCESS LOCKED!*\n\n"
            "To unlock the bot:\n"
            "1. Join our Official Channel and Group below.\n"
            "2. Tap the **✅ Verify** button to unlock instantly!\n"
            "_(No password needed — one-time verification)_"
        ),
        "verified_success": "🎉 *Authentication Successful!*\nBot unlocked permanently. Enjoy all features!",
        "join_both_first": "⚠️ *Please join both the Channel and Group first!*",
        "daily_limit": "❌ *Daily limit reached!*\nYou can send up to 2 likes per day.",
        "invalid_uid": "❌ UID must contain numbers only!",
        "usage_visit": "❌ Usage: `/visit IN 123456789`",
        "usage_like": "❌ Usage: `/like IN 123456789`",
        "usage_info": "❌ Usage: `/info IN 123456789`",
        "choose_lang": "🌐 *Choose your preferred language:*",
        "lang_set": "✅ Language set to **English 🇬🇧**."
    },
    "hi": {
        "welcome": (
            "┏━━━━━━━━━━━━━━━━━━━━━━┓\n"
            "┃ ╔════════════════════╗ \n"
            "┃ ║ ✦ S.KANHAIYA BOT ✦║\n"
            "┃ ║ 🎮 मुख्य मेनू 🎮   ║\n"
            "┃ ╚════════════════════╝ \n"
            "┃                        \n"
            "┃ 🔥 *सक्रिय फीचर्स:*\n"
            "┃ • 📊 प्रोफाइल विजिट\n"
            "┃ • ❤️ गेम लाइक्स भेजें\n"
            "┃ • 👤 प्लेयर विवरण निकालें\n"
            "┃ • 🌐 भाषा बदलने का विकल्प\n"
            "┃                        \n"
            "┃ 📌 *उपयोग कैसे करें:*\n"
            "┃ नीचे दिए कीबोर्ड बटन दबाएं या लिखें:\n"
            "┃ `/visit <region> <uid>`\n"
            "┃ `/like <region> <uid>`\n"
            "┃ `/info <region> <uid>`\n"
            "┃                        \n"
            "┃ ══════════════════════ \n"
            "┃ 💫 @KANHAIYA_VIP 💫   \n"
            "┗━━━━━━━━━━━━━━━━━━━━━━┛"
        ),
        "help": (
            "🔧 *कमांड उपयोग निर्देश:*\n\n"
            "📊 *विजिट:* `/visit IN 123456789`\n"
            "❤️ *लाइक:* `/like IN 123456789`\n"
            "👤 *इन्फो:* `/info IN 123456789`\n\n"
            "🌍 *रीजन:* IN, BD, PK, USA, BR\n"
            "⚠️ *दैनिक सीमा:* 2 लाइक्स\n\n"
            "⚡ *Powered by @KANHAIYA_VIP*"
        ),
        "lock_msg": (
            "🔒 *बॉट लॉक है!*\n\n"
            "बॉट अनलॉक करने के लिए:\n"
            "1. नीचे दिए गए चैनल और ग्रुप दोनों जॉइन करें।\n"
            "2. **✅ Verify** बटन दबाएं — तुरंत अनलॉक हो जाएगा!\n"
            "_(कोई पासवर्ड नहीं चाहिए — एक बार वेरीफाई, हमेशा अनलॉक)_"
        ),
        "verified_success": "🎉 *सत्यापन सफल रहा!*\nबॉट हमेशा के लिए अनलॉक हो गया है।",
        "join_both_first": "⚠️ *कृपया पहले चैनल और ग्रुप दोनों जॉइन करें!*",
        "daily_limit": "❌ *दैनिक सीमा समाप्त!*\nआप प्रतिदिन केवल 2 लाइक्स भेज सकते हैं।",
        "invalid_uid": "❌ UID में केवल संख्या होनी चाहिए!",
        "usage_visit": "❌ उपयोग: `/visit IN 123456789`",
        "usage_like": "❌ उपयोग: `/like IN 123456789`",
        "usage_info": "❌ उपयोग: `/info IN 123456789`",
        "choose_lang": "🌐 *अपनी पसंदीदा भाषा चुनें:*",
        "lang_set": "✅ आपकी भाषा **हिंदी 🇮🇳** सेट कर दी गई है।"
    }
}

def get_user_lang(user_id):
    storage = load_storage()
    return storage["languages"].get(str(user_id), "hi")

def set_user_lang(user_id, lang):
    storage = load_storage()
    storage["languages"][str(user_id)] = lang
    save_storage(storage)

def get_text(user_id, key):
    lang = get_user_lang(user_id)
    return MESSAGES.get(lang, MESSAGES["hi"]).get(key, "")

# ============ VERIFICATION HELPERS ============
async def is_member_of_all(bot, user_id):
    if user_id == ADMIN_ID:
        return True
    # मुख्य चैनल + ग्रुप + अतिरिक्त चैनल्स
    check_list = [CHANNEL_USERNAME, GROUP_USERNAME]
    try:
        storage = load_storage()
        for ch in storage.get("extra_channels", []):
            uname = ch.get("username")
            if uname:
                check_list.append(uname)
    except Exception:
        pass

    for ch in check_list:
        try:
            member = await bot.get_chat_member(chat_id=ch, user_id=user_id)
            if member.status in ["left", "kicked"]:
                return False
        except TelegramError:
            continue
    return True

def is_user_unlocked(user_id):
    if user_id == ADMIN_ID:
        return True
    storage = load_storage()
    return bool(storage["verified_users"].get(str(user_id)))

def unlock_user(user_id):
    storage = load_storage()
    storage["verified_users"][str(user_id)] = True
    save_storage(storage)

# ============ ADMIN ACTIVITY ALERT ============
async def notify_admin(context: ContextTypes.DEFAULT_TYPE, user, command_text):
    if not ADMIN_ID or user.id == ADMIN_ID:
        return
    try:
        user_name = user.full_name or "Unknown"
        username = f"@{user.username}" if user.username else "No Username"
        time_now = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
        
        alert = (
            "🚨 *USER BOT ACTIVITY ALERT* 🚨\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 *Name:* {user_name}\n"
            f"🔗 *Username:* {username}\n"
            f"🆔 *ID:* `{user.id}`\n"
            f"⚡ *Action:* `{command_text}`\n"
            f"⏰ *Time:* `{time_now}`\n"
            "━━━━━━━━━━━━━━━━━━━━━"
        )
        await context.bot.send_message(chat_id=ADMIN_ID, text=alert, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Admin notify error: {e}")

# ============ USER LIMITS ============
def can_user_like(user_id):
    if user_id == ADMIN_ID:
        return True
    storage = load_storage()
    today = str(date.today())
    uid = str(user_id)
    user_data = storage["user_limits"].get(uid, {"date": today, "count": 0})
    if user_data["date"] != today:
        return True
    return user_data["count"] < 2

def update_user_like(user_id):
    if user_id == ADMIN_ID:
        return
    storage = load_storage()
    today = str(date.today())
    uid = str(user_id)
    if uid not in storage["user_limits"] or storage["user_limits"][uid]["date"] != today:
        storage["user_limits"][uid] = {"date": today, "count": 0}
    storage["user_limits"][uid]["count"] += 1
    save_storage(storage)

# ============ STYLISH ANIMATION SYSTEM ============
ANIMATION_STAGES = [
    ("⚡ Connecting Server", "▰▱▱▱▱▱▱▱▱▱ 20%"),
    ("🔍 Encrypting Session", "▰▰▰▰▱▱▱▱▱▱ 45%"),
    ("📡 Querying Game API", "▰▰▰▰▰▰▱▱▱▱ 65%"),
    ("✨ Finalizing Response", "▰▰▰▰▰▰▰▰▰▱ 90%")
]

async def send_animated_loading(update, context, action):
    init_stage, init_bar = ANIMATION_STAGES[0]
    box_anim = (
        f"┏━━━━━━━━━━━━━━━━━━━━┓\n"
        f"┃ ✦ *{action.upper()} PROCESS* ✦\n"
        f"┃ {init_stage}...\n"
        f"┃ `{init_bar}`\n"
        f"┗━━━━━━━━━━━━━━━━━━━━┛"
    )
    msg = await update.message.reply_text(box_anim, parse_mode="Markdown")
    try:
        for stage, bar in ANIMATION_STAGES[1:]:
            await asyncio.sleep(0.35)
            updated_box = (
                f"┏━━━━━━━━━━━━━━━━━━━━┓\n"
                f"┃ ✦ *{action.upper()} PROCESS* ✦\n"
                f"┃ {stage}...\n"
                f"┃ `{bar}`\n"
                f"┗━━━━━━━━━━━━━━━━━━━━┛"
            )
            await msg.edit_text(updated_box, parse_mode="Markdown")
    except Exception:
        pass
    return msg

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
        "┃ 💫 @KANHAIYA_VIP 💫   \n"
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
        "┃ 💫 @KANHAIYA_VIP 💫   \n"
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
        f"┃ │ PET  : {data.get('pet_id', 'No Pet')}\n"
        f"┃ │ PET LVL: {data.get('pet_level', 'N/A')}\n"
        f"┃ │ GENDER: {data.get('gender', 'N/A')}\n"
        f"┃ │ SIGN : {data.get('signature', 'No Sig')[:15]}...\n"
        "┃ └────────────────────┘\n"
    )
    raw_lines = json.dumps(data.get('raw', {}), indent=2, ensure_ascii=False).split('\n')
    raw_part = "".join([f"┃ {line[:35]}...\n" if len(line) > 35 else f"┃ {line}\n" for line in raw_lines[:15]])
    if len(raw_lines) > 15:
        raw_part += "┃ ...(truncated)\n"
    return (
        filtered_info +
        "┃                        \n"
        "┃ ┌─ 📊 RAW DATA ──────┐\n"
        f"{raw_part}"
        "┃ └────────────────────┘\n"
        "┃                        \n"
        "┃ ══════════════════════ \n"
        "┃ 💫 @KANHAIYA_VIP 💫   \n"
        "┗━━━━━━━━━━━━━━━━━━━━━━┛"
    )

# ============ API CALLS ============
async def call_visit_api(region, uid):
    url = f"{VISIT_API_URL}{region}/{uid}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=15) as resp:
                if resp.status != 200:
                    return {"error": f"HTTP {resp.status}"}
                return await resp.json()
    except asyncio.TimeoutError:
        return {"error": "⏰ API request timed out"}
    except Exception as e:
        return {"error": f"❌ Error: {str(e)}"}

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
                            "success": True,
                            "player": data.get('PlayerNickname', 'Unknown'),
                            "uid": data.get('UID', uid),
                            "region": data.get('Region', region_upper),
                            "given": data.get('LikesGivenByAPI', 0),
                            "before": data.get('LikesbeforeCommand', 0),
                            "after": data.get('LikesafterCommand', 0)
                        }
                    elif data.get('status') == 2:
                        return {"error": "❌ Daily limit reached for this UID"}
                    return {"error": "❌ Unknown API response status"}
                return {"error": f"HTTP {resp.status}"}
    except Exception as e:
        return {"error": f"❌ Error: {str(e)}"}

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

                    gender_raw = social.get("gender", "N/A")
                    gender = "Female ♀️" if "FEMALE" in str(gender_raw).upper() else ("Male ♂️" if "MALE" in str(gender_raw).upper() else "N/A")
                    
                    return {
                        "success": True,
                        "nickname": basic.get("nickname") or basic.get("Nickname") or "Unknown",
                        "uid": basic.get("accountId") or uid,
                        "region": basic.get("region", region.upper()),
                        "level": basic.get("level", "N/A"),
                        "exp": basic.get("exp", "N/A"),
                        "likes": basic.get("liked") or basic.get("Liked") or 0,
                        "account_type": "Google/FB" if basic.get("accountType") == 1 else "Guest/Other",
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
    except Exception as e:
        return {"error": f"❌ Error: {str(e)}"}

# ============ TELEGRAM COMMAND HANDLERS ============
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await notify_admin(context, user, "/start")

    # यदि यूज़र अनलॉक्ड नहीं है
    if not is_user_unlocked(user.id):
        await update.message.reply_text(
            get_text(user.id, "lock_msg"),
            parse_mode="Markdown",
            reply_markup=get_join_verification_markup(user.id)
        )
        return

    welcome_text = get_text(user.id, "welcome")
    await update.message.reply_text(
        welcome_text,
        parse_mode="Markdown",
        reply_markup=get_main_reply_keyboard(user.id)
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await notify_admin(context, user, "/help")
    if not is_user_unlocked(user.id):
        await update.message.reply_text(get_text(user.id, "lock_msg"), parse_mode="Markdown", reply_markup=get_join_verification_markup(user.id))
        return
    await update.message.reply_text(get_text(user.id, "help"), parse_mode="Markdown", reply_markup=get_main_reply_keyboard(user.id))

async def language_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await notify_admin(context, user, "/language")
    keyboard = [
        [InlineKeyboardButton("🇮🇳 हिन्दी", callback_data="set_lang_hi")],
        [InlineKeyboardButton("🇬🇧 English", callback_data="set_lang_en")]
    ]
    await update.message.reply_text(get_text(user.id, "choose_lang"), reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def visit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await notify_admin(context, user, f"/visit {' '.join(context.args)}")
    
    if not is_user_unlocked(user.id):
        await update.message.reply_text(get_text(user.id, "lock_msg"), parse_mode="Markdown", reply_markup=get_join_verification_markup(user.id))
        return

    if len(context.args) != 2:
        await update.message.reply_text(get_text(user.id, "usage_visit"), parse_mode="Markdown")
        return
    region = context.args[0].upper()
    try:
        uid = int(context.args[1])
    except ValueError:
        await update.message.reply_text(get_text(user.id, "invalid_uid"), parse_mode="Markdown")
        return

    loading_msg = await send_animated_loading(update, context, "Visit")
    result = await call_visit_api(region, uid)
    if "error" in result:
        await loading_msg.edit_text(f"🚫 *Error:* {result['error']}", parse_mode="Markdown")
        return
    result['region'] = region
    await loading_msg.edit_text(format_visit_result(result), parse_mode="Markdown")

async def like(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await notify_admin(context, user, f"/like {' '.join(context.args)}")

    if not is_user_unlocked(user.id):
        await update.message.reply_text(get_text(user.id, "lock_msg"), parse_mode="Markdown", reply_markup=get_join_verification_markup(user.id))
        return

    if len(context.args) != 2:
        await update.message.reply_text(get_text(user.id, "usage_like"), parse_mode="Markdown")
        return
    region = context.args[0].upper()
    try:
        uid = int(context.args[1])
    except ValueError:
        await update.message.reply_text(get_text(user.id, "invalid_uid"), parse_mode="Markdown")
        return

    if not can_user_like(user.id):
        await update.message.reply_text(get_text(user.id, "daily_limit"), parse_mode="Markdown")
        return

    loading_msg = await send_animated_loading(update, context, "Like")
    result = await call_like_api(region, uid)
    if "error" in result:
        await loading_msg.edit_text(f"🚫 *Error:* {result['error']}", parse_mode="Markdown")
        return

    update_user_like(user.id)
    result['region'] = region
    await loading_msg.edit_text(format_like_result(result), parse_mode="Markdown")

async def info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await notify_admin(context, user, f"/info {' '.join(context.args)}")

    if not is_user_unlocked(user.id):
        await update.message.reply_text(get_text(user.id, "lock_msg"), parse_mode="Markdown", reply_markup=get_join_verification_markup(user.id))
        return

    if len(context.args) != 2:
        await update.message.reply_text(get_text(user.id, "usage_info"), parse_mode="Markdown")
        return
    region = context.args[0].upper()
    try:
        uid = int(context.args[1])
    except ValueError:
        await update.message.reply_text(get_text(user.id, "invalid_uid"), parse_mode="Markdown")
        return

    loading_msg = await send_animated_loading(update, context, "Info")
    result = await call_info_api(region, uid)
    if "error" in result:
        await loading_msg.edit_text(f"🚫 *Error:* {result['error']}", parse_mode="Markdown")
        return

    final_msg = format_info_result(result)
    if len(final_msg) > 4096:
        await loading_msg.edit_text(final_msg[:2000], parse_mode="Markdown")
        await update.message.reply_text(final_msg[2000:4000], parse_mode="Markdown")
    else:
        await loading_msg.edit_text(final_msg, parse_mode="Markdown")

# ============ TEXT & BUTTON INPUT HANDLER ============
async def handle_user_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """कीबोर्ड बटन क्लिक या सामान्य टेक्स्ट को प्रोसेस करें"""
    user = update.effective_user
    text = update.message.text.strip()

    # 1. कीबोर्ड बटन्स का रिस्पॉन्स
    if text in ["📊 Visit", "/visit"]:
        await update.message.reply_text(get_text(user.id, "usage_visit"), parse_mode="Markdown")
        return
    elif text in ["❤️ Like", "/like"]:
        await update.message.reply_text(get_text(user.id, "usage_like"), parse_mode="Markdown")
        return
    elif text in ["👤 Info", "/info"]:
        await update.message.reply_text(get_text(user.id, "usage_info"), parse_mode="Markdown")
        return
    elif text in ["🌐 Language", "/language"]:
        await language_command(update, context)
        return
    elif text in ["📖 Help", "/help"]:
        await help_command(update, context)
        return
    elif text == "📢 Broadcast / Send" and user.id == ADMIN_ID:
        await update.message.reply_text(
            "📌 *Admin Broadcast Guide:*\n\n"
            "• किसी यूजर को DM: `/send <USER_ID> <message>`\n"
            "• किसी यूजर को मैसेज: `/msg <USER_ID> <message>`",
            parse_mode="Markdown"
        )
        return
    elif text == "➕ Add Channel" and user.id == ADMIN_ID:
        await update.message.reply_text(
            "📌 *Add Channel/Group Guide:*\n\n"
            "फॉर्मेट: `/addchannel <username> <Display Name> <invite_link>`\n\n"
            "उदाहरण:\n"
            "`/addchannel @mynewchannel MyChannel https://t.me/mynewchannel`\n\n"
            "• Bot को उस channel/group में admin बनाना ज़रूरी है।\n"
            "• हटाने के लिए: `/removechannel <username>`",
            parse_mode="Markdown"
        )
        return

    # 2. अगर यूजर पहले से अनलॉक है तो सामान्य टेक्स्ट पर कुछ न करें
    if is_user_unlocked(user.id):
        return

    # 3. अनलॉक नहीं है → उसे verify करने की सलाह दें
    await update.message.reply_text(
        get_text(user.id, "lock_msg"),
        parse_mode="Markdown",
        reply_markup=get_join_verification_markup(user.id)
    )

# ============ ADMIN EXCLUSIVE COMMANDS ============
async def send_dm_to_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """एडमिन द्वारा किसी यूजर को मैसेज भेजना: /send <user_id> <message>"""
    if update.effective_user.id != ADMIN_ID:
        return
    if len(context.args) < 2:
        await update.message.reply_text("❌ Use: `/send <USER_ID> <message>`", parse_mode="Markdown")
        return
    target_id = context.args[0]
    msg = " ".join(context.args[1:])
    try:
        await context.bot.send_message(
            chat_id=int(target_id),
            text=f"📩 *Admin Notification:*\n\n{msg}\n\n⚡ *From @KANHAIYA_VIP Management*",
            parse_mode="Markdown"
        )
        await update.message.reply_text(f"✅ Message delivered to `{target_id}`", parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"🚫 Failed to send: {e}")

async def add_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """एडमिन द्वारा नया चैनल/ग्रुप जोड़ना: /addchannel <username> <Display Name> <invite_link>"""
    if update.effective_user.id != ADMIN_ID:
        return
    if len(context.args) < 3:
        await update.message.reply_text(
            "❌ Use: `/addchannel @username DisplayName https://t.me/link`",
            parse_mode="Markdown"
        )
        return

    username = context.args[0]
    if not username.startswith("@"):
        username = "@" + username
    display_name = context.args[1]
    link = context.args[2]

    storage = load_storage()
    # duplicate check
    for ch in storage["extra_channels"]:
        if ch.get("username", "").lower() == username.lower():
            await update.message.reply_text(f"⚠️ `{username}` पहले से मौजूद है।", parse_mode="Markdown")
            return

    storage["extra_channels"].append({
        "username": username,
        "name": display_name,
        "link": link
    })
    save_storage(storage)

    # bot admin है या नहीं verify करने की कोशिश
    warn = ""
    try:
        chat = await context.bot.get_chat(username)
        bot_member = await context.bot.get_chat_member(chat.id, context.bot.id)
        if bot_member.status not in ["administrator", "creator"]:
            warn = "\n\n⚠️ *Warning:* Bot इस चैनल/ग्रुप का admin नहीं है। कृपया bot को admin बनाएं, वरना verify fail होगा।"
    except TelegramError:
        warn = "\n\n⚠️ *Warning:* Bot इस चैनल/ग्रुप को access नहीं कर पा रहा। कृपया bot को जोड़कर admin बनाएं।"

    await update.message.reply_text(
        f"✅ *Channel/Group जोड़ा गया:*\n\n"
        f"• Username: `{username}`\n"
        f"• Name: `{display_name}`\n"
        f"• Link: {link}{warn}",
        parse_mode="Markdown"
    )

async def remove_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """एडमिन द्वारा चैनल/ग्रुप हटाना: /removechannel @username"""
    if update.effective_user.id != ADMIN_ID:
        return
    if len(context.args) < 1:
        await update.message.reply_text("❌ Use: `/removechannel @username`", parse_mode="Markdown")
        return

    username = context.args[0]
    if not username.startswith("@"):
        username = "@" + username

    storage = load_storage()
    before = len(storage["extra_channels"])
    storage["extra_channels"] = [
        ch for ch in storage["extra_channels"]
        if ch.get("username", "").lower() != username.lower()
    ]
    save_storage(storage)

    if len(storage["extra_channels"]) < before:
        await update.message.reply_text(f"✅ `{username}` हटा दिया गया।", parse_mode="Markdown")
    else:
        await update.message.reply_text(f"⚠️ `{username}` सूची में नहीं मिला।", parse_mode="Markdown")

async def list_channels(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """एडमिन द्वारा सभी चैनल देखना: /channels"""
    if update.effective_user.id != ADMIN_ID:
        return
    storage = load_storage()
    lines = [
        "*📋 Required Channels/Groups:*\n",
        f"• `{CHANNEL_USERNAME}` (Main Channel)",
        f"• `{GROUP_USERNAME}` (Main Group)",
        ""
    ]
    extra = storage.get("extra_channels", [])
    if extra:
        lines.append("*➕ Extra Channels/Groups:*")
        for ch in extra:
            lines.append(f"• `{ch.get('username')}` — {ch.get('name')}")
    else:
        lines.append("_कोई अतिरिक्त चैनल/ग्रुप नहीं जोड़ा गया।_")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

# ============ CALLBACK QUERY HANDLER ============
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = update.effective_user
    user_id = user.id
    data = query.data
    await query.answer()

    if data == "verify_membership":
        # चैनल और ग्रुप की सदस्यता चेक करें
        if not await is_member_of_all(context.bot, user_id):
            await query.answer(get_text(user_id, "join_both_first"), show_alert=True)
            return

        # ✅ सीधे अनलॉक कर दें (permanent, no daily re-verify)
        unlock_user(user_id)
        await notify_admin(context, user, "✅ Verified & Unlocked")

        # Confirm message
        try:
            await query.edit_message_text(
                get_text(user_id, "verified_success"),
                parse_mode="Markdown"
            )
        except Exception:
            pass

        # फिर main menu भेजें
        await context.bot.send_message(
            chat_id=user_id,
            text=get_text(user_id, "welcome"),
            parse_mode="Markdown",
            reply_markup=get_main_reply_keyboard(user_id)
        )

    elif data == "open_lang_menu":
        keyboard = [
            [InlineKeyboardButton("🇮🇳 हिन्दी", callback_data="set_lang_hi")],
            [InlineKeyboardButton("🇬🇧 English", callback_data="set_lang_en")]
        ]
        await query.edit_message_text(get_text(user_id, "choose_lang"), reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data == "set_lang_hi":
        set_user_lang(user_id, "hi")
        await query.edit_message_text(get_text(user_id, "lang_set"), parse_mode="Markdown")
        await start(update, context)

    elif data == "set_lang_en":
        set_user_lang(user_id, "en")
        await query.edit_message_text(get_text(user_id, "lang_set"), parse_mode="Markdown")
        await start(update, context)

# ============ VERCEL FASTAPI INTEGRATION ============
app = FastAPI()
ptb_application = Application.builder().token(BOT_TOKEN).build()

# कमांड्स
ptb_application.add_handler(CommandHandler("start", start))
ptb_application.add_handler(CommandHandler("help", help_command))
ptb_application.add_handler(CommandHandler("language", language_command))
ptb_application.add_handler(CommandHandler("visit", visit))
ptb_application.add_handler(CommandHandler("like", like))
ptb_application.add_handler(CommandHandler("info", info))

# एडमिन कमांड्स
ptb_application.add_handler(CommandHandler("send", send_dm_to_user))
ptb_application.add_handler(CommandHandler("msg", send_dm_to_user))
ptb_application.add_handler(CommandHandler("addchannel", add_channel))
ptb_application.add_handler(CommandHandler("removechannel", remove_channel))
ptb_application.add_handler(CommandHandler("channels", list_channels))

# इनलाइन व टेक्स्ट मैसेज हैंडलर्स
ptb_application.add_handler(CallbackQueryHandler(button_handler))
ptb_application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_user_text_message))

@app.on_event("startup")
async def on_startup():
    await ptb_application.initialize()

@app.post("/")
async def process_update(request: Request):
    try:
        req_json = await request.json()
        tg_update = Update.de_json(req_json, ptb_application.bot)
        await ptb_application.process_update(tg_update)
    except Exception as e:
        logger.error(f"Webhook update processing error: {e}")
    return Response(status_code=200)

@app.get("/")
async def index():
    return {"status": "S.Kanhaiya Bot is running smoothly on Vercel!"}