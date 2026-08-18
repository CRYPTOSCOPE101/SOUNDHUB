import { useState, type FormEvent } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import { getDeployment } from "../web3/contracts";
import { setTargetChainId, useWallet } from "../web3/useWallet";
import { errorMessage } from "../errors";

export default function LoginPage() {
  const { login, register } = useAuth();
  const wallet = useWallet();
  const nav = useNavigate();
  const [params] = useSearchParams();
  const [mode, setMode] = useState<"login" | "register">(
    params.get("mode") === "register" ? "register" : "login"
  );
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [walletBusy, setWalletBusy] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      if (mode === "login") await login(username, password);
      else await register(username, password);
      nav("/projects");
    } catch (err) {
      setError(errorMessage(err, "Something went wrong"));
    } finally {
      setBusy(false);
    }
  };

  const signInWithWallet = async () => {
    setError(null);
    setWalletBusy(true);
    try {
      if (!wallet.available) throw new Error("MetaMask not installed");
      const deployment = await getDeployment();
      setTargetChainId(deployment.chainId);
      if (!wallet.connected) await wallet.connect();
      const address = wallet.address;
      if (!address) throw new Error("No wallet address");
      if (wallet.chainId !== deployment.chainId) await wallet.switchToBase();

      const { message } = await api.walletNonce(address);
      const provider = wallet.provider;
      if (!provider) throw new Error("No provider");
      const signer = await provider.getSigner();
      const signature = await signer.signMessage(message);
      await api.walletLogin(address, message, signature);
      nav("/projects");
    } catch (err) {
      setError(errorMessage(err, "Wallet sign-in failed"));
    } finally {
      setWalletBusy(false);
    }
  };

  return (
    <div className="login-wrap">
      <h1>{mode === "login" ? "Sign in" : "Create account"}</h1>
      <p className="muted" style={{ marginTop: 0 }}>
        Demo account: <code>demo / demo123</code>
      </p>
      <button className="btn" onClick={signInWithWallet} disabled={walletBusy} style={{ width: "100%" }}>
        {walletBusy ? "Signing…" : "⛓ Sign in with wallet"}
      </button>
      <div className="row" style={{ gap: 8 }}>
        <span style={{ flex: 1, borderTop: "1px solid var(--border)" }} />
        <span className="muted" style={{ fontSize: 12 }}>or</span>
        <span style={{ flex: 1, borderTop: "1px solid var(--border)" }} />
      </div>
      <form onSubmit={submit} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        <input
          type="text"
          placeholder="username"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          autoFocus
        />
        <input
          type="password"
          placeholder="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        {error && <div className="error">{error}</div>}
        <button className="btn" disabled={busy}>
          {busy ? "…" : mode === "login" ? "Sign in" : "Register"}
        </button>
        <button
          type="button"
          className="btn ghost"
          onClick={() => setMode(mode === "login" ? "register" : "login")}
        >
          {mode === "login" ? "Need an account? Register" : "Have an account? Sign in"}
        </button>
      </form>
    </div>
  );
}
