import { useEffect, useState } from "react";
import { fetchAuthStatus, login } from "./api";
import logo from "./assets/logo-lawcubator.png";

export default function AuthGate({ children }) {
  const [state, setState] = useState("checking"); // checking | locked | open
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    fetchAuthStatus()
      .then((s) => setState(s.authenticated ? "open" : "locked"))
      .catch(() => setState("open")); // backend unreachable: let the app show its own errors
  }, []);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await login(password);
      setState("open");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  if (state === "open") return children;
  if (state === "checking") return null;

  return (
    <div className="login-screen">
      <form className="login-card" onSubmit={submit}>
        <img className="brand-logo" src={logo} alt="Lawcubator" />
        <p>Enter the password to open the video editor.</p>
        <input
          type="password"
          autoFocus
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Password"
        />
        {error && <div className="error">{error}</div>}
        <button className="generate-btn" type="submit" disabled={busy || !password}>
          {busy ? "Checking…" : "Open"}
        </button>
      </form>
    </div>
  );
}
