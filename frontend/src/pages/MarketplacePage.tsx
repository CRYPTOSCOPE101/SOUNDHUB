import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { formatEther, parseEther } from "ethers";
import { api } from "../api";
import type { CatalogAsset, LicenseReceipt } from "../types";
import {
  getDeployment,
  getFaucet,
  getMarket,
  getSnd,
  isDeployed,
  LICENSE_NAMES,
  type Deployment,
} from "../web3/contracts";
import { setTargetChainId, useWallet } from "../web3/useWallet";

interface Listing {
  id: bigint;
  seller: string;
  name: string;
  assetUri: string;
  price: bigint;
  license: number;
  active: boolean;
  buyer: string;
  escrowed: bigint;
  released: boolean;
}

interface Filters {
  q: string;
  genre: string;
  key: string;
  license: string;
  format: string;
  plugin: string;
  bpmMin: string;
  bpmMax: string;
}

const EMPTY_FILTERS: Filters = {
  q: "",
  genre: "",
  key: "",
  license: "",
  format: "",
  plugin: "",
  bpmMin: "",
  bpmMax: "",
};

function LicenseReceiptCard({ receipt }: { receipt: LicenseReceipt }) {
  const download = () => {
    const blob = new Blob([JSON.stringify(receipt, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `soundhub-license-${receipt.receipt_id}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };
  const date = new Date(receipt.issued_at * 1000).toLocaleString();
  return (
    <div className="receipt">
      <div className="row" style={{ marginBottom: 6 }}>
        <h2 style={{ margin: 0 }}>📄 License receipt</h2>
        <span className="spacer" />
        <button className="btn ghost sm" onClick={download}>
          ⤓ .json
        </button>
      </div>
      <div className="receipt-title">
        {receipt.asset_name} · {receipt.license}
      </div>
      <div className="receipt-scope">
        <div>
          <strong>You can:</strong> {receipt.buyer_can}
        </div>
        <div>
          <strong>Seller keeps:</strong> {receipt.seller_keeps}
        </div>
      </div>
      <dl className="receipt-facts">
        <div><dt>receipt</dt><dd>#{receipt.receipt_id} · v{receipt.version}</dd></div>
        <div><dt>date</dt><dd>{date}</dd></div>
        <div><dt>price</dt><dd>{receipt.price_snd} SND</dd></div>
        <div><dt>buyer</dt><dd className="mono">{receipt.buyer.slice(0, 8)}…{receipt.buyer.slice(-6)}</dd></div>
        <div><dt>seller</dt><dd className="mono">{receipt.seller.slice(0, 8)}…{receipt.seller.slice(-6)}</dd></div>
        <div><dt>asset sha256</dt><dd className="mono">{receipt.asset_sha256.slice(0, 16)}…</dd></div>
      </dl>
    </div>
  );
}

function Waveform({
  peaks,
  progress,
  playing,
}: {
  peaks: number[];
  progress: number;
  playing: boolean;
}) {
  const bars = peaks.length ? peaks : Array.from({ length: 120 }, () => 12);
  return (
    <div className="waveform" aria-hidden="true">
      {bars.map((p, i) => (
        <span
          key={i}
          className={`wf-bar${playing && i / bars.length <= progress ? " played" : ""}`}
          style={{ height: `${Math.max(6, Math.round((p / 255) * 100))}%` }}
        />
      ))}
    </div>
  );
}

export default function MarketplacePage() {
  const wallet = useWallet();
  const [deployment, setDeployment] = useState<Deployment | null>(null);
  const [listings, setListings] = useState<Listing[]>([]);
  const [sndBalance, setSndBalance] = useState<string | null>(null);
  const [canClaim, setCanClaim] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [receipt, setReceipt] = useState<LicenseReceipt | null>(null);
  const [receiptErr, setReceiptErr] = useState<string | null>(null);

  // catalog browsing (public API — no wallet needed)
  const [catalog, setCatalog] = useState<CatalogAsset[]>([]);
  const [allAssets, setAllAssets] = useState<CatalogAsset[]>([]);
  const [filters, setFilters] = useState<Filters>({ ...EMPTY_FILTERS });
  const [catalogErr, setCatalogErr] = useState<string | null>(null);
  const [playingId, setPlayingId] = useState<number | null>(null);
  const [progress, setProgress] = useState(0);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  // seller form
  const [lName, setLName] = useState("");
  const [lUri, setLUri] = useState("");
  const [lPrice, setLPrice] = useState("");
  const [lLicense, setLLicense] = useState("1");

  const ensureWallet = async (): Promise<boolean> => {
    if (!deployment) return false;
    setTargetChainId(deployment.chainId);
    if (!wallet.connected) await wallet.connect();
    if (wallet.chainId !== deployment.chainId) await wallet.switchToBase();
    return Boolean(wallet.provider);
  };

  const refresh = useCallback(async () => {
    const dep = await getDeployment();
    setDeployment(dep);
    if (!isDeployed(dep) || !dep.market || !dep.faucet || !wallet.provider || !wallet.address) return;
    try {
      const signer = await wallet.provider.getSigner();
      const snd = await getSnd(signer, dep.snd);
      setSndBalance(formatEther(await snd.balanceOf(wallet.address)));

      const market = await getMarket(signer, dep.market);
      const count = Number(await market.nextListingId());
      const rows: Listing[] = [];
      for (let i = 1; i < count; i++) {
        const l = await market.listings(i);
        rows.push({
          id: l.id,
          seller: l.seller,
          name: l.name,
          assetUri: l.assetUri,
          price: l.price,
          license: Number(l.license),
          active: l.active,
          buyer: l.buyer,
          escrowed: l.escrowed,
          released: l.released,
        });
      }
      setListings(rows.reverse());

      const faucet = await getFaucet(signer, dep.faucet);
      const [last, cooldown, latest] = await Promise.all([
        faucet.lastClaimAt(wallet.address),
        faucet.cooldown(),
        wallet.provider.getBlock("latest"),
      ]);
      setCanClaim(
        latest !== null && Number(last) + Number(cooldown) <= Number(latest.timestamp)
      );
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed to load marketplace");
    }
  }, [wallet.provider, wallet.address]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  // full catalog for filter options
  useEffect(() => {
    api.catalog({ limit: 200 }).then(setAllAssets).catch(() => {});
  }, []);

  // stop preview audio on unmount
  useEffect(() => {
    return () => audioRef.current?.pause();
  }, []);

  // filtered catalog (debounced)
  useEffect(() => {
    const t = window.setTimeout(() => {
      api
        .catalog({
          q: filters.q || undefined,
          genre: filters.genre || undefined,
          key: filters.key || undefined,
          license: filters.license || undefined,
          format: filters.format || undefined,
          plugin: filters.plugin || undefined,
          bpm_min: filters.bpmMin || undefined,
          bpm_max: filters.bpmMax || undefined,
        })
        .then(setCatalog)
        .catch((e) =>
          setCatalogErr(e instanceof Error ? e.message : "Failed to load catalog")
        );
    }, 200);
    return () => window.clearTimeout(t);
  }, [filters]);

  const genreOptions = useMemo(
    () => [...new Set(allAssets.flatMap((a) => a.genres))].sort(),
    [allAssets]
  );
  const keyOptions = useMemo(
    () => [...new Set(allAssets.map((a) => a.key).filter(Boolean) as string[])].sort(),
    [allAssets]
  );
  const licenseOptions = useMemo(
    () => [...new Set(allAssets.map((a) => a.license))].sort(),
    [allAssets]
  );
  const formatOptions = useMemo(
    () => [...new Set(allAssets.map((a) => a.format).filter(Boolean) as string[])].sort(),
    [allAssets]
  );
  const pluginOptions = useMemo(
    () => [...new Set(allAssets.flatMap((a) => a.plugins))].sort(),
    [allAssets]
  );

  const onchainFor = (id: number) => listings.find((l) => Number(l.id) === id);

  const setFilter = (k: keyof Filters, v: string) =>
    setFilters((f) => ({ ...f, [k]: v }));

  const resetFilters = () => setFilters({ ...EMPTY_FILTERS });

  const togglePlay = (a: CatalogAsset) => {
    if (playingId === a.listing_id) {
      audioRef.current?.pause();
      setPlayingId(null);
      setProgress(0);
      return;
    }
    audioRef.current?.pause();
    const audio = new Audio(api.previewUrl(a.listing_id));
    audioRef.current = audio;
    setPlayingId(a.listing_id);
    setProgress(0);
    audio.ontimeupdate = () =>
      setProgress(audio.duration ? audio.currentTime / audio.duration : 0);
    audio.onended = () => {
      setPlayingId(null);
      setProgress(0);
    };
    audio.play().catch(() => setPlayingId(null));
  };

  const claimFaucet = async () => {
    setErr(null);
    setMsg(null);
    if (!deployment?.faucet) return;
    try {
      if (!(await ensureWallet())) return;
      const signer = await wallet.provider!.getSigner();
      const faucet = await getFaucet(signer, deployment.faucet);
      setBusy(true);
      await (await faucet.claim()).wait();
      setMsg("100 SND claimed! Buy something. 🎧");
      await refresh();
    } catch (e2) {
      setErr(e2 instanceof Error ? e2.message : "Claim failed");
    } finally {
      setBusy(false);
    }
  };

  const buy = async (l: Listing) => {
    setErr(null);
    setMsg(null);
    if (!deployment?.market) return;
    try {
      if (!(await ensureWallet())) return;
      const signer = await wallet.provider!.getSigner();
      const snd = await getSnd(signer, deployment.snd);
      const market = await getMarket(signer, deployment.market);
      setBusy(true);
      await (await snd.approve(deployment.market, l.price)).wait();
      await (await market.buy(l.id)).wait();
      setMsg(`Bought "${l.name}" — SND is in escrow. Confirm receipt to pay the seller.`);
      await refresh();
      // ship the signed license receipt
      try {
        setReceiptErr(null);
        setReceipt(
          await api.issueReceipt(Number(l.id), wallet.address!, l.seller)
        );
      } catch (e3) {
        setReceipt(null);
        setReceiptErr(
          e3 instanceof Error ? e3.message : "License receipt unavailable"
        );
      }
    } catch (e2) {
      setErr(e2 instanceof Error ? e2.message : "Buy failed");
    } finally {
      setBusy(false);
    }
  };

  const confirm = async (l: Listing) => {
    setErr(null);
    setMsg(null);
    if (!deployment?.market) return;
    try {
      if (!(await ensureWallet())) return;
      const signer = await wallet.provider!.getSigner();
      const market = await getMarket(signer, deployment.market);
      setBusy(true);
      await (await market.confirmReceipt(l.id)).wait();
      setMsg(`Receipt confirmed — seller paid ✓`);
      await refresh();
    } catch (e2) {
      setErr(e2 instanceof Error ? e2.message : "Confirm failed");
    } finally {
      setBusy(false);
    }
  };

  const listAsset = async (e: FormEvent) => {
    e.preventDefault();
    setErr(null);
    setMsg(null);
    if (!deployment?.market) return;
    try {
      const price = parseEther(lPrice || "0");
      if (price <= 0n) throw new Error("Enter a price in SND");
      if (!(await ensureWallet())) return;
      const signer = await wallet.provider!.getSigner();
      const market = await getMarket(signer, deployment.market);
      setBusy(true);
      await (await market.list(lName.trim(), lUri.trim() || "soundhub://asset", price, Number(lLicense))).wait();
      setMsg("Listed! Buyers can now purchase it with SND.");
      setLName("");
      setLUri("");
      setLPrice("");
      await refresh();
    } catch (e2) {
      setErr(e2 instanceof Error ? e2.message : "Listing failed");
    } finally {
      setBusy(false);
    }
  };

  const deployed = deployment && isDeployed(deployment);
  const filteredCount = catalog.length;

  return (
    <div>
      <h1>🛒 Marketplace</h1>
      <p className="muted" style={{ marginTop: 0 }}>
        Find it. Preview it. Drop it into your track. — finished sounds with clear
        commercial rights, paid for with SND.
      </p>

      {/* ---------- Catalog with filters + previews (public) ---------- */}
      <div className="card filter-bar">
        <input
          type="text"
          placeholder="What are you making? Search presets, loops, packs…"
          value={filters.q}
          onChange={(e) => setFilter("q", e.target.value)}
        />
        <div className="row" style={{ marginTop: 10 }}>
          <select value={filters.genre} onChange={(e) => setFilter("genre", e.target.value)}>
            <option value="">genre</option>
            {genreOptions.map((g) => (
              <option key={g} value={g}>{g}</option>
            ))}
          </select>
          <select value={filters.key} onChange={(e) => setFilter("key", e.target.value)}>
            <option value="">key</option>
            {keyOptions.map((k) => (
              <option key={k} value={k}>{k}</option>
            ))}
          </select>
          <select value={filters.license} onChange={(e) => setFilter("license", e.target.value)}>
            <option value="">license</option>
            {licenseOptions.map((l) => (
              <option key={l} value={l}>{l}</option>
            ))}
          </select>
          <select value={filters.format} onChange={(e) => setFilter("format", e.target.value)}>
            <option value="">format</option>
            {formatOptions.map((f) => (
              <option key={f} value={f}>{f.toUpperCase()}</option>
            ))}
          </select>
          <select value={filters.plugin} onChange={(e) => setFilter("plugin", e.target.value)}>
            <option value="">plugin</option>
            {pluginOptions.map((p) => (
              <option key={p} value={p}>{p}</option>
            ))}
          </select>
          <input
            type="number"
            placeholder="BPM min"
            value={filters.bpmMin}
            onChange={(e) => setFilter("bpmMin", e.target.value)}
            style={{ width: 90 }}
          />
          <input
            type="number"
            placeholder="BPM max"
            value={filters.bpmMax}
            onChange={(e) => setFilter("bpmMax", e.target.value)}
            style={{ width: 90 }}
          />
          <button className="btn ghost sm" onClick={resetFilters}>
            reset
          </button>
        </div>
      </div>

      {catalogErr && <div className="error" style={{ margin: "12px 0" }}>{catalogErr}</div>}

      <p className="muted" style={{ margin: "14px 0 10px" }}>
        {filteredCount} {filteredCount === 1 ? "asset" : "assets"}
      </p>

      <div className="grid asset-grid">
        {catalog.map((a) => {
          const onchain = onchainFor(a.listing_id);
          const sold = onchain ? onchain.escrowed > 0n : false;
          const isMyListing =
            onchain && wallet.address?.toLowerCase() === onchain.seller.toLowerCase();
          const canBuy = Boolean(onchain && onchain.active && !sold && !isMyListing);
          return (
            <div className="card asset-card" key={a.uri || a.listing_id}>
              <div className="row" style={{ alignItems: "flex-start" }}>
                <strong className="asset-name">{a.name}</strong>
                <span className="spacer" />
                {a.verified && <span className="chip added">verified</span>}
              </div>
              <p className="muted asset-desc">{a.description}</p>
              <div className="row" style={{ gap: 6 }}>
                {a.format && <span className="chip">{a.format.toUpperCase()}</span>}
                <span className="chip">{a.license}</span>
                {a.bpm && (
                  <span className="chip">{a.bpm[0]}–{a.bpm[1]} BPM</span>
                )}
                {a.key && <span className="chip">{a.key}</span>}
              </div>
              <Waveform
                peaks={a.waveform}
                progress={playingId === a.listing_id ? progress : 0}
                playing={playingId === a.listing_id}
              />
              <div className="row asset-foot">
                <button
                  className="btn ghost sm"
                  onClick={() => togglePlay(a)}
                  disabled={!a.waveform.length}
                >
                  {playingId === a.listing_id ? "❚❚ pause" : "▶ preview"}
                </button>
                <span className="spacer" />
                {a.duration_seconds > 0 && (
                  <span className="muted" style={{ fontSize: 12 }}>
                    {a.duration_seconds}s
                  </span>
                )}
                <strong>{a.price_snd} SND</strong>
                {canBuy ? (
                  <button
                    className="btn sm"
                    disabled={busy || !wallet.address}
                    title={wallet.address ? "" : "connect wallet to buy"}
                    onClick={() => onchain && buy(onchain)}
                  >
                    Buy
                  </button>
                ) : onchain ? (
                  <span className="chip">{sold ? "sold" : isMyListing ? "yours" : "off market"}</span>
                ) : (
                  <span className="chip">demo</span>
                )}
              </div>
              <div className="muted" style={{ fontSize: 12, marginTop: 8 }}>
                {a.plugins.length > 0
                  ? `needs: ${a.plugins.join(", ")}`
                  : "works without third-party plugins"}
              </div>
            </div>
          );
        })}
      </div>

      {catalog.length === 0 && !catalogErr && (
        <p className="muted">No assets match — try wider filters.</p>
      )}

      {/* ---------- On-chain sections (wallet required) ---------- */}
      {!deployed ? (
        <p className="muted" style={{ marginTop: 24 }}>
          Contracts not deployed yet — catalog preview is still available above.
        </p>
      ) : (
        <>
          <div className="split" style={{ marginTop: 28 }}>
            <div>
              {/* Listings / escrow */}
              <div className="card" style={{ marginBottom: 20 }}>
                <div className="row" style={{ marginBottom: 10 }}>
                  <h2 style={{ margin: 0 }}>Listings &amp; escrow</h2>
                  <span className="spacer" />
                  <button className="btn ghost" onClick={refresh} disabled={busy}>
                    ↻ refresh
                  </button>
                </div>
                {listings.length === 0 && (
                  <p className="muted">No assets listed yet. Be the first seller!</p>
                )}
                {listings.map((l) => {
                  const isMyListing = wallet.address?.toLowerCase() === l.seller.toLowerCase();
                  const amBuyer = wallet.address?.toLowerCase() === l.buyer.toLowerCase();
                  const sold = l.escrowed > 0n;
                  return (
                    <div className="file-row" key={l.id.toString()}>
                      <span className="file-icon">🎛</span>
                      <div style={{ flex: 1 }}>
                        <div>
                          <strong>{l.name}</strong>{" "}
                          <span className="chip">{LICENSE_NAMES[l.license]}</span>
                          {isMyListing && <span className="chip">yours</span>}
                        </div>
                        <div className="muted" style={{ fontSize: 12, fontFamily: "monospace" }}>
                          #{l.id.toString()} · {l.assetUri} · seller{" "}
                          {l.seller.slice(0, 6)}…{l.seller.slice(-4)}
                        </div>
                      </div>
                      <strong>{formatEther(l.price)} SND</strong>
                      {!sold && l.active && !isMyListing && (
                        <button className="btn" disabled={busy} onClick={() => buy(l)}>
                          Buy
                        </button>
                      )}
                      {!sold && l.active && isMyListing && (
                        <span className="chip">listed</span>
                      )}
                      {sold && !l.released && amBuyer && (
                        <button className="btn" disabled={busy} onClick={() => confirm(l)}>
                          Confirm receipt
                        </button>
                      )}
                      {sold && !l.released && isMyListing && (
                        <span className="chip" style={{ color: "#f5c542", borderColor: "#f5c542" }}>
                          in escrow
                        </span>
                      )}
                      {l.released && <span className="chip added">settled</span>}
                    </div>
                  );
                })}
              </div>

              {/* Seller form */}
              <form className="card" onSubmit={listAsset}>
                <h2>Sell a finished sound</h2>
                <div className="row" style={{ gap: 8 }}>
                  <input
                    type="text"
                    placeholder="Name, e.g. 'Dark Bass Patch (Serum)'"
                    value={lName}
                    onChange={(e) => setLName(e.target.value)}
                    style={{ flex: 2 }}
                  />
                  <input
                    type="text"
                    placeholder="Price in SND"
                    value={lPrice}
                    onChange={(e) => setLPrice(e.target.value)}
                    style={{ width: 120 }}
                  />
                  <select
                    value={lLicense}
                    onChange={(e) => setLLicense(e.target.value)}
                    style={{ background: "var(--bg3)", color: "var(--text)", border: "1px solid var(--border)", borderRadius: 8, padding: "9px 12px" }}
                  >
                    {LICENSE_NAMES.map((n, i) => (
                      <option key={n} value={i}>{n}</option>
                    ))}
                  </select>
                </div>
                <input
                  type="text"
                  placeholder="Asset URI (repo path or IPFS), e.g. soundhub://presets/dark-bass"
                  value={lUri}
                  onChange={(e) => setLUri(e.target.value)}
                  style={{ marginTop: 8 }}
                />
                <div className="row" style={{ marginTop: 10 }}>
                  <span className="muted" style={{ fontSize: 12 }}>
                    Wallet:{" "}
                    {wallet.address ? `${wallet.address.slice(0, 6)}…${wallet.address.slice(-4)}` : "not connected"}
                  </span>
                  <span className="spacer" />
                  <button className="btn" disabled={busy}>
                    {busy ? "…" : "List for SND"}
                  </button>
                </div>
              </form>
            </div>

            {/* Faucet / wallet */}
            <div>
              <div className="card sidebar-card">
                <h2>Wallet</h2>
                <div style={{ fontSize: 24, fontWeight: 700 }}>
                  {wallet.address ? `${sndBalance ?? "…"} SND` : "connect wallet"}
                </div>
                <div className="row" style={{ marginTop: 12 }}>
                  {!wallet.connected && (
                    <button className="btn" onClick={() => wallet.connect()}>
                      Connect wallet
                    </button>
                  )}
                  {wallet.connected && !canClaim && (
                    <span className="chip">claimed recently</span>
                  )}
                  {wallet.connected && canClaim && (
                    <button className="btn" onClick={claimFaucet} disabled={busy}>
                      Claim 100 SND (testnet)
                    </button>
                  )}
                </div>
                {msg && <div className="success" style={{ marginTop: 10 }}>{msg}</div>}
                {err && <div className="error" style={{ marginTop: 10 }}>{err}</div>}
                {receiptErr && (
                  <div className="error" style={{ marginTop: 10 }}>
                    {receiptErr}
                  </div>
                )}
                {receipt && <LicenseReceiptCard receipt={receipt} />}
                <p className="muted" style={{ fontSize: 12, marginBottom: 0 }}>
                  Testnet faucet: 100 SND per wallet per day — enough to try
                  buying a preset.
                </p>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
