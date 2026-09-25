# External Sources Review — Candidate Implementations (2026-06-25)

> **Class:** snapshot · **Status:** frozen · **Reviewed:** 2026-09-25

**Planning only. This is a candidate list for confirmation — nothing is added to the
roadmap yet.** Reviewed the supplied links for ideas *not already in the project*,
split into **Product** (YouTube automation) and **Dev Workflow** (Claude Code, for
this repo). After you confirm a subset, I'll fold those into
[roadmap.md](roadmap.md) / set them up (still doc + config only).

### Provenance / honesty
Most links were **blocked at the network proxy** and could not be read directly:
- ✅ Fetched: `github.com/ykdojo/claude-code-tips`.
- ⛔ Blocked (403 / proxy): all `reddit.com` threads, the Medium guide, the Substack
  "30 tips", `artificialcorner.com`.
- Substance for the blocked items was **recovered via web search + domain knowledge**,
  not the original posts — so treat those as *representative*, not verbatim quotes.
Sources used: [ykdojo/claude-code-tips](https://github.com/ykdojo/claude-code-tips),
[KDnuggets — reduce token usage](https://www.kdnuggets.com/7-practical-ways-to-reduce-claude-code-token-usage),
[Claude Code cost docs](https://code.claude.com/docs/en/costs),
[virvid faceless stack 2026](https://virvid.ai/blog/ai-faceless-youtube-automation-stack-2026),
[fluxnote faceless workflow](https://fluxnote.io/guides/faceless-youtube-automation-with-ai).

---

## Part 1 — Product (AI YouTube automation)

**Headline finding (worth stating):** these guides mostly **confirm** what the
machine already does — and in several areas the machine is **ahead** of them
(closed analytics loop, anti-hallucination grounding, the 2026 authenticity layer).
The generic stacks (ChatGPT + ElevenLabs + a video tool + VidIQ) are a *subset* of
this project. So the genuinely-new product items are few and small:

| ID | Candidate | Source theme | Status in project | Effort |
|---|---|---|---|---|
| **P1** | **Batch production** — N ideas → N publish-ready drafts in one unattended pass | "batch 5–10 per session" is the #1 faceless-efficiency tactic | **Roadmapped but deferred** (Efficiency §"Batch generation") — *promote/prioritize* | `[M]` |
| **P2** | **Title click-pattern rule** — front-load the primary keyword + optional bracketed hook `[...]`, scored | "front-load keyword, bracket for click signal" | Partial — `title_features`/A-B loop exist; add the explicit pattern as a rule | `[S]` |
| **P3** | **Description SEO shape** — first 100 chars keyword-dense, then summary + **timestamps/chapters** + source links | "first 100 chars critical; timestamps; source links" | Partial — description gen exists; citation footer already brainstormed (B5) | `[S]` |
| **P4** | **Thumbnail A/B → CTR** | "high-contrast clickable thumbnails", testing | **Roadmapped** (Phase S, deferred) — note only | `[M]` |
| **P5** | **Dedicated SEO/tag research** (VidIQ/TubeBuddy-style) | tag tools | **Already covered** — `config/seo/`, `analytics.seo_refresh` | n/a |

> Net: confirm **P1 (promote batch generation)** is the real product takeaway; **P2/P3**
> are cheap polish. P4/P5 are already tracked/owned. Everything else in the guides the
> machine already does or exceeds — itself a useful validation of positioning.

---

## Part 2 — Dev Workflow (Claude Code) — where most of the new value is

This repo currently has **no `CLAUDE.md`**, and `.claude/` holds only
`settings.local.json` (no commands, no hooks, no shared settings). The workflow/token
sources converge on a setup this repo hasn't adopted — high leverage because it
improves **every** future session (accuracy + token cost), and it's doc/config only.

| ID | Candidate | Source | Why it helps here | Effort |
|---|---|---|---|---|
| **D1** | **Root `CLAUDE.md`** (project memory) | All tip lists; token threads (a stable CLAUDE.md cuts repeated prompt overhead) | Encodes: run tests/lint/typecheck, the **ruff 0.8.4-pinned** caveat (0.15 drifts), module map, "don't touch `data/`/`output/`", env-flag truthy convention, commit/branch rules. Stops every session re-deriving this. | `[S]` |
| **D2** | **Custom slash commands** in `.claude/commands/` | ykdojo (skills vs slash commands); Substack | Project verbs: `/quality-check` (ruff+format+tests), `/intel-report`, `/new-channel`, `/release`, `/spec`. Repeatable, low-token. | `[S–M]` |
| **D3** | **Committed `.claude/settings.json` hooks** | ykdojo (hooks); cost docs | PostToolUse: `ruff format` on edited files; Stop: quick lint. Keeps the tree clean without manual nagging. | `[S]` |
| **D4** | **SessionStart hook** (the `session-start-hook` skill exists) | ykdojo; cost docs | Cloud/web sessions auto-install deps + verify tests/linters — directly addresses "**suite won't run in a fresh env**" (audit E4 / ESB #5). | `[S–M]` |
| **D5** | **Shared permissions allowlist** in `settings.json` | ykdojo (auto-mode); `fewer-permission-prompts` skill | Allowlist safe read-only commands (ruff, pytest, git status) → fewer approval prompts, less round-trip token. | `[S]` |
| **D6** | **`docs/claude_workflow.md`** — token/working agreement | KDnuggets/cost docs; token threads | Documents the practices the threads stress: **plan-mode first**, **Sonnet-default / Opus only for deep work** (up to ~75% cost cut), `/clear` between unrelated tasks, `/compact` before long runs, **subagents for verbose output**, **scope prompts to named files** (don't "look around the repo"). A standing convention, not code. | `[S]` |
| **D7** | **`.github/` hygiene** — PR template + `dependabot.yml` + `CODEOWNERS` | ykdojo (GitHub integration); general | PR template standardizes reviews; Dependabot automates dep/security bumps (complements ESB #6/#8). | `[S]` |
| **D8** | **Headless Claude in CI** (`claude -p …`) | ykdojo (`/gha`, GH Actions debugging) | Optional: auto-draft changelog entries, triage CI failures. Lower priority; revisit after D1–D5. | `[M]` |

---

## Recommended subset (my ranking, for your confirm)

**Do-first (cheap, compounding, helps every session):**
1. **D1 `CLAUDE.md`** — highest leverage; also the single biggest token saver.
2. **D6 `claude_workflow.md`** — the working agreement; zero risk.
3. **D4 SessionStart hook** — fixes the recurring "can't run tests here" pain.
4. **D2 slash commands** (`/quality-check` first) + **D5 permissions allowlist**.

**Product:**
5. **P1 promote batch generation** out of "deferred" — the one substantive product
   idea the guides surface; pairs with the A/B + variation work already planned.
6. **P2 / P3** title+description SEO polish — small, do alongside the quality fixes.

**Track but don't start:** D3, D7, D8, P4 (note overlaps with ESB / roadmap).

---

## Next step
Reply with the IDs you want (e.g. "D1, D6, D4, P1"). On confirmation I will, **still
docs/config only**:
- fold the confirmed **product** items into [roadmap.md](roadmap.md) (and mark P1 as
  promoted from deferred), and
- draft the confirmed **dev-workflow** artifacts (`CLAUDE.md`,
  `docs/claude_workflow.md`, `.claude/commands/*`, hook config) as files for review.
Nothing executes against the pipeline; no runtime code changes.
