import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../api";
import { humanSize, shortDate, type DeliveryPage, type Deliverable } from "../types";

export default function PublicDeliveryPage() {
  const { token } = useParams<{ token: string }>();
  const params = new URLSearchParams(window.location.search);
  const justPaid = params.get("paid") === "1";
  const [page, setPage] = useState<DeliveryPage | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [downloading, setDownloading] = useState<number | null>(null);
  const [dlErr, setDlErr] = useState<string | null>(null);
  const [paying, setPaying] = useState(false);
  const [payErr, setPayErr] = useState<string | null>(null);

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
      } else if (msg.toLowerCase().includes("deposit")) {
        setDlErr("💳 Booking deposit required — pay it above to unlock the files.");
      }
    } finally {
      setDownloading(null);
    }
  };

  const pay = async () => {
    if (!token) return;
    setPaying(true);
    setPayErr(null);
    try {
      const checkout = await api.publicCheckout(token);
      window.location.href = checkout.checkout_url;
    } catch (e) {
      setPayErr(e instanceof Error ? e.message : "Failed to start checkout");
    } finally {
      setPaying(false);
    }
  };

  const fmtMoney = (cents: number, currency: string) => {
    try {
      return new Intl.NumberFormat("en-US", {
        style: "currency",
        currency: currency.toUpperCase(),
      }).format(cents / 100);
    } catch {
      return `${currency.toUpperCase()} ${(cents / 100).toFixed(2)}`;
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
  const depositDue = page.deposit_status === "deposit_due";
  const gate = page.invoice_status === "balance_due" || page.invoice_status === "deposit_due" || depositDue;

  const payDeposit = async () => {
    if (!token) return;
    setPaying(true);
    setPayErr(null);
    try {
      const checkout = await api.publicCheckout(token, "deposit");
      window.location.href = checkout.checkout_url;
    } catch (e) {
      setPayErr(e instanceof Error ? e.message : "Failed to start checkout");
    } finally {
      setPaying(false);
    }
  };

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

        {justPaid && page.invoice_status === "paid" && (
          <div className="public-delivery-paid">✓ Payment received — delivery unlocked.</div>
        )}

        {page.manifest_hash && (
          <div className="public-delivery-manifest">
            Manifest SHA-256: <code>{page.manifest_hash}</code>
          </div>
        )}

        {depositDue && (
          <div className="public-delivery-gate">
            <div className="public-delivery-gate-text">
              💳 Booking deposit due
              {page.deposit_due_cents ? ` — ${fmtMoney(page.deposit_due_cents, page.currency)}` : ""}
              <span className="public-delivery-gate-sub">
                The engineer requires a booking deposit before the final files are handed over.
              </span>
            </div>
            <button type="button" className="rs-btn approve" onClick={() => void payDeposit()} disabled={paying}>
              {paying ? "Opening checkout…" : "💳 Pay deposit"}
            </button>
          </div>
        )}
        {gate && !depositDue && (
          <div className="public-delivery-gate">
            <div className="public-delivery-gate-text">
              💳 {page.invoice_status === "balance_due" ? "Outstanding balance" : "Deposit due"}
              {page.amount_due_cents ? ` — ${fmtMoney(page.amount_due_cents, page.currency)}` : ""}
              <span className="public-delivery-gate-sub">
                Pay to unlock the approved files. Card, Apple Pay and Google Pay accepted.
              </span>
            </div>
            <button type="button" className="rs-btn approve" onClick={() => void pay()} disabled={paying}>
              {paying ? "Opening checkout…" : "💳 Pay with card"}
            </button>
          </div>
        )}
        {payErr && <div className="error">{payErr}</div>}

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
