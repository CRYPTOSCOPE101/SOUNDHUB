import { Link } from "react-router-dom";

/* Docs — the user-facing documentation hub. Covers the core loop, the DAW
   bridge (snd push / snd serve), review sessions, team roles and honest
   limits, and links out to the full project documents. */

const CORE_LOOP = [
  {
    n: "1",
    title: "Create — in any DAW",
    text: "You work in Ableton Live, FL Studio, Cubase or REAPER. SoundHub reads all four project formats (.als, .cpr, .rpp, .flp) so a version isn't a black box.",
  },
  {
    n: "2",
    title: "Push or upload a version",
    text: "From the terminal: `snd push Track_v12.als`. From the web: upload the audio directly. Either way the DAW metadata — BPM, tracks, plugins — is parsed and stored with the commit.",
  },
  {
    n: "3",
    title: "Share the private review link",
    text: "You get a link like soundhub.app/r/abc123. The client or collaborator opens it without an account and leaves timestamped notes. No signup, no wallet, no app to install.",
  },
  {
    n: "4",
    title: "Fix, push v2, A/B",
    text: "Make the change, push the next version, and A/B the two from the same playhead — loudness-matched, so louder isn't confused with better. Guests see a smart diff: what actually changed (BPM 128 → 132, +Pad, +Vital), not “binary file changed”.",
  },
  {
    n: "5",
    title: "Approve and deliver",
    text: "The version gets Approved, you lock the release package with checksums, and the client gets a delivery link with the real files. The decision ledger records every step.",
  },
];

const BRIDGE = [
  { cmd: "snd push Track_v12.als", desc: "Fast push — project + parsed DAW metadata as one versioned commit." },
  { cmd: "snd push Track_v12.als --audio master.wav --stems stems/", desc: "Full review push — opens a public review session with gapless A/B and structured stems." },
  { cmd: "snd push Track_v12.als --project artist-track --branch review/v12 --round 3", desc: "Target a project/branch/round — branch is auto-created on first push." },
  { cmd: "snd serve", desc: "Local JSON bridge on :8765 for the Max for Live push button and automation." },
  { cmd: "snd login --user demo --password demo123", desc: "Save the API URL + token once; needed before any push." },
];

const ROLES = [
  { role: "Engineer", does: "Runs the session, pushes versions, replies to feedback, locks the release package." },
  { role: "Artist", does: "Approve the mix; with the label workflow, gates the master." },
  { role: "A&R", does: "Approves the master in a label workflow — a random email gets a 403, the invited A&R gets a 201." },
  { role: "Feedback owner", does: "Collects everyone's draft notes and submits one consolidated list per round." },
  { role: "Client", does: "Opens the review link, leaves notes, approves, downloads the delivery." },
];

const LIMITS = [
  "Smart contracts are not professionally audited yet — testnet only.",
  "DAW files are reverse-engineered formats; parser coverage is best-effort (.flp reads header/tempo/channels for now).",
  "Gapless A/B needs at least two versions — the first --audio push opens the session.",
  "The M4L device needs `snd serve` running locally (Live blocks shell; the sidecar is planned).",
];

const DOCUMENTS = [
  { name: "Whitepaper (PDF)", desc: "18-page technical deep dive — architecture, formulas, tokenomics, governance.", href: "/Whitepaper.pdf", external: true },
  { name: "Litepaper", desc: "The product in one page: problem, solution, layers, roadmap.", href: "https://github.com/CRYPTOSCOPE101/SoundHub/blob/snd-project-push/LITEPAPER.md", external: true },
  { name: "README", desc: "Quick start, API overview, DAW engine, releases.", href: "https://github.com/CRYPTOSCOPE101/SoundHub/blob/snd-project-push/README.md", external: true },
  { name: "Architecture", desc: "How the Max for Live layer, backend and settlement fit together.", href: "https://github.com/CRYPTOSCOPE101/SoundHub/blob/snd-project-push/ARCHITECTURE.md", external: true },
  { name: "Changelog", desc: "Release notes — what changed, how to test, known limits, release checklist.", href: "https://github.com/CRYPTOSCOPE101/SoundHub/blob/snd-project-push/CHANGELOG.md", external: true },
  { name: "Max for Live device", desc: "Install, bridge contract, push button states, troubleshooting.", href: "https://github.com/CRYPTOSCOPE101/SoundHub/blob/snd-project-push/m4l/README.md", external: true },
];

export default function DocsPage() {
  return (
    <div className="landing docs-page">

      <section className="docs-hero" id="top">
        <p className="bc-eyebrow">📚 SoundHub documentation</p>
        <h1 className="bc-title">
          From DAW to approval,
          <br />
          documented end to end.
        </h1>
        <p className="bc-sub">
          How the review loop works, how to push a project from your DAW, who can
          approve what, and what the current limits are — plus links to the full
          whitepaper and changelog.
        </p>
        <div className="bc-cta">
          <a href="#loop" className="bc-btn bc-btn-primary">The core loop</a>
          <a href="#documents" className="bc-btn bc-btn-ghost">All documents</a>
        </div>
      </section>

      <section className="bc-section" id="loop">
        <p className="bc-eyebrow center" style={{ display: "block", marginBottom: 14 }}>How it works</p>
        <h2 className="bc-h2">The core loop in 5 steps</h2>
        <div className="bc-steps">
          {CORE_LOOP.map((s) => (
            <div key={s.n} className="bc-step">
              <span className="bc-step-n">{s.n}</span>
              <div className="bc-step-body">
                <h3>{s.title}</h3>
                <p>{s.text}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="bc-section" id="bridge">
        <p className="bc-eyebrow center" style={{ display: "block", marginBottom: 14 }}>DAW bridge</p>
        <h2 className="bc-h2">`snd` — push a project from the terminal</h2>
        <p className="docs-lead">
          `snd` is a small CLI that turns a DAW project into a versioned commit —
          and with a master render, into a public review session with gapless A/B.
          The same pipeline powers the Max for Live push button through the
          localhost bridge (`snd serve`).
        </p>
        <div className="docs-cmd-list">
          {BRIDGE.map((c) => (
            <div key={c.cmd} className="docs-cmd-row">
              <code>{c.cmd}</code>
              <span>{c.desc}</span>
            </div>
          ))}
        </div>
        <p className="docs-note">
          Push is atomic (no half-pushed versions), preflighted (corrupt files are
          rejected), and idempotent — re-pushing the same export creates no new
          blobs. See the README for the full bridge contract, error codes and smoke
          commands.
        </p>
      </section>

      <section className="bc-section" id="roles">
        <p className="bc-eyebrow center" style={{ display: "block", marginBottom: 14 }}>Team roles</p>
        <h2 className="bc-h2">Who can approve what</h2>
        <div className="docs-table-wrap">
          <table className="docs-table">
            <thead>
              <tr>
                <th>Role</th>
                <th>What they do</th>
              </tr>
            </thead>
            <tbody>
              {ROLES.map((r) => (
                <tr key={r.role}>
                  <td><strong>{r.role}</strong></td>
                  <td>{r.does}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="docs-note">
          Workflows are configurable per session (solo client, artist team, label
          workflow, post-production). The approval chain is enforced server-side:
          approving outside your role returns 403.
        </p>
      </section>

      <section className="bc-section" id="limits">
        <p className="bc-eyebrow center" style={{ display: "block", marginBottom: 14 }}>Honest limits</p>
        <h2 className="bc-h2">What is not done yet</h2>
        <ul className="docs-limits">
          {LIMITS.map((l) => (
            <li key={l}>{l}</li>
          ))}
        </ul>
      </section>

      <section className="bc-section" id="documents">
        <p className="bc-eyebrow center" style={{ display: "block", marginBottom: 14 }}>Reference</p>
        <h2 className="bc-h2">All documents</h2>
        <div className="docs-grid">
          {DOCUMENTS.map((d) => (
            <a
              key={d.name}
              href={d.href}
              className="docs-card"
              {...(d.external ? { target: "_blank", rel: "noopener noreferrer" } : {})}
            >
              <strong>{d.name}</strong>
              <span>{d.desc}</span>
            </a>
          ))}
        </div>
      </section>

      <section className="bc-section" style={{ textAlign: "center" }}>
        <Link to="/" className="bc-btn bc-btn-ghost">← Back to SoundHub</Link>
      </section>

    </div>
  );
}
