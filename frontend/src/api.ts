import type {
  Commit,
  CommitDetail,
  Diff,
  Project,
  TokenResponse,
  Tree,
} from "./types";

const TOKEN_KEY = "soundhub_token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null) {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body && !(init.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const res = await fetch(path, { ...init, headers });
  if (res.status === 401) {
    setToken(null);
    window.location.href = "/login";
    throw new Error("Not authenticated");
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  login: (username: string, password: string) =>
    request<TokenResponse>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }),
  register: (username: string, password: string) =>
    request<TokenResponse>("/api/auth/register", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }),
  me: () => request<{ id: number; username: string }>("/api/auth/me"),
  walletNonce: (address: string) =>
    request<{ nonce: string; message: string }>("/api/auth/wallet/nonce", {
      method: "POST",
      body: JSON.stringify({ address }),
    }),
  walletLogin: (address: string, message: string, signature: string) =>
    request<TokenResponse>("/api/auth/wallet/login", {
      method: "POST",
      body: JSON.stringify({ address, message, signature }),
    }),
  bindRelease: (id: number, tokenId: number, contractAddress: string, name: string) =>
    request<Project>(`/api/projects/${id}/release`, {
      method: "POST",
      body: JSON.stringify({ token_id: tokenId, contract_address: contractAddress, name }),
    }),
  unbindRelease: (id: number) =>
    request<Project>(`/api/projects/${id}/release`, { method: "DELETE" }),
  listProjects: () => request<Project[]>("/api/projects"),
  createProject: (name: string, description: string) =>
    request<Project>("/api/projects", {
      method: "POST",
      body: JSON.stringify({ name, description }),
    }),
  getProject: (id: number) => request<Project>(`/api/projects/${id}`),
  deleteProject: (id: number) =>
    request<void>(`/api/projects/${id}`, { method: "DELETE" }),
  getTree: (id: number, commitId?: number) =>
    request<Tree>(
      `/api/projects/${id}/tree${commitId ? `?commit_id=${commitId}` : ""}`
    ),
  listCommits: (id: number) => request<Commit[]>(`/api/projects/${id}/commits`),
  getCommit: (id: number, commitId: number) =>
    request<CommitDetail>(`/api/projects/${id}/commits/${commitId}`),
  createCommit: (id: number, message: string, files: FileList | File[]) =>
    request<Commit>(`/api/projects/${id}/commits`, {
      method: "POST",
      body: (() => {
        const fd = new FormData();
        fd.append("message", message);
        Array.from(files).forEach((f) => fd.append("files", f, f.webkitRelativePath || f.name));
        return fd;
      })(),
    }),
  getDiff: (id: number, path: string, from?: number, to?: number) => {
    const q = new URLSearchParams({ path });
    if (from) q.set("from_commit", String(from));
    if (to) q.set("to_commit", String(to));
    return request<Diff>(`/api/projects/${id}/diff?${q.toString()}`);
  },
  fileUrl: (id: number, path: string, download = false) => {
    const q = new URLSearchParams();
    if (download) q.set("download", "1");
    return `/api/projects/${id}/files/${encodePath(path)}${q.size ? `?${q}` : ""}`;
  },
};

function encodePath(path: string): string {
  return path.split("/").map(encodeURIComponent).join("/");
}
