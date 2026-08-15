import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import ReviewSession from "../components/ReviewSession";

const NAV_LINKS = [
  { href: "#workflow", label: "Workflow" },
  { href: "#diff", label: "Smart diff" },
  { href: "#market", label: "Marketplace" },
  { href: "#pricing", label: "Licenses" },
  { href: "#faq", label: "FAQ" },
];

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

const MARKET_BENEFITS = [
  { icon: "🎛", title: "Buy without leaving the session", text: "A revision needs a tighter bass? The panel suggests verified, compatible patches — buy and load in place." },
  { icon: "🔒", title: "Escrow protected", text: "Payments sit in escrow until you confirm receipt. Dispute window and refunds are part of the purchase." },
  { icon: "✅", title: "Verified before you pay", text: "DAW-parsed metadata: BPM, key, plugins, samples. What you're buying is answered before checkout." },
  { icon: "📜", title: "License bound on-chain", text: "Personal / Commercial / Sync / Exclusive tiers attached to the purchase. Rights stay legible end to end." },
];

const INTEGRATIONS = [
  { name: "Ableton Live", status: "panel live", detail: "Max for Live — review comments, catalog & buy & load in the DAW", when: "now" },
  { name: "FL Studio", status: "prototype", detail: "MIDI scripting device + file bridge", when: "beta 2026" },
  { name: "Cubase", status: "prototype", detail: "MIDI Remote script + web panel", when: "beta 2026" },
  { name: "REAPER", status: "planned", detail: "ReaScript — file & HTTP access", when: "Q4 2026" },
];

const LICENSES = [
  { name: "Personal", price: "1×", note: "one track, one producer", features: ["single non-commercial track", "credit the creator", "no resale, no remix distribution"], featured: false },
  { name: "Commercial", price: "5×", note: "the default for releases", features: ["commercial releases & streaming", "YouTube / TikTok / Spotify OK", "no resale of the preset itself"], featured: true },
  { name: "Sync", price: "10×", note: "for film, ads & games", features: ["everything in Commercial", "sync placements (film/TV/ads)", "negotiable exclusivity per placement"], featured: false },
  { name: "Exclusive", price: "custom", note: "take it off the market", features: ["asset leaves the catalog", "full ownership of the sound", "one-to-one deal, escrowed"], featured: false },
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
  { phase: "Now", items: ["Review sessions: versions & approvals", "Timestamped comments & replies", "Private share links", "Private beta on Base Sepolia"], state: "live" },
  { phase: "Next", items: ["A/B version compare", "Stems & loop regions", "Ableton integration for comments", "Card / USDC checkout"], state: "next" },
  { phase: "Later", items: ["REAPER integration", "Mainnet + security audit", "Seller reputation & packs", "DAO governance"], state: "later" },
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

  useEffect(() => {
    const t = setInterval(() => setScene((s) => (s + 1) % SCENES.length), 2600);
    return () => clearInterval(t);
  }, []);

  return (
    <div className="wm-overlay" onClick={onClose}>
      <div className="wm" onClick={(e) => e.stopPropagation()}>
        <div className="wm-head">
          <span className="wm-title">🎬 The SoundHub workflow — 1 min</span>
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
        </div>
      </div>
    </div>
  );
}

function Reveal({ children }: { children: React.ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const io = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          if (e.isIntersecting) e.target.classList.add("revealed");
        }
      },
      { threshold: 0.12 }
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);
  return (
    <div ref={ref} className="reveal">
      {children}
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
      {/* ---------- sticky nav ---------- */}
      <nav className="landing-nav">
        <a href="#top" className="landing-nav-brand">
          <img src="/logo.png" alt="SoundHub" className="landing-nav-logo" /> SoundHub
        </a>
        <div className="landing-nav-links">
          {NAV_LINKS.map((l) => (
            <a key={l.href} href={l.href}>{l.label}</a>
          ))}
        </div>
        <div className="landing-nav-cta">
          <Link to="/login">Sign in</Link>
          <Link to="/login" className="landing-nav-get">Try demo project</Link>
        </div>
      </nav>

      {/* ---------- hero ---------- */}
      <section className="landing-hero" id="top">
        <div className="landing-hero-inner">
          <p className="landing-eyebrow">🎛 For producers, artists & A&R</p>
          <h1 className="landing-title">
            Music review and approvals,
            <br />
            built for the way <span className="landing-title-accent">tracks are made</span>.
          </h1>
          <p className="landing-subtitle">
            Send a private review link. Get timestamped notes. Compare versions.
            Approve the final master — no bounced files, no ZIP archives, no Discord chaos.
          </p>
          <div className="landing-cta">
            <button type="button" className="landing-btn-primary" onClick={() => setShowWorkflow(true)}>
              ▶ Watch the workflow
            </button>
            <Link to="/session" className="landing-btn-ghost">
              Try a demo session
            </Link>
          </div>
          <div className="landing-proof">
            <span>No account for reviewers</span>
            <span>WAV, MP3 &amp; stems</span>
            <span>Ableton integration</span>
          </div>
        </div>

        {/* live review session — the center of the page */}
        <div className="landing-shot" id="workflow">
          <ReviewSession />
        </div>
      </section>

      {/* ---------- workflow loop ---------- */}
      <section className="landing-section landing-workflow">
        <Reveal>
          <p className="landing-eyebrow center">The loop</p>
          <h2 className="landing-h2">From session to approved master</h2>
          <div className="landing-steps-grid">
            {WORKFLOW_STEPS.map((s) => (
              <div key={s.n} className="landing-step">
                <span className="landing-step-n">{s.n}</span>
                <h3>{s.title}</h3>
                <p>{s.text}</p>
              </div>
            ))}
          </div>
        </Reveal>
      </section>

      {/* ---------- smart diff ---------- */}
      <section className="landing-section landing-diff" id="diff">
        <Reveal>
          <div className="landing-diff-grid">
            <div className="landing-diff-copy">
              <p className="landing-eyebrow">Smart diff</p>
              <h2>Version your track like music, not bytes.</h2>
              <p>
                Between v12 and v13, GitHub would say “binary file changed”. SoundHub
                reads the project file and tells you exactly what moved — so a revision
                is a story, not a mystery.
              </p>
            </div>
            <div className="landing-diff-card">
              <div className="landing-diff-head">SoundHub smart diff — v12 → v13</div>
              {DIFF_ROWS.map((r) => (
                <div key={r.label} className={`landing-diff-row ${r.kind === "add" ? "add" : r.kind === "bpm" ? "bpm" : ""}`}>
                  <span className="landing-diff-label">{r.label}</span>
                  <span className="landing-diff-before">{r.before}</span>
                  <span className="landing-diff-arrow">→</span>
                  <span className="landing-diff-after">{r.after}</span>
                </div>
              ))}
            </div>
          </div>
        </Reveal>
      </section>

      {/* ---------- built-in marketplace (second layer) ---------- */}
      <section className="landing-section" id="market">
        <Reveal>
          <p className="landing-eyebrow center">Built-in marketplace</p>
          <h2 className="landing-h2">When a revision needs a sound, buy it in place</h2>
          <p className="landing-pricing-sub">
            The review workflow comes first; the marketplace is the second layer — verified assets,
            escrowed, licensed, right where you're working.
          </p>
          <div className="landing-trust">
            {MARKET_BENEFITS.map((t) => (
              <div key={t.title} className="landing-feature">
                <div className="landing-feature-icon">{t.icon}</div>
                <h3>{t.title}</h3>
                <p>{t.text}</p>
              </div>
            ))}
          </div>
        </Reveal>
      </section>

      {/* ---------- integrations ---------- */}
      <section className="landing-section">
        <Reveal>
          <p className="landing-eyebrow center">Integrations</p>
          <h2 className="landing-h2">Where you make music</h2>
          <div className="landing-integrations">
            {INTEGRATIONS.map((i) => (
              <div key={i.name} className="landing-integration">
                <div className="landing-integration-head">
                  <span className="landing-integration-name">{i.name}</span>
                  <span className={`landing-status ${i.status.replace(/\s+/g, "-")}`}>{i.status}</span>
                </div>
                <p>{i.detail}</p>
                <span className="landing-integration-when">{i.when}</span>
              </div>
            ))}
          </div>
        </Reveal>
      </section>

      {/* ---------- roadmap ---------- */}
      <section className="landing-section">
        <Reveal>
          <p className="landing-eyebrow center">Roadmap</p>
          <h2 className="landing-h2">Honest about where we are</h2>
          <div className="landing-roadmap">
            {ROADMAP.map((r) => (
              <div key={r.phase} className="landing-roadmap-col">
                <div className={`landing-roadmap-phase ${r.state}`}>{r.phase}</div>
                <ul>
                  {r.items.map((it) => <li key={it}>{it}</li>)}
                </ul>
              </div>
            ))}
          </div>
          <p className="landing-status-note">
            Status: <strong>Private beta</strong> · testnet live · open-source contracts ·
            security review in progress · not yet audited
          </p>
        </Reveal>
      </section>

      {/* ---------- licenses ---------- */}
      <section className="landing-section" id="pricing">
        <Reveal>
          <p className="landing-eyebrow center">Licenses</p>
          <h2 className="landing-h2">One purchase. Four license tiers.</h2>
          <p className="landing-pricing-sub">
            The tier is bound to the purchase on-chain — rights stay legible from checkout to the credits.
          </p>
          <div className="landing-licenses">
            {LICENSES.map((l) => (
              <div key={l.name} className={`landing-license ${l.featured ? "featured" : ""}`}>
                {l.featured && <div className="landing-license-tag">Most popular</div>}
                <h3>{l.name}</h3>
                <div className="landing-license-price">{l.price}</div>
                <div className="landing-license-note">{l.note}</div>
                <ul>
                  {l.features.map((f) => <li key={f}>{f}</li>)}
                </ul>
              </div>
            ))}
          </div>
          <table className="landing-license-table">
            <thead>
              <tr>
                <th>Use case</th><th>Personal</th><th>Commercial</th><th>Sync</th><th>Exclusive</th>
              </tr>
            </thead>
            <tbody>
              <tr><td>Non-commercial track</td><td>✓</td><td>✓</td><td>✓</td><td>✓</td></tr>
              <tr><td>Commercial release &amp; streaming</td><td>—</td><td>✓</td><td>✓</td><td>✓</td></tr>
              <tr><td>YouTube / TikTok / Spotify</td><td>—</td><td>✓</td><td>✓</td><td>✓</td></tr>
              <tr><td>Film / TV / ad placements (sync)</td><td>—</td><td>—</td><td>✓</td><td>✓</td></tr>
              <tr><td>Pass project to a client</td><td>—</td><td>✓</td><td>✓</td><td>✓</td></tr>
              <tr><td>Resell the sound itself</td><td>—</td><td>—</td><td>—</td><td>✓</td></tr>
            </tbody>
          </table>
          <p className="landing-license-note small">
            Not legal advice — full terms live in each asset's license agreement. Disputes are
            resolved in escrow; refunds follow the license's refund rules.
          </p>
        </Reveal>
      </section>

      {/* ---------- FAQ ---------- */}
      <section className="landing-section landing-faq" id="faq">
        <Reveal>
          <p className="landing-eyebrow center">FAQ</p>
          <h2 className="landing-h2">Questions, answered</h2>
          <div className="landing-faq-list">
            {FAQ.map((f) => (
              <details key={f.q} className="landing-faq-item" open={f.open}>
                <summary>{f.q}</summary>
                <p>{f.a}</p>
              </details>
            ))}
          </div>
        </Reveal>
      </section>

      {/* ---------- final CTA ---------- */}
      <section className="landing-cta-final" id="waitlist">
        <Reveal>
          <h2 className="landing-h2">Stop sending final_final_2.wav.</h2>
          <p>One workspace for review, versions and approvals — marketplace included.</p>
          <form className="landing-waitlist" onSubmit={joinWaitlist}>
            <input
              type="email"
              placeholder="you@studio.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              aria-label="Email"
            />
            <button type="submit" className="landing-btn-primary">Join the beta</button>
          </form>
          {waitlist && <div className="landing-waitlist-msg">{waitlist}</div>}
          <div className="landing-cta-final-alts">
            <Link to="/session">or try the demo session now →</Link>
          </div>
        </Reveal>
      </section>

      {/* ---------- footer ---------- */}
      <footer className="landing-footer">
        <div className="landing-footer-grid">
          <div className="landing-footer-brand">
            <img src="/logo.png" alt="SoundHub" className="landing-nav-logo" /> SoundHub
            <p className="landing-footer-tag">Review, versions and approvals for music — marketplace built in.</p>
          </div>
          <div className="landing-footer-col">
            <h4>Product</h4>
            <a href="#workflow">Workflow</a>
            <a href="#diff">Smart diff</a>
            <a href="#market">Marketplace</a>
            <a href="#waitlist">Beta</a>
          </div>
          <div className="landing-footer-col">
            <h4>DAWs</h4>
            <a href="#workflow">Ableton Live</a>
            <a href="#workflow">FL Studio</a>
            <a href="#workflow">Cubase</a>
            <a href="#workflow">REAPER · Q4 2026</a>
          </div>
          <div className="landing-footer-col">
            <h4>Ecosystem</h4>
            <Link to="/session">Demo session</Link>
            <Link to="/market">Marketplace</Link>
            <Link to="/dao">Community</Link>
          </div>
        </div>
        <p className="landing-footer-bottom muted">
          Private beta on Base Sepolia · open-source contracts · © {new Date().getFullYear()} SoundHub
        </p>
      </footer>

      {showWorkflow && <WorkflowModal onClose={() => setShowWorkflow(false)} />}
    </div>
  );
}
