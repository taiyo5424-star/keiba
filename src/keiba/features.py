"""Point-in-Time(時点固定)特徴量生成。

バックテストROI 200%超→実運用85%未満の急落例の原因は「騎手勝率などの
集計特徴量を全期間で計算し、未来の実績が過去のレースに混入する」構造的
リークだった(docs/research/ml-implementations.md §4-2)。

このモジュールはレースを日付順に走査し、各レースの特徴量を
「そのレースより前に確定した結果だけ」から逐次更新の累積統計で作る。
実装上、未来参照が構造的に不可能な設計になっている。
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass
class _RollingStat:
    """出走数・勝数・着順和などの累積統計。"""

    starts: int = 0
    wins: int = 0
    finish_sum: float = 0.0
    last_date: str | None = None
    recent_finishes: list = field(default_factory=list)  # 直近の着順(最大5)

    def win_rate(self, prior: float = 0.08, prior_n: float = 20.0) -> float:
        """ラプラス平滑化した勝率(サンプルが少ない主体を全体平均に寄せる)。"""
        return (self.wins + prior * prior_n) / (self.starts + prior_n)

    def avg_recent_finish(self, default: float = 8.0) -> float:
        if not self.recent_finishes:
            return default
        return float(np.mean(self.recent_finishes))

    def update(self, finish_pos: int, date: str) -> None:
        self.starts += 1
        self.wins += int(finish_pos == 1)
        self.finish_sum += finish_pos
        self.last_date = date
        self.recent_finishes.append(finish_pos)
        if len(self.recent_finishes) > 5:
            self.recent_finishes.pop(0)


FEATURE_COLUMNS = [
    "horse_starts",
    "horse_win_rate",
    "horse_avg_recent_finish",
    "days_since_last_run",
    "jockey_win_rate",
    "trainer_win_rate",
    "age",
    "weight",
]


def build_pit_features(
    races: pd.DataFrame,
    runners: pd.DataFrame,
    max_layoff_days: float = 365.0,
) -> pd.DataFrame:
    """日付順にレースを走査し、PIT安全な特徴量テーブルを構築する。

    Args:
        races: columns [race_id, date, ...](store.load_races の出力)。
        runners: columns [race_id, horse_no, horse_id, jockey_id, trainer_id,
                 age, weight, finish_pos](finish_pos は学習用ラベルにのみ使用)。

    Returns:
        1行 = 1出走のDataFrame。FEATURE_COLUMNS + [race_id, horse_no, date, won]。
        特徴量は当該レースの結果を含まない(結果は特徴量計算の「後」に反映)。
    """
    horse_stats: dict[str, _RollingStat] = defaultdict(_RollingStat)
    jockey_stats: dict[str, _RollingStat] = defaultdict(_RollingStat)
    trainer_stats: dict[str, _RollingStat] = defaultdict(_RollingStat)

    runners_by_race = {rid: g for rid, g in runners.groupby("race_id")}
    races_sorted = races.sort_values(["date", "race_id"])
    rows = []

    for race in races_sorted.itertuples():
        entries = runners_by_race.get(race.race_id)
        if entries is None:
            continue
        date = race.date
        date_ts = pd.Timestamp(date)

        # --- 1) 特徴量を「過去の統計のみ」から計算 ---
        for e in entries.itertuples():
            hs = horse_stats[e.horse_id]
            js = jockey_stats[e.jockey_id]
            ts = trainer_stats[e.trainer_id]
            if hs.last_date is not None:
                layoff = min((date_ts - pd.Timestamp(hs.last_date)).days, max_layoff_days)
            else:
                layoff = max_layoff_days
            rows.append(
                {
                    "race_id": race.race_id,
                    "horse_no": e.horse_no,
                    "date": date,
                    "horse_starts": hs.starts,
                    "horse_win_rate": hs.win_rate(),
                    "horse_avg_recent_finish": hs.avg_recent_finish(),
                    "days_since_last_run": layoff,
                    "jockey_win_rate": js.win_rate(),
                    "trainer_win_rate": ts.win_rate(),
                    "age": e.age,
                    "weight": e.weight,
                    "won": int(e.finish_pos == 1) if e.finish_pos is not None else None,
                }
            )

        # --- 2) その後で当該レースの結果を統計に反映(順序が命) ---
        for e in entries.itertuples():
            if e.finish_pos is None or (isinstance(e.finish_pos, float) and np.isnan(e.finish_pos)):
                continue
            pos = int(e.finish_pos)
            horse_stats[e.horse_id].update(pos, date)
            jockey_stats[e.jockey_id].update(pos, date)
            trainer_stats[e.trainer_id].update(pos, date)

    return pd.DataFrame(rows)


def time_series_split(
    features: pd.DataFrame, train_frac: float = 0.7
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """レース単位・日付順で train/test に分割する(ランダム分割は禁止)。"""
    race_order = (
        features[["race_id", "date"]]
        .drop_duplicates()
        .sort_values(["date", "race_id"])["race_id"]
        .tolist()
    )
    n_train = int(len(race_order) * train_frac)
    train_ids = set(race_order[:n_train])
    is_train = features["race_id"].isin(train_ids)
    return features[is_train].copy(), features[~is_train].copy()
