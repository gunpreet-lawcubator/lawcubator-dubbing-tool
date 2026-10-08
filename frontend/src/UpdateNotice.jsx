import { useEffect, useState } from "react";
import { fetchUpdateCheck, applyUpdate } from "./api";

const SEEN_KEY = "lawcubator_update_seen";

export default function UpdateNotice() {
  const [info, setInfo] = useState(null);
  const [open, setOpen] = useState(false);
  const [phase, setPhase] = useState("idle"); // idle | updating | restarting
  const [error, setError] = useState("");

  useEffect(() => {
    fetchUpdateCheck()
      .then((u) => {
        if (!u.update_available) return;
        setInfo(u);
        // Pop up once per new version; after "Later" only the header pill remains.
        try {
          if (localStorage.getItem(SEEN_KEY) !== u.latest) setOpen(true);
        } catch {
          setOpen(true);
        }
      })
      .catch(() => {});
  }, []);

  const later = () => {
    try {
      localStorage.setItem(SEEN_KEY, info.latest);
    } catch {
      /* ignore */
    }
    setOpen(false);
  };

  const updateNow = async () => {
    setError("");
    setPhase("updating");
    try {
      await applyUpdate();
    } catch (e) {
      setError(e.message);
      setPhase("idle");
      return;
    }
    setPhase("restarting");
    // The app restarts itself; wait for it to answer with the new version, then reload.
    const started = Date.now();
    const poll = async () => {
      try {
        const u = await fetchUpdateCheck();
        if (u.current === info.latest) {
          window.location.reload();
          return;
        }
      } catch {
        /* still restarting */
      }
      if (Date.now() - started > 120000) {
        setError("The update is taking longer than usual. Close this window and open the app again.");
        setPhase("idle");
        return;
      }
      setTimeout(poll, 2000);
    };
    setTimeout(poll, 4000);
  };

  if (!info) return null;

  return (
    <>
      <button className="update-pill" onClick={() => setOpen(true)}>
        &#8679; Update available (v{info.latest})
      </button>
      {open && (
        <div className="modal-overlay" onClick={phase === "idle" ? later : undefined}>
          <div className="modal-panel update-panel" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>Update available</h2>
              {phase === "idle" && (
                <button className="modal-close" onClick={later} aria-label="Later">
                  &times;
                </button>
              )}
            </div>
            <p>
              Version <strong>{info.latest}</strong> is ready (you have {info.current}).
            </p>
            {info.notes && <pre className="update-notes">{info.notes}</pre>}
            {phase === "idle" && (
              <p className="update-hint">Updating takes about a minute. Don't start it in the middle of a dub.</p>
            )}
            {phase === "updating" && <p>Downloading and installing…</p>}
            {phase === "restarting" && <p>Restarting the app. This page will reload by itself — please don't close the black window.</p>}
            {error && <div className="error">{error}</div>}
            {phase === "idle" && (
              <div className="voice-form-actions">
                <button className="generate-btn" onClick={updateNow}>
                  Update now
                </button>
                <button onClick={later}>Later</button>
              </div>
            )}
          </div>
        </div>
      )}
    </>
  );
}
