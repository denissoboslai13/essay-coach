import { useEffect, useRef } from "react";

// Finds the passage in the current text. Returns [start, end] or null (e.g. after the user edited it).
function findPassage(text, passage) {
  if (!passage) return null;
  let start = text.indexOf(passage);
  if (start === -1) start = text.toLowerCase().indexOf(passage.toLowerCase());
  return start === -1 ? null : [start, start + passage.length];
}

// A textarea can't style parts of its text, so a "backdrop" div with the same text sits behind it
// and draws the highlight. The textarea itself is transparent.
export default function HighlightEditor({ value, onChange, highlight, onBlockedPaste, ...rest }) {
  const textareaRef = useRef(null);
  const backdropRef = useRef(null);
  const range = findPassage(value, highlight);

  const syncScroll = () => {
    backdropRef.current.scrollTop = textareaRef.current.scrollTop;
  };

  // Scroll the highlighted passage into view if it's outside the visible area
  useEffect(() => {
    const mark = backdropRef.current.querySelector("mark");
    if (!mark) return;
    const textarea = textareaRef.current;
    const top = mark.offsetTop;
    const visible = top >= textarea.scrollTop && top <= textarea.scrollTop + textarea.clientHeight - 40;
    if (!visible) {
      textarea.scrollTop = Math.max(0, top - textarea.clientHeight / 3);
      syncScroll();
    }
  }, [highlight, value]);

  return (
    <div className="editor">
      <div className="editor-backdrop" ref={backdropRef} aria-hidden="true">
        {range ? (
          <>
            {value.slice(0, range[0])}
            <mark>{value.slice(range[0], range[1])}</mark>
            {value.slice(range[1])}
          </>
        ) : (
          value
        )}
        {/* keeps the last line's height in sync with the textarea */}
        {"\n "}
      </div>
      <textarea
        ref={textareaRef}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onScroll={syncScroll}
        onPaste={onBlockedPaste}
        onDrop={onBlockedPaste}
        // Browser spellcheck would mark (and offer fixes for) the errors the learner should find
        spellCheck={false}
        autoCorrect="off"
        autoCapitalize="off"
        {...rest}
      />
    </div>
  );
}
