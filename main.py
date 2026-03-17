# Import necessary libraries
import asyncio
import logging
import io
import aiohttp
import re
import sys
import os
from functools import lru_cache
from typing import Dict, Any, Optional
import time

from aiogram import Bot, Dispatcher, types, BaseMiddleware, F
from aiogram.filters import Command, CommandObject
from aiogram.client.default import DefaultBotProperties
from aiogram.types import Message, BufferedInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton

from config import BOT_TOKEN, DB_PATH, OSU_API_KEY, OSU_CLIENT_ID, OSU_CLIENT_SECRET, OSU_SESSION
from database.db_manager import DBManager
from core.api_droid import DroidAPI
from core.api_osu import OsuAPI
from localization import Localization
from utils.helpers import Helpers
from utils.ui_factory import UIFactory
from utils.graphics import GraphicsGenerator
from utils.logger import setup_logger

# Add path to osudroid-api-wrapper
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'osudroid-api-wrapper', 'src'))
from osudroid_api_wrapper import Profile

# Setup logging
setup_logger()
logger = logging.getLogger("bot")

# Middleware for logging (non-blocking)
class LoggingMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        if isinstance(event, types.Message) and event.text:
            logger.info(f"User {event.from_user.id} (@{event.from_user.username}): {event.text}")
        return await handler(event, data)

db = DBManager(DB_PATH)
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="Markdown"))
dp = Dispatcher()
dp.message.outer_middleware(LoggingMiddleware()) # Register logger

api_d = DroidAPI()
api_o = OsuAPI(OSU_CLIENT_ID, OSU_CLIENT_SECRET)

# Simple cache for API responses
api_cache = {}

async def get_lang(uid):
    """Get user's preferred language"""
    user = db.get_user_settings(uid)
    return user[0] if user else 'en'

# --- COMMANDS ---

@dp.message(Command("start"))
async def cmd_start(m: types.Message):
    await m.reply(UIFactory.get_text('start', await get_lang(m.from_user.id)))

@dp.message(Command("help"))
async def cmd_help(m: types.Message):
    help_text = UIFactory.get_text('help', await get_lang(m.from_user.id))
    
    # Updated commands list
    additional_help = """
    
**Available Commands:**

/u `<username>` - Enhanced profile with real API stats
/leaderboard `[type]` `[region]` - Show leaderboard (pp/score/accuracy, global/country)
/seasonal - Choose seasonal backgrounds for profile cards
/prpic `<username>` - Profile picture card with seasonal background
/map `<link or ID>` - Get beatmap information
/topplays `<username>` - Show top 10 plays
/sr `<query>` - Search beatmaps
/roll `[min max]` - Random number generator
/yn - Yes/No random generator

**Examples:**
/u PippiHBot
/leaderboard pp global
/leaderboard score country
/seasonal
/prpic username
/map https://osu.ppy.sh/beatmapsets/123456#osu/789012
/topplays username
/sr anime
/roll 1 100

**Other Commands:**
/recent `<username>` - Show recent plays using osudroid-api-wrapper
/bind `<username>` - Bind your account
/unbind - Unbind your account
/lang `<ru/en>` - Change language
/compare `<user1> <user2>` - Compare two users
"""
    
    await m.reply(help_text + additional_help)

@dp.message(Command("u", "profile"))
async def cmd_user(m: types.Message):
    """Enhanced profile command using real API"""
    args = m.text.split()
    lang = await get_lang(m.from_user.id)
    
    if len(args) > 1:
        username = args[1]
    else:
        username = db.get_bind(m.from_user.id)
    
    if not username: 
        return await m.reply(Localization.get_text('no_username', lang))
    
    await m.reply(f"Loading profile {username}...")
    
    profile_data = await api_d.get_user_profile_by_username_new(username)
    if not profile_data:
        return await m.reply("Player not found.")
    
    # RECORD PP IN HISTORY (for /ppgraph functionality)
    db.add_pp_record(m.from_user.id, profile_data.get('pp', 0))
    
    # Format enhanced profile text
    acc = profile_data.get('accuracy', 0) * 100
    text = (
        f"**User:** {profile_data.get('username')}\n"
        f"**UID:** {profile_data.get('user_id')}\n"
        f"**Rank:** #{profile_data.get('rank')}\n"
        f"**Country Rank:** #{profile_data.get('country_rank')}\n"
        f"**PP:** {profile_data.get('pp', 0):.2f}\n"
        f"**Accuracy:** {acc:.2f}%\n"
        f"**Playcount:** {profile_data.get('playcount', 0):,}\n"
        f"**Score:** {profile_data.get('score', 0):,}\n"
        f"**Level:** {profile_data.get('level', 1)}\n"
        f"**Country:** {profile_data.get('country', 'Unknown')}\n"
        f"**Joined:** {profile_data.get('joined_at', 'Unknown')}\n"
        f"**Profile:** [Link]({profile_data.get('profile_url')})"
    )
    
    # Add badges if available
    badges = []
    if profile_data.get('supporter'):
        badges.append("Supporter")
    if profile_data.get('core_developer'):
        badges.append("Core Dev")
    if profile_data.get('developer'):
        badges.append("Developer")
    if profile_data.get('contributor'):
        badges.append("Contributor")
    
    if badges:
        text += f"\n\n**Badges:** {' | '.join(badges)}"
    
    await m.reply(text, parse_mode="Markdown", disable_web_page_preview=True)

@dp.message(Command("recent"))
async def cmd_recent(m: types.Message):
    """Show recent plays using osudroid-api-wrapper with pagination"""
    args = m.text.split()
    
    # Try to get nickname from command args, otherwise from database binding
    if len(args) > 1:
        username = args[1]
    else:
        username = db.get_bind(m.from_user.id)
    
    if not username: 
        return await m.reply("Enter nickname or bind account via /bind.")
    
    await m.reply(f"Loading recent games for {username}...")
    
    try:
        # Use osudroid-api-wrapper to get profile
        profile = Profile.from_api(username=username)
        
        if not profile or not profile.recent_scores:
            return await m.reply("Failed to load recent games or no games available.")
        
        # Save data in session for pagination
        await show_recent_score(m, profile.recent_scores, username, 0)
        
    except Exception as e:
        logger.exception(f"Error in /recent command for {username}")
        await m.reply(f"Error loading recent games: {str(e)}")

async def show_recent_score(message, scores, username, index, is_edit=False):
    """Show single score with pagination"""
    if index >= len(scores):
        return await message.answer("No more recent games.")
    
    score = scores[index]
    
    # Get beatmap information
    beatmap = score.beatmap
    if beatmap:
        map_info = f"**{beatmap.artist} - {beatmap.title} [{beatmap.version}]**"
    else:
        # Try to get map info from filename
        if score.filename:
            # Extract title from format "Artist - Title (Creator) [Difficulty]"
            import re
            # Remove hash at the end if present
            clean_filename = re.sub(r'\s*\{[^}]*\}$', '', score.filename)
            # Escape special characters for Markdown
            clean_filename = clean_filename.replace('*', r'\*').replace('_', r'\_').replace('`', r'\`')
            map_info = f"**{clean_filename}**"
        else:
            map_info = "**Unknown map**"
    
    # Format mods
    mods_str = score.mods.as_standard_mods if score.mods else "NoMod"
    
    # Format grade
    grade = score.grade if score.grade else "N/A"
    
    # Format time
    import datetime
    if score.date:
        date = datetime.datetime.fromtimestamp(score.date)
        time_str = date.strftime("%d.%m.%Y %H:%M")
    else:
        time_str = "Unknown"
    
    # Check for None before formatting
    accuracy_str = f"{score.accuracy:.2f}%" if score.accuracy is not None else "N/A"
    dpp_str = f"{score.pp:.2f}dpp" if score.pp is not None else "N/A dpp"
    combo_str = f"{score.combo:,}x" if score.combo is not None else "N/A"
    score_str = f"{score.score:,}" if score.score is not None else "N/A"
    
    # Format text
    text = (
        f"**Recent games {username} - #{index + 1}/{len(scores)}**\n\n"
        f"{map_info}\n\n"
        f"**{grade}** {mods_str}\n\n"
        f"**Accuracy:** {accuracy_str} | **DPP:** {dpp_str}\n"
        f"**Combo:** {combo_str} | **Score:** {score_str}\n"
        f"**Time:** {time_str}"
    )
    
    # Create keyboard for pagination
    builder = InlineKeyboardBuilder()
    
    # Navigation button
    nav_row = []
    if index > 0:
        nav_row.append(InlineKeyboardButton(text="Previous", callback_data=f"recent_page:{username}:{index-1}"))
    
    nav_row.append(InlineKeyboardButton(text=f"{index + 1}/{len(scores)}", callback_data="recent_info"))
    
    if index < len(scores) - 1:
        nav_row.append(InlineKeyboardButton(text="Next", callback_data=f"recent_page:{username}:{index+1}"))
    
    if nav_row:
        builder.row(*nav_row)
    
    # Send or edit message
    if is_edit:
        await message.edit_text(text, parse_mode="Markdown", reply_markup=builder.as_markup())
    else:
        await message.reply(text, parse_mode="Markdown", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("recent_page:"))
async def cb_recent_pagination(c: types.CallbackQuery):
    """Handle recent games pagination"""
    try:
        parts = c.data.split(":")
        if len(parts) < 3:
            return await c.answer("Неверные данные пагинации")
        
        username = parts[1]
        page = int(parts[2])
        
        await c.answer()
        
        # Load profile again
        profile = Profile.from_api(username=username)
        if not profile or not profile.recent_scores:
            return await c.answer("Failed to load recent games")
        
        await show_recent_score(c.message, profile.recent_scores, username, page, is_edit=True)
        
    except Exception as e:
        logger.exception(f"Error in recent pagination: {e}")
        await c.answer("Ошибка при загрузке страницы")

@dp.callback_query(F.data == "recent_info")
async def cb_recent_info(c: types.CallbackQuery):
    """Current page information"""
    await c.answer("Use navigation buttons to view games", show_alert=True)

@dp.message(Command("prpic"))
async def prpic_cmd(message: types.Message):
    args = message.text.split(maxsplit=1)

    # Determine username
    if len(args) > 1:
        username = args[1]
    else:
        username = db.get_bind(message.from_user.id)
        if not username:
            await message.answer("Usage: /prpic <nickname> or bind account first")
            return

    # Get UID
    user_id = await GraphicsGenerator.get_user_id_by_username(username)
    if not user_id:
        await message.answer("User not found")
        return

    # Get profile data
    profile_url = f"https://new.osudroid.moe/api2/frontend/profile-username/{username}"
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(profile_url, timeout=10) as resp:
                if resp.status != 200:
                    await message.answer("Failed to get profile data")
                    return
                data = await resp.json()
        except Exception as e:
            await message.answer("Error getting profile data")
            print(e)
            return

    # Get user's seasonal background
    seasonal_bg = db.get_user_seasonal_bg(message.from_user.id)
    
    # Create card with seasonal background
    buf = await GraphicsGenerator.create_profile_card(data, seasonal_bg_url=seasonal_bg)
    if not buf:
        await message.answer("Failed to generate profile card")
        return

    # Отправляем
    await message.answer_photo(BufferedInputFile(buf.getvalue(), filename="profile_card.png"))

@dp.message(Command("map"))
async def cmd_map(message: Message, command: CommandObject):
    if not command.args:
        return await message.answer("Usage: `/map <link or ID>`")
    
    await process_map_link(message, command.args.strip())

@dp.message(F.text.contains("osu.ppy.sh/beatmapsets/"))
async def handle_osu_link(m: types.Message):
    # Auto-detect map links
    await process_map_link(m, m.text)

async def process_map_link(message: Message, query: str):
    """Process map link or ID"""
    # Regex patterns for parsing
    RE_URL_BID = re.compile(r"beatmapsets/\d+#osu/(\d+)")
    RE_URL_SID = re.compile(r"beatmapsets/(\d+)")
    
    b_id = RE_URL_BID.search(query)
    s_id = RE_URL_SID.search(query)

    status_msg = await message.answer("Loading map information...")

    try:
        # Try to get map information via droid API
        # If direct beatmap ID is available
        beatmap_id = b_id.group(1) if b_id else (query if query.isdigit() and int(query) > 5000 else None)
        
        if beatmap_id:
            # Use droid API to get map information
            dpp_data = await api_d.get_map_pp(beatmap_id)
            if not dpp_data:
                # Try to get information from osu! API as fallback
                try:
                    osu_beatmap = await api_o.get_beatmap(beatmap_id)
                    if not osu_beatmap:
                        return await status_msg.edit_text("Beatmap not found in droid API or osu! API.")
                    
                    # Create basic information from osu! API
                    await status_msg.edit_text(f"**{osu_beatmap.get('artist', 'Unknown')} - {osu_beatmap.get('title', 'Unknown')}**\n\n"
                                            f"**Difficulty:** {osu_beatmap.get('version', 'Unknown')}\n"
                                            f"**Creator:** {osu_beatmap.get('creator', 'Unknown')}\n"
                                            f"**BPM:** {osu_beatmap.get('bpm', 'N/A')}\n"
                                            f"**Length:** {osu_beatmap.get('total_length', 'N/A')} sec\n"
                                            f"**Difficulty:** {osu_beatmap.get('difficulty_rating', 'N/A')}★\n\n"
                                            f"⚠️ PP information unavailable (beatmap not found in droid API)\n\n"
                                            f"[Open in osu!](https://osu.ppy.sh/b/{beatmap_id})",
                                            parse_mode="Markdown", disable_web_page_preview=True)
                    return
                    
                except Exception as e:
                    # Handle exception when getting fallback beatmap data
                    logger.error(f"Error getting fallback beatmap data: {e}")
                    return await status_msg.edit_text("Beatmap not found in droid API and failed to get data from osu! API.")
            
            # Debug: output all fields from droid API
            logger.info(f"Droid API beatmap data: {dpp_data.get('beatmap', {})}")
            
            # Create card with image using dpp_data
            # Format data in expected format for draw_beatmap_card
            map_info = dpp_data.get('beatmap', {})
            stats = map_info.get('stats', {})
            
            # Add parameters to top level for compatibility with draw_beatmap_card
            map_info['cs'] = stats.get('cs', 0)
            map_info['ar'] = stats.get('ar', 0)
            map_info['accuracy'] = stats.get('od', 0)  # OD is called accuracy in function
            map_info['drain'] = stats.get('hp', 0)     # HP is called drain in function
            map_info['status'] = 'ranked'             # Add default status
            map_info['bpm'] = map_info.get('bpm', 0)  # BPM
            
            # Get BPM and status from osu! API
            cache_key_osu = f"osu_map_{beatmap_id}"
            osu_beatmap = api_cache.get(cache_key_osu)
            
            if not osu_beatmap:
                try:
                    osu_beatmap = await api_o.get_beatmap(beatmap_id)
                    if osu_beatmap:
                        api_cache.set(cache_key_osu, osu_beatmap)
                except Exception as e:
                    logger.error(f"Error getting osu! beatmap data: {e}")
            
            if osu_beatmap:
                if osu_beatmap.get('bpm'):
                    map_info['bpm'] = osu_beatmap['bpm']
                if osu_beatmap.get('status'):
                    map_info['status'] = osu_beatmap['status']
                if osu_beatmap.get('total_length'):
                    map_info['total_length'] = osu_beatmap['total_length']
            
            # Extract set ID from link for cover
            set_id = s_id.group(1) if s_id else None
            if not set_id:
                # If set ID not found, try to extract from beatmap ID (usually first digits)
                set_id = str(int(beatmap_id) // 1000) if beatmap_id else beatmap_id
            
            beatmapset_info = {
                'title': map_info.get('title', 'Unknown'),
                'artist': map_info.get('artist', 'Unknown'),
                'covers': {
                    'cover@2x': f"https://assets.ppy.sh/beatmaps/{set_id}/covers/cover@2x.jpg"
                }
            }
            
            # Add set information to beatmap data
            map_info['beatmapset'] = beatmapset_info
            
            # Debug: output cover URL
            cover_url = beatmapset_info['covers']['cover@2x']
            logger.info(f"Trying to load cover from URL: {cover_url}")
            buf = await GraphicsGenerator.draw_beatmap_card(map_info, dpp_data)
            if buf:
                photo = BufferedInputFile(buf.getvalue(), filename=f"map_{beatmap_id}.png")
                
                # Create simple text information
                text = (
                    f"**Beatmap #{beatmap_id}**\n\n"
                    f"**Artist:** {map_info.get('artist', 'N/A')}\n"
                    f"**Title:** {map_info.get('title', 'N/A')}\n"
                    f"**Difficulty:** {map_info.get('version', 'N/A')}\n"
                    f"**Creator:** {map_info.get('creator', 'N/A')}\n\n"
                    f"**DPP:** {dpp_data.get('performance', {}).get('droid', {}).get('total', 0):.2f}pp\n"
                    f"**Stars:** {dpp_data.get('difficulty', {}).get('droid', {}).get('total', 0):.2f}★\n"
                    f"**Max Combo:** {map_info.get('maxCombo', 'N/A')}\n"
                    f"**CS:** {map_info.get('stats', {}).get('cs', 'N/A')} "
                    f"**AR:** {map_info.get('stats', {}).get('ar', 'N/A')} "
                    f"**OD:** {map_info.get('stats', {}).get('od', 'N/A')} "
                    f"**HP:** {map_info.get('stats', {}).get('hp', 'N/A')}\n"
                    f"**BPM:** {map_info.get('bpm', 'N/A')} | "
                    f"**Length:** {map_info.get('total_length', 'N/A')}\n"
                    f"**Status:** {map_info.get('status', 'N/A')}\n\n"
                    f"[Открыть в osu!](https://osu.ppy.sh/b/{beatmap_id})"
                )
                
                # Create keyboard with download buttons
                download_kb = InlineKeyboardBuilder()
                download_kb.row(
                    InlineKeyboardButton(text="Download", callback_data=f"download_osz:{beatmap_id}:{set_id if set_id else beatmap_id}")
                )
                download_kb.row(
                    InlineKeyboardButton(text="osu.direct", callback_data=f"mirror_osz:direct:{set_id if set_id else beatmap_id}"),
                    InlineKeyboardButton(text="beatconnect.io", callback_data=f"mirror_osz:connect:{set_id if set_id else beatmap_id}")
                )
                
                await status_msg.delete()
                await message.answer_photo(
                    photo=photo,
                    caption=text,
                    parse_mode="Markdown",
                    disable_web_page_preview=True,
                    reply_markup=download_kb.as_markup()
                )
            else:
                # If failed to create card, show only text
                map_info = dpp_data.get('beatmap', {})
                text = (
                    f"**Карта #{beatmap_id}**\n\n"
                    f"**Artist:** {map_info.get('artist', 'N/A')}\n"
                    f"**Title:** {map_info.get('title', 'N/A')}\n"
                    f"**Difficulty:** {map_info.get('version', 'N/A')}\n"
                    f"**Creator:** {map_info.get('creator', 'N/A')}\n\n"
                    f"**DPP:** {dpp_data.get('performance', {}).get('droid', {}).get('total', 0):.2f}pp\n"
                    f"**Stars:** {dpp_data.get('difficulty', {}).get('droid', {}).get('total', 0):.2f}★\n"
                    f"**Max Combo:** {map_info.get('maxCombo', 'N/A')}\n"
                    f"**CS:** {map_info.get('stats', {}).get('cs', 'N/A')} "
                    f"**AR:** {map_info.get('stats', {}).get('ar', 'N/A')} "
                    f"**OD:** {map_info.get('stats', {}).get('od', 'N/A')} "
                    f"**HP:** {map_info.get('stats', {}).get('hp', 'N/A')}\n\n"
                    f"[Открыть в osu!](https://osu.ppy.sh/b/{beatmap_id})"
                )
                
                await status_msg.edit_text(text, parse_mode="Markdown", disable_web_page_preview=True)
        else:
            # If this is set ID, try to get information
            set_id = s_id.group(1) if s_id else query
            await status_msg.edit_text(f"For set {set_id} you need to specify specific difficulty.\n\nExample: https://osu.ppy.sh/beatmapsets/{set_id}#osu/123456")

    except Exception as e:
        logger.exception("Error processing beatmap")
        error_msg = str(e).replace('*', r'\*').replace('_', r'\_').replace('`', r'\`')
        await status_msg.edit_text(f"An error occurred: {error_msg}", parse_mode="Markdown")

@dp.message(Command("leaderboard"))
async def cmd_leaderboard(m: types.Message):
    args = m.text.split()
    leaderboard_type = args[1] if len(args) > 1 and args[1] in ['pp', 'score', 'accuracy'] else 'pp'
    region = args[2] if len(args) > 2 and args[2] in ['global', 'country'] else 'global'
    
    await m.reply(f"Loading leaderboard {leaderboard_type} ({region})...")
    
    leaderboard = await api_d.get_leaderboard_new(leaderboard_type, region, 1, 10)
    if not leaderboard:
        return await m.reply("Failed to load leaderboard.")
    
    await show_leaderboard_page(m, leaderboard, leaderboard_type, region, 1)

async def show_leaderboard_page(message, leaderboard, leaderboard_type, region, page, is_edit=False):
    lines = [f"**Leaderboard ({leaderboard_type.upper()} - {region.upper()}) - Page {page}**\n"]
    
    start_idx = (page - 1) * 10
    for i, player in enumerate(leaderboard[start_idx:start_idx + 10], start_idx + 1):
        username = player.get('username', 'Unknown')
        pp = player.get('pp', 0)
        rank = player.get('rank', i)
        score = player.get('score', 0)
        accuracy = player.get('accuracy', 0)
        
        if leaderboard_type == 'pp':
            lines.append(f"{i}. `{username}` - {pp:.2f}pp (#{rank})")
        elif leaderboard_type == 'score':
            lines.append(f"{i}. `{username}` - {score:,} (#{rank})")
        elif leaderboard_type == 'accuracy':
            lines.append(f"{i}. `{username}` - {accuracy*100:.2f}% (#{rank})")
    
    # Create keyboard for navigation
    builder = InlineKeyboardBuilder()
    
    # Navigation buttons
    nav_row = []
    if page > 1:
        nav_row.append(InlineKeyboardButton(text="Previous", callback_data=f"lb_page:{leaderboard_type}:{region}:{page-1}"))
    
    nav_row.append(InlineKeyboardButton(text=f"Page {page}", callback_data="lb_info"))
    
    # Check if next page exists (load 11 records to check)
    next_leaderboard = await api_d.get_leaderboard_new(leaderboard_type, region, page * 10 + 1, 1)
    if next_leaderboard:
        nav_row.append(InlineKeyboardButton(text="Next", callback_data=f"lb_page:{leaderboard_type}:{region}:{page+1}"))
    
    if nav_row:
        builder.row(*nav_row)
    
    if is_edit:
        await message.edit_text("\n".join(lines), parse_mode="Markdown", reply_markup=builder.as_markup())
    else:
        await message.reply("\n".join(lines), parse_mode="Markdown", reply_markup=builder.as_markup())

async def download_beatmap(bid: str, no_video: bool = True):
    """Function to download beatmap from mirrors like in altppy"""
    suffix = "?nv=1" if no_video else ""
    # Mirror order like in altppy
    mirrors = [
        f"https://api.nerinyan.moe/d/{bid}{suffix}",
        f"https://osu.direct/api/d/{bid}{suffix}",
        f"https://api.chimu.moe/v1/download/{bid}{suffix}",
        f"https://dl.sayobot.cn/beatmaps/download/full/{bid}"
    ]
    
    async with aiohttp.ClientSession() as session:
        for url in mirrors:
            try:
                async with session.get(url, timeout=120) as response:  
                    if response.status == 200:
                        data = await response.read()
                        return data, url
            except Exception as e:
                logger.error(f"Mirror error {url}: {e}")
                continue
    return None, None

@dp.callback_query(F.data.startswith("download_osz:"))
async def cb_download_osz(c: types.CallbackQuery):
    """Handle .osz file download like in altppy"""
    try:
        parts = c.data.split(":")
        if len(parts) < 3:
            return await c.answer("Invalid download data")
            
        beatmap_id = parts[1]
        set_id = parts[2]
        
        # 1. Immediately answer Telegram that we accepted the request
        await c.answer("Начинаю загрузку...")
        
        # 2. Notify user in chat
        status_msg = await c.message.answer(f"Downloading beatmap {beatmap_id}...")
        
        # 3. The actual download
        file_data, used_mirror = await download_beatmap(set_id)
        
        if file_data:
            await status_msg.edit_text(f"One moment...")
            
            # Определяем название зеркала для файла
            if "nerinyan" in used_mirror:
                mirror_name = "nerinyan"
            elif "osu.direct" in used_mirror:
                mirror_name = "osudirect"
            elif "chimu" in used_mirror:
                mirror_name = "chimu"
            elif "sayobot" in used_mirror:
                mirror_name = "sayobot"
            else:
                mirror_name = "unknown"
            
            # 4. Send documents
            file = types.BufferedInputFile(file_data, filename=f"{set_id}_{beatmap_id}_from_{mirror_name}.osz")
            try:
                await c.message.answer_document(file)
                await status_msg.delete()
            except Exception as e:
                await status_msg.edit_text(f"Send error: {e}")
        else:
            await status_msg.edit_text("All mirrors unavailable or file too large.")
            
    except Exception as e:
        logger.exception("Error downloading .osz")
        await c.answer(f"Error: {str(e)}")

@dp.callback_query(F.data.startswith("mirror_osz:"))
async def cb_mirror_osz(c: types.CallbackQuery):
    """Handle .osz download from specific mirror"""
    try:
        parts = c.data.split(":")
        if len(parts) < 3:
            return await c.answer("Invalid download data")
            
        mirror_type = parts[1]  # ppy, direct, connect
        set_id = parts[2]
        
        await c.answer(f"Downloading .osz from {mirror_type}...")
        
        # Define mirror URL
        mirror_urls = {
            'ppy': f"https://osu.ppy.sh/beatmapsets/{set_id}/download",
            'direct': f"https://osu.direct/api/d/{set_id}",
            'connect': f"https://beatconnect.io/b/{set_id}"
        }
        
        mirror_url = mirror_urls.get(mirror_type)
        if not mirror_url:
            return await c.answer("Unknown mirror")
        
        # Download file with increased timeout
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(mirror_url, timeout=180) as resp:  
                    if resp.status == 200:
                        osz_content = await resp.read()
                        
                        # Отправляем файл пользователю
                        file = types.BufferedInputFile(osz_content, filename=f"{set_id}_from_{mirror_type}.osz")
                        await c.message.answer_document(file)
                        await c.answer(f"File successfully downloaded from {mirror_type}")
                    else:
                        await c.answer(f"Failed to download .osz from {mirror_type} mirror. Status: {resp.status}")
            except asyncio.TimeoutError:
                await c.answer(f"Timeout when downloading from {mirror_type}. Try another mirror.")
            except Exception as e:
                logger.error(f"Ошибка при скачивании с {mirror_type}: {e}")
                await c.answer(f"Ошибка при скачивании: {str(e)}")
                    
    except Exception as e:
        logger.exception(f"Error downloading .osz from {mirror_type} mirror")
        await c.answer(f"Error: {str(e)}")

@dp.callback_query(F.data.startswith("lb_page:"))
async def cb_leaderboard_pagination(c: types.CallbackQuery):
    parts = c.data.split(":")
    if len(parts) < 4: return
    
    leaderboard_type = parts[1]
    region = parts[2]
    page = int(parts[3])
    
    leaderboard = await api_d.get_leaderboard_new(leaderboard_type, region, page * 10 + 1, 10)
    if not leaderboard:
        return await c.answer("Не удалось загрузить лидерборд.")
    
    await show_leaderboard_page(c.message, leaderboard, leaderboard_type, region, page, is_edit=True)
    await c.answer() # Убираем "часики" с кнопки

@dp.message(Command("sr"))
async def cmd_sr(m: types.Message):
    """Search beatmaps with filters"""
    args = m.text.split(maxsplit=1)
    if len(args) < 2:
        return await m.reply(Localization.get_text('sr_usage', await get_lang(m.from_user.id)))
    
    query = args[1]
    await m.reply(Localization.get_text('sr_searching', await get_lang(m.from_user.id)).format(query=query))
    
    # Parse filters from query (format: query + filters)
    filters = parse_search_filters(query)
    search_query = filters['query']
    
    # Build search URL with filters
    search_url = build_search_url(filters)
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(search_url, timeout=10) as resp:
                if resp.status != 200:
                    await m.reply(Localization.get_text('sr_unavailable', await get_lang(m.from_user.id)).format(query=search_query))
                    return
                
                data = await resp.json()
                beatmaps = data if isinstance(data, list) else []
                
                if not beatmaps:
                    return await m.reply(Localization.get_text('sr_no_results', await get_lang(m.from_user.id)).format(query=search_query))
                
                # Show first map with pagination
                await show_search_results(m, beatmaps, search_query, 0, filters)
                
    except asyncio.TimeoutError:
        await m.reply(Localization.get_text('sr_timeout', await get_lang(m.from_user.id)))
    except Exception as e:
        logger.exception(f"Error in /sr command: {e}")
        await m.reply(Localization.get_text('sr_error', await get_lang(m.from_user.id)).format(query=search_query))

def parse_search_filters(query):
    """Parse search query and filters"""
    filters = {
        'query': '',
        'mode': None,
        'status': None,
        'genre': None,
        'language': None,
        'explicit': None,
        'video': None,
        'storyboard': None,
        'played': None
    }
    
    # Extract query and filter patterns
    parts = query.split()
    query_parts = []
    
    for part in parts:
        if part.startswith('mode:'):
            mode_map = {'osu': '0', 'taiko': '1', 'catch': '2', 'mania': '3'}
            mode = part.split(':')[1].lower()
            filters['mode'] = mode_map.get(mode)
        elif part.startswith('status:'):
            status_map = {'ranked': '1', 'qualified': '3', 'loved': '4', 'pending': '0', 'wip': '5', 'graveyard': '-2'}
            status = part.split(':')[1].lower()
            filters['status'] = status_map.get(status)
        elif part.startswith('genre:'):
            genre_map = {
                'unspecified': '0', 'video': '1', 'anime': '2', 'rock': '3', 'pop': '4', 'other': '5',
                'novelty': '6', 'hip': '7', 'electronic': '8', 'metal': '9', 'classical': '10',
                'folk': '11', 'jazz': '12'
            }
            genre = part.split(':')[1].lower()
            filters['genre'] = genre_map.get(genre)
        elif part.startswith('lang:'):
            lang_map = {
                'unspecified': '0', 'english': '1', 'chinese': '2', 'french': '3', 'german': '4',
                'italian': '5', 'japanese': '6', 'korean': '7', 'spanish': '8', 'swedish': '9',
                'russian': '10', 'polish': '11', 'instrumental': '12'
            }
            lang = part.split(':')[1].lower()
            filters['language'] = lang_map.get(lang)
        elif part.startswith('explicit:'):
            explicit = part.split(':')[1].lower()
            filters['explicit'] = '1' if explicit in ['show', 'true', '1'] else '0'
        elif part.startswith('video:'):
            video = part.split(':')[1].lower()
            filters['video'] = '1' if video in ['yes', 'true', '1'] else '0'
        elif part.startswith('storyboard:'):
            storyboard = part.split(':')[1].lower()
            filters['storyboard'] = '1' if storyboard in ['yes', 'true', '1'] else '0'
        elif part.startswith('played:'):
            played = part.split(':')[1].lower()
            filters['played'] = '1' if played in ['yes', 'true', '1'] else None
        else:
            query_parts.append(part)
    
    filters['query'] = ' '.join(query_parts)
    return filters

def build_search_url(filters):
    """Build search URL with filters"""
    base_url = "https://osu.direct/api/search"
    params = []
    
    if filters['query']:
        params.append(f"q={filters['query']}")
    
    if filters['mode'] is not None:
        params.append(f"m={filters['mode']}")
    
    if filters['status'] is not None:
        params.append(f"s={filters['status']}")
    
    if filters['genre'] is not None:
        params.append(f"g={filters['genre']}")
    
    if filters['language'] is not None:
        params.append(f"l={filters['language']}")
    
    if filters['explicit'] is not None:
        params.append(f"e={filters['explicit']}")
    
    if filters['video'] is not None:
        params.append(f"nsfw={filters['video']}")
    
    if filters['storyboard'] is not None:
        params.append(f"sb={filters['storyboard']}")
    
    if filters['played'] is not None:
        params.append(f"played={filters['played']}")
    
    if params:
        return f"{base_url}?{'&'.join(params)}"
    else:
        return base_url

async def show_search_results(message, beatmaps, query, page, filters, is_edit=False):
    """Show search results with card-style display and gamemode info"""
    if page >= len(beatmaps):
        return await message.answer("Больше карт не найдено.")
    
    bm = beatmaps[page]
    
    # Debug: log the actual structure to see what fields we get
    logger.info(f"Beatmap data: {bm}")
    
    # Try different field names that osu.direct API might return
    title = (bm.get('Title') or bm.get('title') or bm.get('name') or bm.get('Name') or 'Unknown')
    artist = (bm.get('Artist') or bm.get('artist') or bm.get('artist_name') or bm.get('ArtistName') or 'Unknown')
    creator = (bm.get('Creator') or bm.get('creator') or bm.get('creator_name') or bm.get('CreatorName') or 'Unknown')
    set_id = (bm.get('SetID') or bm.get('beatmapset_id') or bm.get('BeatmapSetID') or bm.get('set_id') or 0)
    
    # Get gamemode information from ChildrenBeatmaps
    children_beatmaps = bm.get('ChildrenBeatmaps', [])
    gamemodes = []
    difficulties = []
    
    for child in children_beatmaps:
        mode = child.get('Mode', 0)
        mode_names = {0: 'osu!', 1: 'osu!taiko', 2: 'osu!catch', 3: 'osu!mania'}
        mode_name = mode_names.get(mode, f'Mode {mode}')
        
        if mode_name not in gamemodes:
            gamemodes.append(mode_name)
        
        diff_name = child.get('DiffName', 'Unknown')
        diff_rating = child.get('DifficultyRating', 0)
        difficulties.append(f"{diff_name} ({diff_rating:.2f}★)")
    
    # Create card-style text display
    text = f"**{artist} - {title}**\n\n"
    text += f"**Создатель:** {creator}\n"
    text += f"**ID сета:** {set_id}\n"
    
    if gamemodes:
        text += f"**Режимы:** {', '.join(gamemodes)}\n"
    
    if difficulties:
        text += f"**Сложности:** {', '.join(difficulties[:3])}"  # Show first 3 difficulties
        if len(difficulties) > 3:
            text += f" и еще {len(difficulties) - 3}"
        text += "\n"
    
    # Add additional map info
    if bm.get('RankedStatus') == 1:
        text += f"**Статус:** Ranked\n"
    elif bm.get('RankedStatus') == 3:
        text += f"**Статус:** Qualified\n"
    elif bm.get('RankedStatus') == 4:
        text += f"**Статус:** Loved\n"
    
    if bm.get('Favourites'):
        text += f"**Избранное:** {bm.get('Favourites')}\n"
    
    if bm.get('HasVideo'):
        text += f"**Видео:** Есть\n"
    
    text += f"\n[Открыть в osu!](https://osu.ppy.sh/beatmapsets/{set_id})"
    
    # Create action buttons
    builder = InlineKeyboardBuilder()
    
    # Action buttons row
    action_row = []
    if set_id:
        action_row.append(InlineKeyboardButton(text="Скачать", callback_data=f"sr_download:{set_id}"))
        action_row.append(InlineKeyboardButton(text="Быстрое скачивание", callback_data=f"sr_download_direct:{set_id}"))
        action_row.append(InlineKeyboardButton(text="Открыть в osu!", url=f"https://osu.ppy.sh/beatmapsets/{set_id}"))
    
    if action_row:
        builder.row(*action_row)
    
    # Navigation buttons row
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text="Предыдущая", callback_data=f"sr_page:{query}:{page-1}:{filters['query']}"))
    
    nav_row.append(InlineKeyboardButton(text=f"{page + 1}/{len(beatmaps)}", callback_data="sr_info"))
    
    if page < len(beatmaps) - 1:
        nav_row.append(InlineKeyboardButton(text="Следующая", callback_data=f"sr_page:{query}:{page+1}:{filters['query']}"))
    
    if nav_row:
        builder.row(*nav_row)
    
    if is_edit:
        await message.edit_text(text, parse_mode="Markdown", reply_markup=builder.as_markup(), disable_web_page_preview=True)
    else:
        await message.reply(text, parse_mode="Markdown", reply_markup=builder.as_markup(), disable_web_page_preview=True)

@dp.callback_query(F.data.startswith("sr_page:"))
async def cb_sr_pagination(c: types.CallbackQuery):
    """Handle search results pagination"""
    try:
        parts = c.data.split(":")
        if len(parts) < 4:
            return await c.answer("Неверные данные пагинации")
        
        query = parts[1]
        page = int(parts[2])
        filters_query = parts[3]
        
        await c.answer()
        
        # Parse filters from query to maintain search context
        filters = parse_search_filters(filters_query)
        search_url = build_search_url(filters)
        
        async with aiohttp.ClientSession() as session:
            async with session.get(search_url, timeout=10) as resp:
                if resp.status != 200:
                    return await c.answer("Не удалось загрузить результаты поиска.")
                
                data = await resp.json()
                beatmaps = data if isinstance(data, list) else []
                
                if not beatmaps:
                    return await c.answer("Карты не найдены.")
                
                await show_search_results(c.message, beatmaps, query, page, filters, is_edit=True)
        
    except Exception as e:
        logger.exception(f"Error in search pagination: {e}")
        await c.answer("Ошибка при загрузке страницы")

@dp.callback_query(F.data.startswith("sr_download:"))
async def cb_sr_download(c: types.CallbackQuery):
    """Handle download from search results"""
    try:
        parts = c.data.split(":")
        if len(parts) < 2:
            return await c.answer("Invalid download data")
        
        set_id = parts[1]
        
        await c.answer("Начинаю загрузку...")
        
        # Use existing download function
        file_data, used_mirror = await download_beatmap(set_id)
        
        if file_data:
            await c.answer("Скачиваю...")
            
            # Определяем название зеркала для файла
            if "nerinyan" in used_mirror:
                mirror_name = "nerinyan"
            elif "osu.direct" in used_mirror:
                mirror_name = "osudirect"
            elif "chimu" in used_mirror:
                mirror_name = "chimu"
            elif "sayobot" in used_mirror:
                mirror_name = "sayobot"
            else:
                mirror_name = "unknown"
            
            # Отправка документа
            file = types.BufferedInputFile(file_data, filename=f"{set_id}_from_{mirror_name}.osz")
            await c.message.answer_document(file)
            await c.answer(f"Файл успешно скачан с {mirror_name}")
        else:
            await c.answer("Все зеркала недоступны или файл слишком большой.")
            
    except Exception as e:
        logger.exception(f"Error in search download: {e}")
        await c.answer(f"Ошибка при скачивании: {str(e)}")

@dp.callback_query(F.data.startswith("sr_download_direct:"))
async def cb_sr_download_direct(c: types.CallbackQuery):
    """Handle direct download from search results (like /dwm)"""
    try:
        parts = c.data.split(":")
        if len(parts) < 2:
            return await c.answer("Invalid download data")
        
        set_id = parts[1]
        
        await c.answer("Начинаю быструю загрузку...")
        
        # Download directly from osu.direct (like /dwm method)
        direct_url = f"https://osu.direct/api/d/{set_id}"
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(direct_url, timeout=180) as resp:
                    if resp.status == 200:
                        osz_content = await resp.read()
                        
                        # Отправляем файл пользователю
                        file = types.BufferedInputFile(osz_content, filename=f"{set_id}_from_direct.osz")
                        await c.message.answer_document(file)
                        await c.answer("Файл успешно скачан с osu.direct")
                    else:
                        await c.answer(f"Не удалось скачать .osz с osu.direct. Статус: {resp.status}")
            except asyncio.TimeoutError:
                await c.answer("Таймаут при скачивании с osu.direct. Попробуйте обычное скачивание.")
            except Exception as e:
                logger.error(f"Ошибка при скачивании с osu.direct: {e}")
                await c.answer(f"Ошибка при скачивании: {str(e)}")
                
    except Exception as e:
        logger.exception(f"Error in search direct download: {e}")
        await c.answer(f"Ошибка при скачивании: {str(e)}")

@dp.callback_query(F.data == "sr_info")
async def cb_sr_info(c: types.CallbackQuery):
    """Info about current search page"""
    await c.answer("Используйте кнопки навигации для просмотра карт", show_alert=True)

@dp.message(Command("yn"))
async def cmd_yn(m: types.Message):
    """Yes/No random generator"""
    import random
    result = random.choice(["Да", "Нет"])
    await m.reply(f"**{result}**")

@dp.message(Command("roll"))
async def cmd_roll(m: types.Message):
    """Random number generator"""
    args = m.text.split()
    
    if len(args) == 1:
        # No arguments, default 1-100
        min_val, max_val = 1, 100
    elif len(args) == 2:
        # One argument, use as max value
        try:
            max_val = int(args[1])
            min_val = 1
        except ValueError:
            return await m.reply("Используйте числа.")
    elif len(args) == 3:
        # Two arguments, min and max
        try:
            min_val = int(args[1])
            max_val = int(args[2])
        except ValueError:
            return await m.reply("Используйте числа.")
    else:
        return await m.reply("Использование: /roll [мин] [макс]")
    
    if min_val > max_val:
        min_val, max_val = max_val, min_val
    
    import random
    result = random.randint(min_val, max_val)
    
    await m.reply(f"Выпало число: **{result}** ({min_val}-{max_val})")

async def main():
    await dp.start_polling(bot)
    
@dp.message(Command("bind"))
async def cmd_bind(m: types.Message):
    args = m.text.split(maxsplit=1)
    if len(args) < 2:
        return await m.reply("Использование: /bind <никнейм>")
    
    username = args[1]
    
    # Можно добавить проверку через API Droid
    data = await api_d.get_profile(username)
    if not data:
        return await m.reply("Игрок не найден. Проверьте никнейм.")
    
    # Сохраняем в БД
    db.set_bind(m.from_user.id, username)
    await m.reply(f"Аккаунт привязан к `{username}`.", parse_mode="Markdown")
    
@dp.message(Command("unbind"))
async def cmd_unbind(m: types.Message):
    db.set_bind(m.from_user.id, None)
    await m.reply("Аккаунт отвязан.")
    
# --- Команда LANG ---
@dp.message(Command("lang"))
async def cmd_lang(m: types.Message):
    args = m.text.split()
    if len(args) < 2 or args[1].lower() not in ['ru', 'en']:
        return await m.reply("Использование: `/lang ru` или `/lang en`")
    
    lang = args[1].lower()
    db.update_setting(m.from_user.id, 'lang', lang)
    msg = "Язык изменен на русский" if lang == 'ru' else "Language set to English"
    await m.answer(msg)
    
# --- Команда COMPARE ---
@dp.message(Command("compare"))
async def cmd_compare(m: types.Message):
    args = m.text.split()
    if len(args) < 3:
        return await m.reply("Использование: `/compare <ник1> <ник2>`")

    u1_name, u2_name = args[1], args[2]
    data1 = await api_d.get_profile(u1_name)
    data2 = await api_d.get_profile(u2_name)

    if not data1 or not data2:
        return await m.answer("**BATTLE: {u1_name} vs {u2_name}**\n\n")

    from core.analyzer import StatsAnalyzer
    res = StatsAnalyzer.compare_users(data1, data2)

    def get_line(metric_key, is_percent=False):
        data = res[metric_key]
        v1 = data['u1']
        v2 = data['u2']
        
        # Форматирование значений
        if is_percent:
            v1_str, v2_str = f"{v1*100:.2f}%", f"{v2*100:.2f}%"
        elif metric_key == 'GlobalRank':
            v1_str, v2_str = f"#{int(v1)}", f"#{int(v2)}"
        elif metric_key == 'OverallPP':
            v1_str, v2_str = f"{v1:.2f}pp", f"{v2:.2f}pp"
        else:
            v1_str, v2_str = f"{int(v1)}", f"{int(v2)}"

        line1 = f"{'WIN' if data['winner'] == 1 else 'LOSE'} {u1_name}: `{v1_str}`"
        line2 = f"{'WIN' if data['winner'] == 2 else 'LOSE'} {u2_name}: `{v2_str}`"
        return f"**{data['name']}**\n{line1}\n{line2}\n\n"

    text = f"**BATTLE: {u1_name} vs {u2_name}**\n\n"
    text += get_line('GlobalRank')
    text += get_line('OverallPP')
    text += get_line('OverallAccuracy', is_percent=True)
    text += get_line('OverallPlaycount')
    text += get_line('Level')

    await m.answer(text, parse_mode="Markdown")

    
@dp.message(Command("seasonal"))
async def cmd_seasonal(m: types.Message):
    """Показать доступные сезонные фоны"""
    await m.reply("Загружаю сезонные фоны...")
    
    backgrounds = await GraphicsGenerator.get_seasonal_backgrounds()
    if not backgrounds:
        return await m.reply("Не удалось загрузить сезонные фоны.")
    
    # Показываем первый фон с пагинацией
    await show_seasonal_page(m, backgrounds, 0)


async def show_seasonal_page(message, backgrounds, page, is_edit=False):
    """Показать страницу с сезонными фонами"""
    from aiogram.types import InputMediaPhoto
    
    total = len(backgrounds)
    current_index = page
    
    if current_index >= total:
        if is_edit:
            await message.edit_text("Больше фонов нет.")
        else:
            await message.answer("Больше фонов нет.")
        return
    
    bg = backgrounds[current_index]
    user = bg.get('user', {})
    artist = user.get('username', f'Artist_{current_index}')
    country = user.get('country_code', 'UN')
    bg_url = bg.get('url')
    
    # Создаем клавиатуру
    builder = InlineKeyboardBuilder()
    
    # Кнопка выбора текущего фона
    callback_data = f"seasonal_bg:{current_index}"
    builder.add(InlineKeyboardButton(text=f"Выбрать фон от {artist} ({country})", callback_data=callback_data))
    
    # Навигация
    nav_row = []
    if current_index > 0:
        nav_row.append(InlineKeyboardButton(text="Предыдущий", callback_data=f"seasonal_page:{current_index-1}"))
    
    nav_row.append(InlineKeyboardButton(text=f"{current_index + 1}/{total}", callback_data="seasonal_info"))
    
    if current_index < total - 1:
        nav_row.append(InlineKeyboardButton(text="Следующий", callback_data=f"seasonal_page:{current_index+1}"))
    
    if nav_row:
        builder.row(*nav_row)
    
    builder.add(InlineKeyboardButton(text="Убрать фон", callback_data="seasonal_bg:none"))
    
    # Редактируем или отправляем сообщение
    try:
        if is_edit:
            await message.edit_media(
                media=InputMediaPhoto(
                    media=bg_url,
                    caption=f"**Сезонный фон #{current_index + 1}**\nАвтор: {artist} ({country})"
                ),
                reply_markup=builder.as_markup()
            )
        else:
            await message.answer_photo(
                photo=bg_url,
                caption=f"**Сезонный фон #{current_index + 1}**\nАвтор: {artist} ({country})",
                reply_markup=builder.as_markup(),
                parse_mode="Markdown"
            )
    except Exception as e:
        # Если фото не загрузилось, отправляем/редактируем текст
        caption = f"**Сезонный фон #{current_index + 1}**\nАвтор: {artist} ({country})\n\n[Просмотреть фон]({bg_url})"
        if is_edit:
            await message.edit_text(
                caption,
                reply_markup=builder.as_markup(),
                parse_mode="Markdown",
                disable_web_page_preview=False
            )
        else:
            await message.answer(
                caption,
                reply_markup=builder.as_markup(),
                parse_mode="Markdown",
                disable_web_page_preview=False
            )


@dp.callback_query(lambda c: c.data.startswith("seasonal_page:"))
async def cb_seasonal_page(call: types.CallbackQuery):
    """Обработка пагинации сезонных фонов"""
    page = int(call.data.split(":", 1)[1])
    backgrounds = await GraphicsGenerator.get_seasonal_backgrounds()
    
    await call.answer()
    await show_seasonal_page(call.message, backgrounds, page, is_edit=True)


@dp.callback_query(lambda c: c.data.startswith("seasonal_info"))
async def cb_seasonal_info(call: types.CallbackQuery):
    """Информация о текущем фоне"""
    await call.answer("Используйте кнопки навигации для просмотра фонов", show_alert=True)


@dp.callback_query(lambda c: c.data.startswith("seasonal_bg:"))
async def cb_seasonal_bg(call: types.CallbackQuery):
    """Обработка выбора сезонного фона"""
    bg_choice = call.data.split(":", 1)[1]
    
    if bg_choice == "none":
        # Убираем фон
        db.set_user_seasonal_bg(call.from_user.id, None)
        await call.answer("Фон убран")
        await call.message.edit_text("Сезонный фон убран. Используется стандартный фон.")
    else:
        try:
            bg_index = int(bg_choice)
            backgrounds = await GraphicsGenerator.get_seasonal_backgrounds()
            
            if bg_index < len(backgrounds):
                bg = backgrounds[bg_index]
                bg_url = bg.get('url')
                
                # Сохраняем выбор пользователя
                db.set_user_seasonal_bg(call.from_user.id, bg_url)
                
                user = bg.get('user', {})
                artist = user.get('username', 'Unknown')
                
                await call.answer(f"Выбран фон от {artist}")
                
                # Показываем превью
                from aiogram.types import InputMediaPhoto
                media = InputMediaPhoto(
                    media=bg_url,
                    caption=f"Сезонный фон от {artist} установлен для ваших карточек профиля!"
                )
                await call.message.edit_media(media)
            else:
                await call.answer("Фон не найден")
        except (ValueError, IndexError):
            await call.answer("Ошибка выбора фона")


if __name__ == "__main__":
    asyncio.run(main())