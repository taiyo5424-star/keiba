# EV-first operation

The target is not to maximize action. The target is to maximize verified expected value.

## Daily flow

1. Import or update JRA-VAN data.
2. Generate model probabilities for available races.
3. Pull or manually enter current odds.
4. Run `src/generate_bets.py`.
5. Buy only rows marked `BUY`.
6. After results are known, append the settled rows to historical data.
7. Run `src/backtest.py` and compare expected profit with actual profit.

## Commands

```powershell
& "C:\Users\admin\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" src/baseline_model.py --predictions outputs/model_predictions_example.csv
& "C:\Users\admin\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" src/generate_bets.py
& "C:\Users\admin\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" src/settle_bets.py --input data/bet_log_example.csv
& "C:\Users\admin\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" src/backtest.py
```

## Bet filter

A bet is eligible only when all are true:

- model probability is available
- current odds are available
- `probability * odds - 1 >= min_ev_per_yen`
- recommended stake is at least one stake unit

## Tracking

Track these separately:

- expected profit
- actual profit
- closing-line value
- number of bets
- hit rate
- ROI
- maximum drawdown

Short-term actual profit is noisy. Expected profit quality is judged by calibration and long-run backtest behavior.
