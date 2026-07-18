import argparse
import csv
from collections import defaultdict
from pathlib import Path

from predict_historical_win_ev import odds_bucket
from rolling_backtest_race_features import add_market_probabilities
from rolling_backtest_horse_form import (
    Agg,
    beaten_fav_bucket,
    form3_bucket,
    group_races,
    last_finish_bucket,
    layoff_bucket,
    parse_date,
)


COMBO_FAMILIES = [
    ("fav_signal", "layoff"),
    ("fav_signal", "form3"),
    ("last_finish", "layoff"),
    ("form3", "layoff"),
    ("last_finish", "form3"),
]

# focus on the odds range where single-feature edges concentrated
TARGET_BUCKETS = {"04_5-10", "05_10-20", "06_20-50", "07_50-100"}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Rolling no-leakage backtest for pairwise horse-form feature interactions."
    )
    parser.add_argument("--input", default="data/model/target_win_training_2004_2025.csv")
    parser.add_argument("--eval-start", default="20050101")
    parser.add_argument("--output-dir", default="outputs/backtests/horse_form")
    parser.add_argument("--min-cell-count", type=int, default=1000)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    history: dict[str, list[tuple[int, int, int, int]]] = defaultdict(list)
    total_aggs: dict[tuple[str, str, str, str], Agg] = defaultdict(Agg)
    year_aggs: dict[tuple[str, str, str, str, str], Agg] = defaultdict(Agg)

    races = 0
    for race_id, rows in group_races(Path(args.input)):
        races += 1
        race_date = rows[0]["race_date"]
        date_ord = parse_date(race_date)
        field_size = len(rows)

        ok, _ = add_market_probabilities(rows)
        feats_rows = []
        for row in rows:
            h = history.get(row["horse_id"], [])
            if h:
                last = h[-1]
                feats = {
                    "layoff": layoff_bucket(date_ord - last[0]),
                    "last_finish": last_finish_bucket(last[1], last[2]),
                    "form3": form3_bucket([(d, r, f) for d, r, f, _ in h]),
                    "fav_signal": beaten_fav_bucket(last[3] if last[3] > 0 else None, last[1]),
                }
            else:
                feats = {"layoff": "first_start", "last_finish": "none", "form3": "unknown", "fav_signal": "none"}
            feats_rows.append(feats)

        if ok and race_date >= args.eval_start:
            year = race_date[:4]
            for row, feats in zip(rows, feats_rows):
                try:
                    odds = float(row["win_odds"])
                    won = int(row["label_win"])
                    mp = float(row["market_probability"])
                except (KeyError, ValueError):
                    continue
                bucket = odds_bucket(odds)
                if bucket not in TARGET_BUCKETS:
                    continue
                for fam_a, fam_b in COMBO_FAMILIES:
                    key = (f"{fam_a}*{fam_b}", f"{feats[fam_a]}|{feats[fam_b]}", bucket)
                    total_aggs[(*key,)].update(mp, won, odds)
                    year_aggs[(*key, year)].update(mp, won, odds)

        for row in rows:
            try:
                rank = int(row["finish_rank"])
            except ValueError:
                continue
            if rank <= 0:
                continue
            try:
                pop = int(row["win_popularity"])
            except ValueError:
                pop = 0
            history[row["horse_id"]].append((date_ord, rank, field_size, pop))
            if len(history[row["horse_id"]]) > 6:
                history[row["horse_id"]] = history[row["horse_id"]][-6:]

    out_rows = []
    for (family, value, bucket), agg in total_aggs.items():
        if agg.count < args.min_cell_count or agg.expected <= 0:
            continue
        years = [
            ya
            for (f2, v2, b2, _), ya in year_aggs.items()
            if f2 == family and v2 == value and b2 == bucket and ya.expected > 0 and ya.count >= 30
        ]
        pos = sum(1 for ya in years if ya.wins / ya.expected > 1.0)
        roi_pos = sum(1 for ya in years if ya.count and ya.ret / ya.count > 1.0)
        out_rows.append(
            {
                "combo": family,
                "value": value,
                "odds_bucket": bucket,
                "count": str(agg.count),
                "wins": str(agg.wins),
                "edge_vs_market": f"{agg.wins / agg.expected:.4f}",
                "flat_roi": f"{agg.ret / agg.count:.4f}",
                "years": str(len(years)),
                "years_edge_positive": str(pos),
                "years_roi_positive": str(roi_pos),
            }
        )

    out_rows.sort(key=lambda r: -float(r["flat_roi"]))
    report_path = output_dir / "form_combo_edges.csv"
    with report_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(out_rows[0].keys()))
        writer.writeheader()
        writer.writerows(out_rows)

    print(f"races={races} cells={len(out_rows)} output={report_path}")
    print("top by flat ROI (n>=1000):")
    for row in out_rows[:15]:
        print(
            f"  {row['combo']} {row['value']} odds={row['odds_bucket']} n={row['count']} "
            f"edge={row['edge_vs_market']} roi={row['flat_roi']} "
            f"roi+years={row['years_roi_positive']}/{row['years']} edge+years={row['years_edge_positive']}/{row['years']}"
        )


if __name__ == "__main__":
    main()
