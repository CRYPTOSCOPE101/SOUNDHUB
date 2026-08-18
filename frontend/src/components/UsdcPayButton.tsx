import { useState } from "react";
import { Contract } from "ethers";
import { api } from "../api";
import type { UsdcCheckoutOut } from "../types";
import { useWallet } from "../web3/useWallet";
import { errorMessage } from "../errors";

// USDC ERC-20 interface — only the methods we need
const USDC_ABI = [
  "function transfer(address to, uint256 amount) returns (bool)",
  "function decimals() view returns (uint8)",
  "function balanceOf(address owner) view returns (uint256)",
];

export type UsdcPayTarget = {
  /** Public delivery page: pay by delivery token. Owner view: pass packageId instead. */
  deliveryToken?: string;
  packageId?: number;
  kind: "package" | "deposit";
  /** Shown to the user, e.g. "release package invoice" or "booking deposit" */
  purposeLabel: string;
};

export default function UsdcPayButton({ target }: { target: UsdcPayTarget }) {
  const wallet = useWallet();
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [txHash, setTxHash] = useState<string | null>(null);
  const [confirmed, setConfirmed] = useState(false);

  const pay = async () => {
    setBusy(true);
    setErr(null);
    setTxHash(null);
    try {
      // 1. payment terms — payee address, exact amount in USDC units
      let terms: UsdcCheckoutOut;
      try {
        terms = target.deliveryToken
          ? await api.publicUsdcCheckout(target.deliveryToken, target.kind)
          : await api.usdcCheckout(target.packageId!, target.kind);
      } catch (e) {
        throw new Error(errorMessage(e, "USDC checkout unavailable for this delivery"));
      }

      // 2. connect wallet + switch to Base
      if (!wallet.available) {
        throw new Error("No wallet found — install MetaMask (or another injected wallet) to pay with USDC");
      }
      await wallet.connect();
      if (wallet.chainId !== terms.chain_id) {
        await wallet.switchToBase();
      }
      if (!wallet.provider || !wallet.address) {
        throw new Error("Wallet not connected");
      }

      // 3. send USDC to the payee
      const signer = await wallet.provider.getSigner();
      const token = new Contract(terms.token_address, USDC_ABI, signer);
      const tx = await token.transfer(terms.payee_address, terms.amount_usdc_units);
      setTxHash(tx.hash);
      await tx.wait();

      // 4. server-side verification (reads the tx receipt on-chain)
      const result = await api.usdcVerify({
        txHash: tx.hash,
        packageId: target.deliveryToken ? null : target.packageId ?? null,
        deliveryToken: target.deliveryToken ?? null,
        sessionId: null,
        kind: target.kind,
      });
      if (!result.ok || !result.handled) {
        throw new Error("Payment sent, but we couldn't confirm it yet — the transfer will be verified shortly.");
      }
      setConfirmed(true);
      window.setTimeout(() => window.location.reload(), 1200);
    } catch (e) {
      setErr(errorMessage(e, "USDC payment failed"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="usdc-pay">
      <button
        type="button"
        className="rs-btn"
        onClick={() => void pay()}
        disabled={busy}
        title="Pay with USDC on Base (no card needed)"
      >
        {busy ? (txHash ? "Confirming transfer…" : "Connecting wallet…") : "💠 Pay with USDC"}
      </button>
      {txHash && !confirmed && (
        <div className="usdc-pay-status">
          Transfer sent: <code>{txHash.slice(0, 12)}…{txHash.slice(-8)}</code> — waiting for on-chain confirmation…
        </div>
      )}
      {confirmed && <div className="usdc-pay-ok">✓ USDC payment confirmed — unlocking files…</div>}
      {err && <div className="error">{err}</div>}
    </div>
  );
}
