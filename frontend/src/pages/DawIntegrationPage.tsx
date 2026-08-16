import { Link } from "react-router-dom";

// A standalone integration page for one DAW. The accent color is set via the
// `--daw-accent` CSS variable on the wrapper (see .daw-int in styles.css),
// so Cubase gets its blue and FL Studio its orange without duplicating markup.

interface DawSpec {
  name: string;
  tagline: string;
  intro: string;
  status: string;
  accentVar: string;
  shot: string;
  shotUrl: string;
  shotCaption: string;
  parsed: { label: string; value: string }[];
  workflow: string[];
  formats: string[];
  next: string;
}

export default function DawIntegrationPage({ daw }: { daw: DawSpec }) {
  return (
    <div className="daw-int" style={{ "--daw-accent": daw.accentVar } as React.CSSProperties}>
      <section className="daw-int-hero">
        <p className="daw-int-badge">
          <span className="daw-int-dot" /> {daw.status}
        </p>
        <h1 className="daw-int-title">{daw.name}</h1>
        <p className="daw-int-tagline">{daw.tagline}</p>
        <p className="daw-int-intro">{daw.intro}</p>
        <div className="bc-cta">
          <a href="#parsed" className="bc-btn bc-btn-primary">See what we parse</a>
          <Link to="/" className="bc-btn bc-btn-ghost">← Back to SoundHub</Link>
        </div>
      </section>

      <section className="daw-int-shot">
        <div className="daw-int-shot-frame">
          <div className="cr-shot-bar">
            <span className="dot" />
            <span className="dot" />
            <span className="dot" />
            <span className="cr-shot-url">{daw.shotUrl}</span>
          </div>
          <img src={daw.shot} alt={`${daw.name} project parsed in SoundHub`} loading="lazy" />
        </div>
        <p className="daw-int-shot-cap">{daw.shotCaption}</p>
      </section>

      <section className="daw-int-block" id="parsed">
        <h2 className="bc-h2 left">What we extract from a {daw.name} project</h2>
        <div className="daw-int-grid">
          {daw.parsed.map((p) => (
            <div key={p.label} className="daw-int-cell">
              <dt>{p.label}</dt>
              <dd>{p.value}</dd>
            </div>
          ))}
        </div>
      </section>

      <section className="daw-int-block">
        <h2 className="bc-h2 left">Push from {daw.name} to review</h2>
        <ul className="cr-feature-list">
          {daw.workflow.map((w) => (
            <li key={w}>{w}</li>
          ))}
        </ul>
      </section>

      <section className="daw-int-block">
        <h2 className="bc-h2 left">Supported project files</h2>
        <div className="daw-int-chips">
          {daw.formats.map((f) => (
            <span key={f} className="daw-int-chip">{f}</span>
          ))}
        </div>
        <p className="daw-int-next">{daw.next}</p>
      </section>

      <section className="bc-section" style={{ textAlign: "center" }}>
        <Link to="/" className="bc-btn bc-btn-primary">Back to SoundHub</Link>
      </section>
    </div>
  );
}
