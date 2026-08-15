import { Link } from "react-router-dom";

const FEATURES = [
  {
    icon: "🧠",
    title: "Your DAW, understood",
    text: "SoundHub parses .als, .cpr, .rpp and .flp — so a commit shows “BPM 128 → 132, + track Pad, + plugin Vital”, not “binary file changed”.",
  },
  {
    icon: "🔒",
    title: "Escrow on-chain",
    text: "Every purchase goes through the SoundHubMarket escrow on Base Sepolia. No trust-me selling — funds release when you confirm receipt.",
  },
  {
    icon: "🎛",
    title: "Inside your DAW",
    text: "A Max for Live device embeds the marketplace in Ableton Live. Prototypes for FL Studio and Cubase ship in the repo. Buy where you make music.",
  },
  {
    icon: "🪙",
    title: "Tokenized platform",
    text: "SND token, Release NFTs with royalties and collaborator splits, a DAO with a timelock. Creators get paid automatically when buyers confirm.",
  },
  {
    icon: "✨",
    title: "BPM-aware suggestions",
    text: "The recommendation engine scores assets by genre, BPM proximity, key and device overlap — so a 128 BPM techno set surfaces bass presets that fit.",
  },
  {
    icon: "🗂",
    title: "Version control for tracks",
    text: "Branches, commits, smart diffs. Content-addressed storage deduplicates by SHA-256, so full-snapshot commits cost almost nothing.",
  },
];

const STEPS = [
  {
    n: "01",
    title: "Version your project",
    text: "Push a snapshot of your Ableton / Cubase / REAPER / FL Studio file. SoundHub parses it and shows what actually changed.",
  },
  {
    n: "02",
    title: "Find your sound",
    text: "Browse the catalog or let the DAW context (BPM, key, devices) rank what fits your track. Verified metadata before you pay.",
  },
  {
    n: "03",
    title: "Buy & load",
    text: "Pay with SND through escrow. The preset lands in your library — one click from the SoundHub panel in your DAW.",
  },
];

const DIFF_ROWS = [
  { kind: "bpm", label: "Tempo", before: "128", after: "132" },
  { kind: "add", label: "Track", before: "—", after: "+ Pad (midi)" },
  { kind: "add", label: "Plugin", before: "—", after: "+ Vital" },
  { kind: "add", label: "Sample", before: "—", after: "+ VocalChop_01.wav" },
];

export default function LandingPage() {
  return (
    <div className="landing">
      {/* ---------- hero ---------- */}
      <section className="landing-hero">
        <div className="landing-hero-inner">
          <p className="landing-eyebrow">🎛 SoundHub — tokenized marketplace for finished sounds</p>
          <h1 className="landing-title">
            Don't generate.
            <br />
            <span className="landing-title-accent">Buy.</span>
          </h1>
          <p className="landing-subtitle">
            Presets, loops, stems and sound packs — DAW-verified, escrowed, and paid for
            with SND. The marketplace lives inside your DAW, not in DMs and zip files.
          </p>
          <div className="landing-cta">
            <Link to="/login" className="btn landing-btn-primary">
              Get started free
            </Link>
            <Link to="/login" className="btn landing-btn-ghost">
              Sign in with wallet
            </Link>
          </div>
          <div className="landing-daws" aria-label="Supported DAWs">
            <span>Ableton Live</span>
            <span>FL Studio</span>
            <span>Cubase</span>
            <span>REAPER</span>
          </div>
        </div>

        <div className="landing-shot">
          <div className="landing-shot-bar">
            <span className="dot" />
            <span className="dot" />
            <span className="dot" />
            <span className="landing-shot-url">soundhub — marketplace & version control for music</span>
          </div>
          <img src="/screenshot-main.png" alt="SoundHub marketplace" loading="lazy" />
        </div>
      </section>

      {/* ---------- diff example ---------- */}
      <section className="landing-section landing-diff">
        <div className="landing-diff-copy">
          <h2>See what changed. Not just “file modified”.</h2>
          <p>
            GitHub shows a 40 MB binary and nothing else. SoundHub understands the
            project file — tempo, signature, tracks, devices, plugins, samples — and
            diffs the music, not the bytes.
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
      </section>

      {/* ---------- features ---------- */}
      <section className="landing-section">
        <p className="landing-eyebrow center">Why SoundHub</p>
        <h2 className="landing-h2">Everything a finished sound needs</h2>
        <div className="landing-features">
          {FEATURES.map((f) => (
            <div key={f.title} className="landing-feature">
              <div className="landing-feature-icon">{f.icon}</div>
              <h3>{f.title}</h3>
              <p>{f.text}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ---------- how it works ---------- */}
      <section className="landing-section landing-steps">
        <p className="landing-eyebrow center">How it works</p>
        <h2 className="landing-h2">From project to purchase in three steps</h2>
        <div className="landing-steps-grid">
          {STEPS.map((s) => (
            <div key={s.n} className="landing-step">
              <span className="landing-step-n">{s.n}</span>
              <h3>{s.title}</h3>
              <p>{s.text}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ---------- final CTA ---------- */}
      <section className="landing-cta-final">
        <h2 className="landing-h2">Stop tweaking presets for two hours.</h2>
        <p>Buy the finished sound and keep making music.</p>
        <Link to="/login" className="btn landing-btn-primary">
          Join SoundHub
        </Link>
      </section>

      <footer className="landing-footer">
        <div className="landing-footer-brand">🎛 SoundHub</div>
        <p>Don't generate. Buy. — GitHub for sound, tokenized, inside your DAW.</p>
        <p className="muted">SND · escrow marketplace · Release NFTs · DAO · Max for Live · Base Sepolia</p>
      </footer>
    </div>
  );
}
