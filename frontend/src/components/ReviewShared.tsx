import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api";
import { shortDate, APPROVAL_SCOPES, type ReviewApproval, type ReviewComment, type ReviewVersion } from "../types";

export const fmtClock = (s: number) => {
  const m = Math.floor(s / 60);
  const sec = Math.floor(s % 60);
  return `${m}:${String(sec).padStart(2, "0")}`;
};

/* ---------- interactive waveform canvas ---------- */

export function WaveformCanvas({
  peaks,
  duration,
  position,
  playing,
  comments,
  loop,
  mode,
  onAddComment,
  onLoop,
  highlightComment,
}: {
  peaks: number[];
  duration: number;
  position: number;
  playing: boolean;
  comments: ReviewComment[];
  loop: { start: number; end: number } | null;
  mode: "comment" | "seek";
  onAddComment: (t: number) => void;
  onLoop: (start: number, end: number) => void;
  highlightComment: number | null;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const wrapRef = useRef<HTMLDivElement>(null);
  const dragStartRef = useRef<number | null>(null);

  const toTime = useCallback(
    (clientX: number) => {
      const rect = canvasRef.current?.getBoundingClientRect();
      if (!rect || duration <= 0) return 0;
      return Math.max(0, Math.min(duration, ((clientX - rect.left) / rect.width) * duration));
    },
    [duration]
  );

  useEffect(() => {
    const canvas = canvasRef.current;
    const wrap = wrapRef.current;
    if (!canvas || !wrap) return;
    const dpr = window.devicePixelRatio || 1;
    const w = wrap.clientWidth;
    const h = wrap.clientHeight;
    canvas.width = w * dpr;
    canvas.height = h * dpr;
    canvas.style.width = `${w}px`;
    canvas.style.height = `${h}px`;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);

    const n = peaks.length || 96;
    const bw = w / n;
    const mid = h / 2;
    const dur = Math.max(1, duration);

    if (loop) {
      const lx = (loop.start / dur) * w;
      const rx = (loop.end / dur) * w;
      ctx.fillStyle = "rgba(255, 94, 26, 0.12)";
      ctx.fillRect(lx, 0, rx - lx, h);
      ctx.fillStyle = "rgba(255, 94, 26, 0.7)";
      ctx.fillRect(lx, h - 3, Math.max(1, rx - lx), 3);
    }

    for (let i = 0; i < n; i++) {
      const x = i * bw;
      const val = peaks[i] ?? 0;
      const bh = Math.max(2, val * (h - 6));
      const played = i / n <= position / dur;
      ctx.fillStyle = played ? "#ff5e1a" : "#9a958c";
      ctx.fillRect(x + 0.5, mid - bh / 2, Math.max(1, bw - 1), bh);
    }

    comments.forEach((c) => {
      const x = (c.time_s / dur) * w;
      const isHi = c.id === highlightComment;
      ctx.beginPath();
      ctx.arc(x, 8, isHi ? 7 : 5, 0, Math.PI * 2);
      ctx.fillStyle = c.resolved ? "#9a958c" : "#e0533d";
      ctx.fill();
      if (isHi) {
        ctx.strokeStyle = "#ff5e1a";
        ctx.lineWidth = 2;
        ctx.stroke();
      }
    });

    const px = (position / dur) * w;
    ctx.fillStyle = "#ff5e1a";
    ctx.fillRect(px - 1, 0, 2, h);
  }, [peaks, duration, position, playing, comments, loop, highlightComment]);

  const onPointerDown = (e: React.PointerEvent) => {
    const t = toTime(e.clientX);
    if (mode === "comment") {
      onAddComment(t);
      return;
    }
    dragStartRef.current = t;
    const move = (ev: PointerEvent) => {
      if (dragStartRef.current == null) return;
      const tt = toTime(ev.clientX);
      const s = Math.min(dragStartRef.current, tt);
      const en = Math.max(dragStartRef.current, tt);
      onLoop(s, en);
    };
    const up = () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
      dragStartRef.current = null;
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  };

  return (
    <div
      ref={wrapRef}
      className="rs-canvas-wrap"
      onPointerDown={onPointerDown}
      title={mode === "comment" ? "Click to add a comment at this point" : "Click to seek · drag to select a loop region"}
    >
      <canvas ref={canvasRef} className="rs-canvas" />
      {mode === "comment" && <div className="rs-canvas-hint">✎ click the waveform to comment at that point</div>}
    </div>
  );
}

/* ---------- comment composer ---------- */

export function CommentComposer({
  timeS,
  showName,
  placeholder,
  autoFocus,
  onCancel,
  onSubmit,
}: {
  timeS: number;
  showName?: boolean;
  placeholder: string;
  autoFocus?: boolean;
  onCancel?: () => void;
  onSubmit: (timeS: number, body: string, authorName: string) => Promise<unknown>;
}) {
  const [body, setBody] = useState("");
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!body.trim()) return;
    setBusy(true);
    setErr(null);
    try {
      await onSubmit(timeS, body.trim(), name.trim());
      setBody("");
      onCancel?.();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed to post");
    } finally {
      setBusy(false);
    }
  };

  return (
    <form className="rs-comment-form" onSubmit={submit}>
      <div className="rs-comment-form-row">
        <span className="rs-comment-at">@{fmtClock(timeS)}</span>
        {showName && (
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Your name"
            className="rs-comment-input thin"
          />
        )}
        <input
          type="text"
          value={body}
          onChange={(e) => setBody(e.target.value)}
          placeholder={placeholder}
          autoFocus={autoFocus}
          className="rs-comment-input"
        />
        <button type="submit" className="rs-btn approve sm" disabled={busy}>
          {busy ? "…" : "Post"}
        </button>
        {onCancel && (
          <button type="button" className="rs-btn ghost sm" onClick={onCancel}>
            ✕
          </button>
        )}
      </div>
      {err && <div className="error">{err}</div>}
    </form>
  );
}

/* ---------- approval panel (owner + guest) ---------- */

export function ApprovalPanel({
  sessionId,
  token,
  version,
  approvals,
  onDone,
}: {
  sessionId?: number;
  token?: string;
  version: ReviewVersion;
  approvals: ReviewApproval[];
  onDone: () => Promise<void>;
}) {
  const [scope, setScope] = useState<string>("mix");
  const [decision, setDecision] = useState<"approved" | "needs_changes">("approved");
  const [note, setNote] = useState("");
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (decision === "needs_changes" && !note.trim()) {
      setErr("A 'needs changes' decision requires a note — tell them what to fix.");
      return;
    }
    const approver = name.trim() || (token ? "Reviewer" : "me");
    setBusy(true);
    setErr(null);
    try {
      if (token && sessionId == null) {
        await api.publicAddApproval(token, version.id, scope, decision === "approved", note.trim(), approver);
      } else if (sessionId != null) {
        await api.addApproval(sessionId, version.id, scope, decision === "approved", note.trim(), approver);
      }
      setNote("");
      await onDone();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed to submit approval");
    } finally {
      setBusy(false);
    }
  };

  const latest = approvals[0];

  return (
    <div className="rs-approvals">
      <div className="rs-versions-head">Approval</div>
      {latest && (
        <div className={`rs-approval-latest ${latest.approved ? "ok" : "changes"}`}>
          <div className="rs-approval-title">
            {latest.approved ? "✓ APPROVED" : "△ NEEDS CHANGES"} · {latest.scope}
          </div>
          <div className="rs-approval-meta">
            {latest.approver_name} · {shortDate(latest.created_at)}
          </div>
          {latest.note && <p className="rs-approval-note">“{latest.note}”</p>}
        </div>
      )}
      <form className="rs-approval-form" onSubmit={submit}>
        <div className="rs-approval-row">
          <select value={scope} onChange={(e) => setScope(e.target.value)} className="rs-select">
            {APPROVAL_SCOPES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
          <div className="rs-seg">
            <button
              type="button"
              className={`rs-seg-btn ${decision === "approved" ? "active ok" : ""}`}
              onClick={() => setDecision("approved")}
            >
              Approve
            </button>
            <button
              type="button"
              className={`rs-seg-btn ${decision === "needs_changes" ? "active changes" : ""}`}
              onClick={() => setDecision("needs_changes")}
            >
              Changes
            </button>
          </div>
        </div>
        {token && (
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Your name / email"
            className="rs-comment-input"
          />
        )}
        <textarea
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder={decision === "needs_changes" ? "What needs to change? (required)" : "Optional note"}
          className="rs-approval-note-input"
          rows={2}
        />
        <button type="submit" className="rs-btn approve" disabled={busy}>
          {busy ? "…" : decision === "approved" ? `Approve ${version.label} · ${scope}` : `Request changes · ${scope}`}
        </button>
        {err && <div className="error">{err}</div>}
      </form>
    </div>
  );
}
