"""NAR(地方競馬)の日次データ収集スクリプト。

当日(JST)の全開催について、NAR公式(keiba.go.jp)から成績・払戻を、
楽天競馬から式別票数(プールサイズ)を取得し、data/nar/YYYY-MM-DD/ に
CSVで保存する。追記専用のテキストファイルなので、日次で走らせて
git にコミットしていけばデータセットが育つ。

実行例:
  python scripts/daily_ingest.py                     # 当日(JST)
  python scripts/daily_ingest.py --date 2026/08/06   # 日付指定
  python scripts/daily_ingest.py --skip-rakuten      # 票数取得を省略(高速)

politeness: keiba.go.jp は2秒間隔、楽天は robots.txt の Crawl-Delay 60秒を
フェッチャが強制する。1日あたりのリクエスト数は 開催数×(レース数+2) 程度。
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
    fetch_meetings,
    fetch_race_numbers,
    fetch_race_result,
)
from keiba.ingest.rakuten import fetch_dividend_list  # noqa: E402

JST = dt.timezone(dt.timedelta(hours=9))

BABA_NAMES = {
    3: "帯広ば", 10: "盛岡", 11: "水沢", 18: "浦和", 19: "船橋", 20: "大井",
    21: "川崎", 22: "金沢", 23: "笠松", 24: "名古屋", 27: "園田", 28: "姫路",
    30: "高知", 31: "佐賀", 32: "佐賀", 33: "荒尾", 36: "門別",
}


def ingest_day(date_slash: str, out_root: Path, skip_rakuten: bool = False) -> dict:
    """1日分を収集して out_root/YYYY-MM-DD/*.csv に保存。統計dictを返す。"""
    date_iso = date_slash.replace("/", "-")
    yyyymmdd = date_slash.replace("/", "")
    out_dir = out_root / date_iso
    out_dir.mkdir(parents=True, exist_ok=True)

    meetings = fetch_meetings(date_slash)
    print(f"[{date_iso}] 開催: {[(b, BABA_NAMES.get(b, '?')) for _, b in meetings]}")

    races_rows, result_rows, refund_rows, pool_rows = [], [], [], []
    errors = []

    for _, baba in meetings:
        try:
            race_nos = fetch_race_numbers(date_slash, baba)
        except Exception as e:  # noqa: BLE001
            errors.append(f"RaceList {baba}: {e}")
            continue
        print(f"  babaCode={baba} ({BABA_NAMES.get(baba, '?')}): {len(race_nos)}R")
        for no in race_nos:
            race_id = f"{yyyymmdd}-{baba:02d}-{no:02d}"
            try:
                r = fetch_race_result(date_slash, no, baba)
            except Exception as e:  # noqa: BLE001
                errors.append(f"RaceMarkTable {race_id}: {e}")
                continue
            if not r.finishers:
                # 未確定(発走前・中止等)はスキップ
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

        if not skip_rakuten:
            try:
                for rd in fetch_dividend_list(yyyymmdd, baba):
                    race_id = f"{yyyymmdd}-{baba:02d}-{rd.race_no:02d}"
                    for bet_type, votes in rd.votes.items():
                        pool_rows.append(
                            {
                                "race_id": race_id, "bet_type": bet_type,
                                "votes": votes,
                                "returned_votes": rd.returned_votes.get(bet_type, 0),
                            }
                        )
            except Exception as e:  # noqa: BLE001
                errors.append(f"rakuten {baba}: {e}")

    def _save(name: str, rows: list) -> None:
        if rows:
            pd.DataFrame(rows).to_csv(out_dir / f"{name}.csv", index=False)

    _save("races", races_rows)
    _save("results", result_rows)
    _save("refunds", refund_rows)
    _save("pools", pool_rows)

    stats = {
        "date": date_iso,
        "meetings": len(meetings),
        "races": len(races_rows),
        "results": len(result_rows),
        "refunds": len(refund_rows),
        "pools": len(pool_rows),
        "errors": errors,
    }
    print(f"[{date_iso}] races={stats['races']} results={stats['results']} "
          f"refunds={stats['refunds']} pools={stats['pools']} errors={len(errors)}")
    for e in errors:
        print("  !", e)
    return stats


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="YYYY/MM/DD(省略時は当日JST)")
    ap.add_argument("--out", default="data/nar")
    ap.add_argument("--skip-rakuten", action="store_true")
    args = ap.parse_args()
    date_slash = args.date or dt.datetime.now(JST).strftime("%Y/%m/%d")
    stats = ingest_day(date_slash, Path(args.out), skip_rakuten=args.skip_rakuten)
    # レースが1つも取れず、かつエラーがある場合のみ異常終了
    if stats["races"] == 0 and stats["errors"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
