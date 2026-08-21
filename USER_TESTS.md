# User Tests — First 3 Sessions, Then Fixes

Goal: **see how a real person completes the journey without hints**, and collect verbatim quotes — they will become interface texts, onboarding, and email templates. We don't add features until we fix the top 3 pain points from tests.

## Participants (3 tests)

- **2 mix/master engineers** — one primarily Ableton, the other doesn't matter.
- **1 client/artist who doesn't work in DAW** (important: non-technical).
- Ideally a fourth: person with a small label / A&R (if available).

## Tasks — each has their own, not the full journey for everyone

| Participant | Task (mandatory) |
|---|---|
| **Engineer** | **Main web-flow:** create session from brief → send link → view draft feedback / consolidated round → upload new version **via UI** → compare v12/v13 → build package and run QC → request approval |
| **Client / artist** | Open public link **from phone** → leave structured note + voice note → compare two versions → send feedback → approve |
| **A&R / label** | View version history → perform approval **using their role** (set up/use approval chain) → check delivery package and payment/delivery flow |

### CLI — only for the engineer who truly lives in the terminal

CLI **is not required** in the first test — don't mix two problems (review workflow clarity and dev/DAW bridge comfort). If the engineer regularly works in the terminal — give an additional scenario:

```bash
soundhub requests --session "Neon Warehouse" --format csv
soundhub locator --session "Neon Warehouse"
soundhub push mix.wav --session "Neon Warehouse" --message "v14: kick revised"
```

Then ask separately:
> "At what point in your real DAW workflow would you run this command?"

The answer will show: whether CLI is needed as a standalone product or only as a foundation for a future Max for Live bridge.

## How to Conduct

1. **Don't explain the interface beforehand.** The opening phrase is one:
   > "Imagine this is your current project. Do what you'd normally do."
2. Answer only guiding: "look at the page", "try clicking" — without describing steps.
3. Record the screen where the participant got stuck, and their **verbatim** quotes.

## What to Record — Verbatim Quotes

Catch literally (these are ready-made texts for UI/onboarding/email):

- "I didn't understand what this is..."
- "I'd expect a button here..."
- "I'm scared to click Approve because..."
- "I can't see what changed..."
- "I'd still send this on WhatsApp because..."

## Landing Page Checklist (show before/after first screen)

1. After 10–15 seconds of viewing, ask: **"What is this product and who needs it?"** The correct answer is approximately: "A review, versioning, and approval system for music projects — for engineers, artists, and A&R." If the answer is "preset store / crypto sound store" — the marketplace on the landing page takes up too much space.
2. **"Max for Live panel prototype"** next to `WAV, MP3 & stems` — ask the non-Ableton user: is it clear what already works and what's a prototype?
3. **Marketplace** — is it perceived as the main feature? (Check top navigation and footer: Marketplace/DAO links may give a first impression of "crypto store.")
4. **Roadmap (4 columns)** — do people even reach it, and does it influence their decision to try a demo?

If 2 out of 3 name marketplace as the main feature: halve the marketplace block, remove "escrow protected" and "License bound on-chain" from the landing page into docs/marketplace, replace the Marketplace CTA in top navigation with "How it works" / "Open review", leave marketplace as one compact section after workflow.

## Metrics

| Metric | How to Measure |
|--------|---------------|
| Time to first feedback | From opening link to first comment/voice note |
| % who sent consolidated notes | Submit round without reminder |
| Number of revision rounds | How many rounds until approval |
| % approvals without manual reminders | Approve without pinging the engineer |
| Time-to-payment | From invoice to checkout payment |
| Where they asked for help | List of screens/actions |

## Report Form After Each Test

```markdown
## Test #N — <participant role>, <DAW/none>, <date>

### Verbatim Quotes
> "..."
> "..."

### Where They Had to Explain / Didn't Understand Where to Click
-

### Roles / Approval
-

### What They Called "Important"
-

### What They "Didn't Notice" (features they didn't find on their own)
-

### Metrics
- time-to-first-feedback:
- consolidated notes sent:
- rounds to approval:
- approval without reminders:
- time-to-payment:
- asked for help (screens):

### Landing Page
- Understood "what SoundHub is for"? (verbatim answer)
- Max for Live prototype clear?
- Marketplace perceived as main feature?
- Read roadmap? Influences decision?

### Verdict: completed alone / with hints / did not complete
```

## After 3 Reports — Summary Table

Consolidate all reports into a table:

| Pain / Quote | Role | Frequency | Interface Point | Fix |
|---|---|---:|---|---|
| "Scared to click Approve" | Client | 2/3 | Approval | Confirmation with clear scope |
| "Can't see where to upload v2" | Engineer | 2/3 | Versions | Primary CTA "Upload new version" |
| "I'd reply on WhatsApp" | Artist | 1/3 | Public review | Shareable comment link / email notification |

**Fix rule:** only fix items that recur with **2+ people** or completely block a scenario. This protects against features for a single opinion.

Order: engineer onboarding → public review page → approval copy → pricing / landing narrative. Only after: USDC, Max for Live review comments, REAPER.

## What We're NOT Testing or Building Now

- USDC checkout, mainnet proofs, DAO, NFT licenses, marketplace expansion — until real users pay for the current workflow.
