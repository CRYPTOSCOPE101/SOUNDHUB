import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../api";
import { fmtClock, WaveformCanvas, CommentComposer, ApprovalPanel } from "../components/ReviewShared";
import { fmtTime, humanSize, type ReviewSession, type ReviewVersion } from "../types";

export default function PublicReviewPage() {
  const { token } = useParams<{ token: string }>();
  const [session, setSession] = useState<ReviewSession | null>(null);
  const [current, setCurrent] = useState<ReviewVersion | null>(null);
  const [playing, setPlaying] = useState(false);
  const [position, setPosition] = useState(0);
  const [loop, setLoop] = useState<{ start: number; end: number } | null>(null);
  const [mode, setMode] = useState<"seek" | "comment">("seek");
  const [pendingComment, setPendingComment] = useState<number | null>(null);
  const [name, setName] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [needPassword, setNeedPassword] = useState(false);
  const [password, setPassword] = useState("");
  const [actor] = useState("");
  const audioRef = useRef<HTMLAudioElement>(null);
  const rafRef = useRef<number | null>(null);
  const [approvals, setApprovals] = useState(session?.approvals ?? []);

  const load = useCallback(
    async (pwd?: string) => {
      if (!token) return;
      setErr(null);
      setLoaded(false);
      try {
        const s = await api.publicSession(token, { actor, password: pwd });
        setSession(s);
        setApprovals(s.approvals ?? []);
        const versions = s.versions ?? [];
        setCurrent(versions.length ? versions[0] : null);
        setNeedPassword(false);
      } catch (e) {
        const msg = e instanceof Error ? e.message : "Review link not found";
        if (msg.toLowerCase().includes("password")) {
          setNeedPassword(true);
        } else {
          setErr(msg);
        }
      } finally {
        setLoaded(true);
      }
    },
    [token, actor]
  );

  useEffect(() => {
    void load();
  }, [load]);

  // playhead sync
  useEffect(() => {
    const tick = () => {
      const a = audioRef.current;
      if (a) {
        setPosition(a.currentTime);
        if (loop && a.currentTime >= loop.end) {
          a.currentTime = loop.start;
          a.play().catch(() => undefined);
        }
      }
      rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [loop]);

  const togglePlay = () => {
    const a = audioRef.current;
    if (!a) return;
    if (playing) a.pause();
    else void a.play().catch(() => undefined);
  };

  const seek = (t: number) => {
    const a = audioRef.current;
    if (a) a.currentTime = t;
    setPosition(t);
  };

  const addComment = async (timeS: number, body: string, authorName: string) => {
    if (!token || !current) return;
    const c = await api.publicAddComment(token, current.id, timeS, body, authorName || name || "Reviewer");
    setSession((s) =>
      s
        ? {
            ...s,
            versions: (s.versions ?? []).map((v) => (v.id === current.id ? { ...v, comments: [...v.comments, c] } : v)),
          }
        : s
    );
    setPendingComment(null);
  };

  const onApprovalDone = useCallback(async () => {
    if (!token) return;
    const s = await api.publicSession(token, { actor, password: password || undefined });
    setSession(s);
    setApprovals(s.approvals ?? []);
    setCurrent((c) => {
      const v = (s.versions ?? []).find((x) => x.id === c?.id);
      return v ?? c;
    });
  }, [token, actor, password]);

  if (err) {
    return (
      <div className="session-page">
        <div className="card error">🔗 {err} — this review link doesn't exist.</div>
      </div>
    );
  }

  if (needPassword) {
    return (
      <div className="session-page">
        <div className="card">
          <h2 className="session-title">🔒 Password protected</h2>
          <p className="muted">This review link is protected. Enter the password the owner shared with you.</p>
          <form
            className="session-create"
            onSubmit={(e) => {
              e.preventDefault();
              void load(password);
            }}
          >
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Password"
              className="session-name-input"
              autoFocus
            />
            <button type="submit" className="btn">
              Open review
            </button>
          </form>
        </div>
      </div>
    );
  }

  if (!loaded || !session) {
    return <div className="session-page muted">Loading review…</div>;
  }

  const resolvedCount = current?.comments.filter((c) => c.resolved).length ?? 0;
  const openCount = (current?.comments.length ?? 0) - resolvedCount;
  const canDownload = session.share_permission === "download";

  return (
    <div className="public-review">
      <div className="public-review-head">
        <div className="public-review-brand">
          <img src="/logo.png" alt="SoundHub" className="landing-nav-logo" /> SoundHub
          <span className="public-review-sep">·</span>
          <span className="public-review-for">review for {session.name}</span>
        </div>
        <div
          className={`rs-status ${
            current?.status === "approved" ? "status-approved" : current?.status === "needs_changes" ? "status-changes" : "status-review"
          }`}
        >
          {current?.status === "approved"
            ? `${current.label} · Approved ✓`
            : current?.status === "needs_changes"
              ? `${current?.label} · Needs changes`
              : `${current?.label ?? ""} · Ready for approval`}
        </div>
      </div>

      <div className="public-review-intro">
        <p>
          Hi — <strong>{session.owner_username}</strong> shared this version for feedback. Listen and drop a comment
          at the exact moment. No account needed.
        </p>
        {session.share_permission !== "comment" && (
          <p className="public-review-note">
            {canDownload ? "You can comment and download." : "View only — comments are disabled on this link."}
          </p>
        )}
      </div>

      {current ? (
        <>
          <div className="rs rs-real">
            <div className="rs-player">
              <div className="rs-wave-wrap">
                <button type="button" className="rs-play" onClick={togglePlay} title={playing ? "Pause" : "Play"}>
                  {playing ? "❚❚" : "▶"}
                </button>
                <WaveformCanvas
                  peaks={current.waveform}
                  duration={current.duration_s}
                  position={position}
                  playing={playing}
                  comments={current.comments}
                  loop={loop}
                  mode={session.share_permission === "comment" || canDownload ? mode : "seek"}
                  onAddComment={(t) => setPendingComment(t)}
                  onLoop={(start, end) => {
                    if (Math.abs(end - start) < 0.15) setLoop(null);
                    else setLoop({ start, end });
                  }}
                  highlightComment={null}
                />
                <div className="rs-time">{fmtClock(position)}</div>
                <div className="rs-time right">{fmtClock(current.duration_s)}</div>
              </div>

              <div className="rs-player-row">
                {session.share_permission === "comment" || canDownload ? (
                  <div className="rs-seg">
                    <button type="button" className={`rs-seg-btn ${mode === "seek" ? "active" : ""}`} onClick={() => setMode("seek")}>
                      Seek / loop
                    </button>
                    <button type="button" className={`rs-seg-btn ${mode === "comment" ? "active" : ""}`} onClick={() => setMode("comment")}>
                      Add comment
                    </button>
                  </div>
                ) : (
                  <span className="rs-file-meta">View only</span>
                )}
                {loop && (
                  <button type="button" className="rs-btn ghost sm" onClick={() => setLoop(null)}>
                    loop {fmtClock(loop.start)}–{fmtClock(loop.end)} ✕
                  </button>
                )}
                <span className="rs-file-meta">
                  {current.filename} · {humanSize(current.size)} · {current.audio_format}
                </span>
              </div>

              <audio
                ref={audioRef}
                src={api.audioUrl(api.publicAudioUrl(token ?? "", current.id))}
                onPlay={() => setPlaying(true)}
                onPause={() => setPlaying(false)}
                onEnded={() => setPlaying(false)}
                className="rs-audio"
                preload="auto"
              />

              {pendingComment != null && (
                <CommentComposer
                  timeS={pendingComment}
                  showName
                  placeholder="Comment at this point…"
                  autoFocus
                  onCancel={() => setPendingComment(null)}
                  onSubmit={(t, body, authorName) => addComment(t, body, authorName)}
                />
              )}
            </div>

            {current.waveform_synthetic && <div className="public-review-note">Waveform is illustrative — this file isn't a WAV.</div>}
          </div>

          <div className="public-review-lower">
            <div className="public-review-comments">
              <div className="rs-comments-head">
                <span>Feedback</span>
                <span className="rs-count">
                  {openCount} open · {resolvedCount} resolved
                </span>
              </div>
              {current.comments.length === 0 && <div className="rs-empty">No comments yet — be the first to leave feedback.</div>}
              {current.comments.map((c) => (
                <div key={c.id} className={`rs-comment ${c.resolved ? "resolved" : ""}`}>
                  <button type="button" className="rs-comment-time" onClick={() => seek(c.time_s)} title={`Seek to ${fmtTime(c.time_s)}`}>
                    {fmtTime(c.time_s)}
                  </button>
                  <div className="rs-comment-body">
                    <div className="rs-comment-author">
                      <span className="rs-avatar">{c.author_name[0]?.toUpperCase() ?? "?"}</span>
                      <strong>{c.author_name}</strong>
                    </div>
                    <p>{c.body}</p>
                  </div>
                </div>
              ))}

              {(session.share_permission === "comment" || canDownload) && (
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
                  <CommentComposer
                    timeS={0}
                    showName={false}
                    placeholder="e.g. Bass masks the vocal at this moment…"
                    autoFocus
                    onSubmit={(t, body, authorName) => addComment(t, body, authorName || name)}
                  />
                </div>
              )}
            </div>

            {(session.share_permission === "comment" || canDownload) && (
              <div className="public-review-approve">
                <ApprovalPanel token={token} version={current} approvals={approvals.filter((a) => a.version_id === current.id)} onDone={onApprovalDone} />
              </div>
            )}
          </div>
        </>
      ) : (
        <div className="card muted">No versions shared yet.</div>
      )}
    </div>
  );
}
