import { useState } from "react";
import { Link } from "react-router-dom";
import ReviewSession from "../components/ReviewSession";

// A fixed, live public demo session (seeded at startup) — both "Open a sample
// review" CTAs point here so the promise "No account for reviewers" holds.
const SAMPLE_REVIEW_URL = "/r/demo-review-token";

const WORKFLOW_STEPS = [
  {
    n: "01",
    title: "Send a private review link",
    text: "Share the track or stems with A&R, artists or clients. No account needed for reviewers — just a link.",
  },
  {
    n: "02",
    title: "Get timestamped feedback",
    text: "Comments land at the exact moment: “01:24 — bass masks the vocal”. Reply, resolve, loop regions for stem-level notes.",
  },
  {
    n: "03",
    title: "Fix in your DAW, version it",
    text: "The comment is right there in the panel. Make the change, push v13 — the smart diff shows what moved: bass preset replaced, EQ changed, tempo untouched.",
  },
  {
    n: "04",
    title: "Approve the final master",
    text: "Status moves In review → Needs changes → Approved. One source of truth, no final_final_2.wav floating around Discord.",
  },
];

const DIFF_ROWS = [
  { kind: "bpm", label: "Tempo", before: "128", after: "128 (unchanged)" },
  { kind: "add", label: "Bass preset", before: "Vital · Old Patch", after: "Serum · Dark Bass" },
  { kind: "add", label: "EQ", before: "no change", after: "-3 dB @ 250 Hz" },
  { kind: "add", label: "Sample", before: "—", after: "+ VocalChop_01.wav" },
];

const ENGINE_PILLARS = [
  {
    icon: "🧩",
    title: "DAW parsing engine",
    text: "Reads Ableton .als, Cubase .cpr, REAPER .rpp and FL Studio .flp — tracks, devices, plugins and their settings. No opaque blobs.",
  },
  {
    icon: "📐",
    title: "Smart diff",
    text: "Between versions you see what actually moved: tempo, a bass preset replaced, EQ changed — not “binary file changed”.",
  },
  {
    icon: "🔗",
    title: "Decision ledger",
    text: "Every decision is chained with SHA-256. Rewrite one event and every hash after it breaks — verifiable history, no trust needed.",
  },
  {
    icon: "🗃",
    title: "Content-addressed storage",
    text: "Files are stored by SHA-256, so a full-snapshot version costs almost nothing when little changed — dedup by design.",
  },
  {
    icon: "📊",
    title: "Loudness analysis",
    text: "Short-term LUFS, true peak, sample rate — measured per version and per stem, so A/B compares the mix, not the volume.",
  },
  {
    icon: "🔊",
    title: "Watermarking",
    text: "An audible watermark is mixed into unapproved previews at the sample level — a leaked demo can't pass for the final file.",
  },
];

const DAW_ASSETS = [
  {
    icon: "🎚",
    title: "Tracks & plugins with settings",
    text: "Project files are parsed into structure: tracks, instruments, plugins and the actual state of each instance — REAPER PARAM lines, Ableton preset refs.",
  },
  {
    icon: "🧱",
    title: "Stems by logical name",
    text: "NeonBass_final_03.wav and bass_v13.wav both count as bass — stem-level A/B is matched by what the part is, not what it's called.",
  },
  {
    icon: "🎛",
    title: "Samples & presets",
    text: "The samples a project references and the presets it uses are listed in the tree — you can see what a version is made of.",
  },
  {
    icon: "📦",
    title: "One-command push",
    text: "`snd push` sends a whole project folder as one versioned commit with a SOUNDHUB-MANIFEST.json describing the structure.",
  },
];

const MARKET_BENEFITS = [
  { icon: "🎛", title: "Buy without leaving the session", text: "A revision needs a tighter bass? The panel suggests verified, compatible patches — buy and load in place." },
  { icon: "🔒", title: "Escrow protected", text: "Payments sit in escrow until you confirm receipt. Dispute window and refunds are part of the purchase." },
  { icon: "✅", title: "Verified before you pay", text: "DAW-parsed metadata: BPM, key, plugins, samples. What you're buying is answered before checkout." },
  { icon: "📜", title: "License bound on-chain", text: "Personal / Commercial / Sync / Exclusive tiers attached to the purchase. Rights stay legible end to end." },
];

const INTEGRATIONS = [
  { name: "Ableton Live", status: "available", detail: "`soundhub` CLI bridge — push bounces, export open requests, locator helper · Max for Live catalog panel prototype" },
  { name: "FL Studio", status: "planned", detail: "Planned — no timeline yet" },
  { name: "Cubase", status: "planned", detail: "Planned — no timeline yet" },
  { name: "REAPER", status: "planned", detail: "Planned — no timeline yet" },
];

const FAQ = [
  {
    q: "Do reviewers need an account or a wallet?",
    a: "No. Reviewers open a private link, listen, and leave timestamped comments — no signup, no wallet. The producer works in SoundHub; collaborators just review.",
    open: true,
  },
  {
    q: "How is this different from sending files over Discord or email?",
    a: "SoundHub keeps one source of truth: versions (v11 → v12 → v13), comments pinned to exact moments, statuses (In review / Needs changes / Approved) and smart diffs that show what actually changed between versions.",
    open: true,
  },
  {
    q: "What does the marketplace add?",
    a: "When a revision needs a sound, you can buy a verified, compatible asset right in the project — escrowed, with a license bound to the purchase. It's a second layer on top of the review workflow.",
    open: false,
  },
  {
    q: "Is this live on mainnet?",
    a: "Today SoundHub runs on Base Sepolia (testnet). Contracts are open-source with a full test suite; a security review is in progress before any mainnet deployment.",
    open: false,
  },
];

const ROADMAP = [
  {
    phase: "Now",
    items: [
      "Review sessions & versioning",
      "Revision rounds: consolidated feedback",
      "Loudness-matched A/B (mix & stems)",
      "Release package + QC preflight before lock",
      "Stripe paid delivery: card / Apple Pay / Google Pay",
      "Roles & approval chains for labels",
      "DAW bridge CLI: soundhub push / requests export / locator helper",
    ],
    state: "live",
  },
  {
    phase: "Already works",
    items: [
      "Stems + loop regions, matched by logical name",
      "Reference tracks: mix vs reference A/B (private, non-deliverable)",
      "Client brief + service presets + revision rules",
      "Booking deposit + paid extra rounds",
      "Watermarked previews, public engineer portfolio",
      "Private share links & access audit",
      "Release-package templates + archive/session-file handoff",
      "Change orders: quote late changes after approval",
      "Voice notes & mobile-first guest review",
      "Email reminders & deadlines",
    ],
    state: "also",
  },
  {
    phase: "Next",
    items: ["USDC checkout", "Max for Live: review comments in the DAW", "REAPER integration"],
    state: "next",
  },
  { phase: "Later", items: ["Mainnet + security audit", "Seller reputation & packs", "DAO governance"], state: "later" },
];

// --- Watch-the-workflow modal (scripted scene player) ------------------------

const SCENES = [
  { title: "Share for review", caption: "Neon Warehouse v12 → private review link to Aisha (A&R)", code: "v12 · In review" },
  { title: "Comment at 01:24", caption: "“Kick and bass clash here — let the vocal breathe.”", code: "01:24 · Aisha (A&R)" },
  { title: "Fix in the DAW", caption: "Bass preset replaced, EQ -3 dB @ 250 Hz, new version v13", code: "smart diff: bass replaced · EQ changed" },
  { title: "Approved", caption: "Client approves v13 — ready to master.", code: "v13 · Approved ✓" },
];

function WorkflowModal({ onClose }: { onClose: () => void }) {
  const [scene, setScene] = useState(0);

  const next = () => setScene((s) => (s + 1) % SCENES.length);

  return (
    <div className="wm-overlay" onClick={onClose}>
      <div className="wm" onClick={(e) => e.stopPropagation()}>
        <div className="wm-head">
          <span className="wm-title">The SoundHub workflow — 1 min</span>
          <button type="button" className="wm-close" onClick={onClose}>✕</button>
        </div>
        <div className="wm-stage">
          <div className="wm-scene-code">{SCENES[scene].code}</div>
          <div className="wm-scene-title">{SCENES[scene].title}</div>
          <div className="wm-scene-caption">{SCENES[scene].caption}</div>
        </div>
        <div className="wm-dots">
          {SCENES.map((_, i) => (
            <button
              key={i}
              type="button"
              className={`wm-dot ${i === scene ? "active" : ""}`}
              onClick={() => setScene(i)}
            />
          ))}
          <button type="button" className="wm-next" onClick={next}>Next →</button>
        </div>
      </div>
    </div>
  );
}

export default function LandingPage() {
  const [email, setEmail] = useState("");
  const [waitlist, setWaitlist] = useState<string | null>(null);
  const [showWorkflow, setShowWorkflow] = useState(false);

  const joinWaitlist = (e: React.FormEvent) => {
    e.preventDefault();
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) {
      setWaitlist("Enter a valid email to join the waitlist.");
      return;
    }
    setWaitlist(`You're on the list 🎛 We'll ping ${email} when the beta opens.`);
    setEmail("");
  };

  return (
    <div className="landing">


      {/* ---------- hero ---------- */}
      <section className="bc-hero" id="top">
        <p className="bc-eyebrow">Review · versions · approval — for music</p>
        <h1 className="bc-title">
          Music review and approvals, built for the way tracks are made.
        </h1>
        <p className="bc-sub">
          Send a private review link. Get timestamped notes. Compare versions.
          Approve the final master — no scattered ZIP archives, no Discord chaos.
        </p>
        <div className="bc-cta">
          <Link to={SAMPLE_REVIEW_URL} className="bc-btn bc-btn-primary">▶ Open a sample review</Link>
          <button type="button" className="bc-btn bc-btn-ghost" onClick={() => setShowWorkflow(true)}>
            Watch the workflow — 1 min
          </button>
        </div>
        <div className="bc-tags">
          <span>No account for reviewers</span>
          <span>WAV · MP3 · stems</span>
          <span>Loudness-matched A/B</span>
          <span>Watermarked previews</span>
          <span>Decision ledger</span>
        </div>
      </section>

      {/* ---------- featured: a live review session ---------- */}
      <section className="bc-featured" id="workflow">
        <div className="bc-featured-label">
          <span className="bc-featured-live">● Live sample</span>
          <span>— a real review session, running in your browser</span>
        </div>
        <div className="bc-featured-grid">
          <a href={SAMPLE_REVIEW_URL} className="bc-cover" title="Open the sample review">
            <div className="bc-cover-art">
              <img src="/logo.png" alt="" className="bc-cover-logo" />
            </div>
            <div className="bc-cover-meta">
              <div className="bc-cover-title">Neon Warehouse</div>
              <div className="bc-cover-sub">v13 · In review · stems included</div>
            </div>
          </a>
          <div className="bc-featured-card">
            <ReviewSession />
          </div>
        </div>
      </section>

      {/* ---------- how it works ---------- */}
      <section className="bc-section">
        <h2 className="bc-h2">How it works</h2>
        <div className="bc-steps">
          {WORKFLOW_STEPS.map((s) => (
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

      {/* ---------- smart diff ---------- */}
      <section className="bc-section" id="diff">
        <div className="bc-diff-grid">
          <div className="bc-diff-copy">
            <h2 className="bc-h2 left">Version your track like music, not bytes.</h2>
            <p>
              Between v12 and v13, GitHub would say “binary file changed”. SoundHub
              reads the project file and tells you exactly what moved — so a revision
              is a story, not a mystery.
            </p>
          </div>
          <div className="bc-diff-card">
            <div className="bc-diff-head">SoundHub smart diff — v12 → v13</div>
            {DIFF_ROWS.map((r) => (
              <div key={r.label} className={`bc-diff-row ${r.kind === "add" ? "add" : r.kind === "bpm" ? "bpm" : ""}`}>
                <span className="bc-diff-label">{r.label}</span>
                <span className="bc-diff-before">{r.before}</span>
                <span className="bc-diff-arrow">→</span>
                <span className="bc-diff-after">{r.after}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ---------- sound-tech engine backbone ---------- */}
      <section className="bc-section">
        <h2 className="bc-h2 bc-h2-tech">Sound-tech engine backbone</h2>
        <p className="bc-lead">
          Underneath the review loop sits a small engine that actually understands DAW
          projects — parsing, diffing, hashing and measuring instead of guessing.
        </p>
        <div className="bc-pillars">
          {ENGINE_PILLARS.map((p) => (
            <div key={p.title} className="bc-pillar">
              <span className="bc-pillar-icon">{p.icon}</span>
              <h3>{p.title}</h3>
              <p>{p.text}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ---------- daw-native track assets ---------- */}
      <section className="bc-section">
        <h2 className="bc-h2 bc-h2-tech">DAW-native track assets</h2>
        <p className="bc-lead">
          Versions aren't just audio files — SoundHub understands what a session is made
          of: tracks, plugins, stems and samples, straight from the DAW.
        </p>
        <div className="bc-pillars bc-pillars-2">
          {DAW_ASSETS.map((p) => (
            <div key={p.title} className="bc-pillar">
              <span className="bc-pillar-icon">{p.icon}</span>
              <h3>{p.title}</h3>
              <p>{p.text}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ---------- built-in marketplace (second layer) ---------- */}
      <section className="bc-section" id="market">
        <h2 className="bc-h2">When a revision needs a sound, buy it in place</h2>
        <p className="bc-lead">
          The review workflow comes first; the marketplace is the second layer — verified assets,
          escrowed, licensed, right where you're working.
        </p>
        <div className="bc-benefits">
          {MARKET_BENEFITS.map((t) => (
            <div key={t.title} className="bc-benefit">
              <span className="bc-benefit-icon">{t.icon}</span>
              <div>
                <h3>{t.title}</h3>
                <p>{t.text}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* ---------- integrations ---------- */}
      <section className="bc-section">
        <h2 className="bc-h2">Where you make music</h2>
        <div className="bc-int">
          {INTEGRATIONS.map((i) => (
            <div key={i.name} className="bc-int-row">
              <span className="bc-int-name">{i.name}</span>
              <span className="bc-int-detail">{i.detail}</span>
              <span className={`bc-status ${i.status}`}>{i.status}</span>
            </div>
          ))}
        </div>
      </section>

      {/* ---------- roadmap ---------- */}
      <section className="bc-section">
        <h2 className="bc-h2">Honest about where we are</h2>
        <div className="bc-roadmap">
          {ROADMAP.map((r) => (
            <div key={r.phase} className="bc-roadmap-col">
              <div className={`bc-roadmap-phase ${r.state}`}>{r.phase}</div>
              <ul>
                {r.items.map((it) => <li key={it}>{it}</li>)}
              </ul>
            </div>
          ))}
        </div>
        <p className="bc-status-note">
          Status: <strong>Private beta</strong> · testnet live · open-source contracts ·
          security review in progress · not yet audited
        </p>
      </section>

      {/* ---------- FAQ ---------- */}
      <section className="bc-section" id="faq">
        <h2 className="bc-h2">Questions, answered</h2>
        <div className="bc-faq">
          {FAQ.map((f) => (
            <details key={f.q} className="bc-faq-item" open={f.open}>
              <summary>{f.q}</summary>
              <p>{f.a}</p>
            </details>
          ))}
        </div>
      </section>

      {/* ---------- final CTA ---------- */}
      <section className="bc-cta-final">
        <h2 className="bc-h2">Stop sending final_final_2.wav.</h2>
        <p>One workspace for review, versions and approvals — marketplace included.</p>
        <form className="bc-waitlist" onSubmit={joinWaitlist}>
          <input
            type="email"
            placeholder="you@studio.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            aria-label="Email"
          />
          <button type="submit" className="bc-btn bc-btn-primary">Join the beta</button>
        </form>
        {waitlist && <div className="bc-waitlist-msg">{waitlist}</div>}
        <div className="bc-cta-final-alts">
          <Link to={SAMPLE_REVIEW_URL}>or open a sample review now →</Link>
        </div>
      </section>

      {/* ---------- footer ---------- */}
      <footer className="bc-footer">
        <div className="bc-footer-grid">
          <div className="bc-footer-brand">
            <img src="/logo.png" alt="SoundHub" className="bc-logo" />
            <p>Review, versions and approvals for music — marketplace built in.</p>
          </div>
          <div className="bc-footer-col">
            <h4>Product</h4>
            <a href="#workflow">Workflow</a>
            <a href="#diff">Smart diff</a>
            <a href="#market">Marketplace</a>
            <a href="#faq">FAQ</a>
          </div>
          <div className="bc-footer-col">
            <h4>DAWs</h4>
            <a href="#workflow">Ableton Live · available</a>
            <a href="#workflow">FL Studio · planned</a>
            <a href="#workflow">Cubase · planned</a>
            <a href="#workflow">REAPER · planned</a>
          </div>
          <div className="bc-footer-col">
            <h4>Ecosystem</h4>
            <Link to={SAMPLE_REVIEW_URL}>Open a sample review</Link>
            <Link to="/market">Marketplace</Link>
            <Link to="/kettle">Kettle for beginners</Link>
          </div>
        </div>
        <p className="bc-footer-bottom">
          Private beta on Base Sepolia · open-source contracts · © {new Date().getFullYear()} SoundHub
        </p>
      </footer>

      {showWorkflow && <WorkflowModal onClose={() => setShowWorkflow(false)} />}
    </div>
  );
}
