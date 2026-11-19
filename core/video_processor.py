import subprocess
import uuid
from pathlib import Path
from core.config import FFMPEG_PATH, OUTPUT_DIR

def escape_ffmpeg_path(path_str: str) -> str:
    """Escapes Windows path for FFmpeg filter graph syntax."""
    p = str(Path(path_str).resolve()).replace("\\", "/")
    # Escape colon for ffmpeg filter: C:/ -> C\:/
    if ":" in p:
        drive, rest = p.split(":", 1)
        p = f"{drive}\\:{rest}"
    return p

def render_vertical_clip(
    video_path: str,
    start: float,
    end: float,
    layout: str = "blur_background",
    subtitle_ass_path: str = None,
    output_filename: str = None
) -> str:
    """
    Cuts and renders a 1080x1920 vertical clip using FFmpeg CPU optimization.
    """
    duration = end - start
    if not output_filename:
        output_filename = f"clip_{uuid.uuid4().hex[:8]}.mp4"
    output_path = OUTPUT_DIR / output_filename

    # Construct layout filter
    filter_complex_parts = []
    
    if layout == "center_crop":
        # Crop center 9:16 directly
        filter_str = "[0:v]crop=ih*9/16:ih:(iw-ow)/2:0,scale=1080:1920,setsar=1[v_base]"
        filter_complex_parts.append(filter_str)
        last_v_tag = "[v_base]"

    elif layout == "split_screen":
        # Stacks top half (e.g. facecam) and bottom half (gameplay)
        filter_str = (
            "[0:v]split=2[top_in][bot_in];"
            "[top_in]crop=iw:ih*0.5:0:0,scale=1080:768,setsar=1[v_top];"
            "[bot_in]crop=iw:ih*0.6:0:ih*0.4,scale=1080:1152,setsar=1[v_bot];"
            "[v_top][v_bot]vstack=inputs=2[v_base]"
        )
        filter_complex_parts.append(filter_str)
        last_v_tag = "[v_base]"

    else:
        # Default: blur_background (cleanest and most versatile)
        filter_str = (
            "[0:v]split=2[v_fg][v_bg];"
            "[v_bg]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=20:5,eq=brightness=-0.15[bg];"
            "[v_fg]scale=1080:-2[fg];"
            "[bg][fg]overlay=(W-w)/2:(H-h)/2[v_base]"
        )
        filter_complex_parts.append(filter_str)
        last_v_tag = "[v_base]"

    # Subtitle burning
    if subtitle_ass_path and Path(subtitle_ass_path).exists():
        escaped_sub = escape_ffmpeg_path(subtitle_ass_path)
        filter_complex_parts.append(f"{last_v_tag}ass='{escaped_sub}'[v_out]")
        final_v_map = "[v_out]"
    else:
        final_v_map = last_v_tag

    full_filter = ";".join(filter_complex_parts)

    cmd = [
        FFMPEG_PATH,
        "-y",
        "-ss", str(start),
        "-t", str(duration),
        "-i", str(video_path),
        "-filter_complex", full_filter,
        "-map", final_v_map,
        "-map", "0:a?",
        "-c:v", "libx264",
        "-preset", "ultrafast",  # Fast CPU encoding for low-spec laptop
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "128k",
        "-movflags", "+faststart",
        str(output_path)
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        # If ass filter fails (e.g. missing libass in ffmpeg build), retry without subtitles as fallback
        if subtitle_ass_path and "ass" in full_filter:
            cmd_fallback = [
                FFMPEG_PATH,
                "-y",
                "-ss", str(start),
                "-t", str(duration),
                "-i", str(video_path),
                "-filter_complex", filter_complex_parts[0],
                "-map", last_v_tag,
                "-map", "0:a?",
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-crf", "23",
                "-c:a", "aac",
                "-b:a", "128k",
                "-movflags", "+faststart",
                str(output_path)
            ]
            subprocess.run(cmd_fallback, check=True)
        else:
            raise RuntimeError(f"FFmpeg rendering failed: {result.stderr}")

    return str(output_path)
