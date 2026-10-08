import FileUploadField from "./FileUploadField";
import InfoTooltip from "./InfoTooltip";

const numOr = (value, fallback) => {
  const n = parseFloat(value);
  return Number.isFinite(n) ? n : fallback;
};

export default function AudioSettingsPanel({
  logoIntroEnabled,
  setLogoIntroEnabled,
  logoIntroFilename,
  isLogoIntroDefault,
  logoIntroPreviewUrl,
  onLogoIntroUploaded,
  logoIntroFadeIn,
  setLogoIntroFadeIn,
  logoIntroFadeOut,
  setLogoIntroFadeOut,
  logoIntroVolumePct,
  setLogoIntroVolumePct,
  mainBgmEnabled,
  setMainBgmEnabled,
  mainBgmFilename,
  isMainBgmDefault,
  mainBgmPreviewUrl,
  onMainBgmUploaded,
  mainBgmStartMode,
  setMainBgmStartMode,
  mainBgmStartSeconds,
  setMainBgmStartSeconds,
  mainBgmFadeIn,
  setMainBgmFadeIn,
  mainBgmFadeOut,
  setMainBgmFadeOut,
  mainBgmVolumePct,
  setMainBgmVolumePct,
}) {
  return (
    <div className="audio-panel">
      <div className="audio-tier">
        <div className="field-checkbox">
          <label>
            <input type="checkbox" checked={logoIntroEnabled} onChange={(e) => setLogoIntroEnabled(e.target.checked)} />
            {" "}
            <span className="tier-label">Logo intro jingle</span>
            <InfoTooltip text='Plays for the first few seconds of every video, before the main background music starts. If you don’t pick your own file here, the default Lawcubator jingle is used automatically. Uncheck to skip it entirely — no intro jingle will be added at all.' />
          </label>
        </div>
        <fieldset className="audio-tier-body" disabled={!logoIntroEnabled}>
          <FileUploadField
            filename={logoIntroFilename}
            onSelected={onLogoIntroUploaded}
            category="logo_intro"
            accept="audio/*"
            emptyHint="No jingle set — the default Lawcubator intro will play"
            isDefault={isLogoIntroDefault}
            previewUrl={logoIntroPreviewUrl}
          />
          <div className="fade-row">
            <label>
              Fade in
              <input
                type="number"
                step="0.1"
                min="0"
                value={logoIntroFadeIn}
                onChange={(e) => setLogoIntroFadeIn(numOr(e.target.value, 0))}
              />
              s
            </label>
            <label>
              Fade out
              <input
                type="number"
                step="0.1"
                min="0"
                value={logoIntroFadeOut}
                onChange={(e) => setLogoIntroFadeOut(numOr(e.target.value, 0))}
              />
              s
            </label>
          </div>

          <div className="field">
            <label>
              Volume ({Math.round(logoIntroVolumePct)}%)
              <InfoTooltip text="100% plays the jingle at its original volume." />
            </label>
            <input
              type="range"
              min="0"
              max="100"
              step="1"
              value={logoIntroVolumePct}
              onChange={(e) => setLogoIntroVolumePct(numOr(e.target.value, 100))}
            />
          </div>
        </fieldset>
      </div>

      <div className="audio-tier">
        <div className="field-checkbox">
          <label>
            <input type="checkbox" checked={mainBgmEnabled} onChange={(e) => setMainBgmEnabled(e.target.checked)} />
            {" "}
            <span className="tier-label">Main background music</span>
            <InfoTooltip text="Plays under the voiceover for the rest of the video. If you don’t pick your own file here, the default Lawcubator background track is used automatically. Uncheck to skip it entirely — no background music will be added at all." />
          </label>
        </div>
        <fieldset className="audio-tier-body" disabled={!mainBgmEnabled}>
          <FileUploadField
            filename={mainBgmFilename}
            onSelected={onMainBgmUploaded}
            category="main_bgm"
            accept="audio/*"
            emptyHint="No music set — the default background music will play"
            isDefault={isMainBgmDefault}
            previewUrl={mainBgmPreviewUrl}
          />

          <div className="field-checkbox">
            <label>
              <input
                type="checkbox"
                checked={mainBgmStartMode === "after_intro"}
                onChange={(e) => setMainBgmStartMode(e.target.checked ? "after_intro" : "custom")}
              />
              {" "}Start right after the logo intro
              <InfoTooltip text="Uncheck this to make the main background music start at an exact timestamp instead of immediately after the intro jingle ends." />
            </label>
          </div>

          {mainBgmStartMode === "custom" && (
            <div className="field">
              <label>Start at (seconds)</label>
              <input
                type="number"
                step="0.1"
                min="0"
                value={mainBgmStartSeconds}
                onChange={(e) => setMainBgmStartSeconds(numOr(e.target.value, 0))}
              />
            </div>
          )}

          <div className="fade-row">
            <label>
              Fade in
              <input
                type="number"
                step="0.1"
                min="0"
                value={mainBgmFadeIn}
                onChange={(e) => setMainBgmFadeIn(numOr(e.target.value, 0))}
              />
              s
            </label>
            <label>
              Fade out
              <input
                type="number"
                step="0.1"
                min="0"
                value={mainBgmFadeOut}
                onChange={(e) => setMainBgmFadeOut(numOr(e.target.value, 0))}
              />
              s
            </label>
          </div>

          <div className="field">
            <label>
              Volume ({Math.round(mainBgmVolumePct)}%)
              <InfoTooltip text="100% plays the music at its original volume. Kept low by default so it doesn't compete with the voiceover." />
            </label>
            <input
              type="range"
              min="0"
              max="100"
              step="1"
              value={mainBgmVolumePct}
              onChange={(e) => setMainBgmVolumePct(numOr(e.target.value, 12))}
            />
          </div>
        </fieldset>
      </div>
    </div>
  );
}
