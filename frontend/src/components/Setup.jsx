import { useEffect, useState } from "react";
import { createEssay, getTopics } from "../api.js";

const DEFAULT_MODIFIERS = {
  strict_grading: false,
  timer_minutes: null,
  harder_topics: false,
  min_words: null,
  paste_lock: false,
};

// Turns an input value into a number, or null when empty
const toNumberOrNull = (value) => (value === "" ? null : Number(value));

export default function Setup({ onStart }) {
  const [modifiers, setModifiers] = useState(DEFAULT_MODIFIERS);
  const [topics, setTopics] = useState([]);
  const [error, setError] = useState(null);

  const update = (key, value) => setModifiers((m) => ({ ...m, [key]: value }));

  const loadTopics = () => {
    getTopics(modifiers.harder_topics).then((r) => setTopics(r.topics)).catch((e) => setError(e.message));
  };

  useEffect(loadTopics, [modifiers.harder_topics]);

  const start = async (topic) => {
    setError(null);
    try {
      onStart(await createEssay(topic, modifiers));
    } catch (e) {
      setError(e.message);
    }
  };

  return (
    <section className="setup">
      <div className="card">
        <p className="eyebrow">Difficulty · all optional</p>
        <div className="modifiers">
          <label>
            <input type="checkbox" checked={modifiers.strict_grading} onChange={(e) => update("strict_grading", e.target.checked)} />
            Stricter grading
          </label>
          <label>
            <input type="checkbox" checked={modifiers.harder_topics} onChange={(e) => update("harder_topics", e.target.checked)} />
            Harder topics
          </label>
          <label>
            <input type="checkbox" checked={modifiers.paste_lock} onChange={(e) => update("paste_lock", e.target.checked)} />
            Paste lock
          </label>
          <label>
            Timer
            <input type="number" min="1" max="180" placeholder="off" value={modifiers.timer_minutes ?? ""} onChange={(e) => update("timer_minutes", toNumberOrNull(e.target.value))} />
            min
          </label>
          <label>
            Word target
            <input type="number" min="50" max="2000" placeholder="off" value={modifiers.min_words ?? ""} onChange={(e) => update("min_words", toNumberOrNull(e.target.value))} />
            words (+10% max)
          </label>
        </div>
      </div>

      <div className="card">
        <p className="eyebrow">Pick a topic</p>
        {topics.length > 0 ? (
          <>
            <ol className="topics">
              {topics.map((topic) => (
                <li key={topic}>
                  <span>{topic}</span>
                  <button onClick={() => start(topic)}>Write &rarr;</button>
                </li>
              ))}
            </ol>
            <button onClick={loadTopics}>Other topics</button>
          </>
        ) : (
          <p className="empty-notes">You have finished every topic in this list.</p>
        )}
      </div>

      {error && <p className="notice">Error: {error}</p>}
    </section>
  );
}
