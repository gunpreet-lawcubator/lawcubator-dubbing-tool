export default function SubtitleEditor({ segments, edits, onChange, onApply, onClose, saving, languageLabel }) {
  const changedCount = Object.entries(edits).filter(([i, text]) => text !== segments[i].translated).length;

  return (
    <aside className="subtitle-editor">
      <div className="subtitle-editor-header">
        <h2>Edit {languageLabel || ""} subtitles</h2>
        <button className="modal-close" onClick={onClose} aria-label="Close subtitle editor">
          &times;
        </button>
      </div>
      <p className="subtitle-editor-hint">Fixes the on-screen text only. The spoken audio is not changed.</p>

      <div className="subtitle-editor-list">
        {segments.map((seg, i) => {
          const value = edits[i] ?? seg.translated;
          return (
            <div key={i} className={`subtitle-editor-item${value !== seg.translated ? " edited" : ""}`}>
              <div className="subtitle-editor-meta">
                <span>
                  {seg.start.toFixed(1)}s&ndash;{seg.end.toFixed(1)}s
                </span>
                <span className="subtitle-editor-english">{seg.english}</span>
              </div>
              <textarea rows={3} value={value} onChange={(e) => onChange(i, e.target.value)} />
            </div>
          );
        })}
      </div>

      <div className="subtitle-editor-footer">
        <button className="generate-btn" onClick={onApply} disabled={saving || changedCount === 0}>
          {saving ? "Applying…" : changedCount ? `Apply ${changedCount} edit${changedCount > 1 ? "s" : ""}` : "No changes yet"}
        </button>
      </div>
    </aside>
  );
}
