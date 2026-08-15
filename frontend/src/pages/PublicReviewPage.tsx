import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../api";
import { fmtTime, type ReviewSession, type ReviewVersion } from "../types";

function CommentForm({
  onAdd,
  placeholder,
  defaultTime = 0,
  autoFocus = false,
}: {
  onAdd: (timeS: number, body: string) => Promise<void> | void;
  placeholder: string;
  defaultTime?: number;
  autoFocus?: boolean;
}) {
  const [body, setBody] = useState("");
  const [time, setTime] = useState(String(defaultTime));
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!body.trim()) return;
    setBusy(true);
    setErr(null);
    try {
      await onAdd(Number(time) || 0, body.trim());
      setBody("");
      setTime("0");
    } catch (err) {
      setErr(err instanceof Error ? err.message : "Failed to add comment");
    } finally {
      setBusy(false);
    }
  };

  return (
    <form className="rs-comment-form" onSubmit={submit}>
      <div className="rs-comment-form-row">
        <input type="number" min={0} step={0.1} value={time} onChange={(e) => setTime(e.target.value)} className="rs-time-input" aria-label="Time in seconds" />
        <input type="text" value={body} onChange={(e) => setBody(e.target.value)} placeholder={placeholder} autoFocus={autoFocus} className="rs-comment-input" />
        <button type="submit" className="rs-btn approve sm" disabled={busy}>
          {busy ? "…" : "Comment"}
        </button>
      </div>
      {err && <div className="error">{err}</div>}
    </form>
  );
}

export default function PublicReviewPage() {
  const { token } = useParams<{ token: string }>();
  const [session, setSession] = useState<ReviewSession | null>(null);
  const [current, setCurrent] = useState<ReviewVersion | null>(null);
  const [playing, setPlaying] = useState(false);
  const [name, setName] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);
  const audioRef = useRef<HTMLAudioElement>(null);

  useEffect(() => {
    if (!token) return;
    api
      .publicSession(token)
      .then((s) => {
        setSession(s);
        const versions = s.versions ?? [];
        setCurrent(versions.length ? versions[0] : null);
      })
      .catch((e) => setErr(e instanceof Error ? e.message : "Review link not found"))
      .finally(() => setLoaded(true));
  }, [token]);

  const addComment = async (timeS: number, body: string) => {
    if (!token || !current) return;
    const c = await api.publicAddComment(token, current.id, timeS, body, name || "Reviewer");
    setSession((s) =>
      s
        ? {
            ...s,
            versions: (s.versions ?? []).map((v) =>
              v.id === current.id ? { ...v, comments: [...v.comments, c] } : v
            ),
          }
        : s
    );
  };

  if (err) {
    return (
      <div className="session-page">
        <div className="card error">🔗 {err} — this review link doesn't exist.</div>
      </div>
    );
  }

  if (!loaded || !session) {
    return <div className="session-page muted">Loading review…</div>;
  }

  const resolvedCount = current?.comments.filter((c) => c.resolved).length ?? 0;
  const openCount = (current?.comments.length ?? 0) - resolvedCount;

  return (
    <div className="public-review">
      <div className="public-review-head">
        <div className="public-review-brand">
          <img src="/logo.png" alt="SoundHub" className="landing-nav-logo" /> SoundHub
          <span className="public-review-sep">·</span>
          <span className="public-review-for">review for {session.name}</span>
        </div>
        <div className={`rs-status ${current?.status === "approved" ? "status-approved" : current?.status === "needs_changes" ? "status-changes" : "status-review"}`}>
          {current?.status === "approved"
            ? `${current.label} · Approved ✓`
            : current?.status === "needs_changes"
              ? `${current?.label} · Needs changes`
              : `${current?.label ?? ""} · Ready for approval`}
        </div>
      </div>

      <div className="public-review-intro">
        <p>
          Hi — <strong>{session.owner_username}</strong> shared this version for feedback.
          Listen and drop a comment at the exact moment. No account needed.
        </p>
      </div>

      {current ? (
        <>
          <div className="rs rs-real">
            <div className="rs-wave-wrap">
              <div className={`rs-playhead ${playing ? "run" : ""}`} style={{ animationDuration: `${Math.max(3, current.duration_s)}s` }} />
              <div className="rs-wave">
                {current.waveform.map((h, i) => (
                  <span key={i} style={{ height: `${Math.max(3, h * 100)}%` }} />
                ))}
              </div>
              <button type="button" className="rs-play" onClick={() => setPlaying((p) => !p)}>
                {playing ? "❚❚" : "▶"}
              </button>
              {current.comments
                .filter((c) => !c.resolved)
                .map((c) => (
                  <span key={c.id} className="rs-pin" style={{ left: `${(c.time_s / Math.max(1, current.duration_s)) * 100}%` }} title={`${fmtTime(c.time_s)} · ${c.author_name}`}>
                    ●
                  </span>
                ))}
              <span className="rs-time">0:00</span>
              <span className="rs-time right">{fmtTime(current.duration_s)}</span>
            </div>
            <audio ref={audioRef} src={api.versionAudioUrl(session.id, current.id)} onEnded={() => setPlaying(false)} controls className="rs-audio" />
            {current.waveform_synthetic && (
              <div className="public-review-note">Waveform is illustrative — this file isn't a WAV.</div>
            )}
          </div>

          <div className="public-review-comments">
            <div className="rs-comments-head">
              <span>Feedback</span>
              <span className="rs-count">{openCount} open · {resolvedCount} resolved</span>
            </div>
            {current.comments.length === 0 && (
              <div className="rs-empty">No comments yet — be the first to leave feedback.</div>
            )}
            {current.comments.map((c) => (
              <div key={c.id} className={`rs-comment ${c.resolved ? "resolved" : ""}`}>
                <div className="rs-comment-time">{fmtTime(c.time_s)}</div>
                <div className="rs-comment-body">
                  <div className="rs-comment-author">
                    <span className="rs-avatar">{c.author_name[0]?.toUpperCase() ?? "?"}</span>
                    <strong>{c.author_name}</strong>
                  </div>
                  <p>{c.body}</p>
                </div>
              </div>
            ))}

            <div className="public-review-form">
              <div className="public-review-form-head">Leave feedback</div>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Your name (optional)"
                className="rs-comment-input"
                style={{ marginBottom: 8 }}
              />
              <CommentForm onAdd={addComment} placeholder="e.g. Bass masks the vocal at this moment…" autoFocus />
            </div>
          </div>
        </>
      ) : (
        <div className="card muted">No versions shared yet.</div>
      )}
    </div>
  );
}
