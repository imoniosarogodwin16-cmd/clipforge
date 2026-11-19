# ⚡ ClipForge — $0 AI Clipping Studio

A high-performance, automated clipping platform built for creators. Designed to run **100% locally with zero subscription costs** and optimized for **standard CPUs without requiring an expensive GPU**.

---

## ✨ Features

- **💸 100% Free ($0 Budget):** No API keys, no monthly fees, no watermarks, unlimited exports.
- **🌐 Dual-Mode Ingest:**
  - **Online Streams & VODs:** Paste URLs from YouTube, Twitch, Kick, TikTok, Twitter/X, and podcasts.
  - **Offline Files:** Drag-and-drop local `.mp4`, `.mkv`, `.mov`, `.webm` videos directly into the studio.
- **🎯 AI Audio Highlight Detection:** Waveform energy and excitement peak analysis detects screams, laughter, hype, and intense dialogue moments.
- **⚡ Batch Render Queue:** Queue multiple clips or all highlights simultaneously with background progress tracking.
- **⏱️ Flexible Duration Control:** One-click duration presets (`30s`, `1 min`, `2 mins`, `3 mins`, `4 mins`) and manual timestamp trimming.
- **▶️ One-Click "Part 2" Continuation:** Instantly chain subsequent multi-minute parts with automatic timestamp offsets.
- **📱 9:16 Vertical Formatting (TikTok / Reels / Shorts):**
  - **Blurred Background:** Centers widescreen video over a cinematic blurred background.
  - **Center Crop:** Direct 9:16 framing.
  - **Split Screen:** Stacks webcam over gameplay/screen.
- **🗣️ Dynamic Animated Subtitles:** Powered by `faster-whisper` (CPU quantized int8). Generates high-visibility TikTok/MrBeast-style karaoke captions with customizable word highlight colors (Yellow, Neon Green, Cyan, Pink).

---

## 🚀 How to Run Locally

### Option 1: One-Click Launcher (Windows)
Double-click `run.bat` in this folder. It will start the server and open:
```
http://localhost:8000
```

### Option 2: Command Line
```bash
pip install -r requirements.txt
python -m uvicorn app:app --host 127.0.0.1 --port 8000
```

---

## 🌐 Making It Live (Cloud & Free Public URL)

### Recommended: Free Live URL via Cloudflare Tunnel ($0 / No RAM limits)
Because video encoding and Whisper AI require ~1.5 GB RAM, running locally and exposing via a free tunnel gives you unlimited speed with $0 cost:
```bash
# 1. Download cloudflared (or run via npx)
npx cloudflared tunnel --url http://localhost:8000
```
This gives you an instant free `https://your-name.trycloudflare.com` URL accessible from any phone or computer!

### Deploying to Render / Railway / Docker
A production `Dockerfile` and `render.yaml` are included in the repository.
1. Push this repository to your GitHub account.
2. In Render, create a new **Web Service** from your GitHub repository.
3. Select Docker or Python environment. Render will automatically detect `render.yaml`.
*(Note: For cloud hosting, a 2GB+ RAM plan is recommended for 1080p video rendering).*

---

## 📁 Project Structure

```
c:\Users\speed\Desktop\clip\
├── core/
│   ├── config.py           # Auto-detection of FFmpeg and paths
│   ├── downloader.py       # Online stream & video downloader (yt-dlp)
│   ├── audio_detector.py   # Waveform energy & hype detection
│   ├── transcriber.py      # Whisper speech-to-text (CPU int8)
│   ├── subtitles.py        # Animated TikTok karaoke ASS subtitle generator
│   └── video_processor.py  # 9:16 vertical video rendering engine
├── static/
│   ├── index.html          # Creator dashboard
│   ├── style.css           # Sleek dark theme UI
│   └── app.js             # Queue, trimmer, batch & continuation logic
├── uploads/                # Cached audio and source media
├── output/                 # Exported vertical clips
├── app.py                  # FastAPI server with background queue
├── Dockerfile              # Container deployment
├── render.yaml             # Render cloud blueprint
└── run.bat                 # One-click Windows desktop launcher
```
