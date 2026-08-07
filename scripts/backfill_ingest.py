"""NAR過去データの一括収集(バックフィル)。

月間カレンダーで開催を発見し、指定期間の全レース成績・払戻を
data/nar/YYYY-MM-DD/*.csv に保存する(楽天の票数は含まない)。

注意:
- 成績ページの単勝オッズ欄は概ね直近4〜6ヶ月のみ保持(2026-08実測:
  2026/04は保持、2026/02は消失)。それ以前は popularity のみ残る。
- keiba.go.jp へのアクセス間隔は --interval(既定2.0秒)で制御。
  並列実行する場合はプロセス数×レートがサイトへの総負荷になるため、
  合計でも毎秒2リクエスト程度までに抑えること。

実行例:
  python scripts/backfill_ingest.py --from 2026-04-01 --to 2026-04-30
  python scripts/backfill_ingest.py --from 2026-05-01 --to 2026-05-31 --interval 2.5
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from keiba.ingest.nar_keibago import (  # noqa: E402
    fetch_month_meetings,
    fetch_race_numbers,
    fetch_race_result,
)

BABA_NAMES = {
    3: "帯広ば", 10: "盛岡", 11: "水沢", 18: "浦和", 19: "船橋", 20: "大井",
    21: "川崎", 22: "金沢", 23: "笠松", 24: "名古屋", 27: "園田", 28: "姫路",
    30: "高知", 31: "佐賀", 32: "佐賀", 33: "荒尾", 36: "門別",
}


def _months_between(d1: dt.date, d2: dt.date):
    y, m = d1.year, d1.month
    while (y, m) <= (d2.year, d2.month):
        yield y, m
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)


def ingest_meeting(date_slash: str, baba: int, out_root: Path, interval: float) -> dict:
    """1開催(日×場)を収集して当日ディレクトリのCSVに追記保存する。"""
    date_iso = date_slash.replace("/", "-")
    yyyymmdd = date_slash.replace("/", "")
    out_dir = out_root / date_iso
    out_dir.mkdir(parents=True, exist_ok=True)

    races_rows, result_rows, refund_rows = [], [], []
    errors = []
    try:
        race_nos = fetch_race_numbers(date_slash, baba, min_interval=interval)
    except Exception as e:  # noqa: BLE001
        return {"races": 0, "errors": [f"RaceList {date_iso} {baba}: {e}"]}

    for no in race_nos:
        race_id = f"{yyyymmdd}-{baba:02d}-{no:02d}"
        try:
            r = fetch_race_result(date_slash, no, baba, min_interval=interval)
        except Exception as e:  # noqa: BLE001
            errors.append(f"RaceMarkTable {race_id}: {e}")
            continue
        if not r.finishers:
            continue
        races_rows.append(
            {
                "race_id": race_id, "date": date_iso, "baba_code": baba,
                "baba_name": BABA_NAMES.get(baba, ""), "race_no": no,
                "title": r.title, "surface": r.surface, "distance": r.distance,
                "weather": r.weather, "going": r.going,
            }
        )
        for f in r.finishers:
            row = dataclasses.asdict(f)
            row["race_id"] = race_id
            result_rows.append(row)
        for x in r.refunds:
            refund_rows.append(
                {
                    "race_id": race_id, "bet_type": x.bet_type,
                    "combination": x.combination, "amount": x.amount,
                    "popularity": x.popularity,
                }
            )

    def _append(name: str, rows: list) -> None:
        if not rows:
            return
        path = out_dir / f"{name}.csv"
        df = pd.DataFrame(rows)
        if path.exists():
            old = pd.read_csv(path)
            df = pd.concat([old, df], ignore_index=True).drop_duplicates()
        df.to_csv(path, index=False)

    _append("races", races_rows)
    _append("results", result_rows)
    _append("refunds", refund_rows)
    return {"races": len(races_rows), "errors": errors}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="date_from", required=True, help="YYYY-MM-DD")
    ap.add_argument("--to", dest="date_to", required=True, help="YYYY-MM-DD")
    ap.add_argument("--out", default="data/nar")
    ap.add_argument("--interval", type=float, default=2.0)
    args = ap.parse_args()

    d1 = dt.date.fromisoformat(args.date_from)
    d2 = dt.date.fromisoformat(args.date_to)
    out_root = Path(args.out)

    meetings: list[tuple[str, int]] = []
    for y, m in _months_between(d1, d2):
        for date_slash, baba in fetch_month_meetings(y, m, min_interval=args.interval):
            d = dt.date.fromisoformat(date_slash.replace("/", "-"))
            if d1 <= d <= d2:
                meetings.append((date_slash, baba))
    meetings.sort()
    print(f"対象開催: {len(meetings)}(期間 {d1} 〜 {d2})")

    total_races, all_errors = 0, []
    for i, (date_slash, baba) in enumerate(meetings, 1):
        # 既取得スキップ: 当該開催のレースが races.csv に存在すれば飛ばす
        date_iso = date_slash.replace("/", "-")
        races_csv = out_root / date_iso / "races.csv"
        if races_csv.exists():
            existing = pd.read_csv(races_csv)
            if (existing["baba_code"] == baba).any():
                continue
        stats = ingest_meeting(date_slash, baba, out_root, args.interval)
        total_races += stats["races"]
        all_errors.extend(stats["errors"])
        print(f"[{i}/{len(meetings)}] {date_slash} {BABA_NAMES.get(baba, baba)}: "
              f"{stats['races']}R (累計{total_races}R, err={len(all_errors)})",
              flush=True)

    print(f"完了: {total_races}レース収集, エラー{len(all_errors)}件")
    for e in all_errors[:20]:
        print("  !", e)
    return 0 if total_races > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
