import { useEffect, useState } from "react";
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

// What SoundHub understands about a session vs what a shared file shows.
// CodeRabbit-style "best-in-class context" comparison.
const CONTEXT_WE_SEE = [
  { label: "Tempo & time signature", value: "128 BPM · 4/4" },
  { label: "Tracks", value: "12 — midi · audio · return" },
  { label: "Plugins & their settings", value: "8 — Serum, Vital, Pro-Q 3…" },
  { label: "Samples & presets", value: "42 referenced files" },
  { label: "Loudness", value: "LUFS · true peak · sample rate" },
  { label: "Stems by role", value: "drums · bass · vocal · synths" },
];

const CONTEXT_OTHERS_SEE = [
  "Filename",
  "File size",
  "“Binary file changed”",
];

const CONTEXT_STATS = [
  { n: "4", label: "DAW formats parsed" },
  { n: "30+", label: "context points per version" },
  { n: "0", label: "ZIPs to unzip" },
];

// CodeRabbit-style engine tabs: what the engine actually does per step,
// with a small animated visual per tab (pure CSS, loops forever).
const ENGINE_TABS = [
  {
    id: "parse",
    title: "DAW parsing engine",
    text: "Reads Ableton, REAPER, Cubase and FL Studio projects and extracts BPM, time signature, tracks, plugins with their settings, samples and loudness — the context everything else runs on.",
    points: ["4 DAW formats, one parser", "Plugins with the actual state of each instance", "Loudness measured per version and stem"],
    tags: ["Neon_v13.als", "128 BPM", "4/4", "12 tracks", "8 plugins", "42 samples", "−14 LUFS"],
    blocks: ["Neon_v13.als", "128 BPM · 4/4", "12 tracks", "8 plugins", "42 samples", "−14 LUFS"],
  },
  {
    id: "diff",
    title: "Smart diff",
    text: "Compares two bounces at the project level: tempo, tracks, plugins, samples. A revision is a story — never \"binary file changed\".",
    points: ["BPM and time-signature changes", "Tracks and plugins added / removed", "Raw normalized diff for the curious"],
    tags: ["v12 → v13", "Tempo 128 → 132", "+ Pad track", "+ Vital plugin", "+ Clap.wav", "−2 plugins"],
    blocks: ["v12", "Tempo 128 → 132", "+ Pad track", "+ Vital plugin", "v13"],
  },
  {
    id: "ledger",
    title: "Decision ledger",
    text: "Every request, approval and delivery is hashed into a tamper-evident chain — proof without trusting anyone.",
    points: ["Each event links to the previous hash", "Tampering invalidates the whole chain", "Verifiable end-to-end in one click"],
    tags: ["Chain verified ✓", "request a1f9…", "approval 77c2…", "delivery e4b0…", "stems 9d31…", "master 51aa…"],
    blocks: ["genesis", "request a1f9…", "approval 77c2…", "delivery e4b0…", "chain ✓"],
  },
  {
    id: "dedup",
    title: "Content-addressed storage",
    text: "Identical files are stored once; re-pushing the same .als costs nothing. Dedup is automatic, so a snapshot is almost free.",
    points: ["Same file, one blob, any number of commits", "Re-pushes report what was deduplicated", "A locked delivery can never be silently swapped"],
    tags: ["3 pushes · 1 blob", "push v11", "push v12", "push v13", "dedup: 2", "0 new bytes"],
    blocks: ["push v11", "push v12", "push v13", "1 blob", "dedup: 2"],
  },
  {
    id: "approval",
    title: "Review & approval",
    text: "Timestamped notes, structured rounds and role-based sign-offs — the loop that actually ships a track.",
    points: ["Guests comment at the exact moment, no account", "Draft notes consolidate into one round", "Role-gated approvals (artist, A&R, label)"],
    tags: ["Approved ✓", "Aisha (A&R)", "Marco (client)", "Label", "in review → approved", "delivery locked"],
    blocks: ["in review", "notes 01:24", "round 2", "approved ✓", "delivery locked"],
  },
];

const DAW_ASSETS = [
  {
    title: "Tracks & plugins with settings",
    text: "Project files are parsed into structure: tracks, instruments, plugins and the actual state of each instance — REAPER PARAM lines, Ableton preset refs.",
  },
  {
    title: "Stems by logical name",
    text: "NeonBass_final_03.wav and bass_v13.wav both count as bass — stem-level A/B is matched by what the part is, not what it's called.",
  },
  {
    title: "Samples & presets",
    text: "The samples a project references and the presets it uses are listed in the tree — you can see what a version is made of.",
  },
  {
    title: "One-command push",
    text: "`snd push` sends a whole project folder as one versioned commit with a SOUNDHUB-MANIFEST.json describing the structure.",
  },
];

const MARKET_BENEFITS = [
  { title: "Buy without leaving the session", text: "A revision needs a tighter bass? The panel suggests verified, compatible patches — buy and load in place." },
  { title: "Escrow protected", text: "Payments sit in escrow until you confirm receipt. Dispute window and refunds are part of the purchase." },
  { title: "Verified before you pay", text: "DAW-parsed metadata: BPM, key, plugins, samples. What you're buying is answered before checkout." },
  { title: "License bound on-chain", text: "Personal / Commercial / Sync / Exclusive tiers attached to the purchase. Rights stay legible end to end." },
];

const INTEGRATIONS = [
  { name: "Ableton Live", status: "available", href: null, detail: "`soundhub` CLI bridge — push bounces, export open requests, locator helper · Max for Live panel: catalog + push current export" },
  { name: "FL Studio", status: "available", href: "/integrations/fl-studio", detail: ".flp parsed (FL 11–21) · `snd push` commits project + master + stems → review · VST3 companion panel via the SoundHub Agent — next" },
  { name: "Cubase", status: "available", href: "/integrations/cubase", detail: ".cpr parsed (tracks, VST3 plugins, samples) · `snd push` commits project + master + stems → review · VST3 companion panel via the SoundHub Agent — next" },
  { name: "REAPER", status: "planned", href: null, detail: "Planned — no timeline yet" },
];

// --- feature tabs (CodeRabbit-style) ---------------------------------------

const FEATURE_TABS = [
  {
    id: "review",
    label: "Review",
    title: "Comments at the exact moment",
    text: "Reviewers drop notes on the timeline — “01:24 — bass masks the vocal”. Reply, resolve, loop the region. No account needed.",
    points: ["Timestamped comments & replies", "Consolidated revision rounds", "Voice notes from the phone", "Status: In review → Needs changes → Approved"],
  },
  {
    id: "ab",
    label: "A/B",
    title: "Gapless, level-matched A/B",
    text: "Compare v12 and v13 with one playhead, loudness matched — mix or individual stems. Hear the fix, don't just read it.",
    points: ["Same playhead, loop regions", "Short-term LUFS compensation", "Stem-level compare: drums, bass, vocal, synths", "Reference tracks (private, non-deliverable)"],
  },
  {
    id: "diff",
    label: "Smart diff",
    title: "What actually changed",
    text: "Between versions you see the structure, not “binary file changed”: tempo, tracks, plugins with their settings, samples.",
    points: ["Tempo / signature changes", "Added or removed tracks & plugins", "Plugin parameter diffs (REAPER PARAM, Ableton presets)", "SHA-256 ledger of every decision"],
  },
];

// --- honest testimonials (from Ableton-community research, not invented) ---

const TESTIMONIALS = [
  {
    quote: "I want to work straight from my DAW, not jump between the browser and the project.",
    who: "Producer on r/ableton — what users keep asking for",
  },
  {
    quote: "Give me push-to-work, not \u201copen a site, download a ZIP, unzip, import, compare again\u201d.",
    who: "Ableton forum thread on workflow friction",
  },
  {
    quote: "I need to see exactly what changed between iterations, not just \u201cbinary changed\u201d.",
    who: "Community feedback — the smart-diff ask",
  },
];

// --- pricing (honest: private beta, no invented prices) ---------------------

const PLANS = [
  {
    name: "Free",
    price: "$0",
    note: "For solo producers trying the loop",
    features: ["Review sessions & versioning", "Watermarked previews", "Public share links", "Community support"],
    cta: "Open a sample review",
    href: SAMPLE_REVIEW_URL,
    featured: false,
  },
  {
    name: "Pro",
    price: "beta — from $15/mo",
    note: "For engineers with real clients",
    features: ["Stem-level A/B & reference tracks", "Release package + QC preflight", "Stripe paid delivery (card / AP / GP)", "Booking deposits & paid extra rounds", "Change orders after approval"],
    cta: "Join the beta",
    href: null,
    featured: true,
  },
  {
    name: "Team",
    price: "beta — from $39/mo",
    note: "For labels & studios",
    features: ["Roles & approval chains", "Client briefs + service presets", "Email reminders & deadlines", "Archive & session-file handoff", "Priority support"],
    cta: "Join the beta",
    href: null,
    featured: false,
  },
];

// --- comparison table -------------------------------------------------------

const COMPARE_ROWS = [
  { feature: "Version history", soundhub: true, discord: false, drive: false, github: false },
  { feature: "Timestamped comments on audio", soundhub: true, discord: false, drive: false, github: false },
  { feature: "Smart diff of DAW structure", soundhub: true, discord: false, drive: false, github: false },
  { feature: "Gapless A/B between versions", soundhub: true, discord: false, drive: false, github: false },
  { feature: "Stems matched by role", soundhub: true, discord: false, drive: false, github: false },
  { feature: "Approvals & rounds", soundhub: true, discord: false, drive: false, github: false },
  { feature: "Final delivery with invoice", soundhub: true, discord: false, drive: false, github: false },
  { feature: "DAW parsing (.als/.cpr/.rpp/.flp)", soundhub: true, discord: false, drive: false, github: false },
];

// --- hero rotating word -----------------------------------------------------

const HERO_WORDS = ["review", "versions", "approvals"];

const FAQ = [
  {
    q: "Do reviewers need an account or a wallet?",
    a: "No. Reviewers open a private link, listen, and leave timestamped comments — no signup, no wallet. The producer works in SoundHub; collaborators just review.",
  },
  {
    q: "How is this different from sending files over Discord or email?",
    a: "SoundHub keeps one source of truth: versions (v11 → v12 → v13), comments pinned to exact moments, statuses (In review / Needs changes / Approved) and smart diffs that show what actually changed between versions.",
  },
  {
    q: "What does the marketplace add?",
    a: "When a revision needs a sound, you can buy a verified, compatible asset right in the project — escrowed, with a license bound to the purchase. It's a second layer on top of the review workflow.",
  },
  {
    q: "Is this live on mainnet?",
    a: "Today SoundHub runs on Base Sepolia (testnet). Contracts are open-source with a full test suite; a security review is in progress before any mainnet deployment.",
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
    items: ["Max for Live: review comments in the DAW", "Cubase & FL Studio: VST3 companion panel (JUCE) + SoundHub Agent", "REAPER integration", "Marketplace: sell finished sounds"],
    state: "next",
  },
  { phase: "Later", items: ["Mainnet + security audit", "USDC checkout", "DAO governance"], state: "later" },
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

// A product screenshot framed like a browser window (CodeRabbit-style).
// `src` is a full-resolution MP4 (sharp, full color); `poster` is a static
// PNG fallback shown while the video loads / in browsers without video.
function BrowserShot({ src, url, caption, poster }: { src: string; url: string; caption?: string; poster?: string }) {
  return (
    <div className="cr-shot">
      <div className="cr-shot-bar">
        <span className="dot" />
        <span className="dot" />
        <span className="dot" />
        <span className="cr-shot-url">{url}</span>
      </div>
      <video
        src={src}
        poster={poster}
        autoPlay
        muted
        loop
        playsInline
        preload="metadata"
        aria-label={caption || url}
      >
        <img src={poster || src} alt={caption || url} loading="lazy" />
      </video>
      {caption && <div className="cr-shot-cap">{caption}</div>}
    </div>
  );
}

// Rotating word in the hero headline (CodeRabbit-style motion).
function RotatingWord({ words }: { words: string[] }) {
  const [i, setI] = useState(0);

  useEffect(() => {
    const t = setInterval(() => setI((x) => (x + 1) % words.length), 2200);
    return () => clearInterval(t);
  }, [words.length]);

  return (
    <span className="cr-rotate" key={i}>
      {words[i]}
    </span>
  );
}

// Feature tabs: Review / A/B / Diff.
function FeatureTabs() {
  const [tab, setTab] = useState(FEATURE_TABS[0].id);
  const active = FEATURE_TABS.find((t) => t.id === tab)!;

  return (
    <div className="cr-tabs">
      <div className="cr-tabbar">
        {FEATURE_TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            className={`cr-tab ${t.id === tab ? "active" : ""}`}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>
      <div className="cr-tabpanel" key={active.id}>
        <div className="cr-tabpanel-copy">
          <h3 className="cr-tabpanel-title">{active.title}</h3>
          <p className="cr-tabpanel-text">{active.text}</p>
          <ul className="cr-feature-list">
            {active.points.map((p) => <li key={p}>{p}</li>)}
          </ul>
        </div>
        <div className="cr-tabpanel-art">
          {active.id === "diff" ? (
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
          ) : (
            <div className="cr-tabpanel-panel">
              <div className="cr-tabpanel-head">Neon Warehouse — {active.id === "ab" ? "v12 ↔ v13 A/B" : "Review session"}</div>
              {active.id === "ab" ? (
                <>
                  <div className="cr-ab-wave">
                    {Array.from({ length: 48 }).map((_, k) => (
                      <span key={k} style={{ height: `${18 + Math.abs(Math.sin(k * 1.7)) * 55}%` }} />
                    ))}
                  </div>
                  <div className="cr-ab-modes">
                    <span className="active">Full mix</span>
                    <span>Drums</span>
                    <span>Bass</span>
                    <span>Vocal</span>
                    <span>Synths</span>
                  </div>
                  <div className="cr-ab-gain">LUFS-matched · −0.4 dB</div>
                </>
              ) : (
                <>
                  <div className="cr-comment">
                    <span className="cr-comment-time">01:24</span>
                    <span className="cr-comment-body">“Kick and bass clash here — let the vocal breathe.”</span>
                    <span className="cr-comment-who">Aisha (A&R)</span>
                  </div>
                  <div className="cr-comment">
                    <span className="cr-comment-time">00:52</span>
                    <span className="cr-comment-body">Love the new bass preset — keep it.</span>
                    <span className="cr-comment-who">Marco (client)</span>
                  </div>
                  <div className="cr-comment cr-comment-resolved">
                    <span className="cr-comment-time">02:10</span>
                    <span className="cr-comment-body">EQ −3 dB @ 250 Hz — fixed in v13 ✓</span>
                    <span className="cr-comment-who">SoundHub</span>
                  </div>
                </>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// Blockchain — a hash chain wrapped into a ring, CodeRabbit-style:
// a dark canvas with concentric dashed rings, blocks linked by flowing
// edges around the circle, and source tags fed from the ring's edge.
const CG_RINGS = [
  { r: 176, cls: "cg-ring-a" },
  { r: 124, cls: "cg-ring-b" },
  { r: 72, cls: "cg-ring-c" },
];

// deterministic pseudo-hash per block label, so the chain looks "real"
function blockHash(label: string): string {
  let h = 2166136261;
  for (let i = 0; i < label.length; i++) {
    h ^= label.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return (h >>> 0).toString(16).padStart(8, "0").slice(0, 6);
}

function cgPoint(cx: number, cy: number, r: number, angleDeg: number) {
  const a = (angleDeg * Math.PI) / 180;
  return { x: cx + r * Math.cos(a), y: cy + r * Math.sin(a) };
}

function BlockchainVisual({ tags, blocks }: { tags: string[]; blocks: string[] }) {
  const cx = 205;
  const cy = 185;

  // blocks arranged around the middle ring, chain order clockwise from top
  const chain = blocks.slice(0, 6);
  const pts = chain.map((_, i) => {
    const start = -90;
    const step = chain.length === 1 ? 0 : 360 / chain.length;
    return cgPoint(cx, cy, 104, start + step * i);
  });

  const tagsRight = tags.slice(0, 5);
  const tagX = 352;
  const tagY0 = 64;
  const tagGap = 50;

  return (
    <div className="cg">
      <svg className="cg-svg" viewBox="0 0 660 390" role="img" aria-label="Hash chain of the SoundHub engine">
        {/* concentric dashed rings behind the chain */}
        {CG_RINGS.map((ring) => (
          <circle key={ring.r} className={`cg-ring ${ring.cls}`} cx={cx} cy={cy} r={ring.r} fill="none" />
        ))}

        {/* genesis block at the centre */}
        <g className="cg-block cg-block-genesis">
          <rect x={cx - 40} y={cy - 24} width={80} height={48} rx={12} />
          <text className="cg-block-hash" x={cx} y={cy - 6} textAnchor="middle">
            0x000000
          </text>
          <text className="cg-block-label" x={cx} y={cy + 13} textAnchor="middle">
            genesis
          </text>
        </g>

        {/* links: centre -> each block, and block -> next block around the ring */}
        {pts.map((p, i) => (
          <line
            key={`c${i}`}
            className="cg-edge cg-edge-core"
            x1={cx + 42}
            y1={cy}
            x2={p.x - (p.x > cx ? 42 : -42)}
            y2={p.y - (p.y > cy ? 24 : -24)}
            style={{ animationDelay: `${i * 0.3}s` }}
          />
        ))}
        {pts.map((p, i) => {
          const nxt = pts[(i + 1) % pts.length];
          return (
            <line
              key={`l${i}`}
              className="cg-edge"
              x1={p.x + (nxt.x > p.x ? 42 : -42)}
              y1={p.y + (nxt.y > p.y ? 24 : -24)}
              x2={nxt.x - (nxt.x > p.x ? 42 : -42)}
              y2={nxt.y - (nxt.y > p.y ? 24 : -24)}
              style={{ animationDelay: `${i * 0.25}s` }}
            />
          );
        })}

        {/* blocks around the ring */}
        {chain.map((label, i) => {
          const p = pts[i];
          const last = i === chain.length - 1;
          return (
            <g key={label} className={`cg-block ${last ? "cg-block-head" : ""}`} style={{ animationDelay: `${i * 0.35}s` }}>
              <rect x={p.x - 42} y={p.y - 25} width={84} height={50} rx={12} />
              <text className="cg-block-hash" x={p.x} y={p.y - 7} textAnchor="middle">
                {last ? "✓" : `0x${blockHash(label)}`}
              </text>
              <text className="cg-block-label" x={p.x} y={p.y + 12} textAnchor="middle">
                {label}
              </text>
            </g>
          );
        })}

        {/* source tags fed from the ring's right edge */}
        {tagsRight.map((t, i) => {
          const ty = tagY0 + i * tagGap;
          return (
            <g key={t} className="cg-tag">
              <line className="cg-tag-line" x1={cx + 142} y1={cy + 24} x2={tagX - 14} y2={ty} />
              <rect className={`cg-tag-box ${i === 0 ? "cg-tag-box-solid" : ""}`} x={tagX} y={ty - 15} width={298} height={30} rx={15} />
              <text className={`cg-tag-text ${i === 0 ? "cg-tag-text-solid" : ""}`} x={tagX + 14} y={ty + 5}>
                {t}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

// CodeRabbit-style tabs under "Best-in-class context": a title per engine
// step plus a looping animated preview that switches when you click.
function EngineTabs() {
  const [tab, setTab] = useState(ENGINE_TABS[0].id);
  const active = ENGINE_TABS.find((t) => t.id === tab)!;
  return (
    <div className="cr-engine">
      <div className="cr-engine-tabs" role="tablist" aria-orientation="vertical">
        {ENGINE_TABS.map((t) => (
          <div
            key={t.id}
            role="tab"
            aria-selected={t.id === tab}
            tabIndex={0}
            className={`cr-engine-tab ${t.id === tab ? "active" : ""}`}
            onMouseEnter={() => setTab(t.id)}
            onClick={() => setTab(t.id)}
            onFocus={() => setTab(t.id)}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") setTab(t.id);
            }}
          >
            <span className="cr-engine-tab-head">
              <span className="cr-engine-tab-title">{t.title}</span>
            </span>
            {t.id === tab && (
              <span className="cr-engine-tab-desc">
                {t.text}
                <ul className="cr-engine-tab-points">
                  {t.points.map((pt) => (
                    <li key={pt}>{pt}</li>
                  ))}
                </ul>
              </span>
            )}
          </div>
        ))}
      </div>
      <div className="cr-engine-panel" key={active.id}>
        <div className="cr-engine-visual">
          <BlockchainVisual tags={active.tags} blocks={active.blocks} />
        </div>
      </div>
    </div>
  );
}

// Honest testimonials — real asks from the Ableton community, not invented.
function Testimonials() {
  return (
    <div className="cr-testimonials">
      {TESTIMONIALS.map((t) => (
        <div key={t.who} className="cr-testimonial">
          <p className="cr-testimonial-quote">“{t.quote}”</p>
          <p className="cr-testimonial-who">{t.who}</p>
        </div>
      ))}
    </div>
  );
}

// Rotating 3D word sphere — the producer lingo, as a tag cloud.
// Mostly community mantras: r/synthesizers classics + r/audioengineering advice.
const SPHERE_WORDS = [
  "Just get Maths",
  "Maths is life",
  "Eurorack tax",
  "Cable spaghetti",
  "Knob twiddler",
  "West Coast",
  "East Coast",
  "Gain staging",
  "Trust your ears",
  "It depends",
  "Reference tracks",
  "Treat your room",
  "Don't mix in solo",
  "Leave headroom",
  "Take breaks",
  "Less is more",
  "Static mix first",
  "Don't chase loudness",
];

function spherePoints(n: number, radius: number) {
  // fibonacci sphere — words spread evenly over the ball
  const pts: { x: number; y: number; z: number }[] = [];
  const golden = Math.PI * (3 - Math.sqrt(5));
  for (let i = 0; i < n; i++) {
    const y = 1 - (i / (n - 1)) * 2;
    const r = Math.sqrt(Math.max(0, 1 - y * y));
    const theta = golden * i;
    pts.push({ x: Math.cos(theta) * r * radius, y: y * radius, z: Math.sin(theta) * r * radius });
  }
  return pts;
}

function WordSphere() {
  const pts = spherePoints(SPHERE_WORDS.length, 150);
  return (
    <div className="word-sphere" aria-hidden="true">
      <div className="word-sphere-rot">
        {SPHERE_WORDS.map((w, i) => (
          <span key={w} className="word-sphere-word" style={{ transform: `translate3d(${pts[i].x}px, ${pts[i].y}px, ${pts[i].z}px)` }}>
            {w}
          </span>
        ))}
      </div>
    </div>
  );
}

// Bento grid — the “big websites” trick: uneven tiles, each a glanceable
// fact about SoundHub, with micro-interactions on hover.
const BENTO = [
  {
    size: "wide",
    title: "Smart diff, not \"binary changed\"",
    text: "Between v12 and v13 SoundHub tells you exactly what moved: BPM 128 → 132, + Pad track, + Vital plugin. A revision is a story, never a mystery.",
  },
  {
    size: "tall",
    title: "Decision ledger",
    text: "Every request, approval and delivery is hashed into a tamper-evident chain — proof without trusting anyone.",
  },
  {
    size: "std",
    title: "Content-addressed",
    text: "Same file, one blob, any number of commits. Re-pushes deduplicate — a snapshot costs almost nothing.",
  },
  {
    size: "std",
    title: "Parsed, not guessed",
    text: "Tracks, plugins with settings, samples and loudness — extracted from .als, .cpr, .rpp and .flp.",
  },
  {
    size: "wide",
    title: "Review & approval loop",
    text: "Timestamped notes, structured rounds and role-gated sign-offs — the loop that actually ships a track.",
  },
  {
    size: "std",
    title: "Stems by logical name",
    text: "NeonBass_final_03.wav and bass_v13.wav both count as bass — A/B is matched by what the part is.",
  },
];

function BentoGrid() {
  const spot = (e: React.MouseEvent<HTMLDivElement>) => {
    const el = e.currentTarget;
    const r = el.getBoundingClientRect();
    el.style.setProperty("--mx", `${e.clientX - r.left}px`);
    el.style.setProperty("--my", `${e.clientY - r.top}px`);
  };
  return (
    <div className="bento">
      {BENTO.map((b) => (
        <div key={b.title} className={`bento-tile bento-${b.size}`} onMouseMove={spot}>
          <h3 className="bento-title">{b.title}</h3>
          <p className="bento-text">{b.text}</p>
        </div>
      ))}
    </div>
  );
}

// Comparison table: SoundHub vs the usual ways of sharing files.
function CompareTable() {
  return (
    <div className="cr-compare">
      <div className="cr-compare-head cr-compare-row">
        <span className="cr-compare-feature" />
        <span className="cr-compare-col soundhub">SoundHub</span>
        <span className="cr-compare-col">Discord</span>
        <span className="cr-compare-col">Drive</span>
        <span className="cr-compare-col">GitHub</span>
      </div>
      {COMPARE_ROWS.map((r) => (
        <div key={r.feature} className="cr-compare-row">
          <span className="cr-compare-feature">{r.feature}</span>
          <span className={`cr-compare-col soundhub ${r.soundhub ? "yes" : "no"}`}>{r.soundhub ? "✓" : "—"}</span>
          <span className={`cr-compare-col ${r.discord ? "yes" : "no"}`}>{r.discord ? "✓" : "—"}</span>
          <span className={`cr-compare-col ${r.drive ? "yes" : "no"}`}>{r.drive ? "✓" : "—"}</span>
          <span className={`cr-compare-col ${r.github ? "yes" : "no"}`}>{r.github ? "✓" : "—"}</span>
        </div>
      ))}
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
    setWaitlist(`You're on the list — we'll ping ${email} when the beta opens.`);
    setEmail("");
  };

  return (
    <div className="landing">

      {/* ---------- hero: headline + product screenshot in a browser frame ---------- */}
      <section className="cr-hero" id="top">
        <div className="cr-blob cr-blob-a" aria-hidden="true" />
        <div className="cr-blob cr-blob-b" aria-hidden="true" />
        <div className="cr-blob cr-blob-c" aria-hidden="true" />
        <div className="cr-hero-inner">
          <p className="cr-badge">Review · versions · approval — for music</p>
          <h1 className="cr-title">
            Music <RotatingWord words={HERO_WORDS} /> and approvals,<br />
            built for the way tracks are made.
          </h1>
          <p className="cr-sub">
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
        </div>
        <BrowserShot
          src="/screenshots/repo-page-demo.mp4"
          poster="/screenshots/repo-page.png"
          url="soundhub.local/projects/aurora-night"
          caption="A DAW project as a versioned repo — file tree with parsed tracks, plugins and smart diffs"
        />
      </section>

      {/* ---------- DAW strip: "works with" (CodeRabbit-style trust line) ---------- */}
      <div className="cr-daws">
        <p>Works with the DAWs you already use</p>
        <div className="cr-daws-row">
          <span>Ableton Live</span>
          <span>FL Studio</span>
          <span>Cubase</span>
          <span>REAPER</span>
        </div>
      </div>

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

      {/* ---------- feature tabs: Review / A/B / Diff ---------- */}
      <section className="bc-section cr-tabs-section" id="features">
        <h2 className="bc-h2">One tool, three superpowers</h2>
        <FeatureTabs />
      </section>

      {/* ---------- testimonials (honest community asks) ---------- */}
      <section className="bc-section">
        <h2 className="bc-h2">What producers keep asking for</h2>
        <Testimonials />
      </section>

      {/* ---------- comparison table ---------- */}
      <section className="bc-section" id="compare">
        <h2 className="bc-h2">SoundHub vs. the usual ways</h2>
        <CompareTable />
      </section>

      {/* ---------- feature: one workspace for every version ---------- */}
      <section className="bc-section cr-feature" id="versions">
        <div className="cr-feature-copy">            <h2 className="bc-h2 left">One <span className="grad">workspace</span> for every version</h2>
          <p>
            Every bounce lands in the same repo: v11 → v12 → v13, branches for
            clients and rounds, full history with DAW metadata. No more guessing
            which file is the current mix.
          </p>
          <ul className="cr-feature-list">
            <li>Branches per client / round (review/v12, main)</li>
            <li>Commits carry parsed tracks, plugins and their settings</li>
            <li>Re-pushes deduplicate — a snapshot costs almost nothing</li>
            <li>Public share links for reviewers, private for the rest</li>
          </ul>
        </div>
        <BrowserShot
          src="/screenshots/projects-demo.mp4"
          poster="/screenshots/projects.png"
          url="soundhub.local/projects"
          caption="Every project is a repo — open it, version it, share it"
        />
      </section>

      {/* ---------- smart diff ---------- */}
      <section className="bc-section" id="diff">
        <div className="bc-diff-grid">
          <div className="bc-diff-copy">
            <h2 className="bc-h2 left">Version your track like <span className="grad">music</span>, not bytes.</h2>
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

      {/* ---------- best-in-class context ---------- */}
      <section className="bc-section cr-context" id="context">
        <h2 className="bc-h2">Best-in-class context</h2>
        <p className="cr-context-sub">
          Across each step, we pull in dozens more points of context than other tools.
        </p>
        <div className="cr-context-grid">
          <div className="cr-context-muted">
            <div className="cr-context-head muted">What a shared file shows</div>
            <ul className="cr-context-others">
              {CONTEXT_OTHERS_SEE.map((x) => (
                <li key={x}>{x}</li>
              ))}
            </ul>
          </div>
          <div className="cr-context-rich">
            <div className="cr-context-head">What SoundHub extracts</div>
            <div className="cr-context-rows">
              {CONTEXT_WE_SEE.map((c) => (
                <div key={c.label} className="cr-context-row">
                  <span className="cr-context-label">{c.label}</span>
                  <span className="cr-context-value">{c.value}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
        <div className="cr-context-stats">
          {CONTEXT_STATS.map((s) => (
            <div key={s.label} className="cr-context-stat">
              <span className="cr-context-stat-n">{s.n}</span>
              <span className="cr-context-stat-label">{s.label}</span>
            </div>
          ))}
        </div>
      </section>

      {/* ---------- engine tabs: what the engine does per step ---------- */}
      <section className="bc-section cr-engine-section" id="engine">
        <h2 className="bc-h2">The engine behind every review</h2>
        <p className="cr-context-sub">
          Across each step, we extract dozens more points of context than a shared ZIP ever shows.
        </p>
        <EngineTabs />
      </section>

      {/* ---------- bento grid: glanceable facts ---------- */}
      <section className="bc-section" id="bento">
        <h2 className="bc-h2">Everything in one <span className="grad">glance</span></h2>
        <p className="cr-context-sub">
          No spreadsheets, no "which ZIP is current" — the workspace is built from blocks that each answer one question.
        </p>
        <BentoGrid />
      </section>

      {/* ---------- feature: push from the DAW ---------- */}
      <section className="bc-section cr-feature cr-feature-flip" id="daw">
        <div className="cr-feature-copy">
          <h2 className="bc-h2 left">Push from the DAW, review in the browser</h2>
          <p>
            `snd push` sends the current Live set (or a whole project folder) as
            one versioned commit — master and stems open a public review session
            with gapless A/B. The Max for Live panel puts that one button inside
            Ableton.
          </p>
          <ul className="cr-feature-list">
            <li>Preflight before upload: corrupt files are rejected, never sent</li>
            <li>Atomic push — a failed upload leaves no half-pushed version</li>
            <li>Stems attach by logical name: Kick→drums, Bass→bass…</li>
            <li>Stable JSON contract for automation (M4L, scripts)</li>
          </ul>
        </div>
        <BrowserShot
          src="/screenshots/branches-demo.mp4"
          poster="/screenshots/repo-page-branches.png"
          url="soundhub.local/projects/aurora-night/branches"
          caption="Branches per client and round — the DAW bridge pushes right into them"
        />
      </section>

      {/* ---------- daw-native track assets (bento, not duplicate cards) ---------- */}
      <section className="bc-section">
        <h2 className="bc-h2">DAW-native <span className="grad">track assets</span></h2>
        <p className="cr-context-sub">
          Versions aren't just audio files — SoundHub understands what a session is made
          of: tracks, plugins, stems and samples, straight from the DAW.
        </p>
        <div className="bento">
          {DAW_ASSETS.map((p) => (
            <div key={p.title} className="bento-tile">
              <h3 className="bento-title">{p.title}</h3>
              <p className="bento-text">{p.text}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ---------- built-in marketplace (second layer) ---------- */}
      <section className="bc-section" id="market">
        <h2 className="bc-h2">When a revision needs a sound, buy it in place</h2>
        <p className="bc-lead">
          The review workflow is the product. On-chain rails are the plumbing underneath it —
          escrowed payments, auditable licenses, a tamper-evident ledger — so the marketplace
          is a second layer, not the point of the tool.
        </p>
        <div className="bc-benefits">
          {MARKET_BENEFITS.map((t) => (
            <div key={t.title} className="bc-benefit">
              <div>
                <h3>{t.title}</h3>
                <p>{t.text}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* ---------- integrations ---------- */}
      <section className="bc-section" id="integrations">
        <h2 className="bc-h2">Where you make music</h2>
        <div className="bc-int">
          {INTEGRATIONS.map((i) => (
            <div key={i.name} className="bc-int-row">
              <span className="bc-int-name">{i.name}</span>
              <span className="bc-int-detail">{i.detail}</span>
              <span className={`bc-status ${i.status}`}>{i.status}</span>
              {i.href && (
                <Link to={i.href} className="bc-int-link">
                  Page →
                </Link>
              )}
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

      {/* ---------- pricing ---------- */}
      <section className="bc-section" id="pricing">
        <h2 className="bc-h2">Simple plans — beta pricing, honest</h2>
        <div className="cr-plans">
          {PLANS.map((pl) => (
            <div key={pl.name} className={`cr-plan ${pl.featured ? "featured" : ""}`}>
              <h3 className="cr-plan-name">{pl.name}</h3>
              <div className="cr-plan-price">{pl.price}</div>
              <div className="cr-plan-note">{pl.note}</div>
              <ul className="cr-plan-features">
                {pl.features.map((f) => <li key={f}>{f}</li>)}
              </ul>
              {pl.href ? (
                <Link to={pl.href} className="bc-btn bc-btn-primary">{pl.cta}</Link>
              ) : (
                <button type="button" className={`bc-btn ${pl.featured ? "bc-btn-primary" : "bc-btn-ghost"}`} onClick={joinWaitlist}>
                  {pl.cta}
                </button>
              )}
            </div>
          ))}
        </div>
        <p className="bc-status-note">
          Beta pricing — final tiers land after the user-test round. The review loop is free for everyone.
        </p>
      </section>

      {/* ---------- FAQ ---------- */}
      <section className="bc-section" id="faq">
        <h2 className="bc-h2">Questions, answered</h2>
        <div className="bc-faq">
          {FAQ.map((f) => (
            <details key={f.q} className="bc-faq-item" open>
              <summary>{f.q}</summary>
              <p>{f.a}</p>
            </details>
          ))}
        </div>
      </section>

      {/* ---------- producer lingo word sphere ---------- */}
      <section className="bc-section word-sphere-section">
        <h2 className="bc-h2">Speak the language</h2>
        <p className="bc-lead">
          Just get Maths, trust your ears, treat your room — the mantras producers actually live by.
        </p>
        <WordSphere />
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

      {/* ---------- docs ---------- */}
      <section className="bc-section" id="docs">
        <p className="bc-eyebrow center" style={{ display: "block", marginBottom: 14 }}>Documentation</p>
        <h2 className="bc-h2">Read the docs</h2>
        <div className="docs-landing-grid">
          <Link to="/docs" className="docs-landing-card docs-landing-primary">
            <strong>Docs hub</strong>
            <span>Core loop, snd push, review sessions, roles and honest limits — a user guide on one page.</span>
            <em>Open the guide →</em>
          </Link>
          <a href="/Whitepaper.pdf" className="docs-landing-card">
            <strong>Whitepaper (PDF)</strong>
            <span>18 pages — architecture, formulas, tokenomics, governance.</span>
            <em>Read the whitepaper →</em>
          </a>
          <a href="https://github.com/soundXlab/SoundHub/blob/main/LITEPAPER.md" target="_blank" rel="noopener noreferrer" className="docs-landing-card">
            <strong>Litepaper</strong>
            <span>The product in one page: problem, solution, layers, roadmap.</span>
            <em>Read the litepaper →</em>
          </a>
          <a href="https://github.com/soundXlab/SoundHub/blob/main/CHANGELOG.md" target="_blank" rel="noopener noreferrer" className="docs-landing-card">
            <strong>Changelog</strong>
            <span>Release notes — what changed, how to test, known limits.</span>
            <em>See the changelog →</em>
          </a>
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
            <a href="#features">Features</a>
            <a href="#diff">Smart diff</a>
            <a href="#context">Context</a>
            <a href="#compare">Compare</a>
            <a href="#pricing">Pricing</a>
            <a href="#versions">Versions</a>
            <a href="#daw">DAW bridge</a>
            <a href="#market">Marketplace</a>
            <a href="#faq">FAQ</a>
            <Link to="/docs">Docs</Link>
          </div>
          <div className="bc-footer-col">
            <h4>DAWs</h4>
            <a href="#daw">Ableton Live · available</a>
            <Link to="/integrations/fl-studio">FL Studio · available</Link>
            <Link to="/integrations/cubase">Cubase · available</Link>
            <a href="#daw">REAPER · planned</a>
          </div>
          <div className="bc-footer-col">
            <h4>Ecosystem</h4>
            <Link to={SAMPLE_REVIEW_URL}>Open a sample review</Link>
            <Link to="/market">Marketplace</Link>
            <Link to="/kettle">Kettle for beginners</Link>
            <a href="https://github.com/soundXlab/SoundHub" target="_blank" rel="noopener noreferrer">GitHub · open source</a>
          </div>
        </div>
        <div className="bc-footer-giant" aria-hidden="true">
          <img src="/logo.png" alt="" className="bc-footer-giant-img" />
        </div>
        <div className="bc-footer-legal">
          <a href="/terms">Terms of Service</a>
          <span className="bc-footer-legal-sep">·</span>
          <a href="/privacy">Privacy Policy</a>
          <span className="bc-footer-legal-copy">SoundHub, Inc. © {new Date().getFullYear()}</span>
        </div>
      </footer>

      {showWorkflow && <WorkflowModal onClose={() => setShowWorkflow(false)} />}
    </div>
  );
}
