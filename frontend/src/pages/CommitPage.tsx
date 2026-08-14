import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api";
import { DAW_COLORS, humanSize, shortDate, type CommitDetail } from "../types";

export default function CommitPage() {
  const { id, commitId } = useParams();
  const pid = Number(id);
  const cid = Number(commitId);
  const [commit, setCommit] = useState<CommitDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .getCommit(pid, cid)
      .then(setCommit)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed"));
  }, [pid, cid]);

  if (error) return <div className="error">{error}</div>;
  if (!commit) return <p className="muted">Loading…</p>;

  return (
    <div>
      <div className="row" style={{ marginBottom: 6 }}>
        <Link to={`/projects/${pid}`} className="muted" style={{ fontSize: 13 }}>
          ← project
        </Link>
      </div>
      <h1>
        <span className="commit-marker">#{commit.id}</span> {commit.message || "(no message)"}
      </h1>
      <p className="muted" style={{ marginTop: 0 }}>
        {commit.author.username} committed {shortDate(commit.created_at)} ·{" "}
        {commit.file_count} file(s) · {humanSize(commit.total_size)}
      </p>

      <div className="card">
        <h2>Files in this commit</h2>
        {commit.files.length === 0 && <p className="muted">Empty commit.</p>}
        {commit.files.map((f) => {
          const prev = commit.parent_id;
          return (
            <div className="file-row" key={f.path}>
              <span className="file-icon">{f.daw_format ? "🎛" : "📄"}</span>
              <span style={{ flex: 1, fontFamily: "monospace", fontSize: 13 }}>
                {f.path}
              </span>
              {f.daw_format && (
                <span
                  className="badge badge-daw"
                  style={{ background: DAW_COLORS[f.daw_format] ?? "#888" }}
                >
                  {f.daw_format.toUpperCase()}
                </span>
              )}
              <span className="muted" style={{ fontSize: 12 }}>
                {humanSize(f.size)}
              </span>
              <Link
                className="btn ghost"
                style={{ padding: "4px 10px", fontSize: 12 }}
                to={`/projects/${pid}/diff?path=${encodeURIComponent(f.path)}&to=${commit.id}${prev ? `&from=${prev}` : ""}`}
              >
                Diff vs parent
              </Link>
              <a
                className="muted"
                style={{ fontSize: 12, textDecoration: "none" }}
                href={api.fileUrl(pid, f.path, true)}
                title="Download"
              >
                ⬇
              </a>
            </div>
          );
        })}
      </div>
    </div>
  );
}
