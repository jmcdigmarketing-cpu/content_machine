# The hands-off plan

> **Class:** plan · **Status:** living · **Reviewed:** 2026-10-18

The forward plan from 2026-10-18; it supersedes [optimization_plan_2026-10.md](optimization_plan_2026-10.md)
("the next 100"), whose open rows the [backlog audit](backlog_audit_2026-10-18.md) merged,
retired or kept. [master_plan.md](master_plan.md) keeps the long horizons (M4 volume, M5
reach); this page is how they are worked now.

The operator, 2026-10-18, after a day of using it: *"no damn way am i posting these manually.
plan for improvement on these items, big big plan to adress these moving forward."* The items
are the Content OS Story's list of what is wrong - each one is a section below, under five
themes. Every section says where it stands (measured, with the date), what fixes it, who acts,
and an exit criterion that is a command.

**Who acts.** **Code** - an agent ships it. **You** - a click or a decision only the operator
can make (a Google console, money, the channel's niche). Each "You" step names the exact
command or page.

**Horizons.** **H0** this week · **H1** the next two to four weeks · **H2** the quarter.
[roadmap.md](roadmap.md)'s next five are drawn from H0 and H1.

---

## A — Nothing by hand

The last mile was manual: a queued upload waited for a worker nobody started, a game preview
was posted after its game, a scheduled video went to TikTok and Instagram the next morning,
and `ops crosspost` printed folders to post by hand.

| | Where it stands (2026-10-18) | Fix | Who | H |
|---|---|---|---|---|
| A1 | `ops crosspost` asked for hand posting while Buffer worked | the bare verb is the Buffer round; `pack` only packs public videos (#1298) | Code - done | H0 |
| A2 | batch-review scheduled with a planner that knew no kickoff or news window: the Chargers preview went out 3 days after its game | one slot rule: before the game (or as it uploads), inside the window, the free noon/10 PM (#1298, #1295) | Code - done | H0 |
| A3 | a scheduled video reached Buffer at the morning sync | the worker sends a passed slot within 15 minutes (#1299) | Code - done | H0 |
| A4 | the upload worker task is installed; the overnight task **cannot wake the PC** (WakeToRun off since the 10-18 undo) | `py -m scripts.ops schedule-drafts --wake` | **You** | H0 |
| A5 | the YouTube sign-in ends every 7 days (the Google app is in Testing) | publish the app: the policy pages are built (`ops policy-site`); Google Cloud console -> OAuth consent screen -> Publish app | **You** | H0 |
| A6 | approved drafts wait unlisted only when a claim is flagged; everything else is scheduled | keep it so: a new path that uploads public-now lands unlisted for review (#109) | Code | - |
| A7 | a status-only update may clear status fields YouTube keeps | read them before and after one, send what it keeps (#1306) | Code | H1 |

**Exit:** a week in which every public video was scheduled by the system and reached Buffer
within an hour of its slot - `py -m scripts.ops crosspost status` - and you typed no upload,
go-public or crosspost command.

## B — Bigger ideas, real takes

The ideas were small stories and the previews were not predictions.

| | Where it stands | Fix | Who | H |
|---|---|---|---|---|
| B1 | ideas were a date shuffle of 4 feeds | every configured feed for the channel's domains (17), ranked by how many outlets carry the story (#1300) | Code - done | H0 |
| B2 | previews were matchup + records | a call and the why, against the board's line (#1301) | Code - done | H0 |
| B3 | NFL and NBA news never reach the ideas: TapIn's niche is gaming, UFC, soccer | add `"nfl", "nba"` to `extra_domains` in `config/channels.json`, or keep news to gaming and UFC (#1303) | **You** | H0 |
| B4 | a call's reason is often the season records, and nothing scores a call | feed it the script's matchup research; score calls after the game - "called 7 of 10" is a series and an E1 number (#1304) | Code | H1 |
| B5 | every video opens on a 2.15 s channel intro; `INTRO_TEST=alternate` is running | read the result once enough videos settle it; drop the intro if no-intro holds more viewers (#988) | Code + **You** | H1 |
| B6 | the hook score runs against who stays (r = -0.41) | retune when 21 videos settle it (#1290) | Code | H1 |
| B7 | no recurring format brings a viewer back | a series - "every UFC card, graded", "Week N picks, graded" (#991) | Code + **You** | H1 |
| B8 | clean is not good: a title still read "Denver Loss Angeles" | the title check (#1181) and the take check (#1292) gate a render | Code | - |

**Exit:** the idea menu's first five each read "on N outlets" with N >= 2, every preview
carries a call (`py main.py`, or `py -m scripts.ops overnight-plan`), and the first scored calls
appear in `ops predictions`.

## C — Reach and money, honestly

As of 2026-10-11, in YouTube's own numbers: 69 of 1,000 subscribers; 1,797 organic Shorts views
in 90 days against the 10,000,000 the Shorts path needs (147 a week against 777,778); 10
long-form watch hours against 4,000. +64 subscribers in 28 days, 62 of them while an ad ran.
Median first-week views 83. At this size the Shorts path to the Partner Program is not reachable
by volume alone, so the levers are taken in order of what they can move:

1. **Per-video reach** - B above: bigger stories, real calls, the first second.
2. **TikTok and Instagram** - every public video goes there through Buffer, and each platform's
   results are read back (#1194-#1199, shipped). The weekly report says which feed liked what.
3. **Watch hours** - a weekly long-form compilation from the week's Shorts (#138), the only path
   to 4,000 hours at this size.
4. **Money that is not ads** - one affiliate spike with a kill criterion (#79): two weeks, drop
   it if video -> click -> sale cannot close.

| | Decision | Who | H |
|---|---|---|---|
| C1 | do the ads continue? 62 of 64 new subscribers came while one ran, and `ops promotions` says what each campaign bought | **You** | H0 |
| C2 | volume: 13 uploads in 7 days now, two slots a day plus games; the cap is off (decision 65) | - | - |

**Exit:** `py -m scripts.ops ypp` and `py -m scripts.ops growth` move week over week; the
weekly report names the platform that grew.

## D — Reliability and speed

| | Where it stands | Fix | Who | H |
|---|---|---|---|---|
| D1 | one-key menus showed no prompt, so an unseen Proceed? got an Enter (stop) | the prompt is flushed before the key is read (#1297) | Code - done | H0 |
| D2 | `ops all` ran the suite (259 s) and failed six tests that only fail with `.env` loaded | `all` leaves the suite to CI and `ops test`; `ops test` runs without `.env`'s values (#1302) | Code - done | H0 |
| D3 | a test can read the real `data/` and change verdict on your PC only | an audit hook in `tests/__init__.py` fails it (#1305) | Code | H1 |
| D4 | overnight crashed natively on 10-16 | the next crash names its Python line (shipped 10-16) | - | - |
| D5 | clicks are unmeasured: the Reporting API is off in the sign-in's Google project | `py -m scripts.ops doctor` prints the link that turns it on; then #1058 | **You**, then Code | H0 |

**Exit:** `py -m scripts.ops all` finishes without the suite and with no failure; CI is green on
every push (`gh run list`).

## E — A backlog that earns its place

It grew faster than it shipped: 258 open items against 44 public videos. The 2026-10-18 audit
closed 188 - 92 merged into a later entry, 83 retired, 13 already shipped - and kept 70
([backlog_audit_2026-10-18.md](backlog_audit_2026-10-18.md)). The rules it used now hold every
wave:

1. An item is filed with a measurement or an operator ask - not an idea alone.
2. A wave closes at least as many items as it files.
3. A duplicate is merged into the later or more precise entry on sight, and the closed one
   names it.
4. UI widgets live in [desktop_app.md](desktop_app.md)'s stages, not in the backlog.
5. A parked channel has one item (MoneyWise's depth wave).

**Exit:** `py -m scripts.ops roadmap-index` shows the open count at or under 130 and falling.
`tests/test_docs_lint.py` fails a backlog past 130.

---

## This week (H0)

Code (shipped 2026-10-18, wave 110): A1-A3, B1, B2, D1, D2.

Yours, each one line:

1. `py -m scripts.ops schedule-drafts --wake` - overnight can wake the PC again (A4).
2. Publish the Google OAuth app - the sign-in stops ending every 7 days (A5).
3. Turn on the YouTube Reporting API - the link is in `py -m scripts.ops doctor` (D5).
4. NFL and NBA news in the ideas, or not (B3).
5. Ads: continue or stop (C1).
