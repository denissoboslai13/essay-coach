import { useEffect, useState } from "react";
import { getMe, logout } from "./api.js";
import Login from "./components/Login.jsx";
import Privacy from "./components/Privacy.jsx";
import Setup from "./components/Setup.jsx";
import Writer from "./components/Writer.jsx";

function quotaText({ is_admin, local_mode, quota }) {
  if (quota.budget_reached) return "AI budget used up this month";
  if (local_mode) return "local mode";
  if (is_admin) return "admin · no daily limit";
  return `${quota.reviews_left} of ${quota.daily_reviews} checks left today`;
}

// The privacy page has its own address (/#privacy), so it can be linked, e.g. from Google's consent screen
const onPrivacyPage = () => window.location.hash === "#privacy";

export default function App() {
  // undefined = still checking the session, null = signed out
  const [me, setMe] = useState(undefined);
  // The essay created on the backend: { id, topic, modifiers, ... }
  const [essay, setEssay] = useState(null);
  const [privacy, setPrivacy] = useState(onPrivacyPage);

  // Re-read the user after anything that uses up the daily quota
  const refreshMe = () =>
    getMe()
      .then(setMe)
      .catch((e) => e.status === 401 && setMe(null));

  useEffect(() => {
    getMe()
      .then(setMe)
      .catch(() => setMe(null));
    const onHashChange = () => setPrivacy(onPrivacyPage());
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  const signOut = async () => {
    await logout().catch(() => {});
    setEssay(null);
    setMe(null);
  };

  const accountDeleted = () => {
    setEssay(null);
    setMe(null);
    window.location.hash = "";
  };

  return (
    <>
      <header className="masthead">
        <div className="masthead-inner">
          <div className="brand">
            <h1>Essay Coach</h1>
            <p>an aid, not a shortcut</p>
            {/* eslint-disable-next-line no-undef -- injected by vite.config.js */}
            <span className="build">{__BUILD_LABEL__}</span>
          </div>
          {me && (
            <div className="account">
              <span className="quota">{quotaText(me)}</span>
              {/* Local mode has one built-in account and no session to end */}
              {!me.local_mode && (
                <>
                  <span className="email">{me.email}</span>
                  <button className="link" onClick={signOut}>
                    Sign out
                  </button>
                </>
              )}
            </div>
          )}
        </div>
      </header>
      <main>
        {me !== undefined && privacy && <Privacy me={me} onDeleted={accountDeleted} />}
        {/* Hidden, not unmounted, while the privacy page is open, so an essay in progress is kept */}
        <div hidden={privacy}>
          {me === undefined ? null : me === null ? (
            <Login onLogin={setMe} />
          ) : essay ? (
            <>
              <Writer key={essay.id} essay={essay} onUsage={refreshMe} />
              <div className="footer">
                <button onClick={() => setEssay(null)}>&larr; New essay</button>
              </div>
            </>
          ) : (
            <Setup onStart={setEssay} />
          )}
        </div>
      </main>
      {/* Local mode has no accounts on a server, so there is nothing for a privacy page to cover */}
      {me !== undefined && !me?.local_mode && !privacy && (
        <footer className="site-footer">
          <a href="#privacy">Privacy</a>
        </footer>
      )}
    </>
  );
}
