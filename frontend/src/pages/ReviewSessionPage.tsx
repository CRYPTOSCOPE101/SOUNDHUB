import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api, getToken } from "../api";
import { fmtClock, WaveformCanvas, CommentComposer, ApprovalPanel } from "../components/ReviewShared";
import ABCompare from "../components/ABCompare";
import {
  humanSize,
  shortDate,
  DELIVERABLE_TYPES,
  STEM_LOGICAL_NAMES,
  type LedgerEntry,
  type LedgerVerify,
  type ReleasePackage,
  type ReviewApproval,
  type ReviewComment,
  type ReviewSession,
  type ReviewVersion,
  type StemAsset,
  type VersionComparison,
} from "../types";

/* ---------- helpers ---------- */

const STATUS_TEXT: Record<string, string> = {
  draft: "draft",
  ready: "ready",
  delivered: "delivered",
  archived: "archived",
};

function ledgerText(e: LedgerEntry): string {
  const p = e.payload;
  switch (e.event) {
    case "version.created":
      return `uploaded ${p.label} — ${p.fixed_requests} request${Number(p.fixed_requests) === 1 ? "" : "s"} linked as fixed`;
    case "round.submitted":
      return `submitted Round ${p.round} — ${p.requests} request${Number(p.requests) === 1 ? "" : "s"} consolidated${p.note ? ` · “${p.note}”` : ""}`;
    case "feedback.draft_created":
      return `left a draft note at ${fmtClock(Number(p.time_s))} — “${p.body}”`;
    case "request.created":
      return `opened request at ${fmtClock(Number(p.time_s))} — “${p.body}”`;
    case "request.acknowledged":
      return `acknowledged request “${p.body}”`;
    case "request.in_progress":
      return `started working on “${p.body}”`;
    case "request.fixed":
      return `marked “${p.body}” as fixed${p.fixed_in ? ` in v${String(p.fixed_in).slice(-2)}` : ""}`;
    case "request.verified":
      return `verified “${p.body}”`;
    case "request.approved":
      return `approved request “${p.body}”`;
    case "approval.created":
      return `${p.approved ? "approved" : "requested changes on"} ${p.version} · scope ${p.scope}${p.note ? ` — “${p.note}”` : ""}`;
    case "package.created":
      return `created release package (approved ${p.approved_version})`;
    case "deliverable.added":
      return `added deliverable ${p.type} · ${p.filename}${p.sha256 ? ` · SHA-256 ${String(p.sha256).slice(0, 8)}…` : ""}`;
    case "package.locked":
      return `🔒 locked release package — manifest SHA-256 ${String(p.manifest_sha256).slice(0, 8)}… (scope ${p.approval_scope})`;
    case "delivery.link_opened":
      return `opened the delivery link`;
    case "delivery.downloaded":
      return `downloaded from delivery`;
    case "invoice.paid":
      return `marked invoice as paid (${p.method}) — delivery unlocked`;
    default:
      return e.event.replace(/\./g, " ");
  }
}

function ledgerIcon(e: LedgerEntry): string {
  if (e.event.startsWith("package.") || e.event.startsWith("deliverable.") || e.event.startsWith("delivery.") || e.event.startsWith("invoice.")) return "📦";
  if (e.event.startsWith("request.")) return "🔧";
  if (e.event.startsWith("approval")) return "✅";
  if (e.event.startsWith("round")) return "🗂";
  if (e.event.startsWith("version")) return "⬆";
  return "✎";
}

function DecisionLog({ sessionId }: { sessionId: number }) {
  const [events, setEvents] = useState<LedgerEntry[] | null>(null);
  const [verify, setVerify] = useState<LedgerVerify | null>(null);
  const [proof, setProof] = useState<number | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setEvents((await api.getLedger(sessionId)).events);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed to load decision log");
    }
  }, [sessionId]);

  useEffect(() => {
    void load();
  }, [load]);

  const check = async () => {
    setVerify(await api.verifyLedger(sessionId));
  };

  if (!events) return <div className="rs-empty">Loading decision log…</div>;
  if (events.length === 0) return <div className="rs-empty">No decisions recorded yet.</div>;

  return (
    <div className="rs-ledger">
      <div className="rs-ledger-head">
        <span className="rs-versions-head">Decision log</span>
        <button type="button" className="rs-btn ghost sm" onClick={() => void check()}>
          {verify ? (verify.ok ? "✓ History verified" : "⚠ Tamper detected!") : "Verify history"}
        </button>
      </div>
      {verify && !verify.ok && (
        <div className="rs-ledger-warn">
          Integrity check failed — {verify.problems.length} event{verify.problems.length === 1 ? "" : "s"} in this
          history do not match their hash chain.
        </div>
      )}
      <div className="rs-ledger-list">
        {events.map((e) => (
          <div key={e.id} className="rs-ledger-row">
            <span className="rs-ledger-icon">{ledgerIcon(e)}</span>
            <div className="rs-ledger-main">
              <div className="rs-ledger-text">
                <strong>{e.actor || "anonymous"}</strong> {ledgerText(e)}
              </div>
              <div className="rs-ledger-meta">
                {shortDate(e.occurred_at)} · {e.event}
              </div>
            </div>
            <button type="button" className="rs-btn ghost sm" onClick={() => setProof(proof === e.id ? null : e.id)}>
              {proof === e.id ? "Hide proof" : "View proof"}
            </button>
          </div>
        ))}
      </div>
      {proof != null && (
        <pre className="rs-ledger-proof">{JSON.stringify(events.find((e) => e.id === proof), null, 2)}</pre>
      )}
      {err && <div className="error">{err}</div>}
    </div>
  );
}

function ReleasePackagePanel({
  sessionId,
  version,
}: {
  sessionId: number;
  version: ReviewVersion;
}) {
  const [pkg, setPkg] = useState<ReleasePackage | null>(null);
  const [activeType, setActiveType] = useState<string>("instrumental");
  const [lockNote, setLockNote] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);
  const [showManifest, setShowManifest] = useState(false);
  const [manifest, setManifest] = useState<{ manifest_json: Record<string, unknown>; manifest_hash: string } | null>(null);
  const [invoiceAmountCents, setInvoiceAmountCents] = useState<number | null>(null);

  const load = useCallback(async () => {
    try {
      const list = await api.listReleasePackages(sessionId);
      const p = list.find((p) => p.approved_version_id === version.id) ?? list[0] ?? null;
      setPkg(p);
      setInvoiceAmountCents(p?.amount_due_cents ?? null);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed to load packages");
    }
  }, [sessionId, version.id]);

  useEffect(() => {
    void load();
  }, [load]);

  const create = async () => {
    setBusy(true);
    setErr(null);
    setInfo(null);
    try {
      const p = await api.createReleasePackage(sessionId, version.id, "Final delivery");
      // pre-add the approved master as the required master deliverable
      await api.addDeliverableFromVersion(p.id, "master", version.id);
      await load();
      setInfo("Package created — approved master added ✓");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed to create package");
    } finally {
      setBusy(false);
    }
  };

  const addFromVersion = async (type: string) => {
    if (!pkg) return;
    setErr(null);
    try {
      await api.addDeliverableFromVersion(pkg.id, type, version.id);
      await load();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed");
    }
  };

  const uploadFile = async (type: string, file: File) => {
    if (!pkg) return;
    setErr(null);
    try {
      await api.uploadDeliverable(pkg.id, type, file);
      await load();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed");
    }
  };

  const lock = async () => {
    if (!pkg) return;
    setBusy(true);
    setErr(null);
    setInfo(null);
    try {
      await api.lockReleasePackage(pkg.id, "master", lockNote);
      await load();
      setInfo("RELEASE PACKAGE LOCKED ✓ — manifest hashed, delivery link opened");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Lock failed");
    } finally {
      setBusy(false);
    }
  };

  const viewManifest = async () => {
    if (!pkg) return;
    setManifest(await api.getReleaseManifest(pkg.id));
    setShowManifest(true);
  };

  const copyDelivery = async () => {
    if (!pkg?.delivery_token) return;
    const url = `${window.location.origin}/d/${pkg.delivery_token}`;
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* ignore */
    }
  };

  return (
    <div className="rs-release">
      <div className="rs-versions-head">Final delivery</div>
      {version.status !== "approved" ? (
        <div className="rs-empty">Approve {version.label} to build the release package.</div>
      ) : !pkg ? (
        <div className="rs-release-empty">
          <p>Master approved — assemble the release package: master, instrumental, artwork…</p>
          <button type="button" className="rs-btn approve" onClick={create} disabled={busy}>
            {busy ? "…" : "Create release package"}
          </button>
        </div>
      ) : (
        <>
          <div className={`rs-release-status st-${pkg.status}`}>
            {pkg.status === "ready" ? "🔒 RELEASE PACKAGE LOCKED" : STATUS_TEXT[pkg.status]?.toUpperCase()}
            {pkg.manifest_hash && <span className="rs-release-sha">SHA-256 {pkg.manifest_hash.slice(0, 8)}…{pkg.manifest_hash.slice(-4)}</span>}
          </div>

          <div className="rs-release-check">
            {DELIVERABLE_TYPES.filter((t) => t !== "other").map((t) => {
              const d = pkg.deliverables.find((x) => x.type === t);
              return (
                <div key={t} className={`rs-release-item ${d ? "ok" : ""}`}>
                  <span className="rs-release-check-icon">{d ? "✓" : "·"}</span>
                  <span className="rs-release-item-type">{t}</span>
                  {d ? (
                    <span className="rs-release-item-file">
                      {d.filename} · {humanSize(d.size)} · {d.format}
                      {d.sample_rate ? ` · ${(d.sample_rate / 1000).toFixed(1)} kHz / ${d.bit_depth}-bit` : ""}
                    </span>
                  ) : (
                    <span className="rs-release-item-missing">missing</span>
                  )}
                  {pkg.status === "draft" && !d && (
                    <span className="rs-release-actions">
                      <button type="button" className="rs-btn ghost sm" onClick={() => void addFromVersion(t)}>
                        from {version.label}
                      </button>
                      <label className="rs-btn ghost sm">
                        upload
                        <input
                          type="file"
                          accept=".wav,.mp3,.flac,.png,.jpg,.pdf,.zip,audio/*,image/*"
                          hidden
                          onChange={(e) => {
                            const f = e.target.files?.[0];
                            if (f) void uploadFile(t, f);
                            e.target.value = "";
                          }}
                        />
                      </label>
                    </span>
                  )}
                </div>
              );
            })}
            <label className="rs-release-add">
              + add file as
              <select value={activeType} onChange={(e) => setActiveType(e.target.value)} className="rs-select" style={{ margin: 0 }}>
                {DELIVERABLE_TYPES.filter((t) => t !== "master").map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
              <input
                type="file"
                hidden
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) void uploadFile(activeType, f);
                  e.target.value = "";
                }}
              />
            </label>
          </div>

          {pkg.status === "draft" ? (
            <div className="rs-release-lock">
              <input
                type="text"
                value={lockNote}
                onChange={(e) => setLockNote(e.target.value)}
                placeholder="Note for the receipt (optional)"
                className="rs-input"
              />
              <button type="button" className="rs-btn approve" onClick={lock} disabled={busy || pkg.deliverables.length === 0}>
                {busy ? "…" : "🔒 Lock approved master"}
              </button>
            </div>
          ) : (
            <div className="rs-release-delivery">
              <code>soundhub.app/d/{pkg.delivery_token}</code>
              <button type="button" className="rs-btn ghost sm" onClick={copyDelivery}>
                {copied ? "✓ Copied" : "Copy delivery link"}
              </button>
              <button type="button" className="rs-btn ghost sm" onClick={viewManifest}>
                View manifest
              </button>
              <label className="rs-btn ghost sm">
                Invoice: {pkg.invoice_status}
                <select
                  value={pkg.invoice_status}
                  onChange={(e) => {
                    void api.setInvoiceStatus(pkg.id, e.target.value, invoiceAmountCents, pkg.currency).then(load);
                  }}
                  className="rs-select"
                  style={{ margin: 0 }}
                >
                  <option value="none">none</option>
                  <option value="deposit_due">deposit due</option>
                  <option value="balance_due">balance due</option>
                  <option value="paid">paid</option>
                  <option value="waived">waived</option>
                </select>
              </label>
              {(pkg.invoice_status === "balance_due" || pkg.invoice_status === "deposit_due") && (
                <span className="rs-release-invoice-amount">
                  <input
                    type="number"
                    min={0}
                    value={invoiceAmountCents ?? ""}
                    placeholder={`amount (${pkg.currency} cents)`}
                    onChange={(e) => setInvoiceAmountCents(e.target.value === "" ? null : Number(e.target.value))}
                    className="rs-input"
                    style={{ width: 120, margin: 0 }}
                  />
                  <button
                    type="button"
                    className="rs-btn ghost sm"
                    onClick={() =>
                      void api.setInvoiceStatus(pkg.id, pkg.invoice_status, invoiceAmountCents, pkg.currency).then(load)
                    }
                  >
                    save amount
                  </button>
                  <button
                    type="button"
                    className="rs-btn approve sm"
                    onClick={async () => {
                      try {
                        const c = await api.createCheckout(pkg.id);
                        window.location.href = c.checkout_url;
                      } catch (e) {
                        setErr(e instanceof Error ? e.message : "Checkout failed");
                      }
                    }}
                    title="Open Stripe Checkout (card / Apple Pay / Google Pay)"
                  >
                    💳 Open checkout
                  </button>
                </span>
              )}
            </div>
          )}
          {showManifest && manifest && (
            <pre className="rs-release-manifest">
              {JSON.stringify(manifest.manifest_json, null, 2)}
            </pre>
          )}
        </>
      )}
      {info && <div className="success">{info}</div>}
      {err && <div className="error">{err}</div>}
    </div>
  );
}

async function fetchAudioBlob(url: string): Promise<string> {
  const headers: Record<string, string> = {};
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(url, { headers });
  if (!res.ok) throw new Error(`Audio request failed (${res.status})`);
  const blob = await res.blob();
  return URL.createObjectURL(blob);
}

/* ---------- stems ---------- */

function StemPanel({ version }: { version: ReviewVersion }) {
  const [stems, setStems] = useState<StemAsset[] | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    setStems(await api.listStems(version.id));
  }, [version.id]);

  useEffect(() => {
    void load();
  }, [load]);

  const upload = async (name: string, file: File) => {
    setErr(null);
    try {
      await api.uploadStem(version.id, name, `${name} stem`, 0, file);
      await load();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Upload failed");
    }
  };

  return (
    <div className="rs-stems">
      <div className="rs-versions-head">Stems · {version.label}</div>
      {stems === null ? (
        <div className="rs-empty">Loading stems…</div>
      ) : stems.length === 0 ? (
        <div className="rs-empty">No stems — upload submix renders to compare them between versions.</div>
      ) : (
        <div className="rs-stem-list">
          {stems.map((s) => (
            <div key={s.id} className="rs-stem-row">
              <span className={`rs-stem-dot st-${s.logical_name}`} />
              <span className="rs-stem-name">{s.display_name}</span>
              <span className="rs-stem-meta">
                {humanSize(s.size)} · {s.audio_format}
                {s.start_offset_ms ? ` · +${s.start_offset_ms} ms` : ""}
              </span>
            </div>
          ))}
        </div>
      )}
      <div className="rs-stem-upload">
        {STEM_LOGICAL_NAMES.map((name) => (
          <label key={name} className="rs-btn ghost sm">
            + {name}
            <input
              type="file"
              accept=".wav,.mp3,.flac,.aif,.aiff,.m4a,.ogg,audio/*"
              hidden
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) void upload(name, f);
                e.target.value = "";
              }}
            />
          </label>
        ))}
      </div>
      {err && <div className="error">{err}</div>}
    </div>
  );
}

/* ---------- session detail ---------- */

function SessionDetail({ session, onBack }: { session: ReviewSession; onBack: () => void }) {
  const [versions, setVersions] = useState<ReviewVersion[]>(session.versions ?? []);
  const [approvals, setApprovals] = useState<ReviewApproval[]>(session.approvals ?? []);
  const [rounds, setRounds] = useState(session.rounds ?? []);
  const [events, setEvents] = useState(session.access_events ?? []);
  const [roundNumber, setRoundNumber] = useState(session.round_number ?? 1);
  const [roundsOpen, setRoundsOpen] = useState(session.rounds_open ?? true);
  const [feedbackOwner, setFeedbackOwner] = useState(session.feedback_owner ?? "");
  const [includedRounds, setIncludedRounds] = useState(session.included_rounds ?? 1);
  const [submitNote, setSubmitNote] = useState("");
  const [share, setShare] = useState({
    permission: session.share_permission ?? "comment",
    password: "",
    expires: session.share_expires_at ? session.share_expires_at.slice(0, 10) : "",
    allowlist: session.share_allowlist ?? "",
  });
  const [currentId, setCurrentId] = useState<number | null>(session.versions?.length ? session.versions[0].id : null);
  const [playing, setPlaying] = useState(false);
  const [position, setPosition] = useState(0);
  const [loop, setLoop] = useState<{ start: number; end: number } | null>(null);
  const [mode, setMode] = useState<"seek" | "comment">("seek");
  const [pendingComment, setPendingComment] = useState<number | null>(null);
  const [compare, setCompare] = useState<number | null>(null); // other version id in A/B
  const [comparison, setComparison] = useState<VersionComparison | null>(null); // loudness-matched A/B panel
  const [comparisonErr, setComparisonErr] = useState<string | null>(null);
  const [src, setSrc] = useState<string | null>(null);
  const [srcVersion, setSrcVersion] = useState<number | null>(null);
  const [copied, setCopied] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [highlight, setHighlight] = useState<number | null>(null);
  const audioRef = useRef<HTMLAudioElement>(null);
  const rafRef = useRef<number | null>(null);
  const keepTimeRef = useRef<number | null>(null);

  const current = versions.find((v) => v.id === currentId) ?? versions[0] ?? null;
  const compareVersion = compare ? versions.find((v) => v.id === compare) ?? null : null;

  const refresh = useCallback(async () => {
    const s = await api.getSession(session.id);
    setVersions(s.versions ?? []);
    setApprovals(s.approvals ?? []);
    setRounds(s.rounds ?? []);
    setEvents(s.access_events ?? []);
    setRoundNumber(s.round_number ?? 1);
    setRoundsOpen(s.rounds_open ?? true);
    setFeedbackOwner(s.feedback_owner ?? "");
    setIncludedRounds(s.included_rounds ?? 1);
    setCurrentId((prev) => {
      if (prev && s.versions?.some((v) => v.id === prev)) return prev;
      return s.versions?.length ? s.versions[0].id : null;
    });
  }, [session.id]);

  const loadAudio = useCallback(
    async (version: ReviewVersion, keepTime: number | null = null) => {
      try {
        const url = await fetchAudioBlob(api.versionAudioUrl(session.id, version.id));
        setSrc((old) => {
          if (old) URL.revokeObjectURL(old);
          return url;
        });
        setSrcVersion(version.id);
        keepTimeRef.current = keepTime;
      } catch (e) {
        setErr(e instanceof Error ? e.message : "Failed to load audio");
      }
    },
    [session.id]
  );

  // load audio when switching version / compare
  useEffect(() => {
    if (!current) return;
    if (srcVersion !== current.id) {
      const keep = keepTimeRef.current;
      keepTimeRef.current = null;
      void loadAudio(current, keep);
    }
    setPendingComment(null);
    setLoop(null);
  }, [current?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  // playhead animation
  useEffect(() => {
    const tick = () => {
      const a = audioRef.current;
      if (a) {
        setPosition(a.currentTime);
        if (loop && a.currentTime >= loop.end) {
          a.currentTime = loop.start;
          a.play().catch(() => undefined);
        }
      }
      rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [loop]);

  useEffect(() => {
    return () => {
      if (src) URL.revokeObjectURL(src);
    };
  }, [src]);

  const togglePlay = () => {
    const a = audioRef.current;
    if (!a) return;
    if (playing) {
      a.pause();
    } else {
      void a.play().catch(() => undefined);
    }
  };

  const seek = (t: number) => {
    const a = audioRef.current;
    if (a) a.currentTime = t;
    setPosition(t);
  };

  const switchVersion = (v: ReviewVersion) => {
    const keep = audioRef.current?.currentTime ?? null;
    keepTimeRef.current = keep;
    setCurrentId(v.id);
    setPlaying(false);
    setCompare(null);
  };

  const upload = async (file: File) => {
    setUploading(true);
    setErr(null);
    setInfo(null);
    try {
      await api.uploadVersion(session.id, file, `Uploaded ${file.name}`);
      setInfo("Version uploaded ✓");
      await refresh();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  const carry = async () => {
    if (!current) return;
    setErr(null);
    setInfo(null);
    try {
      await api.carryUnresolved(session.id, current.id);
      setInfo("Unresolved comments carried to the newest version ✓");
      await refresh();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Carry failed");
    }
  };

  const submitFeedback = async () => {
    setErr(null);
    setInfo(null);
    try {
      await api.submitFeedback(session.id, submitNote);
      setSubmitNote("");
      setInfo("Feedback consolidated — round closed, next round opened ✓");
      await refresh();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Submit failed");
    }
  };

  const setRequestStatus = async (commentId: number, status: string) => {
    if (!current) return;
    await api.setRequestStatus(session.id, current.id, commentId, status);
    await refresh();
  };

  const openComparison = async (c: ReviewComment) => {
    if (!c.fixed_in) return;
    setComparisonErr(null);
    try {
      const startMs = Math.max(0, Math.round((c.time_s - 8) * 1000));
      const endMs = Math.round((c.time_s + 8) * 1000);
      const comp = await api.createComparison({
        baseVersionId: c.version_id,
        compareVersionId: c.fixed_in,
        requestId: c.id,
        startMs,
        endMs,
      });
      setComparison(comp);
    } catch (e) {
      setComparisonErr(e instanceof Error ? e.message : "Failed to create comparison");
    }
  };

  const copyLink = async () => {
    const url = `${window.location.origin}/r/${session.share_token}`;
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      setCopied(false);
    }
  };

  const copyCommentLink = async (c: ReviewComment) => {
    const url = `${window.location.origin}/r/${session.share_token}#c${c.id}`;
    try {
      await navigator.clipboard.writeText(url);
      setHighlight(c.id);
      setTimeout(() => setHighlight(null), 2500);
    } catch {
      /* ignore */
    }
  };

  const saveShare = async () => {
    setErr(null);
    try {
      await api.updateShareSettings(session.id, {
        share_permission: share.permission,
        share_password: share.password || null,
        share_expires_at: share.expires ? `${share.expires}T23:59:59Z` : null,
        share_allowlist: share.allowlist,
        feedback_owner: feedbackOwner,
        included_rounds: includedRounds,
      });
      setInfo("Share settings saved ✓");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed to save share settings");
    }
  };

  const commentOnVersion = async (versionId: number, timeS: number, body: string, parentId?: number) =>
    api.addComment(session.id, versionId, timeS, body, parentId);

  const toggleResolved = async (commentId: number, resolved: boolean) => {
    if (!current) return;
    await api.resolveComment(session.id, current.id, commentId, !resolved);
    await refresh();
  };

  const resolvedCount = current?.comments.filter((c) => c.resolved).length ?? 0;
  const openCount = (current?.comments.length ?? 0) - resolvedCount;
  const drafts = current?.comments.filter((c) => c.status === "draft") ?? [];
  const openRequests = current?.comments.filter((c) => c.status === "open" && !c.resolved) ?? [];
  const statusChip =
    current?.status === "approved"
      ? { text: `${current.label} · Approved ✓`, cls: "status-approved" }
      : current?.status === "needs_changes"
        ? { text: `${current.label} · Needs changes`, cls: "status-changes" }
        : { text: `${current?.label ?? ""} · Ready for approval`, cls: "status-review" };

  return (
    <div className="rs rs-real">
      {/* header */}
      <div className="rs-head">
        <div className="rs-title">
          <span className="rs-title-icon">🎧</span>
          <div>
            <div className="rs-name">{session.name}</div>
            <div className="rs-sub">
              Round {roundNumber} · {versions.length} version{versions.length === 1 ? "" : "s"} · shared via private link
            </div>
          </div>
        </div>
        <div className={`rs-status ${statusChip.cls}`}>{statusChip.text}</div>
      </div>

      {/* revision round summary */}
      <div className="rs-round-bar">
        <span className="rs-round-chip">Round {roundNumber}</span>
        <span className="rs-round-stat">
          {openRequests.length} open request{openRequests.length === 1 ? "" : "s"}
        </span>
        <span className="rs-round-stat">
          {drafts.length} draft note{drafts.length === 1 ? "" : "s"}
        </span>
        <span className={`rs-round-stat ${roundsOpen ? "open" : "closed"}`}>
          {roundsOpen ? "collecting feedback" : "round closed"}
        </span>
        {rounds.length > 0 && (
          <span className="rs-round-stat muted">
            {rounds.filter((r) => r.status === "submitted").length} submitted
          </span>
        )}
      </div>

      {current ? (
        <>
          {/* version selector + A/B */}
          <div className="rs-version-tabs">
            {versions.map((v) => (
              <button
                key={v.id}
                type="button"
                className={`rs-tab ${current.id === v.id ? "active" : ""}`}
                onClick={() => switchVersion(v)}
              >
                {v.label}
                <span className="rs-tab-msg">{v.message || v.filename}</span>
              </button>
            ))}
            {versions.length >= 2 && (
              <button
                type="button"
                className={`rs-tab compare ${compare != null ? "active" : ""}`}
                onClick={() => {
                  const other = versions.find((v) => v.id !== current.id);
                  setCompare(compare == null ? (other?.id ?? null) : null);
                  setPlaying(false);
                }}
              >
                {compare != null ? "✕ A/B off" : "A/B"}
              </button>
            )}
          </div>

          {compare != null && compareVersion && (
            <div className="rs-ab-bar">
              <span>
                A: <strong>{current.label}</strong>
              </span>
              <span>
                B: <strong>{compareVersion.label}</strong>
              </span>
              <button
                type="button"
                className="rs-btn ghost sm"
                onClick={() => {
                  const keep = audioRef.current?.currentTime ?? null;
                  keepTimeRef.current = keep;
                  setCurrentId(compareVersion.id);
                  setCompare(current.id);
                  setPlaying(false);
                }}
              >
                ⇄ Swap A/B
              </button>
              <button
                type="button"
                className="rs-btn ghost sm"
                onClick={() => {
                  const t = audioRef.current?.currentTime ?? position;
                  seek(Math.max(0, t - 8));
                }}
              >
                ⟲ ±8s
              </button>
            </div>
          )}

          {/* loudness-matched A/B panel */}
          {comparison && (
            <ABCompare
              sessionId={session.id}
              comparison={comparison}
              onClose={() => setComparison(null)}
            />
          )}
          {comparisonErr && <div className="error">{comparisonErr}</div>}

          {/* player */}
          <div className="rs-player">
            <div className="rs-wave-wrap">
              <button type="button" className="rs-play" onClick={togglePlay} title={playing ? "Pause" : "Play"}>
                {playing ? "❚❚" : "▶"}
              </button>
              <WaveformCanvas
                peaks={current.waveform}
                duration={current.duration_s}
                position={position}
                playing={playing}
                comments={current.comments}
                loop={loop}
                mode={mode}
                onAddComment={(t) => setPendingComment(t)}
                onLoop={(start, end) => {
                  if (Math.abs(end - start) < 0.15) setLoop(null);
                  else setLoop({ start, end });
                }}
                highlightComment={highlight}
              />
              <div className="rs-time">{fmtClock(position)}</div>
              <div className="rs-time right">{fmtClock(current.duration_s)}</div>
            </div>

            <div className="rs-player-row">
              <div className="rs-seg">
                <button
                  type="button"
                  className={`rs-seg-btn ${mode === "seek" ? "active" : ""}`}
                  onClick={() => setMode("seek")}
                >
                  Seek / loop
                </button>
                <button
                  type="button"
                  className={`rs-seg-btn ${mode === "comment" ? "active" : ""}`}
                  onClick={() => setMode("comment")}
                >
                  Add comment
                </button>
              </div>
              {loop && (
                <button
                  type="button"
                  className="rs-btn ghost sm"
                  onClick={() => setLoop(null)}
                  title="Clear loop"
                >
                  loop {fmtClock(loop.start)}–{fmtClock(loop.end)} ✕
                </button>
              )}
              <span className="rs-file-meta">
                {current.filename} · {humanSize(current.size)} · {current.audio_format}
              </span>
            </div>

            <audio
              ref={audioRef}
              src={src ?? undefined}
              onPlay={() => setPlaying(true)}
              onPause={() => setPlaying(false)}
              onEnded={() => setPlaying(false)}
              className="rs-audio"
              preload="auto"
            />

            {pendingComment != null && (
              <CommentComposer
                timeS={pendingComment}
                placeholder="Comment at this point…"
                autoFocus
                onCancel={() => setPendingComment(null)}
                onSubmit={(t, body) => commentOnVersion(current.id, t, body)}
              />
            )}

            <div className="rs-body">
              {/* comments */}
              <div className="rs-comments">
                <div className="rs-comments-head">
                  <span>Comments</span>
                  <span className="rs-count">
                    {resolvedCount} resolved · {openCount} open
                  </span>
                </div>
                {current.comments.length === 0 && (
                  <div className="rs-empty">No comments yet — switch to “Add comment” and click the waveform, or share the link.</div>
                )}
                {current.comments.map((c) => (
                  <div key={c.id} id={`c${c.id}`} className={`rs-comment ${c.resolved ? "resolved" : ""} ${highlight === c.id ? "flash" : ""}`}>
                    <button type="button" className="rs-comment-time" onClick={() => seek(c.time_s)} title={`Seek to ${fmtClock(c.time_s)}`}>
                      {fmtClock(c.time_s)}
                    </button>
                    <div className="rs-comment-body">
                      <div className="rs-comment-author">
                        <span className="rs-avatar">{c.author_name[0]?.toUpperCase() ?? "?"}</span>
                        <strong>{c.author_name}</strong>
                        {c.status !== "open" && c.status !== "draft" && (
                          <span className={`rs-req-status st-${c.status}`}>{c.status}</span>
                        )}
                      </div>
                      <p>{c.body}</p>
                      <div className="rs-comment-actions">
                        {c.status === "draft" && <span className="rs-req-draft">draft — visible to you only</span>}
                        {c.status === "open" && (
                          <button type="button" className="rs-link" onClick={() => setRequestStatus(c.id, "acknowledged")}>
                            Acknowledge
                          </button>
                        )}
                        {(c.status === "acknowledged" || c.status === "in_progress") && (
                          <button type="button" className="rs-link" onClick={() => setRequestStatus(c.id, c.status === "acknowledged" ? "in_progress" : "fixed")}>
                            {c.status === "acknowledged" ? "Start working" : "Mark fixed"}
                          </button>
                        )}
                        {c.status === "fixed" && (
                          <button type="button" className="rs-link" onClick={() => setRequestStatus(c.id, "verified")}>
                            Verify
                          </button>
                        )}
                        {c.status === "verified" && (
                          <button type="button" className="rs-link" onClick={() => setRequestStatus(c.id, "approved")}>
                            Approve request
                          </button>
                        )}
                        {c.fixed_in != null && versions.length >= 2 && (
                          <button type="button" className="rs-link" onClick={() => void openComparison(c)}>
                            🎧 Compare around request
                          </button>
                        )}
                        {c.fixed_in != null && (
                          <span className="rs-req-fixedin">
                            changed in {versions.find((v) => v.id === c.fixed_in)?.label ?? `v${c.fixed_in}`}
                          </span>
                        )}
                        <button type="button" className="rs-link" onClick={() => copyCommentLink(c)}>
                          Copy link to comment
                        </button>
                        <button type="button" className="rs-link" onClick={() => toggleResolved(c.id, c.resolved)}>
                          {c.resolved ? "Reopen" : "Mark resolved"}
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
                <CommentComposer
                  timeS={0}
                  placeholder="Comment on this version…"
                  onSubmit={(t, body) => commentOnVersion(current.id, t, body)}
                />
              </div>

              {/* versions / approvals / share */}
              <div className="rs-side">
                <div className="rs-versions">
                  <div className="rs-versions-head">Versions</div>
                  {versions.map((v) => (
                    <button
                      key={v.id}
                      type="button"
                      className={`rs-version ${current.id === v.id ? "active" : ""}`}
                      onClick={() => switchVersion(v)}
                    >
                      <span className="rs-version-id">{v.label}</span>
                      <span className="rs-version-info">
                        <span className="rs-version-label">{v.message || v.filename}</span>
                        <span className="rs-version-note">
                          {fmtClock(v.duration_s)} · {v.comments.filter((c) => c.resolved).length} resolved
                        </span>
                      </span>
                    </button>
                  ))}
                  <label className="rs-upload">
                    {uploading ? "Uploading…" : "⬆ Upload new version"}
                    <input
                      type="file"
                      accept=".wav,.mp3,.flac,.ogg,.aif,.aiff,.m4a,audio/*"
                      hidden
                      onChange={(e) => {
                        const f = e.target.files?.[0];
                        if (f) void upload(f);
                        e.target.value = "";
                      }}
                    />
                  </label>
                  {versions.length >= 2 && (
                    <button type="button" className="rs-btn ghost" onClick={carry}>
                      Carry unresolved comments →
                    </button>
                  )}
                  {info && <div className="success">{info}</div>}
                  {err && <div className="error">{err}</div>}
                </div>

                {/* stems — submix renders for stem-level A/B comparison */}
                <StemPanel version={current} />

                {/* consolidated feedback — one submitted revision round */}
                <div className="rs-rounds">
                  <div className="rs-versions-head">Revision rounds</div>
                  {rounds.length === 0 && drafts.length === 0 && (
                    <div className="rs-empty">Round {roundNumber} — share the link and collect feedback, then submit one consolidated list.</div>
                  )}
                  {drafts.length > 0 && (
                    <div className="rs-round-drafts">
                      <div className="rs-round-drafts-head">
                        {drafts.length} draft note{drafts.length === 1 ? "" : "s"} → consolidated list
                      </div>
                      {drafts.map((c) => (
                        <div key={c.id} className="rs-round-draft">
                          <span className="rs-comment-at">@{fmtClock(c.time_s)}</span>
                          <span className="rs-round-draft-body">{c.body}</span>
                          <span className="rs-round-draft-author">{c.author_name}</span>
                        </div>
                      ))}
                      <textarea
                        value={submitNote}
                        onChange={(e) => setSubmitNote(e.target.value)}
                        placeholder="Note to the engineer (optional)"
                        className="rs-approval-note-input"
                        rows={2}
                      />
                      <button type="button" className="rs-btn approve" onClick={submitFeedback}>
                        Submit revision notes → Round {roundNumber + 1}
                      </button>
                    </div>
                  )}
                  {rounds.map((r) => (
                    <div key={r.id} className="rs-round-row">
                      <span className="rs-round-chip">Round {r.number}</span>
                      <span className="rs-round-stat">{r.request_count} requests</span>
                      <span className={`rs-round-stat ${r.status === "submitted" ? "open" : "closed"}`}>{r.status}</span>
                      {r.note && <span className="rs-round-note">“{r.note}”</span>}
                    </div>
                  ))}
                </div>

                <ApprovalPanel sessionId={session.id} version={current} approvals={approvals.filter((a) => a.version_id === current.id)} onDone={refresh} />

                <ReleasePackagePanel sessionId={session.id} version={current} />

                <div className="rs-share-block">
                  <div className="rs-versions-head">Review link</div>
                  <div className="rs-share">
                    <code>soundhub.app/r/{session.share_token}</code>
                    <button type="button" className="rs-btn ghost" onClick={copyLink}>
                      {copied ? "✓ Copied" : "Copy"}
                    </button>
                  </div>
                  <div className="rs-share-settings">
                    <div className="rs-share-row">
                      <label>
                        Permission
                        <select value={share.permission} onChange={(e) => setShare({ ...share, permission: e.target.value })} className="rs-select">
                          <option value="view">View only</option>
                          <option value="comment">Comment</option>
                          <option value="download">Comment + download</option>
                        </select>
                      </label>
                      <label>
                        Expires
                        <input type="date" value={share.expires} onChange={(e) => setShare({ ...share, expires: e.target.value })} className="rs-input" />
                      </label>
                    </div>
                    <label>
                      Password (optional)
                      <input
                        type="text"
                        value={share.password}
                        onChange={(e) => setShare({ ...share, password: e.target.value })}
                        placeholder={session.share_has_password && !share.password ? "leave blank to keep current" : "hunter2"}
                        className="rs-input"
                      />
                    </label>
                    <label>
                      Allowlist emails (comma-separated)
                      <input
                        type="text"
                        value={share.allowlist}
                        onChange={(e) => setShare({ ...share, allowlist: e.target.value })}
                        placeholder="aisha@label.com, artist@mail.com"
                        className="rs-input"
                      />
                    </label>
                    <label>
                      Feedback owner (consolidates notes)
                      <input
                        type="text"
                        value={feedbackOwner}
                        onChange={(e) => setFeedbackOwner(e.target.value)}
                        placeholder="aisha@label.com"
                        className="rs-input"
                      />
                    </label>
                    <label>
                      Included revision rounds
                      <input
                        type="number"
                        min={0}
                        max={50}
                        value={includedRounds}
                        onChange={(e) => setIncludedRounds(Number(e.target.value) || 0)}
                        className="rs-input"
                      />
                    </label>
                    <button type="button" className="rs-btn ghost" onClick={saveShare}>
                      Save share settings
                    </button>
                  </div>
                </div>

                {events.length > 0 && (
                  <div className="rs-audit">
                    <div className="rs-versions-head">Access log</div>
                    {events.slice(0, 8).map((e) => (
                      <div key={e.id} className="rs-audit-row">
                        <span className={`rs-audit-action ${e.action}`}>{e.action}</span>
                        <span>{e.actor}</span>
                        <span className="rs-audit-detail">{e.detail}</span>
                        <span className="rs-audit-time">{shortDate(e.created_at)}</span>
                      </div>
                    ))}
                  </div>
                )}

                <DecisionLog sessionId={session.id} />
              </div>
            </div>
          </div>
        </>
      ) : (
        <div className="rs-empty">
          <p>No versions yet. Upload your first bounce (WAV / MP3 / stems) to start a review.</p>
          <label className="rs-upload">
            {uploading ? "Uploading…" : "⬆ Upload first version"}
            <input
              type="file"
              accept=".wav,.mp3,.flac,.ogg,.aif,.aiff,.m4a,audio/*"
              hidden
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) void upload(f);
                e.target.value = "";
              }}
            />
          </label>
        </div>
      )}

      <button type="button" className="session-back-link" onClick={onBack}>
        ← back to sessions
      </button>
    </div>
  );
}

/* ---------- sessions list page ---------- */

export default function ReviewSessionPage() {
  const [sessions, setSessions] = useState<ReviewSession[]>([]);
  const [openId, setOpenId] = useState<number | null>(null);
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setSessions(await api.listSessions());
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed to load sessions");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const create = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    setBusy(true);
    setErr(null);
    try {
      const s = await api.createSession(name.trim());
      setName("");
      await load();
      setOpenId(s.id);
    } catch (err) {
      setErr(err instanceof Error ? err.message : "Failed to create session");
    } finally {
      setBusy(false);
    }
  };

  if (openId != null) {
    const s = sessions.find((x) => x.id === openId);
    if (!s) return null;
    return <SessionDetail session={s} onBack={() => setOpenId(null)} />;
  }

  return (
    <div className="session-page">
      <div className="session-top">
        <div>
          <Link to="/" className="session-back">
            ← back to home
          </Link>
          <h1 className="session-title">Review sessions</h1>
          <p className="muted session-sub">
            The Frame.io-style loop for music: share a version, collect timestamped
            feedback, fix, and approve. No ZIP archives, no Discord chaos.
          </p>
        </div>
      </div>

      <form className="session-create" onSubmit={create}>
        <input
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="New session name, e.g. Neon Warehouse"
          className="session-name-input"
        />
        <button type="submit" className="btn" disabled={busy}>
          {busy ? "Creating…" : "New session"}
        </button>
      </form>
      {err && <div className="error">{err}</div>}

      <div className="session-list">
        {sessions.length === 0 && (
          <div className="card muted">No sessions yet — create one and upload your first bounce.</div>
        )}
        {sessions.map((s) => (
          <div key={s.id} className="session-row" onClick={() => setOpenId(s.id)}>
            <div className="session-row-main">
              <span className="session-row-icon">🎧</span>
              <div>
                <div className="session-row-name">{s.name}</div>
                <div className="session-row-meta">
                  {s.version_count} version{s.version_count === 1 ? "" : "s"} · {s.latest_status || "no versions"}
                </div>
              </div>
            </div>
            <span
              className={`rs-status ${
                s.latest_status === "approved" ? "status-approved" : s.latest_status === "needs_changes" ? "status-changes" : "status-review"
              }`}
            >
              {s.latest_status || "empty"}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
