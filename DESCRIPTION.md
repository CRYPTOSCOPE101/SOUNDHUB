# SoundHub — Don't Generate. Buy.

> **SoundHub is a tokenized marketplace where music producers buy and sell
> finished, verified presets, loops, stems and sound packs — with on-chain
> ownership, clear licensing and automatic creator splits.**

**This is not an AI generator.** No prompting, no "make me a sound". SoundHub
sells **buy-ready, human-made, production-ready assets**: a producer needs a
bass patch, a drum kit, a cinematic impact — and instead of spending hours
generating and tweaking, they **pay with SND and get the finished, verified
sound instantly.**

```
Instead of:  generate → tweak for hours → still not right
SoundHub:    buy the finished preset for 50 SND → done
```

Under the hood it's a **GitHub-like workflow for audio**: every asset is
versioned, verified and licensed — the infrastructure that makes buying sound
trustworthy, not just a storefront.

---

## The problem

**Buying sound today is chaotic.** A producer picks up a loop in a DM, a pack
on Gumroad, a one-shot in a Telegram group — with no provenance, unclear
license, no version history, and no way to split revenue with the people who
actually made it. Two forces make it worse:

- **Generation is cheap but time is expensive.** AI and endless preset-tweaking
  produce *a* sound — but rarely *the* sound. Producers burn hours; the result
  is inconsistent, unverifiable, and hard to license.
- **Buying finished sound is untrusted.** Marketplaces are fragmented,
  licenses are unclear, quality is unverifiable, provenance is missing, and
  paying creators is manual and late.

Code got repositories, attribution and licensing decades ago. Sound is still
sold like loose files in random chats — and creators get paid late or never.

## The core loop

**Create → List → Verify → Buy → Get paid.**

1. **A sound designer creates** a finished preset, kit, or pack (in a DAW: Ableton, FL Studio, Cubase, REAPER).
2. **SoundHub parses and verifies it** — the DAW engine reads what's inside: BPM, tracks, plugins, samples. *"What am I actually buying?"* is answered before the purchase.
3. **The asset is listed for SND** with a license tier and version history.
4. **A producer buys it** — SND goes into **escrow**, the buyer gets the asset + license.
5. **Payment settles** — buyer confirms, or the dispute window passes, and the creator is paid automatically. No spreadsheets, no late manual payouts.

## Inside Ableton Live — the fastest way to buy

A marketplace is only as good as its placement. SoundHub ships a **native
panel for Ableton Live** (Max for Live device, prototype live in `m4l/`):

- Open Live → the SoundHub panel shows the catalog (read straight from the
  chain), your purchases, and new drops — no tab switch.
- It reads the **current project BPM** and suggests relevant assets
  (bass presets for 128 BPM techno, not a flat list). Next iteration adds
  key, tracks and devices via the DAW engine.
- **Buy & Load** — pay with SND (escrow), the asset lands in your project.
  Web3 stays invisible: no approve, no gas, no RPC — just *buy*.
- Same engine, three jobs: verify assets for sale, power in-DAW
  recommendations, and smart-diff project versions.

**SoundHub inside Ableton = buying finished sound at the moment of intent.**
Without it SoundHub is a good niche marketplace; with it, it's part of the
producer's workflow. FL Studio, Cubase and REAPER follow the same pattern.

## Why tokens

Not for hype — because the problems are **access, splits, licensing,
reputation, payouts and ownership**, and those are exactly what tokens solve:

- **Access control** — token-gated downloads, private packs, early releases
- **Creator splits** — on-chain percentages for every contributor, paid automatically
- **Licensing** — personal / commercial / sync / exclusive tiers bound to the purchase
- **Reputation** — verified creators, top sellers, ratings, on-chain history
- **Payouts** — escrow settles the moment the buyer confirms; no manual accounting
- **Community ownership** — the DAO (SND holders) controls fees, curation and grants

SND is the **payment rail** — every purchase is denominated in it. Utility before
speculation.

## Live today (honest)

- ✅ **DAW engine** — parsers for `.als`, `.cpr`, `.rpp`, `.flp`: BPM, tracks, devices, plugins, samples
- ✅ **Smart diffs** — what changed between versions (tempo, tracks, plugins), not "binary file changed"
- ✅ **Repos & versioning** — snapshot commits, SHA-256 content-addressed storage
- ✅ **Token layer on Base Sepolia** — SND (ERC-20, 1,000,000 fixed), Release NFTs with royalties & splits, DAO governor
- ✅ **Escrow marketplace live on Base Sepolia** — list, buy with SND, escrow, dispute window, refunds + testnet SND faucet (100/day)
- ✅ **Wallet identity** — sign in with any EVM wallet

## Roadmap (marketplace first)

| Phase | Scope |
|---|---|
| **1 · Buy flow** ✅ | `SoundHubMarket` live on Base Sepolia → list/buy/confirm/refund in the UI → SND faucet for testers |
| **2 · In-DAW** ✅/⏳ | **SoundHub inside Ableton Live** — M4L prototype shipped (catalog, BPM suggestions, buy & load); next: recommendation service, asset delivery, full import |
| **3 · Trust layer** | Asset verification badge from the DAW engine, seller reputation, license enforcement, packs as composable assets (bundles, drops, forks) |
| **4 · Collaboration** | ✅ Branches (named pointers, per-branch diff) → ⏳ merges (DAG), remix forks, audio preview, comments on tracks |
| **5 · Mainnet** | Base mainnet deployment, SND distribution vote, DAO treasury |

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
| `SoundHubMarket` | escrow marketplace (list/buy/refund) | `0x396d6ad9D5EA19eE56318624b05bC6EEEa2d1F5C` |
| `SoundHubFaucet` | testnet SND faucet (100/day) | `0x479fe2D308D118ef1723b5a34C8f8f37678cbba9` |
| `SoundHubGovernor` | DAO + timelock | `0x2db3F8BA478C445399bB8fbA921fC5e11Af202da` |

*Contracts pass an extensive test suite but are not professionally audited. This document is not financial advice.*
