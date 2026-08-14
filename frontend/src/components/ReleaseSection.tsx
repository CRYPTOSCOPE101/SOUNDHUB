import { useEffect, useState, type FormEvent } from "react";
import { parseEther } from "ethers";
import { api } from "../api";
import {
  explorerTokenUrl,
  getDeployment,
  getRelease,
  getSnd,
  isDeployed,
  type Deployment,
} from "../web3/contracts";
import { setTargetChainId, useWallet } from "../web3/useWallet";

interface Props {
  projectId: number;
  projectName: string;
  releaseTokenId: number | null;
  releaseContract: string | null;
  releaseName: string | null;
  onBound: () => void;
}

export default function ReleaseSection({
  projectId,
  projectName,
  releaseTokenId,
  releaseContract,
  releaseName,
  onBound,
}: Props) {
  const wallet = useWallet();
  const [deployment, setDeployment] = useState<Deployment | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // mint form
  const [name, setName] = useState(projectName);
  const [collabs, setCollabs] = useState("");
  const [royalty, setRoyalty] = useState("500");

  // tip form
  const [tipSnd, setTipSnd] = useState("");
  const [tipEth, setTipEth] = useState("");

  useEffect(() => {
    getDeployment().then(setDeployment);
  }, []);

  const deployed = deployment && isDeployed(deployment);

  const ensureWallet = async (): Promise<boolean> => {
    if (!deployment) return false;
    setTargetChainId(deployment.chainId);
    if (!wallet.connected) await wallet.connect();
    if (wallet.chainId !== deployment.chainId) await wallet.switchToBase();
    return Boolean(wallet.provider);
  };

  const mint = async (e: FormEvent) => {
    e.preventDefault();
    setErr(null);
    setMsg(null);
    if (!deployment) return;
    try {
      const collabPairs = collabs
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean)
        .map((pair) => {
          const [addr, share] = pair.split(":").map((x) => x.trim());
          if (!addr?.startsWith("0x") || !share) throw new Error(`Bad entry: ${pair} (use address:share, shares must sum to 10000)`);
          return { addr, share: Number(share) };
        });
      if (collabPairs.length === 0) throw new Error("Add at least one collaborator (e.g. 0xABC...:5000)");
      const total = collabPairs.reduce((s, c) => s + c.share, 0);
      if (total !== 10000) throw new Error(`Shares sum to ${total}, must be exactly 10000`);

      if (!(await ensureWallet())) return;
      const signer = await wallet.provider!.getSigner();
      const release = await getRelease(signer, deployment.release);
      setBusy(true);
      const metadata = JSON.stringify({ name, platform: "soundhub", project: projectName });
      const tx = await release.mintRelease(
        name,
        metadata,
        collabPairs.map((c) => c.addr),
        collabPairs.map((c) => c.share),
        Number(royalty) || 500
      );
      const receipt = await tx.wait();
      const iface = release.interface;
      const ev = receipt!.logs
        .map((l: unknown) => {
          try {
            return iface.parseLog(l as never);
          } catch {
            return null;
          }
        })
        .find((x: { name?: string } | null) => x && x.name === "ReleaseMinted");
      const tokenId = Number(ev ? ev.args[0] : 1);

      await api.bindRelease(projectId, tokenId, deployment.release, name);
      setMsg(`Release minted! Token #${tokenId}`);
      onBound();
    } catch (e2) {
      setErr(e2 instanceof Error ? e2.message : "Mint failed");
    } finally {
      setBusy(false);
    }
  };

  const tip = async (kind: "eth" | "snd") => {
    setErr(null);
    setMsg(null);
    if (!deployment || !releaseTokenId) return;
    try {
      if (!(await ensureWallet())) return;
      const signer = await wallet.provider!.getSigner();
      const release = await getRelease(signer, deployment.release);
      setBusy(true);
      if (kind === "eth") {
        const amount = tipEth || "0.01";
        await (await release.fund(releaseTokenId, { value: parseEther(amount) })).wait();
        setMsg(`Funded release with ${amount} ETH`);
      } else {
        const amount = tipSnd || "10";
        const snd = await getSnd(signer, deployment.snd);
        const amt = parseEther(amount);
        await (await snd.approve(deployment.release, amt)).wait();
        await (await release.fundWithSND(releaseTokenId, amt)).wait();
        setMsg(`Funded release with ${amount} SND`);
      }
    } catch (e2) {
      setErr(e2 instanceof Error ? e2.message : "Tip failed");
    } finally {
      setBusy(false);
    }
  };

  const claim = async () => {
    setErr(null);
    setMsg(null);
    if (!deployment || !releaseTokenId) return;
    try {
      if (!(await ensureWallet())) return;
      const signer = await wallet.provider!.getSigner();
      const release = await getRelease(signer, deployment.release);
      setBusy(true);
      await (await release.claim(releaseTokenId)).wait();
      setMsg("Claimed your share ✓");
    } catch (e2) {
      setErr(e2 instanceof Error ? e2.message : "Claim failed");
    } finally {
      setBusy(false);
    }
  };

  if (!deployment) return null;

  return (
    <div className="card" style={{ marginBottom: 20 }}>
      <h2>🎵 On-chain release</h2>
      {!deployed ? (
        <p className="muted" style={{ fontSize: 13 }}>
          Contracts not deployed yet. Run <code>npm run deploy:base</code> in{" "}
          <code>contracts/</code> to enable NFT minting, tips and claiming.
        </p>
      ) : (
        <>
          {releaseTokenId && releaseContract ? (
            <div className="daw-box" style={{ borderStyle: "solid" }}>
              <div className="row">
                <strong>🎛 {releaseName || "Release"}</strong>
                <span className="badge badge-daw" style={{ background: "#22d3ee" }}>
                  NFT #{releaseTokenId}
                </span>
                <a
                  className="muted"
                  style={{ fontSize: 12 }}
                  href={explorerTokenUrl(deployment, releaseTokenId)}
                  target="_blank"
                  rel="noreferrer"
                >
                  basescan ↗
                </a>
              </div>
              <div className="row" style={{ marginTop: 12, gap: 8 }}>
                <input
                  type="text"
                  placeholder="Tip SND, e.g. 10"
                  value={tipSnd}
                  onChange={(e) => setTipSnd(e.target.value)}
                  style={{ width: 140 }}
                />
                <button className="btn" disabled={busy} onClick={() => tip("snd")}>
                  Tip SND
                </button>
                <input
                  type="text"
                  placeholder="Tip ETH, e.g. 0.01"
                  value={tipEth}
                  onChange={(e) => setTipEth(e.target.value)}
                  style={{ width: 140 }}
                />
                <button className="btn" disabled={busy} onClick={() => tip("eth")}>
                  Tip ETH
                </button>
                <button className="btn ghost" disabled={busy} onClick={claim}>
                  Claim my share
                </button>
              </div>
            </div>
          ) : (
            <form onSubmit={mint} className="daw-box">
              <p className="muted" style={{ marginTop: 0, fontSize: 13 }}>
                Turn this project into an on-chain release NFT with royalties and
                a collaborator revenue split.
              </p>
              <div className="row" style={{ gap: 8 }}>
                <input
                  type="text"
                  placeholder="Release name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  style={{ flex: 2 }}
                />
                <input
                  type="text"
                  placeholder="Royalty bps (500 = 5%)"
                  value={royalty}
                  onChange={(e) => setRoyalty(e.target.value)}
                  style={{ width: 160 }}
                />
              </div>
              <textarea
                rows={2}
                placeholder="Collaborators — address:share, comma-separated, must sum to 10000. e.g. 0xABC...:6000, 0xDEF...:4000"
                value={collabs}
                onChange={(e) => setCollabs(e.target.value)}
                style={{ marginTop: 8 }}
              />
              <div className="row" style={{ marginTop: 10 }}>
                <span className="muted" style={{ fontSize: 12 }}>
                  Wallet: {wallet.address ? `${wallet.address.slice(0, 6)}…${wallet.address.slice(-4)}` : "not connected"}
                </span>
                <span className="spacer" />
                <button className="btn" disabled={busy}>
                  {busy ? "Minting…" : "Mint release NFT"}
                </button>
              </div>
            </form>
          )}
          {msg && <div className="success" style={{ marginTop: 8 }}>{msg}</div>}
          {err && <div className="error" style={{ marginTop: 8 }}>{err}</div>}
          <div className="muted" style={{ fontSize: 11, marginTop: 8 }}>
            SND contract: <code>{deployment.snd.slice(0, 10)}…</code> · Release:{" "}
            <code>{deployment.release.slice(0, 10)}…</code> · Governor:{" "}
            <code>{deployment.governor.slice(0, 10)}…</code>
          </div>
        </>
      )}
    </div>
  );
}
