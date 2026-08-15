import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";

const NAV_LINKS = [
  { href: "#demo", label: "Demo" },
  { href: "#diff", label: "Smart diff" },
  { href: "#trust", label: "Trust" },
  { href: "#pricing", label: "Licenses" },
  { href: "#faq", label: "FAQ" },
];

// ---------------------------------------------------------------------------
// Interactive product demo — Project Context Marketplace
// ---------------------------------------------------------------------------

const PROJECT_PLUGINS = ["Serum", "Vital", "FabFilter"];

const ASSETS = [
  { name: "Dark Bass Patch", plugin: "Serum", bpm: 128, key: "F minor", price: 50, license: "Commercial" },
  { name: "Warehouse Stab", plugin: "Vital", bpm: 128, key: "F minor", price: 35, license: "Commercial" },
  { name: "Subby Reese", plugin: "Serum", bpm: 126, key: "E minor", price: 45, license: "Sync" },
  { name: "Airy Pad Stack", plugin: "Vital", bpm: 132, key: "F minor", price: 40, license: "Commercial" },
  { name: "Driving Hats Loop", plugin: "none", bpm: 128, key: "any", price: 15, license: "Personal" },
];

function scoreAsset(a: (typeof ASSETS)[number], bpm: number): number {
  let s = 100 - Math.abs(a.bpm - bpm) * 3;
  if (a.key === "F minor") s += 12;
  if (a.key === "any") s += 6;
  if (PROJECT_PLUGINS.includes(a.plugin)) s += 10;
  return Math.min(99, Math.round(s));
}

function DemoPanel() {
  const [bpm, setBpm] = useState(128);
  const [playing, setPlaying] = useState<string | null>(null);
  const [loaded, setLoaded] = useState<Record<string, boolean>>({});
  const [flash, setFlash] = useState<string | null>(null);

  const ranked = useMemo(() => {
    return [...ASSETS]
      .map((a) => ({ ...a, match: scoreAsset(a, bpm) }))
      .sort((a, b) => b.match - a.match);
  }, [bpm]);

  const matchCount = ranked.filter((a) => a.match >= 55).length;

  const buyLoad = (name: string) => {
    setLoaded((l) => ({ ...l, [name]: true }));
    setFlash(name);
    setTimeout(() => setFlash(null), 1200);
  };

  return (
    <div className="demo">
      {/* project context header */}
      <div className="demo-project">
        <div className="demo-project-title">
          <span className="demo-project-icon">🎚</span>
          <div>
            <div className="demo-project-name">Neon Warehouse v12</div>
            <div className="demo-project-meta">
              {bpm} BPM · F minor · Techno · Ableton 12
            </div>
          </div>
        </div>
        <div className="demo-plugins">
          {PROJECT_PLUGINS.map((p) => (
            <span key={p} className="demo-chip">{p}</span>
          ))}
        </div>
      </div>

      {/* BPM selector — live re-ranking */}
      <div className="demo-bpm-row">
        <span className="demo-label">Project BPM</span>
        <div className="demo-bpm-buttons">
          {[124, 126, 128, 130, 132].map((b) => (
            <button
              key={b}
              type="button"
              className={`demo-bpm-btn ${b === bpm ? "active" : ""}`}
              onClick={() => setBpm(b)}
            >
              {b}
            </button>
          ))}
        </div>
        <span className="demo-count">{matchCount} matching sounds</span>
      </div>

      {/* recommended list */}
      <div className="demo-list">
        {ranked.slice(0, 4).map((a, i) => (
          <div key={a.name} className={`demo-item ${i === 0 ? "top" : ""}`}>
            <div className="demo-item-main">
              <button
                type="button"
                className={`demo-play ${playing === a.name ? "on" : ""}`}
                onClick={() => setPlaying(playing === a.name ? null : a.name)}
                title="Preview in mix"
              >
                {playing === a.name ? "❚❚" : "▶"}
              </button>
              <div className="demo-item-info">
                <div className="demo-item-name">{a.name}</div>
                <div className="demo-item-meta">
                  {a.bpm} BPM · {a.key} · {a.plugin !== "none" ? `${a.plugin} compatible` : "no plugins needed"}
                </div>
              </div>
              <div className="demo-match">{a.match}% match</div>
              <div className="demo-price">{a.price} SND</div>
            </div>
            {i === 0 && (
              <div className="demo-reasons">
                <span>✓ same tempo</span>
                <span>✓ same key</span>
                <span>✓ {a.plugin !== "none" ? "uses installed plugin" : "no plugins needed"}</span>
                <span>✓ matches your bass bus</span>
              </div>
            )}
            <div className="demo-actions">
              <button type="button" className="demo-btn ghost">Preview in mix</button>
              <button
                type="button"
                className={`demo-btn ${loaded[a.name] ? "loaded" : ""}`}
                onClick={() => buyLoad(a.name)}
              >
                {loaded[a.name] ? "✓ Loaded to project" : "Buy & Load"}
              </button>
            </div>
          </div>
        ))}
      </div>

      {flash && (
        <div className="demo-flash">
          ✓ <strong>{flash}</strong> escrowed and loaded to your project
        </div>
      )}

      <div className="demo-foot">
        escrow protected · verified metadata · license bound on-chain · auto-payout to creator
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Static content
// ---------------------------------------------------------------------------

const DIFF_ROWS = [
  { kind: "bpm", label: "Tempo", before: "128", after: "132" },
  { kind: "add", label: "Track", before: "—", after: "+ Pad (midi)" },
  { kind: "add", label: "Plugin", before: "—", after: "+ Vital" },
  { kind: "add", label: "Sample", before: "—", after: "+ VocalChop_01.wav" },
];

const TRUST = [
  { icon: "👂", title: "Preview before you buy", text: "Hear the asset in your own mix — dry/wet, against your current sound. No buying blind." },
  { icon: "✅", title: "Verified metadata", text: "DAW-parsed contents: BPM, key, plugins, samples. “What am I buying?” is answered before checkout." },
  { icon: "🔒", title: "Escrow protected", text: "Your SND sits in escrow until you confirm receipt. Dispute window, refunds, no trust-me selling." },
  { icon: "🎧", title: "Compatible with your setup", text: "Plugin compatibility report before purchase, with audio stems as a fallback when a VST is missing." },
];

const INTEGRATIONS = [
  { name: "Ableton Live", status: "panel live", detail: "Max for Live device — catalog, suggest, buy & load", when: "now" },
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
    q: "Do I need a wallet to use SoundHub?",
    a: "No. Browsing, previews and recommendations are free and need no wallet. Buying works with an EVM wallet today; card / USDC / email checkout is on the roadmap so crypto stays invisible.",
    open: true,
  },
  {
    q: "What does “escrow” actually mean?",
    a: "Your SND sits in the SoundHubMarket contract until you confirm receipt — or the 2-day dispute window passes. If the asset isn't right, you can request a refund. Sellers get paid automatically when you confirm.",
    open: true,
  },
  {
    q: "Will the preset work in my project?",
    a: "SoundHub verifies the contents with the DAW engine and shows a plugin compatibility report before purchase. If you're missing a VST, audio stems or a rendered preview are the fallback.",
    open: false,
  },
  {
    q: "Is this live on mainnet?",
    a: "Today SoundHub runs on Base Sepolia (testnet) with a faucet. Contracts are open-source with a full test suite; a security review is in progress before any mainnet deployment.",
    open: false,
  },
];

const ROADMAP = [
  { phase: "Now", items: ["Product demo & previews", "Private beta on Base Sepolia", "FL Studio & Cubase prototypes"], state: "live" },
  { phase: "Next", items: ["Card / USDC checkout", "Collaboration: comments & approvals", "Plugin compatibility reports"], state: "next" },
  { phase: "Later", items: ["REAPER integration", "Mainnet + security audit", "Seller reputation & packs"], state: "later" },
];

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
      {/* ---------- sticky landing nav ---------- */}
      <nav className="landing-nav">
        <a href="#top" className="landing-nav-brand">
          <img src="/logo.png" alt="SoundHub" className="landing-nav-logo" /> SoundHub
        </a>
        <div className="landing-nav-links">
          {NAV_LINKS.map((l) => (
            <a key={l.href} href={l.href}>
              {l.label}
            </a>
          ))}
        </div>
        <div className="landing-nav-cta">
          <Link to="/login">Sign in</Link>
          <Link to="/login" className="landing-nav-get">
            Try demo project
          </Link>
        </div>
      </nav>

      {/* ---------- hero ---------- */}
      <section className="landing-hero" id="top">
        <div className="landing-hero-inner">
          <p className="landing-eyebrow">🎛 SoundHub — for music producers</p>
          <h1 className="landing-title">
            Finish tracks faster,
            <br />
            with sounds that <span className="landing-title-accent">fit your project</span>.
          </h1>
          <p className="landing-subtitle">
            SoundHub reads your DAW project, finds compatible assets, and lets you buy
            and load them without leaving your session.
          </p>
          <div className="landing-cta">
            <Link to="/login" className="landing-btn-primary">
              Try demo project
            </Link>
            <a href="#demo" className="landing-btn-ghost">
              See the panel live ↓
            </a>
          </div>
          <div className="landing-proof">
            <span>✓ DAW-verified contents</span>
            <span>✓ escrow protected</span>
            <span>✓ license clear before you pay</span>
          </div>
        </div>

        {/* interactive product demo */}
        <div className="landing-shot" id="demo">
          <div className="landing-shot-bar">
            <span className="dot" />
            <span className="dot" />
            <span className="dot" />
            <span className="landing-shot-url">soundhub — project context marketplace</span>
          </div>
          <DemoPanel />
        </div>
      </section>

      {/* ---------- one-liner strip ---------- */}
      <section className="landing-logos">
        <p>Use AI for ideas. Use verified sound for the final take.</p>
        <div className="landing-logos-row">
          <span>.als</span>
          <span>.flp</span>
          <span>.cpr</span>
          <span>.rpp</span>
          <span>·</span>
          <span>SND</span>
          <span>Base Sepolia</span>
        </div>
      </section>

      {/* ---------- smart diff ---------- */}
      <section className="landing-section landing-diff" id="diff">
        <Reveal>
          <div className="landing-diff-grid">
            <div className="landing-diff-copy">
              <p className="landing-eyebrow">Smart diff</p>
              <h2>Version your track like music, not bytes.</h2>
              <p>
                GitHub says “binary file changed”. SoundHub reads the project file and
                shows what actually changed — tempo, tracks, plugins, samples — so you
                can collaborate without zip-files floating around a Discord server.
              </p>
            </div>
            <div className="landing-diff-card">
              <div className="landing-diff-head">SoundHub smart diff — track_v3.als</div>
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

      {/* ---------- trust ---------- */}
      <section className="landing-section" id="trust">
        <Reveal>
          <p className="landing-eyebrow center">Trust</p>
          <h2 className="landing-h2">Buying sound shouldn't be a leap of faith</h2>
          <div className="landing-trust">
            {TRUST.map((t) => (
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
                  {r.items.map((it) => (
                    <li key={it}>{it}</li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
          <p className="landing-status-note">
            Status: <strong>Private beta</strong> · testnet live on Base Sepolia ·
            open-source contracts · security review in progress · not yet audited
          </p>
        </Reveal>
      </section>

      {/* ---------- licenses (pricing) ---------- */}
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
                  {l.features.map((f) => (
                    <li key={f}>{f}</li>
                  ))}
                </ul>
              </div>
            ))}
          </div>

          <table className="landing-license-table">
            <thead>
              <tr>
                <th>Use case</th>
                <th>Personal</th>
                <th>Commercial</th>
                <th>Sync</th>
                <th>Exclusive</th>
              </tr>
            </thead>
            <tbody>
              <tr><td>Non-commercial track</td><td>✓</td><td>✓</td><td>✓</td><td>✓</td></tr>
              <tr><td>Commercial release & streaming</td><td>—</td><td>✓</td><td>✓</td><td>✓</td></tr>
              <tr><td>YouTube / TikTok / Spotify</td><td>—</td><td>✓</td><td>✓</td><td>✓</td></tr>
              <tr><td>Film / TV / ad placements (sync)</td><td>—</td><td>—</td><td>✓</td><td>✓</td></tr>
              <tr><td>Pass project to a client</td><td>—</td><td>✓</td><td>✓</td><td>✓</td></tr>
              <tr><td>Resell the sound itself</td><td>—</td><td>—</td><td>—</td><td>✓</td></tr>
            </tbody>
          </table>
          <p className="landing-license-note small">
            Not legal advice — full terms live in each asset's license agreement. Disputes
            are resolved in escrow; refunds follow the license's refund rules.
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

      {/* ---------- final CTA + waitlist ---------- */}
      <section className="landing-cta-final" id="waitlist">
        <Reveal>
          <h2 className="landing-h2">Stop hunting for the right sound.</h2>
          <p>Don't generate. Buy. — verified sounds that fit your project, in your DAW.</p>
          <form className="landing-waitlist" onSubmit={joinWaitlist}>
            <input
              type="email"
              placeholder="you@studio.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              aria-label="Email"
            />
            <button type="submit" className="landing-btn-primary">
              Join the beta
            </button>
          </form>
          {waitlist && <div className="landing-waitlist-msg">{waitlist}</div>}
          <div className="landing-cta-final-alts">
            <Link to="/login">or try the demo project now →</Link>
          </div>
        </Reveal>
      </section>

      {/* ---------- footer ---------- */}
      <footer className="landing-footer">
        <div className="landing-footer-grid">
          <div className="landing-footer-brand">
            <img src="/logo.png" alt="SoundHub" className="landing-nav-logo" /> SoundHub
            <p className="landing-footer-tag">Don't generate. Buy. — verified sounds that fit your project.</p>
          </div>
          <div className="landing-footer-col">
            <h4>Product</h4>
            <a href="#demo">Demo</a>
            <a href="#diff">Smart diff</a>
            <a href="#pricing">Licenses</a>
            <a href="#waitlist">Beta</a>
          </div>
          <div className="landing-footer-col">
            <h4>DAWs</h4>
            <a href="#trust">Ableton Live</a>
            <a href="#trust">FL Studio</a>
            <a href="#trust">Cubase</a>
            <a href="#trust">REAPER · Q4 2026</a>
          </div>
          <div className="landing-footer-col">
            <h4>Ecosystem</h4>
            <Link to="/market">Marketplace</Link>
            <Link to="/dao">Community / governance</Link>
            <Link to="/login">Sign in</Link>
          </div>
        </div>
        <p className="landing-footer-bottom muted">
          Private beta on Base Sepolia · open-source contracts · © {new Date().getFullYear()} SoundHub
        </p>
      </footer>
    </div>
  );
}
