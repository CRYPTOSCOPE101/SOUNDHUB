import { useEffect, useState, useCallback, type FormEvent } from "react";
import { useParams, Link } from "react-router-dom";
import { api } from "../api";
import { shortDate } from "../types";

type FeatureTab =
  | "wiki" | "sprints" | "retros" | "tests" | "kanban"
  | "tasks" | "prs" | "milestones" | "epics" | "discussions"
  | "workflows" | "tags" | "artifacts" | "incidents" | "flags"
  | "time" | "okrs" | "status";

const TABS: { key: FeatureTab; label: string; icon: string }[] = [
  { key: "wiki", label: "Wiki", icon: "📚" },
  { key: "sprints", label: "Sprints", icon: "🏃" },
  { key: "retros", label: "Retros", icon: "🔄" },
  { key: "tests", label: "Test Plans", icon: "🧪" },
  { key: "kanban", label: "Kanban", icon: "📋" },
  { key: "tasks", label: "Tasks", icon: "📌" },
  { key: "prs", label: "Pull Requests", icon: "🔀" },
  { key: "milestones", label: "Milestones", icon: "🏁" },
  { key: "epics", label: "Epics", icon: "🎯" },
  { key: "discussions", label: "Discussions", icon: "💬" },
  { key: "workflows", label: "Workflows", icon: "⚙️" },
  { key: "tags", label: "Tags", icon: "🏷" },
  { key: "artifacts", label: "Artifacts", icon: "📦" },
  { key: "incidents", label: "Incidents", icon: "🚨" },
  { key: "flags", label: "Feature Flags", icon: "🚩" },
  { key: "time", label: "Time Track", icon: "⏱" },
  { key: "okrs", label: "OKRs", icon: "📊" },
  { key: "status", label: "Status Page", icon: "🟢" },
];

export default function ProjectFeaturesHub() {
  const { id } = useParams();
  const pid = Number(id);
  const [tab, setTab] = useState<FeatureTab>("wiki");
  const [projectName, setProjectName] = useState("");

  useEffect(() => {
    api.getProject(pid).then((p) => setProjectName(p.name)).catch(() => {});
  }, [pid]);

  return (
    <div>
      <div className="repo-header">
        <div className="repo-breadcrumb">
          <Link to={`/projects/${pid}`} className="owner">{projectName || `Project #${pid}`}</Link>
          <span className="sep">/</span>
          <span className="name">Features</span>
        </div>
        <div className="repo-tabs" style={{ flexWrap: "wrap" }}>
          {TABS.map((t) => (
            <button
              key={t.key}
              className={`repo-tab ${tab === t.key ? "active" : ""}`}
              onClick={() => setTab(t.key)}
              style={{ background: "none", border: "none", cursor: "pointer", fontFamily: "inherit" }}
            >
              <span>{t.icon}</span> {t.label}
            </button>
          ))}
        </div>
      </div>

      {tab === "wiki" && <WikiTab pid={pid} />}
      {tab === "sprints" && <SprintsTab pid={pid} />}
      {tab === "retros" && <RetrosTab pid={pid} />}
      {tab === "tests" && <TestsTab pid={pid} />}
      {tab === "kanban" && <KanbanTab pid={pid} />}
      {tab === "tasks" && <TasksTab pid={pid} />}
      {tab === "prs" && <PRsTab pid={pid} />}
      {tab === "milestones" && <MilestonesTab pid={pid} />}
      {tab === "epics" && <EpicsTab pid={pid} />}
      {tab === "discussions" && <DiscussionsTab pid={pid} />}
      {tab === "workflows" && <WorkflowsTab pid={pid} />}
      {tab === "tags" && <TagsTab pid={pid} />}
      {tab === "artifacts" && <ArtifactsTab pid={pid} />}
      {tab === "incidents" && <IncidentsTab pid={pid} />}
      {tab === "flags" && <FlagsTab pid={pid} />}
      {tab === "time" && <TimeTab pid={pid} />}
      {tab === "okrs" && <OKRsTab pid={pid} />}
      {tab === "status" && <StatusTab pid={pid} />}
    </div>
  );
}

// ── Helper ──────────────────────────────────────────────────────────────────
function useList<T>(fn: () => Promise<T[]>) {
  const [items, setItems] = useState<T[]>([]);
  const [loading, setLoading] = useState(true);
  const load = useCallback(async () => {
    setLoading(true);
    try { setItems(await fn()); } catch { /* */ }
    setLoading(false);
  }, []);
  useEffect(() => { load(); }, [load]);
  return { items, loading, reload: load };
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="card" style={{ marginTop: 16 }}>
      <h2>{title}</h2>
      {children}
    </div>
  );
}

function Empty({ text }: { text: string }) {
  return <p className="muted" style={{ fontSize: 14 }}>{text}</p>;
}

// ── Wiki ────────────────────────────────────────────────────────────────────
function WikiTab({ pid }: { pid: number }) {
  const { items, loading, reload } = useList(() => api.listWiki(pid));
  const [slug, setSlug] = useState("");
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [creating, setCreating] = useState(false);

  const create = async (e: FormEvent) => {
    e.preventDefault();
    setCreating(true);
    try {
      await api.createWikiPage(pid, slug, title, content);
      setSlug(""); setTitle(""); setContent("");
      reload();
    } finally { setCreating(false); }
  };

  return (
    <>
      <Section title="Wiki Pages">
        {loading ? <Empty text="Loading..." /> : items.length === 0 ? (
          <Empty text="No wiki pages yet. Create one below." />
        ) : (
          <div className="commit-list">
            {items.map((p: any) => (
              <div className="commit-list-row" key={p.slug}>
                <span>📄</span>
                <span className="commit-msg">{p.title}</span>
                <span className="muted" style={{ fontSize: 12 }}>v{p.version}</span>
                <span className="commit-meta">{shortDate(p.updated_at)}</span>
              </div>
            ))}
          </div>
        )}
      </Section>
      <Section title="Create Page">
        <form onSubmit={create}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginBottom: 10 }}>
            <input placeholder="slug (e.g. mixing-guide)" value={slug} onChange={(e) => setSlug(e.target.value)} required />
            <input placeholder="Title" value={title} onChange={(e) => setTitle(e.target.value)} required />
          </div>
          <textarea placeholder="Markdown content..." value={content} onChange={(e) => setContent(e.target.value)}
            style={{ minHeight: 120, marginBottom: 10 }} />
          <button className="btn" disabled={creating}>{creating ? "Creating..." : "Create Page"}</button>
        </form>
      </Section>
    </>
  );
}

// ── Sprints ─────────────────────────────────────────────────────────────────
function SprintsTab({ pid }: { pid: number }) {
  const { items, loading, reload } = useList(() => api.listSprints(pid));
  const [name, setName] = useState("");

  const create = async (e: FormEvent) => {
    e.preventDefault();
    await api.createSprint(pid, name);
    setName(""); reload();
  };

  const stateColor = (s: string) => s === "active" ? "var(--green)" : s === "completed" ? "var(--muted)" : "var(--blue)";

  return (
    <Section title="Sprints">
      {loading ? <Empty text="Loading..." /> : items.length === 0 ? (
        <Empty text="No sprints yet." />
      ) : (
        <div className="commit-list">
          {items.map((s: any) => (
            <div className="commit-list-row" key={s.id}>
              <span style={{ color: stateColor(s.state) }}>●</span>
              <span className="commit-msg">{s.name}</span>
              {s.goal && <span className="muted" style={{ fontSize: 12 }}>{s.goal}</span>}
              <span className="chip" style={{ borderColor: stateColor(s.state), color: stateColor(s.state) }}>{s.state}</span>
              {s.velocity > 0 && <span className="muted" style={{ fontSize: 12 }}>{s.velocity} pts</span>}
              {s.state === "planned" && (
                <button className="btn sm ghost" onClick={() => api.updateSprint(pid, s.id, "active").then(reload)}>Start</button>
              )}
              {s.state === "active" && (
                <button className="btn sm ghost" onClick={() => api.updateSprint(pid, s.id, "completed").then(reload)}>Complete</button>
              )}
            </div>
          ))}
        </div>
      )}
      <form onSubmit={create} style={{ marginTop: 10, display: "flex", gap: 8 }}>
        <input placeholder="Sprint name" value={name} onChange={(e) => setName(e.target.value)} required style={{ flex: 1 }} />
        <button className="btn sm">Create Sprint</button>
      </form>
    </Section>
  );
}

// ── Retrospectives ──────────────────────────────────────────────────────────
function RetrosTab({ pid }: { pid: number }) {
  const { items, loading, reload } = useList(() => api.listRetros(pid));
  const [name, setName] = useState("");
  const [selected, setSelected] = useState<number | null>(null);
  const [retroItems, setRetroItems] = useState<any[]>([]);
  const [itemContent, setItemContent] = useState("");
  const [itemCat, setItemCat] = useState("went_well");

  useEffect(() => {
    if (selected) api.listRetroItems(pid, selected).then(setRetroItems).catch(() => setRetroItems([]));
  }, [selected, pid]);

  const create = async (e: FormEvent) => {
    e.preventDefault();
    await api.createRetro(pid, name);
    setName(""); reload();
  };

  const addItem = async () => {
    if (!selected || !itemContent) return;
    await api.addRetroItem(pid, selected, itemCat, itemContent);
    setItemContent("");
    api.listRetroItems(pid, selected).then(setRetroItems);
  };

  const catEmoji = (c: string) => c === "went_well" ? "✅" : c === "to_improve" ? "⚠️" : "🎯";

  return (
    <>
      <Section title="Retrospectives">
        {loading ? <Empty text="Loading..." /> : items.length === 0 ? (
          <Empty text="No retrospectives yet." />
        ) : (
          <div className="commit-list">
            {items.map((r: any) => (
              <div className="commit-list-row" key={r.id} onClick={() => setSelected(r.id)}
                style={{ cursor: "pointer", background: selected === r.id ? "var(--bg3)" : undefined }}>
                <span>🔄</span>
                <span className="commit-msg">{r.name}</span>
                <span className="chip">{r.state}</span>
                <span className="muted" style={{ fontSize: 12 }}>{r.item_count} items</span>
              </div>
            ))}
          </div>
        )}
        <form onSubmit={create} style={{ marginTop: 10, display: "flex", gap: 8 }}>
          <input placeholder="Retro name" value={name} onChange={(e) => setName(e.target.value)} required style={{ flex: 1 }} />
          <button className="btn sm">Create Retro</button>
        </form>
      </Section>

      {selected && (
        <Section title={`Retro Items (${retroItems.length})`}>
          <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
            <select value={itemCat} onChange={(e) => setItemCat(e.target.value)}>
              <option value="went_well">✅ Went Well</option>
              <option value="to_improve">⚠️ To Improve</option>
              <option value="action_item">🎯 Action Item</option>
            </select>
            <input placeholder="Add item..." value={itemContent} onChange={(e) => setItemContent(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && addItem()} style={{ flex: 1 }} />
            <button className="btn sm" onClick={addItem}>Add</button>
          </div>
          {retroItems.map((item: any) => (
            <div key={item.id} style={{ display: "flex", alignItems: "center", gap: 8, padding: "6px 0", borderBottom: "1px solid var(--border)" }}>
              <span>{catEmoji(item.category)}</span>
              <span style={{ flex: 1, fontSize: 14 }}>{item.content}</span>
              <button className="btn sm ghost" onClick={() => api.voteRetroItem(pid, item.id).then(() => api.listRetroItems(pid, selected).then(setRetroItems))}>
                👍 {item.votes}
              </button>
            </div>
          ))}
        </Section>
      )}
    </>
  );
}

// ── Test Plans ──────────────────────────────────────────────────────────────
function TestsTab({ pid }: { pid: number }) {
  const { items: plans, loading, reload } = useList(() => api.listTestPlans(pid));
  const [name, setName] = useState("");
  const { items: runs } = useList(() => api.listTestRuns(pid));

  const create = async (e: FormEvent) => {
    e.preventDefault();
    await api.createTestPlan(pid, name);
    setName(""); reload();
  };

  return (
    <>
      <Section title="Test Plans">
        {loading ? <Empty text="Loading..." /> : plans.length === 0 ? (
          <Empty text="No test plans yet." />
        ) : (
          <div className="commit-list">
            {plans.map((p: any) => (
              <div className="commit-list-row" key={p.id}>
                <span>🧪</span>
                <span className="commit-msg">{p.name}</span>
                <span className="chip">{p.state}</span>
              </div>
            ))}
          </div>
        )}
        <form onSubmit={create} style={{ marginTop: 10, display: "flex", gap: 8 }}>
          <input placeholder="Plan name" value={name} onChange={(e) => setName(e.target.value)} required style={{ flex: 1 }} />
          <button className="btn sm">Create Plan</button>
        </form>
      </Section>

      <Section title="Test Runs">
        {runs.length === 0 ? <Empty text="No test runs yet." /> : (
          <div className="commit-list">
            {runs.map((r: any) => (
              <div className="commit-list-row" key={r.id}>
                <span>{r.state === "completed" ? (r.failed === 0 ? "✅" : "❌") : "🔄"}</span>
                <span className="commit-msg">{r.name}</span>
                <span className="chip">{r.state}</span>
                {r.total > 0 && (
                  <span className="muted" style={{ fontSize: 12 }}>
                    {r.passed}/{r.total} passed
                  </span>
                )}
              </div>
            ))}
          </div>
        )}
      </Section>
    </>
  );
}

// ── Kanban ──────────────────────────────────────────────────────────────────
function KanbanTab({ pid }: { pid: number }) {
  const { items, loading } = useList(() => api.listKanbanBoards(pid));
  return (
    <Section title="Kanban Boards">
      {loading ? <Empty text="Loading..." /> : items.length === 0 ? (
        <Empty text="No boards yet. Create one via the API." />
      ) : (
        <div className="commit-list">
          {items.map((b: any) => (
            <div className="commit-list-row" key={b.id}>
              <span>📋</span>
              <span className="commit-msg">{b.name}</span>
            </div>
          ))}
        </div>
      )}
    </Section>
  );
}

// ── Tasks ───────────────────────────────────────────────────────────────────
function TasksTab({ pid }: { pid: number }) {
  const { items, loading, reload } = useList(() => api.listTasks(pid));
  const [title, setTitle] = useState("");
  const [type, setType] = useState("task");

  const create = async (e: FormEvent) => {
    e.preventDefault();
    await api.createTask(pid, title, "", type);
    setTitle(""); reload();
  };

  const priorityColor = (p: string) => p === "high" || p === "critical" ? "var(--red)" : p === "medium" ? "var(--yellow)" : "var(--muted)";
  const typeEmoji = (t: string) => t === "bug" ? "🐛" : t === "feature" ? "✨" : t === "question" ? "❓" : "📌";

  return (
    <Section title="Tasks">
      {loading ? <Empty text="Loading..." /> : items.length === 0 ? (
        <Empty text="No tasks yet." />
      ) : (
        <div className="commit-list">
          {items.map((t: any) => (
            <div className="commit-list-row" key={t.id}>
              <span>{typeEmoji(t.type)}</span>
              <span className="commit-msg">{t.title}</span>
              <span className="chip" style={{ borderColor: priorityColor(t.priority), color: priorityColor(t.priority) }}>
                {t.priority}
              </span>
              <span className="chip">{t.status}</span>
            </div>
          ))}
        </div>
      )}
      <form onSubmit={create} style={{ marginTop: 10, display: "flex", gap: 8 }}>
        <select value={type} onChange={(e) => setType(e.target.value)}>
          <option value="task">📌 Task</option>
          <option value="bug">🐛 Bug</option>
          <option value="feature">✨ Feature</option>
          <option value="question">❓ Question</option>
        </select>
        <input placeholder="Task title" value={title} onChange={(e) => setTitle(e.target.value)} required style={{ flex: 1 }} />
        <button className="btn sm">Create</button>
      </form>
    </Section>
  );
}

// ── Pull Requests ───────────────────────────────────────────────────────────
function PRsTab({ pid }: { pid: number }) {
  const { items, loading } = useList(() => api.listPullRequests(pid));
  const statusColor = (s: string) => s === "open" ? "var(--green)" : s === "merged" ? "var(--blue)" : "var(--muted)";

  return (
    <Section title="Pull Requests">
      {loading ? <Empty text="Loading..." /> : items.length === 0 ? (
        <Empty text="No pull requests yet." />
      ) : (
        <div className="commit-list">
          {items.map((pr: any) => (
            <div className="commit-list-row" key={pr.id}>
              <span style={{ color: statusColor(pr.status) }}>●</span>
              <span className="commit-msg">{pr.title}</span>
              <span className="muted" style={{ fontSize: 12 }}>{pr.source_branch} → {pr.target_branch}</span>
              <span className="chip" style={{ borderColor: statusColor(pr.status), color: statusColor(pr.status) }}>{pr.status}</span>
            </div>
          ))}
        </div>
      )}
    </Section>
  );
}

// ── Milestones ──────────────────────────────────────────────────────────────
function MilestonesTab({ pid }: { pid: number }) {
  const { items, loading } = useList(() => api.listMilestones(pid));
  return (
    <Section title="Milestones">
      {loading ? <Empty text="Loading..." /> : items.length === 0 ? (
        <Empty text="No milestones yet." />
      ) : (
        <div className="commit-list">
          {items.map((m: any) => (
            <div className="commit-list-row" key={m.id}>
              <span>🏁</span>
              <span className="commit-msg">{m.title}</span>
              <span className="chip">{m.status}</span>
              {m.due_date && <span className="muted" style={{ fontSize: 12 }}>Due: {shortDate(m.due_date)}</span>}
            </div>
          ))}
        </div>
      )}
    </Section>
  );
}

// ── Epics ───────────────────────────────────────────────────────────────────
function EpicsTab({ pid }: { pid: number }) {
  const { items, loading } = useList(() => api.listEpics(pid));
  return (
    <Section title="Epics">
      {loading ? <Empty text="Loading..." /> : items.length === 0 ? (
        <Empty text="No epics yet." />
      ) : (
        <div className="commit-list">
          {items.map((e: any) => (
            <div className="commit-list-row" key={e.id}>
              <span style={{ color: e.color || "var(--accent)" }}>●</span>
              <span className="commit-msg">{e.title}</span>
              <span className="chip">{e.status}</span>
              <span className="muted" style={{ fontSize: 12 }}>{e.task_count} tasks</span>
            </div>
          ))}
        </div>
      )}
    </Section>
  );
}

// ── Discussions ─────────────────────────────────────────────────────────────
function DiscussionsTab({ pid }: { pid: number }) {
  const { items, loading } = useList(() => api.listDiscussions(pid));
  return (
    <Section title="Discussions">
      {loading ? <Empty text="Loading..." /> : items.length === 0 ? (
        <Empty text="No discussions yet." />
      ) : (
        <div className="commit-list">
          {items.map((d: any) => (
            <div className="commit-list-row" key={d.id}>
              <span>💬</span>
              <span className="commit-msg">{d.title}</span>
              <span className="chip">{d.category}</span>
              {d.pinned && <span className="muted" style={{ fontSize: 12 }}>📌 Pinned</span>}
            </div>
          ))}
        </div>
      )}
    </Section>
  );
}

// ── Workflows ───────────────────────────────────────────────────────────────
function WorkflowsTab({ pid }: { pid: number }) {
  const { items, loading } = useList(() => api.listWorkflows(pid));
  return (
    <Section title="CI/CD Workflows">
      {loading ? <Empty text="Loading..." /> : items.length === 0 ? (
        <Empty text="No workflows configured." />
      ) : (
        <div className="commit-list">
          {items.map((w: any) => (
            <div className="commit-list-row" key={w.id}>
              <span>⚙️</span>
              <span className="commit-msg">{w.name}</span>
              <span className="muted" style={{ fontSize: 12 }}>{w.filename}</span>
              <span className="chip">{w.enabled ? "enabled" : "disabled"}</span>
            </div>
          ))}
        </div>
      )}
    </Section>
  );
}

// ── Tags ────────────────────────────────────────────────────────────────────
function TagsTab({ pid }: { pid: number }) {
  const { items, loading } = useList(() => api.listTags(pid));
  return (
    <Section title="Tags & Releases">
      {loading ? <Empty text="Loading..." /> : items.length === 0 ? (
        <Empty text="No tags yet." />
      ) : (
        <div className="commit-list">
          {items.map((t: any) => (
            <div className="commit-list-row" key={t.id}>
              <span>🏷</span>
              <span className="commit-msg">{t.name}</span>
              {t.is_release && <span className="chip" style={{ borderColor: "var(--green)", color: "var(--green)" }}>release</span>}
              {t.message && <span className="muted" style={{ fontSize: 12 }}>{t.message}</span>}
            </div>
          ))}
        </div>
      )}
    </Section>
  );
}

// ── Artifacts ───────────────────────────────────────────────────────────────
function ArtifactsTab({ pid }: { pid: number }) {
  const { items, loading } = useList(() => api.listArtifactFeeds(pid));
  return (
    <Section title="Artifact Feeds">
      {loading ? <Empty text="Loading..." /> : items.length === 0 ? (
        <Empty text="No artifact feeds yet." />
      ) : (
        <div className="commit-list">
          {items.map((f: any) => (
            <div className="commit-list-row" key={f.id}>
              <span>📦</span>
              <span className="commit-msg">{f.name}</span>
              <span className="chip">{f.type}</span>
              <span className="chip">{f.visibility}</span>
            </div>
          ))}
        </div>
      )}
    </Section>
  );
}

// ── Incidents ───────────────────────────────────────────────────────────────
function IncidentsTab({ pid }: { pid: number }) {
  const { items, loading } = useList(() => api.listIncidents(pid));
  const sevColor = (s: string) => s === "critical" ? "var(--red)" : s === "major" ? "var(--yellow)" : "var(--muted)";
  return (
    <Section title="Incidents">
      {loading ? <Empty text="Loading..." /> : items.length === 0 ? (
        <Empty text="No incidents." />
      ) : (
        <div className="commit-list">
          {items.map((i: any) => (
            <div className="commit-list-row" key={i.id}>
              <span style={{ color: sevColor(i.severity) }}>●</span>
              <span className="commit-msg">{i.title}</span>
              <span className="chip" style={{ borderColor: sevColor(i.severity), color: sevColor(i.severity) }}>{i.severity}</span>
              <span className="chip">{i.status}</span>
            </div>
          ))}
        </div>
      )}
    </Section>
  );
}

// ── Feature Flags ───────────────────────────────────────────────────────────
function FlagsTab({ pid }: { pid: number }) {
  const { items, loading, reload } = useList(() => api.listFeatureFlags(pid));
  return (
    <Section title="Feature Flags">
      {loading ? <Empty text="Loading..." /> : items.length === 0 ? (
        <Empty text="No feature flags." />
      ) : (
        <div className="commit-list">
          {items.map((f: any) => (
            <div className="commit-list-row" key={f.id}>
              <span>{f.enabled ? "🟢" : "🔴"}</span>
              <span className="commit-msg">{f.name}</span>
              {f.description && <span className="muted" style={{ fontSize: 12 }}>{f.description}</span>}
              <button className="btn sm ghost" onClick={() => api.toggleFeatureFlag(pid, f.id, !f.enabled).then(reload)}>
                {f.enabled ? "Disable" : "Enable"}
              </button>
            </div>
          ))}
        </div>
      )}
    </Section>
  );
}

// ── Time Tracking ───────────────────────────────────────────────────────────
function TimeTab({ pid }: { pid: number }) {
  const [data, setData] = useState<any>({ entries: [], total_minutes: 0 });
  const [hours, setHours] = useState("");
  const [desc, setDesc] = useState("");

  useEffect(() => { api.listTimeEntries(pid).then(setData).catch(() => {}); }, [pid]);

  const log = async (e: FormEvent) => {
    e.preventDefault();
    await api.logTime(pid, Number(hours), desc);
    setHours(""); setDesc("");
    api.listTimeEntries(pid).then(setData);
  };

  const fmt = (m: number) => `${Math.floor(m / 60)}h ${m % 60}m`;

  return (
    <Section title="Time Tracking">
      <div className="row" style={{ marginBottom: 12 }}>
        <span style={{ fontSize: 24, fontWeight: 700 }}>{fmt(data.total_minutes)}</span>
        <span className="muted">total logged</span>
      </div>
      {data.entries?.length > 0 && (
        <div className="commit-list" style={{ marginBottom: 12 }}>
          {data.entries.map((e: any) => (
            <div className="commit-list-row" key={e.id}>
              <span>⏱</span>
              <span className="commit-msg">{fmt(e.hours)}</span>
              <span className="muted" style={{ fontSize: 12 }}>{e.description}</span>
              <span className="commit-meta">{shortDate(e.date)}</span>
            </div>
          ))}
        </div>
      )}
      <form onSubmit={log} style={{ display: "flex", gap: 8 }}>
        <input type="number" placeholder="Minutes" value={hours} onChange={(e) => setHours(e.target.value)} required
          style={{ width: 100 }} min="1" />
        <input placeholder="What did you do?" value={desc} onChange={(e) => setDesc(e.target.value)} style={{ flex: 1 }} />
        <button className="btn sm">Log Time</button>
      </form>
    </Section>
  );
}

// ── OKRs ────────────────────────────────────────────────────────────────────
function OKRsTab({ pid }: { pid: number }) {
  const { items, loading } = useList(() => api.listOKRs(pid));
  return (
    <Section title="Objectives & Key Results">
      {loading ? <Empty text="Loading..." /> : items.length === 0 ? (
        <Empty text="No OKRs yet." />
      ) : (
        items.map((o: any) => (
          <div key={o.id} style={{ marginBottom: 16, padding: 12, border: "1px solid var(--border)", borderRadius: 6 }}>
            <div style={{ fontWeight: 700, marginBottom: 4 }}>{o.title}</div>
            <div className="muted" style={{ fontSize: 12, marginBottom: 8 }}>{o.period} · {o.progress}%</div>
            <div style={{ background: "var(--bg3)", borderRadius: 4, height: 6, marginBottom: 8 }}>
              <div style={{ background: "var(--accent)", height: "100%", borderRadius: 4, width: `${o.progress}%` }} />
            </div>
            {o.key_results?.map((kr: any) => (
              <div key={kr.id} style={{ display: "flex", gap: 8, fontSize: 13, padding: "2px 0" }}>
                <span className="muted">KR:</span>
                <span style={{ flex: 1 }}>{kr.title}</span>
                <span className="muted">{kr.current}/{kr.target} {kr.unit}</span>
              </div>
            ))}
          </div>
        ))
      )}
    </Section>
  );
}

// ── Status Page ─────────────────────────────────────────────────────────────
function StatusTab({ pid }: { pid: number }) {
  const [data, setData] = useState<any>({ components: [], incidents: [] });
  useEffect(() => { api.getStatusPage(pid).then(setData).catch(() => {}); }, [pid]);

  const statusIcon = (s: string) => s === "operational" ? "🟢" : s === "degraded" ? "🟡" : "🔴";

  return (
    <Section title="Status Page">
      <h3 style={{ fontSize: 14, marginBottom: 8 }}>Components</h3>
      {data.components?.length === 0 ? <Empty text="No components." /> : (
        <div className="commit-list" style={{ marginBottom: 16 }}>
          {data.components?.map((c: any) => (
            <div className="commit-list-row" key={c.id}>
              <span>{statusIcon(c.status)}</span>
              <span className="commit-msg">{c.name}</span>
              <span className="chip">{c.status}</span>
            </div>
          ))}
        </div>
      )}
      <h3 style={{ fontSize: 14, marginBottom: 8 }}>Active Incidents</h3>
      {data.incidents?.length === 0 ? <Empty text="No active incidents." /> : (
        <div className="commit-list">
          {data.incidents?.map((i: any) => (
            <div className="commit-list-row" key={i.id}>
              <span>🚨</span>
              <span className="commit-msg">{i.title}</span>
              <span className="chip">{i.status}</span>
              <span className="muted" style={{ fontSize: 12 }}>{i.impact}</span>
            </div>
          ))}
        </div>
      )}
    </Section>
  );
}
