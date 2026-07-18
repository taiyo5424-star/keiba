"""モデル確率と市場(公衆)確率のロジット結合 — Benter (1994) の二段階推定。

ファンダメンタルモデル単体の勝率推定は「公衆オッズと乖離する側で
系統的に外れる」バイアスを持つ(Benter 1994)。そのままEV計算に使うと
アドバンテージを過大評価する。条件付きロジットで市場確率と結合し、
較正された最終確率を得るのが実証済みの手順:

    c_i = f_i^α · π_i^β / Σ_j f_j^α · π_j^β

f: モデル確率, π: 市場確率(オッズ由来)。α, β は過去レースの
多項ロジット最尤推定で求める。β が大きいほど市場情報の寄与が大きい。
モデルに市場を超える情報が全く無ければ α→0 に潰れる。
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np


def blend_probabilities(
    model_probs: Sequence[float],
    market_probs: Sequence[float],
    alpha: float,
    beta: float,
    eps: float = 1e-12,
) -> np.ndarray:
    """1レース分のモデル確率と市場確率を指数重みで結合し正規化する。"""
    f = np.clip(np.asarray(model_probs, dtype=float), eps, 1.0)
    pi = np.clip(np.asarray(market_probs, dtype=float), eps, 1.0)
    if f.shape != pi.shape:
        raise ValueError("model_probs and market_probs must have the same length")
    w = np.exp(alpha * np.log(f) + beta * np.log(pi))
    return w / w.sum()


def fit_blend_weights(
    races: Sequence[tuple[Sequence[float], Sequence[float], int]],
    n_iter: int = 500,
    lr: float = 0.5,
    eps: float = 1e-12,
) -> tuple[float, float]:
    """過去レースから (α, β) を多項ロジット最尤推定する。

    Args:
        races: (model_probs, market_probs, winner_index) のリスト。
        n_iter: 勾配上昇の反復回数。
        lr: 学習率。

    Returns:
        (alpha, beta)。
    """
    prepared = []
    for f, pi, w in races:
        lf = np.log(np.clip(np.asarray(f, dtype=float), eps, 1.0))
        lpi = np.log(np.clip(np.asarray(pi, dtype=float), eps, 1.0))
        prepared.append((lf, lpi, int(w)))

    alpha, beta = 0.5, 0.5
    n = len(prepared)
    for _ in range(n_iter):
        ga = gb = 0.0
        for lf, lpi, w in prepared:
            z = alpha * lf + beta * lpi
            z -= z.max()
            p = np.exp(z)
            p /= p.sum()
            # ∂logL/∂α = lf_w - E_p[lf]
            ga += lf[w] - float(p @ lf)
            gb += lpi[w] - float(p @ lpi)
        alpha += lr * ga / n
        beta += lr * gb / n
    return float(alpha), float(beta)


def log_likelihood(
    races: Sequence[tuple[Sequence[float], Sequence[float], int]],
    alpha: float,
    beta: float,
) -> float:
    """与えた (α, β) での平均対数尤度。モデル比較(ΔR²相当)に使う。"""
    total = 0.0
    for f, pi, w in races:
        p = blend_probabilities(f, pi, alpha, beta)
        total += float(np.log(max(p[int(w)], 1e-300)))
    return total / len(races)
