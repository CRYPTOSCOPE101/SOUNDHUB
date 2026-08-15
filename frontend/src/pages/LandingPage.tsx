import { useEffect, useRef, useState } from "react";
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

const SHOWCASES = [
  {
    img: "/screenshot-main.png",
    alt: "SoundHub marketplace",
    eyebrow: "Marketplace",
    title: "Browse. Verify. Buy.",
    text: "Presets, loops, stems and packs with DAW-verified metadata — you see the BPM, the key, the devices and the license tier before you spend a single SND.",
    bullets: ["DAW-verified contents", "4 license tiers, bound on-chain", "escrow + 2-day dispute window"],
  },
  {
    img: "/screenshot-repo.png",
    alt: "SoundHub version control",
    eyebrow: "Version control",
    title: "Git, but for your tracks",
    text: "Commit snapshots of your Ableton, Cubase, REAPER or FL Studio project. Branches, history and diffs that read like music, not bytes.",
    bullets: ["smart diffs: tempo, tracks, plugins, samples", "branches & per-branch history", "SHA-256 content-addressed storage"],
  },
];

const STATS = [
  { value: "4", label: "DAW formats parsed" },
  { value: "1M", label: "SND fixed supply" },
  { value: "2d", label: "escrow dispute window" },
  { value: "12", label: "contract tests, all green" },
];

const LICENSES = [
  {
    name: "Personal",
    price: "1×",
    note: "one track, one producer",
    features: ["use in a single non-commercial track", "credit the creator", "no resale, no remix distribution"],
    featured: false,
  },
  {
    name: "Commercial",
    price: "5×",
    note: "the default for releases",
    features: ["use in commercial releases", "streaming & sales income allowed", "still no resale of the preset itself"],
    featured: true,
  },
  {
    name: "Sync",
    price: "10×",
    note: "for film, ads & games",
    features: ["everything in Commercial", "sync placements (film/TV/ads)", "negotiable exclusivity per placement"],
    featured: false,
  },
  {
    name: "Exclusive",
    price: "custom",
    note: "take it off the market",
    features: ["the asset leaves the catalog", "full ownership of the sound", "one-to-one deal, escrowed"],
    featured: false,
  },
];

const TESTIMONIALS = [
  {
    quote:
      "I used to lose an evening to Serum presets. Now the panel reads my 128 BPM techno set and the right bass patch is two clicks away.",
    author: "Mara, techno producer",
    role: "Ableton Live + SoundHub panel",
  },
  {
    quote:
      "The diff actually understands my project. “BPM 132, + plugin Vital, + sample VocalChop” — that's version control for musicians, not file hoarding.",
    author: "Dev, session musician",
    role: "FL Studio · 214 commits",
  },
  {
    quote:
      "Selling a pack used to mean DMs, spreadsheets and hoping. Now it's escrow, a license bound to the purchase, and the payout arrives by itself.",
    author: "Kai, sound designer",
    role: "seller · 3 packs listed",
  },
];

const NAV_LINKS = [
  { href: "#features", label: "Features" },
  { href: "#product", label: "Product" },
  { href: "#pricing", label: "Licenses" },
  { href: "#faq", label: "FAQ" },
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
            Get started
          </Link>
        </div>
      </nav>

      {/* ---------- hero ---------- */}
      <section className="landing-hero" id="top">
        <div className="landing-hero-inner">
          <p className="landing-eyebrow">🎛 Tokenized marketplace for finished sounds</p>
          <h1 className="landing-title">
            Don't generate.
            <br />
            <span className="landing-title-accent">Buy.</span>
          </h1>
          <p className="landing-subtitle">
            You're in your DAW, the track is missing a bass — that's the moment.
            SoundHub lives right there: verified presets, escrowed purchases, paid in SND.
            No tab switch, no DMs, no zip files.
          </p>
          <div className="landing-cta">
            <a href="#waitlist" className="landing-btn-primary">
              Get started free
            </a>
            <Link to="/login" className="landing-btn-ghost">
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
          <img src="/screenshot-main.png" alt="SoundHub marketplace" loading="eager" />
        </div>
      </section>

      {/* ---------- logo strip ---------- */}
      <section className="landing-logos">
        <p>Your project files. One platform.</p>
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

      {/* ---------- diff example ---------- */}
      <section className="landing-section landing-diff" id="features">
        <Reveal>
          <div className="landing-diff-grid">
            <div className="landing-diff-copy">
              <p className="landing-eyebrow">Smart diff</p>
              <h2>See what changed. Not just “file modified”.</h2>
              <p>
                GitHub shows a 40 MB binary and nothing else. SoundHub understands the
                project file — tempo, signature, tracks, devices, plugins, samples — and
                diffs the music, not the bytes.
              </p>
            </div>
            <div className="landing-diff-card">
              <div className="landing-diff-head">SoundHub smart diff — track_v3.als</div>
              {[
                { kind: "bpm", label: "Tempo", before: "128", after: "132" },
                { kind: "add", label: "Track", before: "—", after: "+ Pad (midi)" },
                { kind: "add", label: "Plugin", before: "—", after: "+ Vital" },
                { kind: "add", label: "Sample", before: "—", after: "+ VocalChop_01.wav" },
              ].map((r) => (
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

      {/* ---------- features ---------- */}
      <section className="landing-section">
        <Reveal>
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
        </Reveal>
      </section>

      {/* ---------- alternating showcases ---------- */}
      <section className="landing-section landing-showcases" id="product">
        {/* The moment of intent — the core positioning, first */}
        <Reveal>
          <div className="landing-showcase">
            <div className="landing-panel">
              <div className="landing-panel-head">
                <span className="landing-panel-dot" />
                <span className="landing-panel-title">SoundHub — Ableton Live</span>
                <span className="landing-panel-bpm">128 BPM</span>
              </div>
              <div className="landing-panel-buttons">
                <button className="landing-panel-btn" type="button">refresh</button>
                <button className="landing-panel-btn" type="button">suggest</button>
                <button className="landing-panel-btn active" type="button">buy &amp; load</button>
              </div>
              <div className="landing-panel-note">matched to your 128 BPM techno set</div>
              <div className="landing-panel-card">
                <div className="landing-panel-card-name">Dark Bass Patch (Serum)</div>
                <div className="landing-panel-card-meta">techno · 128 BPM · 24 Serum presets · verified</div>
                <div className="landing-panel-card-row">
                  <span className="landing-panel-card-price">50 SND</span>
                  <span className="landing-panel-card-license">Commercial</span>
                </div>
              </div>
              <div className="landing-panel-foot">escrow · dispute window 2d · auto-payout to creator</div>
            </div>
            <div className="landing-showcase-copy">
              <p className="landing-eyebrow">The moment of intent</p>
              <h2>Buy where you're already making music</h2>
              <p className="landing-showcase-text">
                The panel reads your project — BPM, and soon key, tracks and devices —
                and puts the right finished sounds in front of you. One click, escrowed,
                landed in your library. The marketplace meets the producer in the DAW,
                not on a website.
              </p>
              <ul className="landing-showcase-bullets">
                <li>catalog read straight from the chain — no signup to browse</li>
                <li>BPM-aware suggestions matched to your set</li>
                <li>Buy &amp; Load: 1–2 clicks, web3 invisible</li>
              </ul>
            </div>
          </div>
        </Reveal>
        {SHOWCASES.map((s, i) => (
          <Reveal key={s.title}>
            <div className={`landing-showcase ${i % 2 === 1 ? "reverse" : ""}`}>
              <div className="landing-showcase-shot">
                <div className="landing-shot-bar">
                  <span className="dot" />
                  <span className="dot" />
                  <span className="dot" />
                </div>
                <img src={s.img} alt={s.alt} loading="lazy" />
              </div>
              <div className="landing-showcase-copy">
                <p className="landing-eyebrow">{s.eyebrow}</p>
                <h2>{s.title}</h2>
                <p className="landing-showcase-text">{s.text}</p>
                <ul className="landing-showcase-bullets">
                  {s.bullets.map((b) => (
                    <li key={b}>{b}</li>
                  ))}
                </ul>
              </div>
            </div>
          </Reveal>
        ))}
      </section>

      {/* ---------- stats band ---------- */}
      <section className="landing-stats">
        <Reveal>
          <div className="landing-stats-grid">
            {STATS.map((s) => (
              <div key={s.label} className="landing-stat">
                <div className="landing-stat-value">{s.value}</div>
                <div className="landing-stat-label">{s.label}</div>
              </div>
            ))}
          </div>
        </Reveal>
      </section>

      {/* ---------- how it works ---------- */}
      <section className="landing-section landing-steps">
        <Reveal>
          <p className="landing-eyebrow center">How it works</p>
          <h2 className="landing-h2">From project to purchase in three steps</h2>
          <div className="landing-steps-grid">
            {[
              { n: "01", title: "Version your project", text: "Push a snapshot of your Ableton / Cubase / REAPER / FL Studio file. SoundHub parses it and shows what actually changed." },
              { n: "02", title: "Find your sound", text: "Browse the catalog or let the DAW context (BPM, key, devices) rank what fits your track. Verified metadata before you pay." },
              { n: "03", title: "Buy & load", text: "Pay with SND through escrow. The preset lands in your library — one click from the SoundHub panel in your DAW." },
            ].map((s) => (
              <div key={s.n} className="landing-step">
                <span className="landing-step-n">{s.n}</span>
                <h3>{s.title}</h3>
                <p>{s.text}</p>
              </div>
            ))}
          </div>
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
        </Reveal>
      </section>

      {/* ---------- testimonials ---------- */}
      <section className="landing-section landing-quotes">
        <Reveal>
          <p className="landing-eyebrow center">Producers</p>
          <h2 className="landing-h2">Loved by people who make music</h2>
          <div className="landing-quotes-grid">
            {TESTIMONIALS.map((t) => (
              <figure key={t.author} className="landing-quote">
                <blockquote>“{t.quote}”</blockquote>
                <figcaption>
                  <strong>{t.author}</strong>
                  <span>{t.role}</span>
                </figcaption>
              </figure>
            ))}
          </div>
        </Reveal>
      </section>

      {/* ---------- final CTA + waitlist ---------- */}
      <section className="landing-cta-final" id="waitlist">
        <Reveal>
          <h2 className="landing-h2">Stop tweaking presets for two hours.</h2>
          <p>Buy the finished sound and keep making music.</p>
          <form className="landing-waitlist" onSubmit={joinWaitlist}>
            <input
              type="email"
              placeholder="you@studio.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              aria-label="Email"
            />
            <button type="submit" className="landing-btn-primary">
              Join the waitlist
            </button>
          </form>
          {waitlist && <div className="landing-waitlist-msg">{waitlist}</div>}
          <div className="landing-cta-final-alts">
            <Link to="/login">or sign in with demo account →</Link>
          </div>
        </Reveal>
      </section>

      {/* ---------- FAQ ---------- */}
      <section className="landing-section landing-faq" id="faq">
        <Reveal>
          <p className="landing-eyebrow center">FAQ</p>
          <h2 className="landing-h2">Questions, answered</h2>
          <div className="landing-faq-list">
            {[
              { q: "Which DAWs does SoundHub understand?", a: "Ableton Live (.als), Cubase (.cpr), REAPER (.rpp) and FL Studio (.flp) — parsed natively for smart diffs and verified asset metadata." },
              { q: "Do I need a wallet to use it?", a: "To browse and recommend — no. To buy, you sign in with a wallet on Base Sepolia; a relayer path for fully invisible web3 is on the roadmap." },
              { q: "What does “escrow” actually mean?", a: "Your SND sits in the SoundHubMarket contract until you confirm receipt (or a 2-day window passes). If it's not right, you can request a refund." },
              { q: "Is this on mainnet?", a: "Today it runs on Base Sepolia with a faucet (100 SND/day). Mainnet deployment is planned once contracts are audited." },
            ].map((f) => (
              <details key={f.q} className="landing-faq-item">
                <summary>{f.q}</summary>
                <p>{f.a}</p>
              </details>
            ))}
          </div>
        </Reveal>
      </section>

      {/* ---------- footer ---------- */}
      <footer className="landing-footer">
        <div className="landing-footer-grid">
          <div className="landing-footer-brand">
            <img src="/logo.png" alt="SoundHub" className="landing-nav-logo" /> SoundHub
            <p className="landing-footer-tag">Don't generate. Buy. — GitHub for sound, tokenized, inside your DAW.</p>
          </div>
          <div className="landing-footer-col">
            <h4>Product</h4>
            <a href="#product">Marketplace</a>
            <a href="#features">Smart diffs</a>
            <a href="#pricing">Licenses</a>
            <a href="#waitlist">Waitlist</a>
          </div>
          <div className="landing-footer-col">
            <h4>Inside your DAW</h4>
            <a href="#product">Max for Live</a>
            <a href="#product">FL Studio</a>
            <a href="#product">Cubase</a>
            <a href="#product">REAPER (soon)</a>
          </div>
          <div className="landing-footer-col">
            <h4>Ecosystem</h4>
            <Link to="/market">Marketplace</Link>
            <Link to="/dao">DAO</Link>
            <Link to="/login">Sign in</Link>
          </div>
        </div>
        <p className="landing-footer-bottom muted">
          SND · escrow marketplace · Release NFTs · DAO · Base Sepolia — © {new Date().getFullYear()} SoundHub
        </p>
      </footer>
    </div>
  );
}
