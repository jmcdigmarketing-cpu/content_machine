# Cloud brief — wave 136: money and reach outside YouTube

> **Class:** plan · **Status:** living · **Reviewed:** 2026-10-28

Money before the Partner Program ([bridge_plan.md](bridge_plan.md), decision 82). The operator
chose three routes: affiliate links, a Facebook Reels crosspost, and TikTok Creator Rewards as a
long-run target. Wave 133 already builds the affiliate links on long-form (#1747, #1748). This wave
adds:
- Facebook as a third crosspost;
- a link-in-bio page;
- income recorded beside spend;
- TikTok cuts that can earn;
- every Short crossposted within the hour.

Today TikTok has 22 posts (2,075 views, ~3 s watched) and Instagram 22 posts (2,304 views).
Facebook is not wired: `publishing/crosspost.PLATFORMS = ("tiktok", "instagram")`. It is planned
for W6 (Nov 30-Dec 6) in [bridge_calendar.md](bridge_calendar.md).

**The operator's sign-ups come first:** a Facebook Page connected in Buffer, and the Amazon
Associates tag. **The cloud has no `data/`, `output/`, database or keys.**

## Start here - the prompt to paste into the cloud session

```text
You are Claude Code in a cloud session on content_machine. Build wave 136: money and reach.
1. git pull. Read docs/handoff.md (both slots), then docs/cloud_brief_wave136.md in full. Each
   item's backlog line in docs/backlog.md is its source (numbers below).
2. next-five skill and tdd: each new test fails first; say how many. Tests in tests/test_wave136.py.
3. Fixtures only - no Buffer, Meta or TikTok call; list the LOCAL checks in your handoff slot.
4. Done: ruff check . ; ruff format --check . ; python scripts/mypy_ratchet.py (92 or fewer) ;
   python -m unittest discover -s tests -t . -v ; python -m scripts.ops test --order reverse.
5. Commit (ASCII body) with your Co-Authored-By trailer, push, read CI; docs in the skill's order,
   your handoff slot last. Nothing outward: no post, no Page, no account.
```

## Ground rules

As in [cloud_brief_wave132.md](cloud_brief_wave132.md#ground-rules-for-this-wave). Buffer's API is
faked in tests with the request shapes `publishing/buffer_api.py` already builds. A new env key goes
in `.env.example` (CRLF), with its suite value in `tests/__init__.py`.

## The wave, in build order

### 1. #1754 B07.8 + #1755 B07.9 - Facebook Reels through Buffer

**Build.**
- `publishing/crosspost.py`: `PLATFORMS` gains `"facebook"`, with `_LABEL` "Facebook" and
  `_CHANNEL_ENV` `BUFFER_FACEBOOK_CHANNEL_ID`. The latter goes in `.env.example`; the suite value
  is `""`.
- `publishing/buffer_api.py`: the Facebook post's metadata, a Reel, set the way Instagram's is
  (`{"instagram": {"type": "reel", ...}}`). The exact field names are from Buffer's API docs -
  LOCAL, checked once on the PC.
- `publishing/platform_metrics.py` reads Facebook rows like Instagram's.
- With no channel id set, nothing is posted, and the crosspost line says "Facebook: not
  connected".

**Fixture:**

| `BUFFER_FACEBOOK_CHANNEL_ID` | the Short | result |
|---|---|---|
| `fb123` | public, 45 s | one Buffer request built for service facebook, carrying the Reel metadata |
| unset | public, 45 s | none; the status line names it |

### 2. #1772 B08.1 - every public Short crossposted within the hour

**Build.**
- The worker's crosspost pass (`_crosspost_scheduled_live`) counts each public Short with no post
  on a connected platform an hour after it went public, and sends it.
- The weekly report gives the misses: per platform, the number and why (not connected, too long
  for Instagram, a Buffer error).

**Fixture:** three public Shorts. One is posted to both platforms; one is posted to TikTok only,
70 minutes ago; one is 95 s long, over Instagram's limit. The pass sends the second's Instagram
post, and the report reads "Instagram: 1 sent late, 1 too long".

### 3. #1750 B07.4 - a link-in-bio page

**Build.**
- `publishing/policy_site.build_policy_site` also writes `links.html` into the same folder. It holds
  this week's long video, the affiliate links of `config/affiliates.json` (with the FTC line), and
  the channel link.
- The operator hosts it with the policy pages (GitHub Pages, Cloudflare Pages or Netlify, per
  `docs/platform_publish_setup.md`), and the bios point to it.

**Fixture:** a map with one GTA 6 link and a long video "GTA 6 - everything we know" gives a page
containing both, the FTC sentence, and no personal data beyond what the policy pages already show.

### 4. #1753 B07.7 - income beside spend

**Build.**
- `core/money/ledger` gains income entries: `add_income(amount, source, on)`, stored beside the
  spend rows.
- `ops spend income --amount 3.12 --what "Amazon Associates, November"` adds one.
- `ops spend` and the scoreboard (wave 134, #1822) show spend, income and net.

**Fixture:** spend $25.65 (the three campaigns) with $3.12 income reads "net -$22.53". Income
entries never count as spend.

### 5. #1758 B07.12 - no affiliate link on a Short

A Short's description links are not clickable, and an affiliate link there earns nothing but still
looks like an ad. `publishing/prepublish.py` drops an affiliate URL from a Short's description, and
its line says so.

**Fixture:**

| video | description link | result |
|---|---|---|
| a 45 s Short | Amazon `?tag=` | removed, one line |
| a 10-minute video | the same link | kept |

### 6. #1756 B07.10 + #1757 B07.11 - TikTok that can earn

TikTok's Creator Rewards pays only for videos over a minute, from accounts with 10k followers and
100k views in 30 days.

**Build.**
- A TikTok post under 61 s is marked "not reward-eligible" in the platform rows.
- The weekly report gives TikTok's followers and 30-day views against 10k and 100k, from Buffer's
  metrics. Where Buffer has no follower count it says "followers: not read".
- The length mix stays as decision 81 set it: no Short is lengthened for TikTok alone.

**Fixture:** posts of 45 s and 75 s give one eligible. 2,075 views in 30 days and no follower count
read "TikTok: 2,075 of 100,000 views in 30 days; followers not read".

### 7. #1775 B08.4 + #1776 B08.5 - TikTok-native first frame and captions

**Build.**
- The stake card (B02.4, if built) and the captions sit inside TikTok's safe zone (clear of the top
  ~10% and the bottom ~20%), so one render fits all three platforms.
- `publishing/platform_captions` writes TikTok's caption as the hook's first line plus three
  hashtags: two from the topic, one from the domain's set.

**Fixture:** "Seahawks defense stifles Chiefs offense in 20-3 Sunday Night Football win" gives a
first line under 100 characters and exactly three `#` tags. For a Short, the caption card's top
edge is at or below 10% of the frame.

### 8. #1791 B08.20 + #1774 B08.3 - cover frame and posting hour per platform

**Build.**
- Buffer's `thumbnail_ms` (already sent for Instagram and TikTok in `buffer_api`) is set to the
  stake card's frame when there is one.
- Each platform's post hour comes from `publishing/platform_recommend` once it has ten posts.
  Before then, the YouTube slot plus one hour.

**Fixture:** a render with a stake card at 0.4 s sends `thumbnail_ms` 400. With nine Instagram posts
the hour is the YouTube slot + 1 h; with ten it is `platform_recommend`'s.

## LOCAL checks - for the PC session

- **The Facebook Page:** created and connected in Buffer (the operator), `BUFFER_FACEBOOK_CHANNEL_ID`
  in `.env`, and the Reel metadata fields checked against Buffer's API docs. Then one real post,
  watched.
- **The policy site rebuilt and redeployed** with `links.html`, and the bios pointed at it.
- **The first month's Amazon Associates figure** entered with `ops spend income`.

## When the wave is done

The next-five skill's order:
1. backlog ticks;
2. this page archived;
3. the calendar's checkpoint (Dec 1) read with the money row;
4. the planning log;
5. the handoff slot last.
