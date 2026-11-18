import { useEffect, useState } from "react";
import { deleteAccount, getAuthConfig } from "../api.js";

// Keep in line with BACKUP_KEEP (days) in backend/.env
const BACKUP_DAYS = 14;

function DeleteAccount({ email, onDeleted }) {
  const [open, setOpen] = useState(false);
  const [typed, setTyped] = useState("");
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  const confirm = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await deleteAccount(typed);
      onDeleted();
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  };

  if (!open) {
    return (
      <button className="danger" onClick={() => setOpen(true)}>
        Delete my account
      </button>
    );
  }

  return (
    <form className="delete-account" onSubmit={confirm}>
      <p>
        This deletes your account and all your essays, revisions and feedback right away. It cannot be undone. Type{" "}
        <strong>{email}</strong> to confirm.
      </p>
      <div>
        <input
          type="email"
          value={typed}
          onChange={(e) => setTyped(e.target.value)}
          aria-label="Your email address"
          autoFocus
        />
        <button className="danger" disabled={busy || typed.trim().toLowerCase() !== email}>
          {busy ? "Deleting..." : "Delete everything"}
        </button>
      </div>
      <button type="button" className="link" onClick={() => setOpen(false)}>
        Cancel
      </button>
      {error && <p className="notice">{error}</p>}
    </form>
  );
}

export default function Privacy({ me, onDeleted }) {
  const [contact, setContact] = useState("");

  useEffect(() => {
    getAuthConfig()
      .then((c) => setContact(c.privacy_contact))
      .catch(() => {});
  }, []);

  const signedIn = me && !me.local_mode;
  const contactText = contact ? (
    <a href={`mailto:${contact}`}>{contact}</a>
  ) : (
    "the person who gave you your invite code"
  );

  return (
    <section className="privacy">
      <div className="card">
        <p className="eyebrow">Privacy</p>
        <h2>What Essay Coach stores about you</h2>
        <p className="lead">
          Essay Coach is a small, invite-only student project, not a company. It stores only what it needs to give
          you feedback, and you can delete all of it yourself.
        </p>

        <h3>What is stored</h3>
        <ul>
          <li>
            <strong>Your Google account:</strong> email address, name and Google's account id. They come from
            Google sign-in. No password is ever stored.
          </li>
          <li>
            <strong>Your essays:</strong> the topic, every version you submit, the feedback you got, your
            disagreements with it, and the difficulty options you chose.
          </li>
          <li>
            <strong>Usage:</strong> when you asked for feedback and how much the AI call cost. This is used for the
            daily limits and the monthly budget.
          </li>
          <li>
            <strong>One cookie</strong> that keeps you signed in. There are no ads, no analytics and no tracking
            cookies.
          </li>
        </ul>

        <h3>Who else sees it</h3>
        <ul>
          <li>
            <strong>Anthropic</strong> (the company behind the Claude AI) receives the text of your essay to write the
            feedback. It does not get your name or email. Anthropic does not use this data to train its models and
            deletes it after a limited time. See{" "}
            <a href="https://www.anthropic.com/legal/privacy" target="_blank" rel="noreferrer">
              Anthropic's privacy policy
            </a>
            .
          </li>
          <li>
            <strong>Google</strong> handles the sign-in.
          </li>
          <li>
            <strong>Cloudflare</strong> passes the connection to the server and provides HTTPS.
          </li>
          <li>
            The person who runs Essay Coach can see the database, for example to fix problems. Nothing is sold or
            shared with anyone else.
          </li>
        </ul>

        <h3>How long it is kept</h3>
        <p>
          Until you delete your account. The data lives on a private server. Backups are made once a day, and each
          one is deleted after {BACKUP_DAYS} days, so deleted data is gone from the backups after {BACKUP_DAYS} days
          too. After a deletion only the cost records stay, with no link to you.
        </p>

        <h3>Your rights</h3>
        <p>
          You can ask to see your data, have it corrected or deleted. Write to {contactText}. You can delete your
          account and everything in it yourself, right here.
        </p>

        {signedIn && (
          <div className="danger-zone">
            <DeleteAccount email={me.email} onDeleted={onDeleted} />
          </div>
        )}

        <p className="back">
          <a href="#">&larr; Back to Essay Coach</a>
        </p>
      </div>
    </section>
  );
}
