# Place EV validation (2026-07-07)

Conclusion: the place BUY gate stays closed. A win-market-anchored place probability model is
globally well calibrated but has no positive edge against the place pool. Live place scoring is
ranking-only (`decision=PASS` always) until a place-specific positive no-leakage backtest exists.

## Data

- `data/model/place_validation_2025_2026.csv`
  - Built by `src/extract_place_validation_dataset.py` from `data/jra_van_exports/raw_race_2025_to_now_full.csv`.
  - Joins SE results (finish rank), final O1 place odds (min/max), and HR place payouts.
  - 2,112 races, 28,617 runners, 2025-06-14 .. 2026-01-18 (68 race days).
  - Refunded runners excluded; races with place 不成立/特払 excluded.
- Parse sanity checks:
  - 99.6% of realized payouts fall inside the final O1 [min, max] range. The 0.4% outside are all
    BELOW min (dead-heat splits / post-snapshot money) — so even "conservative lower bound" EV is
    slightly optimistic in the tail.
  - Payout counts match JRA rules exactly: 2 paid places for 5-7 starters, 3 for 8+, dead heats add extras.

## Model

`PlaceRateModel` in `src/backtest_place_ev.py`: place rate by (field-size bucket, win-market
probability bin), shrunk toward bin and global rates. Trained on 2004-2025 finish-rank labels
(`target_win_training_2004_2025.csv`), rebuilt incrementally so each validation race only sees
strictly earlier data (no leakage).

## Results (`outputs/backtests/place_ev/`)

Calibration is good globally, including extreme longshots:

- Every predicted-probability decile within ±3.4pp of actual.
- Win odds >= 30: predicted 5.35% vs actual 5.30%. Win odds >= 100: 1.99% vs 2.05%.

But EV selection is adversely biased:

| EV(lower) threshold | bets | hit rate | ROI |
|---|---|---|---|
| bet everything | 28,607 | — | 0.70 |
| >= 0.90 | 1,391 | 22.6% | 0.74 |
| >= 1.00 | 465 | 9.0% | 0.57 |
| >= 1.10 | 215 | 7.0% | 0.39 |
| >= 1.20 | 98 | 4.1% | 0.13 |

High estimated EV concentrates where place odds are large relative to win-odds-implied strength.
In that subset the model predicts 13.3% place rate but actual is 7.0%: the place market carries
real information the win market does not. Win-odds-only place probability cannot beat the place pool.

## Caveats

- Decision inputs use final confirmed odds, not 5-minutes-before-cutoff odds. This makes the
  backtest *optimistic* if anything (final odds embed late smart money); the negative result stands.
- Validation window is ~7 months / 2,112 races. Enough to reject the current model at these ROI
  gaps; not enough to certify a marginal positive edge if one is ever found.

## Inverse signal test (2026-07-07, same day): REFUTED

Hypothesis: place odds LOW relative to win-derived expectation (place market bullish) marks horses
the win market underprices — usable as a win-bet filter.

Test: `src/analyze_place_market_win_signal.py`, results in `outputs/backtests/place_market_win_signal/`.
signal = place-market implied place prob / win-derived model place prob (8+ starter races only,
28,068 runners, same no-leakage rolling model).

| signal bucket | n | win edge vs market | win ROI | place edge vs model |
|---|---|---|---|---|
| <0.70 (place bearish) | 919 | 1.00 | 0.53 | 0.60 |
| 0.70-0.85 | 3,674 | 1.12 | 0.82 | 0.91 |
| 0.95-1.05 | 5,672 | 1.02 | 0.83 | 1.04 |
| 1.20-1.50 | 4,112 | 0.91 | 0.61 | 1.10 |
| >=1.50 (place bullish) | 3,025 | 0.90 | 0.42 | 1.31 |

Findings:

- Place-market disagreement encodes HORSE TYPE, not mispricing. Bullish place odds mark
  consistent grinders: they place far more (edge 1.31) and win LESS than the win market
  implies (edge 0.90). The hypothesis direction is exactly backwards.
- Place edge is cleanly monotone in the signal (0.60 -> 1.31): the place pool prices place
  probability correctly in both directions.
- Win edge is weakly monotone DECREASING; the 1.12 cell (0.70-0.85, 276 wins vs 247 expected)
  is ~1.8 sigma and its ROI is still 0.82 — not actionable, re-check if more data accumulates.
- Practical salvage: place-market implied probability is a better ranking input than the
  win-derived model; the live scorer now emits `place_probability_market` and
  `place_market_signal` columns for race-day reports (audit/ranking only, never EV vs its own pool).

## Next hypotheses (in priority order, from the proprietary edge families)

1. ~~Win-vs-place relative mispricing as a win-bet filter~~ — tested, refuted (see above).
2. Place-odds movement between snapshots (needs multiple O1 snapshots per race, collect going forward).
3. Condition-specific place edges (surface/going/field size) on top of the market anchor —
   requires the same adversarial-selection check that killed the baseline.
4. Signal-bucket 0.70-0.85 win edge (1.12, ~1.8 sigma): re-test once the validation window grows;
   treat as noise until then.
