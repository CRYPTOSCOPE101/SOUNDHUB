# Complete Dossier on Splice Studio and Competitors

---

# PART 1: SPLICE STUDIO

---

## What is Splice Studio

**Splice Studio** — a free cloud application for collaborative music production, based on version control and automatic DAW file backup. It was often called **"GitHub for musicians"** — for its analogy with git-workflow: automatic saving, version history, change comments, colleague invitations.

**Status: CLOSED** (March – June 2023)

---

## History and Launch Timeline

| Date | Event |
|------|-------|
| **October 2013** | Private beta of macOS version of Splice Studio |
| **Late 2013** | Windows version released |
| **September 2014** | Public launch ($4.5M Series A, investors: Tiësto, Scooter Braun, True Ventures) |
| **December 2015** | Splice Studio v2 release — improved UI, Audio-Only Projects support |
| **2017** | Last major Studio update. Only maintenance after that |
| **March 9, 2023** | CEO Kakul Srivastava announced Studio closure |
| **April 7, 2023** | New project creation disabled in Desktop App |
| **June 5, 2023** | Studio completely removed from menu and Desktop App |

---

## Founders and Company

| | |
|---|---|
| **Founders** | Steve Martocci (GroupMe) and Matt Aimonetti (Sony PlayStation, LivingSocial) |
| **Company** | Splice (Distributed Creation Inc) |
| **Headquarters** | New York |
| **Current CEO** | Kakul Srivastava (since May 2022) |
| **Technologies** | Go, Objective-C, C#, JavaScript |
| **Total funding** | >$150M (Series A-D, Goldman Sachs lead on Series D) |
| **Valuation** | ~$500M |
| **Now** | Platform focused on Splice Sounds (samples) and Rent-to-Own (plugins). Acquired Spitfire Audio in April 2025 |

---

## What Splice Studio Could Do — Full Feature List

### Automatic Backup
- On every **Save** in DAW, the project was automatically uploaded to the cloud
- All samples and dependencies were also synced
- **Free unlimited storage** forever

### Version Control
- Each save was a new version with timestamp
- Could revert to any previous version
- Visual timeline of the project in browser and app
- Tracking who changed what (like git blame)

### Collaboration
- Invite colleagues by email
- Colleague got access to all versions and timeline
- Comments on each revision
- Project was private by default — only invited people could see it

### DAW Integration (Native Awareness)
Splice Studio "understood" DAW formats and could show:
- Track names within the session
- List of used plugins
- Track structure visualization
- Worked with native files, not just stems

**Supported DAWs:**
- Ableton Live
- FL Studio (including Mac version with FL Studio 20)
- Apple Logic Pro X and GarageBand
- PreSonus Studio One
- Pro Tools (stems only)
- Reaper — NOT supported
- Reason Studios — NOT supported

### Audio-Only Projects (Stems Sharing)
- Upload exported audio stems for cross-platform work
- Allowed working with a colleague who has a different DAW or is missing plugins

### DNA Player
- Public player for listening to tracks
- Visualized each individual track (not just waveform)
- Mute/solo functions for individual instruments
- Listener comments (similar to SoundCloud)
- Ability to make a track publicly remixable

### Desktop App
- Application for macOS and Windows
- Pop-up tray menu showed projects with latest versions
- Could add comments to saves directly from menu
- Background synchronization

### Community Tab (closed in 2023)
- Browse other musicians' projects
- Download others' projects for study
- Find collaborators

---

## Limitations and Weaknesses

| Problem | Details |
|---------|---------|
| Only Splice folder | All synced projects had to live in a special Splice directory. Could change the path, but only one folder |
| No real-time | Colleagues couldn't work simultaneously — only async |
| Need same DAW + plugins | For full project opening, both sides needed the same DAW and all plugins |
| No Pro Tools/Reaper/Reason | Pro Tools, Reaper, Reason were not natively supported |
| Bugs accumulated | No development since 2017, bugs piled up |
| Not monetized | Completely free — cost center for the company |
| Unreliable backup | Experts didn't recommend using as sole backup — critical files better duplicated |
| No mobile Studio | Mobile app only for browsing samples |

---

## Pricing

**Completely free.** Unlimited storage. No subscription. No ads.

This was the reason for closure — the feature was never monetized and hindered Splice's core business (samples + Rent-to-Own).

---

## Why It Was Closed

From CEO Kakul Srivastava's letter (March 9, 2023):

> "While the potential of Studio to help musicians collaborate was at the heart of our ideology, this feature has not been in focus since 2017. Simply put, we weren't able to deliver quality we could be proud of. In fact, maintaining it was slowing us down from creating value faster."

Key reasons:
1. **Unprofitability** — free product without monetization
2. **Priorities** — Splice focused on Sounds (samples) and Rent-to-Own (plugins)
3. **Lack of development** — 6 years without significant updates
4. **Competition** — users found alternatives

---

## What Splice Studio Meant for the Industry

- **First large-scale** version control tool for DAW files
- **GitHub-like approach** to music production
- Used by top producers: Kid Cudi, Jhené Aiko, Tiësto, and others
- Inspiration for dozens of subsequent startups
- Launched the DNA Player concept — interactive listening with track muting

**Example tracks with Splice samples (Splice Sounds, not Studio, but illustrates the brand):**
- Sabrina Carpenter — "Espresso"
- Justin Bieber — "Running Over"
- Zedd & Grey — "The Middle"
- Ariana Grande — "Break Up With Your Girlfriend"
- Lil Nas X — "Panini"
- Dua Lipa — "Don't Start Now"

---

## Technical Architecture

```
Desktop App (macOS/Win) --> Splice Cloud (unlimited) --> Web Browser (Timeline, DNA Player)
       |                          |
       | Filesystem Watcher       | version storage
       | (auto-sync on DAW save)  |
       v                          v
Splice Project Folder <-- Single folder for all projects
```

**Native DAW files:**
- `.als` (Ableton)
- `.flp` (FL Studio)
- `.logic` / `.band` (Logic/GarageBand)
- `.song` (Studio One)

**Stack:** Go (backend), Objective-C (macOS), C# (Windows), JavaScript (web)

---

## Final Rating of Splice Studio

| Criterion | Rating |
|-----------|--------|
| Importance for the industry | 5/5 — Pioneer in version control for music |
| Functionality | 4/5 — Free, unlimited, DAW-aware |
| Stability | 3/5 — Bugs accumulated, support scaled back |
| Usability | 4/5 — Simple workflow, auto-backup |
| Price | 5/5 — Free |
| Legacy | 5/5 — Launched a wave of startups (SyncMuse, Boombox, etc.) |

---

# PART 2: COMPETITORS AND ALTERNATIVES

---

## Market Overview

After Splice Studio closed in May 2023, a void appeared in the music collaboration market. Dozens of platforms are trying to fill it — from direct replacements to fundamentally new solutions.

The market divides into 4 categories:
1. **Async collaboration** (stems, versions, feedback) — SyncMuse, Boombox, Feedtracks, musiciansXchange
2. **Real-time DAW** (collaborative work in one DAW) — BandLab, Soundtrap, Sesh, Sessionwire
3. **Audio review** (feedback for production teams) — Pibox, Feedtracks
4. **Crowdsourcing** (finding musicians) — Kompoz, musiciansXchange

---

## 1. SyncMuse

**Website:** syncmuse.co
**Status:** Active (startup, early stage)
**Goal:** Spiritual successor to Splice Studio — async collaboration without the chaos

### What it is
Platform for asynchronous music collaboration. Works with stems and audio files (not DAW projects). Specifically created as a Splice Studio replacement.

### Key Features
- **Version history** — every uploaded video/audio creates a new version in the timeline
- **Timestamped waveform feedback** — comments tied to specific moments on the waveform
- **DAW-agnostic** — works with any DAW since it accepts WAV/MP3 (stems)
- **Secure sharing** — controlled links with expiry and granular permissions
- **Version comparison** — A/B comparison of any two versions

### What's NOT here (yet)
- Desktop app with auto-sync (planned)
- DAW file parsing (Ableton/Logic/FL)
- Plugin detection
- DNA Player

### Pricing
- **Free plan** — basic features, no credit card
- **Pro plan** — (price not listed, in development)

### For whom
- Producers working asynchronously
- Mix engineers receiving stems from clients
- Bands losing takes in Dropbox

### Rating
- **Pros:** DAW-agnostic, beautiful UI, timestamped feedback, versions
- **Cons:** Early stage, no desktop sync, no DAW-aware, small base (150+ users)

---

## 2. Boombox

**Website:** boombox.io
**Status:** Active, 100K+ artists
**Goal:** All-in-one platform for musicians — from idea to distribution

### What it is
Cloud platform for collaboration, storage, distribution, and music monetization. Positioned as a Splice Studio replacement + more.

### Key Features

**Drive and Storage:**
- Cloud storage for DAW files, stems, bounce, video
- Enterprise-grade security
- All audio formats supported
- Auto-sync via Boombox Sync (macOS)

**Collaboration:**
- Add colleagues to projects
- Timestamped audio comments
- Mix versioning
- In-platform chat

**Playlists:**
- Create private playlists (like Spotify, but for unreleased tracks)
- Custom artwork
- Listening analytics
- Password protection

**Song Splits and Contracts:**
- Copyright distribution tool
- Legally binding contracts
- Sign with a couple clicks

**AI Tools (Boombot AI):**
- Stem splitting
- AI mastering
- Chord generator
- Lyrics assistant

**Distribution:**
- Spotify, Apple Music, 150+ platforms
- 100% royalties stay with the artist
- Split management

### Pricing

| Plan | Price | Storage | Features |
|------|-------|---------|----------|
| **Collaborator (Free)** | $0/mo | 1 GB | Timestamped comments, versioning, 45 AI credits, 5 tracks in playlist |
| **Starter** | $4.20/mo ($50/yr) | 500 GB | Video, fan polls, 55 AI credits, ad-free |
| **Creator** | $8.35/mo ($100/yr) | 2 TB | Branded shares, password protection, AI search, 100 credits, distribution for 2 artists |
| **Pro** | $15.85/mo ($190/yr) | Unlimited | Live stream library, playlist analytics, 200 credits, unlimited distribution |

### For whom
- Producers who need backup + collaboration + distribution
- Indie artists looking for all-in-one solution
- Bands working asynchronously

### Rating
- **Pros:** Wide functionality, mobile apps, splits/contracts, distribution, AI tools, affordable price
- **Cons:** No real-time DAW, no native DAW integration, no auto-sync (macOS only via separate app)

---

## 3. BandLab

**Website:** bandlab.com
**Status:** Active, 100M+ creators
**Goal:** Free browser DAW + social network + AI tools

### What it is
Full-featured DAW in the browser with social features and AI tools. Works on any device without installation.

### Key Features

**BandLab Studio (DAW):**
- 16-48 tracks (depending on plan)
- 436+ virtual instruments
- 300+ effect presets
- Automation
- Multi-track recording
- Real-time collaboration (up to 50 people)
- Versioning
- WAV/MP3 export

**AI Tools:**
- **SongStarter** — generate beats/riffs from genre (free, unlimited)
- **Splitter** — stem splitting (vocals/drums/bass/instruments, up to 7 stems)
- **AutoMix** — automatic mix by genre
- **Voice Cleaner** — noise removal from vocals
- **Voice Changer** — 17 AI voices
- **FX Preset Generator** — generate effect chains from text

**Social Network:**
- Publish tracks
- Followers, likes, comments
- Find colleagues by instrument/genre
- Boost promotion

**Integration:**
- Cakewalk Next and Sonar (desktop DAW from BandLab)
- Mobile apps (iOS/Android)

### Pricing

| Plan | Price | Features |
|------|-------|----------|
| **Free** | $0 | 16 tracks, basic FX, 2 beats/week, 20 samples/mo, 3 stem splits/day |
| **Pro** | $14.99/mo or $99/yr | 32 tracks, ad-free, AI tools, 10 beats/week, distribution |
| **Max** | Coming Soon ($199/yr) | Unlimited, Mastering EQ, $50 Boost/mo, priority support |

### For whom
- Beginner musicians
- Budget producers
- Mobile creators
- Those who need a free DAW for sketches

### Rating
- **Pros:** Completely free, powerful AI tools, 100M+ community, real-time collab up to 50 people, mobile apps
- **Cons:** No VST/AU plugin support, 16-bit/44.1kHz export, cloud-only, limited professional mixing

---

## 4. Soundtrap (Spotify → Founders)

**Website:** soundtrap.com
**Status:** Active (Soundtrap 2.0 launched March 2026)
**Goal:** Browser DAW for real-time collaboration and education

### What it is
Browser DAW owned by Spotify (2017-2023), now back to founders. Specializes in real-time collaboration and education.

### Key Features

**Soundtrap Studio 2.0 (March 2026):**
- Completely redesigned interface
- Desktop app for Mac (Windows coming soon)
- Automation for nearly all effects
- 1000+ new loops and presets
- Unlimited tracks
- Mobile app for listening

**Real-time Collaboration:**
- Up to 30 simultaneous users (Unlimited plan)
- Color cursors for each participant
- Built-in voice chat (push-to-talk)
- Text chat

**Tools:**
- Beatmaker, sampler, synths, drum kits, 808
- 10,000+ royalty-free loops
- Auto-Tune (Antares)
- 40+ effects (reverb, distortion, EQ, delay, compressor)

**Education:**
- Soundtrap for Education (Classroom, School, District plans)
- Google Classroom integration
- COPPA/GDPR/FERPA compliant

### Pricing

| Plan | Price | Features |
|------|-------|----------|
| **Free** | $0 | 5 projects, limited loops, 2 collaborators, MP3 export |
| **Sound Starter** | $9.99/mo ($7.99/yr) | Vocal tuning, automation, extended loops |
| **Music Production** | $9.99/mo | Full library, WAV export, unlimited projects |
| **Vocals & Songwriting** | $14.99/mo | Vocal tools, transcription, podcasts |
| **Production & Vocals** | $14.99/mo | Everything combined |
| **Unlimited** | $16.99/mo ($13.99/yr) | 30 collaborators, early access, full library |
| **Spotify Bundle** | $19.99/mo | Unlimited + Spotify Premium |

### For whom
- Beginner musicians
- Educational institutions
- Podcasters
- Those who need real-time collaboration

### Rating
- **Pros:** Best-in-class real-time (30 people), clean UI, education plans, starting at $0
- **Cons:** No VST/AU, limited automation (volume/pan), no MIDI export, negative reviews about bugs and support

---

## 5. Pibox

**Website:** pibox.com
**Status:** Active, used by Universal Production Music, Epidemic Sound
**Goal:** Audio/video collaboration for production teams

### What it is
Platform for audio/video review and approval. Not a DAW, but a feedback management tool. Positioned as "Dropbox + Trello + Asana for music."

### Key Features
- **Timestamped comments** on audio and video waveforms
- **Lossless playback** — work with original quality
- **Version chains** — link versions for comparison
- **Comments** — public and private
- **File system** — flexible folders for all formats
- **Metadata** — custom forms, Excel/API export
- **AI Workflows** — choose your own AI integration
- **Chat** — team and private
- **Mobile app** (iOS)
- **Multi-team** — manage multiple teams

### Pricing

| Plan | Price | Features |
|------|-------|----------|
| **Free** | $0 | 2 users, 1 GB, 1 group |
| **Pro** | $10/user/mo | 100 GB, unlimited projects, archiving, RAW playback |
| **Team** | $20/user/mo | 1 TB, private comments, auto-forwarding, custom statuses |
| **Enterprise** | Custom | SLA, SSO, API, multi-team, ISO-27001 |

### For whom
- Production teams (Universal, Epidemic Sound)
- Mix engineers receiving client feedback
- Labels managing multiple projects

### Rating
- **Pros:** Excellent waveform feedback, enterprise security, flexible file system
- **Cons:** Expensive for small teams, no DAW integration, no DAW file versioning

---

## 6. Sessionwire

**Website:** sessionwire.com
**Status:** Active, used by Berklee, Blackbird, CRAS
**Goal:** Real-time DAW sessions with studio-grade audio

### What it is
Platform for real-time collaboration directly inside DAW. Streams 48kHz uncompressed stereo — not VoIP like Zoom.

### Key Features
- **HQ Audio Streaming** — 48kHz stereo from DAW to DAW
- **Automute** — automatic talkback disable on playback
- **Plugin Suite** (AAX/VST3/AU) — free plugin for any DAW
- **HD video** — up to 50 participants (Studio plan)
- **Screen sharing** and **Remote Desktop**
- **P2P file sharing** — encrypted, no cloud
- **Session recording** to disk (video + voice)
- **15+ DAW** — Ableton, Logic, FL Studio, Pro Tools, Cubase, etc.

### Pricing

| Plan | Price | Features |
|------|-------|----------|
| **Free** | $0 | Public profile, unlimited Connections, Plugin Suite |
| **Basic** | $9/mo | Private Studio, 1 guest, 100MB files, 5GB Vault |
| **Studio** | $29/mo | 50 guests, disk recording, Remote Desktop, 100GB Vault, Puremix Pro |
| **Business** | Custom | Multi-site, analytics, onboarding, educational institutions |

### For whom
- Professional producers and audio engineers
- Educational institutions (Berklee, CRAS)
- Recording studios
- Real-time sessions with clients

### Rating
- **Pros:** Studio-grade audio, DAW integration, disk recording, Remote Desktop
- **Cons:** Expensive ($29/mo for Studio), no version control, no cloud storage

---

## 7. Sesh

**Website:** sesh.fm
**Status:** Active, 50K+ producers
**Goal:** Browser DAW for real-time beatmaker collaboration

### What it is
Full-featured browser DAW with real-time collaboration and AI stem splitter. Focus on beats and hip-hop.

### Key Features
- **Cloud Studio** — full DAW in browser
- **Real-time collaboration** — see each other's cursors in real time
- **Serum-level synthesis** — pro-grade synthesis with mod matrix in browser
- **Collaborative piano roll** — collaborative note editing
- **AI Stem Splitter** — 3 tools (acapella, drum remover, full splitter)
- **18,000+ sounds**, samples and presets
- **Unlimited version history**
- **Auto-save** — every action syncs
- **Chat** — built into DAW

### Pricing

| Plan | Price | Features |
|------|-------|----------|
| **Free (Starter)** | $0 | Limited projects, limited export, 1-hour history |
| **Pro** | $5/mo (annual) or $19/mo | Unlimited projects/export/collaborators/storage, commercial rights |
| **Founders Club** | $6 (one-time) | Lifetime 20% discount, early access, 1TB storage |

### For whom
- Beatmakers (hip-hop, trap, lo-fi)
- Beginner producers
- Bands working in real-time

### Rating
- **Pros:** Serum-level synthesis in browser, no install, no props, real-time, AI stem splitter, very affordable
- **Cons:** Browser only, no offline, limited functionality for professional mixing

---

## 8. Feedtracks

**Website:** feedtracks.com
**Status:** Active
**Goal:** Google Drive for audio + waveform comments

### What it is
Cloud storage with audio-specific features: waveform comments, versioning, playlists, shared drives.

### Key Features
- **Timestamped comments** on waveform
- **Audio comments** — voice feedback
- **Track versioning** — compare mix versions
- **Playlists** — organize tracks
- **Shared drives** — team collaboration
- **Blockchain Certification** — proof of authorship
- **Security** — OAuth, magic links, passkeys, password protection
- **Dashboard** — analytics and statistics

### Pricing

| Plan | Price | Storage |
|------|-------|---------|
| **Free** | $0 | 1 GB, 100MB/playlist |
| **Fan** | €6.99/mo | 200 GB, unlimited playlists, 2 certificates/mo |
| **Pro** | €12.99/mo | 500 GB, priority support, 5 certificates/mo |
| **Studio** | Custom | 1 TB, unlimited shared drives |

### For whom
- Producers who need "Google Drive for audio"
- Small studios
- Podcasters

### Rating
- **Pros:** Familiar workflow (like Google Drive), waveform comments, blockchain certification
- **Cons:** No real-time DAW, no DAW integration, limited functionality for large teams

---

## 9. musiciansXchange

**Website:** musiciansxchange.com
**Status:** Active (early stage, 500 founding members)
**Goal:** "The missing collaboration layer" — discovery + stems + version control + feedback + auto-credit

### What it is
Platform combining finding collaborators, sharing stems, version control, and crediting in one place. Not a DAW, not streaming, not a marketplace — specifically the collaboration layer.

### Key Features
- **DAW-agnostic stem sharing** — WAV, MP3, AIFF, FLAC, M4A, AAC
- **Git-style version control** — branches, comparison, revert, per-branch revisions
- **Timestamped feedback** — comments on waveform
- **Discovery** — search by instrument, role, genre, level, location
- **Auto-credit** — automatic crediting of all participants
- **Audit trail** — every action logged (download, upload, change)
- **Showcase** — publish finished tracks with credits
- **Desktop app** — Windows (macOS coming soon), watch DAW export folders
- **Real-time chat** — SignalR in every workspace

### Pricing

| Plan | Price | Features |
|------|-------|----------|
| **Free** | $0 forever | 2 GB, 1 private collaboration, unlimited joined collaborations |
| **Pro** | $3.99/mo ($39/yr) | 25 GB, unlimited tracks and collaborations |
| **Unlimited** | $9.99/mo ($99/yr) | Unlimited everything, storage grows |
| **Founders** | Free (first 500) | Unlimited forever free |

### For whom
- Musicians looking for collaborators
- Producers working with session musicians
- Those who need Git-like workflow for audio

### Rating
- **Pros:** Unique combination of discovery + version control + auto-credit, Git-style branches, desktop app with DAW watch, very affordable
- **Cons:** Early stage, small base, no real-time DAW

---

## 10. Satellite Sessions

**Website:** mixedinkey.com/satellite
**Status:** Active
**Goal:** Real-time DAW collaboration via plugin

### What it is
VST/AU/AAX plugin that allows sharing audio and MIDI between DAWs in real time. "The cable between DAWs."

### Key Features
- **Cross-DAW sync** — Ableton ↔ Logic ↔ Pro Tools ↔ FL Studio ↔ Cubase
- **BPM/Time Signature/Sample Rate sync** automatically
- **Satellite Audio** — audio streaming between DAWs
- **Satellite MIDI** — MIDI data exchange
- **Drag & Drop** — drag audio/MIDI between DAW and Satellite
- **Unlimited guests** — invite anyone
- **Chaos Mode** — anyone can upload audio

### Pricing

| Plan | Price | Features |
|------|-------|----------|
| **Free** | $0 | 30 min/session, viewer-only |
| **Pro** | $9.99/mo | No limits, co-host, VIP, unlimited guests |

### For whom
- Producers working in different DAWs
- Real-time jam sessions
- Recording studios

### Rating
- **Pros:** Works directly inside DAW, cross-platform sync, no stem export needed
- **Cons:** No version control, no cloud, internet required, 30 min limit on free

---

## 11. Kompoz

**Website:** kompoz.com
**Status:** Active since 2007
**Goal:** Music crowdsourcing — find collaborators worldwide

### What it is
Platform for finding musicians worldwide and collaboratively creating tracks. Not a DAW, but networking + project management.

### Key Features
- Find collaborators by instrument, genre, license
- Upload tracks for collaboration
- Integration with SoundBlend (music sales)
- Participant crediting
- Creative Commons and traditional licenses

### Pricing

| Plan | Price | Features |
|------|-------|----------|
| **Starter** | $0 | 3 public + 1 private collaboration/year |
| **Plus** | $5/mo ($49/yr) | More collaborations, FLAC downloads |
| **Premier** | $10/mo | 70+ collaborations/year, 90% royalties |
| **Pro** | $20/mo | Unlimited collaborations |

### Rating
- **Pros:** Large base (200K+ tracks), worldwide search, sales through SoundBlend
- **Cons:** No real-time, no version control, no waveform comments, outdated UI

---

## 12. Other Platforms

- **Splice Sounds** (current Splice) — samples + AI search, $9.99/mo
- **LANDR** — AI mastering, distribution, $9.99/mo
- **SoundBetter** — session musician marketplace
- **JamKazam** — real-time jamming over internet

---

# PART 3: COMPARISON TABLES

---

## By Collaboration Type

| Platform | Async stems | Real-time DAW | Waveform feedback | Version control | Discovery |
|----------|:-----------:|:-------------:|:-----------------:|:---------------:|:---------:|
| **Splice Studio** | ✅ | ❌ | ✅ | ✅ | ❌ |
| **SyncMuse** | ✅ | ❌ | ✅ | ✅ | ❌ |
| **Boombox** | ✅ | ❌ | ✅ | ✅ | ❌ |
| **BandLab** | ✅ | ✅ (up to 50) | ❌ | ✅ | ✅ |
| **Soundtrap** | ✅ | ✅ (up to 30) | ❌ | ✅ | ❌ |
| **Sesh** | ✅ | ✅ (unlimited) | ❌ | ✅ | ❌ |
| **Sessionwire** | ✅ | ✅ (real-time) | ❌ | ❌ | ❌ |
| **Satellite** | ✅ | ✅ (real-time) | ❌ | ❌ | ❌ |
| **Pibox** | ✅ | ❌ | ✅ | ✅ | ❌ |
| **Feedtracks** | ✅ | ❌ | ✅ | ✅ | ❌ |
| **musiciansXchange** | ✅ | ❌ | ✅ | ✅ (Git) | ✅ |
| **Kompoz** | ✅ | ❌ | ❌ | ❌ | ✅ |

---

## By Price (Minimum Paid Plan)

| Platform | Minimum Price | What you get |
|----------|:------------:|-------------|
| **BandLab** | $0 (free) | Full DAW, AI tools |
| **musiciansXchange** | $3.99/mo | 25 GB, unlimited collaborations |
| **Sesh** | $5/mo | Unlimited projects, AI stem splitter |
| **Kompoz** | $5/mo | More collaborations |
| **Boombox** | $4.20/mo | 500 GB, video, AI tools |
| **Feedtracks** | €6.99/mo | 200 GB, unlimited playlists |
| **SyncMuse** | Freemium | Basic features |
| **Soundtrap** | $9.99/mo | Full library, WAV export |
| **Sessionwire** | $9/mo | Private Studio, 1 guest |
| **Satellite** | $9.99/mo | Unlimited sessions |
| **Pibox** | $10/user/mo | 100 GB, unlimited projects |

---

## By DAW Integration

| Platform | DAW-aware | Supported DAWs |
|----------|:---------:|---------------|
| **Splice Studio** | ✅ | Ableton, Logic, FL Studio, GarageBand, Studio One |
| **Sessionwire** | ✅ (plugin) | 15+ DAW via AAX/VST3/AU |
| **Satellite** | ✅ (plugin) | Ableton, Logic, FL Studio, Pro Tools, Cubase, Studio One |
| **musiciansXchange** | ✅ (desktop app) | DAW-agnostic (watch export folders) |
| **Boombox** | Partial (macOS sync) | DAW-agnostic |
| **BandLab** | ✅ (built-in) | BandLab Studio + Cakewalk |
| **Soundtrap** | ✅ (built-in) | Soundtrap Studio |
| **Sesh** | ✅ (built-in) | Sesh DAW |
| **SyncMuse** | ❌ | DAW-agnostic (stems) |
| **Pibox** | ❌ | DAW-agnostic (stems) |
| **Feedtracks** | ❌ | DAW-agnostic (stems) |
| **Kompoz** | ❌ | DAW-agnostic (stems) |

---

## By Education and Reviews

| Platform | App Store Rating | Reviews | Education |
|----------|:----------------:|:-------:|:---------:|
| **BandLab** | 4.7/5 (498K) | ⭐⭐⭐⭐ | ❌ |
| **Soundtrap** | 4.5/5 | ⭐⭐⭐ (bugs) | ✅ (Classroom/School) |
| **Sessionwire** | — | ⭐⭐⭐⭐ | ✅ (Berklee, CRAS) |
| **Pibox** | — | ⭐⭐⭐⭐ | ❌ |
| **Sesh** | — | ⭐⭐⭐ | ❌ |

---

# PART 4: RECOMMENDATIONS AND CONCLUSIONS

---

## Recommendations by Scenario

### "I need a Splice Studio replacement"
→ **SyncMuse** (if versions + waveform feedback matter) or **Boombox** (if you need backup + distribution)

### "I need a free DAW with collaboration"
→ **BandLab** (completely free, 100M+ community) or **Sesh** (if focused on beats)

### "I need a real-time DAW plugin"
→ **Sessionwire** (studio-grade) or **Satellite Sessions** (free 30 min)

### "I need Google Drive for audio with feedback"
→ **Feedtracks** (waveform comments + versions) or **Pibox** (for enterprise teams)

### "I need collaborators worldwide"
→ **musiciansXchange** (discovery + Git versions + auto-credit) or **Kompoz** (200K+ tracks)

### "I need distribution + collaboration"
→ **Boombox** (all-in-one) or **BandLab** (free distribution in Pro)

---

## Market Trends 2024-2026

1. **AI tools** — stem splitting, auto-mix, generation — standard for all platforms
2. **Browser-first** — BandLab, Soundtrap, Sesh proved browser DAWs are ready for serious work
3. **Real-time vs Async** — market split: real-time (BandLab, Soundtrap, Sessionwire) vs async (SyncMuse, Boombox)
4. **Git-like workflow** — musiciansXchange and SyncMuse inspired by Splice Studio
5. **All-in-one** — trend to combine storage + collaboration + distribution (Boombox, BandLab)
6. **Education** — Soundtrap and BandLab actively working with schools and universities

---

## Final Verdict

**Splice Studio** left behind a void that at least 10+ platforms are filling. None replicates it 1:1 — each adds something unique.

**Closest to the original:**
- **SyncMuse** — in spirit and functionality (async + versions + feedback)
- **musiciansXchange** — in concept "GitHub for musicians" (Git branches + discovery)

**Most feature-rich:**
- **BandLab** — most powerful free DAW + AI + social network
- **Boombox** — widest functionality (storage + collab + splits + distribution)

**Most professional:**
- **Sessionwire** — studio-grade real-time DAW sessions
- **Pibox** — enterprise approach to audio review

---

**Summary:** Splice Studio was a revolutionary free tool that brought Git-like workflow to music production. It worked from 2014 to 2023, supported 5 DAWs, offered unlimited storage and DAW-aware version control. Closed due to unprofitability and Splice's focus on samples and plugins. The market is now filled by SyncMuse, Boombox, BandLab, and other platforms trying to fill the gap.

---

# PART 5: SOUNDHUB VS COMPETITORS — FINAL COMPARISON TABLE

> *See [SoundHub_vs_Competitors.md](./SoundHub_vs_Competitors.md) for the complete comparison table.*
> *This section duplicates the content of SoundHub_vs_Competitors.md.*

---

*Generated with Codebuff 🤖*
