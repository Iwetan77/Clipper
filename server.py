import os
import uuid
import json
import queue
import threading
from functools import wraps

from flask import (
    Flask, render_template, request,
    jsonify, send_from_directory, Response, abort,
    session, redirect, url_for,
)

import downloader
from config import (
    DOWNLOAD_FOLDER, ALLOWED_DOMAINS, QUALITY_OPTIONS, FORMAT_OPTIONS,
    APP_PASSWORD, SECRET_KEY,
)

app = Flask(__name__)
app.secret_key = SECRET_KEY
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

@app.after_request
def add_no_cache(response):
    if request.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
    return response

# job_id -> Queue of SSE event dicts
_jobs: dict[str, queue.Queue] = {}


# ── Auth ──────────────────────────────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login", next=request.path))
        return f(*args, **kwargs)
    return decorated


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        if request.form.get("password") == APP_PASSWORD:
            session["logged_in"] = True
            session.permanent = True
            return redirect(request.args.get("next") or url_for("index"))
        error = "Wrong password — try again."
    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ── Helper ────────────────────────────────────────────────────────────────────

def _detect_platform(url: str):
    url_l = url.lower()
    for domain, name in ALLOWED_DOMAINS.items():
        if domain in url_l:
            return name
    return None


def _is_playlist(url: str) -> bool:
    url_l = url.lower()
    return (
        "playlist?list=" in url_l or
        "/playlist/" in url_l or
        ("list=" in url_l and "youtube" in url_l)
    )


# ── Pages ─────────────────────────────────────────────────────────────────────

@app.route("/")
@login_required
def index():
    return render_template(
        "index.html",
        quality_options=QUALITY_OPTIONS,
        format_options=FORMAT_OPTIONS,
    )


# ── API  (all protected) ──────────────────────────────────────────────────────

@app.route("/api/start", methods=["POST"])
@login_required
def api_start():
    data     = request.get_json(force=True)
    url      = (data.get("url") or "").strip()
    quality  = data.get("quality", QUALITY_OPTIONS[0])
    fmt      = data.get("format",  FORMAT_OPTIONS[0])
    playlist = bool(data.get("playlist", False))

    if not url:
        return jsonify(error="No URL provided"), 400

    platform = _detect_platform(url)
    if not platform:
        return jsonify(
            error="Only YouTube, Twitter/X, Instagram, Facebook, Reddit and TikTok are supported."
        ), 400

    job_id = str(uuid.uuid4())
    q: queue.Queue = queue.Queue()
    _jobs[job_id] = q

    def _push(event: dict):
        q.put(event)

    def _run():
        downloader.download(
            url      = url,
            quality  = quality,
            fmt      = fmt,
            save_path= DOWNLOAD_FOLDER,
            playlist = playlist,
            on_progress = lambda pct, spd, eta, fname: _push(
                {"type": "progress", "pct": round(pct, 1), "speed": spd, "eta": eta, "filename": fname}
            ),
            on_done  = lambda result: _push({"type": "done",  "result": result}),
            on_error = lambda msg:    _push({"type": "error", "message": msg}),
        )

    threading.Thread(target=_run, daemon=True).start()
    return jsonify(job_id=job_id)


@app.route("/api/progress/<job_id>")
@login_required
def api_progress(job_id):
    """Server-Sent Events stream for a job."""
    q = _jobs.get(job_id)
    if q is None:
        abort(404)

    def _generate():
        while True:
            try:
                event = q.get(timeout=60)
            except queue.Empty:
                yield "event: ping\ndata: {}\n\n"
                continue

            yield f"data: {json.dumps(event)}\n\n"

            if event["type"] in ("done", "error"):
                _jobs.pop(job_id, None)
                break

    return Response(_generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.route("/api/download/<path:filename>")
@login_required
def api_download(filename):
    """Serve the finished file to the browser."""
    safe = os.path.basename(filename)
    return send_from_directory(DOWNLOAD_FOLDER, safe, as_attachment=True)


# ── Run ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"\n  Clipper running → http://0.0.0.0:5000")
    print(f"  Password: {APP_PASSWORD}\n")
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)


# ── Settings / Cookie Upload ──────────────────────────────────────────────────

COOKIES_DIR = os.path.join(os.path.dirname(__file__), "cookies")
os.makedirs(COOKIES_DIR, exist_ok=True)

COOKIE_PLATFORMS = [
    ("youtube",   "YouTube"),
    ("twitter",   "Twitter / X"),
    ("instagram", "Instagram"),
    ("facebook",  "Facebook"),
    ("tiktok",    "TikTok"),
    ("reddit",    "Reddit"),
]


@app.route("/settings")
@login_required
def settings():
    statuses = {}
    for key, _ in COOKIE_PLATFORMS:
        path = os.path.join(COOKIES_DIR, f"{key}.txt")
        statuses[key] = os.path.exists(path)
    return render_template("settings.html", platforms=COOKIE_PLATFORMS, statuses=statuses)


@app.route("/api/cookies/upload", methods=["POST"])
@login_required
def upload_cookies():
    platform = request.form.get("platform", "").strip().lower()
    valid = [k for k, _ in COOKIE_PLATFORMS]
    if platform not in valid:
        return jsonify(error="Unknown platform"), 400

    f = request.files.get("cookies")
    if not f or not f.filename:
        return jsonify(error="No file provided"), 400

    dest = os.path.join(COOKIES_DIR, f"{platform}.txt")
    f.save(dest)
    return jsonify(ok=True, message=f"Cookies saved for {platform}")


@app.route("/api/cookies/delete", methods=["POST"])
@login_required
def delete_cookies():
    platform = request.form.get("platform", "").strip().lower()
    path = os.path.join(COOKIES_DIR, f"{platform}.txt")
    if os.path.exists(path):
        os.remove(path)
    return jsonify(ok=True)
