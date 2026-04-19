import asyncio
import os
import time
from hydrogram import Client, filters
from hydrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from helpers import (
    mx_player_api,
    is_mxplayer_url,
    get_available_formats,
    download_with_ytdlp,
    download_audio_only,
    sanitize_filename,
    SmoothProgress,
    _executor,
    generate_thumbnail,
    split_video_file,
    MAX_UPLOAD_SIZE_BYTES,
)
from database import add_user, increment_download, log_download

# In-memory session store
sessions = {}

PROGRESS_BAR_LEN = 10


def full_name(user) -> str:
    return f"{user.first_name or ''} {user.last_name or ''}".strip()


def make_progress_bar(percent: float) -> str:
    filled = int((percent / 100) * PROGRESS_BAR_LEN)
    return "█" * filled + "░" * (PROGRESS_BAR_LEN - filled)


def escape_html(text: str | None) -> str:
    """Escape < > & in titles/descriptions so they don't break HTML parse mode."""
    if not text:
        return ""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ──────────────────────────────────────────────
# LINK HANDLER
# ──────────────────────────────────────────────

@Client.on_message(filters.text & filters.private)
async def handle_link(client: Client, message: Message):
    url = message.text.strip()
    if not (url.startswith("http://") or url.startswith("https://")):
        return

    await add_user(
        message.from_user.id,
        message.from_user.username,
        full_name(message.from_user),
    )

    checking = await message.reply_text("<b>🔍 Checking Link...</b>")

    if not is_mxplayer_url(url):
        await checking.edit_text("<b>❌ Unsupported Link\nOnly MX Player / MXPlay Links Are Supported</b>")
        return

    await checking.edit_text("<b>⏳ Fetching Video Info...</b>")
    data = await mx_player_api(url)      # title auto-filled from URL if API returns None

    if not data:
        await checking.edit_text("<b>⚠️ API Server Issues — Try Again Later</b>")
        return

    if not data.get("status"):
        await checking.edit_text(f"<b>❌ {escape_html(data.get('message', 'Failed To Fetch Data'))}</b>")
        return

    m3u8 = data.get("m3u8_url", "")
    mpd  = data.get("mpd_url", "")
    download_url = m3u8 or mpd

    if not download_url:
        await checking.edit_text("<b>❌ No Download URL Found\nContact Support</b>")
        return

    # show_title is now guaranteed non-None (mx_player_api fills it from URL)
    title       = data.get("show_title") or "Unknown"
    episode     = data.get("seo_title") or ""
    season      = data.get("season") or ""
    description = data.get("description") or ""
    thumb       = data.get("thumbnail") or ""

    await checking.edit_text("<b>🔎 Fetching Available Formats...</b>")
    formats = await get_available_formats(download_url)

    video_formats = formats.get("video_formats", [])
    audio_formats = formats.get("audio_formats", [])

    if not video_formats and not audio_formats:
        await checking.edit_text("<b>❌ Could Not Detect Any Formats</b>")
        return

    # Store session
    sessions[message.from_user.id] = {
        "url":            download_url,
        "title":          title,
        "episode":        episode,
        "season":         season,
        "thumb":          thumb,
        "description":    description,
        "video_formats":  video_formats,
        "audio_formats":  audio_formats,
        "selected_video": None,
        "selected_audio": [],
        "chat_id":        message.chat.id,
    }

    info_text = (
        f"<b>🎬 Title:</b> {escape_html(title)}\n"
        f"<b>📺 Episode:</b> {escape_html(episode) or 'N/A'}\n"
        f"<b>📦 Season:</b> {escape_html(season) or 'N/A'}\n\n"
        f"<b>📝 Description:</b>\n{escape_html(description[:250])}...\n\n"
        f"<b>🎯 Step 1: Select Video Quality</b>"
    )

    buttons = []
    for fmt in video_formats:
        cb = f"vid_{message.from_user.id}_{fmt['format_id']}"
        buttons.append([InlineKeyboardButton(fmt["label"], callback_data=cb)])

    if audio_formats:
        buttons.append([InlineKeyboardButton("🎵 Audio Only", callback_data=f"audioonly_{message.from_user.id}")])

    buttons.append([InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_{message.from_user.id}")])

    try:
        await checking.delete()
        if thumb:
            await message.reply_photo(
                thumb,
                caption=info_text,
                reply_markup=InlineKeyboardMarkup(buttons),
            )
        else:
            await message.reply_text(info_text, reply_markup=InlineKeyboardMarkup(buttons))
    except Exception:
        await checking.edit_text(info_text, reply_markup=InlineKeyboardMarkup(buttons))


# ──────────────────────────────────────────────
# VIDEO FORMAT SELECTION HANDLER
# ──────────────────────────────────────────────

@Client.on_callback_query(filters.regex(r"^vid_(\d+)_(.+)$"))
async def handle_video_selection(client: Client, callback_query: CallbackQuery):
    _, user_id_str, format_id = callback_query.data.split("_", 2)
    user_id = int(user_id_str)

    if callback_query.from_user.id != user_id:
        await callback_query.answer("❌ This is not your session!", show_alert=True)
        return

    session = sessions.get(user_id)
    if not session:
        await callback_query.answer("❌ Session expired. Send the link again.", show_alert=True)
        return

    session["selected_video"] = format_id
    await callback_query.answer("✅ Video format selected!")

    audio_formats = session["audio_formats"]

    if not audio_formats:
        await start_download(client, callback_query, user_id)
        return

    info_text = (
        f"<b>🎬 Title:</b> {escape_html(session['title'])}\n"
        f"<b>✅ Video Format Selected</b>\n\n"
        f"<b>🎯 Step 2: Select Audio Track(s)</b>\n"
        f"<i>You can select multiple audio tracks</i>"
    )

    buttons = []
    for i in range(0, len(audio_formats), 2):
        row = []
        for fmt in audio_formats[i:i+2]:
            cb = f"aud_{user_id}_{fmt['format_id']}"
            row.append(InlineKeyboardButton(fmt["label"], callback_data=cb))
        buttons.append(row)

    buttons.append([
        InlineKeyboardButton("✅ Done", callback_data=f"done_{user_id}"),
        InlineKeyboardButton("⏭️ Skip Audio", callback_data=f"skip_{user_id}")
    ])
    buttons.append([InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_{user_id}")])

    await callback_query.message.edit_text(
        info_text,
        reply_markup=InlineKeyboardMarkup(buttons)
    )


# ──────────────────────────────────────────────
# AUDIO-ONLY SELECTION HANDLER
# ──────────────────────────────────────────────

@Client.on_callback_query(filters.regex(r"^audioonly_(\d+)$"))
async def handle_audio_only_selection(client: Client, callback_query: CallbackQuery):
    user_id = int(callback_query.data.split("_")[1])

    if callback_query.from_user.id != user_id:
        await callback_query.answer("❌ This is not your session!", show_alert=True)
        return

    session = sessions.get(user_id)
    if not session:
        await callback_query.answer("❌ Session expired. Send the link again.", show_alert=True)
        return

    session["selected_video"] = "audio_only"
    await callback_query.answer("🎵 Audio-only mode selected!")

    audio_formats = session["audio_formats"]

    if not audio_formats:
        await callback_query.message.edit_text("<b>❌ No audio formats available</b>")
        return

    info_text = (
        f"<b>🎬 Title:</b> {escape_html(session['title'])}\n"
        f"<b>🎵 Audio-Only Mode</b>\n\n"
        f"<b>🎯 Select Audio Track(s)</b>\n"
        f"<i>You can select multiple audio tracks</i>"
    )

    buttons = []
    for i in range(0, len(audio_formats), 2):
        row = []
        for fmt in audio_formats[i:i+2]:
            cb = f"aud_{user_id}_{fmt['format_id']}"
            row.append(InlineKeyboardButton(fmt["label"], callback_data=cb))
        buttons.append(row)

    buttons.append([InlineKeyboardButton("✅ Done", callback_data=f"done_{user_id}")])
    buttons.append([InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_{user_id}")])

    await callback_query.message.edit_text(
        info_text,
        reply_markup=InlineKeyboardMarkup(buttons)
    )


# ──────────────────────────────────────────────
# AUDIO FORMAT SELECTION HANDLER (Toggle)
# ──────────────────────────────────────────────

@Client.on_callback_query(filters.regex(r"^aud_(\d+)_(.+)$"))
async def handle_audio_selection(client: Client, callback_query: CallbackQuery):
    _, user_id_str, format_id = callback_query.data.split("_", 2)
    user_id = int(user_id_str)

    if callback_query.from_user.id != user_id:
        await callback_query.answer("❌ This is not your session!", show_alert=True)
        return

    session = sessions.get(user_id)
    if not session:
        await callback_query.answer("❌ Session expired. Send the link again.", show_alert=True)
        return

    if format_id in session["selected_audio"]:
        session["selected_audio"].remove(format_id)
        await callback_query.answer("❌ Audio track removed")
    else:
        session["selected_audio"].append(format_id)
        await callback_query.answer("✅ Audio track added")

    audio_formats = session["audio_formats"]
    is_audio_only = session["selected_video"] == "audio_only"

    info_text = (
        f"<b>🎬 Title:</b> {escape_html(session['title'])}\n"
        f"<b>{'🎵 Audio-Only Mode' if is_audio_only else '✅ Video Format Selected'}</b>\n\n"
        f"<b>🎯 {'Select' if is_audio_only else 'Step 2: Select'} Audio Track(s)</b>\n"
        f"<i>Selected: {len(session['selected_audio'])} track(s)</i>"
    )

    buttons = []
    for i in range(0, len(audio_formats), 2):
        row = []
        for fmt in audio_formats[i:i+2]:
            label = fmt["label"]
            if fmt["format_id"] in session["selected_audio"]:
                label = "✓ " + label
            cb = f"aud_{user_id}_{fmt['format_id']}"
            row.append(InlineKeyboardButton(label, callback_data=cb))
        buttons.append(row)

    if is_audio_only:
        buttons.append([InlineKeyboardButton("✅ Done", callback_data=f"done_{user_id}")])
    else:
        buttons.append([
            InlineKeyboardButton("✅ Done", callback_data=f"done_{user_id}"),
            InlineKeyboardButton("⏭️ Skip Audio", callback_data=f"skip_{user_id}")
        ])
    buttons.append([InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_{user_id}")])

    await callback_query.message.edit_reply_markup(
        reply_markup=InlineKeyboardMarkup(buttons)
    )


# ──────────────────────────────────────────────
# SKIP AUDIO HANDLER
# ──────────────────────────────────────────────

@Client.on_callback_query(filters.regex(r"^skip_(\d+)$"))
async def handle_skip_audio(client: Client, callback_query: CallbackQuery):
    user_id = int(callback_query.data.split("_")[1])

    if callback_query.from_user.id != user_id:
        await callback_query.answer("❌ Not your session!", show_alert=True)
        return

    session = sessions.get(user_id)
    if not session:
        await callback_query.answer("❌ Session expired. Send the link again.", show_alert=True)
        return

    await callback_query.answer("⏭️ Skipping audio selection...")
    session["selected_audio"] = []
    await start_download(client, callback_query, user_id)


# ──────────────────────────────────────────────
# DONE HANDLER
# ──────────────────────────────────────────────

@Client.on_callback_query(filters.regex(r"^done_(\d+)$"))
async def handle_done(client: Client, callback_query: CallbackQuery):
    user_id = int(callback_query.data.split("_")[1])

    if callback_query.from_user.id != user_id:
        await callback_query.answer("❌ Not your session!", show_alert=True)
        return

    session = sessions.get(user_id)
    if not session:
        await callback_query.answer("❌ Session expired. Send the link again.", show_alert=True)
        return

    await callback_query.answer("⬇️ Starting Download...")
    await start_download(client, callback_query, user_id)


# ──────────────────────────────────────────────
# HELPER: upload one video file (single part)
# ──────────────────────────────────────────────

async def _upload_video_part(
    client: Client,
    chat_id: int,
    file_path: str,
    caption: str,
    thumb_path: str | None,
    status_msg,
    display_label: str,
    safe_title_display: str,
    part_label: str = "",
):
    """Upload a single video part with progress reporting."""
    file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
    upload_start     = time.time()
    last_upload_edit = [0.0]

    async def upload_progress(current: int, total: int):
        now = time.time()
        if current < total and now - last_upload_edit[0] < 2.0:
            return
        last_upload_edit[0] = now
        percent  = (current / total) * 100
        bar      = make_progress_bar(percent)
        elapsed  = now - upload_start
        speed    = current / elapsed if elapsed > 0 else 0
        speed_mb = speed / (1024 * 1024)
        remaining = (total - current) / speed if speed > 0 else 0
        try:
            await status_msg.edit_text(
                f"<b>📤 Uploading{part_label} — {display_label}\n\n"
                f"[{bar}] {percent:.1f}%\n\n"
                f"⚡ Speed: {speed_mb:.2f} MB/s\n"
                f"⏱ ETA: {int(remaining)}s\n"
                f"📦 {current/(1024*1024):.1f} / {total/(1024*1024):.1f} MB\n"
                f"🎬 {safe_title_display}</b>"
            )
        except Exception:
            pass

    try:
        await client.send_video(
            chat_id,
            file_path,
            caption=caption,
            thumb=thumb_path,
            progress=upload_progress,
        )
        return True
    except Exception:
        # Fallback: send as document
        try:
            await client.send_document(
                chat_id,
                file_path,
                caption=caption,
                progress=upload_progress,
            )
            return True
        except Exception as e2:
            await status_msg.edit_text(
                f"<b>❌ Upload Failed{part_label}: {escape_html(str(e2))}</b>"
            )
            return False


# ──────────────────────────────────────────────
# START DOWNLOAD
# ──────────────────────────────────────────────

async def start_download(client: Client, callback_query: CallbackQuery, user_id: int):
    session = sessions.get(user_id)
    if not session:
        return

    video_format  = session["selected_video"]
    audio_formats = session["selected_audio"]
    is_audio_only = video_format == "audio_only"

    if not is_audio_only and not video_format:
        await callback_query.message.edit_text(
            "<b>⚠️ Please select a video quality first!</b>"
        )
        return

    # ── Build quality labels ──
    if is_audio_only:
        quality_label = f"Audio_Only_{len(audio_formats)}_track(s)"
        display_label = f"Audio Only ({len(audio_formats)} track(s))"
    else:
        video_fmt = next(
            (f for f in session["video_formats"] if f["format_id"] == video_format), None
        )
        if video_fmt:
            quality_label = f"{video_fmt['quality']}_{video_fmt['ext']}"
            display_label = f"{video_fmt['quality']} - {video_fmt['ext']}"
        else:
            quality_label = video_format
            display_label = video_format

        if audio_formats:
            quality_label += f"_{len(audio_formats)}_audio"
            display_label += f" + {len(audio_formats)} audio"

    safe_title_display = escape_html(session["title"])

    # ── Show initial download progress message ──
    await callback_query.message.edit_text(
        f"<b>⬇️ Downloading — {display_label}\n\n"
        f"[{'░' * PROGRESS_BAR_LEN}] 0.0%\n\n"
        f"🎬 {safe_title_display}</b>"
    )
    status_msg = callback_query.message

    # ── Download progress callback (receives every 0.1 % step) ──
    async def _dl_progress(percent: float, line: str):
        bar = make_progress_bar(percent)
        try:
            await status_msg.edit_text(
                f"<b>⬇️ Downloading — {display_label}\n\n"
                f"[{bar}] {percent:.1f}%\n\n"
                f"🎬 {safe_title_display}</b>"
            )
        except Exception:
            pass

    # SmoothProgress gates how often Telegram is actually edited (every 2 s),
    # but internally every 0.1 % step is tracked by helpers.py
    smooth_dl = SmoothProgress(_dl_progress, throttle=2.0)

    # ── Proxy so helpers.py progress_callback hits our SmoothProgress ──
    async def progress_callback(percent: float, line: str):
        await smooth_dl.update(percent, line)

    safe_title = sanitize_filename(session["title"])
    output_name = f"{safe_title}_{quality_label}"

    # ── Run download in executor ──
    if is_audio_only:
        file_path = await download_audio_only(
            session["url"],
            audio_formats,
            output_name,
            progress_callback,
            user_id=user_id,
        )
    else:
        file_path = await download_with_ytdlp(
            session["url"],
            video_format,
            audio_formats,
            output_name,
            progress_callback,
            user_id=user_id,
        )

    if not file_path or not os.path.exists(file_path):
        await status_msg.edit_text("<b>❌ Download Failed\nTry Another Quality Or Contact Support</b>")
        return

    file_size       = os.path.getsize(file_path)
    file_size_mb    = file_size / (1024 * 1024)
    chat_id         = session.get("chat_id", callback_query.message.chat.id)
    remote_thumb    = session.get("thumb") or None

    caption = (
        f"<b>🎬 {safe_title_display}</b>\n"
        f"<b>📺 Episode:</b> {escape_html(session['episode']) or 'N/A'}\n"
        f"<b>📦 Season:</b> {escape_html(session['season']) or 'N/A'}\n"
        f"<b>🎯 Quality:</b> {display_label}\n\n"
        f"<i>Downloaded via @DsrBotzz</i>"
    )

    # ════════════════════════════════════════════
    # AUDIO-ONLY UPLOAD (no splitting needed)
    # ════════════════════════════════════════════
    if is_audio_only:
        await status_msg.edit_text(
            f"<b>📤 Uploading — {display_label}\n\n"
            f"[{'░' * PROGRESS_BAR_LEN}] 0.0%\n\n"
            f"📦 Size: {file_size_mb:.1f} MB\n"
            f"🎬 {safe_title_display}</b>"
        )

        upload_start     = time.time()
        last_upload_edit = [0.0]

        async def audio_upload_progress(current: int, total: int):
            now = time.time()
            if current < total and now - last_upload_edit[0] < 2.0:
                return
            last_upload_edit[0] = now
            percent  = (current / total) * 100
            bar      = make_progress_bar(percent)
            elapsed  = now - upload_start
            speed    = current / elapsed if elapsed > 0 else 0
            speed_mb = speed / (1024 * 1024)
            remaining = (total - current) / speed if speed > 0 else 0
            try:
                await status_msg.edit_text(
                    f"<b>📤 Uploading — {display_label}\n\n"
                    f"[{bar}] {percent:.1f}%\n\n"
                    f"⚡ Speed: {speed_mb:.2f} MB/s\n"
                    f"⏱ ETA: {int(remaining)}s\n"
                    f"📦 {current/(1024*1024):.1f} / {total/(1024*1024):.1f} MB\n"
                    f"🎬 {safe_title_display}</b>"
                )
            except Exception:
                pass

        try:
            await client.send_audio(
                chat_id,
                file_path,
                caption=caption,
                progress=audio_upload_progress,
            )
        except Exception as e:
            await status_msg.edit_text(f"<b>❌ Upload Failed: {escape_html(str(e))}</b>")
            return

        await _finalize(status_msg, file_path, user_id, session)
        return

    # ════════════════════════════════════════════
    # VIDEO UPLOAD  (with split + thumbnail logic)
    # ════════════════════════════════════════════

    # ── Generate thumbnail from the actual video file ──
    await status_msg.edit_text(
        f"<b>🖼️ Generating Thumbnail...\n\n"
        f"📦 Size: {file_size_mb:.1f} MB\n"
        f"🎬 {safe_title_display}</b>"
    )
    loop = asyncio.get_event_loop()
    thumb_path = await loop.run_in_executor(
        _executor,
        generate_thumbnail,
        file_path,
        remote_thumb,
    )

    # ── Decide: split or upload directly ──
    if file_size > MAX_UPLOAD_SIZE_BYTES:
        # ── File is > 1.85 GB — split it ──
        size_gb = file_size / (1024 ** 3)
        await status_msg.edit_text(
            f"<b>✂️ File is {size_gb:.2f} GB — Splitting into parts...\n\n"
            f"🎬 {safe_title_display}</b>"
        )

        try:
            parts = await loop.run_in_executor(_executor, split_video_file, file_path)
        except Exception as e:
            await status_msg.edit_text(
                f"<b>❌ Splitting Failed: {escape_html(str(e))}</b>"
            )
            return

        total_parts = len(parts)
        await status_msg.edit_text(
            f"<b>✅ Split into {total_parts} part(s)\n"
            f"📤 Uploading parts...\n\n"
            f"🎬 {safe_title_display}</b>"
        )

        for idx, part_path in enumerate(parts, start=1):
            part_size_mb = os.path.getsize(part_path) / (1024 * 1024)
            part_caption = (
                f"<b>🎬 {safe_title_display}</b>\n"
                f"<b>📺 Episode:</b> {escape_html(session['episode']) or 'N/A'}\n"
                f"<b>📦 Season:</b> {escape_html(session['season']) or 'N/A'}\n"
                f"<b>🎯 Quality:</b> {display_label}\n"
                f"<b>📂 Part:</b> {idx} / {total_parts}\n\n"
                f"<i>Downloaded via @DsrBotzz</i>"
            )
            part_label = f" (Part {idx}/{total_parts})"

            await status_msg.edit_text(
                f"<b>📤 Uploading Part {idx}/{total_parts} — {display_label}\n\n"
                f"[{'░' * PROGRESS_BAR_LEN}] 0.0%\n\n"
                f"📦 Size: {part_size_mb:.1f} MB\n"
                f"🎬 {safe_title_display}</b>"
            )

            success = await _upload_video_part(
                client, chat_id, part_path, part_caption,
                thumb_path, status_msg, display_label,
                safe_title_display, part_label,
            )

            # Clean up part file after upload
            if os.path.exists(part_path):
                os.remove(part_path)

            if not success:
                # Clean remaining parts
                for remaining in parts[idx:]:
                    if os.path.exists(remaining):
                        os.remove(remaining)
                return

    else:
        # ── File ≤ 1.85 GB — upload directly ──
        await status_msg.edit_text(
            f"<b>📤 Uploading — {display_label}\n\n"
            f"[{'░' * PROGRESS_BAR_LEN}] 0.0%\n\n"
            f"📦 Size: {file_size_mb:.1f} MB\n"
            f"🎬 {safe_title_display}</b>"
        )

        success = await _upload_video_part(
            client, chat_id, file_path, caption,
            thumb_path, status_msg, display_label,
            safe_title_display,
        )
        if not success:
            return

    await _finalize(status_msg, file_path, user_id, session, thumb_path)


# ──────────────────────────────────────────────
# FINALIZE: cleanup + log
# ──────────────────────────────────────────────

async def _finalize(
    status_msg,
    file_path: str,
    user_id: int,
    session: dict,
    thumb_path: str | None = None,
):
    await status_msg.delete()
    await increment_download(user_id)
    await log_download(user_id, session["title"], session["url"], "")

    for path in [file_path, thumb_path]:
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except Exception:
                pass

    sessions.pop(user_id, None)


# ──────────────────────────────────────────────
# CANCEL HANDLER
# ──────────────────────────────────────────────

@Client.on_callback_query(filters.regex(r"^cancel_(\d+)$"))
async def handle_cancel(client: Client, callback_query: CallbackQuery):
    user_id = int(callback_query.data.split("_")[1])
    if callback_query.from_user.id != user_id:
        await callback_query.answer("❌ Not your session!", show_alert=True)
        return
    sessions.pop(user_id, None)
    await callback_query.message.delete()
    await callback_query.answer("✅ Cancelled")
