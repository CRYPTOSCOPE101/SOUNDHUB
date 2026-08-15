import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../api";
import ReferenceCompare from "../components/ReferenceCompare";
import { fmtClock, WaveformCanvas, CommentComposer, ApprovalPanel } from "../components/ReviewShared";
import {
  fmtTime,
  humanSize,
  type ReferenceComparison,
  type ReferenceTrack,
  type ReviewSession,
  type ReviewVersion,
} from "../types";

const SERVICE_LABELS: Record<string, string> = {
  mix: "Mix",
  master: "Master",
  mix_master: "Mix + master",
  production: "Production",
  stems: "Stem delivery",
};

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
  const [submitNote, setSubmitNote] = useState("");
  const [submitMsg, setSubmitMsg] = useState<string | null>(null);
  const [needPay, setNeedPay] = useState(false);
  const [paying, setPaying] = useState(false);
  const [refs, setRefs] = useState<ReferenceTrack[] | null>(null);
  const [refCompare, setRefCompare] = useState<{ ref: ReferenceTrack; comp: ReferenceComparison } | null>(null);
  const [refErr, setRefErr] = useState<string | null>(null);
  const [refBusy, setRefBusy] = useState<number | null>(null);

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
        setSubmitMsg(null);
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

  // reviewer-visible references (the endpoint enforces comment permission)
  useEffect(() => {
    if (!token) return;
    api
      .publicReferences(token)
      .then((r) => setRefs(r))
      .catch(() => setRefs([]));
  }, [token, session?.round_number]); // eslint-disable-line react-hooks/exhaustive-deps

  const compareReference = async (ref: ReferenceTrack) => {
    if (!token || !current) return;
    setRefBusy(ref.id);
    setRefErr(null);
    try {
      const comp = await api.publicReferenceComparison(token, {
        versionId: current.id,
        referenceId: ref.id,
        startMs: 0,
        endMs: null,
      });
      setRefCompare({ ref, comp });
    } catch (e) {
      setRefErr(e instanceof Error ? e.message : "Comparison failed");
    } finally {
      setRefBusy(null);
    }
  };

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

  const isFeedbackOwner = !!session?.feedback_owner && actor.toLowerCase() === session.feedback_owner.toLowerCase();
  const allDrafts = (session?.versions ?? []).flatMap((v) => v.comments.filter((c) => c.status === "draft")) ?? [];

  const submitFeedback = async () => {
    if (!token) return;
    setSubmitMsg(null);
    setNeedPay(false);
    try {
      await api.publicSubmitFeedback(token, submitNote, actor || "Reviewer");
      setSubmitNote("");
      setSubmitMsg("Feedback submitted — the engineer now has one consolidated list ✓");
      await onApprovalDone();
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Failed to submit";
      setSubmitMsg(msg);
      if (msg.toLowerCase().includes("round")) setNeedPay(true);
    }
  };

  const payExtraRound = async () => {
    if (!token) return;
    setPaying(true);
    setSubmitMsg(null);
    try {
      const c = await api.publicSessionCheckout(token, "extra_round");
      window.location.href = c.checkout_url;
    } catch (e) {
      setSubmitMsg(e instanceof Error ? e.message : "Checkout failed");
    } finally {
      setPaying(false);
    }
  };

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
        <p className="public-review-note">
          Round {session.round_number ?? 1}
          {session.rounds_open === false ? " · this round is closed — notes reopen when the engineer ships the next version" : " · notes are private drafts until the feedback owner submits the consolidated list"}
          {session.feedback_owner ? ` · feedback owner: ${session.feedback_owner}` : ""}
        </p>
        {session.share_permission !== "comment" && (
          <p className="public-review-note">
            {canDownload ? "You can comment and download." : "View only — comments are disabled on this link."}
          </p>
        )}
      </div>

      {session.rounds_open === false && (
        <div className="public-review-closed">This revision round is closed — new notes will be accepted once the engineer uploads the next version.</div>
      )}

      {(() => {
        const briefBits: Array<[string, string]> = [];
        if (session.service_type) briefBits.push(["Service", SERVICE_LABELS[session.service_type] ?? session.service_type]);
        if (session.genre) briefBits.push(["Genre", session.genre]);
        if (session.goal) briefBits.push(["Goal", session.goal]);
        if (session.deadline_at) briefBits.push(["Deadline", new Date(session.deadline_at).toLocaleDateString()]);
        if (session.required_deliverables) briefBits.push(["Deliverables", session.required_deliverables]);
        const refs = (session.reference_links ?? "").split(/\n+/).map((s) => s.trim()).filter(Boolean);
        if (briefBits.length === 0 && refs.length === 0 && !session.do_not_change) return null;
        return (
          <div className="public-brief">
            <div className="public-brief-head">📋 The brief — what was agreed</div>
            <div className="public-brief-grid">
              {briefBits.map(([k, v]) => (
                <div key={k} className="public-brief-chip">
                  <span className="public-brief-key">{k}</span>
                  <span className="public-brief-val">{v}</span>
                </div>
              ))}
            </div>
            {refs.length > 0 && (
              <div className="public-brief-row">
                <span className="public-brief-key">References</span>
                <span>
                  {refs.map((r) => (
                    <a key={r} href={r} target="_blank" rel="noreferrer" className="public-brief-link">
                      {r.replace(/^https?:\/\//, "")} ↗
                    </a>
                  ))}
                </span>
              </div>
            )}
            {session.do_not_change && (
              <div className="public-brief-dnc">🚫 Will not change: {session.do_not_change}</div>
            )}
          </div>
        );
      })()}

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
            {current.watermarked && (
              <div className="public-review-note wm">
                🔊 This preview carries an audible watermark — the clean files arrive after the final delivery.
              </div>
            )}
          </div>

          {refCompare && (
            <ReferenceCompare
              comparison={refCompare.comp}
              reference={refCompare.ref}
              onClose={() => setRefCompare(null)}
            />
          )}
          {refErr && <div className="error">{refErr}</div>}

          {refs && refs.length > 0 && (
            <div className="public-refs">
              <div className="public-refs-head">
                🎯 References — the engineer's orientation tracks
                <span className="public-refs-note">A/B your mix against these</span>
              </div>
              {refs.map((r) => (
                <div key={r.id} className="public-ref">
                  <div className="public-ref-info">
                    <div className="public-ref-title">
                      {r.title}
                      {r.artist && <span className="rs-ref-artist"> · {r.artist}</span>}
                    </div>
                    <div className="public-ref-meta">
                      <span className="rs-ref-purpose">{r.purpose}</span>
                      {r.integrated_lufs != null && <span>{r.integrated_lufs} LUFS</span>}
                      {r.true_peak_dbtp != null && <span>{r.true_peak_dbtp} dBTP</span>}
                      {r.sample_rate ? <span>{(r.sample_rate / 1000).toFixed(1)} kHz</span> : null}
                    </div>
                    {r.note && <div className="public-ref-note">“{r.note}”</div>}
                    {r.source_type === "external_url" && r.external_url && (
                      <a href={r.external_url} target="_blank" rel="noreferrer" className="rs-ref-link">
                        Open reference ↗
                      </a>
                    )}
                  </div>
                  <div className="public-ref-actions">
                    {r.source_type === "private_upload" && (
                      <audio
                        controls
                        preload="none"
                        src={api.audioUrl(api.publicReferenceAudioUrl(token ?? "", r.id))}
                        className="public-ref-audio"
                      />
                    )}
                    {r.source_type === "private_upload" && r.analysis_status === "done" && current && (
                      <button
                        type="button"
                        className="rs-btn approve sm"
                        disabled={refBusy === r.id}
                        onClick={() => void compareReference(r)}
                      >
                        {refBusy === r.id ? "…" : `A/B with ${current.label}`}
                      </button>
                    )}
                  </div>
                </div>
              ))}
              <p className="ref-disclaimer">
                Reference audio is private to this review session and is never delivered, redistributed, or included in
                release exports.
              </p>
            </div>
          )}

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
                      {c.status !== "open" && <span className={`rs-req-status st-${c.status}`}>{c.status}</span>}
                    </div>
                    <p>{c.body}</p>
                    <div className="rs-comment-actions">
                      {c.status === "draft" && <span className="rs-req-draft">draft note — submitted when the feedback owner closes the round</span>}
                    </div>
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
                  {isFeedbackOwner && allDrafts.length > 0 && (
                    <div className="public-review-submit">
                      <div className="public-review-form-head">You are the feedback owner</div>
                      <div className="rs-round-drafts-head">
                        {allDrafts.length} draft note{allDrafts.length === 1 ? "" : "s"} ready to consolidate
                      </div>
                      <textarea
                        value={submitNote}
                        onChange={(e) => setSubmitNote(e.target.value)}
                        placeholder="Note to the engineer (optional)"
                        className="rs-approval-note-input"
                        rows={2}
                      />
                      <button type="button" className="rs-btn approve" onClick={submitFeedback}>
                        Submit revision notes → Round {(session.round_number ?? 1) + 1}
                      </button>
                      {needPay && (
                        <div className="rs-pay-prompt">
                          <span>This round is beyond the included revision budget</span>
                          <button type="button" className="rs-btn approve sm" onClick={() => void payExtraRound()} disabled={paying}>
                            {paying ? "Opening checkout…" : "💳 Pay for extra round"}
                          </button>
                        </div>
                      )}
                      {submitMsg && <div className={submitMsg.includes("✓") ? "success" : "error"}>{submitMsg}</div>}
                    </div>
                  )}
                  {session.feedback_owner && !isFeedbackOwner && allDrafts.length > 0 && (
                    <div className="public-review-note">
                      {allDrafts.length} draft note{allDrafts.length === 1 ? "" : "s"} — {session.feedback_owner} will consolidate them into one list.
                    </div>
                  )}
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
