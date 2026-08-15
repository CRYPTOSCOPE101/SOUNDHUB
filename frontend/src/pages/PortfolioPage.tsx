import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api";
import { fmtTime, type Portfolio, type PortfolioTrack } from "../types";

export default function PortfolioPage() {
  const { username } = useParams<{ username: string }>();
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [playing, setPlaying] = useState<number | null>(null); // session_id currently playing
  const audioRefs = new Map<number, HTMLAudioElement>();

  const load = useCallback(async () => {
    if (!username) return;
    setLoaded(false);
    setErr(null);
    try {
      setPortfolio(await api.portfolioGet(username));
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Portfolio not found");
    } finally {
      setLoaded(true);
    }
  }, [username]);

  useEffect(() => {
    void load();
  }, [load]);

  const togglePlay = (t: PortfolioTrack, el: HTMLAudioElement | null) => {
    if (!el) return;
    if (playing === t.session_id) {
      el.pause();
      setPlaying(null);
      return;
    }
    audioRefs.forEach((a) => a.pause());
    void el.play().catch(() => undefined);
    setPlaying(t.session_id);
  };

  if (err) {
    return (
      <div className="session-page">
        <div className="card error">🔗 {err} — this engineer doesn't have a public portfolio.</div>
      </div>
    );
  }

  if (!loaded || !portfolio) {
    return <div className="session-page muted">Loading portfolio…</div>;
  }

  return (
    <div className="portfolio">
      <div className="public-delivery-brand">
        <img src="/logo.png" alt="SoundHub" className="landing-nav-logo" /> SoundHub
        <span className="public-review-sep">·</span>
        <span className="public-review-for">public portfolio</span>
      </div>

      <div className="portfolio-head">
        <div className="portfolio-avatar">{portfolio.username[0]?.toUpperCase() ?? "?"}</div>
        <div>
          <h1 className="portfolio-name">{username}</h1>
          <p className="muted">
            Approved work, shared by the engineer. Clean files arrive through the delivery link —
            previews here carry a watermark.
          </p>
        </div>
      </div>

      {portfolio.track_count === 0 ? (
        <div className="card muted" style={{ maxWidth: 640, margin: "40px auto", textAlign: "center" }}>
          No public tracks yet. When the engineer marks a session “show on public portfolio”, it lands here.
        </div>
      ) : (
        <div className="portfolio-grid">
          {portfolio.tracks.map((t) => (
            <div key={t.session_id} className={`portfolio-card ${t.has_approved ? "ok" : ""}`}>
              <div className="portfolio-card-head">
                <span className="portfolio-card-title">{t.name}</span>
                {t.has_approved && <span className="rs-release-status st-ready">APPROVED</span>}
              </div>

              {t.has_approved ? (
                <>
                  <div className="portfolio-card-meta">
                    <span>{t.approved_label}</span>
                    <span>·</span>
                    <span>{t.approved_filename}</span>
                  </div>
                  <div className="portfolio-card-meta muted">
                    {t.approved_duration_s > 0 ? fmtTime(t.approved_duration_s) : "—"} · {t.version_count} version
                    {t.version_count === 1 ? "" : "s"}
                    {t.approved_at ? ` · approved ${new Date(t.approved_at).toLocaleDateString()}` : ""}
                  </div>
                  <div className="portfolio-card-actions">
                    <button
                      type="button"
                      className="rs-btn ghost sm"
                      onClick={(e) =>
                        togglePlay(t, (e.currentTarget.parentElement?.parentElement?.querySelector("audio") as HTMLAudioElement) ?? null)
                      }
                    >
                      {playing === t.session_id ? "❚❚ Pause" : "▶ Preview (watermarked)"}
                    </button>
                    {t.delivery_token && (
                      <Link to={`/d/${t.delivery_token}`} className="rs-btn approve sm">
                        📦 Delivery
                      </Link>
                    )}
                  </div>
                  <audio
                    src={t.approved_version_id ? api.audioUrl(api.portfolioPreviewUrl(portfolio.username, t.approved_version_id)) : undefined}
                    preload="none"
                    onEnded={() => setPlaying((p) => (p === t.session_id ? null : p))}
                    ref={(el) => {
                      if (el) audioRefs.set(t.session_id, el);
                    }}
                    className="portfolio-audio"
                  />
                </>
              ) : (
                <div className="portfolio-card-meta muted">No approved version yet</div>
              )}
            </div>
          ))}
        </div>
      )}

      <p className="portfolio-note muted">
        Want this showcase for your own sessions? Open a session → share settings → “Show on public portfolio”.
      </p>
    </div>
  );
}
