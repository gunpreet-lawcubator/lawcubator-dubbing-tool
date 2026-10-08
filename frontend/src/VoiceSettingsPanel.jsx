import { useState } from "react";
import InfoTooltip from "./InfoTooltip";

function VoiceForm({ form, setForm, onSave, onCancel, saving }) {
  return (
    <div className="voice-form">
      <div className="field-row">
        <div className="field">
          <label>Language name</label>
          <input
            type="text"
            value={form.label}
            onChange={(e) => setForm((f) => ({ ...f, label: e.target.value }))}
            placeholder="e.g. Tamil"
          />
        </div>
        <div className="field">
          <label>ElevenLabs voice ID</label>
          <input
            type="text"
            value={form.voiceId}
            onChange={(e) => setForm((f) => ({ ...f, voiceId: e.target.value }))}
            placeholder="Paste from ElevenLabs"
          />
        </div>
      </div>
      <div className="field-checkbox">
        <label>
          <input
            type="checkbox"
            checked={form.isCjk}
            onChange={(e) => setForm((f) => ({ ...f, isCjk: e.target.checked }))}
          />
          {" "}No spaces between words (like Chinese or Japanese)
          <InfoTooltip text="Leave this unchecked for almost every language. Only check it for languages written without spaces between words, so subtitles wrap correctly instead of running off the screen." />
        </label>
      </div>
      <div className="voice-form-actions">
        <button onClick={onSave} disabled={saving}>
          {saving ? "Saving…" : "Save"}
        </button>
        <button onClick={onCancel} disabled={saving}>
          Cancel
        </button>
      </div>
    </div>
  );
}

export default function VoiceSettingsPanel({ voices, onAdd, onUpdate, onDelete, onClose }) {
  const [editingCode, setEditingCode] = useState(null);
  const [form, setForm] = useState({ label: "", voiceId: "", isCjk: false });
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  const startEdit = (v) => {
    setEditingCode(v.code);
    setForm({ label: v.label, voiceId: v.voice_id, isCjk: v.is_cjk });
    setError("");
  };

  const startAdd = () => {
    setEditingCode("__new__");
    setForm({ label: "", voiceId: "", isCjk: false });
    setError("");
  };

  const cancelEdit = () => {
    setEditingCode(null);
    setError("");
  };

  const handleSave = async () => {
    if (!form.label.trim() || !form.voiceId.trim()) {
      setError("Both a language name and a voice ID are required.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      if (editingCode === "__new__") {
        await onAdd(form);
      } else {
        await onUpdate(editingCode, form);
      }
      setEditingCode(null);
    } catch (e) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (code) => {
    if (!window.confirm("Remove this language? Videos already generated in it are unaffected.")) return;
    setError("");
    try {
      await onDelete(code);
    } catch (e) {
      setError(e.message);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-panel" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Voice &amp; language settings</h2>
          <button className="modal-close" onClick={onClose}>
            &times;
          </button>
        </div>

        {error && <div className="error">{error}</div>}

        <div className="voice-list">
          {voices.map((v) => (
            <div key={v.code} className="voice-row">
              {editingCode === v.code ? (
                <VoiceForm form={form} setForm={setForm} onSave={handleSave} onCancel={cancelEdit} saving={saving} />
              ) : (
                <>
                  <div className="voice-row-info">
                    <strong>{v.label}</strong>
                    <span className="voice-id-text">{v.voice_id}</span>
                    {v.is_cjk && <span className="voice-cjk-badge">no spaces (CJK-style)</span>}
                  </div>
                  <div className="voice-row-actions">
                    <button onClick={() => startEdit(v)}>Edit</button>
                    <button onClick={() => handleDelete(v.code)}>Delete</button>
                  </div>
                </>
              )}
            </div>
          ))}
        </div>

        {editingCode === "__new__" ? (
          <div className="voice-row">
            <VoiceForm form={form} setForm={setForm} onSave={handleSave} onCancel={cancelEdit} saving={saving} />
          </div>
        ) : (
          <button className="generate-btn" onClick={startAdd}>
            + Add language
          </button>
        )}
      </div>
    </div>
  );
}
