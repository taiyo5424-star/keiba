# Data contract

The paid JV-Link layer exports normalized files. Model and EV scripts consume only these files.

## `data/jra_van_exports/races.csv`

- `race_id`: stable race key
- `race_date`: ISO date
- `venue`: racecourse
- `race_no`: race number
- `surface`: `turf` or `dirt`
- `distance`: meters
- `going`: race-day going available before prediction
- `available_at`: timestamp when the row became usable

## `data/jra_van_exports/starts.csv`

One row per starter.

- Include only fields available at the prediction timestamp.
- Keep post-race fields such as `finish_position` out of model features unless building settled historical labels.
- Keep final odds out of model features unless the same timestamp is available in live operation.

## `data/jra_van_exports/odds_snapshots.csv`

One row per odds observation.

- `observed_at` is mandatory.
- Use the same odds timestamp in backtests that live operation would have used.
- `is_final=true` is for settlement and CLV, not for pre-race prediction.

## `data/bet_log.csv`

Append actual or paper bets after purchase decision.

- `expected_profit = stake * ev_per_yen`
- `clv = purchase_odds / closing_odds` for decimal odds
- A losing bet with positive CLV can still be a good decision.
