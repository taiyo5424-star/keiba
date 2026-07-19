"""レース・出走馬・オッズ履歴・購入記録のSQLiteストア。

設計方針:
- オッズは「スナップショット時刻付き」で蓄積する(確定オッズだけでは
  実運用シミュレーションができない — docs/strategy.md §2.3)。
- bets テーブルは全購入の完全記録。モデル検証と税務(雑所得認定には
  個々の購入記録の客観的立証が必要 — docs/research/tax.md)の両方を支える。
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

SCHEMA = """
CREATE TABLE IF NOT EXISTS races (
    race_id   TEXT PRIMARY KEY,
    date      TEXT NOT NULL,          -- ISO8601 (YYYY-MM-DD)
    organizer TEXT NOT NULL,          -- 'jra' / 'nar:oi' 等
    course    TEXT,
    race_no   INTEGER,
    distance  INTEGER,
    surface   TEXT,                   -- 芝/ダート
    going     TEXT                    -- 馬場状態
);
CREATE INDEX IF NOT EXISTS idx_races_date ON races(date);

CREATE TABLE IF NOT EXISTS runners (
    race_id    TEXT NOT NULL,
    horse_no   INTEGER NOT NULL,
    horse_id   TEXT NOT NULL,
    jockey_id  TEXT,
    trainer_id TEXT,
    age        INTEGER,
    weight     REAL,                  -- 斤量
    body_weight REAL,                 -- 馬体重
    finish_pos INTEGER,               -- NULL = 未確定
    win_odds_final REAL,              -- 確定単勝オッズ(検証用。購入判断に使わない)
    PRIMARY KEY (race_id, horse_no)
);
CREATE INDEX IF NOT EXISTS idx_runners_horse ON runners(horse_id);

CREATE TABLE IF NOT EXISTS odds_snapshots (
    race_id  TEXT NOT NULL,
    horse_no INTEGER NOT NULL,
    taken_at TEXT NOT NULL,           -- ISO8601 datetime
    win_odds REAL NOT NULL,
    PRIMARY KEY (race_id, horse_no, taken_at)
);

CREATE TABLE IF NOT EXISTS bets (
    bet_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    placed_at TEXT NOT NULL,
    race_id   TEXT NOT NULL,
    bet_type  TEXT NOT NULL,          -- 'win', 'trifecta' 等 (takeout.py のキー)
    selection TEXT NOT NULL,          -- '5' / '3-5-12' 等
    stake     REAL NOT NULL,
    odds_at_purchase REAL,
    returned  REAL DEFAULT 0          -- 払戻額(外れは0)
);
"""


def connect(path: str | Path) -> sqlite3.Connection:
    """DBを開き、スキーマを初期化して接続を返す。":memory:" も可。"""
    conn = sqlite3.connect(str(path))
    conn.executescript(SCHEMA)
    return conn


def insert_races(conn: sqlite3.Connection, df: pd.DataFrame) -> None:
    df.to_sql("races", conn, if_exists="append", index=False)


def insert_runners(conn: sqlite3.Connection, df: pd.DataFrame) -> None:
    df.to_sql("runners", conn, if_exists="append", index=False)


def insert_odds_snapshots(conn: sqlite3.Connection, df: pd.DataFrame) -> None:
    df.to_sql("odds_snapshots", conn, if_exists="append", index=False)


def record_bet(
    conn: sqlite3.Connection,
    placed_at: str,
    race_id: str,
    bet_type: str,
    selection: str,
    stake: float,
    odds_at_purchase: float | None = None,
    returned: float = 0.0,
) -> None:
    conn.execute(
        "INSERT INTO bets (placed_at, race_id, bet_type, selection, stake,"
        " odds_at_purchase, returned) VALUES (?,?,?,?,?,?,?)",
        (placed_at, race_id, bet_type, selection, stake, odds_at_purchase, returned),
    )
    conn.commit()


def load_races(conn: sqlite3.Connection) -> pd.DataFrame:
    return pd.read_sql("SELECT * FROM races ORDER BY date, race_id", conn)


def load_runners(conn: sqlite3.Connection) -> pd.DataFrame:
    return pd.read_sql("SELECT * FROM runners", conn)


def load_bets(conn: sqlite3.Connection) -> pd.DataFrame:
    return pd.read_sql("SELECT * FROM bets ORDER BY placed_at", conn)


def latest_odds_before(
    conn: sqlite3.Connection, race_id: str, cutoff: str
) -> pd.DataFrame:
    """cutoff 時刻までに観測された最新のオッズスナップショットを馬ごとに返す。

    バックテストで「その時点で購入可能だったオッズ」を取り出すための関数。
    """
    return pd.read_sql(
        """
        SELECT s.horse_no, s.win_odds, s.taken_at
        FROM odds_snapshots s
        JOIN (
            SELECT horse_no, MAX(taken_at) AS mt
            FROM odds_snapshots
            WHERE race_id = ? AND taken_at <= ?
            GROUP BY horse_no
        ) last ON s.horse_no = last.horse_no AND s.taken_at = last.mt
        WHERE s.race_id = ?
        ORDER BY s.horse_no
        """,
        conn,
        params=(race_id, cutoff, race_id),
    )


def yearly_betting_summary(conn: sqlite3.Connection) -> pd.DataFrame:
    """年別の購入額・払戻額・収支・回収率(税務申告と網羅性立証の基礎資料)。"""
    return pd.read_sql(
        """
        SELECT substr(placed_at, 1, 4) AS year,
               COUNT(*)      AS n_bets,
               SUM(stake)    AS total_staked,
               SUM(returned) AS total_returned,
               SUM(returned) - SUM(stake) AS profit,
               ROUND(SUM(returned) * 1.0 / SUM(stake), 4) AS roi
        FROM bets GROUP BY year ORDER BY year
        """,
        conn,
    )
