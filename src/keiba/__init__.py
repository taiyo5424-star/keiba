"""keiba — 中央競馬(JRA)・地方競馬(NAR)の期待値ベース馬券戦略ツールキット。

主要モジュール:
- takeout:      券種ごとの払戻率(控除率)テーブル
- ev:           オッズ⇔確率変換、期待値計算、オーバーラウンド除去
- kelly:        ケリー基準による資金配分(単一賭け・同一レース内複数賭け)
- calibration:  予測確率の較正評価(Brierスコア、対数損失、信頼度曲線)
- backtest:     履歴オッズ+着順データによる戦略バックテスト
"""

from keiba.takeout import PAYOUT_RATE_JRA, PAYOUT_RATE_NAR_TYPICAL, takeout_rate
from keiba.ev import (
    implied_probability,
    normalized_implied_probabilities,
    expected_value,
    ev_table,
)
from keiba.kelly import kelly_fraction, kelly_exclusive_outcomes
from keiba.backtest import BacktestResult, backtest_win_bets

__all__ = [
    "PAYOUT_RATE_JRA",
    "PAYOUT_RATE_NAR_TYPICAL",
    "takeout_rate",
    "implied_probability",
    "normalized_implied_probabilities",
    "expected_value",
    "ev_table",
    "kelly_fraction",
    "kelly_exclusive_outcomes",
    "BacktestResult",
    "backtest_win_bets",
]
