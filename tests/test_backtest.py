import numpy as np
import pandas as pd
import pytest

from keiba.backtest import backtest_win_bets
from keiba.calibration import brier_score, log_loss, reliability_table, roi_by_bin


def _synthetic_dataset(n_races=500, seed=42, edge=0.0):
    """較正された確率と、payout 0.8 のパリミュチュエルオッズを持つ合成データ。

    edge > 0 なら、モデル確率が市場より正確という設定を模擬する。
    """
    rng = np.random.default_rng(seed)
    rows = []
    for rid in range(n_races):
        n = 10
        strength = rng.gamma(2.0, 1.0, size=n)
        true_p = strength / strength.sum()
        # 市場はノイズを含んだ確率でオッズを形成
        noise = rng.gamma(50, 1 / 50, size=n)
        market_p = true_p * noise
        market_p = market_p / market_p.sum()
        odds = 0.8 / market_p
        # モデルは真の確率に(edgeの度合いで)近い推定を持つ
        model_p = edge * true_p + (1 - edge) * market_p
        winner = rng.choice(n, p=true_p)
        for i in range(n):
            rows.append(
                {
                    "race_id": rid,
                    "prob": model_p[i],
                    "odds": odds[i],
                    "won": int(i == winner),
                }
            )
    return pd.DataFrame(rows)


def test_backtest_market_probs_lose_takeout():
    """市場確率そのままで全点買い → 回収率は払戻率(~0.8)に収束する。"""
    df = _synthetic_dataset(n_races=800, edge=0.0)
    res = backtest_win_bets(df, min_ev=0.0, staking="flat", flat_stake=0.001)
    assert res.n_bets == len(df)
    assert 0.7 < res.roi < 0.9


def test_backtest_with_true_edge_beats_market():
    """真の確率を知っているモデル(edge=1)はEV>1フィルタでプラス収支になる。"""
    df = _synthetic_dataset(n_races=800, edge=1.0)
    res = backtest_win_bets(df, min_ev=1.05, staking="flat", flat_stake=0.001)
    assert res.n_bets > 100
    assert res.roi > 1.0


def test_backtest_kelly_grows_bankroll():
    df = _synthetic_dataset(n_races=800, edge=1.0)
    res = backtest_win_bets(df, min_ev=1.0, staking="kelly", kelly_fraction=0.25)
    assert res.final_bankroll > 1.0
    assert -1.0 <= res.max_drawdown <= 0.0


def test_backtest_curve_length():
    df = _synthetic_dataset(n_races=50)
    res = backtest_win_bets(df, min_ev=1.0)
    assert res.n_races == 50
    assert len(res.bankroll_curve) == 50


def test_calibration_metrics():
    rng = np.random.default_rng(0)
    p = rng.uniform(0.05, 0.95, size=5000)
    y = (rng.uniform(size=5000) < p).astype(int)  # 完全較正
    table = reliability_table(p, y, n_bins=10)
    # 較正されていれば各ビンの gap は小さい
    assert table["gap"].abs().max() < 0.08
    assert brier_score(p, y) < brier_score(1 - p, y)
    assert log_loss(p, y) < log_loss(np.full_like(p, 0.5), y) + 0.1


def test_roi_by_bin():
    df = _synthetic_dataset(n_races=300, edge=1.0)
    df["ev"] = df["prob"] * df["odds"]
    out = roi_by_bin(df, bin_col="ev", bins=[0, 0.8, 1.0, 1.2, 10.0])
    assert set(out.columns) >= {"n", "hit_rate", "roi"}
    # EVが高いビンほど回収率が高い傾向(最上位ビン > 最下位ビン)
    assert out.iloc[-1]["roi"] > out.iloc[0]["roi"]
