"""WIN5・トリプル馬単などキャリーオーバー型券種の実効還元率とEV。

検証済みの公式(docs/strategy.md §2.1-2.2):
    払戻総額 = R × Pool + A
    (R: 払戻率, Pool: 当該回の投票総額, A: キャリーオーバー額)

→ 実効還元率 R_eff = R + A / Pool。
A > (1 - R) × Pool のとき R_eff > 1 となり、「プール全体としては」
プラスサムになる。ただし自分のEVは的中確率と的中票の分配で決まるため、
プラスサム=個人のEVプラスではない点に注意。
"""

from __future__ import annotations

PAYOUT_RATE_WIN5 = 0.70
PAYOUT_RATE_TRIPLE_EXACTA = 0.70


def effective_payout_rate(pool: float, carryover: float, rate: float = PAYOUT_RATE_WIN5) -> float:
    """キャリーオーバー込みの実効還元率 R_eff = R + A/Pool。"""
    if pool <= 0:
        raise ValueError("pool must be positive")
    if carryover < 0:
        raise ValueError("carryover must be non-negative")
    return rate + carryover / pool


def breakeven_carryover(pool: float, rate: float = PAYOUT_RATE_WIN5) -> float:
    """実効還元率が100%になるキャリーオーバー額 A* = (1-R) × Pool。

    例: WIN5の当該回売上が4億円なら A* = 1.2億円。これを超える
    キャリーオーバーはプール全体をプラスサムにする。
    """
    if pool <= 0:
        raise ValueError("pool must be positive")
    return (1.0 - rate) * pool


def expected_dividend(
    pool: float,
    carryover: float,
    winning_stake: float,
    rate: float = PAYOUT_RATE_WIN5,
) -> float:
    """的中組み合わせへの投票総額が winning_stake のときの100円あたり配当。

    配当 = 払戻総額 / 的中票 = (R×Pool + A) / winning_stake (×100円)
    """
    if winning_stake <= 0:
        raise ValueError("winning_stake must be positive")
    return (rate * pool + carryover) / winning_stake * 100.0


def ticket_ev(
    hit_prob: float,
    pool: float,
    carryover: float,
    winning_stake: float,
    rate: float = PAYOUT_RATE_WIN5,
) -> float:
    """1点100円の期待払戻(円)。EV > 100 が期待値プラス。

    Args:
        hit_prob: その組み合わせが的中する確率の自己推定。
        winning_stake: 的中時にその組み合わせに乗っている投票総額の推定
            (自分の100円を含む)。人気の組み合わせほど大きい。
    """
    if not 0.0 <= hit_prob <= 1.0:
        raise ValueError("hit_prob must be in [0, 1]")
    return hit_prob * expected_dividend(pool, carryover, winning_stake, rate)
