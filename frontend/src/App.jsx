import { useEffect, useState } from "react";
import { getMe, logout } from "./api.js";
import Login from "./components/Login.jsx";
import Setup from "./components/Setup.jsx";
import Writer from "./components/Writer.jsx";

function quotaText({ is_admin, local_mode, quota }) {
  if (quota.budget_reached) return "AI budget used up this month";
  if (local_mode) return "local mode";
  if (is_admin) return "admin · no daily limit";
  return `${quota.reviews_left} of ${quota.daily_reviews} checks left today`;
}

export default function App() {
  // undefined = still checking the session, null = signed out
  const [me, setMe] = useState(undefined);
  // The essay created on the backend: { id, topic, modifiers, ... }
  const [essay, setEssay] = useState(null);

  // Re-read the user after anything that uses up the daily quota
  const refreshMe = () =>
    getMe()
      .then(setMe)
      .catch((e) => e.status === 401 && setMe(null));

  useEffect(() => {
    getMe()
      .then(setMe)
      .catch(() => setMe(null));
  }, []);

  const signOut = async () => {
    await logout().catch(() => {});
    setEssay(null);
    setMe(null);
  };

  return (
    <>
      <header className="masthead">
        <div className="masthead-inner">
          <div className="brand">
            <h1>Essay Coach</h1>
            <p>an aid, not a shortcut</p>
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
      </main>
    </>
  );
}
