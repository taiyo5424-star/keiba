"""ケリー基準による資金配分。

- kelly_fraction: 独立した単一の賭けに対する古典的ケリー
- kelly_exclusive_outcomes: 同一レース内(排反事象)の複数馬への
  同時賭けに対する最適配分(Smoczynski & Tomkins 2010 の陽解法)

実運用ではフルケリーは推定誤差に対して脆弱なので、
fraction 引数で 1/4〜1/2 ケリーに落とすことを推奨。
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np


def kelly_fraction(prob: float, odds: float, fraction: float = 1.0) -> float:
    """単一の賭けに対するケリー賭け比率(資金に対する割合)。

    f* = (b*p - q) / b,  b = odds - 1, q = 1 - p
    期待値がプラスでなければ 0 を返す。

    Args:
        prob: 的中確率の推定値。
        odds: 払戻オッズ(賭け金込み倍率。単勝3.0倍なら3.0)。
        fraction: フラクショナルケリー係数(0.25で1/4ケリー)。
    """
    if not 0.0 <= prob <= 1.0:
        raise ValueError("prob must be in [0, 1]")
    if odds <= 1.0:
        return 0.0
    b = odds - 1.0
    f = (b * prob - (1.0 - prob)) / b
    return max(0.0, f * fraction)


def kelly_exclusive_outcomes(
    probs: Sequence[float],
    odds: Sequence[float],
    fraction: float = 1.0,
) -> np.ndarray:
    """同一レース内の排反な複数馬に同時に賭けるときの最適ケリー配分。

    Smoczynski & Tomkins (2010) の陽解法:
    期待収益率 p_i * o_i の降順に馬を並べ、賭け対象集合 S を
    貪欲に拡大しながら予約率 R(S) = (1 - Σ_{i∈S} p_i) / (1 - Σ_{i∈S} 1/o_i)
    を計算し、p_i * o_i > R(S) が成り立つ間だけ集合に加える。
    最適賭け金は f_i = p_i - R(S) / o_i。

    Returns:
        各馬への賭け比率(資金に対する割合)の配列。賭けない馬は0。
    """
    p = np.asarray(probs, dtype=float)
    o = np.asarray(odds, dtype=float)
    if p.shape != o.shape:
        raise ValueError("probs and odds must have the same length")
    if np.any(p < 0) or p.sum() > 1.0 + 1e-9:
        raise ValueError("probs must be non-negative and sum to at most 1")
    if np.any(o <= 0):
        raise ValueError("all odds must be positive")

    n = len(p)
    order = np.argsort(-(p * o))  # 期待収益率の降順
    in_set = np.zeros(n, dtype=bool)
    sum_p = 0.0
    sum_inv_o = 0.0
    reserve = 1.0  # R(空集合) = 1

    for idx in order:
        if p[idx] * o[idx] <= reserve:
            break  # これ以降の馬はすべて期待収益率が予約率以下
        # 集合に加えた場合の予約率を計算
        new_sum_p = sum_p + p[idx]
        new_sum_inv_o = sum_inv_o + 1.0 / o[idx]
        if new_sum_inv_o >= 1.0:
            # 全対象の合成オッズが1未満 → これ以上加えると裁定不能
            break
        new_reserve = (1.0 - new_sum_p) / (1.0 - new_sum_inv_o)
        in_set[idx] = True
        sum_p, sum_inv_o, reserve = new_sum_p, new_sum_inv_o, new_reserve

    f = np.zeros(n)
    if in_set.any():
        f[in_set] = p[in_set] - reserve / o[in_set]
        f = np.clip(f, 0.0, None)
    return f * fraction


def expected_log_growth(
    probs: Sequence[float],
    odds: Sequence[float],
    stakes: Sequence[float],
) -> float:
    """排反事象への賭け配分の期待対数成長率 E[log(資産倍率)]。

    残り確率(どの賭け馬も勝たない)では賭け金だけ失う。
    配分の良し悪しの比較・検証用。
    """
    p = np.asarray(probs, dtype=float)
    o = np.asarray(odds, dtype=float)
    f = np.asarray(stakes, dtype=float)
    total_stake = f.sum()
    if total_stake >= 1.0:
        raise ValueError("total stake must be < 1")
    growth = 0.0
    for i in range(len(p)):
        if p[i] > 0:
            wealth = 1.0 - total_stake + f[i] * o[i]
            growth += p[i] * np.log(wealth)
    p_none = 1.0 - p.sum()
    if p_none > 0:
        growth += p_none * np.log(1.0 - total_stake)
    return float(growth)
