import { useRef, useState } from "react";
import { uploadFile } from "./api";

// A single "Browse…" button (opens the native OS file picker so the operator
// can pick literally any file on their Mac) plus a read-out of whatever is
// currently selected. No dropdown — there is nothing to choose from besides
// "the default" (shown until overridden) or "whatever was just picked".
export default function FileUploadField({
  filename,
  onSelected,
  category,
  accept,
  emptyHint,
  isDefault,
  previewUrl,
}) {
  const inputRef = useRef(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");

  const handleFile = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    setUploading(true);
    setError("");
    try {
      const uploaded = await uploadFile(file, category);
      onSelected(uploaded);
    } catch (err) {
      setError(err.message);
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="file-upload-field">
      <div className="file-upload-row">
        <button
          type="button"
          className="browse-btn"
          onClick={() => inputRef.current?.click()}
          disabled={uploading}
        >
          {uploading ? "Uploading…" : "Browse…"}
        </button>
        <span className="file-upload-name">
          {filename ? (
            <>
              {filename}
              {isDefault && <span className="default-flag"> (default)</span>}
            </>
          ) : (
            <span className="file-upload-empty">{emptyHint}</span>
          )}
        </span>
        <input ref={inputRef} type="file" accept={accept} style={{ display: "none" }} onChange={handleFile} />
      </div>
      {previewUrl && (
        <audio controls src={previewUrl} className="audio-preview">
          Your browser cannot play audio previews.
        </audio>
      )}
      {error && <p className="file-browse-error">{error}</p>}
    </div>
  );
}
