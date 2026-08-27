# YouTube Data API quota-increase checklist

Use this when remaining units cannot cover **one upload** (~1,600 units). Do not
invent quota numbers — read the tracker (`ops reliability` / `format_uploads_left`).

1. Confirm remaining units ÷ 1,600 is 0 (`uploads_remaining`).
2. Decide whether waiting for the daily reset is enough.
3. In Google Cloud Console → APIs & Services → YouTube Data API v3 → Quotas,
   request an increase. Attach recent `uploads left` figures, not guesses.
4. Keep `YOUTUBE_DAILY_QUOTA` in `.env` aligned with the granted cap after approval.
5. Do not raise this project's local tracker above what Google granted.
