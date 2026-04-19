# 🎬 DsrBotz MX Player Downloader Bot

A Telegram bot to download MX Player / MXPlay videos in any available quality using **Yt-dlp**.

---

## 📁 File Structure

```
mxbot/
├── bot.py              # Entry point — app.run()
├── config.py           # Env variable config
├── database.py         # MongoDB (Motor async) helper
├── helpers.py          # API + N_m3u8DL-RE download logic
├── requirements.txt    # Python dependencies
└── plugins/
    ├── commands.py     # /start /help /stats
    └── downloader.py   # Link handler + quality picker + download/upload
```

---

## ⚙️ Setup

### 1. Install Python Dependencies
```bash
pip install -r requirements.txt
```

### 2. Install N_m3u8DL-RE
Download from: https://github.com/nilaoda/N_m3u8DL-RE/releases

Place the binary in your PATH:
```bash
# Linux / macOS
chmod +x N_m3u8DL-RE
sudo mv N_m3u8DL-RE /usr/local/bin/

# Verify
N_m3u8DL-RE --version
```

### 3. Set Environment Variables
```bash
export API_ID="your_api_id"
export API_HASH="your_api_hash"
export BOT_TOKEN="your_bot_token"
export MONGO_URI="mongodb://localhost:27017"   # or MongoDB Atlas URI
export DB_NAME="dsrbotz_mx"
```

### 4. Run The Bot
```bash
python bot.py
```

---

## 🔄 Flow

1. User sends MX Player link
2. Bot calls `https://ott.dkbotzpro.in/mxplayer?url=...` to resolve m3u8/mpd
3. Bot runs `N_m3u8DL-RE --list-all` to detect all available qualities
4. User sees inline buttons: `🎬 1080p [1920x1080]`, `🎬 720p`, etc.
5. On tap → download with live progress bar → upload with speed/ETA

---

## Credit :- Anonymous, DK, Shivam, hydrogram 

## 🗄️ MongoDB Collections

| Collection  | Purpose                          |
|-------------|----------------------------------|
| `users`     | User records, join date, count   |
| `downloads` | Per-download log with quality    |

---

## 📦 Dependencies

| Package        | Purpose                    |
|----------------|----------------------------|
| hydrogram      | Telegram MTProto client    |
| TgCrypto       | Speed boost for Pyrogram   |
| motor          | Async MongoDB driver       |
| aiohttp        | Async HTTP for API calls   |
| yt-dlp  | m3u8/mpd stream downloader |
