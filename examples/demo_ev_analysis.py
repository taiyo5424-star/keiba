"""期待値分析のデモ。

架空の1レースについて、自前モデルの推定確率と現在オッズから
EV一覧とケリー配分を計算する使用例。

実行: python examples/demo_ev_analysis.py
"""

import numpy as np

from keiba.ev import ev_table, synthetic_odds
from keiba.kelly import kelly_exclusive_outcomes

# --- 架空レース: 10頭立て、自前モデルの勝率推定と単勝オッズ ---
names = [f"{i+1}番" for i in range(10)]
model_probs = [0.28, 0.18, 0.14, 0.10, 0.08, 0.07, 0.06, 0.04, 0.03, 0.02]
odds = [2.4, 5.1, 8.0, 11.5, 13.0, 9.8, 22.0, 35.0, 48.0, 80.0]

print("=== EVテーブル(EV降順) ===")
table = ev_table(model_probs, odds, names=names)
print(table.to_string(index=False, float_format=lambda x: f"{x:.3f}"))

print("\n=== EV >= 1.1 の馬のみ ===")
value_bets = ev_table(model_probs, odds, names=names, min_ev=1.1)
print(value_bets.to_string(index=False, float_format=lambda x: f"{x:.3f}"))

print("\n=== 1/4ケリーによる資金配分 ===")
f = kelly_exclusive_outcomes(model_probs, odds, fraction=0.25)
for name, frac, o in zip(names, f, odds):
    if frac > 0:
        print(f"  {name}: 資金の {frac*100:.2f}% (オッズ {o})")
total = f.sum()
print(f"  合計投下率: {total*100:.2f}%")

targets = [o for o, frac in zip(odds, f) if frac > 0]
if len(targets) >= 2:
    print(f"\n  参考: 対象{len(targets)}点の合成オッズ = {synthetic_odds(targets):.2f}倍")
