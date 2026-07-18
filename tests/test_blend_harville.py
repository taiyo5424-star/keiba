import numpy as np
import pytest

from keiba.blend import blend_probabilities, fit_blend_weights, log_likelihood
from keiba.harville import (
    exacta_probability,
    fit_gamma,
    quinella_probability,
    trifecta_probability,
    trio_probability,
)


def test_blend_normalizes():
    p = blend_probabilities([0.5, 0.3, 0.2], [0.4, 0.4, 0.2], alpha=1.0, beta=1.0)
    assert p.sum() == pytest.approx(1.0)


def test_blend_alpha_zero_returns_market():
    market = [0.5, 0.3, 0.2]
    p = blend_probabilities([0.1, 0.1, 0.8], market, alpha=0.0, beta=1.0)
    assert np.allclose(p, market)


def test_blend_beta_zero_returns_model():
    model = [0.6, 0.3, 0.1]
    p = blend_probabilities(model, [0.2, 0.4, 0.4], alpha=1.0, beta=0.0)
    assert np.allclose(p, model)


def _make_races(n_races=400, seed=1, model_informative=True):
    """真の確率から結果を生成。市場は真の確率のノイズ版、モデルも別ノイズ版。"""
    rng = np.random.default_rng(seed)
    races = []
    for _ in range(n_races):
        n = 8
        s = rng.gamma(2.0, 1.0, size=n)
        true_p = s / s.sum()
        market = true_p * rng.gamma(30, 1 / 30, size=n)
        market /= market.sum()
        if model_informative:
            model = true_p * rng.gamma(30, 1 / 30, size=n)
        else:
            model = rng.dirichlet(np.ones(n))  # 無情報モデル
        model /= model.sum()
        winner = rng.choice(n, p=true_p)
        races.append((model, market, winner))
    return races


def test_fit_blend_informative_model_gets_positive_alpha():
    races = _make_races(model_informative=True)
    alpha, beta = fit_blend_weights(races, n_iter=300)
    assert alpha > 0.2  # モデルに情報がある → α有意
    assert beta > 0.2   # 市場にも情報がある → β有意
    # 結合は市場単体より尤度が高い
    assert log_likelihood(races, alpha, beta) > log_likelihood(races, 0.0, 1.0)


def test_fit_blend_uninformative_model_shrinks_alpha():
    races = _make_races(model_informative=False)
    alpha, beta = fit_blend_weights(races, n_iter=300)
    assert alpha < 0.15  # 無情報モデルの重みはほぼ0に潰れる
    assert beta > 0.5


def test_harville_plain_exacta():
    p = [0.5, 0.3, 0.2]
    # P(0→1) = 0.5 * 0.3/0.5 = 0.3
    assert exacta_probability(p, 0, 1) == pytest.approx(0.5 * 0.3 / 0.5)


def test_harville_trifecta_sums_to_one():
    p = [0.4, 0.3, 0.2, 0.1]
    from itertools import permutations

    total = sum(
        trifecta_probability(p, i, j, k)
        for i, j, k in permutations(range(4), 3)
    )
    assert total == pytest.approx(1.0)


def test_gamma_correction_boosts_longshot_place():
    """γ<1 は人気薄の2着確率を素のHarvilleより引き上げる。"""
    p = [0.6, 0.3, 0.1]
    plain = exacta_probability(p, 0, 2, gamma=1.0)
    corrected = exacta_probability(p, 0, 2, gamma=0.7)
    assert corrected > plain


def test_quinella_and_trio_consistency():
    p = [0.4, 0.3, 0.2, 0.1]
    assert quinella_probability(p, 0, 1) == pytest.approx(
        exacta_probability(p, 0, 1) + exacta_probability(p, 1, 0)
    )
    assert 0 < trio_probability(p, 0, 1, 2) < 1


def test_fit_gamma_recovers_generating_value():
    """γ=0.75で2着を生成したデータからγを再推定できる。"""
    rng = np.random.default_rng(7)
    true_gamma = 0.75
    races = []
    for _ in range(2000):
        n = 8
        s = rng.gamma(2.0, 1.0, size=n)
        p = s / s.sum()
        first = rng.choice(n, p=p)
        w = p.copy() ** true_gamma
        w[first] = 0
        w /= w.sum()
        second = rng.choice(n, p=w)
        races.append((p, first, second))
    est = fit_gamma(races)
    assert est == pytest.approx(true_gamma, abs=0.06)
