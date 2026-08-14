import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import { shortDate, type GhBranch, type GhCommit } from "../types";

const REPO_URL = "https://github.com/CRYPTOSCOPE101/SOUNDHUB";

export default function GitHubRepoPage() {
  const [branches, setBranches] = useState<GhBranch[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [commits, setCommits] = useState<GhCommit[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const loadBranches = useCallback(async () => {
    try {
      const b = await api.ghBranches();
      setBranches(b);
      if (b.length && !selected) setSelected(b.find((x) => x.name === "main")?.name ?? b[0].name);
    } catch (err) {
      setError("Could not reach the GitHub API (rate limit?). Showing local info instead.");
    } finally {
      setLoading(false);
    }
  }, [selected]);

  useEffect(() => {
    loadBranches();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!selected) return;
    api
      .ghBranchCommits(selected)
      .then(setCommits)
      .catch(() => setCommits([]));
  }, [selected]);

  return (
    <div>
      <div className="repo-header">
        <div className="repo-breadcrumb">
          <span className="owner">CRYPTOSCOPE101</span>
          <span className="sep">/</span>
          <a className="name" href={REPO_URL} target="_blank" rel="noreferrer">
            SOUNDHUB
          </a>
          <span className="visibility-chip">Public</span>
        </div>
        <p className="repo-desc">
          The SoundHub codebase itself — this page mirrors its git branches
          and commits live from the public GitHub API.
        </p>
        <div className="row" style={{ marginTop: 8, gap: 8 }}>
          <span className="gh-stat">⎇ <b>{branches.length}</b> branches</span>
          <span className="gh-stat">🕘 <b>{commits.length}</b> commits on {selected ?? "—"}</span>
        </div>
      </div>

      {error && <div className="error" style={{ margin: "10px 0" }}>{error}</div>}
      {loading && <p className="muted">Loading branches…</p>}

      {/* branch selector */}
      {!loading && branches.length > 0 && (
        <>
          <div className="row" style={{ margin: "14px 0" }}>
            <select
              value={selected ?? ""}
              onChange={(e) => setSelected(e.target.value)}
              style={{ width: 320 }}
            >
              {branches.map((b) => (
                <option key={b.name} value={b.name}>
                  ⎇ {b.name} {b.protected ? "(protected)" : ""}
                </option>
              ))}
            </select>
            <a className="btn ghost sm" href={`${REPO_URL}/branches`} target="_blank" rel="noreferrer">
              All branches ↗
            </a>
          </div>

          {/* commits on selected branch */}
          <div className="commit-list">
            <div className="commit-list-head">
              <span>Commits on {selected}</span>
              <span>{commits.length}</span>
            </div>
            {commits.length === 0 && <div className="file-row muted">No commits (rate limited?).</div>}
            {commits.map((c) => (
              <a
                key={c.sha}
                className="commit-list-row"
                href={`${REPO_URL}/commit/${c.sha}`}
                target="_blank"
                rel="noreferrer"
                style={{ textDecoration: "none", color: "inherit" }}
              >
                <span className="avatar">{(c.author || "?").slice(0, 1).toUpperCase()}</span>
                <span className="commit-msg">{c.message}</span>
                <span className="sha">{c.sha.slice(0, 7)}</span>
                <span className="commit-meta">
                  {c.author ?? "unknown"} · {c.date ? shortDate(c.date) : ""}
                </span>
              </a>
            ))}
          </div>
        </>
      )}

      {!loading && branches.length === 0 && (
        <div className="card">
          <h2>Branches</h2>
          <p className="muted">
            The GitHub API didn't return branch data right now (unauthenticated
            rate limit). Open the repo directly:{" "}
            <a href={`${REPO_URL}/branches`} target="_blank" rel="noreferrer">
              {REPO_URL}/branches
            </a>
          </p>
        </div>
      )}
    </div>
  );
}
