import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api";
import ReleaseSection from "../components/ReleaseSection";
import { DAW_COLORS, humanSize, shortDate, type Commit, type DawInfo, type Project, type ProjectFile, type Tree } from "../types";

export default function ProjectPage() {
  const { id } = useParams();
  const pid = Number(id);
  const [project, setProject] = useState<Project | null>(null);
  const [tree, setTree] = useState<Tree | null>(null);
  const [commits, setCommits] = useState<Commit[]>([]);
  const [error, setError] = useState<string | null>(null);

  const [message, setMessage] = useState("");
  const [uploading, setUploading] = useState(false);
  const [asFolder, setAsFolder] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  const load = useCallback(async () => {
    try {
      const [p, t, c] = await Promise.all([
        api.getProject(pid),
        api.getTree(pid),
        api.listCommits(pid),
      ]);
      setProject(p);
      setTree(t);
      setCommits(c);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load project");
    }
  }, [pid]);

  useEffect(() => {
    load();
  }, [load]);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const files = fileInput.current?.files;
    if (!files || files.length === 0) {
      setNotice("Select at least one file to commit.");
      return;
    }
    setUploading(true);
    setNotice(null);
    try {
      await api.createCommit(pid, message.trim() || "Update project files", files);
      setMessage("");
      if (fileInput.current) fileInput.current.value = "";
      await load();
      setNotice("Commit created ✓");
    } catch (err) {
      setNotice(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  const dawBadge = (f: ProjectFile) =>
    f.daw_format && (
      <span
        className="badge badge-daw"
        style={{ background: DAW_COLORS[f.daw_format] ?? "#888" }}
      >
        {f.daw_format.toUpperCase()}
      </span>
    );

  const headCommit = tree ? tree.commit_id : commits[0]?.id;
  const prevCommit = commits.find((c) => c.id !== headCommit)?.id;

  return (
    <div>
      <div className="row" style={{ marginBottom: 6 }}>
        <Link to="/projects" className="muted" style={{ fontSize: 13 }}>
          ← projects
        </Link>
        <span className="spacer" />
        <button
          className="btn danger"
          onClick={async () => {
            if (confirm("Delete this project and all its commits?")) {
              await api.deleteProject(pid);
              window.location.href = "/projects";
            }
          }}
        >
          Delete repo
        </button>
      </div>

      {project && (
        <div style={{ marginBottom: 16 }}>
          <h1>🎛 {project.name}</h1>
          <p className="muted" style={{ margin: "4px 0 0" }}>
            {project.description || "No description"}
          </p>
        </div>
      )}

      {error && <div className="error">{error}</div>}

      {project && (
        <ReleaseSection
          projectId={pid}
          projectName={project.name}
          releaseTokenId={project.release_token_id}
          releaseContract={project.release_contract}
          releaseName={project.release_name}
          onBound={() => load()}
        />
      )}

      <div className="split">
        <div>
          {/* Upload */}
          <form className="card" onSubmit={submit} style={{ marginBottom: 20 }}>
            <h2>Commit files</h2>
            <input
              type="text"
              placeholder="Commit message, e.g. 'Add synth lead to arrangement'"
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              style={{ marginBottom: 10 }}
            />
            <label className="upload-zone" style={{ display: "block" }}>
              <input
                ref={fileInput}
                type="file"
                multiple
                hidden
                {...(asFolder ? { webkitdirectory: "", directory: "" } : {})}
              />
              Click to select files{asFolder ? " (folder)" : ""} — .als, .cpr,
              .rpp, .flp and samples all work.
            </label>
            <div className="row" style={{ marginTop: 10 }}>
              <label className="muted" style={{ fontSize: 13 }}>
                <input
                  type="checkbox"
                  checked={asFolder}
                  onChange={(e) => setAsFolder(e.target.checked)}
                />{" "}
                upload whole folder (keeps paths)
              </label>
              <span className="spacer" />
              <button className="btn" disabled={uploading}>
                {uploading ? "Committing…" : "Create commit"}
              </button>
            </div>
            {notice && (
              <div className={notice.includes("✓") ? "success" : "error"} style={{ marginTop: 10 }}>
                {notice}
              </div>
            )}
          </form>

          {/* Files */}
          <div className="card">
            <div className="row" style={{ marginBottom: 10 }}>
              <h2 style={{ margin: 0 }}>Files</h2>
              <span className="spacer" />
              {tree && (
                <span className="commit-marker">
                  HEAD · {tree.commit_message}
                </span>
              )}
            </div>
            {!tree ? (
              <p className="muted">No commits yet — upload your project files.</p>
            ) : (
              tree.files.map((f) => {
                const isOpen = expanded === f.path;
                return (
                  <div key={f.path}>
                    <div className="file-row" onClick={() => setExpanded(isOpen ? null : f.path)}>
                      <span className="file-icon">{f.daw_format ? "🎛" : "📄"}</span>
                      <span style={{ flex: 1, fontFamily: "monospace", fontSize: 13 }}>
                        {f.path}
                      </span>
                      {dawBadge(f)}
                      <span className="muted" style={{ fontSize: 12, width: 60, textAlign: "right" }}>
                        {humanSize(f.size)}
                      </span>
                      <a
                        className="muted"
                        style={{ fontSize: 12, textDecoration: "none" }}
                        href={api.fileUrl(pid, f.path, true)}
                        title="Download"
                        onClick={(e) => e.stopPropagation()}
                      >
                        ⬇
                      </a>
                      {headCommit && prevCommit && (
                        <Link
                          className="muted"
                          style={{ fontSize: 12, textDecoration: "none" }}
                          to={`/projects/${pid}/diff?path=${encodeURIComponent(f.path)}&from=${prevCommit}&to=${headCommit}`}
                          title="Diff vs previous commit"
                          onClick={(e) => e.stopPropagation()}
                        >
                          ⇄
                        </Link>
                      )}
                    </div>
                    {isOpen && <DawInfoBox info={f.daw_info} />}
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Commits sidebar */}
        <div className="card sidebar-card">
          <h2>History</h2>
          {commits.length === 0 ? (
            <p className="muted">No commits</p>
          ) : (
            commits.map((c) => (
              <Link
                key={c.id}
                className="commit-item"
                to={`/projects/${pid}/commit/${c.id}`}
              >
                <div className="msg">{c.message || "(no message)"}</div>
                <div className="muted" style={{ fontSize: 12, marginTop: 3 }}>
                  <span className="commit-marker">#{c.id}</span> · {c.author.username} ·{" "}
                  {shortDate(c.created_at)}
                </div>
                <div className="muted" style={{ fontSize: 12 }}>
                  {c.file_count} file(s) · {humanSize(c.total_size)}
                </div>
              </Link>
            ))
          )}
        </div>
      </div>
    </div>
  );
}

function DawInfoBox({ info }: { info: DawInfo | null }) {
  if (!info) {
    return (
      <div className="daw-box muted" style={{ fontSize: 12 }}>
        Not a recognized DAW project file (or too large to analyze).
      </div>
    );
  }
  return (
    <div className="daw-box">
      <div className="daw-grid">
        <div>
          <dt>DAW</dt>
          <dd>
            {info.format} <span className="muted">({info.version})</span>
          </dd>
        </div>
        <div>
          <dt>BPM</dt>
          <dd>{info.bpm ?? "—"}</dd>
        </div>
        <div>
          <dt>Signature</dt>
          <dd>{info.time_signature ?? "—"}</dd>
        </div>
        <div>
          <dt>Tracks</dt>
          <dd>
            {info.tracks.map((t) => (
              <div className="track-row" key={t.name + t.kind}>
                <span>{t.name}</span>
                <span className="track-kind">{t.kind}</span>
              </div>
            ))}
          </dd>
        </div>
        <div>
          <dt>Plugins</dt>
          <dd>{info.plugins.length ? info.plugins.join(", ") : "—"}</dd>
        </div>
        <div>
          <dt>Samples</dt>
          <dd>{info.samples.length ? info.samples.join(", ") : "—"}</dd>
        </div>
      </div>
    </div>
  );
}
