import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../api";
import { humanSize, shortDate, type DeliveryPage, type Deliverable } from "../types";

export default function PublicDeliveryPage() {
  const { token } = useParams<{ token: string }>();
  const [page, setPage] = useState<DeliveryPage | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [downloading, setDownloading] = useState<number | null>(null);
  const [dlErr, setDlErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!token) return;
    setLoaded(false);
    setErr(null);
    try {
      setPage(await api.publicDeliveryPage(token));
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Delivery link not found");
    } finally {
      setLoaded(true);
    }
  }, [token]);

  useEffect(() => {
    void load();
  }, [load]);

  const download = async (d: Deliverable) => {
    if (!token) return;
    setDownloading(d.id);
    setDlErr(null);
    try {
      const blob = await api.publicDeliveryDownload(token, d.id);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = d.filename;
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 4000);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Download failed";
      setDlErr(msg);
      if (msg.toLowerCase().includes("payment")) {
        setDlErr("💳 Payment required — the engineer has set an outstanding balance on this delivery.");
      }
    } finally {
      setDownloading(null);
    }
  };

  if (err) {
    return (
      <div className="session-page">
        <div className="card error">🔗 {err} — this delivery link doesn't exist.</div>
      </div>
    );
  }

  if (!loaded || !page) {
    return <div className="session-page muted">Loading delivery…</div>;
  }

  const locked = page.status === "ready" || page.status === "delivered";
  const gate = page.invoice_status === "balance_due" || page.invoice_status === "deposit_due";

  return (
    <div className="public-delivery">
      <div className="public-delivery-brand">
        <img src="/logo.png" alt="SoundHub" className="landing-nav-logo" /> SoundHub
        <span className="public-review-sep">·</span>
        <span className="public-review-for">final delivery</span>
      </div>

      <div className="public-delivery-card">
        <div className="public-delivery-head">
          <div>
            <h1 className="public-delivery-title">{page.name}</h1>
            <p className="muted">
              {page.approved_label} · approved master · locked by {page.locked_by}
              {page.immutable_at ? ` · ${shortDate(page.immutable_at)}` : ""}
            </p>
          </div>
          {locked && <div className="rs-release-status st-ready">🔒 LOCKED</div>}
        </div>

        {page.manifest_hash && (
          <div className="public-delivery-manifest">
            Manifest SHA-256: <code>{page.manifest_hash}</code>
          </div>
        )}

        {gate && (
          <div className="public-delivery-gate">
            💳 {page.invoice_status === "balance_due" ? "Outstanding balance" : "Deposit due"} — files unlock once the
            engineer marks the payment received.
          </div>
        )}

        <div className="public-delivery-files">
          {page.deliverables.map((d) => (
            <div key={d.id} className="public-delivery-file">
              <span className="public-delivery-type">{d.type}</span>
              <span className="public-delivery-name">{d.filename}</span>
              <span className="public-delivery-meta">
                {humanSize(d.size)} · {d.format}
                {d.sample_rate ? ` · ${(d.sample_rate / 1000).toFixed(1)} kHz / ${d.bit_depth}-bit` : ""}
              </span>
              <button
                type="button"
                className="rs-btn approve sm"
                onClick={() => void download(d)}
                disabled={downloading === d.id || gate}
              >
                {downloading === d.id ? "…" : gate ? "Locked" : "Download"}
              </button>
            </div>
          ))}
        </div>

        {dlErr && <div className="error">{dlErr}</div>}

        <p className="public-delivery-note">
          This package is immutable: each file is pinned to the approved version by its SHA-256 checksum.{" "}
          {page.approved_filename} cannot be silently swapped.
        </p>
      </div>
    </div>
  );
}
