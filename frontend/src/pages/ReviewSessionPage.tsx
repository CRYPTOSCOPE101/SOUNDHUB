import { useState } from "react";
import { Link } from "react-router-dom";
import ReviewSession from "../components/ReviewSession";

export default function ReviewSessionPage() {
  const [copied, setCopied] = useState(false);

  const copyLink = async () => {
    try {
      await navigator.clipboard.writeText("https://soundhub.app/r/neon-warehouse-v13");
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      setCopied(false);
    }
  };

  return (
    <div className="session-page">
      <div className="session-top">
        <div>
          <Link to="/" className="session-back">← back to home</Link>
          <h1 className="session-title">Demo review session</h1>
          <p className="muted session-sub">
            Prototype of the review flow: share → timestamped feedback → version → approve.
            Play the track, click a version, resolve a comment, approve v13.
          </p>
        </div>
        <div className="session-share">
          <code className="session-link">soundhub.app/r/neon-warehouse-v13</code>
          <button type="button" className="btn" onClick={copyLink}>
            {copied ? "✓ Copied" : "Copy review link"}
          </button>
        </div>
      </div>

      <ReviewSession />

      <div className="session-note">
        <strong>This is the workflow prototype.</strong> The real flow will upload your own
        bounce (WAV/MP3), let reviewers comment without an account, and push comments back
        into the DAW panel. Marketplace and on-chain settlement are the second layer.
      </div>
    </div>
  );
}
