# Operator guide — how a video gets made

> **Class:** runbook · **Status:** living · **Reviewed:** 2026-10-13

One pass through the machine, in the order it happens. Each step names the one command and
links the doc that goes deeper. Run everything from `C:\dev\content_machine`; the PowerShell
cheat-sheet is [startup_powershell.md](startup_powershell.md).

Every command below was run on 2026-10-10 (#1076). A step that stops working is fixed here or
removed - this doc is not a wish list.

## 0. Before the first video of the day

```powershell
py -m scripts.ops doctor --channel tapin     # links, keys, quota, GPU - one screen
py -m scripts.ops next --channel tapin       # the one thing blocking publish, if any
```

`doctor`'s `workspace` row fails on a missing vault, a vault under OneDrive, or sync-conflict
copies in `data/`, and notes a footage folder with no clips. `daily-brief` does the morning
sync (competitors, SEO hints, vault dossiers) as well as printing the scoreboard - it writes,
so run it once, not as a status check. Trouble: [debugging.md](debugging.md).

## 1. The idea

```powershell
py main.py          # 1 new video · 5 make a video from your own idea / a YouTube link
```

Or the app: the **Content OS** shortcut on the Desktop (`py -m scripts.ops shortcut` puts it
back). Type the idea the way you would say it. To see how it will be read before spending
anything:

```powershell
py -m scripts.ops intent-check "can the chargers still make the super bowl"
```

Why ideas and angles come out the way they do: [idea_quality_diagnosis.md](idea_quality_diagnosis.md).

## 2. The angle screen

Angle 1 is your idea, worded for search. The keys:

| key | does |
|---|---|
| Enter | keeps your idea (angle 1) |
| a number | takes that generated angle |
| `A` | every angle in one long video, a chapter each |
| `M` | changes the mode (hope, take, plan, explainer ...) and rewrites the angles - no new discovery |

Signals ran before this screen. If one looks dead: `py -m scripts.ops reliability`.

## 3. The facts

Paste facts or links when asked; they outrank everything a signal says. A render that still
carries a claim no source backs is **held unlisted**:

```powershell
py -m scripts.ops verify-claim --run-id 120                                   # list what is held
py -m scripts.ops verify-claim --run-id 120 --claim 1 --source "https://..." --apply
py -m scripts.ops verify-claim --run-id 120 --claim 1 --reject
```

The vault the facts are saved to and read from: [vault.md](vault.md).

## 4. Render and footage

The render cuts your own gameplay from `video/backgrounds/`, a new shot every 2-3 seconds.
Which folder, in order: the game the topic names, the playlist key, a sport game's sport, the
topic's sport, the run's idea. A topic about games that names none of yours cuts a mix of your
game folders. Only a sport, film or finance topic with no footage falls to stock, and the
render says so (`Background: STOCK (last resort - no owned footage matches)`).

```powershell
py -m scripts.ops footage-gaps --channel tapin    # what to record next
py -m scripts.ops ingest-clips                    # dry run: captures -> folders
py -m scripts.ops ingest-clips --apply            # import them (safe to stop and rerun)
py -m scripts.ops footage-add --path clip.mp4 --game Minecraft --licence "own capture" --apply
```

Captures are read from `Videos\Captures` (Game Bar), the Xbox DVR folder and NVIDIA's.
The video stack: [video_creation_stack.md](video_creation_stack.md).

## 5. Review

```powershell
py -m scripts.ops booth --channel tapin           # play the last render, grade, cost
py -m scripts.ops batch-review --channel tapin    # the 05:00 overnight drafts, in one pass
py -m scripts.ops chapters --run-id 79             # chapters, and when its Shorts would go
py -m scripts.ops technical-qc --path output\video.mp4   # black frames, frozen stretches, loudness
```

## 6. Publish

Uploads go out unlisted or scheduled; `go-public` is the step that makes one public. It is a
dry run until `--apply`, and it names what it will publish.

```powershell
py -m scripts.ops status --channel tapin
py -m scripts.ops publish-dry-run --channel tapin   # the upload body and the pre-publish checklist
py -m scripts.ops go-public --channel tapin            # what would go public
py -m scripts.ops go-public --channel tapin --apply
py -m scripts.ops recommend-time --channel tapin       # the slot, and how many posts back it
```

A held run is refused until its claim is confirmed or rejected (step 3). Policy trouble:
[policy_incident_runbook.md](policy_incident_runbook.md).

**The shelf.** The startup header ends "N finished, not public" when anything is waiting.
`py -m scripts.ops shelf` lists each one with what it waits on and the exact command: a render
that is queued (the worker sends it), a render never uploaded (queue it, or retire an old one),
an upload still unlisted (`go-public`, or `verify-claim` first when it is held for a claim).

**Uploads go out on their own** once this is run, one time:
`py -m scripts.ops worker-task --install`. It sends queued uploads every 15 minutes while you
are signed in to Windows. Without it they wait for `py -m scripts.ops worker`, and the header
says "1 upload overdue" when one has.

**TikTok and Instagram follow YouTube** (#1188, decision §54): once a video is public on
YouTube it is scheduled on both through Buffer - one a day per platform, the AI label on.
Setting it up once (the Buffer key, the R2 bucket keys, the channel ids) is in
[platform_publish_setup.md](platform_publish_setup.md); `py -m scripts.ops crosspost status`
shows each video on each platform, `crosspost cancel --run-id N` takes one back.

**The YouTube sign-in ends every 7 days** while the Google consent screen is in Testing. From
day 5 the header, `ops status` and the overnight report say how many days are left; once it
has ended they say "sign in" instead of "run the worker". Renew with
`py -m youtube.oauth_setup --channel tapin`. Publishing the consent screen ends the weekly
expiry ([platform_publish_setup.md](platform_publish_setup.md)).

**Mornings.** Overnight (5:00 am) writes drafts and renders up to two clean ones, queued
unlisted. One command does the morning:

```powershell
py -m scripts.ops morning --channel tapin
```

It syncs the numbers, says what overnight rendered and where each one is now, lists the shelf
and any open correction on a published video (one line each; `ops corrections-open` alone),
then walks the waiting drafts for a yes or no each. When the YouTube sign-in has ended it asks
"Sign in to YouTube now?" first - `y` opens Google's page, and the sync runs once you are back. (`ops all` is the weekly batch; the morning
review is not in it.) Run from a scheduled task or a pipe it skips the draft review and says
so. `py -m scripts.ops overnight-plan` shows what tonight would render and why the rest wait.

`ops overnight-last` also says when overnight ran against its 5:00 AM start - late, or not at
all when the PC was asleep. `py -m scripts.ops schedule-drafts --wake` prints the one line that
lets the task wake the PC. Drafts past twice their window are set aside each night (nothing is
deleted): `py -m scripts.ops batch-review --expired` lists them.
`py -m scripts.ops recheck-claims` re-checks the waiting drafts' flagged claims against their
own saved facts (`--apply` stores it).

Overnight stops rendering while three finished videos are not public (`OVERNIGHT_SHELF_MAX`) -
the plan says "Paused" and resumes by itself when the shelf drops. A draft about a scheduled
game renders only before the game: once it has started, or when the draft already calls the
result, it waits for you. So does a draft whose title the title check flagged.

**Is the script clean?** Each draft's review screen carries one line: the stance held, your
typed points used, no claim the facts do not back, nothing hard to say, no label in the title,
and any sentence that was cut. `py -m scripts.ops script-check --channel tapin` counts it over
the newest 30 scripts; `--idea "..."` writes one draft of your idea - as angle 1, your idea
itself, not a generated angle - with no voice, prints its check, and leaves it waiting in
`batch-review` for a yes.

In `batch-review`, a draft with flagged claims offers `c`: it cuts the sentences that carry them
(at most two, never the first, never under 85% of the length), names each sentence cut, stores
the new script and its check, and asks again. When nothing can be cut it says why - often the
claim is the first sentence, and then the fix is yours in `draft.md`.

## 7. Read the numbers

```powershell
py -m scripts.ops sync-metrics --channel tapin
py -m scripts.ops growth --channel tapin          # where the views go, which videos brought a subscriber
py -m scripts.ops ypp --channel tapin             # the Partner Programme bars, and how far each is at this pace
py -m scripts.ops weekly-report --channel tapin   # more of / less of / try next
py -m scripts.ops predictions --channel tapin     # each run's prediction beside what it got
```

`weekly-report` opens with three decisions, each with the number behind it. `growth` compares
Shorts cut from a chapter with Shorts made as Shorts once three of each have a full week.

**Once, for older videos:** `py -m scripts.ops backfill stayed --apply` asks YouTube who stayed
past the swipe on videos synced before that number existed.

**Topics with demand.** `py -m scripts.ops competitors suggest` prints channels in your niches
with their size (it adds nothing, and re-reading it for a week costs no quota);
`competitors add --source <id>` approves one; `competitor-sync --force` then stores their
videos with view counts, and `competitor-health` lists any at three times that channel's median.

## Money

```powershell
py -m scripts.ops reliability                     # credits, quota, cache
py -m scripts.ops spend                           # what has been paid
py -m scripts.ops promotions --channel tapin      # what each ad campaign bought
```

Pace and cost: [operating_plan.md](operating_plan.md). Every command: [ops_commands.md](ops_commands.md).
