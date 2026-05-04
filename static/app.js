const ALLOWED = {
  "youtube.com": ["YouTube", "#ff4444"],
  "youtu.be":    ["YouTube", "#ff4444"],
  "twitter.com": ["Twitter/X", "#1da1f2"],
  "x.com":       ["Twitter/X", "#1da1f2"],
  "instagram.com": ["Instagram", "#e1306c"],
  "facebook.com":  ["Facebook",  "#1877f2"],
  "fb.watch":      ["Facebook",  "#1877f2"],
  "reddit.com":    ["Reddit",    "#ff6500"],
  "redd.it":       ["Reddit",    "#ff6500"],
  "tiktok.com":    ["TikTok",   "#ff0050"],
  "vt.tiktok.com": ["TikTok",   "#ff0050"],
};

const urlInput       = document.getElementById("url-input");
const pasteBtn       = document.getElementById("paste-btn");
const dlBtn          = document.getElementById("dl-btn");
const qualitySel     = document.getElementById("quality-select");
const formatSel      = document.getElementById("format-select");
const platformTag    = document.getElementById("platform-tag");
const playlistToggle = document.getElementById("playlist-toggle");
const playlistRow    = document.getElementById("playlist-row");
const playlistHint   = document.getElementById("playlist-hint");
const progressWrap   = document.getElementById("progress-wrap");
const progressFill   = document.getElementById("progress-fill");
const statPct        = document.getElementById("stat-pct");
const statSpeed      = document.getElementById("stat-speed");
const statEta        = document.getElementById("stat-eta");
const statFile       = document.getElementById("stat-file");
const statusEl       = document.getElementById("status");

// ── Platform detection ────────────────────────────────────────────────────────

function detectPlatform(url) {
  const lower = url.toLowerCase();
  for (const [domain, [name, color]] of Object.entries(ALLOWED)) {
    if (lower.includes(domain)) return [name, color];
  }
  return null;
}

function isPlaylistUrl(url) {
  const l = url.toLowerCase();
  return l.includes("playlist?list=") || l.includes("/playlist/") ||
    (l.includes("list=") && l.includes("youtube"));
}

urlInput.addEventListener("input", () => {
  const val = urlInput.value.trim();
  const match = val ? detectPlatform(val) : null;

  if (match) {
    platformTag.textContent = "● " + match[0];
    platformTag.style.color = match[1];
  } else if (val.length > 5) {
    platformTag.textContent = "● Unsupported";
    platformTag.style.color = "var(--error)";
  } else {
    platformTag.textContent = "";
  }

  // Auto-suggest playlist toggle if URL looks like a playlist
  if (val && isPlaylistUrl(val) && !playlistToggle.checked) {
    playlistHint.textContent = "⚡ Playlist detected — toggle to download all";
    playlistHint.style.color = "var(--warn)";
  } else if (playlistToggle.checked) {
    playlistHint.textContent = "Will download all videos in playlist";
    playlistHint.style.color = "";
  } else {
    playlistHint.textContent = "Enable to grab all videos in a playlist";
    playlistHint.style.color = "";
  }
});

playlistToggle.addEventListener("change", () => {
  if (playlistToggle.checked) {
    playlistRow.classList.add("active");
    playlistHint.textContent = "Will download all videos in playlist";
    playlistHint.style.color = "";
  } else {
    playlistRow.classList.remove("active");
    playlistHint.textContent = "Enable to grab all videos in a playlist";
    playlistHint.style.color = "";
  }
});

// ── Paste button ──────────────────────────────────────────────────────────────

pasteBtn.addEventListener("click", async () => {
  try {
    const text = await navigator.clipboard.readText();
    urlInput.value = text.trim();
    urlInput.dispatchEvent(new Event("input"));
  } catch {
    urlInput.focus();
  }
});

// ── Status helpers ────────────────────────────────────────────────────────────

function setStatus(msg, type = "") {
  statusEl.textContent = msg;
  statusEl.className = "status " + type;
}

function setProgress(pct, speed, eta, filename) {
  progressWrap.classList.add("visible");
  progressFill.style.width = pct + "%";
  statPct.textContent = Math.round(pct) + "%";
  statSpeed.textContent = speed || "";
  statEta.textContent = eta ? "ETA " + eta : "";

  // Trim long filenames
  if (filename) {
    statFile.textContent = filename.length > 45
      ? "…" + filename.slice(-42)
      : filename;
  } else {
    statFile.textContent = "";
  }
}

function resetProgress() {
  progressWrap.classList.remove("visible");
  progressFill.style.width = "0%";
  statPct.textContent = "0%";
  statSpeed.textContent = "";
  statEta.textContent = "";
  statFile.textContent = "";
}

// ── Download ──────────────────────────────────────────────────────────────────

dlBtn.addEventListener("click", startDownload);

async function startDownload() {
  const url      = urlInput.value.trim();
  const quality  = qualitySel.value;
  const format   = formatSel.value;
  const playlist = playlistToggle.checked;

  if (!url) {
    setStatus("✗  Please paste a URL first.", "err");
    return;
  }

  if (!detectPlatform(url)) {
    setStatus("✗  Only YouTube, Twitter/X, Instagram, Facebook, Reddit and TikTok are supported.", "err");
    return;
  }

  dlBtn.disabled = true;
  dlBtn.innerHTML = '<span class="dl-icon">⏳</span> ' + (playlist ? "Downloading playlist…" : "Downloading…");
  resetProgress();
  setStatus(playlist ? "Starting playlist download…" : "Starting…", "active");

  let jobId;
  try {
    const res  = await fetch("/api/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url, quality, format, playlist }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Server error");
    jobId = data.job_id;
  } catch (e) {
    setStatus("✗  " + e.message, "err");
    resetDlBtn();
    return;
  }

  // Stream progress via SSE
  const es = new EventSource(`/api/progress/${jobId}`);

  es.onmessage = (e) => {
    const evt = JSON.parse(e.data);

    if (evt.type === "progress") {
      setProgress(evt.pct, evt.speed, evt.eta, evt.filename);
      const statusParts = ["Downloading…"];
      if (evt.speed) statusParts.push(evt.speed);
      if (evt.eta)   statusParts.push("ETA " + evt.eta);
      setStatus(statusParts.join("  ·  "), "active");

    } else if (evt.type === "done") {
      es.close();
      setProgress(100, "", "", "");
      const result = evt.result;

      if (Array.isArray(result)) {
        // Playlist — multiple files, just confirm
        setStatus(`✓  Done! ${result.length} file(s) saved to server downloads folder.`, "ok");
        setProgress(100, "", "", `${result.length} files downloaded`);
        setTimeout(() => {
          resetDlBtn();
          resetProgress();
          setStatus("Ready — paste a link and hit Download");
        }, 4000);
      } else {
        // Single file — trigger browser download
        setStatus("✓  Done! Saving to your device…", "ok");
        window.location.href = "/api/download/" + encodeURIComponent(result);
        setTimeout(() => {
          resetDlBtn();
          resetProgress();
          setStatus("Ready — paste a link and hit Download");
          urlInput.value = "";
          platformTag.textContent = "";
          playlistToggle.checked = false;
          playlistRow.classList.remove("active");
        }, 3500);
      }

    } else if (evt.type === "error") {
      es.close();
      const short = evt.message.length > 160
        ? evt.message.slice(0, 160) + "…"
        : evt.message;
      setStatus("✗  " + short, "err");
      resetDlBtn();
      resetProgress();
    }
  };

  es.onerror = () => {
    es.close();
    setStatus("✗  Connection lost. Is the server still running?", "err");
    resetDlBtn();
    resetProgress();
  };
}

function resetDlBtn() {
  dlBtn.disabled = false;
  dlBtn.innerHTML = '<span class="dl-icon">↓</span> DOWNLOAD';
}
