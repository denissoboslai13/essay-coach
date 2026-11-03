import { useEffect, useState } from "react";
import { submitRevision } from "../api.js";
import Feedback from "./Feedback.jsx";
import HighlightEditor from "./HighlightEditor.jsx";

const countWords = (text) => text.split(/\s+/).filter(Boolean).length;

function formatTime(seconds) {
  const m = Math.floor(seconds / 60);
  const s = String(seconds % 60).padStart(2, "0");
  return `${m}:${s}`;
}

function modifierTags(m) {
  const tags = [];
  if (m.strict_grading) tags.push("strict grading");
  if (m.harder_topics) tags.push("harder topic");
  if (m.timer_minutes) tags.push(`timer ${m.timer_minutes} min`);
  if (m.min_words) tags.push(`${m.min_words} words`);
  if (m.paste_lock) tags.push("paste lock");
  return tags.length ? tags : ["no modifiers"];
}

// `onUsage`: called after an AI call, so the remaining daily checks can be refreshed
export default function Writer({ essay, onUsage }) {
  const { modifiers } = essay;
  const [text, setText] = useState("");
  const [result, setResult] = useState(null); // last FeedbackOut from the backend
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);
  const [highlight, setHighlight] = useState(null); // passage hovered in the feedback
  const [fixedTotal, setFixedTotal] = useState(0); // issues fixed across all rounds, for the final message
  const [secondsLeft, setSecondsLeft] = useState(modifiers.timer_minutes ? modifiers.timer_minutes * 60 : null);

  // Countdown runs only until the first submission
  const timerRunning = secondsLeft !== null && secondsLeft > 0 && !result;
  useEffect(() => {
    if (!timerRunning) return;
    const id = setInterval(() => setSecondsLeft((s) => s - 1), 1000);
    return () => clearInterval(id);
  }, [timerRunning]);

  const blockPaste = (e) => {
    if (!modifiers.paste_lock) return;
    e.preventDefault();
    setNotice("Paste lock is on. Type the text yourself.");
  };

  const submit = async () => {
    setLoading(true);
    setError(null);
    setHighlight(null);
    try {
      const next = await submitRevision(essay.id, text);
      const fixedNow = (next.previous_issues ?? []).filter((i) => i.resolution === "fixed").length;
      setFixedTotal((n) => n + fixedNow);
      setResult(next);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
      onUsage();
    }
  };

  const words = countWords(text);
  const maxWords = modifiers.max_words;
  const overLimit = maxWords && words > maxWords;
  const finished = result?.status === "no_issues";

  return (
    <section>
      <div className="writer-head">
        <div>
          <p className="eyebrow">Your topic</p>
          <h2>{essay.topic}</h2>
          <div className="tags">
            {modifierTags(modifiers).map((t) => (
              <span key={t} className="tag">
                {t}
              </span>
            ))}
          </div>
        </div>
        {secondsLeft !== null && (
          <div className={`timer${secondsLeft > 0 ? "" : " up"}`}>
            {secondsLeft > 0 ? formatTime(secondsLeft) : "TIME IS UP"}
          </div>
        )}
      </div>

      <div className="workspace">
        <div>
          <HighlightEditor
            value={text}
            onChange={setText}
            highlight={highlight}
            onBlockedPaste={blockPaste}
            placeholder="Start typing your essay here..."
            aria-label="Essay text"
          />
          <div className="editor-bar">
            <span className={`word-count${overLimit ? " over" : ""}`}>
              Words: {words}
              {modifiers.min_words && ` · target ${modifiers.min_words}, max ${maxWords}`}
            </span>
            <button className="primary" onClick={submit} disabled={loading || finished || overLimit || !text.trim()}>
              {finished ? "Finished ✓" : loading ? "Checking..." : result ? "Resubmit" : "Submit"}
            </button>
          </div>
          {overLimit && (
            <p className="notice">
              You are {words - maxWords} words over the limit. Cut it down to {maxWords} words or fewer to submit.
            </p>
          )}
          {notice && <p className="notice">{notice}</p>}
          {error && <p className="notice">Error: {error}</p>}
        </div>

        <aside className={`notes card${result ? " has-feedback" : ""}`}>
          {result ? (
            <Feedback result={result} onHighlight={setHighlight} fixedTotal={fixedTotal} onUsage={onUsage} />
          ) : (
            <p className="empty-notes">
              Feedback will appear here after you submit. You will get questions, not answers.
            </p>
          )}
        </aside>
      </div>
    </section>
  );
}
