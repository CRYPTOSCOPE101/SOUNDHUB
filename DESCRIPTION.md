# SoundHub — GitHub for Sound

**SoundHub is a tokenized, collaborative GitHub for music producers, sound designers, composers, and audio developers.**

While GitHub treats an Ableton project as *"binary file changed"*, SoundHub parses it:

```
GitHub:   binary file changed (38.4 MB)
SoundHub: BPM 128 → 132
          + track  Pad (midi)
          + track  Vocal Chops (audio)
          + plugin Vital
          + sample VocalChop_01.wav
```

That is the core difference. SoundHub turns samples, presets, sound packs, project files, stems, MIDI, plugins, and production templates into **versioned, attributable, and monetizable creative assets** — with a history that records *who created it, who contributed, what license applies, how it evolved, and how revenue is split.*

Instead of losing ownership, credits, and revenue every time a sound file is shared in a chat, uploaded to a drive, or passed between collaborators, creators publish on SoundHub with a verifiable trail — and a tokenized layer that pays contributors automatically.

---

## The Problem

Music production is already collaborative, but its infrastructure is fragmented.

A producer may send a loop through Telegram, receive vocals through Google Drive, edit a project in Ableton or FL Studio, license a sample from a marketplace, and release the final record months later — without a clean provenance trail. That creates persistent problems:

- **Lost attribution** — producers, sound designers, session musicians, and sample creators are often uncredited.
- **Unclear ownership** — hard to prove where a melody, drum loop, patch, stem, or preset originated.
- **Broken royalty splits** — contributors are paid late, manually, or not at all.
- **No version control** — revisions live across local folders, cloud drives, and `final_v12_REAL_FINAL.wav`.
- **Weak monetization** — talented creators distribute valuable assets globally but capture little recurring upside from reuse.
- **High collaboration friction** — no shared workspace that understands both creative files and rights.

## The Core Idea

GitHub standardized collaboration for code through repositories, commits, branches, pull requests, attribution, and open-source licensing. **SoundHub applies that model to audio.**

| GitHub for code | SoundHub for music |
|---|---|
| Repository | Sound repository or project |
| Commit | Audio version or production revision |
| Branch | Alternate mix, remix, or creative direction |
| Pull request | Collaboration request or contribution proposal |
| Contributor history | Verified producer and sound-designer credits |
| Open-source license | Audio, commercial, remix, and royalty license |
| Package registry | Marketplace for samples, presets, stems, MIDI, and tools |
| GitHub Sponsors | On-chain patronage, royalties, and creator rewards |

The result is not merely an NFT marketplace for music. It is a **production layer for the global sound economy.**

---

## Live today

Honest about scope: this is what exists and works right now.

- ✅ **Repos & versioning** — snapshot commits with content-addressed storage (SHA-256 dedup), so versioning multi-megabyte DAW files costs almost nothing.
- ✅ **DAW engine** — parsers for the four major project formats:

| Format | DAW | Parsed data |
|---|---|---|
| `.als` | Ableton Live | BPM, signature, tracks, devices, plugins, samples |
| `.cpr` | Cubase | tempo, tracks, VST plugins |
| `.rpp` | REAPER | tempo, signature, tracks, FX chain |
| `.flp` | FL Studio | version, name, author, tempo, channels |

- ✅ **Smart diffs** — structural summary of what changed (tempo, tracks, devices, plugins, samples) plus a raw unified diff of the normalized content.
- ✅ **On-chain rights layer** — live on **Base Sepolia** (testnet, audited-by-tests):
  - **SND** — ERC-20 platform token, fixed supply **1,000,000**, permit + on-chain voting.
  - **Release NFTs** — ERC-721 + ERC-2981: royalties, on-chain collaborator revenue splits, treasury fundable in ETH/SND, order-independent claiming.
  - **SoundHubGovernor** — DAO: voting delay 1 day, period 3 days, quorum 4%, 1-day timelock.
- ✅ **Wallet identity** — sign in with any EVM wallet (EIP-191 signature verified server-side).

## Smart diffs — the killer feature

DAW files are opaque blobs to normal version control. SoundHub's DAW engine reads the structure and answers the question every collaborator actually asks: **what changed?**

- Tempo, time signature, and DAW version
- Tracks added / removed / renamed (with type: audio, midi, group, master)
- Devices and plugins added / removed (Serum, Vital, ReaComp…)
- Samples and references added / removed
- Raw unified diff of the normalized content for those who want the details

This replaces informal *"trust me, I made that"* collaboration with auditable creative provenance.

## Version control for sound

A SoundHub repository is a living creative workspace. Publish the original idea, invite contributors, compare variations, create alternate versions, and preserve the full evolution of a track or sound pack:

```text
/neon-drift
  /v1 — original 140 BPM synthwave demo
  /v2 — new bassline and drum arrangement
  /v3 — vocal contribution added
  /v4 — club mix
  /v5 — final master
  /remixes — approved community remix branches
```

Every meaningful contribution can be recorded: who uploaded the original loop, who redesigned the bass, who added vocals, who mixed or mastered, which samples and presets were used, which version shipped, and what percentage of revenue each contributor receives.

## What creators can publish

- Drum kits, one-shots, loops, and sample packs
- Synth presets and sound-design patches
- MIDI packs, chord progressions, melodies, arrangements
- Vocals, acapellas, ad-libs, spoken-word recordings
- Stems, mixes, masters, alternate versions
- DAW project templates (Ableton, FL Studio, Logic, Bitwig…)
- Plugin settings, effect chains, mixing presets
- Field recordings, Foley, cinematic SFX, game-audio assets
- AI-assisted sound assets with transparent source and rights metadata
- Full tracks, remix packs, collaborative albums

Each asset has a permanent creator profile, metadata, release terms, version history, and optional on-chain proof of ownership.

## Tokenized rights

SoundHub uses tokenization **selectively — as infrastructure for rights, access, and revenue**, not as a speculative wrapper. Each project or asset can carry a configurable on-chain rights layer:

- **Creator ownership** — immutable proof of original publication and authorship claim
- **Contributor splits** — predefined on-chain percentages for producers, vocalists, engineers, designers, collaborators
- **License tokens** — programmable licenses: personal, commercial, sync, remix, exclusive ownership
- **Access passes** — token-gated downloads, private folders, premium packs, early releases, creator communities
- **Revenue sharing** — automatic distribution from sales, subscriptions, licensing, secondary markets
- **Collectible editions** — limited editions for fans where appropriate
- **Royalty routing** — revenue flows to eligible contributors according to transparent split rules

> If a sound creates value, the people who created that sound should be able to prove it — and be paid automatically.

## Collaboration workflow

1. **Create a repository** — public, private, or token-gated, for a track, pack, artist project, label catalog, or game soundtrack.
2. **Upload source assets** — loops, stems, MIDI, presets, DAW files, BPM/key/genre tags, license settings.
3. **Invite contributors** — request access, submit variations, upload stems, propose remixes, negotiate terms.
4. **Review contributions** — preview changes, compare versions, see contribution history, accept or reject, set credit and split allocations.
5. **Release and monetize** — sell licenses, distribute, create collectible editions, unlock fan access, connect to streaming.
6. **Split revenue automatically** — on sale, licensing deal, or platform payout, funds route by agreed on-chain splits. No spreadsheets. No forgotten collaborators. No delayed manual payouts.

## Use cases

**Producer collaboration** — a beatmaker opens a melodic idea for collaboration; a sound designer adds a signature texture, a vocalist an acapella, an engineer the master. Each accepted contribution receives a transparent share before the track goes live — and payments split automatically.

**Sample-pack marketplace** — a sound designer launches a premium pack under multiple license tiers (attribution-required / creator / commercial / sync / exclusive buyout). Every customer knows exactly what they may do with the sounds.

**Remix economy** — an artist publishes official stems and a remix repository. Producers fork, publish remix branches, and submit for approval; the best remix gets an official release, on-chain attribution, and a preset royalty split.

**AI sound provenance** — creators declare whether an asset is human-made, AI-assisted, generated from licensed material, derived from community assets, or restricted from AI training — a clear rights layer for a rapidly changing landscape.

---

## The SoundHub economy

SND is designed to be useful because SoundHub is useful — not the other way around. Live today: **SND (ERC-20, 1,000,000 fixed supply), Release NFT royalties/splits, DAO governance** — deployed on Base Sepolia, testnet.

Proposed mechanics (subject to DAO vote):

- **Platform token** — governance, creator incentives, fee discounts, staking, premium access
- **Creator tokens** — optional community tokens for producers, labels, collectives
- **Reputation system** — rewards for quality assets, verified credits, reliable licensing
- **Curation incentives** — earnings for discovering, reviewing, and promoting sound libraries
- **Protocol fees** — a small marketplace percentage funding development, curation, grants
- **Creator grants** — support for open sample libraries, audio tools, collaborative releases

## Roadmap

| Phase | Scope |
|---|---|
| **1 · Foundation** ✅ | Repos, snapshot commits, content-addressed storage, DAW parsers, smart diffs, web UI |
| **2 · Tokenized layer** ✅ (testnet) | SND, Release NFTs, DAO, wallet sign-in — live on Base Sepolia |
| **3 · Collaboration** | Branches & merges (DAG), stem/audio preview in browser, real-time editing, comments on tracks & regions |
| **4 · Marketplace** | Licensing, sample/preset storefront, collectible editions, creator tokens, reputation |
| **5 · Mainnet** | Base mainnet deployment, SND distribution vote, DAO-governed treasury |

## Why now

Music is becoming more modular: producers in different countries, distributed vocal sessions, AI-assisted sound design, remix communities, sample marketplaces, multiple monetization channels. The infrastructure is still folders, DMs, and manually maintained split sheets. SoundHub gives producers the primitives developers already expect: version history, collaboration permissions, transparent attribution, reusable building blocks, licensing standards, distribution rails, automated revenue splits, and a global discovery layer.

## SoundHub vs. existing tools

| | GitHub LFS | Splice / Loopcloud | NFT-music (Sound.xyz, Royal) | SoundHub |
|---|---|---|---|---|
| Versions binaries | ✅ | ❌ | ❌ | ✅ |
| Understands DAW files | ❌ | partial (tags only) | ❌ | ✅ **parses & diffs** |
| Smart diffs | ❌ | ❌ | ❌ | ✅ |
| On-chain splits/royalties | ❌ | ❌ | release-only | ✅ per-collaborator |
| Production workspace | ❌ | browser-only | ❌ | ✅ repo + history |
| DAO governance | ❌ | ❌ | ❌ | ✅ |

## Vision

**SoundHub is where sound becomes open, collaborative, programmable, and ownable** — a home for the producer licensing a drum kit, the sound designer building a world-class preset library, the artist launching a remix ecosystem, the indie game studio sourcing audio, and the collective creating the next cultural movement. A global, composable audio graph:

> Every sound has provenance. Every contributor has credit. Every collaboration has transparent ownership. Every successful asset can pay its creators automatically.

**SoundHub is GitHub for sound — powered by creators, versioned by collaboration, and monetized through programmable ownership.**

---

## Contracts (Base Sepolia, testnet)

| Contract | Address |
|---|---|
| SND (ERC-20) | `0x37a6B3aD766ffb98673290A634490C8bF952DB2F` |
| SoundHubRelease (NFT) | `0xb3716751572db83d22aeED95Be7da125A4d22446` |
| TimelockController | `0x98F6a809ffa83cbe5f9bAFa7Cf762f2f24Cfa548` |
| SoundHubGovernor (DAO) | `0x2db3F8BA478C445399bB8fbA921fC5e11Af202da` |

*Contracts pass an extensive test suite (token, royalties, splits, full DAO lifecycle) but have not been professionally audited. This document is not financial advice.*
