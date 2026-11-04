# Decisions, continued (2026-11 onward)

> **Class:** reference · **Status:** living · **Reviewed:** 2026-11-03

[decisions_2026-10.md](decisions_2026-10.md) holds decisions 40-96 and was near its size ceiling
(675 of 800 lines). Decisions 97 onward are here, numbered on. Same rules: code says *what*, this
says *why*. Keep entries short.

---

## 97. Never a death story (2026-11-02)
**Decision:** a headline whose subject is a death is never an idea - not in the menu, not in an
overnight slot, not among a countdown's facts. A death in a title or a first sentence holds the
render, and a description sentence about a death is dropped at upload. A passing mention inside a
script is allowed. **Why:** live on 11-02 a viral fan's death led the Nov 3 GTA 6 countdown (run
226: "has *died*"), sat mid-script in that day's countdown (run 225) and had a draft of its own
(run 229, "GTA 6 Community Mourns Loss of Devoted Fan") - held only because a second read happened
to dislike its first sentence; nothing in the code matched a death. Asked, the operator chose the
stricter option, "Never draft a death story", over "never the hook or title". The redraft (run
231) then had a clean script and a description that still said the fan had died "three weeks
before launch" - so the description is covered too. **Consequence:** `authenticity.death_reason`
/ `is_death_story` at the menu, the overnight gate, the countdown's facts and `ad_limit_reason`'s
four callers; `prepublish.without_death_lines` at upload. Replayed on the stores: 1 of 226 titles,
4 of 1,790 headlines and 3 first lines match, all real deaths; no game title or sport phrase does.

## 98. The night carries the menu's gaming share; a menu is counted once; a deleted video is recorded gone (2026-11-02)
**Decision:** while gaming leads the organic views, a night's drafts - its countdowns and other
dated drafts included - carry `GAMING_FLOOR` of five gaming; a plain headline gives way to the next
gaming idea, never the series or the preview. S15 reads each distinct menu once. A video YouTube no
longer returns is recorded with privacy `gone` (the row stays; nothing is deleted). **Why:**
decision 93's three-of-five floor lived in the interactive menu; overnight's slate (the series,
one preview, then headlines past the outlet gate) offered gaming one row in three every night while
gaming earned 62% of organic views, and `menu_mix` counted each night's menu once per draft. Runs
179, 185 and 186 were deleted in Studio; the sync reported them every night and the shelf still
listed two as "held for a claim" - #1128 had left the record alone on purpose. **Consequence:** a
night with two gaming countdowns already carries the share (3 of 5); after the countdown ends a
three-draft night swaps a headline for gaming. S09 does not count a `gone` record as drift - the
operator deleting a video is not the record drifting.
