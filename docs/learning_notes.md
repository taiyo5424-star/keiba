
## 2004 宝塚記念 blind EV review

- Prediction policy: win bets only, final odds + pre-race historical market-edge features, target result hidden.
- Decision: no bet.
- Actual winner: 15 タップダンスシチー at win odds 3.5.
- Paper stake: 0, return: 0, profit: 0, ROI: 0.0000.
- Self-grade: good risk control. The model avoided a false longshot BUY after switching from raw jockey/trainer win rates to market-relative edge.
- Learning: raw win rates by jockey/trainer are not valid edge signals because they mostly proxy horse quality. Use excess performance versus market-implied expectation and apply shrinkage.
- Next improvement: add race-class and distance/surface-specific calibration, then validate over many historical races before trusting any positive EV.

## 2004 安田記念 blind EV review

- Prediction policy: win bets only, final odds + pre-race historical market-edge features, target result hidden.
- Decision: no bet.
- Actual winner: 14 ツルマルボーイ at win odds 11.3.
- Paper stake: 0, return: 0, profit: 0, ROI: 0.0000.
- Self-grade: good risk control. The model avoided a false longshot BUY after switching from raw jockey/trainer win rates to market-relative edge.
- Learning: raw win rates by jockey/trainer are not valid edge signals because they mostly proxy horse quality. Use excess performance versus market-implied expectation and apply shrinkage.
- Next improvement: add race-class and distance/surface-specific calibration, then validate over many historical races before trusting any positive EV.

## 2004 日本ダービー blind EV review

- Prediction policy: win bets only, final odds + pre-race historical market-edge features, target result hidden.
- Decision: no bet.
- Actual winner: 12 キングカメハメハ at win odds 2.6.
- Paper stake: 0, return: 0, profit: 0, ROI: 0.0000.
- Self-grade: good risk control. The model avoided a false longshot BUY after switching from raw jockey/trainer win rates to market-relative edge.
- Learning: raw win rates by jockey/trainer are not valid edge signals because they mostly proxy horse quality. Use excess performance versus market-implied expectation and apply shrinkage.
- Next improvement: add race-class and distance/surface-specific calibration, then validate over many historical races before trusting any positive EV.

## 2004 スプリンターズS blind EV review

- Prediction policy: win bets only, final odds + pre-race historical market-edge features, target result hidden.
- Decision: no bet.
- Actual winner: 05 カルストンライトオ at win odds 8.5.
- Paper stake: 0, return: 0, profit: 0, ROI: 0.0000.
- Self-grade: good risk control. The model avoided a false longshot BUY after switching from raw jockey/trainer win rates to market-relative edge.
- Learning: raw win rates by jockey/trainer are not valid edge signals because they mostly proxy horse quality. Use excess performance versus market-implied expectation and apply shrinkage.
- Next improvement: add race-class and distance/surface-specific calibration, then validate over many historical races before trusting any positive EV.

## 2004 天皇賞秋 blind EV review

- Prediction policy: win bets only, final odds + pre-race historical market-edge features, target result hidden.
- Decision: no bet.
- Actual winner: 13 ゼンノロブロイ at win odds 3.4.
- Paper stake: 0, return: 0, profit: 0, ROI: 0.0000.
- Self-grade: good risk control. The model avoided a false longshot BUY after switching from raw jockey/trainer win rates to market-relative edge.
- Learning: raw win rates by jockey/trainer are not valid edge signals because they mostly proxy horse quality. Use excess performance versus market-implied expectation and apply shrinkage.
- Next improvement: add race-class and distance/surface-specific calibration, then validate over many historical races before trusting any positive EV.

## 2004 有馬記念 blind EV review

- Prediction policy: win bets only, final odds + pre-race historical market-edge features, target result hidden.
- Decision: no bet.
- Actual winner: 01 ゼンノロブロイ at win odds 2.0.
- Paper stake: 0, return: 0, profit: 0, ROI: 0.0000.
- Self-grade: good risk control. The model avoided a false longshot BUY after switching from raw jockey/trainer win rates to market-relative edge.
- Learning: raw win rates by jockey/trainer are not valid edge signals because they mostly proxy horse quality. Use excess performance versus market-implied expectation and apply shrinkage.
- Next improvement: add race-class and distance/surface-specific calibration, then validate over many historical races before trusting any positive EV.

## 2026-07-07 place EV validation (no-leakage, real payouts)

- Built place validation set from raw JV dump: 2,112 races, final O1 place odds + HR payouts, 2025-06-14..2026-01-18.
- Win-market-anchored place probability is well calibrated globally (even at win odds 100+: pred 2.0% vs actual 2.1%).
- But selecting on high estimated place EV is adversely biased: EV>=1.10 picks predicted 13.3% place rate, actual 7.0%. ROI fell from 0.74 (threshold 0.90) to 0.13 (threshold 1.20) — higher "EV" meant worse returns.
- Learning: when a derived probability is combined with ANOTHER pool's odds, apparent mispricing is usually the other pool's information, not an edge. Calibration on the whole population does not protect against adverse selection in the tail you bet on. Any cross-pool EV signal must be backtested with realized payouts before trusting it.
- Decision: place BUY gate locked (PASS always) in src/score_live_place_ev.py; rankings still produced.

## 2026-07-07 inverse place-market signal test (win-bet filter): refuted

- Hypothesis: place market bullish (place odds low vs win-derived expectation) -> win outperformance. Result: opposite. Bullish-place horses place more (edge 1.31) but win LESS than the win market implies (edge 0.90, win ROI 0.42).
- Learning: cross-pool odds disagreement encodes horse type (consistent placer vs win-skewed), not mispricing. Both pools are internally efficient; their difference is real information about outcome variance, not an arbitrage.
- Salvage: place-market implied probability improves place RANKINGS; added to score_live_place_ev.py output (place_probability_market, place_market_signal) for audit only.

## 2026-07-08 horse-form feature ablation (21-year rolling, no leakage)

- Layoff 71-190d at 10-20x odds: edge 1.156, positive in 21/21 years — a real, mechanistic market bias. BUT decaying: 1.19 (2005-15) -> 1.07 (2021-25). The market corrects known biases; assume any published-style edge is half-strength today.
- Breakeven arithmetic: JRA win takeout ~20% means edge >= ~1.25 required. Single history features top out ~1.19. Only feature INTERACTIONS can plausibly cross breakeven.
- Two interaction cells promoted to PAPER TRADE only (tailed_off x 71-190d x 20-50x; form3 poor x 36-70d x 20-50x). With 349 cells tested, their backtest ROI is PLAUSIBLE, not CONFIRMED — fresh out-of-sample paper results are the deciding evidence.
- Learning: multiple-comparison discipline is the difference between a system and a story. Rank hypotheses by mechanism + year-consistency + recent-half survival, then demand live paper confirmation before money.
