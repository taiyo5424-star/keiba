"""オッズ⇔確率の変換と期待値(EV)計算。

パリミュチュエル方式では、確定オッズは投票総額から控除率を差し引いた
プールの分配比で決まる。オッズから逆算した「市場の暗黙確率」と、
自前モデルの推定確率の乖離が期待値の源泉になる。

用語:
- 暗黙確率 (implied probability): p_mkt = 払戻率 / オッズ(近似)
- オーバーラウンド除去: 全馬の 1/オッズ の合計で正規化した確率
- 期待値 (EV): EV = 推定確率 × オッズ。EV > 1 が期待値プラス。
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np


def implied_probability(odds: float, payout_rate: float = 0.80) -> float:
    """オッズ1点から市場の暗黙確率を求める(控除率調整込み)。

    パリミュチュエルでは オッズ ≒ 払戻率 / 投票シェア なので、
    投票シェア(=市場の暗黙確率)は 払戻率 / オッズ。
    """
    if odds <= 0:
        raise ValueError("odds must be positive")
    return min(1.0, payout_rate / odds)


def normalized_implied_probabilities(odds: Sequence[float]) -> np.ndarray:
    """レース全馬のオッズから、合計1に正規化した暗黙確率を求める。

    1/odds をオーバーラウンド(ブックの取り分+丸め)で正規化する。
    払戻率を知らなくても使える、レース内の相対確率。
    """
    arr = np.asarray(odds, dtype=float)
    if np.any(arr <= 0):
        raise ValueError("all odds must be positive")
    inv = 1.0 / arr
    return inv / inv.sum()


def expected_value(prob: float, odds: float) -> float:
    """1円賭けたときの期待払戻(EV)。EV > 1.0 が期待値プラス。"""
    if not 0.0 <= prob <= 1.0:
        raise ValueError("prob must be in [0, 1]")
    if odds <= 0:
        raise ValueError("odds must be positive")
    return prob * odds


def ev_table(
    probs: Sequence[float],
    odds: Sequence[float],
    names: Sequence[str] | None = None,
    min_ev: float = 0.0,
):
    """レース全馬の推定確率とオッズからEV一覧のDataFrameを作る。

    Args:
        probs: 自前モデルの推定確率(合計~1を推奨)。
        odds: 現在オッズ。
        names: 馬名(省略時は連番)。
        min_ev: この値以上のEVの行だけ返す(0で全馬)。

    Returns:
        columns = [name, prob, odds, market_prob, ev, edge] のDataFrame。
        edge = 推定確率 - 市場確率(正なら市場より強気)。
    """
    import pandas as pd

    probs_arr = np.asarray(probs, dtype=float)
    odds_arr = np.asarray(odds, dtype=float)
    if probs_arr.shape != odds_arr.shape:
        raise ValueError("probs and odds must have the same length")
    market = normalized_implied_probabilities(odds_arr)
    ev = probs_arr * odds_arr
    df = pd.DataFrame(
        {
            "name": list(names) if names is not None else [str(i + 1) for i in range(len(odds_arr))],
            "prob": probs_arr,
            "odds": odds_arr,
            "market_prob": market,
            "ev": ev,
            "edge": probs_arr - market,
        }
    )
    df = df[df["ev"] >= min_ev].sort_values("ev", ascending=False).reset_index(drop=True)
    return df


def breakeven_probability(odds: float) -> float:
    """このオッズで期待値トントンになる的中確率(=1/オッズ)。"""
    if odds <= 0:
        raise ValueError("odds must be positive")
    return 1.0 / odds


def synthetic_odds(odds_list: Sequence[float]) -> float:
    """複数点買いの合成オッズ。1/合成 = Σ(1/各オッズ)。

    資金を各点に均等リスクで配分したときの実効オッズで、
    点数を広げたときの期待値悪化を測る指標。
    """
    arr = np.asarray(odds_list, dtype=float)
    if np.any(arr <= 0):
        raise ValueError("all odds must be positive")
    return 1.0 / float(np.sum(1.0 / arr))
