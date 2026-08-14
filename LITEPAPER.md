# SoundHub Litepaper

**Don't generate. Buy. — a token-powered marketplace for finished sounds.**

> SoundHub is a marketplace where producers buy ready-made, verified presets,
> sample packs and patches with SND — instead of spending hours generating and
> tweaking sounds themselves. The platform parses DAW files to verify what's
> inside, escrows every purchase, and lets the DAO govern fees and curation.
>
> **And it lives where the music is made**: a SoundHub panel inside **Ableton
> Live** (Max for Live prototype shipped) turns buying into a 1–2 click
> action at the moment of intent — the marketplace meets the producer in the
> DAW, not on a website.

---

## 1. The problem

Music production's real bottleneck is **time, not tools**:

- **Generation is cheap, finished sound is not.** AI and endless preset-tweaking
  produce *a* sound — rarely *the* sound. Producers burn hours per sound and
  still end up with inconsistent, unverifiable results.
- **Buying finished sound is untrusted.** Marketplaces are fragmented,
  licenses are unclear, contents are unverifiable, provenance is missing, and
  creators get paid late or never.
- **No attribution infrastructure.** Independent producers and sound designers
  have no lightweight way to prove authorship, set licenses, or get paid for
  reuse.

## 2. The solution

**SoundHub flips the equation: don't generate, buy.** Finished, human-made
sounds — presets, kits, patches, packs, stems — become a token-powered
marketplace on **Base** (EVM). The DAW engine verifies what's inside, escrow
makes buying safe, and SND is the payment rail.

Three layers, one product:

| Layer | What it does |
|---|---|
| **Studio layer** (off-chain) | DAW parsing & verification, smart diffs, repos, versioning |
| **Tokenized layer** (on-chain) | SND payments, escrow marketplace, Release NFTs, DAO governance |
| **Distribution layer** (in-DAW) | SoundHub inside Ableton Live: catalog, BPM-aware suggestions, buy & load |

## 3. How it works — Studio layer

### 3.1 Versioning
Every commit stores a **full snapshot** of the project tree. Files are stored
**content-addressed** (SHA-256, deduplicated), so a snapshot costs almost
nothing when little changed. History is a simple, correct model — branches and
merges arrive with the move to a DAG.

### 3.2 The DAW engine — verification before purchase
The DAW engine is what makes buying finished sound trustworthy. SoundHub
parses the four major project formats instead of treating them as binary, so a
buyer sees exactly what's inside an asset *before* paying:

| Format | DAW | Parsed data |
|---|---|---|
| `.als` | Ableton Live | BPM, time signature, tracks, devices, plugins, samples |
| `.cpr` | Cubase | tempo, tracks, VST plugins |
| `.rpp` | REAPER | tempo, signature, tracks, FX chain |
| `.flp` | FL Studio | version, project name, author, tempo, channel count |

### 3.3 Smart diffs — the killer feature
Where GitHub says *"binary file changed"*, SoundHub says:

```
BPM 128 → 132
+ track  Pad (midi)
+ track  Vocal Chops (audio)
+ plugin Vital
+ sample VocalChop_01.wav
```

A **summary diff** of structured metadata (tracks, devices, plugins, samples,
tempo) plus a **raw unified diff** of the normalized content (pretty-printed
XML / text / hex for binary FLP). Same engine, two jobs: **verify assets for
sale** and **version projects in collaboration**.

## 4. The tokenized layer (on Base)

### 4.1 Wallet identity
Sign in with any EVM wallet via an EIP-191 personal-sign challenge verified
server-side. No password needed; the wallet address becomes the account.

### 4.2 The escrow marketplace (`SoundHubMarket.sol`) — the core
Finished sounds are bought with SND, not generated:

1. **List** — a seller publishes a verified asset (preset, pack, kit, patch)
   with a price in SND, a license tier (personal / commercial / sync /
   exclusive) and a pointer to the file.
2. **Buy** — the buyer's SND goes into **escrow**; the buyer receives the
   asset and license.
3. **Settle** — the buyer confirms receipt (instant payout to the seller) or
   the **2-day dispute window** passes (seller withdraws).
4. **Refund** — inside the window a buyer can request a refund; the arbiter
   (owner today, DAO tomorrow) resolves it.

No trust-me selling. No chargebacks. Payment is automatic and on-chain.

### 4.3 SND — the platform token (`SND.sol`)
- ERC-20 with **permit** (gasless approvals) and **ERC20Votes** (on-chain governance voting).
- **Fixed supply: 1,000,000 SND**, minted once at deployment. No mint function.
- **Primary role: the payment rail** — every marketplace purchase is
denominated in SND. Secondary roles: license fees, tips, token-gated premium
features, staking, and DAO voting power via delegation.

### 4.4 Release NFTs (`SoundHubRelease.sol`)
A finished project can be minted into a **Release NFT** (ERC-721 + ERC-2981):

- **Royalty** — configurable per release (default 5%), paid to the minter on
  secondary sales via ERC-2981.
- **Collaborator split** — revenue split (basis-point weights summing to 10,000)
  recorded on-chain at mint. E.g. producer 70% / vocalist 30%.
- **Treasury** — fans fund a release directly with **ETH or SND**
  (`fund` / `fundWithSND`).
- **Order-independent claiming** — collaborators claim their proportional share
  of the treasury at any time; claiming early doesn't short-change later
  claimers (per-collaborator accounted claims).

### 4.5 SoundHubGovernor — the DAO (`SoundHubGovernor.sol`)
SND holders govern the platform through a standard OpenZeppelin Governor:

- Voting delay **1 day** (blocks), voting period **3 days**, quorum **4%** of supply.
- Execution through a **1-day timelock** — no rug-pull governance.
- Proposals control platform parameters: fees, premium tiers, treasury
  allocation, feature funding.

## 5. Tokenomics (proposed)

Fixed supply **1,000,000 SND** — and its primary demand driver is the
marketplace: **every purchase of a finished sound is denominated in SND**, so
the token is the medium of exchange of the platform itself.

The initial deployment vests the full supply with the deployer; distribution
is *subject to a DAO vote* and should be finalized before mainnet. A reasonable
allocation for the community to ratify:

| Allocation | Share | Purpose |
|---|---|---|
| Ecosystem & community | 35% | airdrops to producers, bounties, faucets |
| DAO treasury | 25% | governed by SND holders via proposals |
| Core team | 20% | 24-month linear vesting, 6-month cliff |
| Liquidity | 10% | SND/ETH pool on Base |
| Early supporters | 10% | testnet contributors, early testers |

> ⚠️ **Nothing above is finalized.** The deployed testnet token has no
> pre-committed distribution; tokenomics are a DAO decision.

## 6. Distribution — SoundHub inside Ableton Live

A marketplace is only as good as its placement. The strongest distribution
channel for SoundHub is the DAW itself:

- **Point of maximum intent.** The producer is already inside Ableton,
  already hearing what's missing. Buying a finished preset there is a
  1–2 click action — no tab switch, no context break, no "I'll do it later".
- **Native panel, not a rewrite.** A **Max for Live device** (JS inside Live)
  reads the catalog straight from the chain via public RPC, reads the Live
  set BPM for context-aware suggestions, and loads purchased assets into the
  project. Prototype shipped in `m4l/` (see `ARCHITECTURE.md`).
- **Context-aware, not just a storefront.** BPM → genre matching today;
  key, tracks and devices (via the DAW engine) tomorrow — "bass presets for
  128 BPM techno" instead of a flat list.
- **Invisible web3.** The user sees *Buy & Load*, never `approve`/gas/RPC.
  WalletConnect pairing or a backend relayer keeps the blockchain under the
  hood.
- **One engine, three markets.** The same DAW parsers that verify assets for
  sale power the in-DAW recommendations and the smart diffs — the
  distribution layer is built on the studio layer.

Why this wins: without the integration SoundHub is a good niche marketplace;
with it, it is part of the producer's workflow — the difference between a
website and a tool.

## 7. Revenue model

- **Marketplace fee** — small % on each escrow purchase (configurable via DAO):
  funds development, curation, grants, ecosystem rewards.
- **Sellers earn** — the core creator income: finished sounds sold for SND,
  settled automatically.
- **Premium tier** — token-gated (hold/stake SND): deeper verification, larger
  listings, analytics.
- **Release royalties** — creator-set ERC-2981 royalty on Release NFT
  secondary sales.
- **Tips** — fans tip producers in SND or ETH, fully on-chain.

## 8. Roadmap

- ✅ **Foundation** — repos, snapshot commits, content-addressed storage, web UI
- ✅ **DAW engine** — parsers for `.als`/`.cpr`/`.rpp`/`.flp` + smart diffs
- ✅ **Tokenized layer** — SND, Release NFTs, DAO, wallet sign-in (deployed on
  **Base Sepolia**)
- ✅ **Marketplace live** — `SoundHubMarket` + faucet deployed, list/buy/confirm
  in the UI, demo listing on-chain
- ✅ **In-DAW prototype** — SoundHub inside Ableton Live (Max for Live):
  catalog from RPC, BPM-aware suggestions, buy & load (see `m4l/`)
- ⏳ **Recommendation service** — DAW-engine-backed `/api/recommend` (BPM, key,
  tracks, devices → ranked assets)
- ⏳ **Asset delivery** — license-scoped download endpoint for the device,
  full Live browser/rack import
- ⏳ **Trust layer** — verification badges from the DAW engine, seller
  reputation, license enforcement
- ⏳ Branches & merges (snapshot → DAG), audio preview, real-time collaboration
- ⏳ WalletConnect signing inside M4L / relayer; FL Studio, Cubase, REAPER
  equivalents
- ⏳ **Base mainnet deployment + token distribution vote**

## 9. Contract addresses (Base Sepolia)

| Contract | Address |
|---|---|
| SND (ERC-20) | `0x37a6B3aD766ffb98673290A634490C8bF952DB2F` |
| SoundHubRelease (NFT) | `0xb3716751572db83d22aeED95Be7da125A4d22446` |
| SoundHubMarket (escrow) | `0x396d6ad9D5EA19eE56318624b05bC6EEEa2d1F5C` |
| SoundHubFaucet (testnet) | `0x479fe2D308D118ef1723b5a34C8f8f37678cbba9` |
| TimelockController | `0x98F6a809ffa83cbe5f9bAFa7Cf762f2f24Cfa548` |
| SoundHubGovernor (DAO) | `0x2db3F8BA478C445399bB8fbA921fC5e11Af202da` |

## 10. Risks & disclaimer

- **Unaudited contracts.** The smart contracts pass an extensive test suite
  (token, royalties, splits, full DAO lifecycle) but have **not** been through
  a professional security audit. Test on testnet first.
- **Narrative-driven market.** The value of SND is tied to platform adoption,
  not to any underlying utility guarantee.
- **Format complexity.** DAW files are reverse-engineered formats; parser
  coverage is best-effort and improves over time.
- This litepaper is **not financial advice** and does not constitute an offer
  to sell securities. Nothing here is an investment contract.
