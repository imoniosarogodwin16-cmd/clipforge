import subprocess
import tempfile
import numpy as np
from pathlib import Path
from scipy.io import wavfile
from faster_whisper import WhisperModel
from core.config import FFMPEG_PATH, MODELS_DIR

_model_cache = {}

def get_whisper_model(model_size: str = "tiny"):
    """Loads and caches the Whisper model in int8 CPU mode."""
    if model_size not in _model_cache:
        # compute_type='int8' runs optimized on standard CPU without heavy memory or GPU
        _model_cache[model_size] = WhisperModel(
            model_size,
            device="cpu",
            compute_type="int8",
            download_root=str(MODELS_DIR)
        )
    return _model_cache[model_size]

def extract_audio_segment(video_path: str, start: float, duration: float) -> str:
    """Extracts a slice of audio for transcription."""
    temp_wav = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    temp_wav.close()

    cmd = [
        FFMPEG_PATH,
        "-y",
        "-ss", str(start),
        "-t", str(duration),
        "-i", str(video_path),
        "-vn",
        "-ac", "1",
        "-ar", "16000",
        temp_wav.name
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    return temp_wav.name

def transcribe_clip(video_path: str, start: float, end: float, model_size: str = "tiny") -> list:
    """
    Transcribes a video segment and returns word-level timestamps relative to clip start (0.0s).
    """
    duration = end - start
    temp_audio = None
    try:
        temp_audio = extract_audio_segment(video_path, start, duration)
        model = get_whisper_model(model_size)
        
        # Load audio into numpy float32 array to bypass PyAV metadata_errors bug
        sample_rate, data = wavfile.read(temp_audio)
        if data.dtype != np.float32 and data.dtype != np.float64:
            data = data.astype(np.float32) / (np.iinfo(data.dtype).max if np.issubdtype(data.dtype, np.integer) else 1.0)

        segments, info = model.transcribe(
            data,
            word_timestamps=True,
            vad_filter=True, # filter out non-speech silence
            vad_parameters=dict(min_silence_duration_ms=500)
        )

        words_data = []
        for segment in segments:
            if segment.words:
                for w in segment.words:
                    word_text = w.word.strip()
                    if word_text:
                        words_data.append({
                            "word": word_text,
                            "start": round(w.start, 2),
                            "end": round(w.end, 2)
                        })
        return words_data
    finally:
        if temp_audio and Path(temp_audio).exists():
            try:
                Path(temp_audio).unlink()
            except Exception:
                pass
