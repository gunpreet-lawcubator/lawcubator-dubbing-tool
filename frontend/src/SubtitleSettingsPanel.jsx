import InfoTooltip from "./InfoTooltip";

const numOr = (value, fallback) => {
  const n = parseFloat(value);
  return Number.isFinite(n) ? n : fallback;
};

const intOr = (value, fallback) => {
  const n = parseInt(value, 10);
  return Number.isFinite(n) ? n : fallback;
};

// Every style value is stored (and sent to the backend) as a percentage of
// the actual video's resolution, so it renders correctly regardless of
// source dimensions. For display, that's converted to plain pixels assuming
// a 1080p reference — familiar units for Ashin, while the underlying value
// stays resolution-independent. Padding and corner radius are relative to
// the *font size* rather than the frame, so their pixel display is derived
// from the current font size instead of a fixed reference.
const REF_HEIGHT = 1080;
const REF_WIDTH = 1920;

const pxFromHeightPct = (pct) => Math.round(pct * REF_HEIGHT);
const pctFromHeightPx = (px) => px / REF_HEIGHT;
const pxFromWidthPct = (pct) => Math.round(pct * REF_WIDTH);
const pctFromWidthPx = (px) => px / REF_WIDTH;

// Reference dimensions the live preview is drawn at — any consistent
// reference gives the same on-screen proportions the real video will use.
const PREVIEW_W = 260;
const PREVIEW_H = 146;
const SAMPLE_LINES = [
  "This is a sample subtitle line",
  "showing your current style settings",
  "across as many lines as you allow",
  "so you can check it before generating",
];

function hexToRgba(hex, opacityPct) {
  const h = (hex || "#000000").replace("#", "");
  const r = parseInt(h.slice(0, 2), 16) || 0;
  const g = parseInt(h.slice(2, 4), 16) || 0;
  const b = parseInt(h.slice(4, 6), 16) || 0;
  const a = Math.max(0, Math.min(100, opacityPct)) / 100;
  return `rgba(${r}, ${g}, ${b}, ${a})`;
}

function SubtitlePreview({
  fontSizePct,
  textColor,
  backgroundColor,
  backgroundOpacity,
  marginVPct,
  marginLrPct,
  paddingXPct,
  paddingYPct,
  cornerRadiusPct,
  maxLinesPerCue,
}) {
  const fontSizePx = Math.max(7, fontSizePct * PREVIEW_H);
  const marginVPx = marginVPct * PREVIEW_H;
  const marginLrPx = marginLrPct * PREVIEW_W;
  const paddingXPx = paddingXPct * fontSizePx;
  const paddingYPx = paddingYPct * fontSizePx;
  const lineCount = Math.max(1, Math.min(intOr(maxLinesPerCue, 2), SAMPLE_LINES.length));
  const lines = SAMPLE_LINES.slice(0, lineCount);

  return (
    <div className="field">
      <label>Preview</label>
      <div className="subtitle-preview-frame" style={{ width: PREVIEW_W, height: PREVIEW_H }}>
        <div className="subtitle-preview-constraint" style={{ left: marginLrPx, right: marginLrPx, bottom: marginVPx }}>
          <div
            className="subtitle-preview-box"
            style={{
              padding: `${paddingYPx}px ${paddingXPx}px`,
              background: hexToRgba(backgroundColor, backgroundOpacity),
              borderRadius: fontSizePx * cornerRadiusPct,
            }}
          >
            <div style={{ color: textColor, fontSize: fontSizePx, lineHeight: 1.35, textAlign: "center" }}>
              {lines.map((line, i) => (
                <div key={i} style={{ whiteSpace: "nowrap" }}>
                  {line}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function SubtitleSettingsPanel({
  subtitlesEnabled,
  setSubtitlesEnabled,
  subtitleFontSizePct,
  setSubtitleFontSizePct,
  subtitleTextColor,
  setSubtitleTextColor,
  subtitleBackgroundColor,
  setSubtitleBackgroundColor,
  subtitleBackgroundOpacity,
  setSubtitleBackgroundOpacity,
  subtitleMarginVPct,
  setSubtitleMarginVPct,
  subtitleMarginLrPct,
  setSubtitleMarginLrPct,
  subtitlePaddingXPct,
  setSubtitlePaddingXPct,
  subtitlePaddingYPct,
  setSubtitlePaddingYPct,
  subtitleCornerRadiusPct,
  setSubtitleCornerRadiusPct,
  subtitleMaxLinesPerCue,
  setSubtitleMaxLinesPerCue,
}) {
  const fontSizePx = pxFromHeightPct(subtitleFontSizePct);

  return (
    <div className="audio-tier">
      <div className="field-checkbox">
        <label>
          <input type="checkbox" checked={subtitlesEnabled} onChange={(e) => setSubtitlesEnabled(e.target.checked)} />
          {" "}
          <span className="tier-label">Subtitles</span>
          <InfoTooltip text="Burned-in captions in the target language. Uncheck to skip them entirely — the video will have no on-screen text at all." />
        </label>
      </div>

      <fieldset className="audio-tier-body" disabled={!subtitlesEnabled}>
        <div className="field-row">
          <div className="field">
            <label>
              Font size <InfoTooltip text="Shown in pixels assuming a 1080p video — it's actually stored as a percentage of height, so it scales correctly on any resolution." />
            </label>
            <div className="input-suffix-row">
              <input
                type="number"
                step="1"
                min="8"
                value={fontSizePx}
                onChange={(e) => setSubtitleFontSizePct(pctFromHeightPx(intOr(e.target.value, 42)))}
              />
              <span>px</span>
            </div>
          </div>
          <div className="field">
            <label>
              Max lines per cue
              <InfoTooltip text="Long sentences that would wrap past this many lines are shown as several sequential captions instead of one oversized block — this is what keeps subtitles from covering too much of the video." />
            </label>
            <input
              type="number"
              step="1"
              min="1"
              value={subtitleMaxLinesPerCue}
              onChange={(e) => setSubtitleMaxLinesPerCue(intOr(e.target.value, 2))}
            />
          </div>
        </div>

        <div className="field-row">
          <div className="field">
            <label>Text color</label>
            <input type="color" value={subtitleTextColor} onChange={(e) => setSubtitleTextColor(e.target.value)} />
          </div>
          <div className="field">
            <label>Box color</label>
            <input
              type="color"
              value={subtitleBackgroundColor}
              onChange={(e) => setSubtitleBackgroundColor(e.target.value)}
            />
          </div>
        </div>

        <div className="field">
          <label>
            Box opacity ({Math.round(subtitleBackgroundOpacity)}%)
            <InfoTooltip text="100% is a solid background box. Lower it for a translucent box that lets the video show through." />
          </label>
          <input
            type="range"
            min="0"
            max="100"
            step="1"
            value={subtitleBackgroundOpacity}
            onChange={(e) => setSubtitleBackgroundOpacity(numOr(e.target.value, 100))}
          />
        </div>

        <div className="field-row">
          <div className="field">
            <label>
              Bottom margin <InfoTooltip text="Pixels at 1080p — stored as a percentage of video height so it scales on any resolution." />
            </label>
            <div className="input-suffix-row">
              <input
                type="number"
                step="1"
                min="0"
                value={pxFromHeightPct(subtitleMarginVPct)}
                onChange={(e) => setSubtitleMarginVPct(pctFromHeightPx(intOr(e.target.value, 60)))}
              />
              <span>px</span>
            </div>
          </div>
          <div className="field">
            <label>
              Side margin <InfoTooltip text="Pixels at 1080p — stored as a percentage of video width so it scales on any resolution." />
            </label>
            <div className="input-suffix-row">
              <input
                type="number"
                step="1"
                min="0"
                value={pxFromWidthPct(subtitleMarginLrPct)}
                onChange={(e) => setSubtitleMarginLrPct(pctFromWidthPx(intOr(e.target.value, 120)))}
              />
              <span>px</span>
            </div>
          </div>
        </div>

        <div className="field-row">
          <div className="field">
            <label>
              Padding (x) <InfoTooltip text="Scales with font size, since the box is sized to fit the text." />
            </label>
            <div className="input-suffix-row">
              <input
                type="number"
                step="1"
                min="0"
                value={Math.round(subtitlePaddingXPct * fontSizePx)}
                onChange={(e) => setSubtitlePaddingXPct(intOr(e.target.value, 25) / Math.max(1, fontSizePx))}
              />
              <span>px</span>
            </div>
          </div>
          <div className="field">
            <label>Padding (y)</label>
            <div className="input-suffix-row">
              <input
                type="number"
                step="1"
                min="0"
                value={Math.round(subtitlePaddingYPct * fontSizePx)}
                onChange={(e) => setSubtitlePaddingYPct(intOr(e.target.value, 15) / Math.max(1, fontSizePx))}
              />
              <span>px</span>
            </div>
          </div>
        </div>

        <div className="field">
          <label>
            Box corner radius <InfoTooltip text="How rounded the caption box's corners are. Also scales with font size." />
          </label>
          <div className="input-suffix-row">
            <input
              type="number"
              step="1"
              min="0"
              value={Math.round(subtitleCornerRadiusPct * fontSizePx)}
              onChange={(e) => setSubtitleCornerRadiusPct(intOr(e.target.value, 15) / Math.max(1, fontSizePx))}
            />
            <span>px</span>
          </div>
        </div>

        <SubtitlePreview
          fontSizePct={subtitleFontSizePct}
          textColor={subtitleTextColor}
          backgroundColor={subtitleBackgroundColor}
          backgroundOpacity={subtitleBackgroundOpacity}
          marginVPct={subtitleMarginVPct}
          marginLrPct={subtitleMarginLrPct}
          paddingXPct={subtitlePaddingXPct}
          paddingYPct={subtitlePaddingYPct}
          cornerRadiusPct={subtitleCornerRadiusPct}
          maxLinesPerCue={subtitleMaxLinesPerCue}
        />
      </fieldset>
    </div>
  );
}
