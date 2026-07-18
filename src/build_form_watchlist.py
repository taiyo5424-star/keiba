import argparse
import csv
from collections import defaultdict
from pathlib import Path

from predict_historical_win_ev import odds_bucket
from rolling_backtest_horse_form import (
    beaten_fav_bucket,
    form3_bucket,
    group_races,
    last_finish_bucket,
    layoff_bucket,
    parse_date,
)
from score_live_place_ev import latest_odds
from score_live_win_ev import group_by_race, read_csv


# Candidate cells under PAPER-TRADE observation. None is approved for real money.
# Promotion requires fresh out-of-sample support; see docs/edge_research_roadmap.md.
WATCH_CELLS = [
    {
        "cell_id": "tailed_off_71-190d_20-50",
        "families": ("last_finish", "layoff"),
        "values": ("tailed_off", "71-190d"),
        "odds_bucket": "06_20-50",
        "backtest": "2005-2025 n=4206 edge=1.41 roi=1.17; 2021-2025 roi=1.21; unstable 2016-2020",
    },
    {
        "cell_id": "form3_poor_36-70d_20-50",
        "families": ("form3", "layoff"),
        "values": ("poor", "36-70d"),
        "odds_bucket": "06_20-50",
        "backtest": "2005-2025 n=1407 edge=1.68 roi=1.29; small yearly n (~60), low power",
    },
]


def build_history(paths: list[Path]) -> tuple[dict[str, list[tuple[int, int, int, int]]], str]:
    """Per-horse (date_ord, finish_rank, field_size, popularity), from all result files, deduped."""
    seen: set[tuple[str, str]] = set()
    runs: dict[str, list[tuple[int, str, int, int, int]]] = defaultdict(list)
    max_date = ""
    for path in paths:
        if not path.exists():
            continue
        for race_id, rows in group_races(path):
            race_date = rows[0]["race_date"]
            date_ord = parse_date(race_date)
            field_size = len(rows)
            for row in rows:
                key = (race_id, row["horse_no"])
                if key in seen:
                    continue
                seen.add(key)
                try:
                    rank = int(row["finish_rank"])
                except (KeyError, ValueError):
                    continue
                if rank <= 0:
                    continue
                try:
                    pop = int(row["win_popularity"])
                except (KeyError, ValueError):
                    pop = 0
                runs[row["horse_id"]].append((date_ord, race_date, rank, field_size, pop))
                if race_date > max_date:
                    max_date = race_date
    history: dict[str, list[tuple[int, int, int, int]]] = {}
    for horse_id, items in runs.items():
        items.sort()
        history[horse_id] = [(d, r, f, p) for d, _, r, f, p in items[-6:]]
    return history, max_date


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Flag runners matching paper-trade candidate form cells. Observation only, never a BUY signal."
    )
    parser.add_argument("--race-date", required=True)
    parser.add_argument("--races", required=True)
    parser.add_argument("--starts", required=True)
    parser.add_argument("--odds", required=True, help="normalized odds CSV (win rows used)")
    parser.add_argument(
        "--history",
        nargs="+",
        default=["data/model/target_win_training_2004_2025.csv", "data/model/win_training_minimal.csv"],
        help="result CSVs used to build horse history (later files fill recent months)",
    )
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    history, history_max_date = build_history([Path(p) for p in args.history])
    if history_max_date < args.race_date:
        gap_note = f"history_ends_{history_max_date}"
    else:
        gap_note = ""

    race_rows = {row["race_id"]: row for row in read_csv(Path(args.races)) if row["race_date"] == args.race_date}
    starts_by_race = group_by_race([row for row in read_csv(Path(args.starts)) if row["race_date"] == args.race_date])
    win_lookup = latest_odds(read_csv(Path(args.odds)), "win")

    date_ord = parse_date(args.race_date)
    out_rows = []
    for race_id, starts in sorted(starts_by_race.items()):
        race = race_rows.get(race_id)
        if not race:
            continue
        for start in starts:
            win = win_lookup.get((race_id, start["horse_no"]))
            if not win:
                continue
            try:
                odds = float(win["odds"])
            except ValueError:
                continue
            bucket = odds_bucket(odds)
            h = history.get(start["horse_id"], [])
            if not h:
                continue
            last = h[-1]
            feats = {
                "layoff": layoff_bucket(date_ord - last[0]),
                "last_finish": last_finish_bucket(last[1], last[2]),
                "form3": form3_bucket([(d, r, f) for d, r, f, _ in h]),
                "fav_signal": beaten_fav_bucket(last[3] if last[3] > 0 else None, last[1]),
            }
            for cell in WATCH_CELLS:
                if bucket != cell["odds_bucket"]:
                    continue
                fam_a, fam_b = cell["families"]
                val_a, val_b = cell["values"]
                if feats[fam_a] == val_a and feats[fam_b] == val_b:
                    out_rows.append(
                        {
                            "cell_id": cell["cell_id"],
                            "race_id": race_id,
                            "race_no": race.get("race_no", ""),
                            "post_time": race.get("post_time", ""),
                            "course_code": race.get("course_code", ""),
                            "horse_no": start["horse_no"],
                            "horse_name": start.get("horse_name", ""),
                            "win_odds": win["odds"],
                            "odds_bucket": bucket,
                            "layoff": feats["layoff"],
                            "last_finish": feats["last_finish"],
                            "form3": feats["form3"],
                            "paper_stake_yen": "100",
                            "status": "paper_trade_only",
                            "data_gap": gap_note,
                            "backtest_context": cell["backtest"],
                            "observed_at": win.get("observed_at", ""),
                        }
                    )

    output = Path(args.output) if args.output else Path("outputs/paper_trades") / f"form_watchlist_{args.race_date}.csv"
    output.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "cell_id", "race_id", "race_no", "post_time", "course_code", "horse_no", "horse_name",
        "win_odds", "odds_bucket", "layoff", "last_finish", "form3",
        "paper_stake_yen", "status", "data_gap", "backtest_context", "observed_at",
    ]
    with output.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(out_rows)
    print(f"watchlist_rows={len(out_rows)} history_through={history_max_date} output={output}")


if __name__ == "__main__":
    main()
