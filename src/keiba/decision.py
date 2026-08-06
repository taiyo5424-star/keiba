"""ベット意思決定エンジン — 結合確率+現在オッズ → 発注リスト。

方針(docs/strategy.md):
- EV = 結合確率 × オッズ が閾値以上の馬券のみ対象
- 配分は同一レース内排反ケリー × フラクション(既定1/4)
- 資金・リスク上限を多層で強制(1点上限・1レース上限・オッズ帯フィルタ)
- 賭け金は投票単位(100円)に切り捨て。単位未満は賭けない

このモジュールは「何をいくら買うか」の決定だけを行い、
実際の発注は execution.py(既定はペーパートレード)が担う。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from collections.abc import Sequence

import numpy as np

from keiba.kelly import kelly_exclusive_outcomes


@dataclass(frozen=True)
class BetOrder:
    """1点の発注。selection は単勝なら馬番文字列(例 '5')。"""

    race_id: str
    bet_type: str
    selection: str
    stake: int          # 円(投票単位に丸め済み)
    prob: float         # 自己推定確率(結合後)
    odds: float         # 判断時点のオッズ
    ev: float           # prob * odds


@dataclass
class DecisionPolicy:
    """リスク管理パラメータ。全て「超えたら賭けない/削る」方向に働く。"""

    min_ev: float = 1.05                 # EV閾値(推定誤差マージン込みで1.0より上)
    kelly_fraction: float = 0.25         # フラクショナルケリー係数
    unit: int = 100                      # 投票単位(円)
    max_stake_per_bet_frac: float = 0.01     # 1点あたり資金比率上限
    max_stake_per_race_frac: float = 0.03    # 1レース合計の資金比率上限
    min_odds: float = 1.5                # これ未満の低オッズは対象外(妙味が薄い)
    max_odds: float = 100.0              # これ超の大穴は対象外(確率推定が不安定)
    min_prob: float = 0.005              # 推定確率の下限(較正外領域を避ける)


def decide_win_bets(
    race_id: str,
    probs: Sequence[float],
    odds: Sequence[float],
    bankroll: float,
    policy: DecisionPolicy | None = None,
    horse_nos: Sequence[int] | None = None,
) -> list[BetOrder]:
    """1レースの単勝発注を決定する。

    Args:
        probs: 結合済み確率(blend.py の出力。モデル単体の確率を渡さないこと)。
        odds: 判断時点で購入可能なオッズ(確定オッズではない)。
        bankroll: 現在資金(円)。
        horse_nos: 馬番(省略時は 1..n)。

    Returns:
        発注リスト(条件を満たす馬券が無ければ空)。
    """
    policy = policy or DecisionPolicy()
    p = np.asarray(probs, dtype=float)
    o = np.asarray(odds, dtype=float)
    if p.shape != o.shape:
        raise ValueError("probs and odds must have the same length")
    if bankroll <= 0:
        return []
    nos = list(horse_nos) if horse_nos is not None else list(range(1, len(p) + 1))

    ev = p * o
    eligible = (
        (ev >= policy.min_ev)
        & (o >= policy.min_odds)
        & (o <= policy.max_odds)
        & (p >= policy.min_prob)
    )
    if not eligible.any():
        return []

    # 対象馬だけで排反ケリー配分(非対象馬の確率は配分対象から外す)
    f = np.zeros(len(p))
    f[eligible] = kelly_exclusive_outcomes(
        p[eligible], o[eligible], fraction=policy.kelly_fraction
    )

    # 上限適用: 1点上限 → レース合計上限(比例縮小)
    f = np.minimum(f, policy.max_stake_per_bet_frac)
    total = f.sum()
    if total > policy.max_stake_per_race_frac:
        f *= policy.max_stake_per_race_frac / total

    orders: list[BetOrder] = []
    for i in range(len(p)):
        if f[i] <= 0:
            continue
        stake = int(f[i] * bankroll // policy.unit) * policy.unit
        if stake < policy.unit:
            continue
        orders.append(
            BetOrder(
                race_id=race_id,
                bet_type="win",
                selection=str(nos[i]),
                stake=stake,
                prob=float(p[i]),
                odds=float(o[i]),
                ev=float(ev[i]),
            )
        )
    return orders
