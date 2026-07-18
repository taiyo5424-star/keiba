"""単勝確率から連系馬券(馬単・三連単等)の的中確率を導く Harville 公式と指数補正。

素の Harville 公式:
    P(i→j) = p_i · p_j / (1 - p_i)
    P(i→j→k) = p_i · p_j/(1-p_i) · p_k/(1-p_i-p_j)

は「人気薄が実際より2着・3着に来にくい」と仮定してしまう既知のバイアスを
持つ(実データでは人気薄はHarville予測より2・3着に来やすい)。
Benter (1994) は2着・3着の条件付き確率を指数で減衰させる補正を用いた:

    2着分布: p_j^γ を正規化   (香港データで γ ≈ 0.81)
    3着分布: p_k^δ を正規化   (同 δ ≈ 0.65)

γ, δ は市場・時代でパラメータが変わるため、対象データで再推定すること。
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np


def _powered_conditional(p: np.ndarray, exclude: list[int], exponent: float) -> np.ndarray:
    """除外馬を除き p^exponent を正規化した条件付き分布を返す。"""
    w = p.copy() ** exponent
    w[exclude] = 0.0
    total = w.sum()
    if total <= 0:
        raise ValueError("no probability mass left after exclusions")
    return w / total


def exacta_probability(
    win_probs: Sequence[float],
    first: int,
    second: int,
    gamma: float = 1.0,
) -> float:
    """馬単 (first→second) の的中確率。gamma=1.0 で素のHarville。"""
    p = np.asarray(win_probs, dtype=float)
    if first == second:
        raise ValueError("first and second must differ")
    cond2 = _powered_conditional(p, [first], gamma)
    return float(p[first] * cond2[second])


def trifecta_probability(
    win_probs: Sequence[float],
    first: int,
    second: int,
    third: int,
    gamma: float = 1.0,
    delta: float = 1.0,
) -> float:
    """三連単 (first→second→third) の的中確率。

    gamma/delta < 1 で人気薄の2着・3着確率を押し上げる(実データ寄り)。
    """
    if len({first, second, third}) != 3:
        raise ValueError("first/second/third must be distinct")
    p = np.asarray(win_probs, dtype=float)
    cond2 = _powered_conditional(p, [first], gamma)
    cond3 = _powered_conditional(p, [first, second], delta)
    return float(p[first] * cond2[second] * cond3[third])


def quinella_probability(
    win_probs: Sequence[float],
    a: int,
    b: int,
    gamma: float = 1.0,
) -> float:
    """馬連 {a, b} の的中確率(= 馬単a→b + 馬単b→a)。"""
    return exacta_probability(win_probs, a, b, gamma) + exacta_probability(
        win_probs, b, a, gamma
    )


def trio_probability(
    win_probs: Sequence[float],
    a: int,
    b: int,
    c: int,
    gamma: float = 1.0,
    delta: float = 1.0,
) -> float:
    """三連複 {a, b, c} の的中確率(6通りの三連単の和)。"""
    from itertools import permutations

    return sum(
        trifecta_probability(win_probs, i, j, k, gamma, delta)
        for i, j, k in permutations((a, b, c))
    )


def fit_gamma(
    races: Sequence[tuple[Sequence[float], int, int]],
    grid: Sequence[float] | None = None,
) -> float:
    """(win_probs, 1着馬, 2着馬) の履歴から γ をグリッド最尤推定する。"""
    if grid is None:
        grid = np.arange(0.4, 1.21, 0.01)
    best_g, best_ll = 1.0, -np.inf
    for g in grid:
        ll = 0.0
        for probs, first, second in races:
            p = np.asarray(probs, dtype=float)
            cond2 = _powered_conditional(p, [first], g)
            ll += np.log(max(cond2[second], 1e-300))
        if ll > best_ll:
            best_g, best_ll = float(g), ll
    return best_g
