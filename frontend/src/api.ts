import type {
  AudioAnalysis,
  Branch,
  ChangeOrder,
  CheckoutOut,
  Commit,
  CommitDetail,
  Deliverable,
  DeliveryPage,
  Diff,
  LedgerResponse,
  LedgerVerify,
  Portfolio,
  PreflightResult,
  ReferenceComparison,
  ReferenceTrack,
  ReleasePackage,
  ReleaseTemplate,
  VersionComparison,
  GhBranch,
  GhCommit,
  Project,
  ReviewApproval,
  ReviewComment,
  ReviewSession,
  ReviewVersion,
  StemAsset,
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
  addVoiceComment: (id: number, versionId: number, timeS: number, body: string, voice: Blob, durationS: number) => {
    const fd = new FormData();
    fd.append("time_s", String(timeS));
    fd.append("body", body);
    fd.append("voice_duration_s", String(durationS));
    const ext = voice.type.includes("ogg") ? "ogg" : voice.type.includes("mp4") || voice.type.includes("m4a") ? "m4a" : voice.type.includes("mp3") ? "mp3" : "webm";
    fd.append("voice", voice, `voice.${ext}`);
    return request<ReviewComment>(`/api/sessions/${id}/versions/${versionId}/comments/voice`, {
      method: "POST",
      body: fd,
    });
  },
  voiceAudioUrl: (id: number, versionId: number, commentId: number) =>
    `/api/sessions/${id}/versions/${versionId}/comments/${commentId}/voice`,
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
      deposit_due_cents?: number | null;
      deposit_status?: string;
      extra_round_price_cents?: number | null;
      rounds_paid?: number;
      portfolio_public?: boolean;
      watermark_enabled?: boolean;
      retention_until?: string | null;
      recall_fee_cents?: number | null;
      revision_fee_cents?: number | null;
    }
  ) =>
    request<ReviewSession>(`/api/sessions/${id}/share`, {
      method: "PATCH",
      body: JSON.stringify(opts),
    }),
  updateBrief: (
    id: number,
    opts: {
      service_type: string;
      genre?: string;
      goal?: string;
      deadline_at?: string | null;
      review_start_at?: string | null;
      reference_links?: string;
      do_not_change?: string;
      required_deliverables?: string;
    }
  ) =>
    request<ReviewSession>(`/api/sessions/${id}/brief`, {
      method: "PATCH",
      body: JSON.stringify(opts),
    }),
  createSessionCheckout: (id: number, kind: "deposit" | "extra_round") => {
    const fd = new FormData();
    fd.append("kind", kind);
    return request<CheckoutOut>(`/api/sessions/${id}/checkout`, { method: "POST", body: fd });
  },
  publicSessionCheckout: (token: string, kind: "deposit" | "extra_round") => {
    const fd = new FormData();
    fd.append("kind", kind);
    return request<CheckoutOut>(`/api/sessions/public/${token}/checkout`, { method: "POST", body: fd });
  },
  // public engineer portfolio
  portfolioGet: (username: string) => request<Portfolio>(`/api/portfolio/${encodeURIComponent(username)}`),
  portfolioPreviewUrl: (username: string, versionId: number) =>
    `/api/portfolio/${encodeURIComponent(username)}/preview/${versionId}`,
  // reference tracks (mix/reference A/B)
  listReferences: (sessionId: number) => request<ReferenceTrack[]>(`/api/sessions/${sessionId}/references`),
  createReferenceUrl: (
    sessionId: number,
    opts: { title: string; artist?: string; external_url: string; purpose?: string; visibility?: string; note?: string }
  ) =>
    request<ReferenceTrack>(`/api/sessions/${sessionId}/references`, {
      method: "POST",
      body: JSON.stringify({ source_type: "external_url", ...opts }),
    }),
  uploadReference: (
    sessionId: number,
    opts: { title: string; artist?: string; purpose?: string; visibility?: string; note?: string; file: File }
  ) => {
    const fd = new FormData();
    fd.append("title", opts.title);
    fd.append("artist", opts.artist ?? "");
    fd.append("purpose", opts.purpose ?? "overall");
    fd.append("visibility", opts.visibility ?? "reviewers");
    fd.append("note", opts.note ?? "");
    fd.append("file", opts.file);
    return request<ReferenceTrack>(`/api/sessions/${sessionId}/references/upload`, { method: "POST", body: fd });
  },
  updateReference: (sessionId: number, referenceId: number, opts: { title?: string; artist?: string; external_url?: string; purpose?: string; visibility?: string; note?: string }) =>
    request<ReferenceTrack>(`/api/sessions/${sessionId}/references/${referenceId}`, {
      method: "PATCH",
      body: JSON.stringify(opts),
    }),
  deleteReference: (sessionId: number, referenceId: number) =>
    request<void>(`/api/sessions/${sessionId}/references/${referenceId}`, { method: "DELETE" }),
  referenceAudioUrl: (sessionId: number, referenceId: number) =>
    `/api/sessions/${sessionId}/references/${referenceId}/audio`,
  createReferenceComparison: (sessionId: number, opts: { versionId: number; referenceId: number; startMs: number; endMs?: number | null; levelMatch?: string }) =>
    request<ReferenceComparison>(`/api/sessions/${sessionId}/references/compare`, {
      method: "POST",
      body: JSON.stringify({
        version_id: opts.versionId,
        reference_id: opts.referenceId,
        start_ms: opts.startMs,
        end_ms: opts.endMs ?? null,
        level_match: opts.levelMatch ?? "short_term_lufs",
      }),
    }),
  // public share references (guests / reviewers)
  publicReferences: (token: string) => request<ReferenceTrack[]>(`/api/sessions/public/${token}/references`),
  publicReferenceAudioUrl: (token: string, referenceId: number) =>
    `/api/sessions/public/${token}/references/${referenceId}/audio`,
  publicReferenceComparison: (token: string, opts: { versionId: number; referenceId: number; startMs: number; endMs?: number | null; levelMatch?: string }) =>
    request<ReferenceComparison>(`/api/sessions/public/${token}/references/compare`, {
      method: "POST",
      body: JSON.stringify({
        version_id: opts.versionId,
        reference_id: opts.referenceId,
        start_ms: opts.startMs,
        end_ms: opts.endMs ?? null,
        level_match: opts.levelMatch ?? "short_term_lufs",
      }),
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
    mode?: string;
    stemLogicalName?: string | null;
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
        mode: opts.mode ?? "full_mix",
        stem_logical_name: opts.stemLogicalName ?? null,
      }),
    }),
  getComparison: (id: number) =>
    request<VersionComparison>(`/api/comparisons/${id}`),
  listStems: (versionId: number) => request<StemAsset[]>(`/api/versions/${versionId}/stems`),
  uploadStem: (versionId: number, logicalName: string, displayName: string, startOffsetMs: number, file: File) => {
    const fd = new FormData();
    fd.append("logical_name", logicalName);
    fd.append("display_name", displayName);
    fd.append("start_offset_ms", String(startOffsetMs));
    fd.append("file", file);
    return request<StemAsset>(`/api/versions/${versionId}/stems`, { method: "POST", body: fd });
  },
  stemAudioUrl: (versionId: number, stemId: number) => `/api/versions/${versionId}/stems/${stemId}/audio`,
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
  publicAddVoiceComment: (token: string, versionId: number, timeS: number, body: string, authorName: string, voice: Blob, durationS: number) => {
    const fd = new FormData();
    fd.append("time_s", String(timeS));
    fd.append("body", body);
    fd.append("author_name", authorName);
    fd.append("voice_duration_s", String(durationS));
    const ext = voice.type.includes("ogg") ? "ogg" : voice.type.includes("mp4") || voice.type.includes("m4a") ? "m4a" : voice.type.includes("mp3") ? "mp3" : "webm";
    fd.append("voice", voice, `voice.${ext}`);
    return request<ReviewComment>(`/api/sessions/public/${token}/versions/${versionId}/comments/voice`, {
      method: "POST",
      body: fd,
    });
  },
  publicVoiceAudioUrl: (token: string, versionId: number, commentId: number) =>
    `/api/sessions/public/${token}/versions/${versionId}/comments/${commentId}/voice`,
  publicCompareVersions: (token: string, opts: { baseVersionId: number; compareVersionId: number; startMs: number; endMs?: number | null; levelMatch?: string }) =>
    request<VersionComparison>(`/api/sessions/public/${token}/compare`, {
      method: "POST",
      body: JSON.stringify({
        base_version_id: opts.baseVersionId,
        compare_version_id: opts.compareVersionId,
        start_ms: opts.startMs,
        end_ms: opts.endMs ?? null,
        level_match: opts.levelMatch ?? "short_term_lufs",
      }),
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
  // change orders — late changes after approval/delivery
  listChangeOrders: (sessionId: number) => request<ChangeOrder[]>(`/api/sessions/${sessionId}/change-orders`),
  publicChangeOrders: (token: string) => request<ChangeOrder[]>(`/api/sessions/public/${token}/change-orders`),
  createChangeOrder: (token: string, reason: string, description: string, actor: string) =>
    request<ChangeOrder>(
      `/api/sessions/public/${token}/change-orders?actor=${encodeURIComponent(actor)}`,
      { method: "POST", body: JSON.stringify({ reason, description }) }
    ),
  quoteChangeOrder: (sessionId: number, coId: number, decision: string, priceCents?: number | null, deadlineAt?: string | null) =>
    request<ChangeOrder>(`/api/sessions/${sessionId}/change-orders/${coId}`, {
      method: "PATCH",
      body: JSON.stringify({ decision, price_cents: priceCents ?? null, deadline_at: deadlineAt ?? null }),
    }),
  declineChangeOrder: (sessionId: number, coId: number) =>
    request<ChangeOrder>(`/api/sessions/${sessionId}/change-orders/${coId}/decline`, { method: "POST" }),
  acceptChangeOrder: (token: string, coId: number, actor: string) =>
    request<ChangeOrder>(
      `/api/sessions/public/${token}/change-orders/${coId}/accept?actor=${encodeURIComponent(actor)}`,
      { method: "POST" }
    ),
  markChangeOrderPaid: (sessionId: number, coId: number) =>
    request<ChangeOrder>(`/api/sessions/${sessionId}/change-orders/${coId}/mark-paid`, { method: "POST" }),
  changeOrderCheckout: (sessionId: number, coId: number) =>
    request<CheckoutOut>(`/api/sessions/${sessionId}/change-orders/${coId}/checkout`, { method: "POST" }),
  publicChangeOrderCheckout: (token: string, coId: number) => {
    const fd = new FormData();
    return request<CheckoutOut>(`/api/sessions/public/${token}/change-orders/${coId}/checkout`, { method: "POST", body: fd });
  },
  // Release packages — final delivery
  listReleasePackages: (sessionId?: number) =>
    request<ReleasePackage[]>(
      `/api/release-packages${sessionId ? `?session_id=${sessionId}` : ""}`
    ),
  listReleaseTemplates: () => request<ReleaseTemplate[]>("/api/release-packages/templates"),
  createReleasePackage: (sessionId: number, approvedVersionId: number, name: string, template: string) =>
    request<ReleasePackage>("/api/release-packages", {
      method: "POST",
      body: JSON.stringify({ session_id: sessionId, approved_version_id: approvedVersionId, name, template }),
    }),
  runPreflight: (packageId: number) =>
    request<PreflightResult>(`/api/release-packages/${packageId}/preflight`, { method: "POST" }),
  updateHandoff: (
    packageId: number,
    opts: {
      plugin_manifest?: string;
      session_manifest?: Record<string, unknown>;
      consolidate_audio?: boolean;
      archive_expires_at?: string | null;
      last_verified_opened_at?: string | null;
    }
  ) =>
    request<ReleasePackage>(`/api/release-packages/${packageId}/handoff`, {
      method: "PATCH",
      body: JSON.stringify(opts),
    }),
  setArchiveStatus: (packageId: number, archiveStatus: string, archiveExpiresAt?: string | null) =>
    request<ReleasePackage>(`/api/release-packages/${packageId}/archive`, {
      method: "POST",
      body: JSON.stringify({ archive_status: archiveStatus, archive_expires_at: archiveExpiresAt ?? null }),
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
  lockReleasePackage: (packageId: number, approvalScope: string, note: string, force = false, forceReason = "") =>
    request<ReleasePackage>(`/api/release-packages/${packageId}/lock`, {
      method: "POST",
      body: JSON.stringify({ approval_scope: approvalScope, note, force, force_reason: forceReason }),
    }),
  getReleaseManifest: (packageId: number) =>
    request<{ package: ReleasePackage; manifest_json: Record<string, unknown>; manifest_hash: string }>(
      `/api/release-packages/${packageId}/manifest`
    ),
  setInvoiceStatus: (packageId: number, invoiceStatus: string, amountCents?: number | null, currency?: string) =>
    request<ReleasePackage>(`/api/release-packages/${packageId}/invoice`, {
      method: "PATCH",
      body: JSON.stringify({
        invoice_status: invoiceStatus,
        amount_due_cents: amountCents ?? null,
        currency: currency ?? "usd",
      }),
    }),
  createCheckout: (packageId: number) =>
    request<CheckoutOut>(`/api/release-packages/${packageId}/checkout`, { method: "POST" }),
  publicCheckout: (token: string, kind: "package" | "deposit" = "package") => {
    const fd = new FormData();
    fd.append("kind", kind);
    return request<CheckoutOut>(`/api/release-packages/public/${token}/checkout`, { method: "POST", body: fd });
  },
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
  // demo sample review (landing CTA)
  demoReview: () =>
    request<{ share_token: string; name: string; url: string; version_count: number }>("/api/demo/review"),
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
