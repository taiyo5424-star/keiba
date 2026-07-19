"""store / features / model / win5 のテスト。

PIT(Point-in-Time)性のテストが最重要: 「過去のレースの特徴量は、
未来のレースの結果を変えても変化しない」ことを直接検証する。
"""

import numpy as np
import pandas as pd
import pytest

from keiba.features import FEATURE_COLUMNS, build_pit_features, time_series_split
from keiba.model import ConditionalLogitModel, mean_race_log_likelihood
from keiba.store import (
    connect,
    insert_odds_snapshots,
    insert_races,
    insert_runners,
    latest_odds_before,
    load_races,
    load_runners,
    record_bet,
    yearly_betting_summary,
)
from keiba.win5 import breakeven_carryover, effective_payout_rate, ticket_ev


def _synthetic_world(n_races=300, n_horses=60, seed=0):
    """能力値を持つ馬・騎手による合成レース履歴を生成する。"""
    rng = np.random.default_rng(seed)
    ability = {f"H{i}": rng.normal(0, 1) for i in range(n_horses)}
    j_skill = {f"J{i}": rng.normal(0, 0.3) for i in range(12)}
    races, runners = [], []
    date = pd.Timestamp("2024-01-01")
    for r in range(n_races):
        rid = f"R{r:04d}"
        date += pd.Timedelta(days=1 if r % 2 else 2)
        races.append(
            {"race_id": rid, "date": date.strftime("%Y-%m-%d"), "organizer": "jra",
             "course": "tokyo", "race_no": 1, "distance": 1600, "surface": "turf",
             "going": "good"}
        )
        field_ids = rng.choice(n_horses, size=8, replace=False)
        utils = []
        entries = []
        for no, h in enumerate(field_ids, start=1):
            hid, jid = f"H{h}", f"J{rng.integers(12)}"
            u = ability[hid] + j_skill[jid] + rng.normal(0, 1.0)
            utils.append(u)
            entries.append(
                {"race_id": rid, "horse_no": no, "horse_id": hid, "jockey_id": jid,
                 "trainer_id": f"T{h % 10}", "age": int(rng.integers(3, 8)),
                 "weight": 55.0, "body_weight": 480.0}
            )
        order = np.argsort(-np.asarray(utils))
        for pos, idx in enumerate(order, start=1):
            entries[idx]["finish_pos"] = pos
        runners.extend(entries)
    return pd.DataFrame(races), pd.DataFrame(runners)


def test_store_roundtrip_and_odds_cutoff():
    conn = connect(":memory:")
    races, runners = _synthetic_world(n_races=5)
    insert_races(conn, races)
    insert_runners(conn, runners)
    assert len(load_races(conn)) == 5
    assert len(load_runners(conn)) == 40

    rid = races.iloc[0]["race_id"]
    snaps = pd.DataFrame(
        [
            {"race_id": rid, "horse_no": 1, "taken_at": "2024-01-01T10:00", "win_odds": 5.0},
            {"race_id": rid, "horse_no": 1, "taken_at": "2024-01-01T15:00", "win_odds": 3.2},
            {"race_id": rid, "horse_no": 1, "taken_at": "2024-01-01T15:59", "win_odds": 2.8},
        ]
    )
    insert_odds_snapshots(conn, snaps)
    # 15:30時点で参照可能なのは15:00のスナップショット
    df = latest_odds_before(conn, rid, "2024-01-01T15:30")
    assert len(df) == 1
    assert df.iloc[0]["win_odds"] == pytest.approx(3.2)


def test_bets_recording_and_summary():
    conn = connect(":memory:")
    record_bet(conn, "2024-03-01T15:00", "R0001", "win", "5", 1000, 4.2, returned=4200)
    record_bet(conn, "2024-03-01T15:30", "R0002", "win", "3", 1000, 6.0, returned=0)
    record_bet(conn, "2025-01-05T15:00", "R0500", "trifecta", "1-2-3", 500, None, returned=0)
    summary = yearly_betting_summary(conn)
    assert list(summary["year"]) == ["2024", "2025"]
    row2024 = summary[summary["year"] == "2024"].iloc[0]
    assert row2024["total_staked"] == 2000
    assert row2024["roi"] == pytest.approx(2.1)


def test_pit_features_do_not_depend_on_future():
    """PIT性の直接検証: 未来のレース結果を改変しても過去の特徴量は不変。"""
    races, runners = _synthetic_world(n_races=100, seed=3)
    feats_a = build_pit_features(races, runners)

    # 後半50レースの着順を全て反転させる
    runners_b = runners.copy()
    late_ids = set(races.sort_values("date")["race_id"].tail(50))
    mask = runners_b["race_id"].isin(late_ids)
    runners_b.loc[mask, "finish_pos"] = 9 - runners_b.loc[mask, "finish_pos"]
    feats_b = build_pit_features(races, runners_b)

    early_ids = set(races["race_id"]) - late_ids
    a = feats_a[feats_a["race_id"].isin(early_ids)].sort_values(["race_id", "horse_no"])
    b = feats_b[feats_b["race_id"].isin(early_ids)].sort_values(["race_id", "horse_no"])
    for col in FEATURE_COLUMNS:
        assert np.allclose(a[col].to_numpy(), b[col].to_numpy()), col


def test_pit_features_first_race_has_no_history():
    races, runners = _synthetic_world(n_races=10, seed=1)
    feats = build_pit_features(races, runners)
    first_rid = races.sort_values("date").iloc[0]["race_id"]
    first = feats[feats["race_id"] == first_rid]
    assert (first["horse_starts"] == 0).all()


def test_time_series_split_is_chronological():
    races, runners = _synthetic_world(n_races=50, seed=2)
    feats = build_pit_features(races, runners)
    train, test = time_series_split(feats, train_frac=0.7)
    assert train["date"].max() <= test["date"].min()
    assert len(train) + len(test) == len(feats)


def test_conditional_logit_beats_uniform():
    races, runners = _synthetic_world(n_races=400, seed=5)
    feats = build_pit_features(races, runners)
    train, test = time_series_split(feats, train_frac=0.7)
    model = ConditionalLogitModel(feature_columns=FEATURE_COLUMNS)
    model.fit(train, n_iter=200)
    probs = model.predict(test)
    ll_model = mean_race_log_likelihood(probs, test)
    ll_uniform = np.log(1 / 8)
    assert ll_model > ll_uniform  # 履歴特徴だけでも一様分布よりは当てられる
    # 各レースで確率は正規化されている
    sums = pd.DataFrame({"p": probs, "race_id": test["race_id"]}).groupby("race_id")["p"].sum()
    assert np.allclose(sums.to_numpy(), 1.0)


def test_win5_carryover_math():
    # 売上4億円・払戻率70% → 損益分岐キャリーオーバーは1.2億円
    assert breakeven_carryover(4e8, 0.70) == pytest.approx(1.2e8)
    assert effective_payout_rate(4e8, 0.0) == pytest.approx(0.70)
    assert effective_payout_rate(4e8, 1.2e8) == pytest.approx(1.0)
    assert effective_payout_rate(4e8, 2.4e8) == pytest.approx(1.3)


def test_win5_ticket_ev():
    # プール4億・キャリーオーバー2億、的中票100万円分、的中確率0.5%
    ev = ticket_ev(hit_prob=0.005, pool=4e8, carryover=2e8, winning_stake=1e6)
    # 配当 = (0.7*4e8 + 2e8)/1e6 * 100 = 48,000円 → EV = 240円 > 100円
    assert ev == pytest.approx(240.0)
    with pytest.raises(ValueError):
        ticket_ev(1.5, 4e8, 0, 1e6)
