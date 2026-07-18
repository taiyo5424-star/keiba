"""予測確率の較正(calibration)評価。

期待値ベッティングでは「勝つ馬を当てる」ことより「確率を正しく見積もる」
ことが重要。モデルの推定確率が実際の的中頻度と一致しているか
(較正されているか)を必ず検証すること。

- brier_score / log_loss: 確率予測の総合精度
- reliability_table: 予測確率ビンごとの実測的中率(較正曲線の素データ)
- roi_by_bin: 予測確率やEVのビンごとの回収率(戦略の実弾検証)
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd


def brier_score(probs: Sequence[float], outcomes: Sequence[int]) -> float:
    """Brierスコア(小さいほど良い)。outcomes は 0/1。"""
    p = np.asarray(probs, dtype=float)
    y = np.asarray(outcomes, dtype=float)
    return float(np.mean((p - y) ** 2))


def log_loss(probs: Sequence[float], outcomes: Sequence[int], eps: float = 1e-12) -> float:
    """対数損失(小さいほど良い)。"""
    p = np.clip(np.asarray(probs, dtype=float), eps, 1.0 - eps)
    y = np.asarray(outcomes, dtype=float)
    return float(-np.mean(y * np.log(p) + (1.0 - y) * np.log(1.0 - p)))


def reliability_table(
    probs: Sequence[float],
    outcomes: Sequence[int],
    n_bins: int = 10,
) -> pd.DataFrame:
    """予測確率をビン分割し、ビンごとの平均予測確率と実測的中率を返す。

    平均予測確率と実測的中率が近ければ較正されている。
    実測 < 予測 のビンは過大評価(そのゾーンの賭けは危険)。
    """
    p = np.asarray(probs, dtype=float)
    y = np.asarray(outcomes, dtype=float)
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    idx = np.clip(np.digitize(p, bins) - 1, 0, n_bins - 1)
    rows = []
    for b in range(n_bins):
        mask = idx == b
        if not mask.any():
            continue
        rows.append(
            {
                "bin_low": bins[b],
                "bin_high": bins[b + 1],
                "n": int(mask.sum()),
                "mean_pred": float(p[mask].mean()),
                "hit_rate": float(y[mask].mean()),
            }
        )
    df = pd.DataFrame(rows)
    if not df.empty:
        df["gap"] = df["hit_rate"] - df["mean_pred"]
    return df


def roi_by_bin(
    df: pd.DataFrame,
    bin_col: str,
    odds_col: str = "odds",
    outcome_col: str = "won",
    bins: Sequence[float] | None = None,
) -> pd.DataFrame:
    """任意の列(EV、予測確率、オッズ帯など)でビン分割した回収率を集計する。

    各行は1点の賭け(均等買い想定)。回収率 = Σ(的中オッズ) / 賭け点数。
    """
    work = df.copy()
    if bins is not None:
        work["_bin"] = pd.cut(work[bin_col], bins=list(bins))
    else:
        work["_bin"] = pd.qcut(work[bin_col], q=10, duplicates="drop")
    grouped = work.groupby("_bin", observed=True)
    out = grouped.apply(
        lambda g: pd.Series(
            {
                "n": len(g),
                "hit_rate": g[outcome_col].mean(),
                "roi": (g[outcome_col] * g[odds_col]).sum() / len(g),
            }
        ),
        include_groups=False,
    ).reset_index(names=bin_col + "_bin")
    return out
