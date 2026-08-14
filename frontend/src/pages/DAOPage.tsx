import { useCallback, useEffect, useState } from "react";
import { formatEther } from "ethers";
import {
  getDeployment,
  getGovernor,
  getSnd,
  isDeployed,
} from "../web3/contracts";
import { useWallet } from "../web3/useWallet";

const STATE_NAMES = [
  "Pending",
  "Active",
  "Canceled",
  "Defeated",
  "Succeeded",
  "Queued",
  "Expired",
  "Executed",
];

interface Proposal {
  id: bigint;
  state: number;
  voted: boolean;
}

export default function DAOPage() {
  const wallet = useWallet();
  const [deployed, setDeployed] = useState(false);
  const [sndBalance, setSndBalance] = useState<string | null>(null);
  const [votes, setVotes] = useState<string | null>(null);
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    const dep = await getDeployment();
    setDeployed(isDeployed(dep));
    if (!isDeployed(dep) || !wallet.provider || !wallet.address) return;
    try {
      const signer = await wallet.provider.getSigner();
      const snd = await getSnd(signer, dep.snd);
      setSndBalance(formatEther(await snd.balanceOf(wallet.address)));
      setVotes(formatEther(await snd.getVotes(wallet.address)));

      const gov = await getGovernor(signer, dep.governor);
      const events = await gov.queryFilter(gov.filters.ProposalCreated(), -100_000);
      const list: Proposal[] = [];
      for (const ev of events) {
        const args = (ev as unknown as { args: unknown[] }).args;
        const id = args[0] as bigint;
        const [state, voted] = await Promise.all([
          gov.state(id),
          gov.hasVoted(id, wallet.address).catch(() => false),
        ]);
        list.push({ id, state: Number(state), voted: Boolean(voted) });
      }
      list.sort((a, b) => (a.id > b.id ? -1 : 1));
      setProposals(list);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed to read DAO state");
    }
  }, [wallet.provider, wallet.address]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const vote = async (id: bigint, support: number) => {
    setBusy(true);
    setErr(null);
    try {
      const dep = await getDeployment();
      const signer = await wallet.provider!.getSigner();
      const gov = await getGovernor(signer, dep.governor);
      await (await gov.castVote(id, support)).wait();
      await refresh();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Vote failed");
    } finally {
      setBusy(false);
    }
  };

  if (!deployed) {
    return (
      <div>
        <h1>DAO</h1>
        <p className="muted">
          The SoundHub Governor is not deployed yet. Deploy the contracts
          (contracts/ → <code>npm run deploy:base</code>) to enable SND voting.
        </p>
      </div>
    );
  }

  return (
    <div>
      <h1>🗳 SoundHub DAO</h1>
      <p className="muted" style={{ marginTop: 0 }}>
        SND holders govern the platform. Delegate your tokens, then vote on
        proposals.
      </p>

      <div className="card" style={{ marginBottom: 20 }}>
        <div className="row">
          <div>
            <div className="muted" style={{ fontSize: 11, textTransform: "uppercase" }}>
              SND balance
            </div>
            <div style={{ fontSize: 20, fontWeight: 700 }}>
              {wallet.address ? sndBalance ?? "—" : "connect wallet"}
            </div>
          </div>
          <div style={{ minWidth: 20 }} />
          <div>
            <div className="muted" style={{ fontSize: 11, textTransform: "uppercase" }}>
              Voting power
            </div>
            <div style={{ fontSize: 20, fontWeight: 700 }}>{votes ?? "0"}</div>
          </div>
          <span className="spacer" />
          {!wallet.connected && (
            <button className="btn" onClick={() => wallet.connect()}>
              Connect wallet
            </button>
          )}
          {wallet.connected && (
            <span className="muted" style={{ fontSize: 12 }}>
              {wallet.address?.slice(0, 6)}…{wallet.address?.slice(-4)}
            </span>
          )}
        </div>
        <p className="muted" style={{ fontSize: 12, marginBottom: 0 }}>
          To get voting power, hold SND and call{" "}
          <code>snd.delegate(yourAddress)</code> from your wallet.
        </p>
      </div>

      <div className="card">
        <h2>Proposals</h2>
        {proposals.length === 0 && (
          <p className="muted">No proposals found (or none in the last 100k blocks).</p>
        )}
        {proposals.map((p) => (
          <div key={p.id.toString()} className="file-row">
            <span className="commit-marker">#{p.id.toString().slice(0, 10)}…</span>
            <span className="chip">{STATE_NAMES[p.state] ?? p.state}</span>
            {p.voted && <span className="chip added">voted</span>}
            <span className="spacer" />
            {p.state === 1 && (
              <>
                <button
                  className="btn"
                  style={{ padding: "4px 10px", fontSize: 12 }}
                  disabled={busy || p.voted}
                  onClick={() => vote(p.id, 1)}
                >
                  For
                </button>
                <button
                  className="btn ghost"
                  style={{ padding: "4px 10px", fontSize: 12 }}
                  disabled={busy || p.voted}
                  onClick={() => vote(p.id, 0)}
                >
                  Against
                </button>
              </>
            )}
          </div>
        ))}
        {err && <div className="error" style={{ marginTop: 8 }}>{err}</div>}
      </div>
    </div>
  );
}
