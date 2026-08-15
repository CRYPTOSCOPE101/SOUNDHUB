import { useMemo, useState } from "react";

type Comment = {
  id: number;
  time: string;
  author: string;
  role: string;
  text: string;
  resolved: boolean;
  status: string; // request lifecycle: Open / Fixed in v13 / Verified…
};

type Status = "in_review" | "needs_changes" | "approved";

const VERSIONS = [
  { id: "v13", label: "Bass revised", note: "2 comments resolved" },
  { id: "v12", label: "Initial review", note: "opened by Aisha" },
  { id: "v11", label: "Arrangement draft", note: "pre-feedback" },
];

const INITIAL_COMMENTS: Comment[] = [
  {
    id: 1,
    time: "01:24",
    author: "Aisha",
    role: "A&R",
    text: "Kick and bass clash here. Keep the energy, but let the vocal breathe.",
    resolved: false,
    status: "open",
  },
  {
    id: 2,
    time: "02:47",
    author: "Marcus",
    role: "Mix engineer",
    text: "Hats sit nicely after the drop — no change needed here.",
    resolved: true,
    status: "fixed",
  },
  {
    id: 3,
    time: "03:05",
    author: "Aisha",
    role: "A&R",
    text: "Outro needs air after the last drop.",
    resolved: false,
    status: "open",
  },
  {
    id: 4,
    time: "00:48",
    author: "Kai",
    role: "Artist",
    text: "Bass patch sounds right now — verified against the reference.",
    resolved: true,
    status: "verified",
  },
];

// deterministic waveform (same on every render)
function useWaveform(bars: number, seed = 7) {
  return useMemo(() => {
    const heights: number[] = [];
    let s = seed;
    const rnd = () => {
      s = (s * 1103515245 + 12345) % 2147483648;
      return s / 2147483648;
    };
    for (let i = 0; i < bars; i++) {
      heights.push(0.15 + rnd() * 0.85);
    }
    return heights;
  }, [bars, seed]);
}

export default function ReviewSession({ compact = false }: { compact?: boolean }) {
  const [status, setStatus] = useState<Status>("in_review");
  const [version, setVersion] = useState("v13");
  const [comments, setComments] = useState<Comment[]>(INITIAL_COMMENTS);
  const [playing, setPlaying] = useState(false);
  const wave = useWaveform(compact ? 48 : 72);

  const toggleResolved = (id: number) =>
    setComments((cs) => cs.map((c) => (c.id === id ? { ...c, resolved: !c.resolved } : c)));

  const statusChip = {
    in_review: { text: `${version} · Ready for approval`, cls: "status-review" },
    needs_changes: { text: `${version} · Needs changes`, cls: "status-changes" },
    approved: { text: `${version} · Approved ✓`, cls: "status-approved" },
  }[status];

  const timeToPct = (time: string) => {
    const [m, s] = time.split(":").map(Number);
    return ((m * 60 + s) / 200) * 100; // ~3:20 track
  };

  return (
    <div className={`rs ${compact ? "rs-compact" : ""}`}>
      {/* header */}
      <div className="rs-head">
        <div className="rs-title">
          <span className="rs-title-icon">🎧</span>
          <div>
            <div className="rs-name">Neon Warehouse</div>
            <div className="rs-sub">track_v13.wav · 3:20 · stems: drums, bass, vocal, synths</div>
          </div>
        </div>
        <div className={`rs-status ${statusChip.cls}`}>{statusChip.text}</div>
      </div>

      {/* revision round bar — the moat, not just comments */}
      <div className="rs-round-bar">
        <span className="rs-round-chip">Round 2</span>
        <span className="rs-round-stat">3 open requests</span>
        <span className="rs-round-stat">8 resolved</span>
        <span className="rs-round-stat muted">feedback closes Aug 18</span>
      </div>

      {/* waveform */}
      <div className="rs-wave-wrap">
        <div className={`rs-playhead ${playing ? "run" : ""}`} />
        <div className="rs-wave">
          {wave.map((h, i) => (
            <span key={i} style={{ height: `${h * 100}%` }} className={i % 5 === 0 ? "bar-accent" : ""} />
          ))}
        </div>
        <button
          type="button"
          className="rs-play"
          onClick={() => setPlaying((p) => !p)}
          title={playing ? "Pause" : "Play"}
        >
          {playing ? "❚❚" : "▶"}
        </button>
        {/* comment pins */}
        {comments
          .filter((c) => !c.resolved)
          .map((c) => (
            <span key={c.id} className="rs-pin" style={{ left: `${timeToPct(c.time)}%` }} title={`${c.time} · ${c.author}`}>
              ●
            </span>
          ))}
        <span className="rs-time">0:00</span>
        <span className="rs-time right">3:20</span>
      </div>

      {/* body */}
      <div className="rs-body">
        {/* comments */}
        <div className="rs-comments">
          <div className="rs-comments-head">
            <span>Requests</span>
            <span className="rs-count">
              {comments.filter((c) => c.status === "open").length} open ·{" "}
              {comments.filter((c) => c.status === "fixed").length} fixed in v13 ·{" "}
              {comments.filter((c) => c.status === "verified").length} verified
            </span>
          </div>
          {comments.map((c) => (
            <div key={c.id} className={`rs-comment ${c.resolved ? "resolved" : ""}`}>
              <div className="rs-comment-time">{c.time}</div>
              <div className="rs-comment-body">
                <div className="rs-comment-author">
                  <span className="rs-avatar">{c.author[0]}</span>
                  <strong>{c.author}</strong> <em>{c.role}</em>
                  <span className={`rs-req-status st-${c.status}`}>
                    {c.status === "fixed" ? "fixed in v13" : c.status}
                  </span>
                </div>
                <p>{c.text}</p>
                <div className="rs-comment-actions">
                  <button type="button" className="rs-link">Reply</button>
                  <button type="button" className="rs-link" onClick={() => toggleResolved(c.id)}>
                    {c.resolved ? "Reopen" : "Mark resolved"}
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* versions */}
        <div className="rs-versions">
          <div className="rs-versions-head">Versions</div>
          {VERSIONS.map((v) => (
            <button
              key={v.id}
              type="button"
              className={`rs-version ${version === v.id ? "active" : ""}`}
              onClick={() => setVersion(v.id)}
            >
              <span className="rs-version-id">{v.id}</span>
              <span className="rs-version-info">
                <span className="rs-version-label">{v.label}</span>
                <span className="rs-version-note">{v.note}</span>
              </span>
            </button>
          ))}
          <div className="rs-approve">
            {status !== "approved" && (
              <>
                <button type="button" className="rs-btn ghost" onClick={() => setStatus("needs_changes")}>
                  Needs changes
                </button>
                <button type="button" className="rs-btn approve" onClick={() => setStatus("approved")}>
                  Approve {version}
                </button>
              </>
            )}
            {status === "approved" && <div className="rs-approved-note">✓ Approved — ready to master</div>}
          </div>
        </div>
      </div>
    </div>
  );
}
