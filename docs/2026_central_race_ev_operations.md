# 2026 Central JRA EV Operations

## Current State

- Scope: JRA central racing only.
- Goal: Score every remaining 2026 central race shortly before the betting cutoff and buy only when historical no-leakage validation supports positive expected value.
- Current live action: PASS unless all data and model-quality gates are satisfied.

## Completed Preparation

- Built TARGET race-condition history:
  - `data/model/target_races_2004_2026.csv`
  - 75,977 historical races.
- Added race-condition rolling backtest:
  - `src/rolling_backtest_race_features.py`
  - Filters abnormal odds markets.
  - Adds surface, distance bucket, course, race class, field-size, sire, damsire, jockey, and trainer features.
- Built TARGET pedigree history:
  - `data/model/target_pedigree_1986_2026.csv`
  - 181,287 horses.
  - 100% match against 2004-2025 win-training rows.
- Added pedigree market-edge exploration:
  - `src/analyze_pedigree_market_edges.py`
  - `outputs/pedigree/sire_surface_distance_edges.csv`
  - `outputs/pedigree/damsire_surface_distance_edges.csv`
- Added live win EV scorer:
  - `src/score_live_win_ev.py`
  - Scores normalized race entries plus latest win odds and pedigree features.
  - Emits BUY/PASS with reasons.
- Strengthened JRA-VAN race normalization:
  - `src/normalize_jv_race.py`
  - Adds race conditions, jockey, trainer, horse weight, and related fields.
- Added purchase policy:
  - `config/purchase_policy.json`

## Validation Result

The stricter race-feature backtest found no valid BUY candidates under the initial real-money policy:

- Window: 2005-2025 rolling validation.
- Races checked: 72,525.
- Valid odds markets: 72,517.
- BUY candidates: 0.
- Top historical candidates were still negative EV after accounting for takeout.
- Adding sire and damsire features still produced 0 BUY candidates under the same real-money gate.

This means the current single-win model should not place real-money bets yet. The correct operational behavior is to keep monitoring and emit PASS until a model version demonstrates positive no-leakage backtest performance.

## Initial BUY Gate

BUY only if all are true:

- Latest win odds are available near cutoff.
- Race conditions and entries are complete.
- No abnormal odds market is detected.
- Estimated EV per yen is at least `0.20`.
- Condition sample count is at least `500`.
- Condition edge is at least `1.02`.
- Win odds are between `2.0` and `50.0`.
- Initial stake is `100` yen.
- Initial scope is win bets only.

## Place EV (added 2026-07-07)

- Live place scorer: `src/score_live_place_ev.py`
  - Ranks all runners by conservative place EV (place probability x lower-bound place odds).
  - `decision` is always PASS: the BUY path requires `--allow-buy`, which must stay unset until a
    place-specific positive no-leakage backtest exists.
  - Per-race live use: `--race-id <race_id> --output outputs/live_predictions/YYYYMMDD/race_<race_id>_place_ev.csv`.
- Validation evidence: `docs/place_ev_validation.md` and `outputs/backtests/place_ev/`.
  - 2,112 races with real final place odds (O1) and payouts (HR), 2025-06-14 .. 2026-01-18.
  - Model is well calibrated globally but negative ROI at every EV threshold (0.13-0.74).
  - High win-derived place EV is adversely selected: the place pool knows more than the win odds.
- Supporting tools:
  - `src/extract_place_validation_dataset.py` (SE + O1 + HR join)
  - `src/backtest_place_ev.py` (rolling no-leakage backtest, calibration, threshold sweep)

## Weekend live sequence (win + place)

One command per cutoff — `src/run_live_cutoff.py` wraps odds normalization, same-day bias,
win EV, place EV, per-race output files, and the accumulated daily summary:

```powershell
# per-race, 5 minutes before post time
python src\run_live_cutoff.py --race-date YYYYMMDD --race-id <race_id> ^
  --races <today>\races_minimal.csv --starts <today>\starts_minimal.csv ^
  --raw-odds-dir <today_odds_dir>

# or all races with odds at once (e.g. end-of-day re-run)
python src\run_live_cutoff.py --race-date YYYYMMDD --races ... --starts ... --raw-odds-dir ...
```

Outputs land in `outputs/live_predictions/YYYYMMDD/`: `race_<race_id>_win_ev.csv`,
`race_<race_id>_place_ev.csv`, `combined_odds.csv`, `daily_summary_YYYYMMDD.csv` (merged across
invocations, post-time order), `buy_candidates_YYYYMMDD.csv`. Same-day bias uses
`--results data/model/win_training_minimal.csv` (default) — refresh it from same-day SE records
with `src/build_win_training_dataset.py` as races complete; without it, bias is neutral.

Manual pipeline (fallback / debugging):

1. Refresh JRA-VAN exports; normalize race cards with `src/normalize_jv_race.py`
   (note: a folder fetched on day D may contain day D+1 cards — check `race_date` inside the CSV).
2. Normalize 0B31 odds snapshots with `src/normalize_jv_odds_o1.py` (emits win AND place rows).
3. Build same-day bias per `docs/jra_same_day_bias_operation.md`.
4. Score win EV: `src/score_live_win_ev.py` (BUY gate active, currently never fires — expected).
5. Score place EV: `src/score_live_place_ev.py` (ranking only, PASS locked).

End-to-end verified 2026-07-07 on the full 2026-06-27 day (36 races / 448 runners, 0 buys on
both pools): `outputs/live_predictions/20260707_orchestrator_test/`.

## Next Model Improvements

Priority order:

1. Add more pre-race features from JV/TARGET:
   - Horse recent form.
   - Trainer/jockey recent form.
   - Course-distance record.
   - Running style and pace proxy.
   - Rest interval.
   - Weight change once final horse weight is available.
   - Pedigree interactions that survive no-leakage rolling validation.
2. Add calibration reports:
   - Predicted probability bucket versus actual win rate.
   - Monthly and yearly ROI.
   - Drawdown.
3. Expand beyond win bets only after win EV validation is positive:
   - Place, quinella, wide, and exacta require separate pool-specific backtests.

## Automation

The thread heartbeat automation is configured to keep checking race-day windows through the end of 2026 and report cutoff-window EV decisions.
