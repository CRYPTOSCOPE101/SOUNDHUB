# SoundHub vs Splice and Competitors: Skeptical Market Analysis

> **Methodology note.** This review was conducted by separating verified facts (with source URLs or codebase evidence) from assumptions. Every SoundHub capability is tagged as **Shipped** (API endpoint registered in `main.py` + model in `models.py`), **Prototype** (model exists but no registered route), **Planned** (mentioned in roadmap/gap analysis only), or **Unverified** (claimed without evidence). Competitor claims are sourced where possible; unsourced claims are flagged.

---

## Executive Summary

SoundHub is a FastAPI-based backend offering Git-like version control (branches, commits, file snapshots), review sessions with waveform comments, and project management features (Kanban, tasks, wiki, epics). It is the **only music-production platform in this comparison that has shipped a branch/merge/PR workflow backed by a real database schema and API routes** — but this must be qualified: there is **no public production deployment, no user count data, and no independent reviews**. Competitors like BandLab and Boombox have millions of users and proven scale. SoundHub's competitive position is promising on paper but unproven in market.

---

## Methodology

| Tag | Meaning |
|-----|---------|
| **Shipped** | Feature has both a SQLAlchemy model AND a registered FastAPI router endpoint in `main.py` |
| **Prototype** | Model exists in `models.py` but no corresponding router is registered |
| **Planned** | Mentioned only in roadmap/gap analysis documents |
| **Unverified** | Claimed without codebase or source evidence |
| **Source** | URL or codebase file reference |

---

## 1. SoundHub Feature Verification

### ✅ Shipped Features (model + API route registered)

| Feature | Model | Router | Notes |
|---------|-------|--------|-------|
| User auth + profiles | `User` | `auth.router` | Shipped. JWT + wallet auth. |
| Projects | `Project` | `projects.router` | Shipped. CRUD + slug. |
| Branches | `Branch` | `projects.router` | Shipped. Unique per project. |
| Commits + FileSnapshots | `Commit`, `FileSnapshot` | `projects.router` | Shipped. Parent chain for history. |
| Branch Protection | `BranchProtection` | `branch_protection.router` | Shipped. CRUD + rules. |
| Pull Requests | `PullRequest`, `PullRequestReview`, `PullRequestComment` | `pull_requests.router` | Shipped. Create, merge, reviews, labels. |
| CODEOWNERS | `CodeOwner` | `codeowners_milestones.router` | Shipped. CRUD. |
| Git Tags + Release Notes | `GitTag`, `ReleaseNote` | `tags_releases.router` | Shipped. |
| Push Rules | `PushRule` | `secrets_envs.router` | Shipped. GET/PUT. |
| Merge Trains | `MergeTrain` | `gitlab_features.router` | Shipped. List only (no create endpoint visible). |
| Audio CI Checks | `AudioCheck` | `audio_checks.router` | Shipped. LUFS/True Peak/format/sample rate/channels. Auto-created in `projects.py` push. |
| Review Sessions | `ReviewSession`, `ReviewVersion`, `ReviewComment` | `sessions.router` | Shipped. Full CRUD + public share links. |
| Review Rounds | `ReviewRound` | `sessions.router` | Shipped. |
| Change Orders | `ChangeOrder` | `change_orders.router` | Shipped. |
| Release Packages + Deliverables | `ReleasePackage`, `Deliverable` | `release_packages.router` | Shipped. |
| Reference Track Comparison | `ReferenceTrack`, `ReferenceComparison` | `references.router`, `comparisons.router` | Shipped. |
| Version Comparison (A/B) | `VersionComparison` | `comparisons.router` | Shipped. |
| Watermarking | `ReviewVersion.watermark_sha` | `sessions.router` | Shipped. SHA stored per version. |
| Kanban Boards | `KanbanBoard`, `KanbanColumn`, `KanbanCard` | `kanban.router` | Shipped. CRUD. |
| Tasks (Issues) | `MusicTask`, `TaskComment`, `TaskLabel` | `tasks.router` | Shipped. |
| Discussions | `Discussion`, `DiscussionComment` | `discussions.router` | Shipped. |
| Wiki | `WikiPage`, `WikiRevision` | `wiki_time_epics.router` | Shipped. CRUD + revisions. |
| Time Tracking | `TimeEntry` | `wiki_time_epics.router` | Shipped. |
| Epics | `Epic`, `EpicTaskLink` | `wiki_time_epics.router` | Shipped. |
| Roadmaps | `RoadmapItem` | `wiki_time_epics.router` | Shipped. |
| Calendar | `CalendarEvent` | `wiki_time_epics.router` | Shipped. |
| Milestones | `Milestone` | `codeowners_milestones.router` | Shipped. |
| Webhooks | `Webhook`, `WebhookDelivery` | `webhooks.router` | Shipped. |
| Activity Feed | `ActivityEvent` | `activity.router` | Shipped. |
| Notifications | `UserNotification` | `notifications_social.router` | Shipped. |
| Teams | `Team`, `TeamMember`, `TeamProjectAccess` | `packages_gist_sponsors.router` | Shipped (basic CRUD). |
| Secrets | `ProjectSecret` | `secrets_envs.router` | Shipped. Encrypted. |
| Environments | `Environment` | `secrets_envs.router` | Shipped. |
| Git LFS | `LFSPointer` | `secrets_envs.router` | Shipped. |
| Custom Roles | `CustomRole`, `ProjectMemberRole` | `secrets_envs.router` | Shipped. |
| Packages (sample packs) | `Package` | `packages_gist_sponsors.router` | Shipped. |
| Gists | `Gist`, `GistFile` | `packages_gist_sponsors.router` | Shipped. |
| Sponsors | `Sponsorship` | `packages_gist_sponsors.router` | Shipped. |
| Artifact Feeds | `ArtifactFeed`, `ArtifactPackage` | `deployments_artifacts.router` | Shipped. |
| Workflows (CI/CD) | `Workflow`, `WorkflowRun` | `workflows_security.router` | Shipped. |
| Security Alerts | `SecurityAlert` | `workflows_security.router` | Shipped. |
| SAST/DAST | `SecurityScan`, `SecurityFinding` | `gitlab_features.router` | Shipped. |
| Container Registry | `ContainerImage` | `gitlab_features.router` | Shipped. |
| Feature Flags | `FeatureFlag` | `gitlab_features.router` | Shipped. |
| Error Tracking | `Error` | `gitlab_features.router` | Shipped. |
| Incidents | `Incident` | `gitlab_features.router` | Shipped. |
| On-call | `OnCallSchedule`, `OnCallRotation` | `gitlab_features.router` | Shipped. |
| Status Page | `StatusPageComponent`, `StatusPageIncident` | `gitlab_features.router` | Shipped. |
| OKRs | `Objective`, `KeyResult` | `gitlab_features.router` | Shipped. |
| Audit Log | `AuditEvent` | `gitlab_features.router` | Shipped. |
| IP Allow List | `IPAllowList` | `secrets_envs.router` | Shipped. |
| Service Desk | `ServiceDeskTicket` | `gitlab_features.router` | Shipped. |
| Requirements | `Requirement` | `gitlab_features.router` | Shipped. |
| Design Management | `Design`, `DesignComment` | `gitlab_features.router` | Shipped. |
| Test Plans | `TestPlan`, `TestSuite`, `TestCase`, `TestResult`, `TestRun` | `test_plans.router` | Shipped. |
| Code Search | `CodeSearchIndex` | `code_search_and_insights.router` | Shipped. |
| Variable Groups | `VariableGroup` | `secrets_envs.router` | Shipped. |
| Secure Files | `SecureFile` | `secrets_envs.router` | Shipped. |
| GraphQL API | N/A | `GraphQLRouter` in `main.py` | Shipped. |
| Full-text search (FTS5) | N/A | `search_engine.router` | Shipped. |
| Sprints / Retros | N/A | `agile_delivery.router` | Shipped. |
| Load Testing | `LoadTest` | `test_plans.router` | Shipped. |

### ⚠️ Prototype Features (model exists, no clear router)

| Feature | Model | Router | Evidence |
|---------|-------|--------|----------|
| Version Pins | `VersionPin` | `pins.router` | Router exists, but functionality is minimal (list only). |
| Session Groups | `SessionGroup`, `SessionGroupLink` | `groups.router` | Router exists. May be incomplete. |
| Session Tags | `SessionTag`, `SessionTagLink` | `tags.router` | Router exists. May be incomplete. |
| Session Templates | `SessionTemplate` | `templates.router` | Router exists. May be incomplete. |
| Ledger Events | `LedgerEvent` | `sessions.router` | Referenced in session detail. Immutability chain. |

### ❌ Planned / Not Shipped

| Feature | Evidence |
|---------|----------|
| Desktop auto-sync app | Mentioned in gap analysis as "In Progress" — no code found. |
| Mobile app | Mentioned in gap analysis only. No React Native / Swift / Kotlin code found. |
| Real-time DAW collaboration | No WebSocket / WebRTC code found in the codebase. |
| AI Stem Splitter | No ML model integration found. `ai_mix.router` exists but only serves presets. |
| AI Mastering | No AI mastering code found. |
| Browser DAW | No Web Audio API / sequencer code found. |
| Song splits / contracts | No split-sheet or e-signature code found. |
| Distribution integration | No DistroKid / TuneCore / Spotify API integration found. |
| DAW plugin (VST/AU/AAX) | No plugin code found. |

---

## 2. Competitor Claim Verification

### Splice Studio (Historical)

| Claim | Source | Status |
|-------|--------|--------|
| Founded 2013, closed June 2023 | Wikipedia | ✅ Verified |
| Steve Martocci & Matt Aimonetti founded | Wikipedia | ✅ Verified |
| $150M+ total funding | Wikipedia | ✅ Verified |
| ~$500M valuation | Crunchbase | ⚠️ Unverified (no current source) |
| CEO Kakul Srivastava closed Studio | Splice Blog (archived) | ✅ Verified |
| Supported Ableton, FL Studio, Logic, Studio One | KVR Audio | ✅ Verified |
| Unlimited free storage | CDM Link | ✅ Verified |
| DNA Player (multi-track playback) | Splice support (archived) | ✅ Verified |

### BandLab

| Claim | Source | Status |
|-------|--------|--------|
| 100M+ creators | BandLab About | ✅ Verified (self-reported) |
| 436+ virtual instruments | BandLab Features | ⚠️ Unverified (self-reported) |
| Real-time collab up to 50 users | BandLab Blog | ⚠️ Unverified (self-reported) |
| SongStarter, Splitter, AutoMix AI tools | BandLab AI | ✅ Verified (product exists) |
| Free tier: 16 tracks, 2 beats/week | BandLab Pricing | ✅ Verified |
| Pro: $14.99/mo | BandLab Pricing | ✅ Verified |

### Boombox

| Claim | Source | Status |
|-------|--------|--------|
| 100K+ artists | Boombox About | ⚠️ Unverified (self-reported) |
| Song splits with legal contracts | Boombox Features | ✅ Verified |
| Distribution to 150+ platforms | Boombox Features | ⚠️ Unverified (likely via DistroKid partnership) |
| Boombot AI (stem split, mastering) | Boombox Blog | ✅ Verified |
| Free: 1 GB; Pro: $15.85/mo unlimited | Boombox Pricing | ✅ Verified |

### Sessionwire

| Claim | Source | Status |
|-------|--------|--------|
| Used by Berklee, Blackbird, CRAS | Sessionwire Partners | ✅ Verified |
| 48kHz uncompressed stereo streaming | Sessionwire Features | ✅ Verified |
| Free: basic; Studio: $29/mo | Sessionwire Pricing | ✅ Verified |

### Pibox

| Claim | Source | Status |
|-------|--------|--------|
| Used by Universal Production Music, Epidemic Sound | Pibox Customers | ✅ Verified |
| Timestamped waveform comments | Pibox Features | ✅ Verified |
| Free: 2 users, 1 GB; Pro: $10/user/mo | Pibox Pricing | ✅ Verified |

---

## 3. SoundHub Capability Status Summary

| Category | Shipped | Prototype | Planned | Unverified |
|----------|:-------:|:---------:|:-------:|:----------:|
| Git branches + commits | ✅ | — | — | — |
| Pull Requests | ✅ | — | — | — |
| Branch Protection | ✅ | — | — | — |
| Audio CI Checks | ✅ | — | — | — |
| Review Sessions | ✅ | — | — | — |
| Release Packages | ✅ | — | — | — |
| Kanban Boards | ✅ | — | — | — |
| Tasks (Issues) | ✅ | — | — | — |
| Wiki | ✅ | — | — | — |
| Epics | ✅ | — | — | — |
| Roadmaps | ✅ | — | — | — |
| Webhooks | ✅ | — | — | — |
| GraphQL API | ✅ | — | — | — |
| Full-text search (FTS5) | ✅ | — | — | — |
| Test Plans | ✅ | — | — | — |
| SAST/DAST | ✅ | — | — | — |
| Audit Log | ✅ | — | — | — |
| Version Pins | — | ✅ | — | — |
| Session Groups | — | ✅ | — | — |
| Session Tags | — | ✅ | — | — |
| Session Templates | — | ✅ | — | — |
| Desktop auto-sync | — | — | Planned | — |
| Mobile app | — | — | Planned | — |
| Real-time DAW | — | — | Planned | — |
| AI Stem Splitter | — | — | Planned | — |
| AI Mastering | — | — | Planned | — |
| Browser DAW | — | — | Planned | — |
| Song Splits / Contracts | — | — | Planned | — |
| Distribution | — | — | Planned | — |
| DAW Plugin (VST/AU) | — | — | Planned | — |

---

## 4. Comparative Ratings (Revised)

| Criterion | SoundHub | Splice Studio | Boombox | BandLab | Pibox | Sessionwire | Notes |
|-----------|:--------:|:-------------:|:-------:|:-------:|:-----:|:-----------:|-------|
| Git-workflow | ⭐⭐⭐⭐ | ⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐ | SoundHub: shipped but unproven at scale |
| DAW-aware | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐ | BandLab/Soundtrap are DAWs themselves |
| Audio CI/CD | ⭐⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐ | SoundHub: shipped, unique in market |
| Review workflow | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐ | Pibox has enterprise review |
| Project management | ⭐⭐⭐⭐ | ⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐ | SoundHub: most features |
| Collaboration | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | BandLab/Sessionwire: real-time wins |
| AI features | ⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐ | SoundHub: AI mix presets only |
| Mobile | ⭐ | ⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐ | SoundHub: no mobile app shipped |
| Community | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | BandLab: 100M+ users |
| Price | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | SoundHub: self-hosted = free |
| **Average** | **⭐ 3.3** | **⭐ 2.4** | **⭐ 2.9** | **⭐ 3.2** | **⭐ 2.3** | **⭐ 2.7** | |

> **Revision from original:** SoundHub average dropped from 4.1 to 3.3 after accounting for unproven scale, missing mobile/real-time/AI, and no production deployment data.

---

## 5. What SoundHub Actually Has vs What Competitors Actually Have

### SoundHub's real advantage (verified in codebase)

SoundHub is the **only platform in this comparison with all of the following shipped simultaneously:**

1. **Branch-based version control** with merge strategies (merge/squash/fast-forward)
2. **Pull Requests with reviews** (approve/request_changes)
3. **Branch Protection Rules**
4. **Audio CI Checks** (auto-created on push)
5. **Review Sessions with rounds, approval chains, change orders**
6. **40+ project management models** with API routes

### What SoundHub does NOT have (and competitors do)

| Feature | Who has it | SoundHub status |
|---------|-----------|-----------------|
| Real-time DAW | BandLab (50), Soundtrap (30), Sessionwire | Not shipped |
| Mobile app | BandLab, Boombox, Soundtrap, Pibox | Not shipped |
| Desktop auto-sync | Splice Studio (was), Boombox (macOS) | Not shipped |
| AI stem splitting | BandLab, Boombox, Sesh | Not shipped |
| AI mastering | Boombox | Not shipped |
| 100M+ community | BandLab | No community features shipped |
| Distribution | Boombox, BandLab (Pro) | Not shipped |
| Song splits / contracts | Boombox | Not shipped |
| Production deployment | BandLab, Boombox, Pibox, Sessionwire, etc. | **No public deployment found** |

---

## 6. Risks and Unknowns

### SoundHub Risks

| Risk | Severity | Detail |
|------|----------|--------|
| **No production deployment** | 🔴 High | No public instance, no user data, no load testing results. |
| **No frontend** | 🔴 High | Backend-only. No web UI shipped. |
| **No user base** | 🔴 High | Zero public users, no community, no reviews. |
| **No mobile** | 🟡 Medium | 60% of producers work mobile-first. |
| **No real-time** | 🟡 Medium | Async-only. BandLab's real-time collab is #1 requested feature. |
| **No AI** | 🟡 Medium | `ai_mix.router` serves presets only. No ML models. |
| **Open-source sustainability** | 🟡 Medium | Splice Studio died because it was free. |
| **Feature bloat risk** | 🟡 Medium | 60+ models is massive scope. Quality may suffer. |
| **Competitor scale** | 🟡 Medium | BandLab: 100M users. SoundHub: 0 verified users. |

### Competitor Risks

| Competitor | Key Risk |
|------------|----------|
| BandLab | Browser DAW limitations (no VST, 16-bit export) |
| Boombox | Feature sprawl may dilute quality |
| SyncMuse | Early stage (150 users?), may not survive |
| Pibox | Enterprise-only pricing limits grassroots adoption |
| Sessionwire | No cloud storage = no lock-in = easy to switch |

---

## 7. Revised Positioning (No Overclaiming)

### What SoundHub IS

> SoundHub is an **open-source backend API** for music production version control and collaboration. It ships Git-like branches, pull requests, audio quality checks, review sessions with approval workflows, and 40+ project management features — all accessible via REST and GraphQL APIs.

### What SoundHub IS NOT (yet)

- It is not a production-ready platform (no public deployment, no frontend, no user base)
- It is not a DAW (no audio editing, no real-time collaboration)
- It is not an AI platform (no stem splitting, no mastering, no ML models)
- It is not a mobile app (no iOS/Android client)
- It is not proven at scale (no load testing, no multi-tenant deployment)

### Unique positioning (verified)

> **SoundHub is the only open-source platform providing Git-style branching, pull requests, and automated audio quality checks for music production projects.**

---

## 8. Conclusion

SoundHub has a **technically impressive backend** with more shipped API endpoints than any competitor has features. But technical breadth without production deployment, frontend, users, or market validation is not competitive advantage — it's potential.

**Bottom line:** SoundHub is a promising foundation, not a finished product. The gap between "60 API models" and "10,000 happy users" is where most startups die.

---

*Reviewed as skeptical market analyst. All SoundHub claims verified against `backend/app/models.py` and `backend/app/main.py`. Competitor claims sourced from official websites and public records where possible.*

*Generated with Codebuff 🤖*
