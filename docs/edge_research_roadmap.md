# Edge research roadmap and monetization path (updated 2026-07-08)

Monetization has exactly one legitimate route here: find a market bias that survives
no-leakage validation AND fresh out-of-sample paper trading, then bet it small.
Nothing else is real. Current status: no cell is approved for real money.

## Promotion pipeline

1. **Hypothesis** — from the proprietary edge families, mechanism required (why would the market misprice this?).
2. **Rolling no-leakage backtest** — 2005-2025, market-relative edge, year-by-year consistency,
   recent-half (2021-2025) check for decay. Multiple-comparison discipline: hundreds of cells
   tested means top ROI cells are PLAUSIBLE, never CONFIRMED.
3. **Paper trade** — `src/build_form_watchlist.py` flags matching runners on race days;
   log paper stakes (100 JPY), settle against results. This is the out-of-sample filter
   backtests cannot provide.
4. **Real-money trial** — only after paper sample supports the edge, only with user approval,
   100 JPY stakes, one point per race.

## Status by edge family

| family | status | evidence |
|---|---|---|
| Static condition edges (surface/dist/class/sire/jockey...) | **dead** | 72,517 races, 0 BUY under gate (2026-06) |
| Place EV from win-derived probability | **dead** | ROI 0.13-0.74 all thresholds; adverse selection (docs/place_ev_validation.md) |
| Win-vs-place cross-pool mispricing | **dead** | encodes horse type, not mispricing; both pools efficient (docs/place_ev_validation.md) |
| Layoff bias (71-190d, 10-20x odds) | **decayed** | edge 1.19 (2005-15) -> 1.07 (2021-25), ROI 0.85 recent. Market corrected it. Useful as model feature, not as bet |
| Form3 low x layoff 71-190d, 10-20x | **decayed** | ROI 0.92 in 2021-2025 |
| **tailed_off x layoff 71-190d, 20-50x** | **paper trade** | n=4,206 edge 1.41 ROI 1.17 (21y); 2021-25 ROI 1.21 but 2016-20 negative; 349-cell selection risk |
| **form3 poor x layoff 36-70d, 20-50x** | **paper trade** | n=1,407 edge 1.68 ROI 1.29 (21y); ~60 bets/year, low power, 2024 spike is noise-sized |
| Late odds movement | **blocked on data** | needs multiple O1 snapshots per race; START COLLECTING on race days (snapshot every 10-15 min via scripts/export_jvrt_odds_for_races.ps1) |
| Same-day bias incremental value | untested as edge | implemented with shrinkage; needs multi-day intraday ablation |
| Jockey same-day form | untested | data available in same-day results |
| Weight change x layoff interaction | untested | horse_weight in SE; combine with form framework |

## Key structural findings (do not relearn these)

- The win market's residual biases are small (edge 1.1-1.2) and the takeout is 20%:
  breakeven needs edge >= ~1.25. Single features never reach it; only interactions might.
- Biases decay: whatever worked 2005-2015 is roughly half as strong 2021-2025.
  Any promoted edge needs ongoing decay monitoring.
- Favorite-longshot bias is alive and huge on the SHORT side (100x+ horses: edge 0.35-0.59)
  but unbettable directly (you cannot short a horse). Its only use: never bet extreme longshots,
  and it inflates apparent edges of anything correlated with mid-odds.

## Race-day operational additions

- Refresh same-day + recent SE results BEFORE running the watchlist so layoff features are
  accurate (watchlist warns with `data_gap` when history is stale).
- Collect 0B31 odds snapshots every 10-15 minutes per race (not just near cutoff) to build
  the late-odds-movement dataset — the most promising untested family.
- Paper-trade watchlist output: `outputs/paper_trades/form_watchlist_YYYYMMDD.csv`;
  settle after the day with results and append outcomes to the same file.
