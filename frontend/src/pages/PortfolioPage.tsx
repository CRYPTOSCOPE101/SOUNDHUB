import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import { fmtTime, type Portfolio, type PortfolioTrack } from "../types";

export default function PortfolioPage() {
  const { username } = useParams<{ username: string }>();
  const { user } = useAuth();
  const isOwner = user?.username === username;
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [playing, setPlaying] = useState<number | null>(null); // session_id currently playing
  const audioRefs = new Map<number, HTMLAudioElement>();
  // profile editing (owner only)
  const [bio, setBio] = useState("");
  const [specialty, setSpecialty] = useState("");
  const [location, setLocation] = useState("");
  const [editMsg, setEditMsg] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);

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

  useEffect(() => {
    if (portfolio?.reputation) {
      setBio(portfolio.reputation.bio);
      setSpecialty(portfolio.reputation.specialty);
      setLocation(portfolio.reputation.location);
    }
  }, [portfolio]);

  const saveProfile = async () => {
    setEditMsg(null);
    try {
      await api.updateProfile({ bio, specialty, location });
      setEditMsg("Profile saved — shown on your public portfolio.");
      setEditing(false);
      void load();
    } catch (e) {
      setEditMsg(e instanceof Error ? e.message : "Save failed");
    }
  };

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
        <img src="/logo.png" alt="SoundHub" className="landing-nav-logo" />
        <span className="public-review-sep">·</span>
        <span className="public-review-for">public portfolio</span>
      </div>

      <div className="portfolio-head">
        <div className="portfolio-avatar">{portfolio.username[0]?.toUpperCase() ?? "?"}</div>
        <div>
          <h1 className="portfolio-name">
            {username}{" "}
            {portfolio.reputation?.verified && (
              <span className="rep-verified" title="Wallet-linked identity — verified by signature at login">
                ✓ Verified
              </span>
            )}
          </h1>
          <p className="muted">
            Approved work, shared by the engineer. Clean files arrive through the delivery link —
            previews here carry a watermark.
          </p>
        </div>
      </div>

      {/* reputation: objective trust signals + seller profile */}
      {portfolio.reputation && (
        <div className="rep-panel">
          <div className="rep-stats">
            <div className="rep-stat">
              <span className="rep-stat-num">{portfolio.reputation.delivered_count}</span>
              <span className="rep-stat-label">delivered packages</span>
            </div>
            <div className="rep-stat">
              <span className="rep-stat-num">{portfolio.reputation.approved_count}</span>
              <span className="rep-stat-label">approved sessions</span>
            </div>
            <div className="rep-stat">
              <span className="rep-stat-num">
                {portfolio.reputation.avg_rounds != null ? portfolio.reputation.avg_rounds : "—"}
              </span>
              <span className="rep-stat-label">avg rounds to approve</span>
            </div>
            {portfolio.reputation.on_time_rate != null && (
              <div className="rep-stat">
                <span className="rep-stat-num">
                  {Math.round(portfolio.reputation.on_time_rate * 100)}%
                </span>
                <span className="rep-stat-label">on-time deliveries</span>
              </div>
            )}
          </div>
          {portfolio.reputation.badges.length > 0 && (
            <div className="rep-badges">
              {portfolio.reputation.badges.map((b) => (
                <span key={b} className="chip">
                  {b}
                </span>
              ))}
            </div>
          )}
          {(portfolio.reputation.specialty || portfolio.reputation.bio || portfolio.reputation.location) && (
            <div className="rep-bio">
              {portfolio.reputation.specialty && (
                <span className="chip rep-specialty">{portfolio.reputation.specialty}</span>
              )}
              {portfolio.reputation.location && (
                <span className="muted rep-location">📍 {portfolio.reputation.location}</span>
              )}
              {portfolio.reputation.bio && <p className="rep-bio-text">{portfolio.reputation.bio}</p>}
            </div>
          )}
          <p className="rep-note muted">
            Numbers are computed from this engineer's real sessions, approvals and deliveries — nothing is
            self-reported.
          </p>
          {isOwner && !editing && (
            <button type="button" className="rs-btn ghost sm" onClick={() => setEditing(true)}>
              ✏️ Edit profile
            </button>
          )}
          {isOwner && editing && (
            <div className="rep-edit">
              <label>
                Specialty
                <select value={specialty} onChange={(e) => setSpecialty(e.target.value)}>
                  <option value="">—</option>
                  <option value="mix">Mix</option>
                  <option value="master">Master</option>
                  <option value="mix_master">Mix + Master</option>
                  <option value="production">Production</option>
                  <option value="stems">Stem delivery</option>
                </select>
              </label>
              <label>
                Location
                <input
                  type="text"
                  value={location}
                  onChange={(e) => setLocation(e.target.value)}
                  placeholder="e.g. Berlin"
                />
              </label>
              <label className="rep-bio-label">
                Bio
                <textarea value={bio} onChange={(e) => setBio(e.target.value)} rows={3} placeholder="How you work, what you're known for…" />
              </label>
              <div className="rep-edit-actions">
                <button type="button" className="rs-btn approve sm" onClick={() => void saveProfile()}>
                  Save
                </button>
                <button type="button" className="rs-btn ghost sm" onClick={() => setEditing(false)}>
                  Cancel
                </button>
              </div>
              {editMsg && <p className="rep-edit-msg">{editMsg}</p>}
            </div>
          )}
        </div>
      )}

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
