import os
import re
import sys
import shutil
import subprocess

try:
    import yt_dlp
    YTDLP_AVAILABLE = True
except ImportError:
    YTDLP_AVAILABLE = False

COOKIES_DIR = os.path.join(os.path.dirname(__file__), "cookies")
os.makedirs(COOKIES_DIR, exist_ok=True)

# Map domain keywords → cookie filename
COOKIE_MAP = {
    "youtube.com": "youtube.txt",
    "youtu.be":    "youtube.txt",
    "instagram.com": "instagram.txt",
    "twitter.com": "twitter.txt",
    "x.com":       "twitter.txt",
    "facebook.com": "facebook.txt",
    "tiktok.com":  "tiktok.txt",
    "reddit.com":  "reddit.txt",
}


def ensure_ytdlp():
    global yt_dlp, YTDLP_AVAILABLE
    if YTDLP_AVAILABLE:
        return True, None
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "yt-dlp", "-q"])
        import yt_dlp as _yt
        yt_dlp = _yt
        YTDLP_AVAILABLE = True
        return True, None
    except Exception as e:
        return False, str(e)


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def strip_ansi(s: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*[mK]", "", s).strip()


def get_cookie_file(url: str) -> str | None:
    url_l = url.lower()
    for keyword, fname in COOKIE_MAP.items():
        if keyword in url_l:
            path = os.path.join(COOKIES_DIR, fname)
            return path if os.path.exists(path) else None
    return None


def build_ydl_opts(url: str, quality: str, fmt: str, save_path: str,
                   hooks: list, playlist: bool) -> dict:
    has_ffmpeg = ffmpeg_available()

    if quality == "Audio Only" or fmt in ("mp3", "m4a"):
        if has_ffmpeg:
            ydl_format = "bestaudio/best"
            postprocessors = [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": fmt if fmt in ("mp3", "m4a") else "mp3",
                "preferredquality": "192",
            }]
        else:
            # No ffmpeg — grab best audio-only stream directly
            ydl_format = "bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio"
            postprocessors = []

    elif quality == "Best Available":
        if has_ffmpeg:
            ydl_format = f"bestvideo[ext={fmt}]+bestaudio/best[ext={fmt}]/best"
        else:
            # No ffmpeg — single-file best (already has audio)
            ydl_format = "best[ext=mp4]/best"
        postprocessors = []

    else:
        height = quality.replace("p", "")
        if has_ffmpeg:
            ydl_format = (
                f"bestvideo[height<={height}][ext={fmt}]+bestaudio/best"
                f"/bestvideo[height<={height}]+bestaudio/best"
            )
        else:
            # No ffmpeg — best single-file stream at or below requested height
            ydl_format = (
                f"best[height<={height}][ext=mp4]"
                f"/best[height<={height}]"
                f"/best[ext=mp4]/best"
            )
        postprocessors = []

    opts = {
        "format":              ydl_format,
        "postprocessors":      postprocessors,
        "progress_hooks":      hooks,
        "quiet":               True,
        "no_warnings":         True,
        "nooverwrites":        False,
        "overwrites":          True,
        "continuedl":          False,
        "abort_on_error":      False,   # never hard-crash on a single format error
    }

    if has_ffmpeg and fmt not in ("mp3", "m4a"):
        opts["merge_output_format"] = fmt

    # Attach cookies if available for this domain
    cookie_file = get_cookie_file(url)
    if cookie_file:
        opts["cookiefile"] = cookie_file

    if playlist:
        opts["outtmpl"] = os.path.join(
            save_path, "%(playlist_title)s",
            "%(playlist_index)s - %(title)s.%(ext)s"
        )
        opts["noplaylist"] = False
    else:
        opts["outtmpl"] = os.path.join(save_path, "%(title)s.%(ext)s")
        opts["noplaylist"] = True

    return opts


def download(url: str, quality: str, fmt: str, save_path: str,
             playlist: bool, on_progress, on_done, on_error):
    ok, err = ensure_ytdlp()
    if not ok:
        on_error(f"Could not install yt-dlp: {err}")
        return

    import yt_dlp as _ydlp

    finished_files = []

    def _hook(d):
        if d["status"] == "downloading":
            raw_pct   = strip_ansi(d.get("_percent_str", "0%"))
            raw_speed = strip_ansi(d.get("_speed_str", ""))
            raw_eta   = strip_ansi(d.get("_eta_str", ""))

            speed = raw_speed if raw_speed and raw_speed != "Unknown B/s" else ""
            eta   = raw_eta   if raw_eta   and raw_eta   != "Unknown"      else ""

            try:
                pct = float(raw_pct.replace("%", ""))
            except ValueError:
                pct = 0.0

            fname = os.path.basename(d.get("filename", ""))
            on_progress(pct, speed, eta, fname)

        elif d["status"] == "finished":
            path = d.get("filename", "")
            if path:
                finished_files.append(path)
            on_progress(95, "", "", os.path.basename(path))

    opts = build_ydl_opts(url, quality, fmt, save_path, [_hook], playlist)

    try:
        with _ydlp.YoutubeDL(opts) as ydl:
            ydl.download([url])

        if finished_files:
            filenames = [os.path.basename(p) for p in finished_files]
        else:
            all_files = sorted(
                [f for f in os.listdir(save_path)
                 if os.path.isfile(os.path.join(save_path, f))],
                key=lambda f: os.path.getmtime(os.path.join(save_path, f)),
                reverse=True,
            )
            filenames = all_files[:1] if all_files else []

        if playlist:
            on_done(filenames)
        else:
            on_done(filenames[0] if filenames else "")

    except Exception as e:
        on_error(str(e))
