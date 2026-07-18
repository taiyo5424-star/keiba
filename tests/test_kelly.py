import numpy as np
import pytest

from keiba.kelly import expected_log_growth, kelly_exclusive_outcomes, kelly_fraction


def test_kelly_single_positive_edge():
    # p=0.5, odds=3.0 → b=2, f* = (2*0.5 - 0.5)/2 = 0.25
    assert kelly_fraction(0.5, 3.0) == pytest.approx(0.25)


def test_kelly_single_no_edge():
    # EVちょうど1.0 → 賭けない
    assert kelly_fraction(0.5, 2.0) == 0.0
    # EVマイナス → 賭けない
    assert kelly_fraction(0.1, 2.0) == 0.0


def test_kelly_fractional():
    full = kelly_fraction(0.5, 3.0, fraction=1.0)
    quarter = kelly_fraction(0.5, 3.0, fraction=0.25)
    assert quarter == pytest.approx(full * 0.25)


def test_kelly_exclusive_no_positive_ev():
    # 全馬EVマイナスなら何も賭けない
    f = kelly_exclusive_outcomes([0.3, 0.3], [2.0, 2.0])
    assert np.allclose(f, 0.0)


def test_kelly_exclusive_single_dominant():
    # 1頭だけ大きなエッジ → その馬だけに賭ける
    f = kelly_exclusive_outcomes([0.5, 0.1, 0.1], [3.0, 3.0, 3.0])
    assert f[0] > 0
    assert f[1] == 0 and f[2] == 0


def test_kelly_exclusive_reduces_to_single_kelly():
    # 賭け対象が1頭のときは単一ケリーと一致するはず
    f = kelly_exclusive_outcomes([0.5, 0.0], [3.0, 100.0])
    assert f[0] == pytest.approx(kelly_fraction(0.5, 3.0), abs=1e-9)


def test_kelly_exclusive_is_log_optimal():
    """陽解法の配分が、近傍の摂動よりも期待対数成長率が高いことを確認。"""
    probs = [0.35, 0.25, 0.15, 0.10]
    odds = [3.5, 5.0, 8.0, 15.0]
    f_opt = kelly_exclusive_outcomes(probs, odds)
    g_opt = expected_log_growth(probs, odds, f_opt)
    rng = np.random.default_rng(0)
    for _ in range(200):
        perturbed = np.clip(f_opt + rng.normal(0, 0.01, size=len(f_opt)), 0, None)
        if perturbed.sum() >= 1.0:
            continue
        assert expected_log_growth(probs, odds, perturbed) <= g_opt + 1e-9


def test_kelly_exclusive_validates_input():
    with pytest.raises(ValueError):
        kelly_exclusive_outcomes([0.7, 0.7], [2.0, 2.0])  # 確率合計>1
    with pytest.raises(ValueError):
        kelly_exclusive_outcomes([0.5], [0.0])  # 不正オッズ
