import type {
  Branch,
  Commit,
  CommitDetail,
  Deliverable,
  DeliveryPage,
  Diff,
  AudioAnalysis,
  LedgerResponse,
  LedgerVerify,
  VersionComparison,
  GhBranch,
  GhCommit,
  Project,
  ReleasePackage,
  ReviewApproval,
  ReviewComment,
  ReviewSession,
  ReviewVersion,
  TokenResponse,
  Tree,
} from "./types";

const TOKEN_KEY = "soundhub_token";

// The backend runs separately from the vite dev server / static host.
const API_ORIGIN = import.meta.env.VITE_API_URL ?? "";

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
  getTree: (id: number, opts: { commitId?: number; branch?: string } = {}) => {
    const q = new URLSearchParams();
    if (opts.commitId) q.set("commit_id", String(opts.commitId));
    if (opts.branch) q.set("branch", opts.branch);
    const qs = q.toString();
    return request<Tree>(`/api/projects/${id}/tree${qs ? `?${qs}` : ""}`);
  },
  listCommits: (id: number, branch?: string) =>
    request<Commit[]>(
      `/api/projects/${id}/commits${branch ? `?branch=${encodeURIComponent(branch)}` : ""}`
    ),
  getCommit: (id: number, commitId: number) =>
    request<CommitDetail>(`/api/projects/${id}/commits/${commitId}`),
  listBranches: (id: number) => request<Branch[]>(`/api/projects/${id}/branches`),
  createBranch: (id: number, name: string, fromBranch?: string) =>
    request<Branch>(`/api/projects/${id}/branches`, {
      method: "POST",
      body: JSON.stringify({ name, from_branch: fromBranch }),
    }),
  deleteBranch: (id: number, name: string) =>
    request<void>(`/api/projects/${id}/branches/${encodeURIComponent(name)}`, {
      method: "DELETE",
    }),
  createCommit: (id: number, message: string, files: FileList | File[], branch = "main") =>
    request<Commit>(`/api/projects/${id}/commits`, {
      method: "POST",
      body: (() => {
        const fd = new FormData();
        fd.append("message", message);
        fd.append("branch", branch);
        Array.from(files).forEach((f) => fd.append("files", f, f.webkitRelativePath || f.name));
        return fd;
      })(),
    }),
  getDiff: (id: number, path: string, opts: { from?: number; to?: number; fromBranch?: string; toBranch?: string } = {}) => {
    const q = new URLSearchParams({ path });
    if (opts.from) q.set("from_commit", String(opts.from));
    if (opts.to) q.set("to_commit", String(opts.to));
    if (opts.fromBranch) q.set("from_branch", opts.fromBranch);
    if (opts.toBranch) q.set("to_branch", opts.toBranch);
    return request<Diff>(`/api/projects/${id}/diff?${q.toString()}`);
  },
  fileUrl: (id: number, path: string, download = false, branch?: string) => {
    const q = new URLSearchParams();
    if (download) q.set("download", "1");
    if (branch) q.set("branch", branch);
    return `/api/projects/${id}/files/${encodePath(path)}${q.size ? `?${q}` : ""}`;
  },
  // Review sessions — the Frame.io-style loop for music
  listSessions: () => request<ReviewSession[]>("/api/sessions"),
  createSession: (name: string, projectId?: number) =>
    request<ReviewSession>("/api/sessions", {
      method: "POST",
      body: JSON.stringify({ name, project_id: projectId ?? null }),
    }),
  getSession: (id: number) => request<ReviewSession>(`/api/sessions/${id}`),
  deleteSession: (id: number) =>
    request<void>(`/api/sessions/${id}`, { method: "DELETE" }),
  uploadVersion: (id: number, file: File, message = "") =>
    request<ReviewVersion>(`/api/sessions/${id}/versions`, {
      method: "POST",
      body: (() => {
        const fd = new FormData();
        fd.append("message", message);
        fd.append("file", file);
        return fd;
      })(),
    }),
  versionAudioUrl: (id: number, versionId: number) =>
    `/api/sessions/${id}/versions/${versionId}/audio`,
  addComment: (id: number, versionId: number, timeS: number, body: string, parentId?: number) =>
    request<ReviewComment>(`/api/sessions/${id}/versions/${versionId}/comments`, {
      method: "POST",
      body: JSON.stringify({ time_s: timeS, body, parent_id: parentId ?? null }),
    }),
  resolveComment: (id: number, versionId: number, commentId: number, resolved: boolean) =>
    request<ReviewComment>(
      `/api/sessions/${id}/versions/${versionId}/comments/${commentId}?resolved=${resolved}`,
      { method: "PATCH" }
    ),
  setVersionStatus: (id: number, versionId: number, status: string) =>
    request<ReviewVersion>(`/api/sessions/${id}/versions/${versionId}/status`, {
      method: "POST",
      body: JSON.stringify({ status }),
    }),
  addApproval: (
    id: number,
    versionId: number,
    scope: string,
    approved: boolean,
    note: string,
    approverName: string
  ) =>
    request<ReviewApproval>(`/api/sessions/${id}/versions/${versionId}/approvals`, {
      method: "POST",
      body: JSON.stringify({
        scope,
        approved,
        note,
        approver_name: approverName,
      }),
    }),
  updateShareSettings: (
    id: number,
    opts: {
      share_password?: string | null;
      share_expires_at?: string | null;
      share_permission?: string;
      share_allowlist?: string;
      feedback_owner?: string;
      included_rounds?: number;
      rounds_open?: boolean;
      feedback_due_at?: string | null;
    }
  ) =>
    request<ReviewSession>(`/api/sessions/${id}/share`, {
      method: "PATCH",
      body: JSON.stringify(opts),
    }),
  carryUnresolved: (id: number, versionId: number) =>
    request<ReviewVersion>(`/api/sessions/${id}/versions/${versionId}/carry`, {
      method: "POST",
    }),
  submitFeedback: (id: number, note: string) =>
    request<ReviewSession>(`/api/sessions/${id}/submit-feedback`, {
      method: "POST",
      body: JSON.stringify({ note }),
    }),
  setRequestStatus: (id: number, versionId: number, commentId: number, status: string) =>
    request<ReviewComment>(`/api/sessions/${id}/versions/${versionId}/requests/${commentId}/status`, {
      method: "POST",
      body: JSON.stringify({ status }),
    }),
  getLedger: (id: number) =>
    request<LedgerResponse>(`/api/sessions/${id}/ledger`),
  verifyLedger: (id: number) =>
    request<LedgerVerify>(`/api/sessions/${id}/ledger/verify`),
  // A/B comparison
  getAudioAnalysis: (versionId: number) =>
    request<AudioAnalysis>(`/api/versions/${versionId}/audio-analysis`),
  createComparison: (opts: {
    baseVersionId: number;
    compareVersionId: number;
    requestId?: number | null;
    startMs: number;
    endMs?: number | null;
    levelMatch?: string;
  }) =>
    request<VersionComparison>("/api/comparisons", {
      method: "POST",
      body: JSON.stringify({
        base_version_id: opts.baseVersionId,
        compare_version_id: opts.compareVersionId,
        request_id: opts.requestId ?? null,
        start_ms: opts.startMs,
        end_ms: opts.endMs ?? null,
        level_match: opts.levelMatch ?? "short_term_lufs",
      }),
    }),
  getComparison: (id: number) =>
    request<VersionComparison>(`/api/comparisons/${id}`),
  publicSubmitFeedback: (token: string, note: string, actor: string) =>
    request<ReviewSession>(
      `/api/sessions/public/${token}/submit-feedback?actor=${encodeURIComponent(actor)}`,
      { method: "POST", body: JSON.stringify({ note }) }
    ),
  // public share endpoints (no auth)
  publicSession: (token: string, opts: { actor?: string; password?: string } = {}) => {
    const q = new URLSearchParams();
    if (opts.actor) q.set("actor", opts.actor);
    if (opts.password) q.set("password", opts.password);
    const qs = q.toString();
    return request<ReviewSession>(`/api/sessions/public/${token}${qs ? `?${qs}` : ""}`);
  },
  publicAddComment: (token: string, versionId: number, timeS: number, body: string, authorName: string) =>
    request<ReviewComment>(`/api/sessions/public/${token}/versions/${versionId}/comments`, {
      method: "POST",
      body: JSON.stringify({ time_s: timeS, body, author_name: authorName }),
    }),
  publicAddApproval: (
    token: string,
    versionId: number,
    scope: string,
    approved: boolean,
    note: string,
    approverName: string
  ) =>
    request<ReviewApproval>(`/api/sessions/public/${token}/versions/${versionId}/approvals`, {
      method: "POST",
      body: JSON.stringify({ scope, approved, note, approver_name: approverName }),
    }),
  publicAudioUrl: (token: string, versionId: number) =>
    `/api/sessions/public/${token}/versions/${versionId}/audio`,
  audioUrl: (path: string) => `${API_ORIGIN}${path}`,
  // Release packages — final delivery
  listReleasePackages: (sessionId?: number) =>
    request<ReleasePackage[]>(
      `/api/release-packages${sessionId ? `?session_id=${sessionId}` : ""}`
    ),
  createReleasePackage: (sessionId: number, approvedVersionId: number, name: string) =>
    request<ReleasePackage>("/api/release-packages", {
      method: "POST",
      body: JSON.stringify({ session_id: sessionId, approved_version_id: approvedVersionId, name }),
    }),
  addDeliverableFromVersion: (packageId: number, type: string, fromVersionId: number) =>
    request<Deliverable>(`/api/release-packages/${packageId}/deliverables/from-version`, {
      method: "POST",
      body: JSON.stringify({ type, from_version_id: fromVersionId, is_required: true }),
    }),
  uploadDeliverable: (packageId: number, type: string, file: File) =>
    request<Deliverable>(`/api/release-packages/${packageId}/deliverables/upload`, {
      method: "POST",
      body: (() => {
        const fd = new FormData();
        fd.append("type", type);
        fd.append("is_required", "true");
        fd.append("file", file);
        return fd;
      })(),
    }),
  lockReleasePackage: (packageId: number, approvalScope: string, note: string) =>
    request<ReleasePackage>(`/api/release-packages/${packageId}/lock`, {
      method: "POST",
      body: JSON.stringify({ approval_scope: approvalScope, note }),
    }),
  getReleaseManifest: (packageId: number) =>
    request<{ package: ReleasePackage; manifest_json: Record<string, unknown>; manifest_hash: string }>(
      `/api/release-packages/${packageId}/manifest`
    ),
  setInvoiceStatus: (packageId: number, invoiceStatus: string) =>
    request<ReleasePackage>(`/api/release-packages/${packageId}/invoice`, {
      method: "PATCH",
      body: JSON.stringify({ invoice_status: invoiceStatus }),
    }),
  releaseDownloadUrl: (packageId: number, deliverableId: number) =>
    `/api/release-packages/${packageId}/download?deliverable_id=${deliverableId}`,
  // public delivery link
  publicDeliveryPage: (token: string) =>
    request<DeliveryPage>(`/api/release-packages/public/${token}`),
  publicDeliveryDownloadUrl: (token: string, deliverableId: number) =>
    `/api/release-packages/public/${token}/files/${deliverableId}`,
  publicDeliveryDownload: (token: string, deliverableId: number) =>
    request<Blob>(`/api/release-packages/public/${token}/files/${deliverableId}`, {
      headers: { Accept: "application/octet-stream" },
    }),
  // GitHub API (public, unauthenticated) — the SoundHub code repo itself
  ghBranches: () =>
    fetch("https://api.github.com/repos/CRYPTOSCOPE101/SOUNDHUB/branches").then((r) =>
      r.ok ? (r.json() as Promise<GhBranch[]>) : Promise.reject(new Error("GitHub API error"))
    ),
  ghBranchCommits: (branch: string) =>
    fetch(
      `https://api.github.com/repos/CRYPTOSCOPE101/SOUNDHUB/commits?sha=${encodeURIComponent(branch)}&per_page=15`
    ).then((r) =>
      r.ok
        ? r.json().then((rows) => ghCommits(rows as Array<Record<string, unknown>>))
        : Promise.reject(new Error("GitHub API error"))
    ),
};

function encodePath(path: string): string {
  return path.split("/").map(encodeURIComponent).join("/");
}

function ghCommits(rows: Array<Record<string, unknown>>): GhCommit[] {
  return rows.map((row) => {
    const c = (row as { commit?: { message?: string; author?: { name?: string | null; date?: string | null } } }).commit;
    const sha = String((row as { sha?: string }).sha || "");
    return {
      sha,
      message: (c?.message || "").split("\n")[0],
      author: c?.author?.name ?? null,
      date: c?.author?.date ?? null,
    };
  });
}
