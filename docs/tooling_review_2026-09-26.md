# Tooling review — 2026-09-26

> **Class:** snapshot · **Status:** frozen · **Reviewed:** 2026-09-26

Aimed at the gaps run 98 exposed, not a general survey. The last external-repo evaluation was
the 2026-08-25 addendum in [tooling_landscape.md](tooling_landscape.md); what shipped from it
is in [tool_integration_plan.md](tool_integration_plan.md). Every entry below was checked
against its PyPI page or repository on 2026-09-26. Anything that could not be checked says so.
Nothing here is adopted; each row names the backlog item that would adopt it.

## Gap 1 — pages the link reader cannot read

Run 98: premierleague.com/en/stats rendered with JavaScript and gave only its title and
meta description; nytimes.com/athletic returned HTTP 403. Today's stack is goose3 (main text),
a BeautifulSoup `<p>` fallback, and the opt-in `LINK_READER_PROXY` (r.jina.ai, third-party).

| Tool | Checked | Licence | Fit |
|---|---|---|---|
| goose3 (in use) | 3.1.22, 2026-07-23 | Apache-2.0 | keep; `pyproject.toml` pins `>=3.1.19` |
| trafilatura | 2.2.0, 2026-07-31 | Apache-2.0 (GPL before 1.8.0) | best-known main-text extractor; worth a second-extractor slot when goose3 returns nothing |
| newspaper4k | 0.9.6, 2026-07-19 | MIT | article + metadata extractor; overlaps goose3 - pick one of it or trafilatura, not both |
| jina-ai/reader | repository active, Docker image `ghcr.io/jina-ai/reader:oss` | Apache-2.0 | the service behind today's proxy, **self-hostable**: points `LINK_READER_PROXY` at a local instance and keeps the self-hosted-first default |
| Playwright for Python | 1.63.0, 2026-09-15 | Apache-2.0 | real browser rendering; heavy (a Chromium download) but local |
| Crawl4AI | 0.9.4, 2026-09-23 | Apache-2.0 | crawler built on Playwright with LLM-ready output; more than a single-page reader needs |

**Recommendation.** Measure before adopting. The operator's own pasted links are the test set:
run each extractor over run 98's six URLs plus the last ten runs' links, and count body lines
kept and junk lines admitted. If a second extractor wins on JS pages, adopt **one**
(trafilatura) as the fallback inside `link_facts._article_extract`. For paywalled and
bot-blocked pages the honest answer stays "paste the text" - no extractor fixes a 403.
Filed as part of #848, which reads pages the pipeline finds itself.

## Gap 2 — football data (TapIn's new domain)

Football became TapIn's on 2026-09-26 (decisions §34). The `sports` group already has
`api_sports` (API-SPORTS, `v3.football.api-sports.io`, keyed), but its team search takes the
raw 48-character topic (#852).

| Source | Checked | Licence / terms | Fit |
|---|---|---|---|
| API-SPORTS (in use) | integrated, `API_SPORTS_KEY` | commercial API, free tier | fix the query first (#852); cheapest win |
| soccerdata (probberechts/soccerdata) | repository active | Apache-2.0 code; scrapes Club Elo, ESPN, FBref, Football-Data.co.uk, Sofascore, SoFIFA, Understat, WhoScored | rich stats, but each source has its own terms; scraping belongs behind the same caution as the retired Apify scrapers |
| football-data.org | **not checked** - blocked by this environment's network proxy | - | verify on the operator's box before considering |
| RSS: no soccer feed is configured | `config/data_sources.json` `domain_rss` has none | - | add two soccer feeds the operator trusts (#859) |

## Gap 3 — the vault as an interface

| Tool | Checked | Licence | Fit |
|---|---|---|---|
| obsidian-local-rest-api (coddingtonbear) | repository active | MIT | a REST API **and MCP server** into a running Obsidian: read, write, search notes. The pipeline does not need it (it reads files directly), but a desktop "facts room" or an agent reviewing the vault could use it instead of file access |

## What this review rejects

- **Adding more signals.** [engine_upgrades.md](engine_upgrades.md) §5 still holds: steam and
  igdb returned something on 1 of 33 runs (#854 retires them).
- **Crawl4AI as the default reader.** A crawler for a single pasted page is weight without gain.
- **Any scraper of a paywalled site.** The Athletic's 403 is the site's answer.
