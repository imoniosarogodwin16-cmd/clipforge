import os
import sys
import shutil
from pathlib import Path

# Base Paths
BASE_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "output"
MODELS_DIR = BASE_DIR / "models"

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
MODELS_DIR.mkdir(parents=True, exist_ok=True)

def find_binary(binary_name: str) -> str:
    """Finds an executable in PATH or standard Windows installation locations."""
    # First check system PATH
    found = shutil.which(binary_name)
    if found:
        return found
    
    # Check common Windows locations (winget, local app data)
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    candidates = [
        Path(local_app_data) / "Microsoft" / "WinGet" / "Packages",
        Path(local_app_data) / "Programs",
        Path("C:/Program Files/ffmpeg/bin"),
        Path("C:/ffmpeg/bin")
    ]
    
    target = f"{binary_name}.exe" if sys.platform == "win32" else binary_name
    
    for candidate in candidates:
        if candidate.exists():
            for match in candidate.glob(f"**/{target}"):
                if match.is_file():
                    # Also append its directory to PATH for the current process
                    bin_dir = str(match.parent)
                    if bin_dir not in os.environ.get("PATH", ""):
                        os.environ["PATH"] = bin_dir + os.pathsep + os.environ.get("PATH", "")
                    return str(match)
                    
    return binary_name

FFMPEG_PATH = find_binary("ffmpeg")
FFPROBE_PATH = find_binary("ffprobe")
