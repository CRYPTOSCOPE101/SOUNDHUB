import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api";
import { shortDate, type Branch, type Project } from "../types";
import { errorMessage } from "../errors";

export default function BranchesPage() {
  const { id } = useParams();
  const pid = Number(id);
  const [project, setProject] = useState<Project | null>(null);
  const [branches, setBranches] = useState<Branch[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [from, setFrom] = useState("main");

  const load = useCallback(async () => {
    try {
      const [p, b] = await Promise.all([api.getProject(pid), api.listBranches(pid)]);
      setProject(p);
      setBranches(b);
    } catch (err) {
      setError(errorMessage(err, "Failed"));
    }
  }, [pid]);

  useEffect(() => {
    load();
  }, [load]);

  const create = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setNotice(null);
    try {
      await api.createBranch(pid, name.trim(), from);
      setName("");
      await load();
      setNotice(`Branch "${name.trim()}" created ✓`);
    } catch (err) {
      setError(errorMessage(err, "Create failed"));
    }
  };

  const remove = async (name_: string) => {
    if (!confirm(`Delete branch "${name_}"? Its commits stay in history.`)) return;
    try {
      await api.deleteBranch(pid, name_);
      await load();
    } catch (err) {
      setError(errorMessage(err, "Delete failed"));
    }
  };

  return (
    <div>
      <div className="row" style={{ marginBottom: 14 }}>
        <Link to={`/projects/${pid}`} className="btn ghost sm">
          ← project
        </Link>
        <span className="spacer" />
      </div>

      {project && (
        <div className="repo-breadcrumb" style={{ marginBottom: 14 }}>
          <span className="owner">{project.owner.username}</span>
          <span className="sep">/</span>
          <span className="name">{project.name}</span>
          <span className="sep">/</span>
          <span className="name">Branches</span>
        </div>
      )}

      {error && <div className="error" style={{ margin: "8px 0" }}>{error}</div>}
      {notice && <div className="success" style={{ margin: "8px 0" }}>{notice}</div>}

      <form className="card" onSubmit={create} style={{ marginBottom: 16 }}>
        <h2>New branch</h2>
        <div className="row" style={{ gap: 8 }}>
          <input
            type="text"
            placeholder="Branch name, e.g. remix-vocals"
            value={name}
            onChange={(e) => setName(e.target.value)}
            style={{ flex: 2 }}
          />
          <select value={from} onChange={(e) => setFrom(e.target.value)} style={{ width: 180 }}>
            {branches.map((b) => (
              <option key={b.name} value={b.name}>
                from {b.name}
              </option>
            ))}
          </select>
          <button className="btn" disabled={!name.trim()}>
            Create branch
          </button>
        </div>
      </form>

      <div className="branches-table">
        <div className="file-table-head">
          <span>Branches</span>
          <span>{branches.length}</span>
        </div>
        {branches.map((b) => (
          <div className="file-row" key={b.name}>
            <span className="file-icon">⎇</span>
            <span style={{ flex: 1 }}>
              <Link to={`/projects/${pid}?branch=${encodeURIComponent(b.name)}`} style={{ fontWeight: 700 }}>
                {b.name}
              </Link>
              {b.is_default && <span className="default-badge" style={{ marginLeft: 8 }}>default</span>}
              <div className="muted" style={{ fontSize: 12, marginTop: 2 }}>
                {b.head_sha ? (
                  <>
                    <span className="sha">{b.head_sha}</span> · {b.head_message.slice(0, 60)}
                    {" · "}
                    {b.head_date ? shortDate(b.head_date) : ""}
                  </>
                ) : (
                  "no commits"
                )}
              </div>
            </span>
            <span className="muted" style={{ fontSize: 12 }}>
              {b.commit_count} commit(s)
            </span>
            {!b.is_default && (
              <button className="btn danger sm" onClick={() => remove(b.name)}>
                Delete
              </button>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
