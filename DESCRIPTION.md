# SoundHub — Don't Generate. Buy.

**SoundHub is a token-powered marketplace for finished sounds: presets, sample packs, kits, patches, stems and templates.**

A producer needs a bass patch, a drum kit, a cinematic impact — and instead of
spending hours generating and tweaking, they **pay with SND and get a ready,
verified sound instantly.** Sellers publish finished, human-made assets with a
verifiable history; buyers purchase them with tokens and clear licenses; and
the DAO governs the platform.

```
Instead of:  generate → tweak for hours → still not right
SoundHub:    buy the finished preset for 50 SND → done
```

The point is **not** to generate sound (AI or otherwise). The point is to make
*finished sound a commodity you buy* — fast, trusted, and on-chain.

---

## The problem

Two forces are colliding in music production:

- **Generation is cheap but time is expensive.** AI and endless preset-tweaking
  produce *a* sound — but rarely *the* sound. Producers burn hours; the result
  is inconsistent, unverifiable, and hard to license.
- **Buying finished sound is untrusted.** Marketplaces are fragmented,
  licenses are unclear, quality is unverifiable, provenance is missing, and
  paying creators is manual and late.

The infrastructure treats sounds as loose files — while code got repositories,
attribution and licensing decades ago.

## The core loop

**Create → List → Verify → Buy → Get paid.**

1. **A sound designer creates** a finished preset, kit, or pack (in a DAW: Ableton, FL Studio, Cubase, REAPER).
2. **SoundHub parses and verifies it** — the DAW engine reads what's inside: BPM, tracks, plugins, samples. *"What am I actually buying?"* is answered before the purchase.
3. **The asset is listed for SND** with a license tier and version history.
4. **A producer buys it** — SND goes into **escrow**, the buyer gets the asset + license.
5. **Payment settles** — buyer confirms, or the dispute window passes, and the creator is paid automatically. No spreadsheets, no late manual payouts.

## Why tokens

SND is the **payment rail** — the thing you buy finished sounds with. Utility
before speculation:

- **Buy assets** — every purchase is denominated in SND (escrow contract)
- **License** — personal / commercial / sync / exclusive tiers on-chain
- **Govern** — SND holders control fees, curation, grants (1-day timelock)
- **Tip & fund releases** — fans fund release treasuries with SND or ETH

## Live today (honest)

- ✅ **DAW engine** — parsers for `.als`, `.cpr`, `.rpp`, `.flp`: BPM, tracks, devices, plugins, samples
- ✅ **Smart diffs** — what changed between versions (tempo, tracks, plugins), not "binary file changed"
- ✅ **Repos & versioning** — snapshot commits, SHA-256 content-addressed storage
- ✅ **Token layer on Base Sepolia** — SND (ERC-20, 1,000,000 fixed), Release NFTs with royalties & splits, DAO governor
- ✅ **Escrow marketplace contract** — list, buy with SND, escrow, dispute window, refunds (tested, not yet deployed)
- ✅ **Wallet identity** — sign in with any EVM wallet

## Roadmap (marketplace first)

| Phase | Scope |
|---|---|
| **1 · Buy flow** ⏳ | Deploy `SoundHubMarket` on Base Sepolia → list/buy in the UI → SND faucet for testers |
| **2 · Trust layer** | Asset verification badge from the DAW engine, seller reputation, license enforcement |
| **3 · Collaboration** | Branches & merges, remix forks, audio preview, comments on tracks |
| **4 · Mainnet** | Base mainnet deployment, SND distribution vote, DAO treasury |

## SoundHub vs. alternatives

| | Generate it yourself (AI/tweaking) | Splice | GitHub LFS | SoundHub |
|---|---|---|---|---|
| Time to a usable sound | hours | browsing | n/a | **seconds (buy)** |
| Verified contents | no | tags only | no | ✅ DAW-parsed |
| Token payment | — | fiat sub | — | ✅ SND + escrow |
| License clarity | — | partial | — | ✅ on-chain tiers |
| Creator payout | — | royalty model | — | ✅ automatic escrow |

## Vision

**Every sound you need is one token away. Every sound you make can be sold.**

SoundHub turns the global, fragmented sound economy into a marketplace:
presets, kits, patches, stems and templates that are verified before you buy,
licensed after you buy, and paid for the moment you do — no generation
rabbit-holes, no trust-me collaboration.

**SoundHub — don't generate. Buy.**

---

## Contracts

| Contract | Role | Address (Base Sepolia) |
|---|---|---|
| `SND` | platform token (payment rail) | `0x37a6B3aD766ffb98673290A634490C8bF952DB2F` |
| `SoundHubRelease` | release NFTs: royalties & splits | `0xb3716751572db83d22aeED95Be7da125A4d22446` |
| `SoundHubMarket` | escrow marketplace (tested, to deploy) | — |
| `SoundHubGovernor` | DAO + timelock | `0x2db3F8BA478C445399bB8fbA921fC5e11Af202da` |

*Contracts pass an extensive test suite but are not professionally audited. This document is not financial advice.*
