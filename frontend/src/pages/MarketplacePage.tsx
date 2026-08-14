import { useCallback, useEffect, useState, type FormEvent } from "react";
import { formatEther, parseEther } from "ethers";
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

export default function MarketplacePage() {
  const wallet = useWallet();
  const [deployment, setDeployment] = useState<Deployment | null>(null);
  const [listings, setListings] = useState<Listing[]>([]);
  const [sndBalance, setSndBalance] = useState<string | null>(null);
  const [canClaim, setCanClaim] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

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

  return (
    <div>
      <h1>🛒 Marketplace</h1>
      <p className="muted" style={{ marginTop: 0 }}>
        Don't generate. Buy. — finished sounds, verified, paid for with SND.
      </p>

      {!deployed ? (
        <p className="muted">Contracts not deployed yet.</p>
      ) : (
        <>
          <div className="split">
            <div>
              {/* Listings */}
              <div className="card" style={{ marginBottom: 20 }}>
                <div className="row" style={{ marginBottom: 10 }}>
                  <h2 style={{ margin: 0 }}>Listings</h2>
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
