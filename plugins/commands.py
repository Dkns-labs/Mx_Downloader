from hydrogram import Client, filters
from hydrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from database import add_user, get_stats


def full_name(user) -> str:
    return f"{user.first_name or ''} {user.last_name or ''}".strip()


@Client.on_message(filters.command("start"))
async def start_cmd(client: Client, message: Message):
    await add_user(
        message.from_user.id,
        message.from_user.username,
        full_name(message.from_user),
    )
    await message.reply_text(
        "<b>🎬 Welcome To DsrBotz MX Player Downloader\n\n"
        "<i>⚡️ Download MX Player Movies & Web Shows Instantly\n\n"
        "✨ Just Send A Valid MX Player / MXPlay Link\n"
        "🎯 Choose Your Preferred Quality\n"
        "📥 Get The File Directly In Chat</i>\n\n"
        "💡 Send /help For Detailed Guide</b>",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📖 Help", callback_data="help"),
             InlineKeyboardButton("📊 Stats", callback_data="stats")],
        ])
    )


@Client.on_message(filters.command("help"))
async def help_cmd(client: Client, message: Message):
    await message.reply_text(
        "<b>📖 DsrBotz — Help Guide\n\n"
        "🎯 How To Use:\n"
        "1️⃣ Send Any MX Player / MXPlay Video Link\n"
        "2️⃣ Bot Will Fetch All Available Qualities\n"
        "3️⃣ Tap Your Preferred Format (1080p, 720p, etc.)\n"
        "4️⃣ Bot Downloads & Uploads The File To You\n\n"
        "🚀 Supported Qualities:\n"
        "• 4K (2160p) / 1440p / 1080p / 720p / 480p / 360p\n\n"
        "⚙️ Powered By:\n"
        "• N_m3u8DL-RE — Ultra Fast Downloader\n"
        "• MX Player API — Link Resolver\n\n"
        "⚠️ Notes:\n"
        "• Only MX Player / MXPlay Links Supported\n"
        "• Processing Time Depends On File Size</b>"
    )


@Client.on_message(filters.command("stats"))
async def stats_cmd(client: Client, message: Message):
    total_users, total_downloads = await get_stats()
    await message.reply_text(
        f"<b>📊 DsrBotz Stats\n\n"
        f"👥 Total Users: {total_users}\n"
        f"📥 Total Downloads: {total_downloads}</b>"
    )


@Client.on_callback_query(filters.regex("^help$"))
async def help_callback(client, callback_query):
    await callback_query.answer()
    # Edit the existing message instead of sending a new one
    await callback_query.message.edit_text(
        "<b>📖 DsrBotz — Help Guide\n\n"
        "🎯 How To Use:\n"
        "1️⃣ Send Any MX Player / MXPlay Video Link\n"
        "2️⃣ Bot Will Fetch All Available Qualities\n"
        "3️⃣ Tap Your Preferred Format\n"
        "4️⃣ Bot Downloads & Uploads The File To You\n\n"
        "🚀 Supported Qualities:\n"
        "• 4K (2160p) / 1440p / 1080p / 720p / 480p / 360p\n\n"
        "⚙️ Powered By:\n"
        "• yt-dlp — Ultra Fast Downloader\n"
        "• MX Player API — Link Resolver\n\n"
        "⚠️ Notes:\n"
        "• Only MX Player / MXPlay Links Supported\n"
        "• Processing Time Depends On File Size</b>",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data="back_start")]
        ])
    )


@Client.on_callback_query(filters.regex("^stats$"))
async def stats_callback(client, callback_query):
    await callback_query.answer()
    total_users, total_downloads = await get_stats()
    # Edit the existing message instead of sending a new one
    await callback_query.message.edit_text(
        f"<b>📊 DsrBotz Stats\n\n"
        f"👥 Total Users: {total_users}\n"
        f"📥 Total Downloads: {total_downloads}</b>",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data="back_start")]
        ])
    )


@Client.on_callback_query(filters.regex("^back_start$"))
async def back_start_callback(client, callback_query):
    await callback_query.answer()
    await callback_query.message.edit_text(
        "<b>🎬 Welcome To DsrBotz MX Player Downloader\n\n"
        "<i>⚡️ Download MX Player Movies & Web Shows Instantly\n\n"
        "✨ Just Send A Valid MX Player / MXPlay Link\n"
        "🎯 Choose Your Preferred Quality\n"
        "📥 Get The File Directly In Chat</i>\n\n"
        "💡 Send /help For Detailed Guide</b>",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📖 Help", callback_data="help"),
             InlineKeyboardButton("📊 Stats", callback_data="stats")],
        ])
    )
