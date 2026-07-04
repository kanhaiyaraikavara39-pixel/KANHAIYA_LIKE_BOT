import os
import logging
import aiohttp
import asyncio
import base64
import json
from datetime import date, datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler
import random
from fastapi import FastAPI, Request, Response

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", 
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Bot token
BOT_TOKEN = os.getenv("BOT_TOKEN", "8752690086:AAGEdWri8qtC6vHw2wHDObUmWmoa-hyyh-M")

# ============ API CONFIGURATIONS ============
VISIT_API_URL = "https://kanhaiya-vvvvbvvb.vercel.app/"
LIKE_API_URL = "https://kanhaiya-raikwar.vercel.app/"
ENCODED_KEY = "WkVYWFk="
API_KEY = base64.b64decode(ENCODED_KEY).decode()
INFO_API_URL = "https://s-kanhaiya-ff-info.vercel.app/player-info"

# ============ USER LIMITS ============
user_limits = {}
daily_limit = 2

def today_str():
    return str(date.today())

def can_user_like(user_id):
    t = today_str()
    if user_id not in user_limits or user_limits[user_id]['date'] != t:
        user_limits[user_id] = {'date': t, 'count': 0}
        return True
    return user_limits[user_id]['count'] < daily_limit

def update_user_like(user_id):
    t = today_str()
    if user_id not in user_limits or user_limits[user_id]['date'] != t:
        user_limits[user_id] = {'date': t, 'count': 0}
    user_limits[user_id]['count'] += 1

# ============ ANIMATION ============
LOADING_EMOJIS = ["⚡", "✨", "🌟", "💫", "🔥", "⭐"]
LOADING_FRAMES = [
    "🔄 Initializing...",
    "⏳ Connecting to API...",
    "⚡ Fetching Data...",
    "🌟 Processing...",
    "✨ Almost Done...",
    "💫 Finalizing..."
]

async def send_animated_loading(update, context, action):
    """Send animated loading message"""
    msg = await update.message.reply_text(
        f"⚡ *Processing {action}...*\n\n"
        "```\n████░░░░░░░░  20%\n```\n"
        "🔄 Initializing...",
        parse_mode="Markdown"
    )
    
    context.user_data['loading_msg_id'] = msg.message_id
    context.user_data['chat_id'] = update.effective_chat.id
    context.user_data['is_animating'] = True
    context.user_data['animation_index'] = 0
    
    if context.job_queue:
        if 'animation_job' in context.user_data:
            try:
                context.user_data['animation_job'].schedule_removal()
            except:
                pass
        
        job = context.job_queue.run_repeating(
            animate_loading,
            interval=0.6,
            first=0.3,
            data={'chat_id': update.effective_chat.id}
        )
        context.user_data['animation_job'] = job
    
    return msg

async def animate_loading(context):
    """Animate loading"""
    try:
        if not context.job or not context.job.data:
            return
        
        chat_id = context.job.data.get('chat_id')
        if not chat_id or not context.user_data.get('is_animating', False):
            return
        
        msg_id = context.user_data.get('loading_msg_id')
        if not msg_id:
            return
        
        idx = context.user_data.get('animation_index', 0)
        progress = min(20 + (idx % 7) * 10, 90)
        filled = int(progress / 10)
        bar = "█" * filled + "░" * (10 - filled)
        
        status = LOADING_FRAMES[idx % len(LOADING_FRAMES)]
        emoji = random.choice(LOADING_EMOJIS)
        
        loading_text = (
            f"{emoji} *Processing...*\n\n"
            f"```\n{bar}\n```\n"
            f"{status}\n"
            f"*Progress:* {progress}%"
        )
        
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=msg_id,
            text=loading_text,
            parse_mode="Markdown"
        )
        
        context.user_data['animation_index'] = idx + 1
        
    except Exception as e:
        logger.error(f"Animation error: {e}")

async def stop_animation(context):
    """Stop animation"""
    context.user_data['is_animating'] = False
    if 'animation_job' in context.user_data:
        try:
            context.user_data['animation_job'].schedule_removal()
            del context.user_data['animation_job']
        except:
            pass

# ============ FORMAT FUNCTIONS ============

def format_like_result(data):
    """Format like result in S.KANHAIYA style - Small Box"""
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
    """Format visit result in S.KANHAIYA style - Small Box"""
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
    """Format info result with filtered + raw data - Small Box"""
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

# ============ API FUNCTIONS ============

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

# ============ TELEGRAM COMMANDS ============

async def start(update, context):
    keyboard = [
        [InlineKeyboardButton("📊 Visit", callback_data="help_visit")],
        [InlineKeyboardButton("❤️ Likes", callback_data="help_like")],
        [InlineKeyboardButton("👤 Info", callback_data="help_info")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    welcome = (
        "🌟 *S.KANHAIYA BOT* 🌟\n\n"
        "🔥 *Features:*\n"
        "• 📊 Profile Visit\n"
        "• ❤️ Send Likes\n"
        "• 👤 Player Info\n"
        "• ✨ Animated Loading\n\n"
        "📌 *Commands:*\n"
        "/start – Show menu\n"
        "/visit `<region>` `<uid>` – Visit\n"
        "/like `<region>` `<uid>` – Likes\n"
        "/info `<region>` `<uid>` – Info\n\n"
        f"⚡ *Powered by @S.KANHAIYA*"
    )
    await update.message.reply_text(welcome, parse_mode="Markdown", reply_markup=reply_markup)

async def help_command(update, context):
    help_text = (
        "🔧 *How to use this bot*\n\n"
        "📊 *Visit:* `/visit IN 123456789`\n"
        "❤️ *Like:* `/like IN 123456789`\n"
        "👤 *Info:* `/info IN 123456789`\n\n"
        "🌍 Regions: IN, BD, PK, USA, BR\n"
        "⚠️ Daily limit: 2 likes\n\n"
        f"⚡ *Powered by @S.KANHAIYA*"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")

async def button_handler(update, context):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        f"📌 *Command Info*\n\n"
        f"Use: `/{query.data.replace('help_', '')} <region> <uid>`\n"
        f"Example: `/{query.data.replace('help_', '')} IN 123456789`",
        parse_mode="Markdown"
    )

# ============ COMMAND HANDLERS ============

async def visit(update, context):
    if len(context.args) != 2:
        await update.message.reply_text("❌ Use: `/visit IN 123456789`", parse_mode="Markdown")
        return
    region = context.args[0].upper()
    try:
        uid = int(context.args[1])
    except ValueError:
        await update.message.reply_text("❌ UID must be a number!", parse_mode="Markdown")
        return
    
    loading_msg = await send_animated_loading(update, context, "Visit")
    result = await call_visit_api(region, uid)
    await stop_animation(context)
    
    if "error" in result:
        await loading_msg.edit_text(f"🚫 *Error:* {result['error']}", parse_mode="Markdown")
        return
    result['region'] = region
    final_msg = format_visit_result(result)
    await loading_msg.edit_text(final_msg, parse_mode="Markdown")

async def like(update, context):
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
    
    loading_msg = await send_animated_loading(update, context, "Like")
    result = await call_like_api(region, uid)
    await stop_animation(context)
    
    if "error" in result:
        await loading_msg.edit_text(f"🚫 *Error:* {result['error']}", parse_mode="Markdown")
        return
    
    update_user_like(user_id)
    result['region'] = region
    final_msg = format_like_result(result)
    await loading_msg.edit_text(final_msg, parse_mode="Markdown")

async def info(update, context):
    if len(context.args) != 2:
        await update.message.reply_text("❌ Use: `/info IN 123456789`", parse_mode="Markdown")
        return
    region = context.args[0].upper()
    try:
        uid = int(context.args[1])
    except ValueError:
        await update.message.reply_text("❌ UID must be a number!", parse_mode="Markdown")
        return
    
    loading_msg = await send_animated_loading(update, context, "Info")
    result = await call_info_api(region, uid)
    await stop_animation(context)
    
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

# ============ VERCEL WEBHOOK INTEGRATION ============

app = FastAPI()

# Global Application instance initialize करेंगे (बगैर run_polling के)
ptb_application = Application.builder().token(BOT_TOKEN).build()

ptb_application.add_handler(CommandHandler("start", start))
ptb_application.add_handler(CommandHandler("help", help_command))
ptb_application.add_handler(CommandHandler("visit", visit))
ptb_application.add_handler(CommandHandler("like", like))
ptb_application.add_handler(CommandHandler("info", info))
ptb_application.add_handler(CallbackQueryHandler(button_handler))

@app.on_event("startup")
async def on_startup():
    # Vercel Serverless Function शुरू होते ही PTB को Initialize करेगा
    await ptb_application.initialize()

@app.post("/")
async def process_update(request: Request):
    """Vercel पर Telegram Webhook से आने वाले डेटा को हैंडल करने के लिए रूट"""
    try:
        req_json = await request.json()
        tg_update = Update.de_json(req_json, ptb_application.bot)
        await ptb_application.process_update(tg_update)
    except Exception as e:
        logger.error(f"Webhook update processing error: {e}")
    return Response(status_code=200)

@app.get("/")
async def index():
    return {"status": "S.Kanhaiya Bhoot is running on Vercel!"}
