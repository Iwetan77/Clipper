import os
import re
import sys
import subprocess

try:
    import yt_dlp
    YTDLP_AVAILABLE = True
except ImportError:
    YTDLP_AVAILABLE = False


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


def strip_ansi(s: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*[mK]", "", s).strip()


def build_ydl_opts(quality: str, fmt: str, save_path: str, hooks: list, playlist: bool) -> dict:
    if quality == "Audio Only" or fmt in ("mp3", "m4a"):
        ydl_format = "bestaudio/best"
        postprocessors = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": fmt if fmt in ("mp3", "m4a") else "mp3",
            "preferredquality": "192",
        }]
    elif quality == "Best Available":
        ydl_format = f"bestvideo[ext={fmt}]+bestaudio/best[ext={fmt}]/best"
        postprocessors = []
    else:
        height = quality.replace("p", "")
        ydl_format = (
            f"bestvideo[height<={height}][ext={fmt}]+bestaudio/best"
            f"/bestvideo[height<={height}]+bestaudio/best"
        )
        postprocessors = []

    opts = {
        "format":               ydl_format,
        "postprocessors":       postprocessors,
        "progress_hooks":       hooks,
        "quiet":                True,
        "no_warnings":          True,
        "merge_output_format":  fmt if fmt not in ("mp3", "m4a") else None,
        # Fix: always re-download, never skip existing files
        "nooverwrites":         False,
        "overwrites":           True,
        "continuedl":           False,
    }

    if playlist:
        opts["outtmpl"] = os.path.join(save_path, "%(playlist_title)s", "%(playlist_index)s - %(title)s.%(ext)s")
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

    opts = build_ydl_opts(quality, fmt, save_path, [_hook], playlist)

    try:
        with _ydlp.YoutubeDL(opts) as ydl:
            ydl.download([url])

        if finished_files:
            filenames = [os.path.basename(p) for p in finished_files]
        else:
            all_files = sorted(
                [f for f in os.listdir(save_path) if os.path.isfile(os.path.join(save_path, f))],
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
