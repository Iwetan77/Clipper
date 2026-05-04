# Clipper — Web

A private, password-protected Flask web app for downloading videos from
YouTube, Twitter/X, Instagram, Facebook and Reddit.

## Setup

```bash
pip install -r requirements.txt
python server.py
```

Open `http://localhost:5000` — you'll be prompted for the password.

## Change the password

Open `config.py` and edit this line:

```python
APP_PASSWORD = os.environ.get("CLIPPER_PASSWORD", "clipper2024")
```

Replace `clipper2024` with whatever you want. Or set it as an env variable:

```bash
# Mac / Linux
export CLIPPER_PASSWORD="your-secret-password"

# Windows
set CLIPPER_PASSWORD=your-secret-password
```

## Before going live — generate a proper secret key

Run this and paste the output into SECRET_KEY in config.py:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

## Share with friends

1. Find your IP: `ipconfig` (Windows) or `ifconfig` (Mac/Linux)
2. Run the server
3. Send friends: `http://YOUR_IP:5000` + the password
4. Allow port 5000 through your firewall

## Project structure

```
clipper-web/
├── server.py             # Flask app — routes, auth, SSE streaming
├── downloader.py         # yt-dlp download logic
├── config.py             # Password, secret key, platforms, options
├── requirements.txt
├── downloads/            # Temporary download folder
├── templates/
│   ├── login.html        # Password gate
│   └── index.html        # Main downloader page
└── static/
    ├── style.css
    └── app.js
```

## Notes

- Clean the `downloads/` folder occasionally — files pile up.
- ffmpeg optional but recommended: `brew install ffmpeg` / `apt install ffmpeg`
- Private use only. Do not make publicly accessible.
