# MoneyPrinter vs Content OS — clip pipeline, compared

> **Class:** reference · **Status:** living · **Reviewed:** 2026-09-20

Written 2026-08-26 after the operator's step-3 note: **unnecessary stock
footage is often unrelated, and a hard cut from gaming to live-action reality
is disorienting.** Standing rule: [decisions.md](decisions.md) §26. Session
log: [planning_log.md](planning_log.md) 2026-08-26.

This is not a star-count contest. It is which system should own **TapIn /
MoneyWise Shorts**.

Two different GitHub projects share the MoneyPrinter name. Mixing them is how
the landscape table used to lie.

| Project | Repo | Licence | What it is |
|---|---|---|---|
| **MoneyPrinterTurbo** | `harry0703/MoneyPrinterTurbo` | **MIT** | Faceless assembler: topic → LLM script → **stock clips** → TTS → MoviePy/FFmpeg. Wave A Coverr/Edge TTS source. |
| **MoneyPrinterV2** | `FujiwaraChoki/MoneyPrinterV2` | **AGPL-3.0** | Velocity/cost bot (gpt4free, KittenTTS, Selenium). Pattern-borrow only. **Do not clone near this repo.** |
| **Content OS** | this repo | Proprietary | Decide → research with verified facts → script → grade → render → YouTube → learn. Stock is one background provider, not the product. |

The rest of this file means **Turbo** unless it says V2.

---

## What Turbo actually does for video clips

Read from `app/services/material.py` (fetched 2026-08-26), not from the README.

After the script exists, an LLM emits search terms (default **five**). Turbo
then:

1. Picks **one** `video_source`: `pexels` | `pixabay` | `coverr` | `local`
   (a folder of mp4/mov/images). These are exclusive. There is **no hybrid**
   of owned gameplay plus stock in one render.
2. For each term, searches that API. Coverr is `GET https://api.coverr.co/videos`
   with `Authorization: Bearer` and `urls=true` (the same endpoint we shipped
   in `assets/coverr_provider.py`).
3. Downloads until `sum(min(max_clip_duration, clip.duration))` covers VO
   length. Default **`max_clip_duration = 5` seconds**.
4. Concatenates. Default concat is **`random`** (shuffle the downloaded
   files). `sequential` keeps download order. `match_script_order` can keep
   term order.
5. Optional **transitions** between those clips: `none` (hard cut),
   `fade-in` / `fade-out`, `slide-in` / `slide-out`, or `shuffle` (a random
   transition per cut).
6. A separate paid path, **WaveSpeed**, generates AI clips on demand and
   **stops when duration is filled** so unused prompts are not billed. That
   is the analogue of our parked ComfyUI / LTX slot, not of Pexels.

Keyword match quality is whatever Pexels/Pixabay/Coverr return for those five
LLM strings. Turbo itself does not check that the clip is the same *world* as
the narration (game vs street vs office).

Local mode is the honest Turbo answer for a gaming channel: put gameplay in
`material_directory` and set `video_source = local`. Then there is no stock
at all — and also no research, no claim verifier, no YouTube loop.

---

## What Content OS actually does for video clips

Shipped TapIn (`config/channels.json`):

- `background_mode: hybrid`
- `hybrid_local_ratio: 0.45` → **~45% owned gameplay, ~55% stock**
- `asset_provider_order: ["local", "pexels", "pixabay", "coverr"]`

`assets/manager.get_background_asset` loads **one** local clip and **one**
stock clip, then `assets/composite.build_hybrid_concat_command` hard-concats
them (`concat=n=2`, **no xfade**). The jump the operator hates is that join.

Guards that exist and still cannot fix "this is live-action":

- `assets/background_query.py` rewrites vague topics toward "gameplay / octagon
  / court" and skips abstract fog/bokeh tags.
- #121 never Pexels-searches the trademark `UFC` (rewrites to `mma`).
- Coverr face skip is **tag-based**, not vision.

Opt-in `SCENE_MATCHED_BROLL` (`video/scene_plan.py`) splits the script into
beats and concatenates **one stock clip per beat**. That is Turbo's five-term
concatenator with stopword queries instead of an LLM. **Do not turn it on for
TapIn** under §26 — more stock cuts, same world-mismatch.

AI video (`AI_VIDEO_PROVIDER` / `core/comfy_client.py`) is registered and
fail-open to stock. The backend is parked on CUDA torch (`2.8.0+cpu` on the
4070 Ti), not on missing hardware.

---

## Head-to-head (what each is actually better at)

| Axis | Turbo | Content OS | Winner for TapIn |
|---|---|---|---|
| Clip sourcing | LLM → 5 keyword searches → many 5s stock clips | One local + one stock (hybrid) or local-only | **OS**, if local folder is stocked |
| Transitions | Fade/slide/shuffle between stock clips | Hard concat at the hybrid join | **Turbo** (the one visual borrow) |
| World match (game vs reality) | None. Keywords hit whatever the stock API has | Same keyword hole on the stock half; local half is owned | **OS local path**; hybrid still loses |
| Script substance | LLM from a topic; no fact corpus | Verified facts, claim verifier, title grounding, vault | **OS** |
| After publish | Upload-ish WebUI; no engagement loop | Best-bet / length / post-time from real YouTube | **OS** |
| 2026 authenticity | Not a product surface | Report card, disclosure, cadence, semantic arm | **OS** |
| Cost honesty | Free Edge TTS; stock is $0; WaveSpeed is paid | TTS ~91% of a rendered run; governor; `ops economics` | **OS** for the business; Turbo cheaper to *click Generate* |
| TTS | Edge (undocumented Microsoft endpoint) default | ElevenLabs default; Piper/Kokoro/XTTS/Qwen fail-open | Split: Turbo cheaper; OS safer + caption-retexted |
| Operator control | Streamlit + REST "one topic" | CLI + booth + overnight gates | **OS** for a real channel; Turbo for a demo |
| Licence to copy clip code | MIT | n/a | Turbo code *could* be copied; §26 says **don't copy the stock concatenator** |

**Which is better overall?** Content OS, for the job this repo exists to do.
Turbo is a better *stock slideshow factory*. That factory is the thing the
operator just rejected for TapIn.

**Which is better at the complaint that triggered this file?** Neither Turbo
default nor our hybrid default. Turbo's default is *more* unrelated live-action
per minute. Our hybrid at least spends ~45% in owned footage, then sabotages
it with a hard cut. The fix is not Coverr, not five LLM search terms, and not
`SCENE_MATCHED_BROLL`. It is **more owned clips**, `background_mode: local`
(or a much higher `hybrid_local_ratio`), and if hybrid stays, a **crossfade
on that one join**.

---

## What not to build from this comparison

- Do not add a fourth stock API.
- Do not enable scene-matched stock on TapIn.
- Do not replace the pipeline with Turbo's WebUI.
- Do not treat `COVERR_API_KEY` as a quality upgrade (fail-open with no key is
  the correct shipped state).
- Do not lift MoneyPrinterV2 source (AGPL).

## What is worth borrowing later (still not this session)

1. **xfade** (or fade-out/fade-in) at the hybrid local→stock join — Turbo's
   only clip-pipeline idea that addresses "untransitioned."
2. **Local-only as the TapIn default** once `video/backgrounds/` has enough
   franchise footage. Operator call; not flipped here.
3. **WaveSpeed-style "stop generating when duration is filled"** when the
   ComfyUI slot is live, so unused scene beats do not burn GPU-seconds.

V2's only surviving lesson is still cost posture (local TTS), already shipped
as Piper/Kokoro/XTTS. It has nothing useful to say about B-roll.
