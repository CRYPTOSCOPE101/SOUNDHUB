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
          <Route path="/p/:username" element={<PortfolioPage />} />
          <Route path="/session" element={<ReviewSessionPage />} />
          <Route path="/sessions" element={<ReviewSessionPage />} />
          <Route path="/r/:token" element={<PublicReviewPage />} />
          <Route path="/d/:token" element={<PublicDeliveryPage />} />
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
