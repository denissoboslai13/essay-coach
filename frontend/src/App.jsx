import { useState } from "react";
import Setup from "./components/Setup.jsx";
import Writer from "./components/Writer.jsx";

export default function App() {
  // The essay created on the backend: { id, topic, modifiers, ... }
  const [essay, setEssay] = useState(null);

  return (
    <>
      <header className="masthead">
        <div className="masthead-inner">
          <h1>Essay Coach</h1>
          <p>an aid, not a shortcut</p>
        </div>
      </header>
      <main>
        {essay ? (
          <>
            <Writer key={essay.id} essay={essay} />
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
