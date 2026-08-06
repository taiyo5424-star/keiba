import datetime as dt
from pathlib import Path

import numpy as np
import pytest

from keiba.decision import BetOrder, DecisionPolicy, decide_win_bets
from keiba.execution import ExecutionGuard, PaperBroker, execute_orders
from keiba.store import connect, load_bets


def test_decide_no_positive_ev_returns_empty():
    orders = decide_win_bets("R1", [0.3, 0.2], [2.0, 3.0], bankroll=1_000_000)
    assert orders == []


def test_decide_filters_and_rounds_to_unit():
    policy = DecisionPolicy(min_ev=1.05, kelly_fraction=0.25)
    # 馬2はEV=0.20*6.5=1.30で対象。馬1はEVちょうど1.0で対象外
    orders = decide_win_bets(
        "R1", [0.50, 0.20], [2.0, 6.5], bankroll=1_000_000, policy=policy
    )
    assert len(orders) == 1
    o = orders[0]
    assert o.selection == "2"
    assert o.stake % 100 == 0 and o.stake > 0
    assert o.ev == pytest.approx(1.30)


def test_decide_respects_race_cap():
    policy = DecisionPolicy(
        min_ev=1.0, max_stake_per_bet_frac=0.05, max_stake_per_race_frac=0.02
    )
    probs = [0.30, 0.25, 0.20]
    odds = [4.5, 5.5, 7.0]  # 全馬EVプラス
    orders = decide_win_bets("R1", probs, odds, bankroll=1_000_000, policy=policy)
    total = sum(o.stake for o in orders)
    assert total <= 0.02 * 1_000_000 + 1e-9


def test_decide_odds_band_filter():
    policy = DecisionPolicy(min_ev=1.0, min_odds=2.0, max_odds=50.0)
    orders = decide_win_bets(
        "R1", [0.9, 0.012], [1.2, 100.0], bankroll=1_000_000, policy=policy
    )
    assert orders == []  # 低オッズと上限超の大穴は両方除外


def test_decide_small_bankroll_below_unit():
    orders = decide_win_bets("R1", [0.5], [3.0], bankroll=500)
    assert orders == []  # 100円単位に満たない賭けは出さない


def _order(race="R1", sel="1", stake=1000, odds=4.0):
    return BetOrder(race_id=race, bet_type="win", selection=sel,
                    stake=stake, prob=0.3, odds=odds, ev=0.3 * odds)


def test_execute_paper_and_settle(tmp_path):
    conn = connect(":memory:")
    broker = PaperBroker(conn)
    guard = ExecutionGuard(kill_switch_path=tmp_path / "KILL_SWITCH")
    now = dt.datetime(2026, 7, 19, 15, 0)
    res = execute_orders([_order(sel="5", stake=1000, odds=4.2)], broker, guard, now)
    assert len(res.placed) == 1 and not res.rejected

    broker.settle_win_race("R1", winner_selection="5", final_odds=3.8)
    bets = load_bets(conn)
    assert bets.iloc[0]["returned"] == pytest.approx(3800)  # 清算は確定オッズ


def test_execute_kill_switch_blocks(tmp_path):
    conn = connect(":memory:")
    ks = tmp_path / "KILL_SWITCH"
    ks.write_text("stop")
    guard = ExecutionGuard(kill_switch_path=ks)
    res = execute_orders([_order()], PaperBroker(conn), guard)
    assert not res.placed
    assert res.rejected[0][1] == "kill switch is on"
    assert len(load_bets(conn)) == 0  # 記録すらされない


def test_execute_daily_caps_and_duplicates(tmp_path):
    conn = connect(":memory:")
    guard = ExecutionGuard(
        kill_switch_path=tmp_path / "KILL_SWITCH", max_daily_stake=2500
    )
    now = dt.datetime(2026, 7, 19, 15, 0)
    orders = [
        _order(sel="1", stake=1000),
        _order(sel="1", stake=1000),   # 重複
        _order(sel="2", stake=1000),
        _order(sel="3", stake=1000),   # 日次上限超過
    ]
    res = execute_orders(orders, PaperBroker(conn), guard, now)
    assert len(res.placed) == 2
    reasons = [r for _, r in res.rejected]
    assert "duplicate order" in reasons
    assert any("daily stake cap" in r for r in reasons)
