import { useState } from "react";
import { disputeIssue } from "../api.js";

const VERDICTS = {
  error: "The note stands.",
  acceptable: "You're right. This won't be flagged again.",
  style_preference: "It's a style choice, and yours to make. This won't be flagged again.",
};

function Congratulations({ rounds, fixedTotal }) {
  return (
    <div className="congrats">
      <div className="done-icon" aria-hidden="true">✓</div>
      <h4>No issues left</h4>
      {rounds === 1 ? (
        <p>No problems found on the first try. That is a really clean essay.</p>
      ) : (
        <p>
          You found and fixed {fixedTotal} {fixedTotal === 1 ? "problem" : "problems"} yourself in {rounds} rounds,
          without being given a single answer. That is exactly how writing gets better.
        </p>
      )}
    </div>
  );
}

// `fixedTotal`: number of issues confirmed as fixed across all rounds of this essay
export default function Feedback({ result, onHighlight, fixedTotal }) {
  if (result.status === "too_short" || result.status === "too_long") {
    return <p className="notice">{result.message}</p>;
  }

  const { revision } = result;
  const previous = result.previous_issues.filter((i) => i.resolution);
  return (
    <section>
      <div className="notes-head">
        <h3>Feedback</h3>
        <span className="round">Round {revision.round}</span>
      </div>

      {previous.length > 0 && <SinceLastRound previous={previous} />}

      {result.status === "no_issues" ? (
        <Congratulations rounds={revision.round} fixedTotal={fixedTotal} />
      ) : (
        <>
          <p className="hint">
            Most important first. Hover over an issue to see the passage in your text, fix it yourself, then
            resubmit.
          </p>
          <ul className="issues">
            {revision.issues.map((issue, i) => (
              <IssueItem key={issue.id} number={i + 1} issue={issue} onHighlight={onHighlight} />
            ))}
          </ul>
        </>
      )}

      {revision.strength && (
        <p className="strength">
          <strong>What you do well</strong>
          {revision.strength}
        </p>
      )}
    </section>
  );
}

function SinceLastRound({ previous }) {
  return (
    <div className="since-last">
      <h4>Since last round</h4>
      <ul>
        {previous.map((issue) => {
          const fixed = issue.resolution === "fixed";
          return (
            <li key={issue.id} className={fixed ? "fixed" : "not-fixed"}>
              <span className="mark" aria-label={fixed ? "Fixed" : "Not fixed yet"}>
                {fixed ? "✓" : "✗"}
              </span>
              <span className="type">“{issue.passage}”</span> {issue.resolution_comment}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function IssueItem({ number, issue: initialIssue, onHighlight }) {
  const [issue, setIssue] = useState(initialIssue);
  const [showForm, setShowForm] = useState(false);
  const [comment, setComment] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const dispute = async () => {
    setLoading(true);
    setError(null);
    try {
      setIssue(await disputeIssue(issue.id, comment || null));
      setShowForm(false);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <li
      className="issue"
      tabIndex={0}
      onMouseEnter={() => onHighlight(issue.passage)}
      onMouseLeave={() => onHighlight(null)}
      onFocus={() => onHighlight(issue.passage)}
      onBlur={() => onHighlight(null)}
    >
      <span className="num">{number}</span>
      <span className="category-chip">{issue.category}</span>
      <p className="passage">{issue.passage}</p>
      <p>{issue.problem}</p>
      <p className="question">{issue.question}</p>

      {issue.rule_explanation ? (
        <p className={`rule ${issue.dismissed ? "accepted" : "stands"}`}>
          <span className="verdict">
            {VERDICTS[issue.dispute_verdict] ?? VERDICTS.error}
          </span>
          {issue.rule_explanation}
        </p>
      ) : showForm ? (
        <div className="dispute-form">
          <input
            type="text"
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder="Why do you think it's correct? (optional)"
          />
          <button onClick={dispute} disabled={loading}>
            {loading ? "Asking..." : "Explain"}
          </button>
        </div>
      ) : (
        <button className="link" onClick={() => setShowForm(true)}>
          I don't think that is an error
        </button>
      )}
      {error && <p className="notice">Error: {error}</p>}
    </li>
  );
}
