import os
import json
import uuid
import shutil
import subprocess
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional

from core.config import BASE_DIR, UPLOAD_DIR, OUTPUT_DIR, FFMPEG_PATH, FFPROBE_PATH
from core.downloader import fetch_stream_audio, fetch_clip_video, get_download_state
from core.audio_detector import detect_audio_highlights
from core.transcriber import transcribe_clip
from core.subtitles import generate_animated_ass
from core.video_processor import render_vertical_clip

app = FastAPI(title="ClipForge - Smart AI Clipping Platform")

STATIC_DIR = BASE_DIR / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

def get_video_duration(file_path: str) -> float:
    """Gets video duration in seconds via ffprobe."""
    try:
        cmd = [
            FFPROBE_PATH,
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(file_path)
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return float(res.stdout.strip())
    except Exception:
        return 0.0

@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")

class AnalyzeUrlRequest(BaseModel):
    url: str

@app.get("/api/download-progress")
def api_download_progress():
    return get_download_state()

@app.post("/api/analyze-url")
def api_analyze_url(req: AnalyzeUrlRequest):
    """
    Automated stream clipping:
    1. Fetches lightweight audio track via native multi-thread yt-dlp.
    2. Runs AI highlight detection automatically.
    3. Returns top viral clips ready to render!
    """
    try:
        stream_info = fetch_stream_audio(req.url)
        highlights = detect_audio_highlights(
            stream_info["audio_path"],
            min_clip_duration=25.0,
            max_clip_duration=55.0,
            max_clips=6
        )
        return {
            "status": "success",
            "title": stream_info["title"],
            "duration": stream_info["duration"],
            "url": req.url,
            "audio_path": stream_info["audio_path"],
            "highlights": highlights
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/upload")
async def api_upload(file: UploadFile = File(...)):
    try:
        file_ext = Path(file.filename).suffix or ".mp4"
        clean_name = f"upload_{uuid.uuid4().hex[:8]}_{Path(file.filename).stem[:30]}{file_ext}"
        saved_path = UPLOAD_DIR / clean_name
        
        with open(saved_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        dur = get_video_duration(str(saved_path))
        
        return {
            "status": "success",
            "video": {
                "id": str(uuid.uuid4())[:8],
                "title": Path(file.filename).stem,
                "duration": round(dur, 2),
                "file_path": str(saved_path),
                "filename": clean_name,
                "source": "local"
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/videos")
def list_videos():
    videos = []
    for f in UPLOAD_DIR.glob("*.*"):
        if f.suffix.lower() in [".mp4", ".mkv", ".mov", ".webm", ".avi", ".m4a"]:
            if f.name.endswith(".part") or f.name.endswith(".ytdl") or ".part-Frag" in f.name or f.name.startswith("slice_") or f.name.startswith("test_"):
                continue
            meta_file = f.with_suffix(".json")
            meta = {}
            if meta_file.exists():
                try:
                    with open(meta_file, "r", encoding="utf-8") as mf:
                        meta = json.load(mf)
                except Exception:
                    pass

            title = meta.get("title") or f.stem
            dur = meta.get("duration") or get_video_duration(str(f))
            videos.append({
                "filename": f.name,
                "file_path": str(f.resolve()),
                "title": title,
                "duration": dur,
                "url": meta.get("url"),
                "highlights": meta.get("highlights", []),
                "is_stream": bool(meta.get("url") or f.name.startswith("audio_")),
                "size_mb": round(f.stat().st_size / (1024 * 1024), 2),
                "modified": f.stat().st_mtime
            })
    videos.sort(key=lambda x: x["modified"], reverse=True)
    return videos

class HighlightRequest(BaseModel):
    file_path: str
    min_duration: Optional[float] = 20.0
    max_duration: Optional[float] = 50.0

@app.post("/api/detect-highlights")
def api_highlights(req: HighlightRequest):
    p = Path(req.file_path)
    if not p.exists():
        raise HTTPException(status_code=404, detail="Video file not found")

    # Fast cache return
    meta_file = p.with_suffix(".json")
    if meta_file.exists():
        try:
            with open(meta_file, "r", encoding="utf-8") as f:
                meta = json.load(f)
                if meta.get("highlights"):
                    return {"status": "success", "highlights": meta["highlights"]}
        except Exception:
            pass

    try:
        clips = detect_audio_highlights(
            str(p),
            min_clip_duration=req.min_duration,
            max_clip_duration=req.max_duration
        )
        try:
            existing = {}
            if meta_file.exists():
                with open(meta_file, "r", encoding="utf-8") as f:
                    existing = json.load(f)
            existing["highlights"] = clips
            with open(meta_file, "w", encoding="utf-8") as f:
                json.dump(existing, f, indent=2)
        except Exception:
            pass
        return {"status": "success", "highlights": clips}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Highlight detection failed: {str(e)}")

import time
import queue
import threading

class CreateClipRequest(BaseModel):
    file_path: Optional[str] = None
    url: Optional[str] = None
    title: Optional[str] = None
    start: float
    end: float
    layout: Optional[str] = "blur_background"
    enable_subtitles: Optional[bool] = True
    subtitle_color: Optional[str] = "yellow"

render_tasks = {}
render_queue = queue.Queue()

def render_worker():
    """Background worker for batch and async clip rendering."""
    while True:
        task = render_queue.get()
        if task is None:
            break
        task_id = task["task_id"]
        req = task["req"]
        try:
            render_tasks[task_id]["status"] = "processing"
            result = run_clip_pipeline(req, task_id=task_id)
            render_tasks[task_id].update({
                "status": "completed",
                "percent": 100,
                "stage": "Finished!",
                "clip_url": result["clip_url"],
                "clip_filename": result["clip_filename"],
                "title": result.get("title", "")
            })
        except Exception as e:
            render_tasks[task_id].update({
                "status": "error",
                "error": str(e),
                "stage": f"Failed: {str(e)}"
            })
        finally:
            render_queue.task_done()

# Start background render worker
_worker_thread = threading.Thread(target=render_worker, daemon=True)
_worker_thread.start()

def run_clip_pipeline(req: CreateClipRequest, task_id: Optional[str] = None) -> dict:
    temp_slice = None
    ass_path = None
    try:
        if task_id:
            render_tasks[task_id].update({"stage": "Fetching video slice...", "percent": 25})

        if req.url:
            temp_slice = fetch_clip_video(req.url, req.start, req.end)
            source_video = temp_slice
            slice_start = 0.0
            slice_end = req.end - req.start
        elif req.file_path and Path(req.file_path).exists():
            source_video = req.file_path
            slice_start = req.start
            slice_end = req.end
        else:
            raise HTTPException(status_code=400, detail="Missing source video or URL")

        # Step 1: Subtitle transcription if enabled
        if req.enable_subtitles:
            if task_id:
                render_tasks[task_id].update({"stage": "Transcribing speech...", "percent": 55})
            try:
                words = transcribe_clip(source_video, slice_start, slice_end, model_size="tiny")
                if words:
                    temp_ass = UPLOAD_DIR / f"sub_{uuid.uuid4().hex[:8]}.ass"
                    generate_animated_ass(
                        words=words,
                        output_ass_path=str(temp_ass),
                        highlight_color=req.subtitle_color or "yellow"
                    )
                    ass_path = str(temp_ass)
            except Exception as e:
                print(f"Transcription warning: {e}. Proceeding without subtitles.")

        # Step 2: Render 9:16 vertical clip
        if task_id:
            render_tasks[task_id].update({"stage": "Rendering 9:16 layout & subtitles...", "percent": 80})

        clip_name = f"clip_{uuid.uuid4().hex[:8]}.mp4"
        out_path = render_vertical_clip(
            video_path=source_video,
            start=slice_start,
            end=slice_end,
            layout=req.layout or "blur_background",
            subtitle_ass_path=ass_path,
            output_filename=clip_name
        )

        # Save clip metadata for chaining and 'Clip Next Part'
        clip_meta = {
            "filename": clip_name,
            "url": f"/media/output/{clip_name}",
            "title": req.title or f"Clip ({req.start:.1f}s - {req.end:.1f}s)",
            "start": round(req.start, 2),
            "end": round(req.end, 2),
            "duration": round(req.end - req.start, 2),
            "source_url": req.url,
            "source_file": req.file_path,
            "layout": req.layout or "blur_background",
            "created_at": time.time()
        }
        with open(OUTPUT_DIR / f"{clip_name}.json", "w", encoding="utf-8") as f:
            json.dump(clip_meta, f, indent=2)

        return {
            "status": "success",
            "clip_filename": clip_name,
            "clip_url": f"/media/output/{clip_name}",
            "file_path": out_path,
            "title": clip_meta["title"],
            "start": clip_meta["start"],
            "end": clip_meta["end"],
            "duration": clip_meta["duration"]
        }
    finally:
        if ass_path and Path(ass_path).exists():
            try:
                Path(ass_path).unlink()
            except Exception:
                pass
        if temp_slice and Path(temp_slice).exists():
            try:
                Path(temp_slice).unlink()
            except Exception:
                pass

@app.post("/api/create-clip")
def api_create_clip(req: CreateClipRequest):
    try:
        return run_clip_pipeline(req)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Rendering failed: {str(e)}")

@app.post("/api/create-clip-async")
def api_create_clip_async(req: CreateClipRequest):
    task_id = f"task_{uuid.uuid4().hex[:8]}"
    render_tasks[task_id] = {
        "task_id": task_id,
        "title": req.title or f"Clip ({req.start:.0f}s - {req.end:.0f}s)",
        "status": "queued",
        "stage": "Waiting in queue...",
        "percent": 0,
        "start": req.start,
        "end": req.end
    }
    render_queue.put({"task_id": task_id, "req": req})
    return {"status": "queued", "task_id": task_id}

class BatchClipsRequest(BaseModel):
    url: Optional[str] = None
    file_path: Optional[str] = None
    clips: list
    layout: Optional[str] = "blur_background"
    enable_subtitles: Optional[bool] = True
    subtitle_color: Optional[str] = "yellow"

@app.post("/api/batch-create-clips")
def api_batch_create_clips(req: BatchClipsRequest):
    queued = []
    for c in req.clips:
        task_id = f"task_{uuid.uuid4().hex[:8]}"
        clip_req = CreateClipRequest(
            url=req.url,
            file_path=req.file_path,
            title=c.get("label") or f"Clip ({c['start']:.0f}s - {c['end']:.0f}s)",
            start=float(c["start"]),
            end=float(c["end"]),
            layout=req.layout,
            enable_subtitles=req.enable_subtitles,
            subtitle_color=req.subtitle_color
        )
        render_tasks[task_id] = {
            "task_id": task_id,
            "title": clip_req.title,
            "status": "queued",
            "stage": "Waiting in queue...",
            "percent": 0,
            "start": clip_req.start,
            "end": clip_req.end
        }
        render_queue.put({"task_id": task_id, "req": clip_req})
        queued.append(task_id)
    return {"status": "batch_queued", "total": len(queued), "task_ids": queued}

@app.get("/api/render-tasks")
def api_render_tasks():
    return list(render_tasks.values())[-10:]

@app.get("/api/clips")
def list_clips():
    clips = []
    for f in OUTPUT_DIR.glob("*.mp4"):
        meta = {}
        meta_file = OUTPUT_DIR / f"{f.name}.json"
        if meta_file.exists():
            try:
                with open(meta_file, "r", encoding="utf-8") as mf:
                    meta = json.load(mf)
            except Exception:
                pass

        title = meta.get("title") or f.stem
        start = meta.get("start", 0.0)
        end = meta.get("end", 0.0)
        duration = meta.get("duration") or get_video_duration(str(f))

        clips.append({
            "filename": f.name,
            "url": f"/media/output/{f.name}",
            "title": title,
            "start": start,
            "end": end,
            "duration": duration,
            "source_url": meta.get("source_url"),
            "source_file": meta.get("source_file"),
            "size_mb": round(f.stat().st_size / (1024 * 1024), 2),
            "modified": f.stat().st_mtime
        })
    clips.sort(key=lambda x: x["modified"], reverse=True)
    return clips

@app.get("/media/uploads/{filename}")
def stream_upload(filename: str):
    path = UPLOAD_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path, media_type="video/mp4")

@app.get("/media/output/{filename}")
def stream_output(filename: str):
    path = OUTPUT_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path, media_type="video/mp4")
