import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../api";
import ReferenceCompare from "../components/ReferenceCompare";
import { fmtClock, WaveformCanvas, ApprovalPanel } from "../components/ReviewShared";
import ABCompare from "../components/ABCompare";
import VoiceRecorder from "../components/VoiceRecorder";
import {
  fmtTime,
  humanSize,
  CHANGE_ORDER_REASONS,
  type ChangeOrder,
  type ReferenceComparison,
  type ReferenceTrack,
  type ReviewSession,
  type ReviewVersion,
  type VersionComparison,
} from "../types";

const FEEDBACK_TEMPLATES = [
  { id: "too_loud", label: "🔊 Something is too loud / quiet", text: "Something is too loud / quiet" },
  { id: "masked", label: "🌫 Something is unclear or masked", text: "Something is unclear or masked" },
  { id: "energy", label: "⚡ The energy changes here", text: "The energy changes here" },
  { id: "reference", label: "🎯 This differs from the reference", text: "This differs from the reference" },
  { id: "technical", label: "🔧 Technical issue / click / edit", text: "Technical issue / click / edit" },
  { id: "keep", label: "❤️ I like this — keep it", text: "I like this — keep it" },
];

const ELEMENTS = ["Vocal", "Bass", "Drums", "Synths", "Other"];
const DIRECTIONS = ["louder", "quieter", "brighter", "darker", "wider", "tighter"];

const REASON_LABELS: Record<string, string> = {
  mix_revision: "Mix revision",
  new_stem_request: "New stem request",
  format_change: "Format change",
  mastering_recall: "Mastering recall",
};

const DECISION_LABELS: Record<string, string> = {
  courtesy: "Included courtesy change",
  paid_round: "Paid revision round",
  new_mastering_pass: "New mastering pass",
};

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
  const [changeOrders, setChangeOrders] = useState<ChangeOrder[]>([]);
  const [changeReason, setChangeReason] = useState("mix_revision");
  const [changeDesc, setChangeDesc] = useState("");
  const [changeMsg, setChangeMsg] = useState<string | null>(null);
  const [showChangeForm, setShowChangeForm] = useState(false);
  const [coBusy, setCoBusy] = useState(false);
  // structured feedback + voice notes
  const [fbTemplate, setFbTemplate] = useState<string | null>(null);
  const [fbElement, setFbElement] = useState("Vocal");
  const [fbDirection, setFbDirection] = useState("louder");
  const [fbNote, setFbNote] = useState("");
  const [voiceBlob, setVoiceBlob] = useState<{ blob: Blob; dur: number } | null>(null);
  const [fbMsg, setFbMsg] = useState<string | null>(null);
  // public version A/B
  const [compareBaseId, setCompareBaseId] = useState<number | null>(null);
  const [publicComp, setPublicComp] = useState<VersionComparison | null>(null);
  const [compareErr, setCompareErr] = useState<string | null>(null);
  const [compareBusy, setCompareBusy] = useState(false);

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
        if (s.status === "approved") {
          api
            .publicChangeOrders(token)
            .then(setChangeOrders)
            .catch(() => setChangeOrders([]));
        }
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

  const addVoiceNote = async (blob: Blob, dur: number) => {
    setVoiceBlob({ blob, dur });
    setFbMsg(null);
  };

  const submitFeedbackNote = async () => {
    if (!token || !current) return;
    const t = pendingComment ?? position;
    let body = "";
    if (fbTemplate) {
      const tpl = FEEDBACK_TEMPLATES.find((x) => x.id === fbTemplate);
      body = `${tpl?.text ?? fbTemplate} · Element: ${fbElement} · Direction: ${fbDirection}`;
    }
    if (fbNote.trim()) body = body ? `${body}\n${fbNote.trim()}` : fbNote.trim();
    if (!body && !voiceBlob) {
      setFbMsg("Pick a template or write what you hear — then add the note.");
      return;
    }
    try {
      const c = voiceBlob
        ? await api.publicAddVoiceComment(token, current.id, t, body, name || "Reviewer", voiceBlob.blob, voiceBlob.dur)
        : await api.publicAddComment(token, current.id, t, body, name || "Reviewer");
      setSession((s) =>
        s
          ? {
              ...s,
              versions: (s.versions ?? []).map((v) => (v.id === current.id ? { ...v, comments: [...v.comments, c] } : v)),
            }
          : s
      );
      setFbTemplate(null);
      setFbNote("");
      setVoiceBlob(null);
      setPendingComment(null);
      setFbMsg("✓ Note added to your draft notes.");
    } catch (e) {
      setFbMsg(e instanceof Error ? e.message : "Failed to add the note");
    }
  };

  const runPublicCompare = async () => {
    if (!token || !current || !compareBaseId) return;
    setCompareBusy(true);
    setCompareErr(null);
    try {
      const comp = await api.publicCompareVersions(token, {
        baseVersionId: compareBaseId,
        compareVersionId: current.id,
        startMs: 0,
        endMs: null,
      });
      setPublicComp(comp);
    } catch (e) {
      setCompareErr(e instanceof Error ? e.message : "Compare failed");
    } finally {
      setCompareBusy(false);
    }
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
  const versionList = session.versions ?? []; // newest first

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
        <details className="public-details">
          <summary>Details</summary>
          <ul className="public-details-list">
            <li>Round {session.round_number ?? 1}{session.rounds_open === false ? " · closed (reopens with the next version)" : ""}</li>
            {session.feedback_due_at && <li>Feedback due {new Date(session.feedback_due_at).toLocaleDateString()}</li>}
            {session.feedback_owner && <li>Feedback owner: {session.feedback_owner}</li>}
            <li>Share permission: {session.share_permission}</li>
            <li>Watermarked previews: {session.watermark_enabled ? "on (unapproved versions)" : "off"}</li>
            <li>Included revision rounds: {session.included_rounds ?? 1}{session.change_rounds_granted ? ` + ${session.change_rounds_granted} granted by change orders` : ""}</li>
            {session.retention_until && <li>Archive retained until {new Date(session.retention_until).toLocaleDateString()}</li>}
          </ul>
        </details>
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

            </div>

            {current.waveform_synthetic && <div className="public-review-note">Waveform is illustrative — this file isn't a WAV.</div>}
            {current.watermarked && (
              <div className="public-review-note wm">
                🔊 This preview carries an audible watermark — the clean files arrive after the final delivery.
              </div>
            )}
          </div>

          {versionList.length > 1 && (
            <div className="public-compare">
              <div className="public-compare-head">↔ Compare versions</div>
              <div className="rs-share-row">
                <label>
                  Version A (base)
                  <select
                    value={compareBaseId ?? versionList[versionList.length - 1]?.id ?? ""}
                    onChange={(e) => {
                      setCompareBaseId(Number(e.target.value));
                      setPublicComp(null);
                    }}
                    className="rs-select"
                  >
                    {versionList.filter((v) => v.id !== current.id).map((v) => (
                      <option key={v.id} value={v.id}>{v.label}</option>
                    ))}
                  </select>
                </label>
                <button type="button" className="rs-btn approve sm" onClick={() => void runPublicCompare()} disabled={compareBusy}>
                  {compareBusy ? "…" : `Compare ${current.label} ↔ base`}
                </button>
              </div>
              <p className="rs-brief-hint">
                Same playhead, loop region, loudness matched in the preview — so you compare quality, not volume.
              </p>
              {compareErr && <div className="error">{compareErr}</div>}
              {publicComp && (
                <ABCompare
                  sessionId={0}
                  comparison={publicComp}
                  onClose={() => setPublicComp(null)}
                  audioUrls={{
                    base: api.audioUrl(api.publicAudioUrl(token ?? "", publicComp.base_version_id)),
                    compare: api.audioUrl(api.publicAudioUrl(token ?? "", publicComp.compare_version_id)),
                  }}
                />
              )}
            </div>
          )}

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
                    {c.voice_format && (
                      <audio controls preload="none" src={api.publicVoiceAudioUrl(token!, current.id, c.id)} className="rs-voice" style={{ width: "100%", marginTop: 6 }} />
                    )}
                    <div className="rs-comment-actions">
                      {c.status === "draft" && <span className="rs-req-draft">draft note — submitted when the feedback owner closes the round</span>}
                    </div>
                  </div>
                </div>
              ))}

              {(session.share_permission === "comment" || canDownload) && (
                <div className="public-review-form">
                  <div className="public-review-form-head">
                    Leave feedback
                    <span className="rs-count">
                      your draft notes: {allDrafts.length}
                    </span>
                  </div>
                  <input
                    type="text"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="Your name (optional)"
                    className="rs-comment-input"
                    style={{ marginBottom: 8 }}
                  />
                  <p className="rs-brief-hint">
                    {pendingComment != null
                      ? `📌 Note lands at ${fmtTime(pendingComment)} — click the waveform to move it.`
                      : "Tap a spot on the waveform to pin the moment, or use the playhead position."}
                  </p>
                  <div className="fb-templates">
                    {FEEDBACK_TEMPLATES.map((t) => (
                      <button
                        key={t.id}
                        type="button"
                        className={`fb-tpl ${fbTemplate === t.id ? "active" : ""}`}
                        onClick={() => setFbTemplate(fbTemplate === t.id ? null : t.id)}
                      >
                        {t.label}
                      </button>
                    ))}
                  </div>
                  {fbTemplate && (
                    <div className="fb-structured">
                      <div className="rs-share-row">
                        <label>
                          Element
                          <select value={fbElement} onChange={(e) => setFbElement(e.target.value)} className="rs-select">
                            {ELEMENTS.map((el) => (
                              <option key={el} value={el}>{el}</option>
                            ))}
                          </select>
                        </label>
                        <label>
                          Direction
                          <select value={fbDirection} onChange={(e) => setFbDirection(e.target.value)} className="rs-select">
                            {DIRECTIONS.map((d) => (
                              <option key={d} value={d}>{d}</option>
                            ))}
                          </select>
                        </label>
                      </div>
                      <p className="rs-brief-hint">
                        {fmtTime(pendingComment ?? position)} — what should change?
                      </p>
                    </div>
                  )}
                  <textarea
                    value={fbNote}
                    onChange={(e) => setFbNote(e.target.value)}
                    rows={2}
                    placeholder="Add detail in your own words (optional) — e.g. “at 01:24 the kick and bass clash”"
                    className="rs-comment-input"
                  />
                  <div className="rs-share-row" style={{ justifyContent: "space-between" }}>
                    <VoiceRecorder onRecorded={(blob, dur) => void addVoiceNote(blob, dur)} onCancel={() => setVoiceBlob(null)} />
                    <button type="button" className="rs-btn approve sm" onClick={() => void submitFeedbackNote()} disabled={compareBusy}>
                      {voiceBlob ? "🎙 Add voice note" : "Add note"}
                    </button>
                  </div>
                  {voiceBlob && (
                    <div className="success" style={{ marginTop: 6 }}>
                      🎙 Voice note ready ({voiceBlob.dur}s) — press “Add voice note” to attach it.
                    </div>
                  )}
                  {fbMsg && <div className={fbMsg.includes("✓") ? "success" : "error"} style={{ marginTop: 6 }}>{fbMsg}</div>}
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

          {session.status === "approved" && (
            <div className="public-change">
              <div className="public-change-head">🔁 Request a change after approval</div>
              <p className="public-review-note">
                The project is approved and delivered. Want something different now? Request a change — the
                engineer quotes it (included courtesy change, paid revision round or a new mastering pass) or
                declines, you accept the price + deadline, and the revision round reopens.
              </p>
              {changeOrders.length > 0 && (
                <div className="public-change-list">
                  {changeOrders.map((co) => (
                    <div key={co.id} className={`rs-co ${co.status}`}>
                      <div className="rs-co-head">
                        <span className="rs-co-reason">{REASON_LABELS[co.reason] ?? co.reason}</span>
                        <span className={`rs-round-stat ${co.status === "declined" ? "closed" : "open"}`}>{co.status}</span>
                        {co.round_granted && <span className="rs-round-stat open">✓ round reopened</span>}
                      </div>
                      <p className="rs-co-desc">“{co.description || "No details"}”</p>
                      <div className="rs-co-meta">
                        {co.decision && <span>{co.decision.replace(/_/g, " ")}</span>}
                        {co.price_cents != null && (
                          <span>
                            {new Intl.NumberFormat("en-US", { style: "currency", currency: co.currency.toUpperCase() }).format(co.price_cents / 100)}
                          </span>
                        )}
                        {co.deadline_at && <span>by {new Date(co.deadline_at).toLocaleDateString()}</span>}
                        {co.target_round && <span>reopens Round {co.target_round}</span>}
                      </div>
                      {co.status === "quoted" && (
                        <div className="rs-co-actions">
                          <div className="rs-co-summary">
                            <strong>{DECISION_LABELS[co.decision ?? ""] ?? (co.decision ?? "").replace(/_/g, " ")}</strong>
                            {co.price_cents != null && (
                              <span>
                                {co.price_cents === 0 ? "· free (courtesy)" : ` · ${new Intl.NumberFormat("en-US", { style: "currency", currency: co.currency.toUpperCase() }).format(co.price_cents / 100)}`}
                              </span>
                            )}
                            {co.deadline_at && <span>· delivery by {new Date(co.deadline_at).toLocaleDateString()}</span>}
                            {session.retention_until && <span>· archive retained until {new Date(session.retention_until).toLocaleDateString()}</span>}
                            {co.quote_expires_at && <span>· quote expires {new Date(co.quote_expires_at).toLocaleDateString()}</span>}
                          </div>
                          <button
                            type="button"
                            className="rs-btn approve sm"
                            disabled={coBusy}
                            onClick={() =>
                              void (async () => {
                                setCoBusy(true);
                                setChangeMsg(null);
                                try {
                                  await api.acceptChangeOrder(token!, co.id, name || "Client");
                                  setChangeMsg("✓ Quote accepted — the engineer will reopen the round after payment.");
                                  setChangeOrders(await api.publicChangeOrders(token!));
                                } catch (e2) {
                                  setChangeMsg(e2 instanceof Error ? e2.message : "Accept failed");
                                } finally {
                                  setCoBusy(false);
                                }
                              })()
                            }
                          >
                            Accept quote
                          </button>
                        </div>
                      )}
                      {co.status === "expired" && (
                        <div className="rs-co-actions">
                          <span className="rs-round-stat closed">This quote expired — ask the engineer to re-quote</span>
                        </div>
                      )}
                      {co.status === "accepted" && !co.round_granted && (co.price_cents ?? 0) > 0 && (
                        <div className="rs-co-actions">
                          <span className="rs-round-stat open">Quote accepted — pay to reopen the round</span>
                          <button
                            type="button"
                            className="rs-btn approve sm"
                            disabled={coBusy}
                            onClick={() =>
                              void (async () => {
                                setCoBusy(true);
                                setChangeMsg(null);
                                try {
                                  const c = await api.publicChangeOrderCheckout(token!, co.id);
                                  window.location.href = c.checkout_url;
                                } catch (e2) {
                                  setChangeMsg(e2 instanceof Error ? e2.message : "Checkout failed");
                                  setCoBusy(false);
                                }
                              })()
                            }
                          >
                            💳 Pay {new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format((co.price_cents ?? 0) / 100)}
                          </button>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
              {!showChangeForm ? (
                <button type="button" className="rs-btn ghost" onClick={() => setShowChangeForm(true)} disabled={changeOrders.some((c) => ["requested", "quoted", "accepted"].includes(c.status))}>
                  {changeOrders.some((c) => ["requested", "quoted", "accepted"].includes(c.status)) ? "Change request pending…" : "Request a change"}
                </button>
              ) : (
                <div className="public-change-form">
                  <div className="rs-share-row">
                    <label>
                      What changed?
                      <select value={changeReason} onChange={(e) => setChangeReason(e.target.value)} className="rs-select">
                        {CHANGE_ORDER_REASONS.map((r) => (
                          <option key={r} value={r}>{REASON_LABELS[r]}</option>
                        ))}
                      </select>
                    </label>
                    <label>
                      Your name / email
                      <input type="text" value={name} onChange={(e) => setName(e.target.value)} placeholder="optional" className="rs-input" />
                    </label>
                  </div>
                  <textarea
                    value={changeDesc}
                    onChange={(e) => setChangeDesc(e.target.value)}
                    rows={2}
                    placeholder="e.g. We need a new mix — the vocal sits too far back now…"
                    className="rs-approval-note-input"
                  />
                  <div className="rs-share-row">
                    <button
                      type="button"
                      className="rs-btn approve sm"
                      disabled={coBusy || !changeDesc.trim()}
                      onClick={() =>
                        void (async () => {
                          setCoBusy(true);
                          setChangeMsg(null);
                          try {
                            const co = await api.createChangeOrder(token!, changeReason, changeDesc.trim(), name || "Client");
                            setChangeDesc("");
                            setShowChangeForm(false);
                            setChangeMsg(`✓ Change request sent — the engineer will quote it shortly (Round ${co.target_round}).`);
                            setChangeOrders(await api.publicChangeOrders(token!));
                          } catch (e2) {
                            setChangeMsg(e2 instanceof Error ? e2.message : "Request failed");
                          } finally {
                            setCoBusy(false);
                          }
                        })()
                      }
                    >
                      Send change request
                    </button>
                    <button type="button" className="rs-btn ghost sm" onClick={() => setShowChangeForm(false)}>
                      Cancel
                    </button>
                  </div>
                </div>
              )}
              {changeMsg && <div className={changeMsg.includes("✓") ? "success" : "error"} style={{ marginTop: 8 }}>{changeMsg}</div>}
            </div>
          )}
        </>
      ) : (
        <div className="card muted">No versions shared yet.</div>
      )}
    </div>
  );
}
