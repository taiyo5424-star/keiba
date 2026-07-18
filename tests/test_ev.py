import numpy as np
import pytest

from keiba.ev import (
    breakeven_probability,
    ev_table,
    expected_value,
    implied_probability,
    normalized_implied_probabilities,
    synthetic_odds,
)
from keiba.takeout import payout_rate, takeout_rate


def test_payout_rates_jra():
    assert payout_rate("win") == 0.80
    assert payout_rate("trifecta") == 0.725
    assert payout_rate("win5") == 0.70
    assert takeout_rate("win") == pytest.approx(0.20)


def test_payout_rate_overrides():
    assert payout_rate("trifecta", organizer="nar", overrides={"trifecta": 0.70}) == 0.70


def test_payout_rates_nar():
    # 地方標準: 馬連75%・三連複72.5%(JRAより不利)
    assert payout_rate("quinella", organizer="nar") == 0.750
    assert payout_rate("trio", organizer="nar") == 0.725
    # ホッカイドウ: ワイド80%、三連単70%
    assert payout_rate("wide", organizer="hokkaido") == 0.800
    assert payout_rate("trifecta", organizer="hokkaido") == 0.700
    # 高知ファイナルレース三連単77%
    assert payout_rate("trifecta", organizer="kochi_final_race") == 0.770


def test_unknown_bet_type():
    with pytest.raises(KeyError):
        payout_rate("nope")


def test_implied_probability():
    # 単勝2.0倍 → 市場確率 0.8/2.0 = 40%
    assert implied_probability(2.0, 0.80) == pytest.approx(0.40)
    # 極端な低オッズは1.0でクリップ
    assert implied_probability(0.5, 0.80) == 1.0


def test_normalized_probs_sum_to_one():
    probs = normalized_implied_probabilities([2.0, 4.0, 8.0, 8.0])
    assert probs.sum() == pytest.approx(1.0)
    assert probs[0] > probs[1] > probs[2]


def test_expected_value():
    assert expected_value(0.25, 5.0) == pytest.approx(1.25)  # EVプラス
    assert expected_value(0.10, 5.0) == pytest.approx(0.50)  # EVマイナス


def test_breakeven():
    assert breakeven_probability(4.0) == pytest.approx(0.25)


def test_synthetic_odds():
    # 同オッズ2点なら合成は半分
    assert synthetic_odds([4.0, 4.0]) == pytest.approx(2.0)


def test_ev_table_ranks_by_ev():
    df = ev_table(
        probs=[0.40, 0.30, 0.20, 0.10],
        odds=[2.0, 5.0, 6.0, 20.0],
        names=["A", "B", "C", "D"],
    )
    assert list(df.columns) == ["name", "prob", "odds", "market_prob", "ev", "edge"]
    assert df.iloc[0]["ev"] >= df.iloc[-1]["ev"]
    # D: 0.10*20 = 2.0 が最大EV
    assert df.iloc[0]["name"] == "D"


def test_ev_table_min_ev_filter():
    df = ev_table(probs=[0.5, 0.1], odds=[1.5, 3.0], min_ev=1.0)
    assert len(df) == 0  # 0.75, 0.30 とも1.0未満
