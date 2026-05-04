import os
import secrets

DOWNLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "downloads")

# ── Auth ──────────────────────────────────────────────────────────────────────
# Change APP_PASSWORD to whatever you want your friends to use.
APP_PASSWORD = os.environ.get("CLIPPER_PASSWORD", "clipper2024")

# SECRET_KEY signs the session cookie — keep this stable so logins survive restarts.
# Generate a strong one with: python -c "import secrets; print(secrets.token_hex(32))"
SECRET_KEY = os.environ.get("CLIPPER_SECRET", "change-this-to-a-long-random-string")

PLATFORMS = [
    ("YouTube",    "#ff4444", ["youtube.com", "youtu.be"]),
    ("Twitter/X",  "#1da1f2", ["twitter.com", "x.com"]),
    ("Instagram",  "#e1306c", ["instagram.com"]),
    ("Facebook",   "#1877f2", ["facebook.com", "fb.watch"]),
    ("Reddit",     "#ff6500", ["reddit.com", "redd.it"]),
    ("TikTok",     "#ff0050", ["tiktok.com", "vt.tiktok.com"]),
]

ALLOWED_DOMAINS = {
    domain: name
    for name, _color, domains in PLATFORMS
    for domain in domains
}

QUALITY_OPTIONS = ["Best Available", "1080p", "720p", "480p", "360p", "Audio Only"]
FORMAT_OPTIONS  = ["mp4", "mkv", "webm", "mp3", "m4a"]
