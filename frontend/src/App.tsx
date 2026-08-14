import { Link, Navigate, Route, Routes } from "react-router-dom";
import { isLoggedIn, useAuth } from "./auth";
import CommitPage from "./pages/CommitPage";
import DiffPage from "./pages/DiffPage";
import DAOPage from "./pages/DAOPage";
import LoginPage from "./pages/LoginPage";
import MarketplacePage from "./pages/MarketplacePage";
import ProjectPage from "./pages/ProjectPage";
import ProjectsPage from "./pages/ProjectsPage";

function RequireAuth({ children }: { children: JSX.Element }) {
  if (!isLoggedIn()) return <Navigate to="/login" replace />;
  return children;
}

export default function App() {
  const { user, logout } = useAuth();
  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="logo">◉</span>
          <span>SoundHub</span>
          <span className="tagline">version control for music</span>
        </div>
        {user && (
          <div className="userbox">
            <Link to="/market" className="btn ghost" style={{ padding: "6px 12px", fontSize: 13 }}>
              🛒 Market
            </Link>
            <Link to="/dao" className="btn ghost" style={{ padding: "6px 12px", fontSize: 13 }}>
              🗳 DAO
            </Link>
            <span className="username">{user.username}</span>
            <button className="btn ghost" onClick={logout}>
              logout
            </button>
          </div>
        )}
      </header>
      <main className="content">
        <Routes>
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
          <Route path="*" element={<Navigate to="/projects" replace />} />
        </Routes>
      </main>
    </div>
  );
}
