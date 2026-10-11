# Operator guide — how a video gets made

> **Class:** runbook · **Status:** living · **Reviewed:** 2026-10-10

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
py -m scripts.ops technical-qc --path outputideo.mp4   # black frames, frozen stretches, loudness
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

## 7. Read the numbers

```powershell
py -m scripts.ops sync-metrics --channel tapin
py -m scripts.ops growth --channel tapin          # where the views go, the three biggest gaps
py -m scripts.ops weekly-report --channel tapin   # more of / less of / try next
py -m scripts.ops predictions --channel tapin     # each run's prediction beside what it got
```

`weekly-report` opens with three decisions, each with the number behind it. `growth` compares
Shorts cut from a chapter with Shorts made as Shorts once three of each have a full week.

## Money

```powershell
py -m scripts.ops reliability                     # credits, quota, cache
py -m scripts.ops spend                           # what has been paid
py -m scripts.ops promotions --channel tapin      # what each ad campaign bought
```

Pace and cost: [operating_plan.md](operating_plan.md). Every command: [ops_commands.md](ops_commands.md).
