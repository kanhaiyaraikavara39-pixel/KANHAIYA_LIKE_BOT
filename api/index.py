import os
import logging
import aiohttp
import asyncio
import base64
import json
from datetime import date, datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler
from telegram.error import TelegramError
import random
from fastapi import FastAPI, Request, Response

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", 
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ============ BOT & ADMIN CONFIGURATIONS ============
BOT_TOKEN = os.getenv("BOT_TOKEN", "8752690086:AAGEdWri8qtC6vHw2wHDObUmWmoa-hyyh-M")
ADMIN_ID = int(os.getenv("ADMIN_ID", "7890824548"))  # अपनी टेलीग्राम एडमिन आईडी

# ============ API CONFIGURATIONS ============
VISIT_API_URL = "https://kanhaiya-vvvvbvvb.vercel.app/"
LIKE_API_URL = "https://kanhaiya-raikwar.vercel.app/"
ENCODED_KEY = "WkVYWFk="
API_KEY = base64.b64decode(ENCODED_KEY).decode()
INFO_API_URL = "https://s-kanhaiya-ff-info.vercel.app/player-info"

# ============ STATE / IN-MEMORY STORAGE ============
user_limits = {}
user_languages = {}      # {user_id: 'hi' or 'en'}
required_channels = []   # जैसे: ['@YourChannel', '@YourGroup']
daily_limit = 2

# डिफॉल्ट चैनल अगर आप कोड में सेट करना चाहें (उदा: ['@MyChannel'])
DEFAULT_CHANNELS = os.getenv("REQUIRED_CHANNELS", "").split(",")
for ch in DEFAULT_CHANNELS:
    ch = ch.strip()
    if ch and ch not in required_channels:
        required_channels.append(ch)

# ============ MULTI-LANGUAGE STRINGS ============
MESSAGES = {
    "en": {
        "welcome": (
            "🌟 *S.KANHAIYA BOT* 🌟\n\n"
            "🔥 *Features:*\n"
            "• 📊 Profile Visit\n"
            "• ❤️ Send Likes\n"
            "• 👤 Player Info\n"
            "• 🌐 Multi-Language\n\n"
            "📌 *Commands:*\n"
            "/start – Show menu\n"
            "/visit `<region>` `<uid>` – Send visits\n"
            "/like `<region>` `<uid>` – Send likes\n"
            "/info `<region>` `<uid>` – Player details\n"
            "/language – Change language\n\n"
            "⚡ *Powered by @S.KANHAIYA*"
        ),
        "help": (
            "🔧 *How to use this bot*\n\n"
            "📊 *Visit:* `/visit IN 123456789`\n"
            "❤️ *Like:* `/like IN 123456789`\n"
            "👤 *Info:* `/info IN 123456789`\n\n"
            "🌍 *Regions:* IN, BD, PK, USA, BR\n"
            "⚠️ *Daily Limit:* 2 likes\n\n"
            "⚡ *Powered by @S.KANHAIYA*"
        ),
        "force_sub": "⚠️ *Access Denied!*\nPlease join our official channels to unlock the bot features.",
        "verified_success": "✅ *Verification Successful!* You can now use the bot.",
        "verified_fail": "❌ *You have not joined all channels yet!* Please join and try again.",
        "daily_limit": "❌ *Daily limit reached!*\nYou can send 2 likes per day.",
        "invalid_uid": "❌ UID must contain digits only!",
        "usage_visit": "❌ Usage: `/visit IN 123456789`",
        "usage_like": "❌ Usage: `/like IN 123456789`",
        "usage_info": "❌ Usage: `/info IN 123456789`",
        "choose_lang": "🌐 *Choose your preferred language:*",
        "lang_set": "✅ Language changed to English 🇬🇧"
    },
    "hi": {
        "welcome": (
            "🌟 *S.KANHAIYA BOT* 🌟\n\n"
            "🔥 *मुख्य फीचर्स:*\n"
            "• 📊 प्रोफाइल विजिट\n"
            "• ❤️ गेम लाइक्स भेजें\n"
            "• 👤 प्लेयर डिटेल्स निकालें\n"
            "• 🌐 भाषा बदलने की सुविधा\n\n"
            "📌 *कमांड्स:*\n"
            "/start – मेन मेनू देखें\n"
            "/visit `<region>` `<uid>` – विजिट भेजें\n"
            "/like `<region>` `<uid>` – लाइक्स भेजें\n"
            "/info `<region>` `<uid>` – प्लेयर जानकारी\n"
            "/language – भाषा बदलें\n\n"
            "⚡ *Powered by @S.KANHAIYA*"
        ),
        "help": (
            "🔧 *बॉट का उपयोग कैसे करें*\n\n"
            "📊 *विजिट:* `/visit IN 123456789`\n"
            "❤️ *लाइक:* `/like IN 123456789`\n"
            "👤 *इन्फो:* `/info IN 123456789`\n\n"
            "🌍 *रीजन:* IN, BD, PK, USA, BR\n"
            "⚠️ *दैनिक सीमा:* 2 लाइक्स\n\n"
            "⚡ *Powered by @S.KANHAIYA*"
        ),
        "force_sub": "⚠️ *बॉट लॉक है!*\nबॉट के सभी फीचर्स अनलॉक करने के लिए कृपया हमारे चैनल/ग्रुप से जुड़ें।",
        "verified_success": "✅ *सत्यापन सफल रहा!* अब आप बॉट का इस्तेमाल कर सकते हैं।",
        "verified_fail": "❌ *आपने अभी तक सभी चैनल्स जॉइन नहीं किए हैं!* कृपया जॉइन करें और दोबारा वेरीफाई करें।",
        "daily_limit": "❌ *दैनिक सीमा समाप्त!*\nआप प्रतिदिन केवल 2 लाइक्स भेज सकते हैं।",
        "invalid_uid": "❌ UID में केवल संख्या (नंबर) होने चाहिए!",
        "usage_visit": "❌ उपयोग: `/visit IN 123456789`",
        "usage_like": "❌ उपयोग: `/like IN 123456789`",
        "usage_info": "❌ उपयोग: `/info IN 123456789`",
        "choose_lang": "🌐 *अपनी मनपसंद भाषा चुनें:*",
        "lang_set": "✅ भाषा बदलकर हिंदी 🇮🇳 कर दी गई है।"
    }
}

def get_text(user_id, key):
    lang = user_languages.get(user_id, "hi")
    return MESSAGES.get(lang, MESSAGES["hi"]).get(key, "")

# ============ ADMIN ALERT HELPER ============
async def notify_admin(context: ContextTypes.DEFAULT_TYPE, user, command_text):
    """एडमिन को यूजर एक्टिविटी का मैसेज भेजें"""
    if not ADMIN_ID:
        return
    try:
        user_name = user.full_name or "Unknown"
        username = f"@{user.username}" if user.username else "No Username"
        user_id = user.id
        time_now = datetime.now().strftime("%d-%m-%Y %H:%M:%S")

        alert = (
            "🚨 *USER BOT ACTIVITY ALERT* 🚨\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 *नाम:* {user_name}\n"
            f"🔗 *यूज़रनेम:* {username}\n"
            f"🆔 *आईडी:* `{user_id}`\n"
            f"⚡ *कमांड:* `{command_text}`\n"
            f"⏰ *समय:* `{time_now}`\n"
            "━━━━━━━━━━━━━━━━━━━━━"
        )
        await context.bot.send_message(chat_id=ADMIN_ID, text=alert, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Failed to send admin notification: {e}")

# ============ FORCE JOIN LOGIC ============
async def is_user_subscribed(bot, user_id):
    """चेक करें कि यूजर ने सभी अनिवार्य चैनल्स जॉइन किए हैं या नहीं"""
    if user_id == ADMIN_ID:
        return True
    if not required_channels:
        return True
        
    for ch in required_channels:
        try:
            member = await bot.get_chat_member(chat_id=ch, user_id=user_id)
            if member.status in ["left", "kicked"]:
                return False
        except TelegramError as e:
            logger.error(f"Force sub check error for {ch}: {e}")
            # अगर चैनल आईडी गलत है या बॉट एडमिन नहीं है तो यूजर को ब्लॉक न करें
            continue
    return True

def get_force_sub_keyboard(user_id):
    keyboard = []
    for idx, ch in enumerate(required_channels, 1):
        clean_name = ch.replace("@", "")
        url = f"https://t.me/{clean_name}"
        keyboard.append([InlineKeyboardButton(f"📢 Join Channel {idx}", url=url)])
    keyboard.append([InlineKeyboardButton("✅ Verify / अनलॉक करें", callback_data="verify_sub")])
    return InlineKeyboardMarkup(keyboard)

# ============ USER LIMITS ============
def today_str():
    return str(date.today())

def can_user_like(user_id):
    if user_id == ADMIN_ID:
        return True
    t = today_str()
    if user_id not in user_limits or user_limits[user_id]['date'] != t:
        user_limits[user_id] = {'date': t, 'count': 0}
        return True
    return user_limits[user_id]['count'] < daily_limit

def update_user_like(user_id):
    if user_id == ADMIN_ID:
        return
    t = today_str()
    if user_id not in user_limits or user_limits[user_id]['date'] != t:
        user_limits[user_id] = {'date': t, 'count': 0}
    user_limits[user_id]['count'] += 1

# ============ STYLISH ANIMATION SYSTEM ============
ANIMATION_STAGES = [
    ("⚡ Connecting to Server", "▰▱▱▱▱▱▱▱▱▱ 15%"),
    ("🔍 Encrypting Session",  "▰▰▰▱▱▱▱▱▱▱ 35%"),
    ("📡 Fetching Game Data",  "▰▰▰▰▰▱▱▱▱▱ 55%"),
    ("⚙️ Processing Request",  "▰▰▰▰▰▰▰▱▱▱ 75%"),
    ("✨ Finalizing Payload",  "▰▰▰▰▰▰▰▰▰▱ 92%"),
]

async def send_animated_loading(update, context, action):
    """स्टाइलिश लोडिंग मैसेज भेजें और एनिमेट करें"""
    init_stage, init_bar = ANIMATION_STAGES[0]
    box_anim = (
        f"┏━━━━━━━━━━━━━━━━━━━━┓\n"
        f"┃ ✦ *{action.upper()} PROCESS* ✦\n"
        f"┃ {init_stage}...\n"
        f"┃ `{init_bar}`\n"
        f"┗━━━━━━━━━━━━━━━━━━━━┛"
    )
    msg = await update.message.reply_text(box_anim, parse_mode="Markdown")
    
    # 2-3 फ्रेम्स का स्मूथ और फास्ट इन-लाइन अपडेट
    try:
        for stage, bar in ANIMATION_STAGES[1:]:
            await asyncio.sleep(0.4)
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
        f"┃ │ PET  : {data.get('pet_id', 'No Pet')}\n"
        f"┃ │ PET LVL: {data.get('pet_level', 'N/A')}\n"
        f"┃ │ GENDER: {data.get('gender', 'N/A')}\n"
        f"┃ │ SIGN : {data.get('signature', 'No Sig')[:15]}...\n"
        "┃ └────────────────────┘\n"
    )
    
    raw_data = data.get('raw', {})
    raw_json = json.dumps(raw_data, indent=2, ensure_ascii=False)
    
    raw_lines = raw_json.split('\n')
    raw_part = ""
    for line in raw_lines[:15]:
        if len(line) > 35:
            line = line[:35] + "..."
        raw_part += f"┃ {line}\n"
    
    if len(raw_lines) > 15:
        raw_part += "┃ ...(truncated)\n"
    
    final_msg = (
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
    return final_msg

# ============ API CALL FUNCTIONS ============
async def call_visit_api(region, uid):
    url = f"{VISIT_API_URL}{region}/{uid}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=15) as resp:
                if resp.status != 200:
                    try:
                        error_json = await resp.json()
                        return {"error": error_json.get("error", f"HTTP {resp.status}")}
                    except:
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
                    api_status = data.get('status')
                    if api_status == 1:
                        return {
                            "success": True,
                            "player": data.get('PlayerNickname', 'Unknown'),
                            "uid": data.get('UID', uid),
                            "region": data.get('Region', region_upper),
                            "level": data.get('Level', 'N/A'),
                            "given": data.get('LikesGivenByAPI', 0),
                            "before": data.get('LikesbeforeCommand', 0),
                            "after": data.get('LikesafterCommand', 0)
                        }
                    elif api_status == 2:
                        return {"error": "❌ Today's like limit reached for this UID"}
                    else:
                        return {"error": "❌ API returned unknown status"}
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
                    
                    last_login_ts = basic.get("lastLoginAt") or basic.get("lastLogin") or 0
                    create_at_ts = basic.get("createAt") or basic.get("createTime") or 0
                    
                    try:
                        last_login = datetime.fromtimestamp(int(last_login_ts)).strftime('%d-%m-%Y %H:%M') if last_login_ts else "N/A"
                    except:
                        last_login = "N/A"
                    
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
                        "success": True,
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
                        "last_login": last_login,
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
    
    # चेक करें कि यूजर सबस्क्राइब्ड है या नहीं
    if not await is_user_subscribed(context.bot, user.id):
        await update.message.reply_text(
            get_text(user.id, "force_sub"),
            parse_mode="Markdown",
            reply_markup=get_force_sub_keyboard(user.id)
        )
        return

    keyboard = [
        [InlineKeyboardButton("📊 Visit", callback_data="help_visit"), InlineKeyboardButton("❤️ Likes", callback_data="help_like")],
        [InlineKeyboardButton("👤 Info", callback_data="help_info"), InlineKeyboardButton("🌐 Language", callback_data="open_lang_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    welcome_text = get_text(user.id, "welcome")
    await update.message.reply_text(welcome_text, parse_mode="Markdown", reply_markup=reply_markup)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await notify_admin(context, user, "/help")
    
    if not await is_user_subscribed(context.bot, user.id):
        await update.message.reply_text(
            get_text(user.id, "force_sub"),
            parse_mode="Markdown",
            reply_markup=get_force_sub_keyboard(user.id)
        )
        return

    await update.message.reply_text(get_text(user.id, "help"), parse_mode="Markdown")

async def language_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await notify_admin(context, user, "/language")
    
    keyboard = [
        [InlineKeyboardButton("🇮🇳 हिन्दी", callback_data="set_lang_hi")],
        [InlineKeyboardButton("🇬🇧 English", callback_data="set_lang_en")]
    ]
    await update.message.reply_text(
        get_text(user.id, "choose_lang"),
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def visit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    full_cmd = f"/visit {' '.join(context.args)}"
    await notify_admin(context, user, full_cmd)
    
    if not await is_user_subscribed(context.bot, user.id):
        await update.message.reply_text(
            get_text(user.id, "force_sub"),
            parse_mode="Markdown",
            reply_markup=get_force_sub_keyboard(user.id)
        )
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
    final_msg = format_visit_result(result)
    await loading_msg.edit_text(final_msg, parse_mode="Markdown")

async def like(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    full_cmd = f"/like {' '.join(context.args)}"
    await notify_admin(context, user, full_cmd)
    
    if not await is_user_subscribed(context.bot, user.id):
        await update.message.reply_text(
            get_text(user.id, "force_sub"),
            parse_mode="Markdown",
            reply_markup=get_force_sub_keyboard(user.id)
        )
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
    
    user_id = user.id
    if not can_user_like(user_id):
        await update.message.reply_text(get_text(user_id, "daily_limit"), parse_mode="Markdown")
        return
    
    loading_msg = await send_animated_loading(update, context, "Like")
    result = await call_like_api(region, uid)
    
    if "error" in result:
        await loading_msg.edit_text(f"🚫 *Error:* {result['error']}", parse_mode="Markdown")
        return
    
    update_user_like(user_id)
    result['region'] = region
    final_msg = format_like_result(result)
    await loading_msg.edit_text(final_msg, parse_mode="Markdown")

async def info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    full_cmd = f"/info {' '.join(context.args)}"
    await notify_admin(context, user, full_cmd)
    
    if not await is_user_subscribed(context.bot, user.id):
        await update.message.reply_text(
            get_text(user.id, "force_sub"),
            parse_mode="Markdown",
            reply_markup=get_force_sub_keyboard(user.id)
        )
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
        part1 = final_msg[:2000]
        part2 = final_msg[2000:4000]
        await loading_msg.edit_text(part1, parse_mode="Markdown")
        await update.message.reply_text(part2, parse_mode="Markdown")
    else:
        await loading_msg.edit_text(final_msg, parse_mode="Markdown")

# ============ ADMIN EXCLUSIVE COMMANDS ============

async def send_dm_to_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """एडमिन किसी भी यूजर को डायरेक्ट मैसेज भेज सकता है: /send <user_id> <message>"""
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        return

    if len(context.args) < 2:
        await update.message.reply_text("❌ प्रारूप: `/send <USER_ID> <आपका संदेश>`", parse_mode="Markdown")
        return

    target_id = context.args[0]
    message_to_send = " ".join(context.args[1:])

    try:
        target_uid = int(target_id)
        admin_dm = (
            f"📩 *Admin Message / सूचना:*\n\n"
            f"{message_to_send}\n\n"
            f"⚡ *From Management*"
        )
        await context.bot.send_message(chat_id=target_uid, text=admin_dm, parse_mode="Markdown")
        await update.message.reply_text(f"✅ संदेश सफलता से `{target_uid}` को भेज दिया गया!", parse_mode="Markdown")
    except ValueError:
        await update.message.reply_text("❌ अमान्य User ID (केवल संख्या होनी चाहिए)!")
    except Exception as e:
        await update.message.reply_text(f"🚫 संदेश भेजने में विफल: {e}")

async def add_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """एडमिन द्वारा चैनल जोड़ना: /addchannel @channel_username"""
    if update.effective_user.id != ADMIN_ID:
        return
    if not context.args:
        await update.message.reply_text("❌ प्रारूप: `/addchannel @username`", parse_mode="Markdown")
        return
    ch = context.args[0].strip()
    if ch not in required_channels:
        required_channels.append(ch)
        await update.message.reply_text(f"✅ चैनल `{ch}` अनिवार्य लिस्ट में जोड़ दिया गया।", parse_mode="Markdown")
    else:
        await update.message.reply_text(f"⚠️ `{ch}` पहले से लिस्ट में मौजूद है।", parse_mode="Markdown")

async def del_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """एडमिन द्वारा चैनल हटाना: /delchannel @channel_username"""
    if update.effective_user.id != ADMIN_ID:
        return
    if not context.args:
        await update.message.reply_text("❌ प्रारूप: `/delchannel @username`", parse_mode="Markdown")
        return
    ch = context.args[0].strip()
    if ch in required_channels:
        required_channels.remove(ch)
        await update.message.reply_text(f"✅ चैनल `{ch}` अनिवार्य लिस्ट से हटा दिया गया।", parse_mode="Markdown")
    else:
        await update.message.reply_text(f"❌ `{ch}` लिस्ट में नहीं मिला।", parse_mode="Markdown")

async def list_channels(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """अनिवार्य चैनल्स की लिस्ट देखना: /listchannels"""
    if update.effective_user.id != ADMIN_ID:
        return
    if not required_channels:
        await update.message.reply_text("📌 अभी कोई भी अनिवार्य चैनल सेट नहीं है।")
        return
    text = "📢 *अनिवार्य चैनल्स की सूची:*\n\n" + "\n".join([f"• `{c}`" for c in required_channels])
    await update.message.reply_text(text, parse_mode="Markdown")

# ============ CALLBACK QUERY HANDLER ============

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = update.effective_user
    user_id = user.id
    data = query.data
    await query.answer()

    if data == "verify_sub":
        if await is_user_subscribed(context.bot, user_id):
            await query.edit_message_text(get_text(user_id, "verified_success"), parse_mode="Markdown")
            await start(update, context)
        else:
            await query.answer(get_text(user_id, "verified_fail"), show_alert=True)
            
    elif data == "open_lang_menu":
        keyboard = [
            [InlineKeyboardButton("🇮🇳 हिन्दी", callback_data="set_lang_hi")],
            [InlineKeyboardButton("🇬🇧 English", callback_data="set_lang_en")]
        ]
        await query.edit_message_text(
            get_text(user_id, "choose_lang"),
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        
    elif data == "set_lang_hi":
        user_languages[user_id] = "hi"
        await query.edit_message_text(get_text(user_id, "lang_set"), parse_mode="Markdown")
        
    elif data == "set_lang_en":
        user_languages[user_id] = "en"
        await query.edit_message_text(get_text(user_id, "lang_set"), parse_mode="Markdown")
        
    elif data.startswith("help_"):
        cmd = data.replace("help_", "")
        await query.edit_message_text(
            f"📌 *Command Info*\n\n"
            f"Use: `/{cmd} <region> <uid>`\n"
            f"Example: `/{cmd} IN 123456789`",
            parse_mode="Markdown"
        )

# ============ VERCEL FASTAPI WEBHOOK INTEGRATION ============

app = FastAPI()

ptb_application = Application.builder().token(BOT_TOKEN).build()

# यूज़र कमांड्स
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
ptb_application.add_handler(CommandHandler("delchannel", del_channel))
ptb_application.add_handler(CommandHandler("listchannels", list_channels))

# इनलाइन बटन हैंडलर
ptb_application.add_handler(CallbackQueryHandler(button_handler))

@app.on_event("startup")
async def on_startup():
    await ptb_application.initialize()

@app.post("/")
async def process_update(request: Request):
    """Vercel Webhook Endpoint"""
    try:
        req_json = await request.json()
        tg_update = Update.de_json(req_json, ptb_application.bot)
        await ptb_application.process_update(tg_update)
    except Exception as e:
        logger.error(f"Webhook update processing error: {e}")
    return Response(status_code=200)

@app.get("/")
async def index():
    return {"status": "S.Kanhaiya Bot is live and running with enhanced features!"}
