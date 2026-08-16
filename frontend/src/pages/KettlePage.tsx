import { Link } from "react-router-dom";

/* Kettle — the corner for noobs, novices and everyone who just wants the
   workflow explained without the jargon. The kettle logo is drawn inline
   (SVG) so it ships with the page. */

function KettleLogo({ size = 96 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 120 120" fill="none" aria-label="Kettle" role="img">
      {/* steam */}
      <path d="M52 22c0-6 8-6 8-12M70 18c0-5 7-5 7-10M88 22c0-6 8-6 8-12" stroke="#ff5e1a" strokeWidth="5" strokeLinecap="round" />
      {/* lid + knob */}
      <ellipse cx="70" cy="38" rx="34" ry="8" fill="#2b3148" />
      <circle cx="70" cy="30" r="6" fill="#ff5e1a" />
      {/* body */}
      <path d="M36 42h68a30 30 0 0 1-30 36H66a30 30 0 0 1-30-36Z" fill="#3a4157" />
      {/* spout */}
      <path d="M92 50c14-2 18 10 10 14-6 3-12 0-12-6" stroke="#3a4157" strokeWidth="9" strokeLinecap="round" />
      {/* handle */}
      <path d="M42 50c-12 4-16-6-8-10" stroke="#2b3148" strokeWidth="9" strokeLinecap="round" />
      {/* shine */}
      <path d="M48 52a18 18 0 0 0 8 20" stroke="#ff5e1a" strokeWidth="4" strokeLinecap="round" opacity="0.7" />
    </svg>
  );
}

const STEPS = [
  {
    n: "1",
    title: "Upload a version",
    text: "A version is one audio file — your mix, a demo, a take. SoundHub calls it v1, v2, v3… so nobody has to rename final_final_2 (v2 real).wav ever again.",
  },
  {
    n: "2",
    title: "Share the private link",
    text: "You get a link like soundhub.app/r/abc123. Send it to your client, your bandmate, your A&R. They don't need an account — they just open it and listen.",
  },
  {
    n: "3",
    title: "Comments pinned to moments",
    text: "“01:24 — bass masks the vocal” lands exactly at 01:24. Click a comment and the track jumps there. No more “you know, that part around the middle-ish”.",
  },
  {
    n: "4",
    title: "Fix, upload the next version",
    text: "Make the change in your DAW, upload v2. Your old requests get marked “fixed in v2”, and you can A/B the two versions to prove the fix — level-matched, so louder isn't confused with better.",
  },
  {
    n: "5",
    title: "Approve and deliver",
    text: "When everyone's happy, the version is Approved. You lock the final package, and the client gets a delivery link with the real files — checksummed so nothing gets swapped.",
  },
];

const GLOSSARY = [
  { term: "Bounce", def: "Exporting audio out of your DAW (Logic, Ableton, FL…) into a file. The thing you upload as a version." },
  { term: "Version", def: "One exported audio file in a session. v1, v2, v13 — every bounce keeps its own history and comments." },
  { term: "Master", def: "The final, finished mix of a track — the one that goes to the label, the store, the world." },
  { term: "Stems", def: "Submixes of a track: drums, bass, vocals, synths, each in its own file. Useful for pinpointing what changed between versions." },
  { term: "LUFS", def: "A measure of how loud a track feels. SoundHub level-matches versions before you A/B them, so you compare the mix, not the volume knob." },
  { term: "A/B compare", def: "Listening to two versions back to back from the same moment. Great for proving “it's better now” instead of hoping." },
  { term: "Revision round", def: "One complete cycle of feedback → fixes. Rounds keep revisions controlled — everyone knows what round we're on, and what's included in the deal." },
  { term: "Feedback owner", def: "The person who collects everyone's draft notes and submits one consolidated list. One round, one list, no chaos." },
  { term: "Approval", def: "An explicit thumbs-up (or “needs changes”) recorded against a version and a scope — mix, master, arrangement, release." },
  { term: "Watermark", def: "An audible beep mixed into previews that aren't approved yet, so a leaked demo can't pass for the final file." },
  { term: "Release package", def: "The locked set of final deliverables (master, instrumental, artwork…) with checksums. Immutable — nobody can silently swap the approved master." },
  { term: "Decision ledger", def: "A tamper-evident history of every decision in a session — who approved what, when. Verifiable, not just a chat log." },
  { term: "Deposit", def: "Money paid up front to book the work. Engineers love them; SoundHub can gate the final delivery on one." },
  { term: "Invoice / delivery gate", def: "When a balance is due, downloads stay locked (HTTP 402) until it's paid — card, Apple Pay or Google Pay, no account needed." },
];

const FAQ = [
  {
    q: "Do I need a DAW to use SoundHub?",
    a: "No. Uploading audio and reviewing works from any browser. The DAW integrations (Ableton, FL, Cubase) are extras — the review loop doesn't need them.",
  },
  {
    q: "Does the reviewer need an account?",
    a: "No. Reviewers open the private link, type their name, and leave comments. That's it. No signup, no wallet, no app to install.",
  },
  {
    q: "What does “watermarked preview” mean?",
    a: "Until a version is approved, guests hear the audio with a soft beep mixed in. It keeps unapproved demos from leaking as “the final file”. Approved versions and paid deliveries are clean.",
  },
  {
    q: "What if I don't understand a word on this page?",
    a: "That's exactly what Kettle is for. The glossary above covers the whole workflow — if something's still unclear, ask your engineer. They love explaining (usually).",
  },
];

export default function KettlePage() {
  return (
    <div className="landing kettle">

      <section className="kettle-hero" id="top">
        <div className="kettle-logo">
          <KettleLogo size={110} />
        </div>
        <p className="bc-eyebrow">🫖 Kettle — the newbie corner</p>
        <h1 className="bc-title">
          Music review &amp; approvals,
          <br />
          explained like you're new.
        </h1>
        <p className="bc-sub kettle-sub">
          You make music. Maybe you've never “sent a mix for approval” before. This page
          explains the whole SoundHub loop in plain words — what everything means, what
          each button does, and what not to worry about.
        </p>
        <div className="bc-cta">
          <a href="#steps" className="bc-btn bc-btn-primary">Show me how it works</a>
          <Link to="/session" className="bc-btn bc-btn-ghost">Skip to the demo</Link>
        </div>
      </section>

      <section className="bc-section" id="steps">
        <p className="bc-eyebrow center" style={{ display: "block", marginBottom: 14 }}>The loop, step by step</p>
        <h2 className="bc-h2">Your first review session in 5 steps</h2>
        <div className="bc-steps">
          {STEPS.map((s) => (
            <div key={s.n} className="bc-step">
              <span className="bc-step-n">{s.n}</span>
              <div className="bc-step-body">
                <h3>{s.title}</h3>
                <p>{s.text}</p>
              </div>
            </div>
          ))}
        </div>
        <div className="kettle-banner">
          <span className="kettle-banner-icon">💡</span>
          <p>
            The golden rule: <strong>one version at a time, one consolidated list of feedback per round.</strong>{" "}
            That's the whole trick. Everything else on this page is details.
          </p>
        </div>
      </section>

      <section className="bc-section" id="glossary">
        <p className="bc-eyebrow center" style={{ display: "block", marginBottom: 14 }}>The glossary</p>
        <h2 className="bc-h2">Every word, translated</h2>
        <div className="kettle-glossary">
          {GLOSSARY.map((g) => (
            <div key={g.term} className="kettle-term">
              <h3>{g.term}</h3>
              <p>{g.def}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="bc-section" id="faq">
        <p className="bc-eyebrow center" style={{ display: "block", marginBottom: 14 }}>Still curious?</p>
        <h2 className="bc-h2">Questions you might actually have</h2>
        <div className="bc-faq">
          {FAQ.map((f) => (
            <details key={f.q} className="bc-faq-item" open>
              <summary>{f.q}</summary>
              <p>{f.a}</p>
            </details>
          ))}
        </div>
      </section>

      <section className="bc-cta-final">
        <h2 className="bc-h2">Ready to stop emailing audio files?</h2>
        <p>Create a session, upload a bounce, and see the loop yourself.</p>
        <div className="bc-cta-final-alts">
          <Link to="/session">try the demo session now →</Link>
          <Link to="/">or go back to the main page →</Link>
        </div>
      </section>

      <footer className="bc-footer">
        <div className="bc-footer-grid">
          <div className="bc-footer-brand">
            <img src="/logo.png" alt="SoundHub" className="bc-logo" />
            <p>Review, versions and approvals for music.</p>
          </div>
          <div className="bc-footer-col">
            <h4>Learn</h4>
            <a href="#steps">How it works</a>
            <a href="#glossary">Glossary</a>
            <Link to="/session">Demo session</Link>
          </div>
        </div>
        <p className="bc-footer-bottom">
          Kettle · the friendliest room in SoundHub · © {new Date().getFullYear()}
        </p>
      </footer>
    </div>
  );
}
