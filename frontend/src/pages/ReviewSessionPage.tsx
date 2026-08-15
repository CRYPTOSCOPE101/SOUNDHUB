import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api, getToken } from "../api";
import { fmtClock, WaveformCanvas, CommentComposer, ApprovalPanel } from "../components/ReviewShared";
import ABCompare from "../components/ABCompare";
import ReferenceCompare from "../components/ReferenceCompare";
import {
  humanSize,
  shortDate,
  DELIVERABLE_TYPES,
  STEM_LOGICAL_NAMES,
  CHANGE_ORDER_DECISIONS,
  REMINDER_CATEGORIES,
  type ChangeOrder,
  type LedgerEntry,
  type LedgerVerify,
  type NotificationOut,
  type PreflightResult,
  type ReferenceComparison,
  type ReferenceTrack,
  type ReleasePackage,
  type ReleaseTemplate,
  type ReminderSettings,
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
    case "deposit.paid":
      return `paid the booking deposit (${p.method}) — delivery unlocked`;
    case "round.extra_paid":
      return `paid for an extra revision round (${p.method})`;
    case "change_order.created":
      return `received a change request — ${String(p.reason).replace(/_/g, " ")}${p.description ? ` · “${p.description}”` : ""}`;
    case "change_order.quoted":
      return `quoted the change — ${String(p.decision).replace(/_/g, " ")}${p.price_cents ? ` · $${(Number(p.price_cents) / 100).toFixed(2)}` : " (courtesy)"}`;
    case "change_order.accepted":
      return `client accepted the change quote${p.price_cents ? ` · $${(Number(p.price_cents) / 100).toFixed(2)}` : " (courtesy)"}`;
    case "change_order.declined":
      return `declined the change request — ${String(p.reason).replace(/_/g, " ")}`;
    case "change_order.paid":
      return `paid for the change order${p.price_cents ? ` · $${(Number(p.price_cents) / 100).toFixed(2)}` : ""} — revision round granted`;
    case "change_order.round_opened":
      return `reopened Round ${p.round} for the change order (${String(p.reason).replace(/_/g, " ")})`;
    case "brief.updated":
      return `updated the client brief — ${p.service_type}${p.genre ? ` · ${p.genre}` : ""}${p.deadline ? ` · deadline ${String(p.deadline).slice(0, 10)}` : ""}`;
    case "reference.created":
      return `added reference “${p.title}”${p.artist ? ` by ${p.artist}` : ""} (${p.source_type === "external_url" ? "link" : "audio"}, ${p.visibility})`;
    case "reference.updated":
      return `updated reference “${p.title}”`;
    case "reference.removed":
      return `removed reference “${p.title}”`;
    case "reference.compared":
      return `compared ${p.version} vs reference “${p.reference}”${p.artist ? ` (${p.artist})` : ""} — ${p.level_match}`;
    case "notification.sent":
      return `📧 sent email reminder (${p.kind}) → ${p.recipient}`;
    case "notification.failed":
      return `⚠ email reminder failed (${p.kind}) → ${p.recipient}${p.error ? ` — ${p.error}` : ""}`;
    case "notification.dismissed":
      return `client dismissed email reminder (${p.kind})`;
    case "reminders.settings_updated":
      return `updated reminder settings — ${p.enabled ? "automation on" : "automation off"}${p.client_email ? ", client email set" : ""}`;
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
  if (e.event.startsWith("change_order")) return "🔄";
  if (e.event.startsWith("deposit")) return "💰";
  if (e.event.startsWith("notification") || e.event.startsWith("reminders")) return "📧";
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
  const [templates, setTemplates] = useState<ReleaseTemplate[]>([]);
  const [selectedTemplate, setSelectedTemplate] = useState("final_master");
  const [preflight, setPreflight] = useState<PreflightResult | null>(null);
  const [handoffOpen, setHandoffOpen] = useState(false);
  const [pluginManifest, setPluginManifest] = useState("");
  const [sessionManifest, setSessionManifest] = useState("");
  const [consolidate, setConsolidate] = useState(false);
  const [archiveExpires, setArchiveExpires] = useState("");
  const [showForceForm, setShowForceForm] = useState(false);
  const [confirmForce, setConfirmForce] = useState(false);
  const [forceReason, setForceReason] = useState("");
  const [lastVerified, setLastVerified] = useState("");

  const load = useCallback(async () => {
    try {
      const list = await api.listReleasePackages(sessionId);
      const p = list.find((p) => p.approved_version_id === version.id) ?? list[0] ?? null;
      setPkg(p);
      setInvoiceAmountCents(p?.amount_due_cents ?? null);
      setPluginManifest(p?.plugin_manifest ?? "");
      setSessionManifest(JSON.stringify(p?.session_manifest ?? {}, null, 2));
      setConsolidate(p?.consolidate_audio ?? false);
      setArchiveExpires(p?.archive_expires_at ? p.archive_expires_at.slice(0, 10) : "");
      setLastVerified(p?.last_verified_opened_at ? p.last_verified_opened_at.slice(0, 10) : "");
      setShowForceForm(false);
      setConfirmForce(false);
      setForceReason("");
      setPreflight(null);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed to load packages");
    }
  }, [sessionId, version.id]);

  useEffect(() => {
    void load();
    void api.listReleaseTemplates().then((t) => {
      setTemplates(t);
      setSelectedTemplate(t.some((x) => x.id === "final_master") ? "final_master" : (t[0]?.id ?? "custom"));
    }).catch(() => undefined);
  }, [load]);

  const create = async () => {
    setBusy(true);
    setErr(null);
    setInfo(null);
    try {
      const tpl = templates.find((t) => t.id === selectedTemplate);
      const p = await api.createReleasePackage(sessionId, version.id, tpl?.name ?? "Final delivery", selectedTemplate);
      // pre-add the approved master as the required master deliverable
      await api.addDeliverableFromVersion(p.id, "master", version.id);
      await load();
      setInfo(`Package created from “${tpl?.name ?? selectedTemplate}” — approved master added ✓`);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed to create package");
    } finally {
      setBusy(false);
    }
  };

  const runPreflight = async () => {
    if (!pkg) return;
    setErr(null);
    try {
      setPreflight(await api.runPreflight(pkg.id));
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Preflight failed");
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

  const lock = async (force = false) => {
    if (!pkg) return;
    if (force && !forceReason.trim()) {
      setErr("Write down why you're overriding QC — it goes into the manifest and the ledger.");
      return;
    }
    setBusy(true);
    setErr(null);
    setInfo(null);
    try {
      await api.lockReleasePackage(pkg.id, "master", lockNote, force, forceReason);
      await load();
      setInfo("RELEASE PACKAGE LOCKED ✓ — manifest hashed, delivery link opened");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Lock failed");
    } finally {
      setBusy(false);
    }
  };

  const saveHandoff = async () => {
    if (!pkg) return;
    setErr(null);
    try {
      let manifest: Record<string, unknown> = {};
      try {
        manifest = JSON.parse(sessionManifest || "{}");
      } catch {
        setErr("Session manifest must be valid JSON");
        return;
      }
      await api.updateHandoff(pkg.id, {
        plugin_manifest: pluginManifest,
        session_manifest: manifest,
        consolidate_audio: consolidate,
        archive_expires_at: archiveExpires ? `${archiveExpires}T23:59:59Z` : null,
        last_verified_opened_at: lastVerified ? `${lastVerified}T12:00:00Z` : null,
      });
      await load();
      setInfo("Handoff manifest saved ✓");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed to save handoff");
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
          <p>Master approved — pick a delivery preset, then assemble the package.</p>
          <label className="rs-brief-preset">
            Template
            <select value={selectedTemplate} onChange={(e) => setSelectedTemplate(e.target.value)} className="rs-select">
              {templates.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name} — {t.description}
                </option>
              ))}
              <option value="custom">Custom — build it manually</option>
            </select>
          </label>
          {templates.find((t) => t.id === selectedTemplate)?.note && (
            <p className="rs-brief-hint">{templates.find((t) => t.id === selectedTemplate)?.note}</p>
          )}
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
              <div className="rs-share-row">
                <button type="button" className="rs-btn ghost" onClick={runPreflight} disabled={pkg.deliverables.length === 0}>
                  {preflight ? "↻ Re-run preflight" : "✓ QC preflight"}
                </button>
                <button type="button" className="rs-btn approve" onClick={() => void lock(false)} disabled={busy || pkg.deliverables.length === 0}>
                  {busy ? "…" : "🔒 Lock approved master"}
                </button>
              </div>
              {preflight && (
                <div className="rs-preflight">
                  <div className="rs-preflight-head">
                    Pre-flight check{preflight.blocking ? " — blocking issues found" : preflight.checks.length ? " — clear" : ""}
                    {preflight.blocking && !preflight.passed && !showForceForm && (
                      <button type="button" className="rs-btn ghost sm" onClick={() => setShowForceForm(true)} title="Skip the blocking checks — you own the risk">
                        Lock anyway (force)
                      </button>
                    )}
                  </div>
                  {preflight.blocking && !preflight.passed && showForceForm && (
                    <div className="rs-force-lock">
                      <p className="rs-brief-hint">
                        ⚠️ A forced lock is recorded as <code>qc_status: forced</code> in the manifest and as a
                        dedicated ledger event — reason, unresolved warnings and who confirmed stay on record.
                      </p>
                      <textarea
                        value={forceReason}
                        onChange={(e) => setForceReason(e.target.value)}
                        rows={2}
                        placeholder="Why are you overriding QC? e.g. label moved the deadline, stems ship next week"
                        className="rs-approval-note-input"
                      />
                      <label className="rs-check">
                        <input type="checkbox" checked={confirmForce} onChange={(e) => setConfirmForce(e.target.checked)} />
                        I confirm the forced lock with the reason above
                      </label>
                      <div className="rs-share-row">
                        <button type="button" className="rs-btn approve sm" onClick={() => void lock(true)} disabled={busy || !forceReason.trim() || !confirmForce}>
                          {busy ? "…" : "Confirm forced lock"}
                        </button>
                        <button type="button" className="rs-btn ghost sm" onClick={() => { setShowForceForm(false); setConfirmForce(false); setForceReason(""); }}>
                          Back
                        </button>
                      </div>
                    </div>
                  )}
                  {preflight.checks.map((c, i) => (
                    <div key={i} className={`rs-preflight-row ${c.status}`}>
                      <span className="rs-preflight-icon">{c.status === "block" ? "✕" : c.status === "warn" ? "!" : "✓"}</span>
                      <span className="rs-preflight-label">{c.label}</span>
                      <span className="rs-preflight-detail">{c.detail}</span>
                    </div>
                  ))}
                </div>
              )}
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

          <details className="rs-handoff" open={handoffOpen} onToggle={(e) => setHandoffOpen((e.target as HTMLDetailsElement).open)}>
            <summary className="rs-versions-head">Archive & session handoff</summary>
            <p className="rs-brief-hint">
              Stem / archive / label handoffs are a separate, often paid service. Describe what the client gets
              and how long the archive is retained — never promise session restoration without a retention date.
            </p>
            <div className="rs-share-row">
              <label>
                Last verified opened
                <input type="date" value={lastVerified} onChange={(e) => setLastVerified(e.target.value)} className="rs-input" />
              </label>
              <label>
                Archive status
                <select
                  value={pkg.archive_status}
                  onChange={(e) => void api.setArchiveStatus(pkg.id, e.target.value).then(load)}
                  className="rs-select"
                >
                  <option value="available_now">Available now</option>
                  <option value="needs_preparation">Needs preparation</option>
                  <option value="archived">Archived</option>
                  <option value="permanently_deleted">Permanently deleted</option>
                </select>
              </label>
              <label>
                Archive expires
                <input type="date" value={archiveExpires} onChange={(e) => setArchiveExpires(e.target.value)} className="rs-input" />
              </label>
            </div>
            <label className="rs-check">
              <input type="checkbox" checked={consolidate} onChange={(e) => setConsolidate(e.target.checked)} />
              Consolidate audio — all files aligned to one start point
            </label>
            <label>
              Plugin manifest
              <textarea
                value={pluginManifest}
                onChange={(e) => setPluginManifest(e.target.value)}
                rows={2}
                placeholder="Ableton 12.1 · Serum 1.36 (missing: Ozone 11 → fallback stock EQ)"
                className="rs-approval-note-input"
              />
            </label>
            <label>
              Session manifest (JSON)
              <textarea
                value={sessionManifest}
                onChange={(e) => setSessionManifest(e.target.value)}
                rows={4}
                placeholder={'{"sample_rate": 48000, "bit_depth": 24, "tempo": 128, "key": "F min"}'}
                className="rs-approval-note-input"
              />
            </label>
            <button type="button" className="rs-btn ghost sm" onClick={saveHandoff}>
              Save handoff manifest
            </button>
            <p className="rs-brief-hint" style={{ marginTop: 6 }}>
              {pkg.archive_expires_at ? `Archive retained until ${shortDate(pkg.archive_expires_at)}` : "No archive expiry set — add one so the retention policy is explicit."}
            </p>
          </details>
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

/* ---------- client brief + service presets ---------- */

const SERVICE_PRESETS = [
  { id: "mix", label: "Mix", deliverables: "master, instrumental", included: 2, extraCents: 2500, desc: "A polished mix; master + instrumental in the delivery." },
  { id: "master", label: "Master", deliverables: "master", included: 1, extraCents: 1500, desc: "Final loudness + format for streaming or label." },
  { id: "mix_master", label: "Mix + master", deliverables: "master, instrumental, acapella", included: 2, extraCents: 3500, desc: "Mix and final master in one pass." },
  { id: "production", label: "Production", deliverables: "master, instrumental, acapella, clean_edit, stems", included: 3, extraCents: 5000, desc: "Full production deliverables, stems included." },
  { id: "stems", label: "Stem delivery", deliverables: "stems", included: 1, extraCents: 2000, desc: "Submix renders only." },
];

function ClientBriefPanel({
  session,
  onApplyPreset,
}: {
  session: ReviewSession;
  onApplyPreset: (included: number, extraCents: number | null) => Promise<void>;
}) {
  const [preset, setPreset] = useState<string>(session.service_type ?? "mix");
  const [serviceType, setServiceType] = useState(session.service_type ?? "mix");
  const [genre, setGenre] = useState(session.genre ?? "");
  const [goal, setGoal] = useState(session.goal ?? "");
  const [deadline, setDeadline] = useState(session.deadline_at ? session.deadline_at.slice(0, 10) : "");
  const [reviewStart, setReviewStart] = useState(session.review_start_at ? session.review_start_at.slice(0, 10) : "");
  const [refLinks, setRefLinks] = useState(session.reference_links ?? "");
  const [doNotChange, setDoNotChange] = useState(session.do_not_change ?? "");
  const [required, setRequired] = useState(session.required_deliverables ?? "");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);

  const applyPreset = async (id: string) => {
    const p = SERVICE_PRESETS.find((x) => x.id === id);
    if (!p) return;
    setPreset(p.id);
    setServiceType(p.id);
    setRequired(p.deliverables);
    setErr(null);
    setInfo(null);
    try {
      await onApplyPreset(p.included, p.extraCents);
      setInfo(`Preset “${p.label}” applied — included rounds (${p.included}) and extra-round price ($${(p.extraCents / 100).toFixed(2)}) updated too.`);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Preset failed");
    }
  };

  const save = async () => {
    setBusy(true);
    setErr(null);
    setInfo(null);
    try {
      await api.updateBrief(session.id, {
        service_type: serviceType,
        genre,
        goal,
        deadline_at: deadline ? `${deadline}T23:59:59Z` : null,
        review_start_at: reviewStart ? `${reviewStart}T09:00:00Z` : null,
        reference_links: refLinks,
        do_not_change: doNotChange,
        required_deliverables: required,
      });
      setInfo("Client brief saved ✓ — the client sees these rules on the review link.");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Save failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="rs-brief">
      <div className="rs-versions-head">Client brief</div>
      <p className="rs-brief-hint">
        Fix expectations before the first bounce — the client sees these rules on the review link.
      </p>
      <label className="rs-brief-preset">
        Service preset
        <select
          value={preset}
          onChange={(e) => void applyPreset(e.target.value)}
          className="rs-select"
        >
          {SERVICE_PRESETS.map((p) => (
            <option key={p.id} value={p.id}>
              {p.label} — {p.desc}
            </option>
          ))}
        </select>
      </label>
      <div className="rs-share-row">
        <label>
          Service
          <select value={serviceType} onChange={(e) => setServiceType(e.target.value)} className="rs-select">
            {SERVICE_PRESETS.map((p) => (
              <option key={p.id} value={p.id}>
                {p.label}
              </option>
            ))}
          </select>
        </label>
        <label>
          Goal
          <select value={goal} onChange={(e) => setGoal(e.target.value)} className="rs-select">
            <option value="">—</option>
            <option value="streaming">Streaming</option>
            <option value="label">Label release</option>
            <option value="sync">Sync</option>
            <option value="dj">DJ</option>
            <option value="social">Social media</option>
            <option value="other">Other</option>
          </select>
        </label>
      </div>
      <label>
        Genre
        <input type="text" value={genre} onChange={(e) => setGenre(e.target.value)} placeholder="e.g. Neo-soul / UK garage" className="rs-input" />
      </label>
      <div className="rs-share-row">
        <label>
          Review starts
          <input type="date" value={reviewStart} onChange={(e) => setReviewStart(e.target.value)} className="rs-input" />
        </label>
        <label>
          Deadline
          <input type="date" value={deadline} onChange={(e) => setDeadline(e.target.value)} className="rs-input" />
        </label>
      </div>
      <label>
        Reference tracks (one link per line)
        <textarea
          value={refLinks}
          onChange={(e) => setRefLinks(e.target.value)}
          rows={2}
          placeholder="https://soundcloud.com/…/ref1"
          className="rs-approval-note-input"
        />
      </label>
      <label>
        Required deliverables
        <input type="text" value={required} onChange={(e) => setRequired(e.target.value)} placeholder="master, instrumental, acapella…" className="rs-input" />
      </label>
      <label>
        What we will NOT change
        <textarea
          value={doNotChange}
          onChange={(e) => setDoNotChange(e.target.value)}
          rows={2}
          placeholder="e.g. keep the vocal balance as-is; don't touch the arrangement"
          className="rs-approval-note-input"
        />
      </label>
      <button type="button" className="rs-btn ghost" onClick={save} disabled={busy}>
        {busy ? "…" : "Save client brief"}
      </button>
      {info && <div className="success">{info}</div>}
      {err && <div className="error">{err}</div>}
    </div>
  );
}

/* ---------- reference tracks (mix/reference A/B) ---------- */

const PURPOSE_LABELS: Record<string, string> = {
  balance: "Balance",
  low_end: "Low end",
  vocal: "Vocal level",
  width: "Stereo width",
  arrangement: "Arrangement",
  overall: "Overall tone",
};

function ReferencePanel({
  sessionId,
  version,
  onCompare,
}: {
  sessionId: number;
  version: ReviewVersion;
  onCompare: (ref: import("../types").ReferenceTrack, c: import("../types").ReferenceComparison) => void;
}) {
  const [refs, setRefs] = useState<import("../types").ReferenceTrack[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [artist, setArtist] = useState("");
  const [url, setUrl] = useState("");
  const [purpose, setPurpose] = useState("overall");
  const [visibility, setVisibility] = useState("reviewers");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [compareBusy, setCompareBusy] = useState<number | null>(null);

  const load = useCallback(async () => {
    setRefs(await api.listReferences(sessionId));
  }, [sessionId]);

  useEffect(() => {
    void load();
  }, [load]);

  const addUrl = async () => {
    if (!title.trim() || !url.trim()) {
      setErr("Title and URL are required");
      return;
    }
    setBusy(true);
    setErr(null);
    try {
      await api.createReferenceUrl(sessionId, { title: title.trim(), artist, external_url: url.trim(), purpose, visibility, note });
      setTitle("");
      setArtist("");
      setUrl("");
      setNote("");
      await load();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed to add reference");
    } finally {
      setBusy(false);
    }
  };

  const upload = async (file: File) => {
    if (!title.trim()) {
      setErr("Give the reference a title first");
      return;
    }
    setBusy(true);
    setErr(null);
    try {
      await api.uploadReference(sessionId, { title: title.trim(), artist, purpose, visibility, note, file });
      setTitle("");
      setArtist("");
      setNote("");
      await load();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setBusy(false);
    }
  };

  const remove = async (refId: number) => {
    await api.deleteReference(sessionId, refId);
    await load();
  };

  const compare = async (ref: import("../types").ReferenceTrack) => {
    setCompareBusy(ref.id);
    setErr(null);
    try {
      const c = await api.createReferenceComparison(sessionId, {
        versionId: version.id,
        referenceId: ref.id,
        startMs: 0,
        endMs: null,
      });
      onCompare(ref, c);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Comparison failed");
    } finally {
      setCompareBusy(null);
    }
  };

  const canCompare = (ref: import("../types").ReferenceTrack) => ref.source_type === "private_upload" && ref.analysis_status === "done";

  return (
    <div className="rs-refs">
      <div className="rs-versions-head">References</div>
      <p className="rs-brief-hint">
        Orientation tracks for mix/reference A/B — private to this session, never delivered.
      </p>
      {refs === null ? (
        <div className="rs-empty">Loading references…</div>
      ) : refs.length === 0 ? (
        <div className="rs-empty">No references yet. Add a link, or upload a file you have rights to.</div>
      ) : (
        <div className="rs-ref-list">
          {refs.map((r) => (
            <div key={r.id} className="rs-ref-row">
              <div className="rs-ref-main">
                <div className="rs-ref-title">
                  {r.title}
                  {r.artist && <span className="rs-ref-artist"> · {r.artist}</span>}
                </div>
                <div className="rs-ref-meta">
                  <span className={`rs-req-status st-${r.source_type === "private_upload" ? "verified" : "draft"}`}>
                    {r.source_type === "private_upload" ? "audio" : "link"}
                  </span>
                  <span className="rs-ref-purpose">{PURPOSE_LABELS[r.purpose] ?? r.purpose}</span>
                  <span className="rs-ref-vis">{r.visibility === "reviewers" ? "reviewers" : "engineer only"}</span>
                  {r.integrated_lufs != null && <span className="rs-ref-metric">{r.integrated_lufs} LUFS</span>}
                  {r.true_peak_dbtp != null && <span className="rs-ref-metric">{r.true_peak_dbtp} dBTP</span>}
                  {r.sample_rate ? <span className="rs-ref-metric">{(r.sample_rate / 1000).toFixed(1)} kHz</span> : null}
                </div>
                {r.note && <div className="rs-ref-note">“{r.note}”</div>}
                {r.source_type === "external_url" && r.external_url && (
                  <a href={r.external_url} target="_blank" rel="noreferrer" className="rs-ref-link">
                    {r.external_url.replace(/^https?:\/\//, "")} ↗
                  </a>
                )}
              </div>
              <div className="rs-ref-actions">
                <button
                  type="button"
                  className="rs-btn ghost sm"
                  disabled={!canCompare(r) || compareBusy === r.id}
                  title={canCompare(r) ? `A/B ${version.label} vs this reference` : "Uploaded reference with analysis required"}
                  onClick={() => void compare(r)}
                >
                  {compareBusy === r.id ? "…" : `A/B with ${version.label}`}
                </button>
                <button type="button" className="rs-btn ghost sm" onClick={() => void remove(r.id)}>
                  ✕
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="rs-ref-add">
        <div className="rs-share-row">
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Reference title"
            className="rs-input"
            style={{ margin: 0 }}
          />
          <input
            type="text"
            value={artist}
            onChange={(e) => setArtist(e.target.value)}
            placeholder="Artist (optional)"
            className="rs-input"
            style={{ margin: 0 }}
          />
        </div>
        <div className="rs-share-row">
          <select value={purpose} onChange={(e) => setPurpose(e.target.value)} className="rs-select" style={{ margin: 0 }}>
            {Object.entries(PURPOSE_LABELS).map(([k, v]) => (
              <option key={k} value={k}>
                {v}
              </option>
            ))}
          </select>
          <select value={visibility} onChange={(e) => setVisibility(e.target.value)} className="rs-select" style={{ margin: 0 }}>
            <option value="reviewers">visible to reviewers</option>
            <option value="engineer_only">engineer only</option>
          </select>
        </div>
        <input
          type="text"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="External URL (SoundCloud, Spotify…) — opened in a new tab"
          className="rs-input"
        />
        <textarea
          value={note}
          onChange={(e) => setNote(e.target.value)}
          rows={1}
          placeholder="Note — e.g. oriented by low end and width"
          className="rs-approval-note-input"
        />
        <div className="rs-ref-add-actions">
          <button type="button" className="rs-btn ghost sm" onClick={addUrl} disabled={busy}>
            + Add link reference
          </button>
          <label className="rs-btn ghost sm">
            + Upload private reference
            <input
              type="file"
              accept=".wav,.mp3,.flac,.aif,.aiff,.m4a,.ogg,audio/*"
              hidden
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) void upload(f);
                e.target.value = "";
              }}
            />
          </label>
        </div>
      </div>
      {err && <div className="error">{err}</div>}
      <p className="rs-ref-disclaimer">
        Reference audio is private to this review session and is never delivered, redistributed, or included in release
        exports.
      </p>
    </div>
  );
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

/* ---------- change orders (late changes after approval/delivery) ---------- */

const REASON_LABELS: Record<string, string> = {
  mix_revision: "Mix revision",
  new_stem_request: "New stem request",
  format_change: "Format change",
  mastering_recall: "Mastering recall",
};

const DECISION_LABELS: Record<string, string> = {
  courtesy: "Included courtesy change",
  paid_round: "Paid revision round",
  new_mastering_pass: "New mastering pass",
};

function ChangeOrdersPanel({ sessionId }: { sessionId: number }) {
  const [orders, setOrders] = useState<ChangeOrder[]>([]);
  const [quote, setQuote] = useState<Record<number, { decision: string; price: string; deadline: string }>>({});
  const [err, setErr] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const rows = await api.listChangeOrders(sessionId);
      setOrders(rows);
      setQuote((prev) => {
        const next = { ...prev };
        for (const co of rows) {
          if (!next[co.id]) next[co.id] = { decision: "paid_round", price: "", deadline: "" };
        }
        return next;
      });
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed to load change orders");
    }
  }, [sessionId]);

  useEffect(() => {
    void load();
  }, [load]);

  const act = async (fn: () => Promise<unknown>) => {
    setBusy(true);
    setErr(null);
    setInfo(null);
    try {
      await fn();
      await load();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Action failed");
    } finally {
      setBusy(false);
    }
  };

  const quoteOrder = (co: ChangeOrder) =>
    act(() => {
      const q = quote[co.id];
      const price = q.price === "" ? null : Number(q.price);
      return api.quoteChangeOrder(sessionId, co.id, q.decision, price, q.deadline ? `${q.deadline}T23:59:59Z` : null);
    });

  const money = (cents: number | null) =>
    cents == null ? "" : new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(cents / 100);

  if (orders.length === 0) return null;

  return (
    <div className="rs-change-orders">
      <div className="rs-versions-head">Change orders <span className="rs-round-stat">late changes after approval</span></div>
      <p className="rs-brief-hint">
        “We came back after three months, fix it for free” — the client requests, you quote (courtesy / paid round /
        new mastering pass) or decline, they accept, and the round reopens as Round {orders[0] ? `N+1` : ""}.
      </p>
      {orders.map((co) => (
        <div key={co.id} className={`rs-co ${co.status}`}>
          <div className="rs-co-head">
            <span className="rs-co-reason">{REASON_LABELS[co.reason] ?? co.reason}</span>
            <span className={`rs-round-stat ${co.status === "declined" ? "closed" : "open"}`}>{co.status}</span>
            {co.round_granted && <span className="rs-round-stat open">✓ round reopened</span>}
          </div>
          <p className="rs-co-desc">“{co.description || "No details"}” — {co.created_by}</p>
          <div className="rs-co-meta">
            {co.decision && <span>{DECISION_LABELS[co.decision] ?? co.decision}</span>}
            {co.price_cents != null && <span>{money(co.price_cents)}</span>}
            {co.deadline_at && <span>by {new Date(co.deadline_at).toLocaleDateString()}</span>}
            <span>reopens Round {co.target_round}</span>
            {co.quote_version > 0 && <span>quote v{co.quote_version}</span>}
            {co.quote_expires_at && co.status === "quoted" && (
              <span className={new Date(co.quote_expires_at) < new Date() ? "rs-round-stat closed" : ""}>
                quote {new Date(co.quote_expires_at) < new Date() ? "expired" : `expires ${new Date(co.quote_expires_at).toLocaleDateString()}`}
              </span>
            )}
            {co.accepted_at && <span>accepted {shortDate(co.accepted_at)}</span>}
          </div>
          {co.status === "requested" || co.status === "quoted" || co.status === "expired" ? (
            <div className="rs-co-actions">
              <select
                value={quote[co.id]?.decision ?? "paid_round"}
                onChange={(e) => setQuote({ ...quote, [co.id]: { ...quote[co.id], decision: e.target.value } })}
                className="rs-select"
              >
                {CHANGE_ORDER_DECISIONS.map((d) => (
                  <option key={d} value={d}>{DECISION_LABELS[d]}</option>
                ))}
              </select>
              <input
                type="number"
                min={0}
                value={quote[co.id]?.price ?? ""}
                onChange={(e) => setQuote({ ...quote, [co.id]: { ...quote[co.id], price: e.target.value } })}
                placeholder="price (cents) — blank = preset fee"
                className="rs-input"
                style={{ width: 180 }}
              />
              <input
                type="date"
                value={quote[co.id]?.deadline ?? ""}
                onChange={(e) => setQuote({ ...quote, [co.id]: { ...quote[co.id], deadline: e.target.value } })}
                className="rs-input"
              />
              <button type="button" className="rs-btn approve sm" disabled={busy} onClick={() => void quoteOrder(co)}>
                {co.status === "requested" ? "Send quote" : "Re-quote (v" + ((co.quote_version || 0) + 1) + ")"}
              </button>
              <button type="button" className="rs-btn ghost sm" disabled={busy} onClick={() => void act(() => api.declineChangeOrder(sessionId, co.id))}>
                Decline
              </button>
            </div>
          ) : null}
          {co.status === "accepted" && !co.round_granted && (co.price_cents ?? 0) > 0 && (
            <div className="rs-co-actions">
              <span className="rs-round-stat open">Client accepted — collect the payment, then the round reopens</span>
              <button type="button" className="rs-btn ghost sm" disabled={busy} onClick={() => void act(() => api.markChangeOrderPaid(sessionId, co.id))}>
                ✓ Mark paid (manual)
              </button>
              <button
                type="button"
                className="rs-btn approve sm"
                disabled={busy}
                onClick={() =>
                  void act(async () => {
                    const c = await api.changeOrderCheckout(sessionId, co.id);
                    window.location.href = c.checkout_url;
                  })
                }
              >
                💳 Open checkout
              </button>
            </div>
          )}
        </div>
      ))}
      {err && <div className="error">{err}</div>}
      {info && <div className="success">{info}</div>}
    </div>
  );
}

function RemindersPanel({ sessionId }: { sessionId: number }) {
  const [settings, setSettings] = useState<ReminderSettings | null>(null);
  const [notifs, setNotifs] = useState<NotificationOut[]>([]);
  const [email, setEmail] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const r = await api.sessionReminders(sessionId);
      setSettings(r.settings);
      setNotifs(r.notifications);
      setEmail(r.settings.client_email);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed to load reminders");
    }
  }, [sessionId]);

  useEffect(() => {
    void load();
  }, [load]);

  const save = async (patch: Partial<ReminderSettings>) => {
    setBusy(true);
    setErr(null);
    try {
      await api.updateReminderSettings(sessionId, patch);
      await load();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Save failed");
    } finally {
      setBusy(false);
    }
  };

  const runNow = async () => {
    setBusy(true);
    setErr(null);
    try {
      await api.evaluateReminders();
      await load();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Evaluate failed");
    } finally {
      setBusy(false);
    }
  };

  if (!settings) return <div className="rs-empty">Loading reminders…</div>;

  const cats = settings.reminder_categories ? settings.reminder_categories.split(",").map((s) => s.trim()).filter(Boolean) : [];

  const toggleCat = (id: string) => {
    const next = cats.includes(id) ? cats.filter((c) => c !== id) : [...cats, id];
    void save({ reminder_categories: next.join(",") });
  };

  return (
    <div className="rs-reminders">
      <div className="rs-versions-head">Email reminders <span className="rs-round-stat">deadlines & nudges</span></div>
      <p className="rs-brief-hint">
        Nudge the client instead of chasing: review opened, feedback deadlines, idle drafts, invoice due,
        quote expiring, archive & delivery-link expiry. One email per type per 24h, everything logged in the decision ledger.
      </p>
      <div className="rs-rem-row">
        <span className="rs-rem-label">Automated reminders</span>
        <button
          type="button"
          className={`rs-btn sm ${settings.reminders_enabled ? "approve" : "ghost"}`}
          disabled={busy}
          onClick={() => void save({ reminders_enabled: !settings.reminders_enabled })}
        >
          {settings.reminders_enabled ? "● On" : "○ Off"}
        </button>
      </div>
      <div className="rs-rem-row">
        <span className="rs-rem-label">Client email</span>
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="aisha@label.com — where reminders go"
          className="rs-input"
          style={{ flex: 1 }}
        />
        <button type="button" className="rs-btn ghost sm" disabled={busy} onClick={() => void save({ client_email: email })}>
          Save
        </button>
      </div>
      {!settings.client_email && (
        <div className="rs-round-stat closed" style={{ marginTop: 6 }}>
          Set a client email to enable reminders for this session.
        </div>
      )}
      <div className="rs-rem-cats">
        {REMINDER_CATEGORIES.map((c) => (
          <button
            key={c.id}
            type="button"
            className={`rs-chip ${cats.length === 0 || cats.includes(c.id) ? "on" : ""}`}
            title={cats.length === 0 ? "All categories are on (empty = all)" : c.label}
            onClick={() => void toggleCat(c.id)}
          >
            {c.label}
          </button>
        ))}
      </div>
      <div className="rs-rem-row" style={{ marginTop: 6 }}>
        <button type="button" className="rs-btn ghost sm" disabled={busy} onClick={() => void runNow()}>
          ⚡ Evaluate & send now
        </button>
        <span className="rs-round-stat">cron-friendly: re-running never duplicates</span>
      </div>
      {settings.client_opted_out && (
        <div className="rs-round-stat closed" style={{ marginTop: 6 }}>
          Client opted out of non-critical reminders — payment & delivery emails still go.
        </div>
      )}
      {notifs.length > 0 && (
        <div className="rs-rem-log">
          {notifs.slice(0, 25).map((n) => (
            <div key={n.id} className="rs-rem-row">
              <span className={`rs-round-stat ${n.status === "sent" ? "open" : n.status === "failed" ? "closed" : ""}`}>{n.status}</span>
              <span className="rs-rem-kind">{n.kind}</span>
              <span className="rs-rem-sub">{n.subject}</span>
            </div>
          ))}
        </div>
      )}
      {err && <div className="error">{err}</div>}
    </div>
  );
}

function SessionDetail({ session, onBack }: { session: ReviewSession; onBack: () => void }) {
  const [versions, setVersions] = useState<ReviewVersion[]>(session.versions ?? []);
  const [approvals, setApprovals] = useState<ReviewApproval[]>(session.approvals ?? []);
  const [rounds, setRounds] = useState(session.rounds ?? []);
  const [events, setEvents] = useState(session.access_events ?? []);
  const [roundNumber, setRoundNumber] = useState(session.round_number ?? 1);
  const [roundsOpen, setRoundsOpen] = useState(session.rounds_open ?? true);
  const [feedbackOwner, setFeedbackOwner] = useState(session.feedback_owner ?? "");
  const [includedRounds, setIncludedRounds] = useState(session.included_rounds ?? 1);
  const [depositCents, setDepositCents] = useState<number | null>(session.deposit_due_cents ?? null);
  const [depositStatus, setDepositStatus] = useState(session.deposit_status ?? "none");
  const [extraRoundCents, setExtraRoundCents] = useState<number | null>(session.extra_round_price_cents ?? null);
  const [roundsPaid, setRoundsPaid] = useState(session.rounds_paid ?? 0);
  const [portfolioPublic, setPortfolioPublic] = useState(session.portfolio_public ?? false);
  const [watermarkEnabled, setWatermarkEnabled] = useState(session.watermark_enabled ?? true);
  const [retentionUntil, setRetentionUntil] = useState(session.retention_until ? session.retention_until.slice(0, 10) : "");
  const [recallFeeCents, setRecallFeeCents] = useState<number | null>(session.recall_fee_cents ?? null);
  const [revisionFeeCents, setRevisionFeeCents] = useState<number | null>(session.revision_fee_cents ?? null);
  const [payPrompt, setPayPrompt] = useState<"deposit" | "extra_round" | null>(null);
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
  const [refCompare, setRefCompare] = useState<{ ref: ReferenceTrack; comp: ReferenceComparison } | null>(null);
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
    setDepositCents(s.deposit_due_cents ?? null);
    setDepositStatus(s.deposit_status ?? "none");
    setExtraRoundCents(s.extra_round_price_cents ?? null);
    setRoundsPaid(s.rounds_paid ?? 0);
    setPortfolioPublic(s.portfolio_public ?? false);
    setWatermarkEnabled(s.watermark_enabled ?? true);
    setRetentionUntil(s.retention_until ? s.retention_until.slice(0, 10) : "");
    setRecallFeeCents(s.recall_fee_cents ?? null);
    setRevisionFeeCents(s.revision_fee_cents ?? null);
    setPayPrompt(null);
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
    setPayPrompt(null);
    try {
      await api.submitFeedback(session.id, submitNote);
      setSubmitNote("");
      setInfo("Feedback consolidated — round closed, next round opened ✓");
      await refresh();
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Submit failed";
      setErr(msg);
      if (msg.toLowerCase().includes("round")) setPayPrompt("extra_round");
    }
  };

  const pay = async (kind: "deposit" | "extra_round") => {
    setErr(null);
    setInfo(null);
    try {
      const c = await api.createSessionCheckout(session.id, kind);
      window.location.href = c.checkout_url;
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Checkout failed");
    }
  };

  const applyPreset = async (included: number, extraCents: number | null) => {
    setErr(null);
    setIncludedRounds(included);
    setExtraRoundCents(extraCents);
    await api.updateShareSettings(session.id, {
      included_rounds: included,
      extra_round_price_cents: extraCents,
    });
    await refresh();
  };

  const saveCommerce = async () => {
    setErr(null);
    try {
      await api.updateShareSettings(session.id, {
        deposit_due_cents: depositCents,
        deposit_status: depositStatus,
        extra_round_price_cents: extraRoundCents,
        rounds_paid: roundsPaid,
        portfolio_public: portfolioPublic,
        watermark_enabled: watermarkEnabled,
        retention_until: retentionUntil ? `${retentionUntil}T23:59:59Z` : null,
        recall_fee_cents: recallFeeCents,
        revision_fee_cents: revisionFeeCents,
      });
      setInfo("Payment & portfolio settings saved ✓");
      await refresh();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed to save settings");
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
        <span className="rs-round-stat muted" title="Included revision rounds + extra rounds already paid for">
          budget: {includedRounds} incl{roundsPaid > 0 ? ` + ${roundsPaid} paid` : ""}
        </span>
        {depositStatus === "deposit_due" && (
          <span className="rs-round-stat due">💰 deposit due{depositCents ? ` · $${(depositCents / 100).toFixed(2)}` : ""}</span>
        )}
        {depositStatus === "paid" && <span className="rs-round-stat open">💰 deposit paid</span>}
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
                {v.watermarked && (
                  <span className="rs-wm-chip" title="Guests hear an audible watermark on this preview — approved versions are clean">
                    🔊
                  </span>
                )}
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

          {/* mix ↔ reference A/B panel */}
          {refCompare && (
            <ReferenceCompare
              comparison={refCompare.comp}
              reference={refCompare.ref}
              onClose={() => setRefCompare(null)}
            />
          )}

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
                {current.watermarked && (
                  <span className="rs-wm-chip" title="Audible watermark is mixed into the guest preview of this version">
                    🔊 watermarked preview
                  </span>
                )}
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
                      {c.voice_format && (
                        <audio controls preload="none" src={api.voiceAudioUrl(session.id, current.id, c.id)} className="rs-voice" style={{ width: "100%", marginTop: 6 }} />
                      )}
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

                {/* references — mix/reference A/B (private, non-deliverable) */}
                <ReferencePanel
                  sessionId={session.id}
                  version={current}
                  onCompare={(ref, comp) => setRefCompare({ ref, comp })}
                />

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
                      {payPrompt === "extra_round" && (
                        <div className="rs-pay-prompt">
                          <span>Round {roundNumber + 1} is beyond the included budget</span>
                          <button
                            type="button"
                            className="rs-btn approve sm"
                            onClick={() => void pay("extra_round")}
                            title="Stripe Checkout — card / Apple Pay / Google Pay"
                          >
                            💳 Pay for extra round{extraRoundCents ? ` · $${(extraRoundCents / 100).toFixed(2)}` : ""}
                          </button>
                        </div>
                      )}
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

                <ChangeOrdersPanel sessionId={session.id} />

                <RemindersPanel sessionId={session.id} />

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

                  <div className="rs-share-settings">
                    <div className="rs-versions-head">Money & showcase</div>
                    <div className="rs-share-row">
                      <label>
                        Booking deposit (cents)
                        <input
                          type="number"
                          min={0}
                          value={depositCents ?? ""}
                          onChange={(e) => setDepositCents(e.target.value === "" ? null : Number(e.target.value))}
                          placeholder="e.g. 5000 = $50"
                          className="rs-input"
                        />
                      </label>
                      <label>
                        Status
                        <select value={depositStatus} onChange={(e) => setDepositStatus(e.target.value)} className="rs-select">
                          <option value="none">none</option>
                          <option value="deposit_due">deposit due</option>
                          <option value="paid">paid</option>
                          <option value="waived">waived</option>
                        </select>
                      </label>
                    </div>
                    {depositStatus === "deposit_due" && (
                      <div className="rs-pay-prompt">
                        <span>Client pays the booking deposit via the share link</span>
                        <button type="button" className="rs-btn approve sm" onClick={() => void pay("deposit")}>
                          💳 Pay deposit{depositCents ? ` · $${(depositCents / 100).toFixed(2)}` : ""}
                        </button>
                      </div>
                    )}
                    <label>
                      Extra round price (cents)
                      <input
                        type="number"
                        min={0}
                        value={extraRoundCents ?? ""}
                        onChange={(e) => setExtraRoundCents(e.target.value === "" ? null : Number(e.target.value))}
                        placeholder="e.g. 2500 = $25 per revision beyond included"
                        className="rs-input"
                      />
                    </label>
                    {roundsPaid > 0 && (
                      <div className="rs-round-stat open" style={{ marginBottom: 8 }}>
                        ✓ {roundsPaid} extra round{roundsPaid === 1 ? "" : "s"} paid
                      </div>
                    )}
                    <label className="rs-check">
                      <input
                        type="checkbox"
                        checked={portfolioPublic}
                        onChange={(e) => setPortfolioPublic(e.target.checked)}
                      />
                      Show on public portfolio ({window.location.origin}/p/{session.owner_username})
                    </label>
                    <label className="rs-check">
                      <input
                        type="checkbox"
                        checked={watermarkEnabled}
                        onChange={(e) => setWatermarkEnabled(e.target.checked)}
                      />
                      Watermark unapproved previews for guests
                    </label>
                    <div className="rs-share-row">
                      <label>
                        Revision fee (cents)
                        <input
                          type="number"
                          min={0}
                          value={revisionFeeCents ?? ""}
                          onChange={(e) => setRevisionFeeCents(e.target.value === "" ? null : Number(e.target.value))}
                          placeholder="one-off mix revision, e.g. 4500"
                          className="rs-input"
                        />
                      </label>
                      <label>
                        Recall fee (cents)
                        <input
                          type="number"
                          min={0}
                          value={recallFeeCents ?? ""}
                          onChange={(e) => setRecallFeeCents(e.target.value === "" ? null : Number(e.target.value))}
                          placeholder="mastering recall / new pass, e.g. 12000"
                          className="rs-input"
                        />
                      </label>
                    </div>
                    <label>
                      Project archive retained until
                      <input
                        type="date"
                        value={retentionUntil}
                        onChange={(e) => setRetentionUntil(e.target.value)}
                        className="rs-input"
                      />
                    </label>
                    <p className="rs-brief-hint" style={{ marginTop: 4 }}>
                      🛡 Late changes after approval go through a change order — the client requests, you quote
                      (courtesy / paid round / new pass), they accept, and the round reopens. Fees above become
                      the default quote. Retention tells the client how long the archive is kept.
                    </p>
                    <button type="button" className="rs-btn ghost" onClick={saveCommerce}>
                      Save payment & portfolio settings
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

      <ClientBriefPanel session={session} onApplyPreset={applyPreset} />

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
