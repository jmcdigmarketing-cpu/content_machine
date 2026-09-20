# Policy incident runbook

> **Class:** runbook · **Status:** living · **Reviewed:** 2026-09-20

In-repo template for a YouTube **strike**, **Content ID** claim, or **appeal**.
Print the path with `py -m scripts.ops policy-runbook`. Do not paste secrets.

## Strike

1. Open YouTube Studio → Channel → Copyright / Community guidelines.
2. Screenshot the notice (date, video id, policy cited).
3. Pause overnight and public uploads for this channel until the appeal is filed
   or the strike expires.
4. Do not delete the video until Studio says that is required.

## Content ID

1. Note the claimant, the asset title, and whether the match is audio, visual, or both.
2. If the clip is owned gameplay / fair-use commentary, keep the video private
   and file a dispute with the timestamps.
3. If the match is stock we licensed, attach the provider page (Pexels/Pixabay/Coverr)
   — Coverr is not a quality lever; it is only provenance.

## Appeal

Subject: Appeal — [video id] — [strike or Content ID]

Body:

- What the video is (commentary / news / owned gameplay).
- Why it does not infringe or violate the cited policy.
- What we changed, if anything (trim, mute, disclosure).
- Request: restore the video / release the claim.

Keep a copy of the appeal text in the vault `_runs/` dossier for that `run_id`.
