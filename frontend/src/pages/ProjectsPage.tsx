import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import type { Project } from "../types";

export default function ProjectsPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [name, setName] = useState("");
  const [desc, setDesc] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      setProjects(await api.listProjects());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load projects");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const create = async (e: FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    setError(null);
    try {
      const p = await api.createProject(name.trim(), desc.trim());
      setName("");
      setDesc("");
      await load();
      window.location.href = `/projects/${p.id}`;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create");
    }
  };

  return (
    <div>
      <div className="row" style={{ marginBottom: 20 }}>
        <h1 style={{ margin: 0 }}>Projects</h1>
        <span className="muted">{projects.length} repo(s)</span>
      </div>

      <form className="card" onSubmit={create} style={{ marginBottom: 20 }}>
        <h2>New project</h2>
        <div className="row">
          <input
            type="text"
            placeholder="Project name, e.g. 'Neon Dreams EP'"
            value={name}
            onChange={(e) => setName(e.target.value)}
            style={{ flex: 2, minWidth: 260 }}
          />
          <input
            type="text"
            placeholder="Short description"
            value={desc}
            onChange={(e) => setDesc(e.target.value)}
            style={{ flex: 3, minWidth: 260 }}
          />
          <button className="btn" type="submit">
            Create repo
          </button>
        </div>
        {error && <div className="error" style={{ marginTop: 10 }}>{error}</div>}
      </form>

      {loading ? (
        <p className="muted">Loading…</p>
      ) : projects.length === 0 ? (
        <p className="muted">
          No projects yet. Create your first repo above — upload an Ableton,
          Cubase, REAPER or FL Studio project file.
        </p>
      ) : (
        <div className="grid">
          {projects.map((p) => (
            <Link key={p.id} to={`/projects/${p.id}`} className="card project-card">
              <div className="name">🎛 {p.name}</div>
              <div className="desc">{p.description || "No description"}</div>
              <div className="row muted" style={{ fontSize: 12 }}>
                <span>@{p.owner.username}</span>
                <span>·</span>
                <span>updated {new Date(p.updated_at).toLocaleDateString()}</span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
