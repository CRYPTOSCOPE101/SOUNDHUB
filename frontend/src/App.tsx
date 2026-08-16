import { useEffect, useState } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { isLoggedIn } from "./auth";
import SiteHeader from "./components/SiteHeader";
import BranchesPage from "./pages/BranchesPage";
import CommitPage from "./pages/CommitPage";
import DiffPage from "./pages/DiffPage";
import DAOPage from "./pages/DAOPage";
import GitHubRepoPage from "./pages/GitHubRepoPage";
import KettlePage from "./pages/KettlePage";
import LandingPage from "./pages/LandingPage";
import LoginPage from "./pages/LoginPage";
import PortfolioPage from "./pages/PortfolioPage";
import PublicDeliveryPage from "./pages/PublicDeliveryPage";
import PublicReviewPage from "./pages/PublicReviewPage";
import MarketplacePage from "./pages/MarketplacePage";
import ReviewSessionPage from "./pages/ReviewSessionPage";
import ProjectPage from "./pages/ProjectPage";
import ProjectsPage from "./pages/ProjectsPage";
import DawIntegrationPage from "./pages/DawIntegrationPage";
import DocsPage from "./pages/DocsPage";

// Integration pages for individual DAWs — same layout, per-DAW accent color.
const CUBASE = {
  name: "Cubase",
  tagline: "Push the session, review every bounce — without leaving Steinberg's world.",
  intro:
    "SoundHub reads .cpr files directly: tempo, time signature, tracks, VST/VST3 plugins with their settings, and referenced samples. The `snd push` CLI turns a Cubase session into one versioned commit — and with a master export, into a shareable review with gapless A/B.",
  status: "Cubase 13 parsed · push via snd",
  accentVar: "#2e6bd6",
  shot: "/screenshots/cubase-integration.png",
  shotUrl: "soundhub.local/projects/cubase-sessions",
  shotCaption:
    "A real Cubase 13 session pushed to SoundHub — 126 BPM, five tracks, eight plugins (Serum, FabFilter, SSL, Waves…) parsed from the .cpr.",
  parsed: [
    { label: "Format", value: ".cpr — Cubase project XML" },
    { label: "Project version", value: "13.0.40 (any 6–14 read)" },
    { label: "Tempo & signature", value: "TempoTrack → BPM, time sig" },
    { label: "Tracks", value: "midi · audio · instrument · group · folder" },
    { label: "Plugins", value: "VST3 / VST2 / VST by name + inserts" },
    { label: "Samples", value: "referenced paths from Sample tags" },
  ],
  workflow: [
    "`snd push track.cpr` — one command, one versioned commit, DAW metadata extracted",
    "`--audio master.wav` opens a public review session with gapless A/B",
    "`--stems stems/` attaches renders by logical name (Kick→drums, Bass→bass…)",
    "Preflight rejects corrupt .cpr before anything is uploaded",
    "Atomic: a failed upload leaves no half-pushed version behind",
  ],
  formats: [".cpr", ".cpr.backup", ".cprx"],
  next:
    "A native Cubase panel (same pattern as the Max for Live device) is the next step — for now the CLI bridge covers push, open requests and the locator helper.",
};

const FL_STUDIO = {
  name: "FL Studio",
  tagline: "From the playlist to a review link — versioned, shared, approved.",
  intro:
    "SoundHub reads .flp project files: FL version, tempo, project name and channel structure. The `snd push` CLI commits the project, attaches the rendered master and stems, and opens a review where clients hear the difference — not just a file name.",
  status: "FL 21 parsed · push via snd",
  accentVar: "#ff7a1a",
  shot: "/screenshots/fl-integration.png",
  shotUrl: "soundhub.local/projects/fl-sessions",
  shotCaption:
    "A real FL Studio 21 project pushed to SoundHub — 140 BPM, FL 21, three channels (Kick, Lead, Sub Bass) parsed from the binary .flp.",
  parsed: [
    { label: "Format", value: ".flp — binary chunk format (FL 21+)" },
    { label: "Project version", value: "FL 11 · 12 · 20 · 21 detected" },
    { label: "Tempo", value: "project BPM from FLPI info" },
    { label: "Channels", value: "FLCh channel chunks counted" },
    { label: "Project info", value: "name · author · comment" },
    { label: "Structure", value: "chunk map — FLhd / FLPI / FLdt" },
  ],
  workflow: [
    "`snd push track.flp` — one command, one versioned commit, DAW metadata extracted",
    "`--audio master.wav` opens a public review session with gapless A/B",
    "`--stems stems/` attaches renders by logical name for stem-level compare",
    "Preflight validates the .flp before anything is uploaded",
    "Atomic: a failed upload leaves no half-pushed version behind",
  ],
  formats: [".flp"],
  next:
    "Deep event parsing (per-channel plugins, patterns) is the next step — today we read the header, tempo and channel structure from the binary.",
};


const THEME_KEY = "soundhub_theme";

function getInitialTheme(): "light" | "dark" {
  const saved = localStorage.getItem(THEME_KEY);
  if (saved === "light" || saved === "dark") return saved;
  return "light";
}

function RequireAuth({ children }: { children: JSX.Element }) {
  if (!isLoggedIn()) return <Navigate to="/login" replace />;
  return children;
}

export default function App() {
  const [theme, setTheme] = useState<"light" | "dark">(getInitialTheme);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem(THEME_KEY, theme);
  }, [theme]);

  const toggleTheme = () => setTheme((t) => (t === "light" ? "dark" : "light"));

  return (
    <div className="app">
      {/* bandcamp-style global header: logo + search + auth, subnav below */}
      <SiteHeader theme={theme} onToggleTheme={toggleTheme} />
      <main className="content">
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/kettle" element={<KettlePage />} />
          <Route path="/docs" element={<DocsPage />} />
          <Route path="/p/:username" element={<PortfolioPage />} />
          <Route path="/session" element={<ReviewSessionPage />} />
          <Route path="/sessions" element={<ReviewSessionPage />} />
          <Route path="/r/:token" element={<PublicReviewPage />} />
          <Route path="/d/:token" element={<PublicDeliveryPage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route
            path="/integrations/cubase"
            element={<DawIntegrationPage daw={CUBASE} />}
          />
          <Route
            path="/integrations/fl-studio"
            element={<DawIntegrationPage daw={FL_STUDIO} />}
          />
          <Route
            path="/projects"
            element={
              <RequireAuth>
                <ProjectsPage />
              </RequireAuth>
            }
          />
          <Route
            path="/projects/:id"
            element={
              <RequireAuth>
                <ProjectPage />
              </RequireAuth>
            }
          />
          <Route
            path="/projects/:id/branches"
            element={
              <RequireAuth>
                <BranchesPage />
              </RequireAuth>
            }
          />
          <Route
            path="/projects/:id/commit/:commitId"
            element={
              <RequireAuth>
                <CommitPage />
              </RequireAuth>
            }
          />
          <Route
            path="/projects/:id/diff"
            element={
              <RequireAuth>
                <DiffPage />
              </RequireAuth>
            }
          />
          <Route
            path="/dao"
            element={
              <RequireAuth>
                <DAOPage />
              </RequireAuth>
            }
          />
          <Route
            path="/market"
            element={
              <RequireAuth>
                <MarketplacePage />
              </RequireAuth>
            }
          />
          <Route
            path="/github"
            element={
              <RequireAuth>
                <GitHubRepoPage />
              </RequireAuth>
            }
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  );
}
