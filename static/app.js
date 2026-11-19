let activeVideo = null;
let activeStreamUrl = null;

document.addEventListener("DOMContentLoaded", () => {
  loadVideos();
  loadClips();
  setupDropZone();
});

function switchTab(tab) {
  const urlTab = document.getElementById("tabUrl");
  const uploadTab = document.getElementById("tabUpload");
  const urlBtn = document.getElementById("tabUrlBtn");
  const uploadBtn = document.getElementById("tabUploadBtn");

  if (tab === "url") {
    urlTab.classList.remove("hidden");
    uploadTab.classList.add("hidden");
    urlBtn.classList.add("active");
    uploadBtn.classList.remove("active");
  } else {
    uploadTab.classList.remove("hidden");
    urlTab.classList.add("hidden");
    uploadBtn.classList.add("active");
    urlBtn.classList.remove("active");
  }
}

function setupDropZone() {
  const dropZone = document.getElementById("dropZone");
  if (!dropZone) return;

  ["dragenter", "dragover"].forEach(name => {
    dropZone.addEventListener(name, e => {
      e.preventDefault();
      e.stopPropagation();
      dropZone.style.borderColor = "var(--primary)";
    });
  });

  ["dragleave", "drop"].forEach(name => {
    dropZone.addEventListener(name, e => {
      e.preventDefault();
      e.stopPropagation();
      dropZone.style.borderColor = "var(--border-color)";
    });
  });

  dropZone.addEventListener("drop", e => {
    const files = e.dataTransfer.files;
    if (files.length > 0) {
      uploadFile(files[0]);
    }
  });
}

function handleFileUpload(event) {
  const file = event.target.files[0];
  if (file) {
    uploadFile(file);
  }
}

async function uploadFile(file) {
  const spinner = document.getElementById("uploadSpinner");
  spinner.classList.remove("hidden");

  const formData = new FormData();
  formData.append("file", file);

  try {
    const res = await fetch("/api/upload", {
      method: "POST",
      body: formData
    });
    const data = await res.json();
    if (res.ok && data.status === "success") {
      activeStreamUrl = null;
      await loadVideos();
      selectVideo(data.video);
    } else {
      alert("Upload failed: " + (data.detail || "Unknown error"));
    }
  } catch (err) {
    alert("Upload error: " + err.message);
  } finally {
    spinner.classList.add("hidden");
  }
}

async function analyzeStreamUrl() {
  const input = document.getElementById("videoUrlInput");
  const url = input.value.trim();
  if (!url) {
    alert("Please enter a valid video or stream URL.");
    return;
  }

  const progressBox = document.getElementById("downloadProgressBarBox");
  const btn = document.getElementById("downloadBtn");
  
  progressBox.classList.remove("hidden");
  btn.disabled = true;

  document.getElementById("downloadProgressTitle").textContent = "Fetching stream audio (~20 MB)...";
  document.getElementById("downloadProgressPct").textContent = "0%";
  document.getElementById("downloadProgressBarFill").style.width = "0%";
  document.getElementById("downloadProgressMb").textContent = "Connecting...";
  document.getElementById("downloadProgressSpeed").textContent = "";
  document.getElementById("downloadProgressEta").textContent = "ETA: --";

  // Polling loop for audio download
  const pollInterval = setInterval(async () => {
    try {
      const pRes = await fetch("/api/download-progress");
      if (pRes.ok) {
        const p = await pRes.json();
        if (p.status === "downloading_audio" || p.status === "starting") {
          if (p.title) document.getElementById("downloadProgressTitle").textContent = p.title;
          document.getElementById("downloadProgressPct").textContent = `${p.percent}%`;
          document.getElementById("downloadProgressBarFill").style.width = `${Math.min(100, p.percent)}%`;
          document.getElementById("downloadProgressMb").textContent = `${p.downloaded_mb} MB / ${p.total_mb > 0 ? p.total_mb + ' MB' : '?'}`;
          document.getElementById("downloadProgressSpeed").textContent = p.speed_str || "";
          document.getElementById("downloadProgressEta").textContent = `ETA: ${p.eta_str || '--'}`;

          if (p.percent >= 100) {
            document.getElementById("downloadProgressTitle").textContent = "⚡ Audio ready! AI is scanning peaks for viral clips...";
            document.getElementById("downloadProgressSpeed").textContent = "Analyzing waveforms...";
            document.getElementById("downloadProgressEta").textContent = "Almost done";
          }
        }
      }
    } catch (_) {}
  }, 800);

  try {
    const res = await fetch("/api/analyze-url", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url })
    });
    const data = await res.json();
    if (res.ok && data.status === "success") {
      activeStreamUrl = url;
      activeVideo = {
        title: data.title,
        duration: data.duration,
        url: url,
        file_path: data.audio_path,
        is_stream: true
      };

      document.getElementById("activeVideoTitle").textContent = data.title;
      document.getElementById("activeVideoDuration").textContent = formatSec(data.duration);
      document.getElementById("generateClipBtn").disabled = false;
      document.getElementById("scanHighlightsBtn").disabled = false;

      // Render the automatically discovered highlights
      renderHighlights(data.highlights);

      // Scroll to highlights
      document.getElementById("highlightsContainer").scrollIntoView({ behavior: 'smooth' });
    } else {
      alert("Analysis failed: " + (data.detail || "Unknown error"));
    }
  } catch (err) {
    alert("Error analyzing stream: " + err.message);
  } finally {
    clearInterval(pollInterval);
    progressBox.classList.add("hidden");
    btn.disabled = false;
  }
}

async function loadVideos() {
  try {
    const res = await fetch("/api/videos");
    const videos = await res.json();
    const list = document.getElementById("videoList");
    const countBadge = document.getElementById("videoCount");
    countBadge.textContent = videos.length;

    if (!videos || videos.length === 0) {
      list.innerHTML = `<div class="empty-state">No videos loaded yet.</div>`;
      return;
    }

    list.innerHTML = videos.map(v => `
      <div class="video-item ${activeVideo && activeVideo.filename === v.filename ? 'active' : ''}" 
           onclick='selectVideo(${JSON.stringify(v).replace(/'/g, "&#39;")})'>
        <span class="video-item-title">${escapeHtml(v.title)}</span>
        <span class="video-item-meta">${v.size_mb} MB • ${v.highlights && v.highlights.length ? '🔥 ' + v.highlights.length + ' Highlights' : v.filename}</span>
      </div>
    `).join("");

    // Auto-select latest video if none selected yet
    if (!activeVideo && videos.length > 0) {
      selectVideo(videos[0]);
    }
  } catch (err) {
    console.error("Failed to load videos:", err);
  }
}

function selectVideo(video) {
  activeVideo = video;
  activeStreamUrl = video.url || null;
  document.getElementById("activeVideoTitle").textContent = video.title || video.filename;
  if (video.duration) {
    document.getElementById("activeVideoDuration").textContent = formatSec(video.duration);
  }
  
  const player = document.getElementById("mainVideoPlayer");
  player.src = `/media/uploads/${encodeURIComponent(video.filename)}`;
  player.load();

  document.getElementById("scanHighlightsBtn").disabled = false;
  document.getElementById("generateClipBtn").disabled = false;
  
  document.getElementById("startTimeInput").value = 0.0;
  document.getElementById("endTimeInput").value = 30.0;

  const container = document.getElementById("highlightsContainer");
  if (video.highlights && video.highlights.length > 0) {
    renderHighlights(video.highlights);
  } else {
    container.innerHTML = "";
    container.classList.add("hidden");
  }

  // Update visual selection in library
  const items = document.querySelectorAll(".video-item");
  items.forEach(el => el.classList.remove("active"));
}

function updatePlayerTime() {
  const start = parseFloat(document.getElementById("startTimeInput").value) || 0;
  const player = document.getElementById("mainVideoPlayer");
  if (player.src && !activeVideo?.is_stream) {
    player.currentTime = start;
  }
}

let currentHighlights = [];
let queuePollTimer = null;

function parseTime(val) {
  if (typeof val === 'number') return val;
  if (!val) return 0.0;
  val = String(val).trim();
  if (val.includes(':')) {
    const parts = val.split(':').map(Number);
    if (parts.length === 2) {
      return (parts[0] * 60) + parts[1];
    } else if (parts.length === 3) {
      return (parts[0] * 3600) + (parts[1] * 60) + parts[2];
    }
  }
  return parseFloat(val) || 0.0;
}

function onTimingChange() {
  const start = parseTime(document.getElementById("startTimeInput").value);
  const end = parseTime(document.getElementById("endTimeInput").value);
  const dur = Math.max(0, end - start);
  const badge = document.getElementById("clipDurationBadge");
  if (badge) {
    badge.textContent = `⏱️ Duration: ${formatSec(dur)} (${dur.toFixed(1)}s)`;
  }
  updatePlayerTime();
}

function setClipDuration(seconds) {
  const start = parseTime(document.getElementById("startTimeInput").value);
  const newEnd = start + seconds;
  document.getElementById("endTimeInput").value = newEnd.toFixed(1);
  onTimingChange();
}

function extendClipDuration(seconds) {
  const currentEnd = parseTime(document.getElementById("endTimeInput").value);
  const newEnd = currentEnd + seconds;
  document.getElementById("endTimeInput").value = newEnd.toFixed(1);
  onTimingChange();
}

async function scanHighlights() {
  if (!activeVideo) return;

  const spinner = document.getElementById("highlightsLoader");
  const btn = document.getElementById("scanHighlightsBtn");
  const container = document.getElementById("highlightsContainer");
  const targetSelect = document.getElementById("highlightDurationTarget");
  const targetSec = targetSelect ? parseInt(targetSelect.value) : 40;

  let minDur = 25.0;
  let maxDur = 50.0;
  if (targetSec === 75) {
    minDur = 60.0;
    maxDur = 120.0;
  } else if (targetSec === 180) {
    minDur = 120.0;
    maxDur = 240.0;
  }

  spinner.classList.remove("hidden");
  btn.disabled = true;
  container.innerHTML = "";
  container.classList.add("hidden");

  try {
    const res = await fetch("/api/detect-highlights", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        file_path: activeVideo.file_path,
        min_duration: minDur,
        max_duration: maxDur
      })
    });
    const data = await res.json();

    if (res.ok && data.status === "success") {
      renderHighlights(data.highlights);
    } else {
      alert("Failed to detect highlights: " + (data.detail || "Unknown error"));
    }
  } catch (err) {
    alert("Highlight analysis error: " + err.message);
  } finally {
    spinner.classList.add("hidden");
    btn.disabled = false;
  }
}

function renderHighlights(highlights) {
  const container = document.getElementById("highlightsContainer");
  const batchHeader = document.getElementById("batchActionHeader");
  const countDisplay = document.getElementById("hlCountDisplay");

  currentHighlights = highlights || [];

  if (!highlights || highlights.length === 0) {
    if (batchHeader) batchHeader.classList.add("hidden");
    container.innerHTML = `<div class="empty-state">No distinct peaks found. You can trim manually below!</div>`;
    container.classList.remove("hidden");
    return;
  }

  if (batchHeader) {
    batchHeader.classList.remove("hidden");
    if (countDisplay) countDisplay.textContent = highlights.length;
  }

  container.innerHTML = highlights.map((h, i) => `
    <div class="highlight-card" onclick="applyHighlight(${h.start}, ${h.end})">
      <div class="hl-score">🔥 Viral Score: ${h.score}%</div>
      <div class="hl-title">${escapeHtml(h.label)}</div>
      <div class="hl-time">⏱️ ${formatSec(h.start)} - ${formatSec(h.end)} (${h.duration}s)</div>
      <button class="accent-btn" style="margin-top: 0.6rem; width: 100%; font-size: 0.78rem;" 
              onclick="generateClipFromHighlight(${h.start}, ${h.end}, '${escapeHtml(h.label)}', event)">
        ⚡ 1-Click Create 9:16 Clip
      </button>
    </div>
  `).join("");

  container.classList.remove("hidden");

  if (highlights.length > 0) {
    applyHighlight(highlights[0].start, highlights[0].end);
  }
}

function applyHighlight(start, end) {
  document.getElementById("startTimeInput").value = start.toFixed(1);
  document.getElementById("endTimeInput").value = end.toFixed(1);
  onTimingChange();
}

async function generateClipFromHighlight(start, end, label, event) {
  if (event) {
    event.stopPropagation();
  }
  document.getElementById("startTimeInput").value = start.toFixed(1);
  document.getElementById("endTimeInput").value = end.toFixed(1);
  onTimingChange();
  await queueSingleClip(start, end, label);
}

async function queueSingleClip(start, end, label) {
  const layout = document.getElementById("layoutSelect").value;
  const enableSubtitles = document.getElementById("subtitlesToggle").checked;
  const subtitleColor = document.getElementById("subtitleColorSelect").value;

  const payload = {
    start,
    end,
    title: label || `Clip (${formatSec(start)} - ${formatSec(end)})`,
    layout,
    enable_subtitles: enableSubtitles,
    subtitle_color: subtitleColor
  };

  if (activeStreamUrl) {
    payload.url = activeStreamUrl;
  } else if (activeVideo) {
    payload.file_path = activeVideo.file_path;
  } else {
    alert("Please select a video or URL first.");
    return;
  }

  try {
    const res = await fetch("/api/create-clip-async", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    if (res.ok) {
      startQueuePolling();
    } else {
      const data = await res.json();
      alert("Failed to queue clip: " + (data.detail || "Unknown error"));
    }
  } catch (err) {
    alert("Queue error: " + err.message);
  }
}

async function batchGenerateAllHighlights() {
  if (!currentHighlights || currentHighlights.length === 0) {
    alert("No highlights available to batch generate.");
    return;
  }

  const layout = document.getElementById("layoutSelect").value;
  const enableSubtitles = document.getElementById("subtitlesToggle").checked;
  const subtitleColor = document.getElementById("subtitleColorSelect").value;

  const payload = {
    clips: currentHighlights,
    layout,
    enable_subtitles: enableSubtitles,
    subtitle_color: subtitleColor
  };

  if (activeStreamUrl) {
    payload.url = activeStreamUrl;
  } else if (activeVideo) {
    payload.file_path = activeVideo.file_path;
  } else {
    alert("Please select a video or URL first.");
    return;
  }

  const btn = document.getElementById("batchGenerateBtn");
  btn.disabled = true;
  btn.textContent = "⏳ Queueing Batch...";

  try {
    const res = await fetch("/api/batch-create-clips", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (res.ok) {
      startQueuePolling();
      document.getElementById("renderQueueBox").scrollIntoView({ behavior: 'smooth' });
    } else {
      alert("Batch error: " + (data.detail || "Unknown error"));
    }
  } catch (err) {
    alert("Batch error: " + err.message);
  } finally {
    btn.disabled = false;
    btn.textContent = "⚡ Batch Generate All Clips (Queue Background)";
  }
}

function startQueuePolling() {
  if (queuePollTimer) clearInterval(queuePollTimer);
  const queueBox = document.getElementById("renderQueueBox");
  queueBox.classList.remove("hidden");

  pollRenderTasks();
  queuePollTimer = setInterval(pollRenderTasks, 1500);
}

async function pollRenderTasks() {
  try {
    const res = await fetch("/api/render-tasks");
    if (!res.ok) return;
    const tasks = await res.json();
    const queueBox = document.getElementById("renderQueueBox");
    const titleEl = document.getElementById("queueStatusTitle");
    const pctEl = document.getElementById("queueStatusPct");
    const fillEl = document.getElementById("queueProgressBarFill");
    const detailEl = document.getElementById("queueStatusDetail");

    const activeTasks = tasks.filter(t => t.status === "queued" || t.status === "processing");

    if (activeTasks.length === 0) {
      pctEl.textContent = "All Done! 🎉";
      fillEl.style.width = "100%";
      detailEl.textContent = "All clips rendered and available in the gallery below!";
      await loadClips();
      setTimeout(() => {
        clearInterval(queuePollTimer);
        queuePollTimer = null;
      }, 3000);
      return;
    }

    const current = activeTasks[0];
    titleEl.textContent = `🎬 Rendering: ${current.title || 'Clip'}`;
    pctEl.textContent = `In Queue: ${activeTasks.length} clip(s)`;
    fillEl.style.width = `${current.percent || 20}%`;
    detailEl.textContent = `${current.stage || 'Processing...'} (Clip ${formatSec(current.start)} - ${formatSec(current.end)})`;
    
    // Refresh clips to show any newly completed clip in gallery immediately
    loadClips();
  } catch (_) {}
}

async function generateClip() {
  const start = parseTime(document.getElementById("startTimeInput").value);
  const end = parseTime(document.getElementById("endTimeInput").value);

  if (end <= start) {
    alert("End time must be greater than start time.");
    return;
  }

  await queueSingleClip(start, end, `Manual Clip (${formatSec(start)} - ${formatSec(end)})`);
}

function clipNextPart(endSec, durationSec, sourceUrl, sourceFile, prevTitle) {
  const nextStart = parseFloat(endSec);
  const nextEnd = nextStart + parseFloat(durationSec);

  document.getElementById("startTimeInput").value = nextStart.toFixed(1);
  document.getElementById("endTimeInput").value = nextEnd.toFixed(1);
  onTimingChange();

  if (sourceUrl) {
    activeStreamUrl = sourceUrl;
  } else if (sourceFile) {
    activeVideo = { file_path: sourceFile };
  }

  // Scroll smoothly to trimming editor
  document.querySelector(".export-controls").scrollIntoView({ behavior: 'smooth' });

  // Queue next part immediately
  const partNum = prevTitle && prevTitle.includes("Part") ? "" : " (Continuation)";
  queueSingleClip(nextStart, nextEnd, `${prevTitle || 'Clip'} ${partNum}: ${formatSec(nextStart)} - ${formatSec(nextEnd)}`);
}

async function loadClips() {
  try {
    const res = await fetch("/api/clips");
    const clips = await res.json();
    const gallery = document.getElementById("clipsGallery");

    if (!clips || clips.length === 0) {
      gallery.innerHTML = `<div class="empty-state">No clips created yet. Find a highlight above to generate one!</div>`;
      return;
    }

    gallery.innerHTML = clips.map(c => `
      <div class="clip-card">
        <video controls playsinline preload="metadata">
          <source src="${c.url}" type="video/mp4">
        </video>
        <div class="clip-card-info">
          <div class="clip-card-title">${escapeHtml(c.title || c.filename)}</div>
          <div style="font-size: 0.76rem; color: #94a3b8; margin: 0.2rem 0;">
            ⏱️ ${formatSec(c.start || 0)} - ${formatSec(c.end || c.duration)} (${(c.duration || 0).toFixed(1)}s) • ${c.size_mb} MB
          </div>
          <div class="clip-card-actions">
            <a href="${c.url}" download="${c.filename}" class="download-link">⬇️ Download Ready-to-Post</a>
          </div>
          <!-- Next Part Chaining Controls -->
          <div class="next-part-actions">
            <span style="font-size: 0.72rem; color: #94a3b8; width: 100%;">Audience wants more? Clip Next Part:</span>
            <button class="next-part-btn" onclick="clipNextPart(${c.end || c.duration}, 60, '${c.source_url || ''}', '${c.source_file || ''}', '${escapeHtml(c.title || '')}')">
              ▶️ Part 2 (+1m)
            </button>
            <button class="next-part-btn" onclick="clipNextPart(${c.end || c.duration}, 120, '${c.source_url || ''}', '${c.source_file || ''}', '${escapeHtml(c.title || '')}')">
              ▶️ Part 2 (+2m)
            </button>
            <button class="next-part-btn" onclick="clipNextPart(${c.end || c.duration}, 180, '${c.source_url || ''}', '${c.source_file || ''}', '${escapeHtml(c.title || '')}')">
              ▶️ Part 2 (+3m)
            </button>
            <button class="next-part-btn" onclick="clipNextPart(${c.end || c.duration}, 240, '${c.source_url || ''}', '${c.source_file || ''}', '${escapeHtml(c.title || '')}')">
              ▶️ Part 2 (+4m)
            </button>
          </div>
        </div>
      </div>
    `).join("");
  } catch (err) {
    console.error("Failed to load clips:", err);
  }
}

function formatSec(seconds) {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s < 10 ? '0' : ''}${s}`;
}

function escapeHtml(str) {
  if (!str) return "";
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}
