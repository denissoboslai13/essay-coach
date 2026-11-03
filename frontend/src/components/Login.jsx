import { useEffect, useRef, useState } from "react";
import { getAuthConfig, loginWithGoogle } from "../api.js";

const GOOGLE_SCRIPT = "https://accounts.google.com/gsi/client";
// Backend's answer when an unknown account signs in without an invite code
const INVITE_REQUIRED = "invite_required";

// Loads Google Identity Services once
let googleScript = null;
function loadGoogle() {
  googleScript ??= new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = GOOGLE_SCRIPT;
    script.async = true;
    script.onload = resolve;
    script.onerror = () => {
      googleScript = null;
      reject(new Error("Could not load Google sign-in."));
    };
    document.head.appendChild(script);
  });
  return googleScript;
}

export default function Login({ onLogin }) {
  const [config, setConfig] = useState(null);
  // Set when an invite code is needed. Google's token is kept so the user doesn't sign in twice
  // (it is valid for an hour)
  const [credential, setCredential] = useState(null);
  const [invite, setInvite] = useState("");
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const buttonRef = useRef(null);

  const signIn = async (googleCredential, inviteCode = null) => {
    setLoading(true);
    setError(null);
    try {
      onLogin(await loginWithGoogle(googleCredential, inviteCode));
    } catch (e) {
      // 403 = no code yet, or a wrong one: ask for a code
      if (e.status === 403) setCredential(googleCredential);
      if (e.message !== INVITE_REQUIRED) setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    getAuthConfig().then(setConfig).catch((e) => setError(e.message));
  }, []);

  const needsInvite = credential !== null;

  useEffect(() => {
    if (!config?.google_client_id || needsInvite) return;
    loadGoogle()
      .then(() => {
        window.google.accounts.id.initialize({
          client_id: config.google_client_id,
          callback: (response) => signIn(response.credential),
        });
        window.google.accounts.id.renderButton(buttonRef.current, { theme: "outline", size: "large", width: 280 });
      })
      .catch((e) => setError(e.message));
  }, [config, needsInvite]);

  return (
    <section className="login">
      <div className="card">
        <p className="eyebrow">Sign in</p>
        <h2>Write it yourself.</h2>
        <p className="lead">
          Essay Coach reads your essay and asks questions that help you find your own mistakes. It never rewrites
          your text.
        </p>

        {needsInvite ? (
          <form
            className="invite-form"
            onSubmit={(e) => {
              e.preventDefault();
              signIn(credential, invite);
            }}
          >
            <p>Essay Coach is invite-only for now. Enter the code you received.</p>
            <div>
              <input
                type="text"
                value={invite}
                onChange={(e) => setInvite(e.target.value)}
                placeholder="ABCD-EFGH"
                aria-label="Invite code"
                autoFocus
              />
              <button className="primary" disabled={loading || !invite.trim()}>
                {loading ? "Checking..." : "Continue"}
              </button>
            </div>
            <button type="button" className="link" onClick={() => setCredential(null)}>
              Use a different Google account
            </button>
          </form>
        ) : config && !config.google_client_id ? (
          <p className="notice">
            Sign-in is not configured. Set GOOGLE_CLIENT_ID in backend/.env, or LOCAL_MODE=true for local development.
          </p>
        ) : (
          <div className="google-button" ref={buttonRef} />
        )}

        {error && <p className="notice">{error}</p>}
      </div>
    </section>
  );
}
