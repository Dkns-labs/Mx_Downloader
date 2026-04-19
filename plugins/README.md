# MX Player Downloader Bot - YT-DLP Version

## 🎯 What's Changed

This updated version replaces `N_m3u8DL-RE` with `yt-dlp` for more reliable downloading and adds a **two-step format selection** process:

1. **Step 1**: Select Video Quality (or choose Audio-Only mode)
2. **Step 2**: Select Audio Track(s) - supports multiple audio languages

## ✨ New Features

### 1. **Two-Step Selection Process**
- First, choose your preferred video quality
- Then, select one or more audio tracks (different languages)
- Option to skip audio selection (uses best available)
- Option to download audio-only

### 2. **Multiple Audio Track Support**
- Select multiple audio tracks in different languages
- Each track shows bitrate and language
- Tracks are merged into the final video

### 3. **Better Format Detection**
- Shows resolution, file size, and codec for each format
- Displays video formats first (sorted by quality)
- Then shows audio formats (sorted by bitrate)
- Shows language labels for audio tracks (Hindi, English, Tamil, etc.)

### 4. **Audio-Only Mode**
- Download just the audio without video
- Supports multiple audio tracks
- Output in MP3 format

## 📋 Requirements

### Install yt-dlp
```bash
# Option 1: Using pip
pip install yt-dlp

# Option 2: Using apt (Debian/Ubuntu)
sudo apt update
sudo apt install yt-dlp

# Option 3: Download binary
sudo wget https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp -O /usr/local/bin/yt-dlp
sudo chmod a+rx /usr/local/bin/yt-dlp
```

### Install ffmpeg (required for format conversion)
```bash
sudo apt update
sudo apt install ffmpeg
```

### Python Dependencies
No changes to existing dependencies. Make sure you have:
- pyrogram
- aiohttp
- Your database module

## 🎮 How to Use

### For Users:

1. **Send MX Player Link**
   - Bot shows video information with thumbnail
   - Displays all available video qualities

2. **Select Video Quality**
   - Tap on your preferred video quality
   - OR tap "🎵 Audio Only" for audio-only download

3. **Select Audio Track(s)**
   - Tap on one or more audio tracks
   - Selected tracks show a checkmark (✓)
   - Tap "✅ Done" when finished
   - OR tap "⏭️ Skip Audio" to use default audio

4. **Download Starts**
   - Bot downloads and uploads the file
   - Shows real-time progress

## 🔧 Configuration

### Environment Variables (Optional)

```bash
# Download directory (default: /tmp)
export DOWNLOAD_DIR="/path/to/downloads"
```

## 📝 File Changes

### `helpers.py`
- ✅ Replaced `N_m3u8DL-RE` functions with `yt-dlp`
- ✅ New `get_available_formats()` - returns separate video/audio formats
- ✅ New `download_with_ytdlp()` - downloads video with selected audio tracks
- ✅ New `download_audio_only()` - downloads audio-only in MP3
- ✅ Better format parsing with file sizes and language detection

### `downloader.py`
- ✅ Two-step selection flow (video → audio)
- ✅ Session management for multi-step selection
- ✅ Toggle audio track selection (select multiple)
- ✅ Audio-only mode support
- ✅ Visual feedback with checkmarks for selected audio tracks
- ✅ Skip audio option

### `commands.py`
- ℹ️ No changes required

## 🎨 UI Flow

```
User sends link
    ↓
Bot shows video qualities
    ↓
User selects video quality (or Audio-Only)
    ↓
Bot shows audio tracks
    ↓
User selects audio track(s) (can select multiple)
    ↓
User clicks "Done" or "Skip Audio"
    ↓
Download starts
    ↓
File uploaded to user
```

## 🔍 Format Display Examples

### Video Formats:
```
🎬 1080p - 1920x1080 (245.5 MB) - mp4
🎬 720p - 1280x720 (156.2 MB) - mp4
🎬 480p - 854x480 (89.1 MB) - mp4
🎬 360p - 640x360 (45.3 MB) - mp4
```

### Audio Formats:
```
🎵 128kbps - Hindi (12.5 MB) - m4a
🎵 128kbps - English (12.3 MB) - m4a
🎵 64kbps - Tamil (6.2 MB) - m4a
```

## ⚠️ Important Notes

1. **yt-dlp is more reliable** than N_m3u8DL-RE for most streaming services
2. **Multiple audio tracks** are merged into a single file
3. **File sizes** are approximate and shown when available
4. **Language detection** works for common Indian languages
5. **Audio-only downloads** are converted to MP3 format

## 🐛 Troubleshooting

### "No formats detected"
- The URL might not be accessible
- yt-dlp might need updating: `yt-dlp -U`

### "Download failed"
- Check if ffmpeg is installed
- Verify internet connection
- Try a different quality

### Slow downloads
- This is normal for large files
- Progress is shown in real-time

## 📦 Installation

1. Replace your old `helpers.py` and `downloader.py` with the new versions
2. Install yt-dlp and ffmpeg
3. Restart your bot
4. Test with an MX Player link

## 🎉 Enjoy!

Your bot now has a much better format selection system with support for multiple audio tracks and more reliable downloads!
