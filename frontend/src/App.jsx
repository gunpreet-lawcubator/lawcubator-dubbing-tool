import { useEffect, useRef, useState } from "react";
import "./App.css";
import {
  fetchLanguages,
  fetchBgMusic,
  fetchLogoIntroMusic,
  fetchPlatformConfig,
  fetchVoices,
  addVoice,
  updateVoice,
  deleteVoice,
  startProcessing,
  fetchStatus,
  resolveJob,
  updateSubtitles,
  mediaUrl,
} from "./api";
import FileUploadField from "./FileUploadField";
import AudioSettingsPanel from "./AudioSettingsPanel";
import SubtitleSettingsPanel from "./SubtitleSettingsPanel";
import SubtitleEditor from "./SubtitleEditor";
import UpdateNotice from "./UpdateNotice";
import OperatorNotes from "./OperatorNotes";
import InfoTooltip from "./InfoTooltip";
import ProgressSteps from "./ProgressSteps";
import ReviewPanel from "./ReviewPanel";
import VoiceSettingsPanel from "./VoiceSettingsPanel";
import logo from "./assets/logo-lawcubator.png";

const TRANSLATION_MODEL = "google/gemini-3.6-flash";

function App() {
  const [languages, setLanguages] = useState([]);
  const [voices, setVoices] = useState([]);
  const [showVoiceSettings, setShowVoiceSettings] = useState(false);
  const [selectedVideo, setSelectedVideo] = useState("");
  const [languageCode, setLanguageCode] = useState("");
  const [syncMode, setSyncMode] = useState("video");

  const [platformConfig, setPlatformConfig] = useState(null);
  const [logoIntroTracks, setLogoIntroTracks] = useState([]);
  const [mainBgmTracks, setMainBgmTracks] = useState([]);
  const [logoIntroEnabled, setLogoIntroEnabled] = useState(true);
  const [mainBgmEnabled, setMainBgmEnabled] = useState(true);
  const [logoIntroFilename, setLogoIntroFilename] = useState("");
  const [mainBgmFilename, setMainBgmFilename] = useState("");
  const [mainBgmStartMode, setMainBgmStartMode] = useState("after_intro");
  const [mainBgmStartSeconds, setMainBgmStartSeconds] = useState(0);
  const [logoIntroFadeIn, setLogoIntroFadeIn] = useState(0.5);
  const [logoIntroFadeOut, setLogoIntroFadeOut] = useState(1.5);
  const [logoIntroVolumePct, setLogoIntroVolumePct] = useState(100);
  const [mainBgmFadeIn, setMainBgmFadeIn] = useState(1);
  const [mainBgmFadeOut, setMainBgmFadeOut] = useState(4);
  const [mainBgmVolumePct, setMainBgmVolumePct] = useState(12);

  const [subtitlesEnabled, setSubtitlesEnabled] = useState(true);
  const [subtitleFontSizePct, setSubtitleFontSizePct] = useState(0.039);
  const [subtitleTextColor, setSubtitleTextColor] = useState("#ffffff");
  const [subtitleBackgroundColor, setSubtitleBackgroundColor] = useState("#000000");
  const [subtitleBackgroundOpacity, setSubtitleBackgroundOpacity] = useState(100);
  const [subtitleMarginVPct, setSubtitleMarginVPct] = useState(0.056);
  const [subtitleMarginLrPct, setSubtitleMarginLrPct] = useState(0.0625);
  const [subtitlePaddingXPct, setSubtitlePaddingXPct] = useState(0.6);
  const [subtitlePaddingYPct, setSubtitlePaddingYPct] = useState(0.35);
  const [subtitleCornerRadiusPct, setSubtitleCornerRadiusPct] = useState(0.35);
  const [subtitleMaxLinesPerCue, setSubtitleMaxLinesPerCue] = useState(2);

  const [operatorNotes, setOperatorNotes] = useState("");

  const [jobId, setJobId] = useState(null);
  const [jobStatus, setJobStatus] = useState(null);
  const [error, setError] = useState("");
  const [segmentsExpanded, setSegmentsExpanded] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [pollTrigger, setPollTrigger] = useState(0);
  const [subtitleEdits, setSubtitleEdits] = useState({});
  const [savingSubtitles, setSavingSubtitles] = useState(false);
  const [videoCacheBust, setVideoCacheBust] = useState(0);
  const [subtitleEditorOpen, setSubtitleEditorOpen] = useState(false);
  const pollRef = useRef(null);

  useEffect(() => {
    fetchLanguages()
      .then((list) => setLanguages(list))
      .catch((e) => setError(e.message));

    fetchVoices()
      .then((list) => setVoices(list))
      .catch((e) => setError(e.message));

    fetchBgMusic()
      .then((list) => setMainBgmTracks(list))
      .catch((e) => setError(e.message));

    fetchLogoIntroMusic()
      .then((list) => setLogoIntroTracks(list))
      .catch((e) => setError(e.message));

    fetchPlatformConfig()
      .then((config) => {
        setPlatformConfig(config);
        if (config.default_logo_intro_filename) setLogoIntroFilename(config.default_logo_intro_filename);
        if (config.default_main_bgm_filename) setMainBgmFilename(config.default_main_bgm_filename);
        setLogoIntroFadeIn(config.logo_intro_fade_in);
        setLogoIntroFadeOut(config.logo_intro_fade_out);
        setLogoIntroVolumePct(config.logo_intro_volume_pct);
        setMainBgmFadeIn(config.main_bgm_fade_in);
        setMainBgmFadeOut(config.main_bgm_fade_out);
        setMainBgmVolumePct(config.main_bgm_volume_pct);
        setSubtitlesEnabled(config.subtitles_enabled);
        setSubtitleFontSizePct(config.subtitle_font_size_pct);
        setSubtitleTextColor(config.subtitle_text_color);
        setSubtitleBackgroundColor(config.subtitle_background_color);
        setSubtitleBackgroundOpacity(config.subtitle_background_opacity);
        setSubtitleMarginVPct(config.subtitle_margin_v_pct);
        setSubtitleMarginLrPct(config.subtitle_margin_lr_pct);
        setSubtitlePaddingXPct(config.subtitle_padding_x_pct);
        setSubtitlePaddingYPct(config.subtitle_padding_y_pct);
        setSubtitleCornerRadiusPct(config.subtitle_corner_radius_pct);
        setSubtitleMaxLinesPerCue(config.subtitle_max_lines_per_cue);
      })
      .catch((e) => setError(e.message));
  }, []);

  useEffect(() => {
    if (!jobId) return;
    pollRef.current = setInterval(async () => {
      try {
        const status = await fetchStatus(jobId);
        setJobStatus(status);
        if (status.status === "done" || status.status === "error" || status.status === "needs_review") {
          clearInterval(pollRef.current);
        }
      } catch (e) {
        setError(e.message);
        clearInterval(pollRef.current);
      }
    }, 1500);
    return () => clearInterval(pollRef.current);
  }, [jobId, pollTrigger]);

  const handleVideoUploaded = (filename) => {
    setSelectedVideo(filename);
  };

  const handleLogoIntroUploaded = async (filename) => {
    const list = await fetchLogoIntroMusic();
    setLogoIntroTracks(list);
    setLogoIntroFilename(filename);
  };

  const handleMainBgmUploaded = async (filename) => {
    const list = await fetchBgMusic();
    setMainBgmTracks(list);
    setMainBgmFilename(filename);
  };

  const refreshVoicesAndLanguages = async () => {
    const [voiceList, languageList] = await Promise.all([fetchVoices(), fetchLanguages()]);
    setVoices(voiceList);
    setLanguages(languageList);
  };

  const handleAddVoice = async (form) => {
    await addVoice(form);
    await refreshVoicesAndLanguages();
  };

  const handleUpdateVoice = async (code, form) => {
    await updateVoice(code, form);
    await refreshVoicesAndLanguages();
  };

  const handleDeleteVoice = async (code) => {
    await deleteVoice(code);
    if (languageCode === code) setLanguageCode("");
    await refreshVoicesAndLanguages();
  };

  const handleGenerate = async () => {
    setError("");
    setJobStatus(null);
    setJobId(null);
    setSegmentsExpanded(false);
    setSubtitleEdits({});
    setVideoCacheBust(0);
    setSubtitleEditorOpen(false);
    try {
      const id = await startProcessing({
        videoFilename: selectedVideo,
        languageCode,
        translationModel: TRANSLATION_MODEL,
        syncMode,
        logoIntroFilename: logoIntroEnabled ? logoIntroFilename : "",
        mainBgmFilename: mainBgmEnabled ? mainBgmFilename : "",
        mainBgmStartMode,
        mainBgmStartSeconds,
        logoIntroFadeIn,
        logoIntroFadeOut,
        logoIntroVolumePct,
        mainBgmFadeIn,
        mainBgmFadeOut,
        mainBgmVolumePct,
        operatorNotes,
        subtitlesEnabled,
        subtitleFontSizePct,
        subtitleTextColor,
        subtitleBackgroundColor,
        subtitleBackgroundOpacity,
        subtitleMarginVPct,
        subtitleMarginLrPct,
        subtitlePaddingXPct,
        subtitlePaddingYPct,
        subtitleCornerRadiusPct,
        subtitleMaxLinesPerCue,
      });
      setJobId(id);
      setJobStatus({ status: "running", step: "" });
    } catch (e) {
      setError(e.message);
    }
  };

  const handleResolve = async (choicesByIndex) => {
    if (!jobId) return;
    setError("");
    try {
      await resolveJob(jobId, choicesByIndex);
      setJobStatus((s) => ({ ...s, status: "running" }));
      setPollTrigger((t) => t + 1);
    } catch (e) {
      setError(e.message);
    }
  };

  const handleApplySubtitleEdits = async () => {
    if (!jobId) return;
    const edits = Object.entries(subtitleEdits)
      .map(([index, text]) => ({ index: Number(index), text }))
      .filter(({ index, text }) => text !== jobStatus.segments[index].translated);
    if (edits.length === 0) return;
    setSavingSubtitles(true);
    setError("");
    try {
      await updateSubtitles(jobId, edits);
      setJobStatus((s) => {
        const segments = s.segments.map((seg, i) =>
          i in subtitleEdits ? { ...seg, translated: subtitleEdits[i] } : seg
        );
        return { ...s, segments };
      });
      setSubtitleEdits({});
      setVideoCacheBust(Date.now());
    } catch (e) {
      setError(e.message);
    } finally {
      setSavingSubtitles(false);
    }
  };

  const handleDownload = async () => {
    if (!jobStatus?.video_url) return;
    setDownloading(true);
    try {
      const res = await fetch(mediaUrl(jobStatus.video_url));
      if (!res.ok) throw new Error(`Download failed: ${res.status}`);
      const blob = await res.blob();
      const blobUrl = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = blobUrl;
      a.download = `${selectedVideo.replace(/\.[^.]+$/, "")}_${languageCode}.mp4`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(blobUrl);
    } catch (e) {
      setError(e.message);
    } finally {
      setDownloading(false);
    }
  };

  const selectedLanguage = languages.find((l) => l.code === languageCode);
  const isRunning = jobStatus && jobStatus.status === "running";
  const isDone = jobStatus?.status === "done";
  const needsReview = jobStatus?.status === "needs_review";

  const logoIntroTrack = logoIntroTracks.find((t) => t.filename === logoIntroFilename);
  const mainBgmTrack = mainBgmTracks.find((t) => t.filename === mainBgmFilename);

  return (
    <div className="app-shell">
      <header className="app-header">
        <img className="brand-logo" src={logo} alt="Lawcubator" />
        <span className="brand-sub">Proprietary Multi-Language Video Editor</span>
        <UpdateNotice />
        <button
          className="header-icon-btn"
          onClick={() => setShowVoiceSettings(true)}
          title="Voice & language settings"
        >
          &#9881;
        </button>
        <span className="ai-badge">
          <span className="ai-badge-icon">&#10024;</span> AI Powered
        </span>
      </header>

      {showVoiceSettings && (
        <VoiceSettingsPanel
          voices={voices}
          onAdd={handleAddVoice}
          onUpdate={handleUpdateVoice}
          onDelete={handleDeleteVoice}
          onClose={() => setShowVoiceSettings(false)}
        />
      )}

      <div className="app-body">
        {subtitleEditorOpen && isDone && (
          <SubtitleEditor
            segments={jobStatus.segments}
            edits={subtitleEdits}
            onChange={(i, text) => setSubtitleEdits((edits) => ({ ...edits, [i]: text }))}
            onApply={handleApplySubtitleEdits}
            onClose={() => setSubtitleEditorOpen(false)}
            saving={savingSubtitles}
            languageLabel={selectedLanguage?.label}
          />
        )}

        <aside className="sidebar" hidden={subtitleEditorOpen && isDone}>
          <section className="side-section">
            <div className="field">
              <label>
                Video <InfoTooltip text="Pick the English training video you want dubbed. Any video file on your Mac — it will be uploaded and a transcript generated automatically." />
              </label>
              <FileUploadField
                filename={selectedVideo}
                onSelected={handleVideoUploaded}
                category="video"
                accept="video/*"
                emptyHint="No video selected yet"
              />
            </div>

            <div className="field">
              <label>
                Target language <InfoTooltip text="The language the video will be dubbed into. You must pick one before generating." />
              </label>
              <select value={languageCode} onChange={(e) => setLanguageCode(e.target.value)} required>
                <option value="" disabled>
                  -- select a language --
                </option>
                {languages.map((l) => (
                  <option key={l.code} value={l.code}>
                    {l.label}
                  </option>
                ))}
              </select>
            </div>

            <div className="field">
              <label>
                Sync mode <InfoTooltip text="Stretch video (recommended): the voiceover plays at its natural pace and the video speeds up or slows down to match — best audio quality, video timing shifts slightly. Stretch audio: video timing stays exactly as the original, but the voiceover is time-stretched to fit, which can sound a little off on longer stretches." />
              </label>
              <select value={syncMode} onChange={(e) => setSyncMode(e.target.value)}>
                <option value="video">Stretch video (recommended)</option>
                <option value="audio">Stretch audio</option>
              </select>
            </div>

            <OperatorNotes value={operatorNotes} onChange={setOperatorNotes} />
          </section>

          <section className="side-section">
            <h2 className="side-section-title">Audio</h2>
            <AudioSettingsPanel
              logoIntroEnabled={logoIntroEnabled}
              setLogoIntroEnabled={setLogoIntroEnabled}
              logoIntroFilename={logoIntroFilename}
              isLogoIntroDefault={Boolean(platformConfig) && logoIntroFilename === platformConfig.default_logo_intro_filename}
              logoIntroPreviewUrl={logoIntroTrack ? mediaUrl(logoIntroTrack.url) : ""}
              onLogoIntroUploaded={handleLogoIntroUploaded}
              logoIntroFadeIn={logoIntroFadeIn}
              setLogoIntroFadeIn={setLogoIntroFadeIn}
              logoIntroFadeOut={logoIntroFadeOut}
              setLogoIntroFadeOut={setLogoIntroFadeOut}
              logoIntroVolumePct={logoIntroVolumePct}
              setLogoIntroVolumePct={setLogoIntroVolumePct}
              mainBgmEnabled={mainBgmEnabled}
              setMainBgmEnabled={setMainBgmEnabled}
              mainBgmFilename={mainBgmFilename}
              isMainBgmDefault={Boolean(platformConfig) && mainBgmFilename === platformConfig.default_main_bgm_filename}
              mainBgmPreviewUrl={mainBgmTrack ? mediaUrl(mainBgmTrack.url) : ""}
              onMainBgmUploaded={handleMainBgmUploaded}
              mainBgmStartMode={mainBgmStartMode}
              setMainBgmStartMode={setMainBgmStartMode}
              mainBgmStartSeconds={mainBgmStartSeconds}
              setMainBgmStartSeconds={setMainBgmStartSeconds}
              mainBgmFadeIn={mainBgmFadeIn}
              setMainBgmFadeIn={setMainBgmFadeIn}
              mainBgmFadeOut={mainBgmFadeOut}
              setMainBgmFadeOut={setMainBgmFadeOut}
              mainBgmVolumePct={mainBgmVolumePct}
              setMainBgmVolumePct={setMainBgmVolumePct}
            />
          </section>

          <section className="side-section">
            <h2 className="side-section-title">Subtitles</h2>
            <SubtitleSettingsPanel
              subtitlesEnabled={subtitlesEnabled}
              setSubtitlesEnabled={setSubtitlesEnabled}
              subtitleFontSizePct={subtitleFontSizePct}
              setSubtitleFontSizePct={setSubtitleFontSizePct}
              subtitleTextColor={subtitleTextColor}
              setSubtitleTextColor={setSubtitleTextColor}
              subtitleBackgroundColor={subtitleBackgroundColor}
              setSubtitleBackgroundColor={setSubtitleBackgroundColor}
              subtitleBackgroundOpacity={subtitleBackgroundOpacity}
              setSubtitleBackgroundOpacity={setSubtitleBackgroundOpacity}
              subtitleMarginVPct={subtitleMarginVPct}
              setSubtitleMarginVPct={setSubtitleMarginVPct}
              subtitleMarginLrPct={subtitleMarginLrPct}
              setSubtitleMarginLrPct={setSubtitleMarginLrPct}
              subtitlePaddingXPct={subtitlePaddingXPct}
              setSubtitlePaddingXPct={setSubtitlePaddingXPct}
              subtitlePaddingYPct={subtitlePaddingYPct}
              setSubtitlePaddingYPct={setSubtitlePaddingYPct}
              subtitleCornerRadiusPct={subtitleCornerRadiusPct}
              setSubtitleCornerRadiusPct={setSubtitleCornerRadiusPct}
              subtitleMaxLinesPerCue={subtitleMaxLinesPerCue}
              setSubtitleMaxLinesPerCue={setSubtitleMaxLinesPerCue}
            />
          </section>

          <button className="generate-btn" onClick={handleGenerate} disabled={!selectedVideo || !languageCode || isRunning}>
            Generate dub
          </button>
        </aside>

        <main className="main-area">
          {error && <div className="error">{error}</div>}

          {!jobStatus && (
            <div className="empty-state">
              <p>Select a video and settings on the left, then click &ldquo;Generate dub&rdquo;.</p>
            </div>
          )}

          {jobStatus && !isDone && !needsReview && (
            <ProgressSteps languageLabel={selectedLanguage?.label} step={jobStatus.step} status={jobStatus.status} error={jobStatus.error} />
          )}

          {needsReview && <ReviewPanel flaggedSegments={jobStatus.flagged_segments} onSubmit={handleResolve} />}

          {isDone && (
            <div className="review-area">
              <section className="panel review-top">
                <video
                  className="output-preview"
                  src={mediaUrl(jobStatus.video_url) + (videoCacheBust ? `?t=${videoCacheBust}` : "")}
                  controls
                  width="100%"
                />

                <button className="download-video-link" onClick={handleDownload} disabled={downloading}>
                  &#8681; {downloading ? "Preparing download…" : `Download dubbed video (MP4, ${selectedLanguage?.label || languageCode} audio)`}
                </button>
                {jobStatus.subtitles_enabled !== false && (
                  <button className="edit-subtitles-btn" onClick={() => setSubtitleEditorOpen((v) => !v)}>
                    &#9998; {subtitleEditorOpen ? "Close subtitle editor" : "Edit subtitles"}
                  </button>
                )}
              </section>

              <section className="panel segments-panel">
                <button className="segments-toggle" onClick={() => setSegmentsExpanded((v) => !v)}>
                  <span>{segmentsExpanded ? "▾" : "▸"} Segments ({jobStatus.segments.length})</span>
                </button>
                {segmentsExpanded && (
                  <div className="segments-scroll">
                    <table className="segments">
                      <thead>
                        <tr>
                          <th>Time</th>
                          <th>English</th>
                          <th>{selectedLanguage?.label || "Translated"} (subtitle)</th>
                          <th>Speech (TTS)</th>
                          <th>Target dur</th>
                          <th>TTS dur</th>
                          <th>ElevenLabs speed</th>
                          <th>Residual stretch</th>
                          <th>Video speed</th>
                        </tr>
                      </thead>
                      <tbody>
                        {jobStatus.segments.map((seg, i) => (
                          <tr key={i} className={seg.clamped ? "tempo-clamped" : ""}>
                            <td>
                              {seg.start.toFixed(1)}s&ndash;{seg.end.toFixed(1)}s
                              {seg.video_factor != null && (seg.orig_start !== seg.start || seg.orig_end !== seg.end) && (
                                <div className="orig-time">was {seg.orig_start.toFixed(1)}s&ndash;{seg.orig_end.toFixed(1)}s</div>
                              )}
                            </td>
                            <td>{seg.english}</td>
                            <td>{seg.translated}</td>
                            <td className={seg.speech_text !== seg.translated ? "speech-diff" : ""}>{seg.speech_text}</td>
                            <td>{seg.target_duration}s</td>
                            <td>{seg.raw_duration}s</td>
                            <td>{seg.regenerated ? `${seg.speed_used}x` : "— (not needed)"}</td>
                            <td>
                              {seg.tempo_applied}x
                              {seg.clamped && (
                                <span className="clamp-flag" title={`Needed ${seg.tempo_needed}x to fit exactly, clamped to ${seg.tempo_applied}x`}>
                                  {" "}
                                  &#9888; clamped (needed {seg.tempo_needed}x)
                                </span>
                              )}
                            </td>
                            <td>{seg.video_factor != null ? `${seg.video_factor}x` : "— (not used)"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </section>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}

export default App;
