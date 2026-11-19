import os
import sys
import time
import re
import shutil
import subprocess
from pathlib import Path

def main():
    print("=" * 70)
    print("⚡ Starting ClipForge Cloud Studio...")
    print("=" * 70)

    # 1. Mount / Link Google Drive storage
    drive_base = Path("/content/drive/MyDrive/ClipForge")
    if drive_base.parent.exists():
        drive_output = drive_base / "output"
        drive_uploads = drive_base / "uploads"
        drive_output.mkdir(parents=True, exist_ok=True)
        drive_uploads.mkdir(parents=True, exist_ok=True)

        local_out = Path("output")
        local_up = Path("uploads")

        # Symlink output and uploads to Google Drive for permanent preservation
        if local_out.exists() and not local_out.is_symlink():
            shutil.rmtree(local_out, ignore_errors=True)
        if not local_out.exists():
            try:
                os.symlink(str(drive_output), str(local_out))
                print("📁 Output linked permanently to Google Drive: My Drive/ClipForge/output")
            except Exception:
                pass

        if local_up.exists() and not local_up.is_symlink():
            shutil.rmtree(local_up, ignore_errors=True)
        if not local_up.exists():
            try:
                os.symlink(str(drive_uploads), str(local_up))
                print("📁 Uploads linked to Google Drive: My Drive/ClipForge/uploads")
            except Exception:
                pass

        # Preserve database in Google Drive
        drive_db = drive_base / "clipforge.db"
        local_db = Path("clipforge.db")
        if drive_db.exists():
            if local_db.exists() and not local_db.is_symlink():
                local_db.unlink()
            if not local_db.exists():
                try:
                    os.symlink(str(drive_db), str(local_db))
                    print("💽 Database linked to Google Drive: My Drive/ClipForge/clipforge.db")
                except Exception:
                    pass
        elif local_db.exists():
            try:
                shutil.copy2(local_db, drive_db)
                local_db.unlink()
                os.symlink(str(drive_db), str(local_db))
                print("💽 Initialized database backup in Google Drive!")
            except Exception:
                pass

    # 2. Download Cloudflare binary if not installed
    cloudflared_path = Path("/usr/local/bin/cloudflared")
    if not cloudflared_path.exists():
        print("🌐 Downloading Cloudflare Tunnel binary...")
        cmd = [
            "wget", "-q", "-nc",
            "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64",
            "-O", str(cloudflared_path)
        ]
        subprocess.run(cmd, check=False)
        try:
            cloudflared_path.chmod(0o755)
        except Exception:
            pass

    # 3. Start Uvicorn Server in background
    print("🚀 Starting FastAPI backend on port 8000...")
    server_proc = subprocess.Popen([
        sys.executable, "-m", "uvicorn", "app:app",
        "--host", "0.0.0.0",
        "--port", "8000"
    ])

    time.sleep(3)

    # 4. Start Cloudflare Tunnel with logfile
    log_file = Path("/tmp/cloudflared.log")
    if log_file.exists():
        log_file.unlink()

    tunnel_proc = subprocess.Popen([
        str(cloudflared_path) if cloudflared_path.exists() else "cloudflared",
        "tunnel",
        "--url", "http://127.0.0.1:8000",
        "--logfile", str(log_file)
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # Also start localtunnel for fixed domain option
    try:
        subprocess.Popen([
            "npx", "localtunnel", "--port", "8000", "--subdomain", "clipforge-studio"
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass

    # 5. Extract public URL from logfile
    public_url = None
    for _ in range(25):
        time.sleep(1)
        if log_file.exists():
            try:
                content = log_file.read_text(encoding="utf-8", errors="ignore")
                match = re.search(r'https://[a-zA-Z0-9-]+\.trycloudflare\.com', content)
                if match:
                    public_url = match.group(0)
                    break
            except Exception:
                pass

    print("\n" + "=" * 70)
    print("🎉 CLIPFORGE CLOUD STUDIO IS LIVE!")
    print("=" * 70)
    if public_url:
        print(f"👉 DIRECT LIVE LINK (Click to Open):\n{public_url}")
    print("\n⭐ PERMANENT FIXED LINK (Save to Bookmarks):\n👉 https://clipforge-studio.loca.lt")
    print("=" * 70)
    print("💡 You can now close your laptop or use this link on your phone anywhere!")
    print("=" * 70 + "\n")

    try:
        server_proc.wait()
    except KeyboardInterrupt:
        print("\nStopping ClipForge server...")
        server_proc.terminate()
        tunnel_proc.terminate()

if __name__ == "__main__":
    main()