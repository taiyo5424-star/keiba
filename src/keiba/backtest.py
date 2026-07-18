"""履歴データによる戦略バックテスト。

入力は「1行=1候補馬券」のDataFrame:
    race_id, odds, prob, won(0/1) が最低限の列。
    odds は購入時点で参照可能だったオッズを使うこと(確定オッズで
    テストすると実運用より甘い結果になる点に注意)。

賭け方:
- flat: EV閾値を超えた馬券に均等額
- kelly: レースごとに排反ケリー配分(kelly_exclusive_outcomes)

出力は総合収支と時系列資産推移。ドローダウンも計算する。
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from keiba.kelly import kelly_exclusive_outcomes


@dataclass
class BacktestResult:
    n_races: int
    n_bets: int
    total_staked: float
    total_returned: float
    final_bankroll: float
    max_drawdown: float
    bankroll_curve: pd.Series = field(repr=False)

    @property
    def roi(self) -> float:
        """回収率(払戻/投票額)。1.0超がプラス収支。"""
        return self.total_returned / self.total_staked if self.total_staked > 0 else float("nan")

    @property
    def profit(self) -> float:
        return self.total_returned - self.total_staked


def _max_drawdown(curve: pd.Series) -> float:
    peak = curve.cummax()
    dd = (curve - peak) / peak
    return float(dd.min()) if len(dd) else 0.0


def backtest_win_bets(
    df: pd.DataFrame,
    min_ev: float = 1.0,
    staking: str = "flat",
    kelly_fraction: float = 0.25,
    flat_stake: float = 0.01,
    initial_bankroll: float = 1.0,
    prob_col: str = "prob",
    odds_col: str = "odds",
    outcome_col: str = "won",
    race_col: str = "race_id",
) -> BacktestResult:
    """EV閾値戦略のバックテストを実行する。

    Args:
        df: 候補馬券のDataFrame(レース時系列順に並んでいること)。
        min_ev: prob*odds がこの値以上の馬券のみ購入。
        staking: "flat"(資金の flat_stake 割合を均等賭け)または
                 "kelly"(レース内排反ケリー × kelly_fraction)。
        initial_bankroll: 初期資金(規格化して1.0でよい)。
    """
    if staking not in ("flat", "kelly"):
        raise ValueError("staking must be 'flat' or 'kelly'")

    bankroll = initial_bankroll
    curve = []
    n_bets = 0
    total_staked = 0.0
    total_returned = 0.0
    race_ids = df[race_col].unique()

    for rid in race_ids:
        race = df[df[race_col] == rid]
        probs = race[prob_col].to_numpy(dtype=float)
        odds = race[odds_col].to_numpy(dtype=float)
        won = race[outcome_col].to_numpy(dtype=float)
        ev = probs * odds

        if staking == "flat":
            stakes = np.where(ev >= min_ev, flat_stake, 0.0) * bankroll
        else:
            mask = ev >= min_ev
            f = np.zeros(len(race))
            if mask.any():
                f[mask] = kelly_exclusive_outcomes(
                    probs[mask], odds[mask], fraction=kelly_fraction
                )
            stakes = f * bankroll

        staked = float(stakes.sum())
        returned = float((stakes * odds * won).sum())
        bankroll = bankroll - staked + returned
        n_bets += int((stakes > 0).sum())
        total_staked += staked
        total_returned += returned
        curve.append(bankroll)
        if bankroll <= 0:
            break

    curve_s = pd.Series(curve, index=race_ids[: len(curve)], name="bankroll")
    return BacktestResult(
        n_races=len(curve),
        n_bets=n_bets,
        total_staked=total_staked,
        total_returned=total_returned,
        final_bankroll=bankroll,
        max_drawdown=_max_drawdown(curve_s),
        bankroll_curve=curve_s,
    )
