# Decisions, continued (2026-10 onward)

> **Class:** reference · **Status:** living · **Reviewed:** 2026-10-11

[decisions.md](decisions.md) reached its size ceiling at decision 39 (docs_standard.md §7).
Decisions 40 onward are here, numbered on. Same rules: code says *what*, this says *why*.
Keep entries short.

---

## 40. Overnight may render, up to a number the channel sets (2026-10-11)
**Decision:** `ops overnight` renders up to `overnight.renders` drafts (tapin: 2; default 0) and
queues each one **unlisted**. It takes only a draft nothing is flagged on: no unsupported claim,
an `ok` authenticity verdict, no conflicting facts, no ungrounded name, no weak hook, no label
in the title, still inside its freshness window. It never queues public; the operator watches
and runs `go-public`. `OVERNIGHT_RENDERS` overrides the channel and the suite pins it to 0.
**Why:** this reverses "overnight stays render-free" (wave 27). That rule kept unattended runs
from paying for a voice; it also meant 69 runs stopped at a draft, because the morning review
that was meant to render them was not being run. The operator chose it: "yes, up to 2 a night".
**Consequence:** a night can spend ElevenLabs characters for two videos with nobody watching.
The checks above are the whole guard - loosen one and say so here.

## 41. A parked channel stays set up and out of the way (2026-10-11)
**Decision:** `"parked": true` in `channels.json` takes a channel out of the picker and takes its
own feeds out of `ops doctor`; `--channel <id>` still reaches it and deleting the flag restores
it. MoneyWise is parked. **Why:** it had made no video, and its dead finance feed was failing
the doctor for the channel that is worked. Nothing is deleted, so nothing has to be rebuilt.
