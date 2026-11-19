import json
import subprocess
import tempfile
import numpy as np
from pathlib import Path
from scipy.io import wavfile
from core.config import FFMPEG_PATH

def extract_fast_audio(video_path: str) -> str:
    """Extracts lightweight mono 16kHz WAV audio using FFmpeg."""
    temp_wav = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    temp_wav.close()
    
    cmd = [
        FFMPEG_PATH,
        "-y",
        "-i", str(video_path),
        "-vn",
        "-ac", "1",
        "-ar", "4000",
        "-f", "wav",
        temp_wav.name
    ]
    
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    return temp_wav.name

def detect_audio_highlights(video_path: str, min_clip_duration: float = 25.0, max_clip_duration: float = 50.0, max_clips: int = 5) -> list:
    """
    Scans audio volume & energy peaks offline.
    Detects moments of laughter, yelling, hype, and intense action.
    Returns ranked list of candidate clip timestamps.
    Caches detected peaks locally for instant re-mining.
    """
    cache_path = Path(str(video_path) + "_peaks_cache.json")
    if cache_path.exists():
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                cached = json.load(f)
                if isinstance(cached, list) and len(cached) >= max_clips:
                    return cached[:max_clips]
                elif isinstance(cached, list) and len(cached) > 0:
                    return cached
        except Exception:
            pass

    wav_path = None
    try:
        wav_path = extract_fast_audio(video_path)
        sample_rate, data = wavfile.read(wav_path)
        
        # Convert to float array
        if data.dtype != np.float32 and data.dtype != np.float64:
            data = data.astype(np.float32) / (np.iinfo(data.dtype).max if np.issubdtype(data.dtype, np.integer) else 1.0)
            
        total_seconds = len(data) / sample_rate
        if total_seconds < min_clip_duration:
            return [{
                "start": 0.0,
                "end": round(total_seconds, 2),
                "duration": round(total_seconds, 2),
                "score": 100,
                "label": "Full Video Clip"
            }]

        # Compute RMS energy per 0.5 second frame
        frame_len = int(sample_rate * 0.5)
        num_frames = len(data) // frame_len
        if num_frames == 0:
            return []
            
        reshaped = data[:num_frames * frame_len].reshape(num_frames, frame_len)
        rms_energy = np.sqrt(np.mean(reshaped ** 2, axis=1))

        # Smooth RMS energy with a sliding window (~3 seconds)
        window_size = 6
        smoothed = np.convolve(rms_energy, np.ones(window_size) / window_size, mode='same')
        
        # Baseline noise floor
        median_energy = np.median(smoothed)
        std_energy = np.std(smoothed)
        threshold = median_energy + 0.5 * std_energy

        # Find continuous peaks above threshold
        candidates = []
        is_above = smoothed > threshold
        start_frame = None

        for idx, val in enumerate(is_above):
            if val and start_frame is None:
                start_frame = idx
            elif not val and start_frame is not None:
                end_frame = idx
                peak_time = ((start_frame + end_frame) / 2) * 0.5
                peak_val = np.max(smoothed[start_frame:end_frame])
                candidates.append((peak_time, peak_val))
                start_frame = None
                
        if start_frame is not None:
            peak_time = ((start_frame + len(is_above)) / 2) * 0.5
            peak_val = np.max(smoothed[start_frame:])
            candidates.append((peak_time, peak_val))

        # If no significant peaks, divide video into high-activity sections
        if not candidates:
            step = total_seconds / (max_clips + 1)
            for i in range(1, max_clips + 1):
                candidates.append((i * step, float(smoothed[int(min(i * step * 2, len(smoothed) - 1))])))

        # Sort candidate peaks by loudness/energy
        candidates.sort(key=lambda x: x[1], reverse=True)

        selected_clips = []
        target_duration = (min_clip_duration + max_clip_duration) / 2

        for peak_time, peak_val in candidates:
            # Build window around peak (lead-in 40% before peak, 60% after peak for punchline/reaction)
            start = max(0.0, peak_time - (target_duration * 0.4))
            end = min(total_seconds, start + target_duration)
            start = max(0.0, end - target_duration)

            # Check for overlap with already selected clips
            overlap = False
            for sc in selected_clips:
                if not (end < sc["start"] or start > sc["end"]):
                    overlap = True
                    break

            if not overlap:
                # Calculate normalized score (0-100)
                norm_score = min(100, int(50 + (peak_val / (np.max(smoothed) + 1e-6)) * 50))
                selected_clips.append({
                    "start": round(start, 2),
                    "end": round(end, 2),
                    "duration": round(end - start, 2),
                    "score": norm_score,
                    "label": f"Highlight #{len(selected_clips) + 1} (Score: {norm_score}%)"
                })

            if len(selected_clips) >= max_clips:
                break

        # Sort chronologically for natural presentation
        selected_clips.sort(key=lambda x: x["start"])

        # Cache peaks for instant retrieval
        try:
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(selected_clips, f, indent=2)
        except Exception:
            pass

        return selected_clips

    finally:
        if wav_path and Path(wav_path).exists():
            try:
                Path(wav_path).unlink()
            except Exception:
                pass
