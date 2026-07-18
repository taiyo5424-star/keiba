# JRA same-day bias operation

Purpose: every live JRA central-racing prediction must use only information available before the target race, including completed same-day races.

## Required live sequence

1. Refresh JRA-VAN/TARGET data for the day.
2. Normalize `RACE` raw data with `src/normalize_jv_race.py`.
3. Build same-day result rows from completed `SE` records with `src/build_win_training_dataset.py`.
4. Build same-day bias context before the target race:

```powershell
python src\build_same_day_bias_context.py --race-date YYYYMMDD --as-of-post-time HHMM --races path\to\races_minimal.csv --starts path\to\starts_minimal.csv --results data\model\win_training_minimal.csv --output outputs\live_predictions\YYYYMMDD\day_bias_context_HHMM.csv
```

5. Score live odds with the bias file:

```powershell
python src\score_live_win_ev.py --race-date YYYYMMDD --races path\to\races_minimal.csv --starts path\to\starts_minimal.csv --odds path\to\odds.csv --same-day-bias outputs\live_predictions\YYYYMMDD\day_bias_context_HHMM.csv --output outputs\live_predictions\YYYYMMDD\race_<race_id>_win_ev.csv
```

## Current same-day signals

- Completed races before target post time only.
- Same course + same surface is preferred.
- Fallback scopes: same course, then all-day.
- Gate bucket winner bias.
- Favorite wins and longshot wins.
- Fastest-last-3F winner count and average winner last-3F rank.
- Neutral factor when sample is too small.

## Safety rules

- Never use target-race result data.
- Never use races with post time equal to or later than the target race.
- Keep `bias_factor` clamped between `0.90` and `1.10`.
- Keep pre-bias probability and EV in output for audit.
- If latest odds are missing, prediction can be ranked but purchase remains PASS.
