const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

export async function fetchLanguages() {
  const res = await fetch(`${API_BASE}/api/languages`);
  if (!res.ok) throw new Error(`Failed to fetch languages: ${res.status}`);
  const data = await res.json();
  return data.languages;
}

export async function fetchBgMusic() {
  const res = await fetch(`${API_BASE}/api/bg-music`);
  if (!res.ok) throw new Error(`Failed to fetch background music: ${res.status}`);
  const data = await res.json();
  return data.tracks;
}

export async function fetchLogoIntroMusic() {
  const res = await fetch(`${API_BASE}/api/logo-intro-music`);
  if (!res.ok) throw new Error(`Failed to fetch logo intro music: ${res.status}`);
  const data = await res.json();
  return data.tracks;
}

export async function fetchPlatformConfig() {
  const res = await fetch(`${API_BASE}/api/platform-config`);
  if (!res.ok) throw new Error(`Failed to fetch platform config: ${res.status}`);
  return res.json();
}

export async function uploadFile(file, category) {
  const form = new FormData();
  form.append("file", file);
  form.append("category", category);
  const res = await fetch(`${API_BASE}/api/upload`, { method: "POST", body: form });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Upload failed: ${res.status}`);
  }
  const data = await res.json();
  return data.filename;
}

export async function startProcessing(params) {
  const res = await fetch(`${API_BASE}/api/process`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      video_filename: params.videoFilename,
      language_code: params.languageCode,
      translation_model: params.translationModel,
      sync_mode: params.syncMode,
      logo_intro_filename: params.logoIntroFilename || null,
      main_bgm_filename: params.mainBgmFilename || null,
      main_bgm_start_mode: params.mainBgmStartMode,
      main_bgm_start_seconds: params.mainBgmStartSeconds,
      logo_intro_fade_in: params.logoIntroFadeIn,
      logo_intro_fade_out: params.logoIntroFadeOut,
      logo_intro_volume_pct: params.logoIntroVolumePct,
      main_bgm_fade_in: params.mainBgmFadeIn,
      main_bgm_fade_out: params.mainBgmFadeOut,
      main_bgm_volume_pct: params.mainBgmVolumePct,
      operator_notes: params.operatorNotes || "",
      subtitles_enabled: params.subtitlesEnabled,
      subtitle_font_size_pct: params.subtitleFontSizePct,
      subtitle_text_color: params.subtitleTextColor,
      subtitle_background_color: params.subtitleBackgroundColor,
      subtitle_background_opacity: params.subtitleBackgroundOpacity,
      subtitle_margin_v_pct: params.subtitleMarginVPct,
      subtitle_margin_lr_pct: params.subtitleMarginLrPct,
      subtitle_padding_x_pct: params.subtitlePaddingXPct,
      subtitle_padding_y_pct: params.subtitlePaddingYPct,
      subtitle_corner_radius_pct: params.subtitleCornerRadiusPct,
      subtitle_max_lines_per_cue: params.subtitleMaxLinesPerCue,
    }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Failed to start processing: ${res.status}`);
  }
  const data = await res.json();
  return data.job_id;
}

export async function fetchStatus(jobId) {
  const res = await fetch(`${API_BASE}/api/status/${jobId}`);
  if (!res.ok) throw new Error(`Failed to fetch status: ${res.status}`);
  return res.json();
}

export async function fetchVoices() {
  const res = await fetch(`${API_BASE}/api/voices`);
  if (!res.ok) throw new Error(`Failed to fetch voices: ${res.status}`);
  const data = await res.json();
  return data.voices;
}

async function _voiceRequest(url, method, body) {
  const res = await fetch(url, {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const errBody = await res.json().catch(() => ({}));
    throw new Error(errBody.detail || `Request failed: ${res.status}`);
  }
  return res.json();
}

export function addVoice({ label, voiceId, isCjk }) {
  return _voiceRequest(`${API_BASE}/api/voices`, "POST", { label, voice_id: voiceId, is_cjk: isCjk });
}

export function updateVoice(code, { label, voiceId, isCjk }) {
  return _voiceRequest(`${API_BASE}/api/voices/${code}`, "PUT", { label, voice_id: voiceId, is_cjk: isCjk });
}

export async function deleteVoice(code) {
  const res = await fetch(`${API_BASE}/api/voices/${code}`, { method: "DELETE" });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Failed to delete voice: ${res.status}`);
  }
  return res.json();
}

export async function resolveJob(jobId, resolutions) {
  const res = await fetch(`${API_BASE}/api/resolve/${jobId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ resolutions }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Failed to submit resolution: ${res.status}`);
  }
  return res.json();
}

export async function updateSubtitles(jobId, edits) {
  const res = await fetch(`${API_BASE}/api/jobs/${jobId}/subtitles`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ segments: edits }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Failed to update subtitles: ${res.status}`);
  }
  return res.json();
}

export function mediaUrl(path) {
  return `${API_BASE}${path}`;
}

export async function fetchAuthStatus() {
  const res = await fetch(`${API_BASE}/api/auth-status`);
  if (!res.ok) throw new Error(`Failed to check login: ${res.status}`);
  return res.json();
}

export async function login(password) {
  const res = await fetch(`${API_BASE}/api/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ password }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Login failed: ${res.status}`);
  }
}

export async function fetchUpdateCheck() {
  const res = await fetch(`${API_BASE}/api/update-check`);
  if (!res.ok) throw new Error(`Failed to check for updates: ${res.status}`);
  return res.json();
}

export async function applyUpdate() {
  const res = await fetch(`${API_BASE}/api/update`, { method: "POST" });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Update failed: ${res.status}`);
  }
  return res.json();
}
