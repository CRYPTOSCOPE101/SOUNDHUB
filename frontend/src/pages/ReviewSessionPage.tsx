import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { fmtTime, type ReviewSession, type ReviewVersion } from "../types";

function Waveform({ peaks, playing }: { peaks: number[]; playing: boolean }) {
  return (
    <div className="rs-wave">
      {peaks.map((h, i) => (
        <span
          key={i}
          style={{ height: `${Math.max(3, h * 100)}%` }}
          className={playing ? "bar-live" : ""}
        />
      ))}
    </div>
  );
}

function CommentForm({
  onAdd,
  placeholder,
  defaultTime = 0,
  timeEditable = true,
  autoFocus = false,
}: {
  onAdd: (timeS: number, body: string) => Promise<unknown> | void;
  placeholder: string;
  defaultTime?: number;
  timeEditable?: boolean;
  autoFocus?: boolean;
}) {
  const [body, setBody] = useState("");
  const [time, setTime] = useState(String(defaultTime));
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const t = Number(time) || 0;
    if (!body.trim()) return;
    setBusy(true);
    setErr(null);
    try {
      await onAdd(t, body.trim());
      setBody("");
      if (timeEditable) setTime("0");
    } catch (err) {
      setErr(err instanceof Error ? err.message : "Failed to add comment");
    } finally {
      setBusy(false);
    }
  };

  return (
    <form className="rs-comment-form" onSubmit={submit}>
      <div className="rs-comment-form-row">
        {timeEditable && (
          <input
            type="number"
            min={0}
            step={0.1}
            value={time}
            onChange={(e) => setTime(e.target.value)}
            className="rs-time-input"
            aria-label="Time in seconds"
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
          {busy ? "…" : "Comment"}
        </button>
      </div>
      {err && <div className="error">{err}</div>}
    </form>
  );
}

function SessionDetail({ session, onBack }: { session: ReviewSession; onBack: () => void }) {
  const [versions, setVersions] = useState<ReviewVersion[]>(session.versions ?? []);
  const [currentId, setCurrentId] = useState<number | null>(
    session.versions?.length ? session.versions[0].id : null
  );
  const [playing, setPlaying] = useState(false);
  const [copied, setCopied] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadMsg, setUploadMsg] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const audioRef = useRef<HTMLAudioElement>(null);

  const current = versions.find((v) => v.id === currentId) ?? versions[0] ?? null;

  const refresh = useCallback(async () => {
    const s = await api.getSession(session.id);
    setVersions(s.versions ?? []);
    setCurrentId((prev) => {
      if (prev && s.versions?.some((v) => v.id === prev)) return prev;
      return s.versions?.length ? s.versions[0].id : null;
    });
  }, [session.id]);

  const upload = async (file: File) => {
    setUploading(true);
    setUploadMsg("");
    setErr(null);
    try {
      await api.uploadVersion(session.id, file, `Uploaded ${file.name}`);
      setUploadMsg("Version uploaded ✓");
      await refresh();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  const copyLink = async () => {
    const url = `${window.location.origin}/r/${session.share_token}`;
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      setCopied(false);
    }
  };

  const setStatus = async (status: string) => {
    if (!current) return;
    await api.setVersionStatus(session.id, current.id, status);
    await refresh();
  };

  const toggleResolved = async (commentId: number, resolved: boolean) => {
    if (!current) return;
    await api.resolveComment(session.id, current.id, commentId, !resolved);
    await refresh();
  };

  useEffect(() => {
    if (!playing || !current) return;
    audioRef.current?.play().catch(() => setPlaying(false));
  }, [playing, current]);

  const resolvedCount = current?.comments.filter((c) => c.resolved).length ?? 0;
  const openCount = (current?.comments.length ?? 0) - resolvedCount;

  const statusChip =
    current?.status === "approved"
      ? { text: `${current.label} · Approved ✓`, cls: "status-approved" }
      : current?.status === "needs_changes"
        ? { text: `${current.label} · Needs changes`, cls: "status-changes" }
        : { text: `${current?.label ?? ""} · Ready for approval`, cls: "status-review" };

  return (
    <div className="rs rs-real">
      {/* header */}
      <div className="rs-head">
        <div className="rs-title">
          <span className="rs-title-icon">🎧</span>
          <div>
            <div className="rs-name">{session.name}</div>
            <div className="rs-sub">
              {versions.length} version{versions.length === 1 ? "" : "s"} · shared via private link
            </div>
          </div>
        </div>
        <div className={`rs-status ${statusChip.cls}`}>{statusChip.text}</div>
      </div>

      {/* waveform + audio */}
      {current && (
        <>
          <div className="rs-wave-wrap">
            <div className={`rs-playhead ${playing ? "run" : ""}`} style={{ animationDuration: `${Math.max(3, current.duration_s)}s` }} />
            <Waveform peaks={current.waveform} playing={playing} />
            <button
              type="button"
              className="rs-play"
              onClick={() => setPlaying((p) => !p)}
              title={playing ? "Pause" : "Play"}
            >
              {playing ? "❚❚" : "▶"}
            </button>
            {current.comments
              .filter((c) => !c.resolved)
              .map((c) => (
                <span
                  key={c.id}
                  className="rs-pin"
                  style={{ left: `${(c.time_s / Math.max(1, current.duration_s)) * 100}%` }}
                  title={`${fmtTime(c.time_s)} · ${c.author_name}`}
                >
                  ●
                </span>
              ))}
            <span className="rs-time">0:00</span>
            <span className="rs-time right">{fmtTime(current.duration_s)}</span>
          </div>

          <audio
            ref={audioRef}
            src={api.versionAudioUrl(session.id, current.id)}
            onEnded={() => setPlaying(false)}
            controls
            className="rs-audio"
          />

          <div className="rs-body">
            {/* comments */}
            <div className="rs-comments">
              <div className="rs-comments-head">
                <span>Comments</span>
                <span className="rs-count">
                  {resolvedCount} resolved · {openCount} open
                </span>
              </div>
              {current.comments.length === 0 && (
                <div className="rs-empty">No comments yet — share the link and ask for feedback.</div>
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
                    <div className="rs-comment-actions">
                      <button type="button" className="rs-link" onClick={() => toggleResolved(c.id, c.resolved)}>
                        {c.resolved ? "Reopen" : "Mark resolved"}
                      </button>
                    </div>
                  </div>
                </div>
              ))}
              <CommentForm
                onAdd={(t, body) => api.addComment(session.id, current.id, t, body)}
                placeholder="Comment on this version… (time in seconds)"
                defaultTime={0}
              />
            </div>

            {/* versions */}
            <div className="rs-versions">
              <div className="rs-versions-head">Versions</div>
              {versions.map((v) => (
                <button
                  key={v.id}
                  type="button"
                  className={`rs-version ${current.id === v.id ? "active" : ""}`}
                  onClick={() => {
                    setCurrentId(v.id);
                    setPlaying(false);
                  }}
                >
                  <span className="rs-version-id">{v.label}</span>
                  <span className="rs-version-info">
                    <span className="rs-version-label">{v.message || v.filename}</span>
                    <span className="rs-version-note">
                      {fmtTime(v.duration_s)} · {v.comments.filter((c) => c.resolved).length} resolved
                    </span>
                  </span>
                </button>
              ))}
              <label className="rs-upload">
                {uploading ? "Uploading…" : "⬆ Upload new version"}
                <input
                  type="file"
                  accept=".wav,.mp3,.flac,.ogg,.aif,.aiff,.m4a,audio/*"
                  hidden
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (f) void upload(f);
                    e.target.value = "";
                  }}
                />
              </label>
              {uploadMsg && <div className="success">{uploadMsg}</div>}
              {err && <div className="error">{err}</div>}

              <div className="rs-approve">
                {current.status !== "approved" ? (
                  <>
                    <button type="button" className="rs-btn ghost" onClick={() => setStatus("needs_changes")}>
                      Needs changes
                    </button>
                    <button type="button" className="rs-btn approve" onClick={() => setStatus("approved")}>
                      Approve {current.label}
                    </button>
                  </>
                ) : (
                  <div className="rs-approved-note">✓ Approved — ready to master</div>
                )}
              </div>

              <div className="rs-share">
                <code>soundhub.app/r/{session.share_token}</code>
                <button type="button" className="rs-btn ghost" onClick={copyLink}>
                  {copied ? "✓ Copied" : "Copy review link"}
                </button>
              </div>
            </div>
          </div>
        </>
      )}

      {!current && (
        <div className="rs-empty">
          <p>No versions yet. Upload your first bounce (WAV / MP3 / stems) to start a review.</p>
          <label className="rs-upload">
            {uploading ? "Uploading…" : "⬆ Upload first version"}
            <input
              type="file"
              accept=".wav,.mp3,.flac,.ogg,.aif,.aiff,.m4a,audio/*"
              hidden
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) void upload(f);
                e.target.value = "";
              }}
            />
          </label>
        </div>
      )}

      <button type="button" className="session-back-link" onClick={onBack}>
        ← back to sessions
      </button>
    </div>
  );
}

export default function ReviewSessionPage() {
  const [sessions, setSessions] = useState<ReviewSession[]>([]);
  const [openId, setOpenId] = useState<number | null>(null);
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setSessions(await api.listSessions());
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed to load sessions");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const create = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    setBusy(true);
    setErr(null);
    try {
      const s = await api.createSession(name.trim());
      setName("");
      await load();
      setOpenId(s.id);
    } catch (err) {
      setErr(err instanceof Error ? err.message : "Failed to create session");
    } finally {
      setBusy(false);
    }
  };

  if (openId != null) {
    const s = sessions.find((x) => x.id === openId);
    if (!s) return null;
    return <SessionDetail session={s} onBack={() => setOpenId(null)} />;
  }

  return (
    <div className="session-page">
      <div className="session-top">
        <div>
          <Link to="/" className="session-back">← back to home</Link>
          <h1 className="session-title">Review sessions</h1>
          <p className="muted session-sub">
            The Frame.io-style loop for music: share a version, collect timestamped
            feedback, fix, and approve. No ZIP archives, no Discord chaos.
          </p>
        </div>
      </div>

      <form className="session-create" onSubmit={create}>
        <input
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="New session name, e.g. Neon Warehouse"
          className="session-name-input"
        />
        <button type="submit" className="btn" disabled={busy}>
          {busy ? "Creating…" : "New session"}
        </button>
      </form>
      {err && <div className="error">{err}</div>}

      <div className="session-list">
        {sessions.length === 0 && (
          <div className="card muted">
            No sessions yet — create one and upload your first bounce.
          </div>
        )}
        {sessions.map((s) => (
          <div key={s.id} className="session-row" onClick={() => setOpenId(s.id)}>
            <div className="session-row-main">
              <span className="session-row-icon">🎧</span>
              <div>
                <div className="session-row-name">{s.name}</div>
                <div className="session-row-meta">
                  {s.version_count} version{s.version_count === 1 ? "" : "s"} ·{" "}
                  {s.latest_status || "no versions"}
                </div>
              </div>
            </div>
            <span className={`rs-status ${s.latest_status === "approved" ? "status-approved" : s.latest_status === "needs_changes" ? "status-changes" : "status-review"}`}>
              {s.latest_status || "empty"}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
