# YouTube Studio, as the operator saw it on 2026-10-30

> **Class:** snapshot · **Status:** frozen · **Reviewed:** 2026-10-30

Eight screenshots of the YouTube Studio app's Shorts list and its comments, taken by the operator
around 12:20 on Fri 2026-10-30 and handed over with *"input these"*. This page writes them down as
they were. It is not the system's copy of the numbers: the PC's metrics sync reads every video's
numbers from YouTube itself. It is the operator's view on the day, and the evidence behind
[decision 85](decisions_2026-10.md) and the plans written the same day:
[tapin_philosophy.md](tapin_philosophy.md), [tapin_principles.md](tapin_principles.md),
[logistics_plan.md](logistics_plan.md), [look_and_feel.md](look_and_feel.md) and
[horizons_2027.md](horizons_2027.md).

## Every Short in the screenshots

Titles are cut where Studio cuts them. Ages are as Studio showed them on 10-30. Views are all
views, paid and organic together.

| Short | age | views | likes | comments |
|---|---|---:|---:|---:|
| Modern Warfare 4 campaign praised by Steam players as return to form | 8 days | 37K | 473 | 2 |
| Seahawks defense stifles Chiefs offense in 20-3 Sunday Night Foot... | 3 days | 1.9K | 71 | 1 |
| GTA 6 online mode may repeat GTA Onl... | 3 days | 1K | 12 | 0 |
| Valve's Steam AI crackdown stance s... | 1 day | 969 | 10 | 0 |
| Fans react to GTA 6 launch trailer with h... | 9 days | 314 | 1 | 1 |
| ...Fight Reaction to Mi... (Dana White, Malott) | 8 days | 265 | 5 | 0 |
| GTA 6 character switching risks feeli... | 1 day | 260 | 0 | 0 |
| GTA 6 leaks reveal missing single-play... | 4 days | 258 | 2 | 0 |
| GTA 6 economy design could break i... | 1 day | 212 | 1 | 0 |
| Coach Conversation: Volkanovski vs Evlo... | 6 days | 96 | 4 | 0 |
| Breaking down Real Madrid's set-piece... | 4 days | 91 | 0 | 0 |
| UFC 333 Shows Where Decline Com... | 15 hours | 68 | 0 | 1 |
| Jalen Hurts out for season with blood c... | 9 days | 63 | 0 | 0 |
| Bonfim vs Brady fight preview: 5-fight win... | 1 hour | 36 | 0 | 0 |
| Xbox Game Pass subscribers react to... | 4 days | 30 | 1 | 0 |
| Jackson's brace ends Man City's perfect s... | 3 days | 26 | 0 | 0 |
| Picks gone wrong: Oct 19 board under... | 5 days | 16 | 1 | 0 |
| Star Wars Zero Company's Progres... | 8 days | 13 | 0 | 0 |
| Makhachev's praise highlights mutual re... | 2 days | 6 | 0 | 0 |
| Harry Kane Wins 2026 Ballon d'Or Af... | 2 days | 5 | 0 | 0 |
| The UFC 333 loss forces a reckoning:... | 1 hour | 4 | 0 | 0 |
| What's Next for Kane After Claiming His F... | scheduled 10/30/26, 5:00 PM | - | - | - |

**Modern Warfare 4's 37K is mostly paid.** It was promoted on Oct 26, and decision 82 records those
campaigns at about 37k views and 29 subscribers for $15.65. None of that counts toward YPP. Which
other rows carry paid views is in `py -m scripts.ops promotions`, not in these pictures.

## The comments

| Short | comment |
|---|---|
| UFC 333 Shows Where Decline Comes From | "lame" |
| Seahawks defense stifles Chiefs offense in 20-3 Sunday Night Foot... | five red hearts |
| Modern Warfare 4 campaign praised by Steam players as return to form | ten party poppers |

## What the pictures show

Studio's Shorts tiles show a frame of each video, with the burned-in caption words on it. Two of
the comment rows also show the custom thumbnail.

- **Different videos, one frame.**
  - *GTA 6 character switching* and *GTA 6 economy design*: the same dark car with red tail lights.
  - *What's Next for Kane*, *Breaking down Real Madrid's set-piece* and *Jackson's brace ends Man
    City's*: the same EA FC squad-menu screen, FC Barcelona's crest on it, with "INVITE" across it.
    That is Barcelona's menu behind stories about Bayern's striker, Real Madrid and Manchester
    City.
  - (The green car under a "Dexerto." caption shows twice only because two screenshots overlap:
    both are *GTA 6 leaks reveal missing single-player*.)
- **Footage that is not the story.**
  - *Valve's Steam AI crackdown*: a cartoon-skinned shooter.
  - *Xbox Game Pass subscribers react*: Minecraft.
  - *Star Wars Zero Company*: a stock shot of someone at a desk.
  - The UFC Shorts run on UFC 5 game footage, the NFL Shorts on Madden and the NBA ones on 2K.
    Those match their sport.
- **The custom thumbnails look alike.** The Seahawks and Modern Warfare 4 rows show an AI-made
  young man beside the title. One sits on teal and one on a cyan-to-pink gradient, and neither
  comes from the video's own footage.

Why each of these happens, traced in the code on `899ff58`, is in
[look_and_feel.md](look_and_feel.md#why-it-looks-like-this).

## A reading, on the day

- **Gaming and sports both travel.** The best tile on the sports side (Seahawks, 1.9K, 71 likes) and
  the best on the gaming side (GTA 6 online mode 1K; Valve 969 in one day) sit side by side.
- **GTA 6 is the steadiest subject.** Five GTA 6 Shorts took 212 to 1K each.
- **Small stories stay small.** Soccer took 5-91 and the UFC 333 follow-ups 4-68, as did Makhachev
  (6), Star Wars (13) and the picks recap (16). That is decision 81's finding again.
- **The one critique in words is "lame",** on a UFC 333 follow-up.
- **The two emoji-only comments sit on the two most-viewed Shorts,** one of them the promoted one.
