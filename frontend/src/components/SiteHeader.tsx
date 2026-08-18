import { useEffect, useRef, useState, type ReactNode } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import { errorMessage, reportError } from "../errors";
import type { SearchResults } from "../types";

interface SiteHeaderProps {
  theme: "light" | "dark";
  onToggleTheme: () => void;
}

/* ---------- tiny inline icons (stroke, currentColor) ---------- */

function Icon({ d, extra }: { d: string; extra?: string }) {
  return (
    <svg
      width="15"
      height="15"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d={d} />
      {extra && <path d={extra} />}
    </svg>
  );
}

const ICONS: Record<string, ReactNode> = {
  workflow: <Icon d="M21 12a9 9 0 1 1-2.6-6.4M21 3v6h-6" />, // loop — the review loop
  diff: <Icon d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z" extra="M12 11v6M9 14h6" />, // file + plus
  market: <Icon d="M6 7h12l1.2 13H4.8z" extra="M9 10V6a3 3 0 0 1 6 0v4" />, // shopping bag
  faq: <Icon d="M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z" extra="M9.6 9a2.4 2.4 0 1 1 3.3 2.2c-.8.3-.9.9-.9 1.6M12 16.6h.01" />, // question
  sessions: <Icon d="M3 12h2l2-8 3 16 3-12 2 4h6" />, // waveform pulse
  portfolio: <Icon d="M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8z" extra="M4 21c0-4 3.6-6 8-6s8 2 8 6" />, // user
  dao: <Icon d="M4 4h16v16H4z" extra="M8.5 12.5l2 2 5-5" />, // ballot / vote
  repo: <Icon d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20V3H6.5A2.5 2.5 0 0 0 4 5.5z" extra="M4 19.5A2.5 2.5 0 0 0 6.5 22H20v-5" />, // book
  cubase: <Icon d="M12 3l8 4.5v9L12 21l-8-4.5v-9z" extra="M12 12l8-4.5M12 12v9M12 12L4 7.5" />, // cube — Cubase
  fl: <Icon d="M4 6h16M4 10h10M4 14h16M4 18h7" />, // playlist rows — FL Studio
};

interface SubnavItem {
  key: string;
  label: string;
  to: string; // "#hash" for landing sections, or a route path
  icon: ReactNode;
  kind: "anchor" | "route";
}

const SAMPLE_REVIEW_URL = "/r/demo-review-token";

/* ---------- live search (same as the old landing header) ---------- */

function HeaderSearch() {
  const navigate = useNavigate();
  const [q, setQ] = useState("");
  const [results, setResults] = useState<SearchResults | null>(null);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const boxRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onDocClick = (e: MouseEvent) => {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, []);

  useEffect(() => {
    const query = q.trim();
    if (!query) {
      setResults(null);
      setSearchError(null);
      setOpen(false);
      return;
    }
    setBusy(true);
    const t = setTimeout(() => {
      api
        .search(query)
        .then((r) => {
          setResults(r);
          setSearchError(null);
          setOpen(true);
        })
        .catch((e: unknown) => {
          reportError(`search for "${query}"`, e);
          setResults({ query, engineers: [], sessions: [] });
          setSearchError(errorMessage(e, "Search is unavailable right now."));
          setOpen(true);
        })
        .finally(() => setBusy(false));
    }, 200);
    return () => clearTimeout(t);
  }, [q]);

  const total = (results?.engineers.length ?? 0) + (results?.sessions.length ?? 0);

  const go = (to: string) => {
    setOpen(false);
    setQ("");
    navigate(to);
  };

  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === "Escape") {
      setOpen(false);
      return;
    }
    if (e.key === "Enter") {
      if (results?.engineers.length) go(`/p/${results.engineers[0].username}`);
      else if (results?.sessions.length) go(`/r/${results.sessions[0].share_token}`);
    }
  };

  return (
    <div className="bc-search" ref={boxRef}>
      <div className="bc-search-box">
        <svg className="bc-search-icon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
          <circle cx="11" cy="11" r="7" />
          <path d="m21 21-4.3-4.3" />
        </svg>
        <input
          type="search"
          placeholder="Search engineers &amp; sessions"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onFocus={() => {
            if (searchError || (results && total > 0)) setOpen(true);
          }}
          onKeyDown={onKey}
          aria-label="Search"
        />
        {busy && <span className="bc-search-busy">…</span>}
      </div>
      {open && results && q.trim() && (
        <div className="bc-search-menu">
          {searchError && <div className="bc-search-empty">Search failed: {searchError}</div>}
          {!searchError && total === 0 && (
            <div className="bc-search-empty">Nothing public found for “{q.trim()}”.</div>
          )}
          {results.engineers.length > 0 && (
            <>
              <div className="bc-search-group">Engineers</div>
              {results.engineers.map((e) => (
                <button key={e.username} type="button" className="bc-search-item" onClick={() => go(`/p/${e.username}`)}>
                  <span className="bc-search-avatar">{e.username[0]?.toUpperCase() ?? "?"}</span>
                  <span className="bc-search-title">{e.username}</span>
                  <span className="bc-search-meta">
                    {e.session_count} public session{e.session_count === 1 ? "" : "s"}
                  </span>
                </button>
              ))}
            </>
          )}
          {results.sessions.length > 0 && (
            <>
              <div className="bc-search-group">Public sessions</div>
              {results.sessions.map((s) => (
                <button key={s.share_token} type="button" className="bc-search-item" onClick={() => go(`/r/${s.share_token}`)}>
                  <span className="bc-search-avatar">{s.name[0]?.toUpperCase() ?? "?"}</span>
                  <span className="bc-search-title">{s.name}</span>
                  <span className="bc-search-meta">by {s.owner_username}</span>
                </button>
              ))}
            </>
          )}
        </div>
      )}
    </div>
  );
}

/* ---------- the two-row bandcamp-style header ---------- */

export default function SiteHeader({ theme, onToggleTheme }: SiteHeaderProps) {
  const { user, logout } = useAuth();
  const location = useLocation();
  const onLanding = location.pathname === "/" || location.pathname === "/kettle";

  // All "other pages" live in the second row, bandcamp-style.
  const subnav: SubnavItem[] = [
    { key: "workflow", label: "Workflow", to: onLanding ? "#workflow" : "/#workflow", icon: ICONS.workflow, kind: "anchor" },
    { key: "diff", label: "Smart diff", to: onLanding ? "#diff" : "/#diff", icon: ICONS.diff, kind: "anchor" },
    { key: "docs", label: "Docs", to: "/docs", icon: <Icon d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20V3H6.5A2.5 2.5 0 0 0 4 5.5z" extra="M9 7h6M9 11h6" />, kind: "route" },
    { key: "wiki", label: "Wiki", to: "https://deepwiki.com/soundXlab/SoundHub", icon: <Icon d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />, kind: "anchor" },
    { key: "cubase", label: "Cubase", to: "/integrations/cubase", icon: ICONS.cubase, kind: "route" },
    { key: "fl", label: "FL Studio", to: "/integrations/fl-studio", icon: ICONS.fl, kind: "route" },
    { key: "market", label: "Marketplace", to: onLanding ? "#market" : "/#market", icon: ICONS.market, kind: "anchor" },
    { key: "faq", label: "FAQ", to: onLanding ? "#faq" : "/#faq", icon: ICONS.faq, kind: "anchor" },
  ];
  if (user) {
    subnav.push(
      { key: "sessions", label: "Sessions", to: "/sessions", icon: ICONS.sessions, kind: "route" },
      { key: "portfolio", label: "Portfolio", to: `/p/${user.username}`, icon: ICONS.portfolio, kind: "route" },
      { key: "market-app", label: "Market", to: "/market", icon: ICONS.market, kind: "route" },
      { key: "dao", label: "DAO", to: "/dao", icon: ICONS.dao, kind: "route" },
      { key: "repo", label: "Repo", to: "/github", icon: ICONS.repo, kind: "route" }
    );
  }
  subnav.push({ key: "kettle", label: "Kettle", to: "/kettle", icon: <span className="bc-subnav-emoji">🫖</span>, kind: "route" });

  return (
    <header className="bc-site-header">
      <div className="bc-top">
        <Link to="/" className="bc-brand" title="SoundHub">
          <img src="/logo.png" alt="SoundHub" className="bc-logo" />
        </Link>

        <HeaderSearch />

        <div className="bc-auth">
          {user ? (
            <>
              <span className="bc-auth-user">{user.username}</span>
              <button className="bc-icon-btn" onClick={onToggleTheme} title="Toggle theme">
                {theme === "light" ? "🌙" : "☀️"}
              </button>
              <button className="bc-auth-logout" onClick={logout}>
                Log out
              </button>
            </>
          ) : (
            <>
              <Link to="/login?mode=register" className="bc-auth-signup">Sign up</Link>
              <Link to="/login" className="bc-auth-login">Log in</Link>
            </>
          )}
        </div>
      </div>

      <nav className="bc-subnav" aria-label="Site">
        <div className="bc-subnav-inner">
          {subnav.map((item) =>
            item.kind === "anchor" ? (
              <a key={item.key} href={item.to} className="bc-subnav-link">
                {item.icon}
                {item.label}
              </a>
            ) : (
              <Link key={item.key} to={item.to} className="bc-subnav-link">
                {item.icon}
                {item.label}
              </Link>
            )
          )}
          {!user && (
            <Link to={SAMPLE_REVIEW_URL} className="bc-subnav-link bc-subnav-sample">
              <Icon d="M8 5v14l11-7z" />
              Sample review
            </Link>
          )}
        </div>
      </nav>
    </header>
  );
}
