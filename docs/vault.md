# Obsidian vault

> **Class:** reference · **Status:** living · **Reviewed:** 2026-09-26

The one place that says how Content Machine uses an Obsidian vault: where it reads facts
from, what it writes back, and which files are safe to edit by hand. Everything here is a
no-op when `OBSIDIAN_VAULT_PATH` is unset. Decisions behind it: [decisions.md](decisions.md)
§4 (operator facts are ground truth), §17b (the vault mirrors machine state), §27 and §34
(link lines are not operator facts).

## Setup

- Set `OBSIDIAN_VAULT_PATH` in `.env` to the vault folder (see [../.env.example](../.env.example)).
- Notes are scoped to a channel by a channel-named subfolder or frontmatter `channel: tapin`.
- Tag a note `tags: [facts]` to keep it evergreen for that channel.
- Starter notes: [vault_templates/](vault_templates/) (`_operator_facts.md`, `_sources.md`,
  `_strategy.md`), checked by `tests/test_vault_templates.py`.

## Layout

Everything a channel owns lives under `<vault>/<channel>/`.

| Path | Written by | Read back as facts? | Hand-edit? |
|---|---|---|---|
| `_operator_facts/<date>_<slug>.md` | the key-facts prompt: lines you **typed** (`tier: operator`) | yes, top tier | yes |
| `_link_facts/<date>_<slug>.md` | the key-facts prompt: lines scraped from a **pasted URL** (`tier: link`, since 2026-09-26) | yes, below operator | yes |
| `_ingest/<date>_<slug>.md` | `py -m scripts.ops ingest <url/pdf/youtube>` (`tier: link`, `source:` url) | yes | yes |
| `_sources.md` | pasted-link titles and web-search result URLs, append-only | yes, link tier | append only |
| `_strategy.md` | you | playbook guidance, never facts | yes |
| `_machine-beliefs.md` | `ops vault-sync` (what the analytics believe) | playbook only | no - overwritten |
| `_runs/<run_id>_<slug>.md` | `_finalize_run`, refreshed by `ops vault-sync` | never (machine record) | no - upserted by run id |
| `_reports/<date>_<kind>.md` | weekly report, `ops digest` | never (machine record) | no |

Any other note in the channel folder is read as `tier: vault` unless its frontmatter
declares a tier. Before 2026-09-26 scraped link lines were saved under `_operator_facts/` as
operator tier; those notes are not migrated, but a borrowed vault line never pins in the
prompt any more (§34). Backlog #857 proposes a dry-run re-tier.

## Tiers

Each fact carries a provenance tier (`core/fact_store.py` `TIER_WEIGHTS`). The weight is how
much a line can lend to grounding a claim.

| Tier | Where it comes from | Weight |
|---|---|---|
| operator | a line you typed this run or saved under `_operator_facts/` | 1.0 |
| link | a line scraped from a pasted URL or an ingest | 0.85 |
| web | live web search results | 0.6 |
| signal | structured API data (RAWG, sports APIs, finance) | 0.55 |
| vault | any other vault note | 0.5 |
| brief | the LLM research brief | 0.4 |
| context | YouTube titles and popularity data - never evidence | 0.0 |

Only lines typed this run are pinned ahead of everything else in the prompt.

## How a run reads the vault

1. You add facts at the key-facts prompt (typed lines, pasted blocks, URLs).
2. Pasted-link lines with no contact with the angle, topic or signal evidence are listed;
   Enter drops them, `k` keeps them (`FACT_OFF_TOPIC_FILTER`).
3. The vault scan scores every candidate bullet (`core/vault_relevance.py`, weights and
   thresholds in `config/vault_relevance.json`): entity and cosine support against the
   signal evidence and your facts, franchise-anchor alignment, and a small tier term.
   Popularity data (Twitch, Trends, Wikipedia pageviews, autocomplete) is excluded from that
   evidence since run 98.
4. **Confident** bullets attach automatically (`VAULT_FACTS_AUTO=true`); **uncertain** ones are
   listed with their reasons and you choose (`Enter=all / n=none / 2,5`).
5. Selection ranks everything against the budget (`MAX_OPERATOR_KEY_FACTS`,
   `OPERATOR_KEY_FACT_CHAR_BUDGET`); what did not fit is still saved.
6. New typed lines go to `_operator_facts/`, new link lines to `_link_facts/` - never the
   borrowed vault lines, which would re-title another topic's facts as this one's.

Settings: `VAULT_RELEVANCE_MODE` (`scored` default), `VAULT_RELEVANCE_TIEBREAK` (optional LLM
tiebreak, off), `LINK_FACT_MAX_LINES`, `LINK_READER_PROXY`.

## Ops verbs

| Command | What it does |
|---|---|
| `py -m scripts.ops vault-sync` | writes `_machine-beliefs.md` and refreshes run dossiers |
| `py -m scripts.ops vault-eval` | subject-relevance precision/recall on the holdout set |
| `py -m scripts.ops vault-decay` | lists notes whose `expires:` date has passed |
| `py -m scripts.ops ingest <url>` | saves a URL, PDF or YouTube link as an `_ingest/` note |
| `py -m scripts.ops dossier --run-id N` | one run end to end |
| `py -m scripts.ops digest` | this week's three decisions, written to `_reports/` |
| `py -m scripts.ops moat-backup` | plans a vault + database + traces backup (dry run) |

## What not to do

- Do not hand-edit `_runs/`, `_reports/` or `_machine-beliefs.md`; the next sync overwrites them.
- Do not copy a borrowed bullet into another topic's `_operator_facts/` note: it will match
  that topic strongly forever (the laundering loop recorded in `core/ui.py`).
- Do not point tests at a real vault. Tests patch `core.obsidian_facts._vault_path` to a temp dir.

## Open

Backlog items that touch the vault: #857 re-tier old link-derived notes, #848 auto-research
(would add web-tier lines, never operator), #555 vault deduplication, #216 dossier reader,
#834 a `core/vault/` sub-package, #156 Vault Companion. The desktop "facts room" proposal is in
[desktop_app.md](desktop_app.md).
