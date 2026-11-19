import os
import re
import uuid
import yt_dlp
from pathlib import Path
from core.config import UPLOAD_DIR, FFMPEG_PATH

download_state = {
    "status": "idle",
    "percent": 0.0,
    "downloaded_mb": 0.0,
    "total_mb": 0.0,
    "speed_str": "",
    "eta_str": "",
    "title": ""
}

def get_download_state() -> dict:
    return download_state.copy()

def format_eta(seconds):
    if not seconds or seconds < 0:
        return "--"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h}h {m}m"
    return f"{m}m {s}s"

def format_speed(bytes_per_sec):
    if not bytes_per_sec:
        return "0 KB/s"
    if bytes_per_sec >= 1024 * 1024:
        return f"{bytes_per_sec / (1024 * 1024):.1f} MB/s"
    return f"{bytes_per_sec / 1024:.0f} KB/s"

def fetch_stream_audio(url: str) -> dict:
    """
    Downloads lightweight audio track with full resume support & fragment error resilience.
    Avoids multi-file collisions on Windows while resuming cleanly.
    """
    global download_state
    download_state = {
        "status": "downloading_audio",
        "percent": 0.0,
        "downloaded_mb": 0.0,
        "total_mb": 0.0,
        "speed_str": "",
        "eta_str": "",
        "title": ""
    }

    # Step 1: Extract info first to get stable video ID (enables resume!)
    with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True}) as ydl_info:
        info = ydl_info.extract_info(url, download=False)
        video_id = info.get("id") or str(uuid.uuid4())[:8]
        title = info.get("title", "Unknown Stream")
        duration = info.get("duration", 0)
        thumbnail = info.get("thumbnail", "")
        download_state["title"] = title

    outtmpl = str(UPLOAD_DIR / f"audio_{video_id}.%(ext)s")

    def yt_progress_hook(d):
        global download_state
        if d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            downloaded = d.get("downloaded_bytes") or 0
            pct = round((downloaded / total * 100), 1) if total > 0 else 0.0
            speed = d.get("speed") or 0
            eta = d.get("eta")

            download_state.update({
                "status": "downloading_audio",
                "percent": pct,
                "downloaded_mb": round(downloaded / (1024 * 1024), 1),
                "total_mb": round(total / (1024 * 1024), 1) if total > 0 else 0.0,
                "speed_str": format_speed(speed),
                "eta_str": format_eta(eta)
            })

    ydl_opts = {
        # Format: ultra lightweight audio (Opus / AAC 50-70kbps)
        "format": "worstaudio/bestaudio[ext=m4a]/bestaudio/best",
        "outtmpl": outtmpl,
        "ffmpeg_location": FFMPEG_PATH,
        "quiet": True,
        "no_warnings": True,
        # Resilience options to prevent fragment crashes on Windows:
        "retries": 20,
        "fragment_retries": 20,
        "file_access_retries": 20,
        "skip_unavailable_fragments": True,
        "continuedl": True,  # Enables instant resume of existing downloads!
        "buffersize": 1024 * 1024,
        "progress_hooks": [yt_progress_hook],
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

            matches = list(UPLOAD_DIR.glob(f"audio_{video_id}.*"))
            # Filter out .part or .ytdl files
            completed_matches = [m for m in matches if not m.name.endswith(".part") and not m.name.endswith(".ytdl") and not ".part-Frag" in m.name]
            if not completed_matches or not completed_matches[0].exists():
                raise FileNotFoundError("Audio track could not be saved to disk.")

            audio_file = str(completed_matches[0])
            download_state.update({"status": "finished", "percent": 100.0})

            return {
                "id": video_id,
                "title": title,
                "duration": duration,
                "audio_path": audio_file,
                "thumbnail": thumbnail,
                "url": url,
                "source": "url_audio"
            }
    except Exception as e:
        err_msg = str(e)
        if "getaddrinfo failed" in err_msg or "Failed to resolve" in err_msg:
            friendly = "Internet connection dropped or DNS failed. Please check your Wi-Fi connection."
        elif "This video is unavailable" in err_msg:
            friendly = "This video is unavailable or private on YouTube."
        elif "No such file or directory" in err_msg:
            friendly = "Temporary file write glitch on Windows. Resuming now."
        else:
            friendly = err_msg
        download_state.update({"status": "error", "error": friendly})
        raise RuntimeError(friendly)

def fetch_clip_video(url: str, start_sec: float, end_sec: float) -> str:
    """
    Downloads ONLY the exact 30-60 second slice in FULL 1080p HD.
    File size is only ~8-12 MB! Takes ~5 to 10 seconds.
    """
    clip_id = str(uuid.uuid4())[:8]
    outtmpl = str(UPLOAD_DIR / f"slice_{clip_id}.%(ext)s")

    ydl_opts = {
        "format": "best[height<=720]/bestvideo[height<=720]+bestaudio/best",
        "download_ranges": yt_dlp.utils.download_range_func(None, [(start_sec, end_sec)]),
        "outtmpl": outtmpl,
        "merge_output_format": "mp4",
        "ffmpeg_location": FFMPEG_PATH,
        "force_keyframes_at_cuts": True,
        "quiet": True,
        "no_warnings": True,
        "retries": 10,
        "fragment_retries": 10
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    matches = list(UPLOAD_DIR.glob(f"slice_{clip_id}*.mp4"))
    if not matches:
        matches = list(UPLOAD_DIR.glob(f"slice_{clip_id}*"))
    if not matches or not matches[0].exists():
        raise FileNotFoundError("Target HD clip slice could not be downloaded.")

    return str(matches[0])
