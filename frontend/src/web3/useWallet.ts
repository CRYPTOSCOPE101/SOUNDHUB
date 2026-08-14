import { useCallback, useEffect, useState } from "react";
import { BrowserProvider, type Eip1193Provider } from "ethers";

declare global {
  interface Window {
    ethereum?: Eip1193Provider & {
      request: (args: { method: string; params?: unknown[] }) => Promise<unknown>;
      on: (event: string, handler: (...args: unknown[]) => void) => void;
      removeListener: (event: string, handler: (...args: unknown[]) => void) => void;
    };
  }
}

export interface WalletState {
  address: string | null;
  chainId: number | null;
  provider: BrowserProvider | null;
  connected: boolean;
  available: boolean;
  connect: () => Promise<void>;
  disconnect: () => void;
  switchToBase: () => Promise<void>;
}

let BASE_CHAIN_ID = 8453;

export function setTargetChainId(chainId: number) {
  BASE_CHAIN_ID = chainId;
}

export function useWallet(): WalletState {
  const [address, setAddress] = useState<string | null>(null);
  const [chainId, setChainId] = useState<number | null>(null);
  const [provider, setProvider] = useState<BrowserProvider | null>(null);

  const available = typeof window !== "undefined" && Boolean(window.ethereum);

  const refresh = useCallback(async () => {
    if (!window.ethereum) return;
    const p = new BrowserProvider(window.ethereum);
    setProvider(p);
    try {
      const accounts = (await window.ethereum.request({ method: "eth_accounts" })) as string[];
      setAddress(accounts[0] ?? null);
      const net = await p.getNetwork();
      setChainId(Number(net.chainId));
    } catch {
      /* wallet not unlocked */
    }
  }, []);

  useEffect(() => {
    refresh();
    const eth = window.ethereum;
    if (!eth) return;
    const onAccounts = () => refresh();
    const onChain = () => refresh();
    eth.on("accountsChanged", onAccounts);
    eth.on("chainChanged", onChain);
    return () => {
      eth.removeListener("accountsChanged", onAccounts);
      eth.removeListener("chainChanged", onChain);
    };
  }, [refresh]);

  const connect = useCallback(async () => {
    if (!window.ethereum) throw new Error("MetaMask not installed");
    const accounts = (await window.ethereum.request({
      method: "eth_requestAccounts",
    })) as string[];
    setAddress(accounts[0] ?? null);
    await refresh();
  }, [refresh]);

  const disconnect = useCallback(() => {
    setAddress(null);
  }, []);

  const switchToBase = useCallback(async () => {
    if (!window.ethereum) return;
    try {
      await window.ethereum.request({
        method: "wallet_switchEthereumChain",
        params: [{ chainId: `0x${BASE_CHAIN_ID.toString(16)}` }],
      });
    } catch {
      // chain not added yet
      await window.ethereum.request({
        method: "wallet_addEthereumChain",
        params: [
          {
            chainId: `0x${BASE_CHAIN_ID.toString(16)}`,
            chainName: "Base",
            nativeCurrency: { name: "Ether", symbol: "ETH", decimals: 18 },
            rpcUrls: ["https://mainnet.base.org"],
            blockExplorerUrls: ["https://basescan.org"],
          },
        ],
      });
    }
    await refresh();
  }, [refresh]);

  return {
    address,
    chainId,
    provider,
    connected: Boolean(address),
    available,
    connect,
    disconnect,
    switchToBase,
  };
}
