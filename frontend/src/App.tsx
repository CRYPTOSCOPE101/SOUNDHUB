import { useEffect, useState } from "react";
import { Link, Navigate, Route, Routes } from "react-router-dom";
import { isLoggedIn, useAuth } from "./auth";
import BranchesPage from "./pages/BranchesPage";
import CommitPage from "./pages/CommitPage";
import DiffPage from "./pages/DiffPage";
import DAOPage from "./pages/DAOPage";
import GitHubRepoPage from "./pages/GitHubRepoPage";
import LandingPage from "./pages/LandingPage";
import LoginPage from "./pages/LoginPage";
import MarketplacePage from "./pages/MarketplacePage";
import ProjectPage from "./pages/ProjectPage";
import ProjectsPage from "./pages/ProjectsPage";

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
  const { user, logout } = useAuth();
  const [theme, setTheme] = useState<"light" | "dark">(getInitialTheme);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem(THEME_KEY, theme);
  }, [theme]);

  const toggleTheme = () => setTheme((t) => (t === "light" ? "dark" : "light"));

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <Link to="/" className="logo" title="SoundHub">
            <img src="/logo.png" alt="SoundHub" />
          </Link>
          <Link to="/">SoundHub</Link>
          {!user && <span className="tagline">buy finished sound</span>}
          {user && <span className="tagline">version control for music</span>}
        </div>
        {user && (
          <div className="userbox">
            <Link to="/market" className="btn ghost" style={{ padding: "6px 12px", fontSize: 13 }}>
              🛒 Market
            </Link>
            <Link to="/dao" className="btn ghost" style={{ padding: "6px 12px", fontSize: 13 }}>
              🗳 DAO
            </Link>
            <Link to="/github" className="btn ghost" style={{ padding: "6px 12px", fontSize: 13 }}>
              ◈ Repo
            </Link>
            <button className="theme-toggle" onClick={toggleTheme} title="Toggle theme">
              {theme === "light" ? "🌙" : "☀️"}
            </button>
            <span className="username">{user.username}</span>
            <button className="btn ghost" onClick={logout}>
              logout
            </button>
          </div>
        )}
        {!user && (
          <div className="userbox">
            <Link to="/login" className="btn ghost" style={{ padding: "6px 12px", fontSize: 13 }}>
              Sign in
            </Link>
            <Link to="/login" className="btn" style={{ padding: "6px 12px", fontSize: 13 }}>
              Get started
            </Link>
          </div>
        )}
      </header>
      <main className="content">
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/login" element={<LoginPage />} />
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
